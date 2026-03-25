from __future__ import annotations

import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


STOPWORDS = {
    "a",
    "about",
    "also",
    "an",
    "and",
    "another",
    "are",
    "as",
    "at",
    "based",
    "be",
    "but",
    "by",
    "can",
    "cannot",
    "does",
    "done",
    "each",
    "for",
    "from",
    "have",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "mean",
    "means",
    "more",
    "most",
    "must",
    "next",
    "no",
    "of",
    "on",
    "only",
    "or",
    "such",
    "than",
    "that",
    "their",
    "them",
    "then",
    "there",
    "they",
    "this",
    "those",
    "through",
    "to",
    "used",
    "using",
    "was",
    "were",
    "what",
    "when",
    "where",
    "whether",
    "which",
    "while",
    "will",
    "with",
    "yes",
    "your",
}

GENERIC_TERMS = {
    "analysis",
    "answer",
    "answers",
    "appendix",
    "chapter",
    "check",
    "checks",
    "concept",
    "concepts",
    "context",
    "day",
    "days",
    "definition",
    "definitions",
    "detail",
    "details",
    "document",
    "documents",
    "example",
    "examples",
    "exercise",
    "exercises",
    "file",
    "files",
    "foundation",
    "foundations",
    "idea",
    "ideas",
    "introduction",
    "item",
    "items",
    "lesson",
    "lessons",
    "module",
    "modules",
    "note",
    "notes",
    "objective",
    "objectives",
    "overview",
    "page",
    "pages",
    "paragraph",
    "paragraphs",
    "part",
    "parts",
    "point",
    "points",
    "problem",
    "problems",
    "question",
    "questions",
    "recommendation",
    "recommendations",
    "reference",
    "references",
    "revision",
    "section",
    "sections",
    "step",
    "steps",
    "subject",
    "subjects",
    "summary",
    "solution",
    "solutions",
    "takeaway",
    "topic",
    "topics",
    "unit",
}

ACRONYM_TERMS = {
    "api",
    "cpu",
    "faiss",
    "gguf",
    "gpu",
    "http",
    "https",
    "json",
    "llm",
    "mse",
    "os",
    "pdf",
    "rag",
    "sql",
    "tcp",
    "udp",
    "yaml",
}

PROJECT_HINTS = {
    "agent",
    "api",
    "app",
    "engine",
    "framework",
    "graph",
    "index",
    "model",
    "os",
    "pipeline",
    "platform",
    "process",
    "protocol",
    "search",
    "service",
    "stack",
    "studio",
    "system",
    "workflow",
}

TYPE_PRIORITY = {"doc": 0, "project": 1, "topic": 2, "person": 3, "other": 4}
PERSON_JOINERS = {"da", "de", "del", "di", "la", "van", "von"}
CAPITALIZED_PHRASE_RE = re.compile(
    r"\b(?:[A-Z][a-z0-9]+|[A-Z]{2,}|[A-Za-z]+[A-Z][A-Za-z0-9]*)(?:\s+(?:[A-Z][a-z0-9]+|[A-Z]{2,}|[A-Za-z]+[A-Z][A-Za-z0-9]*)){0,2}\b"
)


@dataclass(frozen=True)
class TermCandidate:
    canonical: str
    label: str
    node_type: str
    score: float
    origin: str


def _canonical_token(token: str) -> str:
    token = re.sub(r"[^A-Za-z0-9+\-]", "", token).lower()
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]
    return token


def _clean_term(term: str) -> str:
    cleaned = re.sub(r"[_/]+", " ", term.strip())
    cleaned = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -:;,.")


def _canonical_term(term: str) -> str:
    tokens = [_canonical_token(token) for token in _clean_term(term).split()]
    tokens = [token for token in tokens if token]
    return " ".join(tokens)


def _display_term(term: str) -> str:
    words = []
    for raw in _clean_term(term).split():
        lower = raw.lower()
        if lower in ACRONYM_TERMS:
            words.append(lower.upper())
        elif raw.isupper():
            words.append(raw)
        else:
            words.append(raw.capitalize())
    return " ".join(words)


def _is_meaningful_term(term: str) -> bool:
    words = [word for word in term.split() if word]
    if not words or len(term) < 4 or len(term) > 72:
        return False
    if words[0] in STOPWORDS or words[-1] in STOPWORDS:
        return False
    if words[0] in GENERIC_TERMS or words[-1] in GENERIC_TERMS:
        return False
    if all(word in STOPWORDS or word in GENERIC_TERMS for word in words):
        return False
    if len(words) == 1 and (words[0] in STOPWORDS or words[0] in GENERIC_TERMS or len(words[0]) < 4):
        return False
    if any(len(word) == 1 and word not in ACRONYM_TERMS for word in words):
        return False
    return True


