from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.rag import RAGEngine, extractive_answer


class ExtractiveAnswerTests(unittest.TestCase):
    def test_compare_question_uses_compare_format(self) -> None:
        sources = [
            {
                "source_file": "ml.txt",
                "page_number": None,
                "text": (
                    "Cross entropy is commonly used for classification tasks. "
                    "MSE is often used for regression. "
                    "Cross entropy penalizes confident wrong predictions more strongly than MSE."
                ),
            }
        ]

        answer = extractive_answer("Compare cross entropy and MSE", sources)

        self.assertIn("Comparison based on your data:", answer)
        self.assertNotIn("Summary:", answer)
        self.assertIn("ml.txt", answer)

    def test_plan_question_uses_numbered_steps(self) -> None:
        sources = [
            {
                "source_file": "revision.md",
                "page_number": None,
                "text": (
                    "Day 1: review weak topics and summarize definitions. "
                    "Day 2: solve practice questions on the same topics. "
                    "Day 3: revisit mistakes and write short recall notes."
                ),
            }
        ]

        answer = extractive_answer("Make a 3 day revision plan", sources)

        self.assertIn("Suggested plan from your data:", answer)
        self.assertIn("1.", answer)
        self.assertIn("revision.md", answer)

    def test_empty_sources_returns_not_found(self) -> None:
        answer = extractive_answer("Explain TCP congestion control", [])
        self.assertEqual(answer, "Not found in your data.")

    def test_flashcards_mode_formats_qa_pairs(self) -> None:
        sources = [
            {
                "source_file": "ml.txt",
                "page_number": None,
                "text": (
                    "Cross entropy is commonly used for classification tasks. "
                    "It penalizes confident wrong predictions strongly."
                ),
            }
        ]

        answer = extractive_answer("Explain cross entropy", sources, answer_mode="flashcards")

        self.assertIn("Q:", answer)
        self.assertIn("A:", answer)
        self.assertIn("ml.txt", answer)

    def test_rag_engine_can_use_openai_mode(self) -> None:
        original_key = os.environ.get("OPENAI_API_KEY")
        original_model = os.environ.get("OPENAI_MODEL")
        original_provider = os.environ.get("LOCALMIND_LLM_PROVIDER")
        try:
            os.environ["OPENAI_API_KEY"] = "test-key"
            os.environ["OPENAI_MODEL"] = "gpt-test"
            os.environ["LOCALMIND_LLM_PROVIDER"] = "openai"
            engine = RAGEngine(Path("models"))
            engine._call_openai_chat_completions = lambda _messages: "Premium answer from API [S1]"

            answer = engine.generate_answer(
                "Explain TCP congestion control",
                [
                    {
                        "source_file": "network.txt",
                        "page_number": 1,
                        "text": "TCP congestion control adjusts send rate to avoid overwhelming the network.",
                        "chunk_id": "chunk_1",
                    }
                ],
            )

            self.assertEqual(answer, "Premium answer from API [S1]")
            self.assertEqual(engine.mode, "openai:gpt-test")
        finally:
            if original_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = original_key

            if original_model is None:
                os.environ.pop("OPENAI_MODEL", None)
            else:
                os.environ["OPENAI_MODEL"] = original_model

            if original_provider is None:
                os.environ.pop("LOCALMIND_LLM_PROVIDER", None)
            else:
                os.environ["LOCALMIND_LLM_PROVIDER"] = original_provider

    def test_local_answer_without_citations_gets_grounding_appendix(self) -> None:
        engine = RAGEngine(Path("missing-models"))
        engine.mode = "llama-cpp"
        engine._llama = object()
        engine._call_local_chat = lambda _question, _sources, _answer_mode="answer": "TCP uses a congestion window to control sending rate."

        answer = engine.generate_answer(
            "Explain TCP congestion control",
            [
                {
                    "source_file": "network.txt",
                    "page_number": 1,
                    "text": (
                        "TCP congestion control adjusts the congestion window based on perceived network conditions. "
                        "Slow start increases the window rapidly until packet loss or a threshold is reached."
                    ),
                    "chunk_id": "chunk_1",
                }
            ],
        )

        self.assertIn("Key evidence:", answer)
        self.assertIn("network.txt", answer)


if __name__ == "__main__":
    unittest.main()
