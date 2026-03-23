from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Tuple


STOPWORDS = {
    "a",
    "another",
    "an",
    "the",
    "and",
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
    "if",
    "in",
    "from",
    "for",
    "have",
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
    "too",
    "through",
    "to",
    "using",
    "used",
    "whether",
    "when",
    "where",
    "which",
    "while",
    "with",
    "yes",
    "your",
    "was",
    "were",
    "about",
    "also",
    "data",
    "what",
    "will",
}

GENERIC_TERMS = {
    "analysis",
    "answer",
    "answers",
    "chapter",
    "concept",
    "concepts",
    "context",
    "day",
    "days",
    "definition",
    "definitions",
    "detail",
    "details",
    "derivation",
    "derivations",
    "document",
    "documents",
    "example",
    "examples",
    "file",
    "files",
    "foundation",
    "foundations",
    "idea",
    "ideas",
    "item",
    "items",
    "note",
    "notes",
    "overview",
    "page",
    "pages",
    "point",
    "points",
    "problem",
    "problems",
    "question",
    "questions",
    "recommendation",
    "recommendations",
    "revision",
    "section",
    "sections",
    "step",
    "steps",
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
    "json",
    "llm",
    "mse",
    "os",
    "pdf",
    "rag",
    "tcp",
    "udp",
    "yaml",
}


def _canonical_token(token: str) -> str:
    token = re.sub(r"[^A-Za-z0-9+\-]", "", token).lower()
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]
    return token


def _clean_term(term: str) -> str:
    cleaned = re.sub(r"[_/]+", " ", term.strip())
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


def _term_kind(term: str) -> str:
    words = term.lower().split()
    if any(word in ACRONYM_TERMS for word in words):
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
            record(line.split(":", 1)[0], 2.2)

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
                    record(" ".join(original_tokens[start : start + size]), 1.2 + (0.55 * size))

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

    def _extract_terms(self, text: str) -> List[Tuple[str, str]]:
        if self._nlp is None:
            return [(term, _term_kind(term)) for term in _simple_keywords(text)]

        doc = self._nlp(text[:8000])
        terms: List[Tuple[str, str]] = []
        seen = set()
        for ent in doc.ents:
            label = "other"
            if ent.label_ == "PERSON":
                label = "person"
            elif ent.label_ in {"ORG", "PRODUCT", "EVENT", "WORK_OF_ART"}:
                label = "project"
            elif ent.label_ in {"NORP", "GPE", "LOC"}:
                label = "topic"
            value = _clean_term(ent.text)
            canonical = _canonical_term(value)
            key = (canonical, label)
            if canonical and _is_meaningful_term(canonical) and key not in seen:
                seen.add(key)
                terms.append((_display_term(value), label))

        noun_chunks = []
        for chunk in doc.noun_chunks:
            value = _clean_term(chunk.text)
            canonical = _canonical_term(value)
            if canonical and _is_meaningful_term(canonical):
                noun_chunks.append(value)
        for value in noun_chunks[:10]:
            canonical = _canonical_term(value)
            key = (canonical, "topic")
            if key not in seen:
                seen.add(key)
                terms.append((_display_term(value), "topic"))

        return terms[:16]

    def build_graph(self, chunks: List[Dict]) -> Dict[str, List[Dict]]:
        node_map: Dict[str, Dict] = {}
        node_mentions: Counter[str] = Counter()
        edge_map = defaultdict(set)

        def add_node(node_id: str, label: str, node_type: str) -> None:
            if node_id not in node_map:
                node_map[node_id] = {"id": node_id, "label": label, "type": node_type}

        for chunk in chunks:
            source_file = chunk.get("source_file", "unknown")
            doc_id = f"doc:{source_file}"
            add_node(doc_id, source_file, "doc")
            node_mentions[doc_id] += 1

            terms = self._extract_terms(chunk.get("text", ""))
            term_ids: List[str] = []
            for term, ttype in terms:
                canonical = _canonical_term(term)
                if not canonical:
                    continue
                tid = f"{ttype}:{canonical}"
                add_node(tid, term, ttype if ttype in {"topic", "person", "project", "doc", "other"} else "other")
                edge_map[(doc_id, tid, "mentions")].add(chunk.get("chunk_id"))
                term_ids.append(tid)
                node_mentions[tid] += 1

            for i in range(min(len(term_ids), 7)):
                for j in range(i + 1, min(len(term_ids), 7)):
                    if term_ids[i] != term_ids[j]:
                        a, b = sorted((term_ids[i], term_ids[j]))
                        edge_map[(a, b, "related_to")].add(chunk.get("chunk_id"))

        edges = [
            {"source": s, "target": t, "relation": r, "weight": len(chunk_ids)}
            for (s, t, r), chunk_ids in edge_map.items()
        ]
        edges.sort(key=lambda edge: (edge["relation"], edge["weight"], edge["source"], edge["target"]), reverse=True)

        degree_counter: Counter[str] = Counter()
        for edge in edges:
            degree_counter[edge["source"]] += 1
            degree_counter[edge["target"]] += 1

        nodes = []
        for node_id, node in node_map.items():
            node_copy = dict(node)
            node_copy["mentions"] = int(node_mentions.get(node_id, 0))
            node_copy["degree"] = int(degree_counter.get(node_id, 0))
            nodes.append(node_copy)
        nodes.sort(key=lambda node: (node["type"], node["mentions"], node["degree"], node["label"]), reverse=True)
        return {"nodes": nodes, "edges": edges}
