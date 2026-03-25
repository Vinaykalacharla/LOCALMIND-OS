from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.embeddings import EmbeddingService, HashedTfidfEncoder


class EmbeddingServiceTests(unittest.TestCase):
    def test_hashed_tfidf_token_index_is_deterministic(self) -> None:
        encoder_a = HashedTfidfEncoder(dim=2048)
        encoder_b = HashedTfidfEncoder(dim=2048)

        indices_a = [encoder_a._index(token) for token in ["tcp", "congestion", "control"]]
        indices_b = [encoder_b._index(token) for token in ["tcp", "congestion", "control"]]

        self.assertEqual(indices_a, indices_b)

    def test_prepare_runtime_refits_hashed_tfidf_encoder_for_loaded_chunks(self) -> None:
        service = EmbeddingService()
        service.mode = "hashed-tfidf"
        service.model_name = "hashed-tfidf-2048"
        service._st_model = None

        service.prepare_runtime(
            [
                "TCP congestion control adjusts send rate.",
                "Cross entropy is used for classification.",
            ]
        )

        vector = service.embed_query("tcp congestion control")

        self.assertTrue(service._fallback.fitted)
        self.assertEqual(vector.shape[1], service._fallback.dim)
        self.assertGreater(float(vector.max()), 0.0)

    def test_index_signature_changes_with_active_embedding_backend(self) -> None:
        service = EmbeddingService()
        service.mode = "hashed-tfidf"
        service.model_name = "hashed-tfidf-2048"
        service._st_model = None
        hashed_signature = service.index_signature()

        service.mode = "sentence-transformers"
        service.model_name = "all-MiniLM-L6-v2"
        service._st_model = object()
        transformer_signature = service.index_signature()

        self.assertNotEqual(hashed_signature, transformer_signature)


if __name__ == "__main__":
    unittest.main()
