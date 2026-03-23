from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.chunking import chunk_text


class ChunkingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
