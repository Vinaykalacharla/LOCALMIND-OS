from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List


STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "because",
    "control",
    "does",
    "done",
    "each",
    "explain",
    "from",
    "into",
    "make",
    "my",
    "note",
    "notes",
    "plan",
    "point",
    "points",
    "question",
    "questions",
    "show",
    "tell",
    "that",
    "their",
    "them",
    "then",
    "these",
    "they",
    "topic",
    "topics",
    "using",
    "what",
    "with",
    "your",
}


def _read_jsonl(path: Path) -> List[Dict]:
    rows: List[Dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                import json

                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _coerce_logs(query_log_source: Path | List[Dict]) -> List[Dict]:
    if isinstance(query_log_source, Path):
        return _read_jsonl(query_log_source)
    return list(query_log_source)


def _normalize_token(token: str) -> str:
    token = token.lower().strip()
    token = re.sub(r"[^a-z0-9+\-]", "", token)
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]
    return token


def _extract_query_terms(text: str) -> List[str]:
    terms = []
    for raw in re.findall(r"[A-Za-z][A-Za-z0-9+\-]{1,}", text):
        token = _normalize_token(raw)
        if len(token) < 4 or token in STOPWORDS:
            continue
        terms.append(token)
    return terms


def build_insights(query_log_source: Path | List[Dict], graph_data: Dict) -> Dict:
    logs = _coerce_logs(query_log_source)
    topic_counter = Counter()
    recent_queries: List[str] = []
    hour_counter = defaultdict(int)
    searched_terms = set()

    for row in logs:
        query = (row.get("query") or "").strip()
        if query:
            recent_queries.append(query)
            for token in _extract_query_terms(query):
                topic_counter[token] += 1
                searched_terms.add(token)
        ts = row.get("timestamp")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                hour_counter[dt.strftime("%H:00")] += 1
            except Exception:
                pass

    most_searched_topics = [{"topic": t, "count": c} for t, c in topic_counter.most_common(8)]
    graph_topics = []
    for node in graph_data.get("nodes") or []:
        if node.get("type") not in {"topic", "project"}:
            continue
        label = (node.get("label") or "").strip()
        if not label:
            continue
        label_terms = set(_extract_query_terms(label))
        if not label_terms:
            continue
        mentions = int(node.get("mentions") or 0)
        degree = int(node.get("degree") or 0)
        if mentions < 2 and len(label_terms) == 1:
            continue
        if searched_terms & label_terms:
            continue
        graph_topics.append((mentions, degree, label))

    graph_topics.sort(key=lambda item: (item[0], item[1], len(item[2])), reverse=True)
    not_revised = [label for _mentions, _degree, label in graph_topics[:10]]
    peak_activity = "N/A"
    if hour_counter:
        peak_activity = max(hour_counter.items(), key=lambda x: x[1])[0]

    return {
        "most_searched_topics": most_searched_topics,
        "not_revised_topics": not_revised,
        "peak_activity": peak_activity,
        "recent_queries": recent_queries[-10:][::-1],
    }
