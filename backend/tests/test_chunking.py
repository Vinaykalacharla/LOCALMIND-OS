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

        self.assertEqual(CHUNKING_VERSION, "structured-v3")
        self.assertEqual(len(chunks), 1)
        self.assertIn("Section: Loss Functions > Cross Entropy", chunks[0].text)
        self.assertEqual(chunks[0].section_path, ["Loss Functions", "Cross Entropy"])
        self.assertEqual(chunks[0].block_kind, "paragraph")

    def test_chunk_text_prefers_paragraph_boundaries(self) -> None:
        text = (
            "Paragraph one explains TCP congestion control clearly.\n\n"
            "Paragraph two explains slow start and congestion avoidance in more detail.\n\n"
            "Paragraph three covers packet loss and window reduction."
        )

        chunks = chunk_text(text, chunk_size=90, overlap=20)

        self.assertGreaterEqual(len(chunks), 2)
        self.assertIn("Paragraph one explains TCP congestion control clearly.", chunks[0])
        self.assertTrue(any("Paragraph two explains slow start" in chunk for chunk in chunks))

    def test_chunk_text_splits_long_text_without_empty_chunks(self) -> None:
        text = (
            "TCP congestion control adjusts sending behavior based on perceived network conditions. "
            "Slow start increases the congestion window quickly. "
            "Congestion avoidance then increases the window more gradually. "
            "Packet loss causes the sender to reduce the congestion window."
        )

        chunks = chunk_text(text, chunk_size=80, overlap=12)

        self.assertGreaterEqual(len(chunks), 3)
        self.assertTrue(all(chunk.strip() for chunk in chunks))
        self.assertTrue(all(len(chunk) <= 92 for chunk in chunks))

    def test_chunk_document_uses_overlap_between_adjacent_segments(self) -> None:
        text = (
            "# TCP Notes\n\n"
            "TCP congestion control adapts the send rate to the network. "
            "Slow start increases the congestion window rapidly at first. "
            "Congestion avoidance grows more carefully after the threshold. "
            "Packet loss reduces the window and triggers recovery."
        )

        chunks = chunk_document(text, chunk_size=120, overlap=45)

        self.assertGreaterEqual(len(chunks), 2)
        self.assertIn("Slow start increases", chunks[1].text)


if __name__ == "__main__":
    unittest.main()