def _looks_like_person(term: str) -> bool:
    words = [word for word in _clean_term(term).split() if word]
    if not 2 <= len(words) <= 3:
        return False
    capitalized_words = 0
    for word in words:
        lowered = word.lower()
        if lowered in PERSON_JOINERS:
            continue
        if lowered in ACRONYM_TERMS or lowered in PROJECT_HINTS:
            return False
        if not (word[0].isupper() and word[1:].islower()):
            return False
        capitalized_words += 1
    return capitalized_words >= 2


def _term_kind(term: str) -> str:
    if _looks_like_person(term):
        return "person"
    words = _canonical_term(term).split()
    if any(word in ACRONYM_TERMS or word in PROJECT_HINTS for word in words):
        return "project"
    return "topic"


def _simple_keywords(text: str, top_n: int = 8) -> List[str]:
    scores: Counter[str] = Counter()
    surface_forms: Dict[str, str] = {}

    def record(term: str, weight: float) -> None:
        canonical = _canonical_term(term)
        if not _is_meaningful_term(canonical):
            return
        scores[canonical] += weight
        surface_forms.setdefault(canonical, _display_term(term))

    stripped_lines = []
    for raw in text.splitlines():
        line = re.sub(r"^[#>\-\*\d\.\)\s]+", "", raw).strip()
        if line:
            stripped_lines.append(_clean_term(line))

    for line in stripped_lines[:120]:
        if 4 <= len(line) <= 80:
            record(line, 2.5 if len(line.split()) <= 6 else 1.5)
        if ":" in line:
            record(line.split(":", 1)[0], 2.1)

    for line in stripped_lines[:160]:
        original_tokens = re.findall(r"[A-Za-z][A-Za-z0-9+\-]{1,}", line)
        canonical_tokens = [_canonical_token(token) for token in original_tokens]
        if 2 <= len(original_tokens) <= 14:
            for size in (3, 2):
                for start in range(0, max(0, len(canonical_tokens) - size + 1)):
                    window = canonical_tokens[start : start + size]
                    if any(not token or token in STOPWORDS for token in window):
                        continue
                    if any(token in GENERIC_TERMS for token in window):
                        continue
                    record(" ".join(original_tokens[start : start + size]), 1.15 + (0.52 * size))

        for original, canonical in zip(original_tokens, canonical_tokens):
            if not canonical or canonical in STOPWORDS or canonical in GENERIC_TERMS:
                continue
            record(original, 0.25 if len(original_tokens) > 10 else 0.35)

    ranked = sorted(
        scores.items(),
        key=lambda item: (item[1], len(item[0].split()), len(item[0])),
        reverse=True,
    )

    selected: List[str] = []
    selected_tokens: List[set[str]] = []
    for canonical, _score in ranked:
        token_set = set(canonical.split())
        if any(token_set <= existing or existing <= token_set for existing in selected_tokens):
            continue
        selected.append(surface_forms.get(canonical, _display_term(canonical)))
        selected_tokens.append(token_set)
        if len(selected) >= top_n:
            break
    return selected


def _pattern_entity_candidates(text: str, top_n: int = 8) -> List[Tuple[str, str, float]]:
    counts: Counter[str] = Counter()
    labels: Dict[str, str] = {}
    types: Dict[str, str] = {}

    for match in CAPITALIZED_PHRASE_RE.finditer(text[:8000]):
        raw = _clean_term(match.group(0))
        canonical = _canonical_term(raw)
        if not _is_meaningful_term(canonical):
            continue
        node_type = _term_kind(raw)
        counts[canonical] += 1
        labels.setdefault(canonical, _display_term(raw))
        if types.get(canonical) != "person":
            types[canonical] = node_type

    ranked = sorted(
        counts.items(),
        key=lambda item: (item[1], len(item[0].split()), len(item[0])),
        reverse=True,
    )

    candidates: List[Tuple[str, str, float]] = []
    for canonical, count in ranked[:top_n]:
        node_type = types.get(canonical, "topic")
        base = 1.95 if node_type in {"person", "project"} else 1.45
        score = min(2.55, base + (0.18 * (count - 1)))
        candidates.append((labels.get(canonical, _display_term(canonical)), node_type, score))
    return candidates


