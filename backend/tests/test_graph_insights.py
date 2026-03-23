from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.graph import GraphBuilder
from services.insights import build_insights


class GraphAndInsightsTests(unittest.TestCase):
    def test_fallback_graph_surfaces_meaningful_terms(self) -> None:
        builder = GraphBuilder()
        builder._nlp = None
        builder.mode = "heuristic-fallback"

        graph = builder.build_graph(
            [
                {
                    "chunk_id": "chunk_1",
                    "source_file": "networking_notes.txt",
                    "text": "TCP Congestion Control\nSlow Start\nCongestion Avoidance improves throughput.",
                    "page_number": None,
                    "chunk_index": 0,
                }
            ]
        )

        labels = {node["label"] for node in graph["nodes"] if node["type"] != "doc"}
        self.assertIn("TCP Congestion Control", labels)
        self.assertIn("Slow Start", labels)
        self.assertNotIn("Notes", labels)

        concept_node = next(node for node in graph["nodes"] if node["label"] == "TCP Congestion Control")
        self.assertGreaterEqual(concept_node["mentions"], 1)
        self.assertGreaterEqual(concept_node["degree"], 1)

    def test_insights_filter_noisy_topics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            query_log = Path(temp_dir) / "query_log.jsonl"
            rows = [
                {"timestamp": "2026-03-11T06:00:00+00:00", "type": "ask", "query": "Explain TCP congestion control"},
                {"timestamp": "2026-03-11T07:00:00+00:00", "type": "search", "query": "TCP congestion control"},
            ]
            query_log.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            graph_data = {
                "nodes": [
                    {"label": "TCP Congestion Control", "type": "project", "mentions": 4, "degree": 3},
                    {"label": "Cross Entropy", "type": "topic", "mentions": 3, "degree": 2},
                    {"label": "Any", "type": "topic", "mentions": 5, "degree": 1},
                    {"label": "Revision Plan", "type": "topic", "mentions": 1, "degree": 1},
                ]
            }

            insights = build_insights(query_log, graph_data)

        not_revised = insights["not_revised_topics"]
        self.assertIn("Cross Entropy", not_revised)
        self.assertNotIn("TCP Congestion Control", not_revised)
        self.assertNotIn("Any", not_revised)
        self.assertNotIn("Revision Plan", not_revised)


if __name__ == "__main__":
    unittest.main()
