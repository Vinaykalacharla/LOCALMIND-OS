from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence


CHUNKING_VERSION = "structured-v3"

ATX_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
SETEXT_HEADING_RE = re.compile(r"^\s*(=+|-{3,})\s*$")
LIST_ITEM_RE = re.compile(r"^\s*((?:[-*+])|(?:(?:\d+|[A-Za-z])[.)]))\s+(.*)$")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
INLINE_WHITESPACE_RE = re.compile(r"[ \t]+")


@dataclass
class ChunkSegment:
    text: str
    section_path: List[str]
    block_kind: str


@dataclass
class StructuredBlock:
    text: str
    section_path: List[str]
    block_kind: str


def _normalize_inline_whitespace(text: str) -> str:
    return INLINE_WHITESPACE_RE.sub(" ", text).strip()


def _split_by_words(text: str, chunk_size: int) -> List[str]:
    words = text.split()
    if not words:
        return []

    pieces: List[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        pieces.append(current)
        current = word
    if current:
        pieces.append(current)
    return pieces


def _split_paragraph_units(text: str, chunk_size: int) -> List[str]:
    normalized = _normalize_inline_whitespace(text)
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    sentences = [part.strip() for part in SENTENCE_SPLIT_RE.split(normalized) if part.strip()]
    if len(sentences) <= 1:
        return _split_by_words(normalized, chunk_size)

    units: List[str] = []
    current = ""
    for sentence in sentences:
        smaller_parts = [sentence]
        if len(sentence) > chunk_size:
            smaller_parts = _split_by_words(sentence, chunk_size)
        for part in smaller_parts:
            if not current:
                current = part
                continue
            candidate = f"{current} {part}"
            if len(candidate) <= chunk_size:
                current = candidate
                continue
            units.append(current)
            current = part
    if current:
        units.append(current)
    return units


def _normalize_list_lines(lines: Sequence[str]) -> List[str]:
    items: List[str] = []
    current_marker = "-"
    current_body_parts: List[str] = []

    def flush_item() -> None:
        if not current_body_parts:
            return
        body = _normalize_inline_whitespace(" ".join(current_body_parts))
        if body:
            items.append(f"{current_marker} {body}")

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip():
            flush_item()
            current_body_parts = []
            continue

        match = LIST_ITEM_RE.match(line.strip())
        if match:
            flush_item()
            current_marker = match.group(1)
            current_body_parts = [match.group(2)]
            continue

        if not current_body_parts:
            current_marker = "-"
            current_body_parts = [line.strip()]
            continue

        current_body_parts.append(line.strip())

    flush_item()
    return items


def _split_list_units(text: str, chunk_size: int) -> List[str]:
    items = [item.strip() for item in text.splitlines() if item.strip()]
    if not items:
        return []

    units: List[str] = []
    current = ""
    for item in items:
        item_variants = [item]
        if len(item) > chunk_size:
            marker_match = LIST_ITEM_RE.match(item)
            marker = "-"
            body = item
            if marker_match:
                marker = marker_match.group(1)
                body = marker_match.group(2)
            item_variants = [f"{marker} {part}" for part in _split_paragraph_units(body, max(80, chunk_size - len(marker) - 1))]

        for variant in item_variants:
            if not current:
                current = variant
                continue
            candidate = f"{current}\n{variant}"
            if len(candidate) <= chunk_size:
                current = candidate
                continue
            units.append(current)
            current = variant

    if current:
        units.append(current)
    return units


def _set_heading_path(current: Sequence[str], level: int, title: str) -> List[str]:
    normalized_title = _normalize_inline_whitespace(title)
    trimmed = list(current[: max(0, level - 1)])
    trimmed.append(normalized_title)
    return trimmed


def _render_section_prefix(section_path: Sequence[str]) -> str:
    if not section_path:
        return ""
    return f"Section: {' > '.join(section_path)}\n"


def _tail_overlap_paragraph(text: str, overlap: int) -> str:
    if overlap <= 0:
        return ""
    normalized = _normalize_inline_whitespace(text)
    if not normalized:
        return ""
    if len(normalized) <= overlap:
        return normalized

    sentences = [part.strip() for part in SENTENCE_SPLIT_RE.split(normalized) if part.strip()]
    if len(sentences) > 1:
        chosen: List[str] = []
        total = 0
        for sentence in reversed(sentences):
            addition = len(sentence) + (1 if chosen else 0)
            if total + addition > overlap:
                break
            chosen.insert(0, sentence)
            total += addition
        if chosen:
            return " ".join(chosen)

    words = normalized.split()
    chosen_words: List[str] = []
    total = 0
    for word in reversed(words):
        addition = len(word) + (1 if chosen_words else 0)
        if chosen_words and total + addition > overlap:
            break
        chosen_words.insert(0, word)
        total += addition
    return " ".join(chosen_words)


def _tail_overlap_list(text: str, overlap: int) -> str:
    if overlap <= 0:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""

    chosen: List[str] = []
    total = 0
    for line in reversed(lines):
        addition = len(line) + (1 if chosen else 0)
        if total + addition > overlap:
            break
        chosen.insert(0, line)
        total += addition
    return "\n".join(chosen)


def _block_to_units(block: StructuredBlock, chunk_size: int, overlap: int) -> List[ChunkSegment]:
    prefix = _render_section_prefix(block.section_path)
    available = max(80, chunk_size - len(prefix))

    if block.block_kind == "list":
        units = _split_list_units(block.text, available)
        overlap_builder = _tail_overlap_list
        separator = "\n"
    else:
        units = _split_paragraph_units(block.text, available)
        overlap_builder = _tail_overlap_paragraph
        separator = " "

    segments: List[ChunkSegment] = []
    previous_unit = ""
    overlap_budget = min(overlap, max(60, available // 3))

    for unit in units:
        overlap_prefix = ""
        if previous_unit and overlap_budget > 0:
            allowed_prefix = max(0, available - len(unit) - len(separator))
            if allowed_prefix > 0:
                overlap_prefix = overlap_builder(previous_unit, min(overlap_budget, allowed_prefix))

        body = unit
        if overlap_prefix and overlap_prefix != unit:
            body = f"{overlap_prefix}{separator}{unit}"

        text = f"{prefix}{body}" if prefix else body
        segments.append(ChunkSegment(text=text, section_path=list(block.section_path), block_kind=block.block_kind))
        previous_unit = unit

    return segments


def _parse_structured_blocks(text: str) -> List[StructuredBlock]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: List[StructuredBlock] = []
    section_path: List[str] = []
    paragraph_lines: List[str] = []
    index = 0

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if not paragraph_lines:
            return
        paragraph = _normalize_inline_whitespace(" ".join(line.strip() for line in paragraph_lines if line.strip()))
        if paragraph:
            blocks.append(StructuredBlock(text=paragraph, section_path=list(section_path), block_kind="paragraph"))
        paragraph_lines = []

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        next_line = lines[index + 1] if index + 1 < len(lines) else ""

        if not stripped:
            flush_paragraph()
            index += 1
            continue

        atx_match = ATX_HEADING_RE.match(line)
        if atx_match:
            flush_paragraph()
            section_path = _set_heading_path(section_path, len(atx_match.group(1)), atx_match.group(2))
            index += 1
            continue

        if stripped and next_line.strip() and SETEXT_HEADING_RE.match(next_line.strip()):
            flush_paragraph()
            underline = next_line.strip()
            level = 1 if underline.startswith("=") else 2
            section_path = _set_heading_path(section_path, level, stripped)
            index += 2
            continue

        if LIST_ITEM_RE.match(stripped):
            flush_paragraph()
            list_lines = [line]
            index += 1
            while index < len(lines):
                candidate = lines[index]
                candidate_stripped = candidate.strip()
                following = lines[index + 1] if index + 1 < len(lines) else ""
                if not candidate_stripped:
                    break
                if ATX_HEADING_RE.match(candidate) or (candidate_stripped and following.strip() and SETEXT_HEADING_RE.match(following.strip())):
                    break
                list_lines.append(candidate)
                index += 1

            normalized_items = _normalize_list_lines(list_lines)
            if normalized_items:
                blocks.append(
                    StructuredBlock(
                        text="\n".join(normalized_items),
                        section_path=list(section_path),
                        block_kind="list",
                    )
                )
            continue

        paragraph_lines.append(line)
        index += 1

    flush_paragraph()
    return blocks


def chunk_document(text: str, chunk_size: int = 900, overlap: int = 150) -> List[ChunkSegment]:
    if not text:
        return []
    if chunk_size <= 0:
        chunk_size = 900
    if overlap < 0:
        overlap = 0

    cleaned = text.replace("\r\n", "\n").strip()
    if not cleaned:
        return []

    blocks = _parse_structured_blocks(cleaned)
    if not blocks:
        return [ChunkSegment(text=piece, section_path=[], block_kind="paragraph") for piece in _split_paragraph_units(cleaned, chunk_size)]

    segments: List[ChunkSegment] = []
    for block in blocks:
        segments.extend(_block_to_units(block, chunk_size, overlap))
    return segments


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> List[str]:
    return [segment.text for segment in chunk_document(text, chunk_size=chunk_size, overlap=overlap)]
