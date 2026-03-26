from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from fastapi import HTTPException


class DummyUpload:
    def __init__(self, name: str, content: bytes):
        self.filename = name
        self.file = io.BytesIO(content)


class FakeEmbeddingService:
    mode = "hashed-tfidf"
    model_name = "hashed-tfidf-2048"

    def embed_query(self, _query: str):
        return [[1.0]]

    def index_signature(self) -> str:
        return "hashed-tfidf:2048:test"

    def prepare_runtime(self, _texts) -> None:
        return None


class QueryAwareEmbeddingService(FakeEmbeddingService):
    def embed_query(self, query: str):
        return query


class FakeVectorIndex:
    backend_name = "numpy-fallback"
    size = 1

    def search(self, _query_vector, _top_k: int):
        return [(0, 0.875)]


class FakeVectorIndexWithDuplicates:
    backend_name = "numpy-fallback"
    size = 4

    def __init__(self) -> None:
        self.requested_top_k = None

    def search(self, _query_vector, top_k: int):
        self.requested_top_k = top_k
        hits = [(0, 0.99), (1, 0.98), (2, 0.97), (3, 0.96)]
        return hits[:top_k]


class FakeVectorIndexLexicalPreference:
    backend_name = "numpy-fallback"
    size = 2

    def search(self, _query_vector, top_k: int):
        hits = [(0, 0.95), (1, 0.82)]
        return hits[:top_k]


class FakeVectorIndexLowConfidence:
    backend_name = "numpy-fallback"
    size = 1

    def search(self, _query_vector, top_k: int):
        return [(0, -0.4)][:top_k]


class FakeVectorIndexZeroSimilarity:
    backend_name = "numpy-fallback"
    size = 1

    def search(self, _query_vector, top_k: int):
        return [(0, 0.0)][:top_k]


class FakeVectorIndexMissesExactCandidate:
    backend_name = "numpy-fallback"
    size = 1

    def search(self, _query_vector, top_k: int):
        return [(0, 0.73)][:top_k]


class FakeVectorIndexMetadataPreference:
    backend_name = "numpy-fallback"
    size = 2

    def search(self, _query_vector, top_k: int):
        return [(0, 0.89), (1, 0.84)][:top_k]


class FakeVectorIndexQueryVariants:
    backend_name = "numpy-fallback"
    size = 2

    def search(self, query_vector, _top_k: int):
        lowered = str(query_vector).lower()
        if "from my notes" in lowered:
            return [(0, 0.72)]
        if "tcp congestion control" in lowered:
            return [(1, 0.88), (0, 0.61)]
        return [(0, 0.5)]


class DummySecurityManager:
    configured = False
    unlocked = False

    def status(self):
        return {"configured": False, "unlocked": False}

    def is_encrypted_blob(self, _payload: bytes) -> bool:
        return False

    def encrypt_bytes(self, payload: bytes) -> bytes:
        return payload

    def decrypt_bytes(self, payload: bytes) -> bytes:
        return payload


class DummyRerankerService:
    mode = "disabled"
    model_name = "lexical-only"

    def rerank(self, _query, candidates):
        return list(candidates)


class FakeRagEngine:
    def __init__(self) -> None:
        self.calls = []
        self.mode = "extractive-fallback"
        self.model_name = "extractive-fallback"

    def generate_answer(self, *, question: str, sources, answer_mode: str):
        self.calls.append({"question": question, "sources": sources, "answer_mode": answer_mode})
        return f"mode={answer_mode}"


class FakeSelectableEmbeddingService(FakeEmbeddingService):
    def __init__(self, _models_dir=None, preferred_model: str | None = None) -> None:
        self.preferred_model = (preferred_model or "").strip()
        self.last_error = ""
        if self.preferred_model == "embeddings/strong-embed":
            self.mode = "sentence-transformers"
            self.model_name = "strong-embed"
        elif self.preferred_model in {"auto", ""}:
            self.mode = "sentence-transformers"
            self.model_name = "auto-embed"
        elif self.preferred_model == "hashed-tfidf":
            self.mode = "hashed-tfidf"
            self.model_name = "hashed-tfidf-2048"
        else:
            self.mode = "hashed-tfidf"
            self.model_name = "hashed-tfidf-2048"
            self.last_error = "bad embedding"

    def index_signature(self) -> str:
        if self.mode == "sentence-transformers":
            return f"sentence-transformers:{self.model_name}"
        return "hashed-tfidf:2048:test"

    def prepare_runtime(self, _texts) -> None:
        return None


