from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.graph import GraphBuilder


class GraphBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = GraphBuilder()
        self.builder._nlp = None
        self.builder.mode = "heuristic-fallback"

    def test_build_graph_uses_section_metadata_for_nodes_and_doc_edges(self) -> None:
        chunks = [
            {
                "chunk_id": "chunk_1",
                "text": "cwnd doubles every round trip time until it reaches ssthresh.",
                "source_file": "tcp_revision_plan.txt",
                "section_path": ["TCP Congestion Control", "Slow Start"],
                "block_kind": "list",
            }
        ]

        graph = self.builder.build_graph(chunks)
        labels = {node["label"] for node in graph["nodes"]}

        self.assertIn("TCP Congestion Control", labels)
        self.assertIn("Slow Start", labels)

        node_ids = {node["label"]: node["id"] for node in graph["nodes"]}
        self.assertIn(
            {
                "source": "doc:tcp_revision_plan.txt",
                "target": node_ids["Slow Start"],
                "relation": "covers",
                "weight": 3,
            },
            graph["edges"],
        )

    def test_build_graph_filters_generic_terms_and_links_related_docs(self) -> None:
        chunks = [
            {
                "chunk_id": "doc_a_1",
                "text": "Classification uses logits before the final probability mapping.",
                "source_file": "ml_notes_a.txt",
                "section_path": ["Overview", "Cross Entropy", "Logits"],
                "block_kind": "paragraph",
            },
            {
                "chunk_id": "doc_a_2",
                "text": "Cross entropy compares logits against the target class.",
                "source_file": "ml_notes_a.txt",
                "section_path": ["Summary", "Cross Entropy", "Logits"],
                "block_kind": "paragraph",
            },
            {
                "chunk_id": "doc_b_1",
                "text": "Logits feed the loss before probabilities are normalized.",
                "source_file": "ml_notes_b.txt",
                "section_path": ["Overview", "Cross Entropy", "Logits"],
                "block_kind": "paragraph",
            },
            {
                "chunk_id": "doc_b_2",
                "text": "Cross entropy works directly on logits for classification.",
                "source_file": "ml_notes_b.txt",
                "section_path": ["Summary", "Cross Entropy", "Logits"],
                "block_kind": "paragraph",
            },
        ]

        graph = self.builder.build_graph(chunks)
        labels = {node["label"] for node in graph["nodes"]}

        self.assertIn("Cross Entropy", labels)
        self.assertIn("Logits", labels)
        self.assertNotIn("Overview", labels)
        self.assertNotIn("Summary", labels)

        doc_links = [
            edge
            for edge in graph["edges"]
            if edge["relation"] == "shares_topics"
            and {edge["source"], edge["target"]} == {"doc:ml_notes_a.txt", "doc:ml_notes_b.txt"}
        ]
        self.assertTrue(doc_links)


if __name__ == "__main__":
    unittest.main()
