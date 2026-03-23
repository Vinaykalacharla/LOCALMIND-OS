from __future__ import annotations

import re
from typing import List


PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
WHITESPACE_RE = re.compile(r"\s+")


def _normalize_block(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


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


def _split_long_block(text: str, chunk_size: int) -> List[str]:
    normalized = _normalize_block(text)
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    sentences = [part.strip() for part in SENTENCE_SPLIT_RE.split(normalized) if part.strip()]
    if len(sentences) <= 1:
        return _split_by_words(normalized, chunk_size)

    pieces: List[str] = []
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
            pieces.append(current)
            current = part
    if current:
        pieces.append(current)
    return pieces


def _tail_overlap(text: str, overlap: int) -> str:
    if overlap <= 0 or not text:
        return ""
    if len(text) <= overlap:
        return text.strip()
    tail = text[-overlap:].strip()
    first_space = tail.find(" ")
    if first_space > 0:
        tail = tail[first_space + 1 :]
    return tail.strip()


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> List[str]:
    """Split text into paragraph-aware chunks with sentence and word fallback."""
    if not text:
        return []
    if chunk_size <= 0:
        chunk_size = 900
    if overlap < 0:
        overlap = 0
    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 4)

    cleaned = text.replace("\r\n", "\n").strip()
    if not cleaned:
        return []

    blocks = [_normalize_block(block) for block in PARAGRAPH_SPLIT_RE.split(cleaned)]
    pieces: List[str] = []
    for block in blocks:
        if not block:
            continue
        pieces.extend(_split_long_block(block, chunk_size))
    if not pieces:
        return []

    chunks: List[str] = []
    current = ""
    for piece in pieces:
        if not current:
            current = piece
            continue
        candidate = f"{current} {piece}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        emitted = current.strip()
        if emitted:
            chunks.append(emitted)

        overlap_text = _tail_overlap(emitted, overlap)
        if overlap_text:
            candidate = f"{overlap_text} {piece}"
            current = candidate if len(candidate) <= chunk_size else piece
        else:
            current = piece

    if current.strip():
        chunks.append(current.strip())
    return chunks