class FakeSelectableRerankerService(DummyRerankerService):
    def __init__(self, _models_dir=None, preferred_model: str | None = None) -> None:
        self.preferred_model = (preferred_model or "").strip()
        self.last_error = ""
        if self.preferred_model == "rerankers/strong-reranker":
            self.mode = "cross-encoder"
            self.model_name = "strong-reranker"
        elif self.preferred_model in {"auto", "", "disabled"}:
            self.mode = "disabled"
            self.model_name = "lexical-only"
        else:
            self.mode = "disabled"
            self.model_name = "lexical-only"
            self.last_error = "bad reranker"


class FakeSelectableRAGEngine(FakeRagEngine):
    def __init__(self, _models_dir=None, *, provider: str | None = None, preferred_local_model: str | None = None) -> None:
        super().__init__()
        self.provider = provider or "local"
        self.preferred_local_model = (preferred_local_model or "").strip()
        self.last_error = ""
        if self.preferred_local_model == "demo.gguf":
            self.mode = "llama-cpp"
            self.model_name = "demo.gguf"
        elif self.preferred_local_model in {"auto", ""}:
            self.mode = "llama-cpp"
            self.model_name = "auto.gguf"
        elif self.preferred_local_model == "extractive-fallback":
            self.mode = "extractive-fallback"
            self.model_name = "extractive-fallback"
        else:
            self.mode = "extractive-fallback"
            self.model_name = "extractive-fallback"
            self.last_error = "bad llm"


class MainBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_uploads_dir = main.UPLOADS_DIR
        self.original_demo_data_dir = main.DEMO_DATA_DIR
        self.original_query_log_file = main.QUERY_LOG_FILE
        self.original_model_settings_file = main.MODEL_SETTINGS_FILE
        self.original_jobs = dict(main.jobs)
        self.original_chunks_store = list(main.chunks_store)
        self.original_chunk_by_id = dict(main.chunk_by_id)
        self.original_index_map = dict(main.index_map)
        self.original_meta = dict(main.meta)
        self.original_model_settings = dict(main.model_settings)
        self.original_graph_cache = dict(main.graph_cache)
        self.original_retrieval_stats = main.retrieval_stats
        self.original_chunk_sequences = dict(main.chunk_sequences)
        self.original_chunk_sequence_positions = dict(main.chunk_sequence_positions)
        self.original_prepare_index_state = main.prepare_index_state
        self.original_embedding_service_cls = main.EmbeddingService
        self.original_embedding_service = main.embedding_service
        self.original_vector_index = main.vector_index
        self.original_reranker_service_cls = main.RerankerService
        self.original_reranker_service = main.reranker_service
        self.original_rag_engine_cls = main.RAGEngine
        self.original_rag_engine = main.rag_engine
        self.original_security_manager = main.security_manager
        self.original_ensure_unlocked = main.ensure_unlocked
        main.QUERY_LOG_FILE = Path(self.temp_dir.name) / "query_log.jsonl"
        main.MODEL_SETTINGS_FILE = Path(self.temp_dir.name) / "model_settings.json"
        main.model_settings = {"llm": "auto", "embedding": "auto", "reranker": "auto"}
        main.security_manager = DummySecurityManager()
        main.ensure_unlocked = lambda: None
        main.reranker_service = DummyRerankerService()

    def tearDown(self) -> None:
        main.UPLOADS_DIR = self.original_uploads_dir
        main.DEMO_DATA_DIR = self.original_demo_data_dir
        main.QUERY_LOG_FILE = self.original_query_log_file
        main.MODEL_SETTINGS_FILE = self.original_model_settings_file
        main.jobs = self.original_jobs
        main.chunks_store = self.original_chunks_store
        main.chunk_by_id = self.original_chunk_by_id
        main.index_map = self.original_index_map
        main.meta = self.original_meta
        main.model_settings = self.original_model_settings
        main.graph_cache = self.original_graph_cache
        main.retrieval_stats = self.original_retrieval_stats
        main.chunk_sequences = self.original_chunk_sequences
        main.chunk_sequence_positions = self.original_chunk_sequence_positions
        main.prepare_index_state = self.original_prepare_index_state
        main.EmbeddingService = self.original_embedding_service_cls
        main.embedding_service = self.original_embedding_service
        main.vector_index = self.original_vector_index
        main.RerankerService = self.original_reranker_service_cls
        main.reranker_service = self.original_reranker_service
        main.RAGEngine = self.original_rag_engine_cls
        main.rag_engine = self.original_rag_engine
        main.security_manager = self.original_security_manager
        main.ensure_unlocked = self.original_ensure_unlocked
        self.temp_dir.cleanup()

    def test_save_uploads_keeps_duplicate_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            main.UPLOADS_DIR = Path(temp_dir)
            uploads = [DummyUpload("notes.txt", b"first"), DummyUpload("notes.txt", b"second")]
            saved = main.save_uploads("job-1", uploads)

        self.assertEqual(len(saved), 2)
        self.assertEqual(len({str(path) for path in saved}), 2)
        self.assertEqual([path.name for path in saved], ["notes.txt", "notes.txt"])

    def test_search_rejects_blank_query(self) -> None:
        with self.assertRaises(HTTPException) as context:
            main.search(main.SearchRequest(query="   ", top_k=3))
        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("Query cannot be empty", context.exception.detail)

    def test_ask_rejects_blank_question(self) -> None:
        with self.assertRaises(HTTPException) as context:
            main.ask(main.AskRequest(question="   ", top_k=3))
        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("Question cannot be empty", context.exception.detail)

    def test_search_results_include_full_text(self) -> None:
        chunk = {
            "chunk_id": "chunk_alpha",
            "text": "Alpha beta gamma delta",
            "source_file": "notes.txt",
            "page_number": None,
            "chunk_index": 0,
        }
        main.chunks_store = [chunk]
        main.chunk_by_id = {"chunk_alpha": chunk}
        main.index_map = {"0": "chunk_alpha"}
        main.refresh_memory_maps()
        main.embedding_service = FakeEmbeddingService()
        main.vector_index = FakeVectorIndex()

        response = main.search(main.SearchRequest(query="alpha", top_k=1))

        self.assertEqual(len(response["results"]), 1)
        self.assertEqual(response["results"][0]["text"], "Alpha beta gamma delta")

    def test_search_overfetches_to_fill_requested_top_k_with_unique_chunks(self) -> None:
        chunk_a = {
            "chunk_id": "chunk_a",
            "text": "Alpha beta gamma delta",
            "source_file": "notes.txt",
            "page_number": None,
            "chunk_index": 0,
        }
        chunk_b = {
            "chunk_id": "chunk_b",
            "text": "Beta only details",
            "source_file": "notes.txt",
            "page_number": None,
            "chunk_index": 1,
        }
        chunk_c = {
            "chunk_id": "chunk_c",
            "text": "Gamma additional details",
            "source_file": "notes.txt",
            "page_number": None,
            "chunk_index": 2,
        }
        duplicate_index = FakeVectorIndexWithDuplicates()
        main.chunks_store = [chunk_a, chunk_a, chunk_b, chunk_c]
        main.chunk_by_id = {"chunk_a": chunk_a, "chunk_b": chunk_b, "chunk_c": chunk_c}
        main.index_map = {"0": "chunk_a", "1": "chunk_a", "2": "chunk_b", "3": "chunk_c"}
        main.refresh_memory_maps()
        main.embedding_service = FakeEmbeddingService()
        main.vector_index = duplicate_index

        response = main.search(main.SearchRequest(query="alpha", top_k=2))

        self.assertEqual(len(response["results"]), 2)
        self.assertEqual([item["chunk_id"] for item in response["results"]], ["chunk_a", "chunk_b"])
        self.assertEqual(duplicate_index.requested_top_k, 4)

    def test_search_reranks_exact_phrase_match_higher(self) -> None:
        chunk_generic = {
            "chunk_id": "chunk_generic",
            "text": "TCP packets travel across the network and reliability is handled at the transport layer.",
            "source_file": "network.txt",
            "page_number": 1,
            "chunk_index": 0,
        }
        chunk_exact = {
            "chunk_id": "chunk_exact",
            "text": "TCP congestion control adjusts send rate to avoid overwhelming the network.",
            "source_file": "network.txt",
            "page_number": 2,
            "chunk_index": 1,
        }
        main.chunks_store = [chunk_generic, chunk_exact]
        main.chunk_by_id = {"chunk_generic": chunk_generic, "chunk_exact": chunk_exact}
        main.index_map = {"0": "chunk_generic", "1": "chunk_exact"}
        main.refresh_memory_maps()
        main.embedding_service = FakeEmbeddingService()
        main.vector_index = FakeVectorIndexLexicalPreference()

        response = main.search(main.SearchRequest(query="tcp congestion control", top_k=2))

        self.assertEqual(len(response["results"]), 2)
        self.assertEqual(response["results"][0]["chunk_id"], "chunk_exact")
        self.assertGreaterEqual(response["results"][0]["score"], response["results"][1]["score"])

    def test_search_filters_zero_similarity_results(self) -> None:
        chunk = {
            "chunk_id": "chunk_irrelevant",
            "text": "TCP packets travel across the network.",
            "source_file": "network.txt",
            "page_number": 1,
            "chunk_index": 0,
        }
        main.chunks_store = [chunk]
        main.chunk_by_id = {"chunk_irrelevant": chunk}
        main.index_map = {"0": "chunk_irrelevant"}
        main.refresh_memory_maps()
        main.embedding_service = FakeEmbeddingService()
        main.vector_index = FakeVectorIndexZeroSimilarity()

        response = main.search(main.SearchRequest(query="cross entropy", top_k=3))

        self.assertEqual(response["results"], [])

    def test_search_can_be_scoped_to_selected_files(self) -> None:
        chunk_a = {
            "chunk_id": "chunk_a",
            "text": "TCP congestion control adjusts send rate.",
            "source_file": "network.txt",
            "page_number": 1,
            "chunk_index": 0,
        }
        chunk_b = {
            "chunk_id": "chunk_b",
            "text": "Cross entropy is used for classification.",
            "source_file": "ml.txt",
            "page_number": 1,
            "chunk_index": 0,
        }
        main.chunks_store = [chunk_a, chunk_b]
        main.chunk_by_id = {"chunk_a": chunk_a, "chunk_b": chunk_b}
        main.index_map = {"0": "chunk_a", "1": "chunk_b"}
        main.refresh_memory_maps()
        main.embedding_service = FakeEmbeddingService()
        main.vector_index = FakeVectorIndexLexicalPreference()

        response = main.search(main.SearchRequest(query="cross entropy", top_k=2, source_files=["network.txt"]))

        self.assertEqual(len(response["results"]), 1)
        self.assertEqual(response["results"][0]["chunk_id"], "chunk_a")

    def test_search_uses_query_variants_for_better_matches(self) -> None:
        chunk_generic = {
            "chunk_id": "chunk_generic",
            "text": "TCP uses packets and acknowledgements.",
            "source_file": "network.txt",
            "page_number": 1,
            "chunk_index": 0,
        }
        chunk_exact = {
            "chunk_id": "chunk_exact",
            "text": "TCP congestion control adjusts send rate to avoid overwhelming the network.",
            "source_file": "network.txt",
            "page_number": 2,
            "chunk_index": 1,
        }
        main.chunks_store = [chunk_generic, chunk_exact]
        main.chunk_by_id = {"chunk_generic": chunk_generic, "chunk_exact": chunk_exact}
        main.index_map = {"0": "chunk_generic", "1": "chunk_exact"}
        main.refresh_memory_maps()
        main.embedding_service = QueryAwareEmbeddingService()
        main.vector_index = FakeVectorIndexQueryVariants()

        response = main.search(main.SearchRequest(query="Explain TCP congestion control from my notes", top_k=2))

        self.assertEqual(len(response["results"]), 2)
        self.assertEqual(response["results"][0]["chunk_id"], "chunk_exact")

    def test_search_can_recover_exact_match_from_lexical_candidates(self) -> None:
        chunk_generic = {
            "chunk_id": "chunk_generic",
            "text": "TCP uses sequence numbers and acknowledgements for reliability.",
            "source_file": "network.txt",
            "page_number": 1,
            "chunk_index": 0,
        }
        chunk_exact = {
            "chunk_id": "chunk_exact",
            "text": "TCP congestion control adjusts send rate to avoid overwhelming the network.",
            "source_file": "network.txt",
            "page_number": 2,
            "chunk_index": 1,
        }
        main.chunks_store = [chunk_generic, chunk_exact]
        main.chunk_by_id = {"chunk_generic": chunk_generic, "chunk_exact": chunk_exact}
        main.index_map = {"0": "chunk_generic", "1": "chunk_exact"}
        main.refresh_memory_maps()
        main.embedding_service = FakeEmbeddingService()
        main.vector_index = FakeVectorIndexMissesExactCandidate()

        response = main.search(main.SearchRequest(query="tcp congestion control", top_k=2))

        self.assertEqual(len(response["results"]), 2)
        self.assertEqual(response["results"][0]["chunk_id"], "chunk_exact")

    def test_search_uses_source_file_metadata_for_reranking(self) -> None:
        chunk_generic = {
            "chunk_id": "chunk_generic",
            "text": "Day 1 focus on foundations and timed practice.",
            "source_file": "notes.txt",
            "page_number": None,
            "chunk_index": 0,
            "section_path": [],
            "block_kind": "paragraph",
        }
        chunk_file_match = {
            "chunk_id": "chunk_file_match",
            "text": "Day 1 focus on foundations and timed practice.",
            "source_file": "revision_plan_ideas.txt",
            "page_number": None,
            "chunk_index": 0,
            "section_path": [],
            "block_kind": "paragraph",
        }
        main.chunks_store = [chunk_generic, chunk_file_match]
        main.chunk_by_id = {"chunk_generic": chunk_generic, "chunk_file_match": chunk_file_match}
        main.index_map = {"0": "chunk_generic", "1": "chunk_file_match"}
        main.refresh_memory_maps()
        main.embedding_service = FakeEmbeddingService()
        main.vector_index = FakeVectorIndexMetadataPreference()

        response = main.search(main.SearchRequest(query="revision plan ideas", top_k=2))

        self.assertEqual(len(response["results"]), 2)
        self.assertEqual(response["results"][0]["chunk_id"], "chunk_file_match")

    def test_expand_answer_hits_includes_adjacent_chunks_for_context(self) -> None:
        chunk_prev = {
            "chunk_id": "chunk_prev",
            "text": "TCP starts with slow start and uses a small congestion window.",
            "source_file": "network.txt",
            "page_number": 1,
            "chunk_index": 0,
        }
        chunk_center = {
            "chunk_id": "chunk_center",
            "text": "After the threshold, congestion avoidance grows the congestion window linearly.",
            "source_file": "network.txt",
            "page_number": 1,
            "chunk_index": 1,
        }
        chunk_next = {
            "chunk_id": "chunk_next",
            "text": "Packet loss triggers fast retransmit or timeout recovery depending on severity.",
            "source_file": "network.txt",
            "page_number": 1,
            "chunk_index": 2,
        }
        main.chunks_store = [chunk_prev, chunk_center, chunk_next]
        main.refresh_memory_maps()

        expanded = main._expand_answer_hits([dict(chunk_center, score=0.8, vector_score=0.8, preview="")])

        self.assertEqual(len(expanded), 1)
        self.assertIn("slow start", expanded[0]["text"])
        self.assertIn("Packet loss triggers", expanded[0]["text"])

    def test_catalog_returns_source_summaries(self) -> None:
        main.chunks_store = [
            {
                "chunk_id": "chunk_a",
                "text": "Alpha",
                "source_file": "notes.txt",
                "page_number": None,
                "chunk_index": 0,
                "created_at": "2025-01-01T00:00:00+00:00",
            },
            {
                "chunk_id": "chunk_b",
                "text": "Beta",
                "source_file": "notes.txt",
                "page_number": None,
                "chunk_index": 1,
                "created_at": "2025-01-01T00:00:01+00:00",
            },
            {
                "chunk_id": "chunk_c",
                "text": "Gamma",
                "source_file": "slides.pdf",
                "page_number": 3,
                "chunk_index": 0,
                "created_at": "2025-01-02T00:00:00+00:00",
            },
        ]

        response = main.catalog()

        self.assertEqual(len(response["sources"]), 2)
        self.assertEqual(response["sources"][0]["source_file"], "notes.txt")
        self.assertEqual(response["sources"][0]["chunks"], 2)
        self.assertEqual(response["sources"][1]["kind"], "pdf")

    def test_ask_uses_trust_mode_gate_for_low_confidence(self) -> None:
        chunk = {
            "chunk_id": "chunk_a",
            "text": "TCP packets travel across the network.",
            "source_file": "network.txt",
            "page_number": 1,
            "chunk_index": 0,
        }
        fake_rag = FakeRagEngine()
        main.chunks_store = [chunk]
        main.chunk_by_id = {"chunk_a": chunk}
        main.index_map = {"0": "chunk_a"}
        main.refresh_memory_maps()
        main.embedding_service = FakeEmbeddingService()
        main.vector_index = FakeVectorIndexLowConfidence()
        main.rag_engine = fake_rag

        response = main.ask(main.AskRequest(question="Explain transformers in depth", top_k=2, trust_mode=True))

        self.assertIn("do not have enough evidence", response["answer"].lower())
        self.assertEqual(response["evidence_status"], "insufficient")
        self.assertEqual(fake_rag.calls, [])

    def test_ask_uses_extractive_answer_for_limited_evidence_in_trust_mode(self) -> None:
        chunk = {
            "chunk_id": "chunk_a",
            "text": "TCP congestion control adjusts the send rate to avoid overwhelming the network.",
            "source_file": "network.txt",
            "page_number": 1,
            "chunk_index": 0,
        }
        fake_rag = FakeRagEngine()
        main.chunks_store = [chunk]
        main.chunk_by_id = {"chunk_a": chunk}
        main.index_map = {"0": "chunk_a"}
        main.refresh_memory_maps()
        main.embedding_service = FakeEmbeddingService()
        main.vector_index = FakeVectorIndex()
        main.rag_engine = fake_rag

        response = main.ask(main.AskRequest(question="Explain TCP congestion control in detail", top_k=2, trust_mode=True))

        self.assertIn("network.txt", response["answer"])
        self.assertEqual(response["evidence_status"], "limited")
        self.assertEqual(fake_rag.calls, [])

    def test_ask_passes_answer_mode_to_rag_engine(self) -> None:
        chunk = {
            "chunk_id": "chunk_a",
            "text": "TCP congestion control adjusts send rate to avoid congestion.",
            "source_file": "network.txt",
            "page_number": 1,
            "chunk_index": 0,
        }
        fake_rag = FakeRagEngine()
        main.chunks_store = [chunk]
        main.chunk_by_id = {"chunk_a": chunk}
        main.index_map = {"0": "chunk_a"}
        main.refresh_memory_maps()
        main.embedding_service = FakeEmbeddingService()
        main.vector_index = FakeVectorIndex()
        main.rag_engine = fake_rag

        response = main.ask(main.AskRequest(question="Explain TCP congestion control", top_k=2, mode="flashcards"))

        self.assertEqual(response["answer"], "mode=flashcards")
        self.assertEqual(response["answer_mode"], "flashcards")
        self.assertEqual(fake_rag.calls[0]["answer_mode"], "flashcards")

    def test_retrieval_queries_add_keyword_variant(self) -> None:
        queries = main._retrieval_queries("Explain TCP congestion control from my notes")

        self.assertGreaterEqual(len(queries), 2)
        self.assertEqual(queries[0], "Explain TCP congestion control from my notes")
        self.assertTrue(any("tcp congestion control" in query.lower() for query in queries[1:]))

    def test_stats_include_feature_status(self) -> None:
        response = main.stats()

        self.assertIn("feature_status", response)
        self.assertTrue(response["feature_status"])
        self.assertIn("graph_mode", response)
        self.assertIn("pdf_backend", response)

    def test_stats_reports_reindex_recommended_for_old_chunking_version(self) -> None:
        main.chunks_store = [
            {
                "chunk_id": "chunk_a",
                "text": "Alpha",
                "source_file": "notes.txt",
                "page_number": None,
                "chunk_index": 0,
            }
        ]
        main.meta = {"chunking_version": "legacy-v1"}

        response = main.stats()

        self.assertTrue(response["reindex_recommended"])
        self.assertEqual(response["chunking_version"], "legacy-v1")

    def test_stats_reports_reindex_recommended_for_embedding_signature_mismatch(self) -> None:
        main.chunks_store = [
            {
                "chunk_id": "chunk_a",
                "text": "Alpha",
                "source_file": "notes.txt",
                "page_number": None,
                "chunk_index": 0,
            }
        ]
        main.meta = {"chunking_version": main.CHUNKING_VERSION, "embedding_signature": "sentence-transformers:old-embed"}
        main.vector_index = FakeVectorIndex()
        main.embedding_service = FakeEmbeddingService()

        response = main.stats()

        self.assertTrue(response["reindex_recommended"])

    def test_apply_models_updates_runtime_and_persists_selection(self) -> None:
        main.EmbeddingService = FakeSelectableEmbeddingService
        main.RerankerService = FakeSelectableRerankerService
        main.RAGEngine = FakeSelectableRAGEngine
        main.chunks_store = [
            {
                "chunk_id": "chunk_a",
                "text": "Alpha beta",
                "source_file": "notes.txt",
                "page_number": None,
                "chunk_index": 0,
            }
        ]
        main.meta = {"chunking_version": main.CHUNKING_VERSION, "embedding_signature": "hashed-tfidf:2048:test"}
        main.vector_index = FakeVectorIndex()

        response = main.apply_models(
            main.ModelSettingsRequest(
                llm="demo.gguf",
                embedding="embeddings/strong-embed",
                reranker="rerankers/strong-reranker",
            )
        )

        self.assertEqual(main.model_settings["llm"], "demo.gguf")
        self.assertEqual(main.embedding_service.model_name, "strong-embed")
        self.assertEqual(main.reranker_service.model_name, "strong-reranker")
        self.assertEqual(main.rag_engine.model_name, "demo.gguf")
        self.assertEqual(response["validation"]["embedding"]["ok"], True)
        self.assertTrue(main.MODEL_SETTINGS_FILE.exists())
        saved = json.loads(main.MODEL_SETTINGS_FILE.read_text(encoding="utf-8"))
        self.assertEqual(saved["embedding"], "embeddings/strong-embed")

    def test_apply_models_rejects_invalid_selection(self) -> None:
        main.EmbeddingService = FakeSelectableEmbeddingService
        main.RerankerService = FakeSelectableRerankerService
        main.RAGEngine = FakeSelectableRAGEngine
        main.chunks_store = []

        with self.assertRaises(HTTPException) as context:
            main.apply_models(main.ModelSettingsRequest(embedding="embeddings/bad-embed"))

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(main.model_settings["embedding"], "auto")

    def test_validate_models_reports_candidate_without_mutating_runtime(self) -> None:
        main.EmbeddingService = FakeSelectableEmbeddingService
        main.RerankerService = FakeSelectableRerankerService
        main.RAGEngine = FakeSelectableRAGEngine
        main.embedding_service = FakeSelectableEmbeddingService(preferred_model="hashed-tfidf")
        main.reranker_service = FakeSelectableRerankerService(preferred_model="disabled")
        main.rag_engine = FakeSelectableRAGEngine(preferred_local_model="extractive-fallback")

        response = main.validate_models(main.ModelSettingsRequest(embedding="embeddings/strong-embed", llm="demo.gguf"))

        self.assertTrue(response["validation"]["embedding"]["ok"])
        self.assertEqual(response["embedding"]["selected"], "embeddings/strong-embed")
        self.assertEqual(main.embedding_service.model_name, "hashed-tfidf-2048")
        self.assertEqual(main.model_settings["embedding"], "auto")

    def test_duplicate_source_file_is_skipped(self) -> None:
        chunk = {
            "chunk_id": "chunk_existing",
            "text": "Existing note text",
            "source_file": "notes.txt",
            "page_number": None,
            "chunk_index": 0,
        }
        main.jobs = {}
        main.chunks_store = [chunk]
        main.chunk_by_id = {"chunk_existing": chunk}
        main.index_map = {"0": "chunk_existing"}
        main.refresh_memory_maps()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "notes.txt"
            path.write_text("New content that should be skipped", encoding="utf-8")
            main.process_ingestion("job-duplicate", [path])

        self.assertEqual(len(main.chunks_store), 1)
        self.assertEqual(main.jobs["job-duplicate"]["state"], "done")
        self.assertIn("already indexed", main.jobs["job-duplicate"]["message"].lower())

    def test_failed_prepare_does_not_mutate_chunks_store(self) -> None:
        chunk = {
            "chunk_id": "chunk_existing",
            "text": "Existing note text",
            "source_file": "notes.txt",
            "page_number": None,
            "chunk_index": 0,
        }
        main.jobs = {}
        main.chunks_store = [chunk]
        main.chunk_by_id = {"chunk_existing": chunk}
        main.index_map = {"0": "chunk_existing"}
        main.refresh_memory_maps()

        def fail_prepare(*_args, **_kwargs):
            raise RuntimeError("boom")

        main.prepare_index_state = fail_prepare

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "fresh.txt"
            path.write_text("Fresh content", encoding="utf-8")
            main.process_ingestion("job-fail", [path])

        self.assertEqual(main.chunks_store, [chunk])
        self.assertEqual(main.jobs["job-fail"]["state"], "error")
        self.assertEqual(main.jobs["job-fail"]["message"], "boom")


if __name__ == "__main__":
    unittest.main()