def _list_heading_candidates(text: str, top_n: int = 4) -> List[Tuple[str, str, float]]:
    candidates: List[Tuple[str, str, float]] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = re.sub(r"^(?:[-*]|\d+[.)])\s*", "", raw).strip()
        if not line:
            continue
        if ":" in line:
            line = line.split(":", 1)[0]
        line = _clean_term(line)
        canonical = _canonical_term(line)
        if canonical in seen or not _is_meaningful_term(canonical):
            continue
        seen.add(canonical)
        candidates.append((_display_term(line), _term_kind(line), 1.55))
        if len(candidates) >= top_n:
            break
    return candidates


def _choose_label(label_scores: Counter[str]) -> str:
    if not label_scores:
        return ""
    return max(label_scores.items(), key=lambda item: (item[1], len(item[0]), item[0]))[0]


class GraphBuilder:
    def __init__(self) -> None:
        self._nlp = None
        self.mode = "heuristic-fallback"
        self._load_spacy()

    def _load_spacy(self) -> None:
        if sys.version_info >= (3, 14):
            self._nlp = None
            self.mode = "python-3.14-fallback"
            return
        try:
            import spacy  # type: ignore

            self._nlp = spacy.load("en_core_web_sm")
            self.mode = "spacy"
        except Exception:
            self._nlp = None
            self.mode = "heuristic-fallback"

    def _register_candidate(
        self,
        seen: Dict[str, TermCandidate],
        *,
        term: str,
        node_type: str,
        score: float,
        origin: str,
    ) -> None:
        canonical = _canonical_term(term)
        if not canonical or not _is_meaningful_term(canonical):
            return

        normalized_type = node_type if node_type in TYPE_PRIORITY else _term_kind(term)
        candidate = TermCandidate(
            canonical=canonical,
            label=_display_term(term),
            node_type=normalized_type,
            score=score,
            origin=origin,
        )

        existing = seen.get(canonical)
        if existing is None:
            seen[canonical] = candidate
            return

        merged_score = min(5.0, existing.score + (score * 0.35))
        if score > existing.score or (score == existing.score and len(candidate.label) > len(existing.label)):
            seen[canonical] = TermCandidate(
                canonical=canonical,
                label=candidate.label,
                node_type=candidate.node_type,
                score=merged_score,
                origin=origin,
            )
        else:
            seen[canonical] = TermCandidate(
                canonical=canonical,
                label=existing.label,
                node_type=existing.node_type,
                score=merged_score,
                origin=existing.origin,
            )

    def _spacy_candidates(self, text: str) -> List[Tuple[str, str, float]]:
        if self._nlp is None:
            return []

        doc = self._nlp(text[:8000])
        candidates: List[Tuple[str, str, float]] = []
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                node_type = "person"
                score = 2.55
            elif ent.label_ in {"ORG", "PRODUCT", "EVENT", "WORK_OF_ART"}:
                node_type = "project"
                score = 2.25
            elif ent.label_ in {"NORP", "GPE", "LOC"}:
                node_type = "topic"
                score = 1.85
            else:
                node_type = "other"
                score = 1.55
            candidates.append((ent.text, node_type, score))

        for chunk in list(doc.noun_chunks)[:14]:
            candidates.append((chunk.text, "topic", 1.05))
        return candidates

    def _extract_term_candidates(self, chunk: Dict) -> List[TermCandidate]:
        seen: Dict[str, TermCandidate] = {}
        text = str(chunk.get("text") or "")
        source_file = str(chunk.get("source_file") or "")
        block_kind = str(chunk.get("block_kind") or "")
        section_path = chunk.get("section_path") or []

        source_label = _clean_term(Path(source_file).stem)
        if source_label:
            self._register_candidate(seen, term=source_label, node_type=_term_kind(source_label), score=2.2, origin="source")

        if isinstance(section_path, Sequence) and not isinstance(section_path, str):
            for depth, item in enumerate(section_path[:4]):
                section = str(item or "").strip()
                if not section:
                    continue
                section_score = max(2.1, 2.9 - (depth * 0.25))
                self._register_candidate(
                    seen,
                    term=section,
                    node_type=_term_kind(section),
                    score=section_score,
                    origin="section",
                )

        if block_kind == "list":
            for term, node_type, score in _list_heading_candidates(text):
                self._register_candidate(seen, term=term, node_type=node_type, score=score, origin="list")

        extraction_candidates = self._spacy_candidates(text) if self._nlp is not None else _pattern_entity_candidates(text)
        for term, node_type, score in extraction_candidates:
            self._register_candidate(seen, term=term, node_type=node_type, score=score, origin="entity")

        for index, term in enumerate(_simple_keywords(text, top_n=8)):
            self._register_candidate(
                seen,
                term=term,
                node_type=_term_kind(term),
                score=max(0.95, 2.05 - (index * 0.16)),
                origin="keyword",
            )

        return sorted(seen.values(), key=lambda item: (item.score, len(item.label.split()), len(item.label)), reverse=True)[:12]

    def _keep_term_node(
        self,
        *,
        node_type: str,
        total_score: float,
        chunk_count: int,
        doc_freq: int,
        importance: float,
    ) -> bool:
        if total_score <= 0.0:
            return False
        if node_type == "person":
            return total_score >= 1.6 or chunk_count >= 2
        if node_type == "project":
            return total_score >= 1.4 or doc_freq >= 2 or importance >= 2.6
        if doc_freq >= 2 and importance >= 2.4:
            return True
        if chunk_count >= 3 and importance >= 2.6:
            return True
        return importance >= 3.4 and not (node_type == "topic" and chunk_count == 1 and total_score < 2.6)

    def build_graph(self, chunks: List[Dict]) -> Dict[str, List[Dict]]:
        node_map: Dict[str, Dict] = {}
        node_mentions: Counter[str] = Counter()
        term_score_totals: Counter[str] = Counter()
        term_chunk_counts: Counter[str] = Counter()
        term_docs: Dict[str, set[str]] = defaultdict(set)
        label_scores: Dict[str, Counter[str]] = defaultdict(Counter)
        doc_term_scores: Dict[str, Counter[str]] = defaultdict(Counter)
        doc_term_origins: Dict[str, Dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        term_term_scores: Counter[Tuple[str, str, str]] = Counter()
        term_term_chunks: Dict[Tuple[str, str, str], set[str]] = defaultdict(set)

        def add_node(node_id: str, label: str, node_type: str) -> None:
            if node_id not in node_map:
                node_map[node_id] = {"id": node_id, "label": label, "type": node_type}

        for chunk in chunks:
            source_file = str(chunk.get("source_file") or "unknown")
            chunk_id = str(chunk.get("chunk_id") or f"{source_file}:{len(doc_term_scores[source_file])}")
            doc_id = f"doc:{source_file}"
            add_node(doc_id, source_file, "doc")
            node_mentions[doc_id] += 1

            local_candidates = self._extract_term_candidates(chunk)
            local_terms: List[Tuple[str, float, str]] = []
            for candidate in local_candidates:
                term_id = f"{candidate.node_type}:{candidate.canonical}"
                add_node(term_id, candidate.label, candidate.node_type)
                label_scores[term_id][candidate.label] += candidate.score
                term_score_totals[term_id] += candidate.score
                term_chunk_counts[term_id] += 1
                term_docs[term_id].add(doc_id)
                doc_term_scores[doc_id][term_id] += candidate.score
                doc_term_origins[doc_id][term_id].add(candidate.origin)
                local_terms.append((term_id, candidate.score, candidate.origin))

            for i in range(min(len(local_terms), 6)):
                for j in range(i + 1, min(len(local_terms), 6)):
                    left_id, left_score, left_origin = local_terms[i]
                    right_id, right_score, right_origin = local_terms[j]
                    if left_id == right_id:
                        continue
                    source_id, target_id = sorted((left_id, right_id))
                    weight = (left_score + right_score) / 2.0
                    if "section" in {left_origin, right_origin}:
                        weight *= 1.12
                    if str(chunk.get("block_kind") or "") == "list":
                        weight *= 1.05
                    key = (source_id, target_id, "related_to")
                    term_term_scores[key] += weight
                    term_term_chunks[key].add(chunk_id)

        doc_ids = sorted(node_id for node_id, node in node_map.items() if node["type"] == "doc")
        doc_total = max(1, len(doc_ids))

        term_importance: Dict[str, float] = {}
        for node_id, node in node_map.items():
            if node["type"] == "doc":
                continue
            doc_freq = len(term_docs.get(node_id, set()))
            total_score = float(term_score_totals.get(node_id, 0.0))
            chunk_count = int(term_chunk_counts.get(node_id, 0))
            specificity = 1.0 + math.log1p((doc_total + 1.0) / (doc_freq + 0.75))
            importance = total_score * specificity
            if doc_freq > max(3, int(math.ceil(doc_total * 0.75))) and node["type"] == "topic":
                importance *= 0.72
            term_importance[node_id] = round(importance, 4)

        kept_term_ids = [
            node_id
            for node_id in sorted(
                term_importance,
                key=lambda item: (term_importance[item], term_chunk_counts[item], term_score_totals[item], node_map[item]["label"]),
                reverse=True,
            )
            if self._keep_term_node(
                node_type=node_map[node_id]["type"],
                total_score=float(term_score_totals[node_id]),
                chunk_count=int(term_chunk_counts[node_id]),
                doc_freq=len(term_docs.get(node_id, set())),
                importance=term_importance[node_id],
            )
        ][:72]
        kept_term_set = set(kept_term_ids)

        edges: List[Dict[str, object]] = []

        for doc_id in doc_ids:
            ranked_terms = [
                (term_id, float(score))
                for term_id, score in doc_term_scores.get(doc_id, Counter()).items()
                if term_id in kept_term_set
            ]
            ranked_terms.sort(key=lambda item: (item[1], term_importance.get(item[0], 0.0), item[0]), reverse=True)
            for term_id, score in ranked_terms[:12]:
                relation = "covers" if {"section", "source"} & doc_term_origins[doc_id].get(term_id, set()) or score >= 3.2 else "mentions"
                edges.append(
                    {
                        "source": doc_id,
                        "target": term_id,
                        "relation": relation,
                        "weight": max(1, int(round(score))),
                    }
                )

        doc_doc_edges: List[Dict[str, object]] = []
        for index, left_doc in enumerate(doc_ids):
            left_terms = {term_id for term_id in doc_term_scores.get(left_doc, Counter()) if term_id in kept_term_set}
            for right_doc in doc_ids[index + 1 :]:
                shared_terms = left_terms & {term_id for term_id in doc_term_scores.get(right_doc, Counter()) if term_id in kept_term_set}
                if not shared_terms:
                    continue
                ranked_shared = sorted(
                    shared_terms,
                    key=lambda term_id: (
                        term_importance.get(term_id, 0.0),
                        min(doc_term_scores[left_doc][term_id], doc_term_scores[right_doc][term_id]),
                    ),
                    reverse=True,
                )
                score = 0.0
                for term_id in ranked_shared[:5]:
                    common_strength = min(doc_term_scores[left_doc][term_id], doc_term_scores[right_doc][term_id])
                    score += min(2.4, 0.7 + (term_importance.get(term_id, 0.0) / 3.5)) * max(0.75, common_strength / 2.2)
                if len(ranked_shared) >= 2 or score >= 4.0:
                    doc_doc_edges.append(
                        {
                            "source": left_doc,
                            "target": right_doc,
                            "relation": "shares_topics",
                            "weight": max(1, int(round(score))),
                        }
                    )

        edges.extend(sorted(doc_doc_edges, key=lambda item: (item["weight"], item["source"], item["target"]), reverse=True)[:36])

        term_edges: List[Dict[str, object]] = []
        for (source_id, target_id, relation), score in term_term_scores.items():
            if source_id not in kept_term_set or target_id not in kept_term_set:
                continue
            chunk_hits = len(term_term_chunks[(source_id, target_id, relation)])
            adjusted_score = score * min(1.6, 1.0 + (0.1 * max(0, chunk_hits - 1)))
            if chunk_hits >= 2 or adjusted_score >= 2.5:
                term_edges.append(
                    {
                        "source": source_id,
                        "target": target_id,
                        "relation": relation,
                        "weight": max(1, int(round(adjusted_score))),
                    }
                )

        edges.extend(
            sorted(
                term_edges,
                key=lambda item: (item["weight"], item["source"], item["target"]),
                reverse=True,
            )[:140]
        )

        degree_counter: Counter[str] = Counter()
        for edge in edges:
            degree_counter[str(edge["source"])] += 1
            degree_counter[str(edge["target"])] += 1

        nodes: List[Dict[str, object]] = []
        for doc_id in doc_ids:
            doc_node = dict(node_map[doc_id])
            doc_node["mentions"] = int(node_mentions.get(doc_id, 0))
            doc_node["degree"] = int(degree_counter.get(doc_id, 0))
            nodes.append(doc_node)

        for term_id in kept_term_ids:
            node = dict(node_map[term_id])
            chosen_label = _choose_label(label_scores[term_id])
            if chosen_label:
                node["label"] = chosen_label
            node["mentions"] = int(max(1, round(float(term_score_totals.get(term_id, 0.0)) + (0.25 * len(term_docs.get(term_id, set()))))))
            node["degree"] = int(degree_counter.get(term_id, 0))
            nodes.append(node)

        nodes.sort(
            key=lambda node: (
                TYPE_PRIORITY.get(str(node["type"]), 99),
                -int(node["degree"]),
                -int(node["mentions"]),
                str(node["label"]),
            )
        )
        edges.sort(key=lambda edge: (-int(edge["weight"]), str(edge["relation"]), str(edge["source"]), str(edge["target"])))
        return {"nodes": nodes, "edges": edges}
