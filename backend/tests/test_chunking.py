from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.chunking import CHUNKING_VERSION, chunk_document, chunk_text


class ChunkingTests(unittest.TestCase):
    def test_chunk_document_preserves_heading_context(self) -> None:
        text = """# Loss Functions

## Cross Entropy
Cross entropy is used for classification and penalizes confident wrong predictions.
"""

        chunks = chunk_document(text, chunk_size=180)

        self.assertEqual(CHUNKING_VERSION, "structured-v2")
        self.assertEqual(len(chunks), 1)
        self.assertIn("Section: Loss Functions > Cross Entropy", chunks[0].text)
        self.assertEqual(chunks[0].section_path, ["Loss Functions", "Cross Entropy"])
        self.assertEqual(chunks[0].block_kind, "paragraph")

    def test_chunk_document_keeps_list_structure(self) -> None:
        text = """TCP Congestion Control
======================

1. Slow Start:
- cwnd grows quickly.
- growth stops at ssthresh.
"""

        chunks = chunk_document(text, chunk_size=180)

        self.assertEqual(len(chunks), 1)
        self.assertIn("Section: TCP Congestion Control", chunks[0].text)
        self.assertIn("1. Slow Start:", chunks[0].text)
        self.assertIn("- cwnd grows quickly.", chunks[0].text)
        self.assertEqual(chunks[0].block_kind, "list")

    def test_chunk_text_remains_backward_compatible(self) -> None:
        text = "Paragraph one.\n\nParagraph two."

        chunks = chunk_text(text, chunk_size=120)

        self.assertTrue(chunks)
        self.assertTrue(all(isinstance(chunk, str) for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
