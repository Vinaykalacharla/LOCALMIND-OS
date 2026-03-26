from __future__ import annotations

import json
import math
import os
import re
import tempfile
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.capabilities import build_feature_status, detect_pdf_backend
from services.chunking import CHUNKING_VERSION, chunk_document
from services.embeddings import EmbeddingService
from services.graph import GraphBuilder
from services.ingestion import extract_many
from services.insights import build_insights
from services.rag import RAGEngine, _gguf_quality_score, extractive_answer
from services.reranker import RerankerService
from services.security import SecurityError, SecurityManager
from services.vector_index import VectorIndex

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
DEMO_DATA_DIR = BASE_DIR / "demo_data"
UPLOADS_DIR = DATA_DIR / "uploads"

CHUNKS_FILE = DATA_DIR / "chunks.jsonl"
INDEX_FILE = DATA_DIR / "faiss.index"
INDEX_MAP_FILE = DATA_DIR / "index_map.json"
META_FILE = DATA_DIR / "meta.json"
GRAPH_FILE = DATA_DIR / "graph.json"
QUERY_LOG_FILE = DATA_DIR / "query_log.jsonl"
SECURITY_FILE = DATA_DIR / "security.json"
MODEL_SETTINGS_FILE = DATA_DIR / "model_settings.json"
CONVERSATIONS_FILE = DATA_DIR / "conversations.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="LocalMind OS API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=30)
    source_files: List[str] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=30)
    source_files: List[str] = Field(default_factory=list)
    mode: str = Field(default="answer", min_length=1, max_length=40)
    trust_mode: bool = True
    session_id: Optional[str] = None


class SecurityPassphraseRequest(BaseModel):
    passphrase: str = Field(min_length=8, max_length=512)


class ModelSettingsRequest(BaseModel):
    llm: Optional[str] = None
    embedding: Optional[str] = None
    reranker: Optional[str] = None


@dataclass
class RetrievalStats:
    doc_count: int
    avg_doc_length: float
    doc_freqs: Dict[str, int]
    token_counts_by_chunk: Dict[str, Dict[str, int]]
    doc_lengths_by_chunk: Dict[str, int]
    source_tokens_by_chunk: Dict[str, List[str]]
    section_tokens_by_chunk: Dict[str, List[str]]
    block_kind_by_chunk: Dict[str, str]


def _empty_retrieval_stats() -> RetrievalStats:
    return RetrievalStats(
        doc_count=0,
        avg_doc_length=1.0,
        doc_freqs={},
        token_counts_by_chunk={},
        doc_lengths_by_chunk={},
        source_tokens_by_chunk={},
        section_tokens_by_chunk={},
        block_kind_by_chunk={},
    )


jobs: Dict[str, Dict[str, Any]] = {}
jobs_lock = threading.Lock()
index_lock = threading.Lock()
query_log_lock = threading.Lock()

chunks_store: List[Dict[str, Any]] = []
chunk_by_id: Dict[str, Dict[str, Any]] = {}
index_map: Dict[str, str] = {}
meta: Dict[str, Any] = {}
graph_cache: Dict[str, List[Dict[str, Any]]] = {"nodes": [], "edges": []}
retrieval_stats = _empty_retrieval_stats()
chunk_sequences: Dict[tuple[str, int | None], List[Dict[str, Any]]] = {}
chunk_sequence_positions: Dict[str, int] = {}
model_settings: Dict[str, str] = {"llm": "auto", "embedding": "auto", "reranker": "auto"}
conversations_store: List[Dict[str, Any]] = []

security_manager = SecurityManager(SECURITY_FILE)
embedding_service = EmbeddingService(MODELS_DIR)
vector_index = VectorIndex()
graph_builder = GraphBuilder()
reranker_service = RerankerService(MODELS_DIR)
rag_engine = RAGEngine(MODELS_DIR)


SEARCH_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
SEARCH_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "with",
}


@dataclass
class PreparedIndexState:
    chunks: List[Dict[str, Any]]
    chunk_by_id: Dict[str, Dict[str, Any]]
    index_map: Dict[str, str]
    meta: Dict[str, Any]
    graph_cache: Dict[str, List[Dict[str, Any]]]
    vector_index: VectorIndex
    index_bytes: bytes | None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def reset_runtime_state(*, clear_jobs: bool = False) -> None:
    global chunks_store, chunk_by_id, index_map, meta, graph_cache, vector_index, retrieval_stats, chunk_sequences, chunk_sequence_positions, conversations_store
    chunks_store = []
    chunk_by_id = {}
    index_map = {}
    meta = {}
    graph_cache = {"nodes": [], "edges": []}
    retrieval_stats = _empty_retrieval_stats()
    chunk_sequences = {}
    chunk_sequence_positions = {}
    conversations_store = []
    vector_index = VectorIndex()
    if clear_jobs:
        with jobs_lock:
            jobs.clear()


def _artifact_is_upload(path: Path) -> bool:
    try:
        return path.resolve().is_relative_to(UPLOADS_DIR.resolve())
    except Exception:
        return False


def _managed_artifact_paths() -> List[Path]:
    paths = [CHUNKS_FILE, INDEX_FILE, INDEX_MAP_FILE, META_FILE, GRAPH_FILE, QUERY_LOG_FILE, MODEL_SETTINGS_FILE, CONVERSATIONS_FILE]
    if UPLOADS_DIR.exists():
        paths.extend(p for p in UPLOADS_DIR.rglob("*") if p.is_file())
    return paths


def _default_model_settings() -> Dict[str, str]:
    return {"llm": "auto", "embedding": "auto", "reranker": "auto"}


def _normalize_model_choice(scope: str, value: str | None) -> str:
    cleaned = (value or "").strip()
    lowered = cleaned.lower()
    if scope == "llm":
        if not cleaned or lowered == "auto":
            return "auto"
        if lowered in {"extractive-fallback", "fallback", "disabled", "none"}:
            return "extractive-fallback"
        return cleaned
    if scope == "embedding":
        if not cleaned or lowered == "auto":
            return "auto"
        if lowered in {"hashed-tfidf", "fallback", "disabled"}:
            return "hashed-tfidf"
        return cleaned
    if scope == "reranker":
        if not cleaned or lowered == "auto":
            return "auto"
        if lowered in {"disabled", "lexical-only", "none"}:
            return "disabled"
        return cleaned
    return cleaned


def _load_model_settings() -> Dict[str, str]:
    raw = _load_json_artifact(MODEL_SETTINGS_FILE, {})
    settings = _default_model_settings()
    if isinstance(raw, dict):
        for key in settings:
            settings[key] = _normalize_model_choice(key, str(raw.get(key, "")))
    return settings


def _save_model_settings(settings: Dict[str, str]) -> None:
    payload = json.dumps(settings, indent=2, ensure_ascii=True).encode("utf-8")
    staged = _stage_bytes_file(MODEL_SETTINGS_FILE, payload, encrypt=security_manager.configured)
    try:
        os.replace(staged, MODEL_SETTINGS_FILE)
    finally:
        if staged.exists():
            staged.unlink(missing_ok=True)


def _load_conversations() -> List[Dict[str, Any]]:
    raw = _load_json_artifact(CONVERSATIONS_FILE, [])
    if not isinstance(raw, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        messages = item.get("messages")
        cleaned.append(
            {
                "session_id": str(item.get("session_id") or uuid.uuid4().hex),
                "title": str(item.get("title") or "New chat"),
                "created_at": str(item.get("created_at") or utc_now_iso()),
                "updated_at": str(item.get("updated_at") or item.get("created_at") or utc_now_iso()),
                "messages": list(messages) if isinstance(messages, list) else [],
            }
        )
    cleaned.sort(key=lambda row: str(row.get("updated_at") or ""), reverse=True)
    return cleaned


def _save_conversations() -> None:
    payload = json.dumps(conversations_store, indent=2, ensure_ascii=True).encode("utf-8")
    staged = _stage_bytes_file(CONVERSATIONS_FILE, payload, encrypt=security_manager.configured)
    try:
        os.replace(staged, CONVERSATIONS_FILE)
    finally:
        if staged.exists():
            staged.unlink(missing_ok=True)


def _conversation_title(question: str) -> str:
    normalized = " ".join(question.strip().split())
    if not normalized:
        return "New chat"
    return normalized[:72]


def _find_conversation(session_id: str) -> Dict[str, Any] | None:
    for conversation in conversations_store:
        if str(conversation.get("session_id")) == session_id:
            return conversation
    return None


def _conversation_summaries() -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for conversation in sorted(conversations_store, key=lambda row: str(row.get("updated_at") or ""), reverse=True):
        messages = list(conversation.get("messages") or [])
        summaries.append(
            {
                "session_id": conversation.get("session_id"),
                "title": conversation.get("title", "New chat"),
                "message_count": len(messages),
                "created_at": conversation.get("created_at", ""),
                "updated_at": conversation.get("updated_at", ""),
                "last_message_preview": str(messages[-1].get("text", ""))[:120] if messages else "",
            }
        )
    return summaries


def _conversation_followup_query(question: str, history: Sequence[Dict[str, Any]]) -> str:
    normalized = question.strip()
    if not history:
        return normalized

    user_messages = [str(message.get("text") or "").strip() for message in history if str(message.get("role") or "") == "user"]
    user_messages = [text for text in user_messages if text]
    if not user_messages:
        return normalized

    lowered = normalized.lower()
    followup_prefixes = (
        "and ",
        "also ",
        "what about",
        "how about",
        "why ",
        "how ",
        "what ",
        "compare ",
        "then ",
    )
    referential_tokens = {"it", "that", "those", "them", "this", "these", "he", "she", "they"}
    question_terms = _query_terms(normalized)
    is_followup = (
        len(question_terms) <= 3
        or lowered.startswith(followup_prefixes)
        or any(token in referential_tokens for token in _tokenize_query_text(lowered)[:3])
    )
    if not is_followup:
        return normalized

    recent_context = user_messages[-2:]
    return " ".join([*recent_context, normalized])[:420]


def _serialize_conversation_message(
    *,
    role: str,
    text: str,
    answer_mode: str | None = None,
    sources: Sequence[Dict[str, Any]] | None = None,
    confidence: float | None = None,
    confidence_label: str | None = None,
    evidence_status: str | None = None,
    follow_up_question: str | None = None,
    used_scope: Sequence[str] | None = None,
    trust_mode: bool | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": f"msg_{uuid.uuid4().hex[:12]}",
        "role": role,
        "text": text,
        "created_at": utc_now_iso(),
    }
    if answer_mode is not None:
        payload["answer_mode"] = answer_mode
    if sources is not None:
        payload["sources"] = list(sources)
    if confidence is not None:
        payload["confidence"] = confidence
    if confidence_label is not None:
        payload["confidence_label"] = confidence_label
    if evidence_status is not None:
        payload["evidence_status"] = evidence_status
    if follow_up_question is not None:
        payload["follow_up_question"] = follow_up_question
    if used_scope is not None:
        payload["used_scope"] = list(used_scope)
    if trust_mode is not None:
        payload["trust_mode"] = trust_mode
    return payload


def _model_choice_label(scope: str, choice: str) -> str:
    normalized = _normalize_model_choice(scope, choice)
    if scope == "llm":
        if normalized == "auto":
            return "Auto-select best local GGUF"
        if normalized == "extractive-fallback":
            return "Extractive fallback only"
    if scope == "embedding":
        if normalized == "auto":
            return "Auto-select local embedding model"
        if normalized == "hashed-tfidf":
            return "Hashed TF-IDF fallback"
    if scope == "reranker":
        if normalized == "auto":
            return "Auto-select local reranker"
        if normalized == "disabled":
            return "Disabled"
    return Path(normalized).name


def _model_validation(scope: str, requested: str, *, mode: str, model_name: str, last_error: str = "") -> Dict[str, Any]:
    normalized = _normalize_model_choice(scope, requested)
    requested_label = _model_choice_label(scope, normalized)
    active_label = model_name or mode or "unknown"

    if scope == "llm":
        if normalized == "auto":
            return {
                "ok": True,
                "detail": f"Auto mode active. Runtime selected {active_label}.",
                "selected": normalized,
                "active_mode": mode,
                "active_model": model_name,
            }
        if normalized == "extractive-fallback":
            ok = mode == "extractive-fallback"
            detail = "Extractive fallback is active." if ok else f"Expected extractive fallback, found {active_label}."
            return {"ok": ok, "detail": detail, "selected": normalized, "active_mode": mode, "active_model": model_name}
        expected_name = Path(normalized).name
        ok = mode == "llama-cpp" and model_name == expected_name
        detail = f"Loaded {expected_name}." if ok else (last_error or f"Could not load {expected_name}; active runtime is {active_label}.")
        return {"ok": ok, "detail": detail, "selected": normalized, "active_mode": mode, "active_model": model_name}

    if scope == "embedding":
        if normalized == "auto":
            return {
                "ok": True,
                "detail": f"Auto mode active. Runtime selected {active_label}.",
                "selected": normalized,
                "active_mode": mode,
                "active_model": model_name,
            }
        if normalized == "hashed-tfidf":
            ok = mode == "hashed-tfidf"
            detail = "Hashed TF-IDF fallback is active." if ok else f"Expected hashed TF-IDF, found {active_label}."
            return {"ok": ok, "detail": detail, "selected": normalized, "active_mode": mode, "active_model": model_name}
        expected_name = Path(normalized).name
        ok = mode == "sentence-transformers" and model_name == expected_name
        detail = f"Loaded {expected_name}." if ok else (last_error or f"Could not load {expected_name}; active runtime is {active_label}.")
        return {"ok": ok, "detail": detail, "selected": normalized, "active_mode": mode, "active_model": model_name}

    if normalized == "auto":
        return {
            "ok": True,
            "detail": (
                f"Auto mode active. Runtime selected {active_label}."
                if mode == "cross-encoder"
                else "Auto mode active. No local reranker is loaded."
            ),
            "selected": normalized,
            "active_mode": mode,
            "active_model": model_name,
        }
    if normalized == "disabled":
        ok = mode == "disabled"
        detail = "Reranker is disabled." if ok else f"Expected reranker disabled, found {active_label}."
        return {"ok": ok, "detail": detail, "selected": normalized, "active_mode": mode, "active_model": model_name}

    expected_name = Path(normalized).name
    ok = mode == "cross-encoder" and model_name == expected_name
    detail = f"Loaded {expected_name}." if ok else (last_error or f"Could not load {expected_name}; active runtime is {active_label}.")
    return {"ok": ok, "detail": detail, "selected": normalized, "active_mode": mode, "active_model": model_name}


def _build_runtime_stack(settings: Dict[str, str], rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    next_embedding = EmbeddingService(MODELS_DIR, preferred_model=settings["embedding"])
    next_embedding.prepare_runtime([str(row.get("text", "")) for row in rows if str(row.get("text", "")).strip()])
    next_reranker = RerankerService(MODELS_DIR, preferred_model=settings["reranker"])
    next_rag = RAGEngine(MODELS_DIR, provider="local", preferred_local_model=settings["llm"])

    validation = {
        "llm": _model_validation(
            "llm",
            settings["llm"],
            mode=next_rag.mode,
            model_name=next_rag.model_name,
            last_error=next_rag.last_error,
        ),
        "embedding": _model_validation(
            "embedding",
            settings["embedding"],
            mode=next_embedding.mode,
            model_name=next_embedding.model_name,
            last_error=next_embedding.last_error,
        ),
        "reranker": _model_validation(
            "reranker",
            settings["reranker"],
            mode=next_reranker.mode,
            model_name=next_reranker.model_name,
            last_error=next_reranker.last_error,
        ),
    }

    return {
        "settings": dict(settings),
        "embedding_service": next_embedding,
        "reranker_service": next_reranker,
        "rag_engine": next_rag,
        "validation": validation,
    }


def _apply_runtime_stack(stack: Dict[str, Any]) -> None:
    global embedding_service, reranker_service, rag_engine, model_settings
    embedding_service = stack["embedding_service"]
    reranker_service = stack["reranker_service"]
    rag_engine = stack["rag_engine"]
    model_settings = dict(stack["settings"])


def _model_options() -> Dict[str, List[Dict[str, str]]]:
    llm_files = sorted(MODELS_DIR.glob("*.gguf"), key=lambda path: _gguf_quality_score(path), reverse=True)
    embedding_root = MODELS_DIR / "embeddings"
    reranker_root = MODELS_DIR / "rerankers"
    embedding_dirs = [path for path in sorted(embedding_root.iterdir()) if path.is_dir()] if embedding_root.exists() else []
    reranker_dirs = [path for path in sorted(reranker_root.iterdir()) if path.is_dir()] if reranker_root.exists() else []

    return {
        "llm": [
            {"id": "auto", "label": "Auto-select", "detail": "Pick the strongest local GGUF automatically."},
            {"id": "extractive-fallback", "label": "Extractive fallback", "detail": "Disable local generation and answer only from retrieved text."},
            *[
                {"id": path.name, "label": path.name, "detail": "GGUF model under backend/models."}
                for path in llm_files
            ],
        ],
        "embedding": [
            {"id": "auto", "label": "Auto-select", "detail": "Pick the first available local embedding model or use the offline fallback."},
            {"id": "hashed-tfidf", "label": "Hashed TF-IDF", "detail": "Stay fully offline with the built-in fallback embedder."},
            *[
                {"id": f"embeddings/{path.name}", "label": path.name, "detail": "Local embedding model folder."}
                for path in embedding_dirs
            ],
        ],
        "reranker": [
            {"id": "auto", "label": "Auto-select", "detail": "Use the first available local reranker automatically."},
            {"id": "disabled", "label": "Disabled", "detail": "Skip reranking and keep hybrid lexical plus vector scoring only."},
            *[
                {"id": f"rerankers/{path.name}", "label": path.name, "detail": "Local reranker model folder."}
                for path in reranker_dirs
            ],
        ],
    }


def _build_model_manager_response(validation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    current_validation = validation or {
        "llm": _model_validation("llm", model_settings["llm"], mode=rag_engine.mode, model_name=rag_engine.model_name, last_error=getattr(rag_engine, "last_error", "")),
        "embedding": _model_validation("embedding", model_settings["embedding"], mode=embedding_service.mode, model_name=embedding_service.model_name, last_error=getattr(embedding_service, "last_error", "")),
        "reranker": _model_validation("reranker", model_settings["reranker"], mode=reranker_service.mode, model_name=reranker_service.model_name, last_error=getattr(reranker_service, "last_error", "")),
    }
    return {
        "indexed_chunks": len(chunks_store),
        "reindex_recommended": _reindex_recommended(chunks_store, meta, vector_index),
        "index_embedding_model": str(meta.get("embedding_model") or ""),
        "index_embedding_signature": str(meta.get("embedding_signature") or ""),
        "model_roots": {
            "llm": str(MODELS_DIR),
            "embedding": str(MODELS_DIR / "embeddings"),
            "reranker": str(MODELS_DIR / "rerankers"),
        },
        "llm": {
            "selected": model_settings["llm"],
            "active_mode": rag_engine.mode,
            "active_model": rag_engine.model_name,
            "options": _model_options()["llm"],
        },
        "embedding": {
            "selected": model_settings["embedding"],
            "active_mode": embedding_service.mode,
            "active_model": embedding_service.model_name,
            "requires_reindex": _reindex_recommended(chunks_store, meta, vector_index),
            "options": _model_options()["embedding"],
        },
        "reranker": {
            "selected": model_settings["reranker"],
            "active_mode": reranker_service.mode,
            "active_model": reranker_service.model_name,
            "options": _model_options()["reranker"],
        },
        "validation": current_validation,
    }


def _stage_bytes_file(path: Path, payload: bytes, *, encrypt: bool) -> Path:
    staged_path: Optional[Path] = None
    try:
        final_payload = security_manager.encrypt_bytes(payload) if encrypt else payload
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp.write(final_payload)
            staged_path = Path(tmp.name)
        return staged_path
    except Exception:
        if staged_path and staged_path.exists():
            staged_path.unlink(missing_ok=True)
        raise


def _read_artifact_bytes(path: Path) -> bytes | None:
    if not path.exists():
        return None
    payload = path.read_bytes()
    if security_manager.configured and security_manager.is_encrypted_blob(payload):
        return security_manager.decrypt_bytes(payload)
    return payload


def _serialize_chunks(chunks: List[Dict[str, Any]]) -> bytes:
    return "".join(json.dumps(row, ensure_ascii=True) + "\n" for row in chunks).encode("utf-8")


def _load_json_artifact(path: Path, default: Any) -> Any:
    raw = _read_artifact_bytes(path)
    if raw is None:
        return default
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return default


def _load_jsonl_rows(path: Path) -> List[Dict[str, Any]]:
    raw = _read_artifact_bytes(path)
    rows: List[Dict[str, Any]] = []
    if raw is None:
        return rows
    for line in raw.decode("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def load_chunks() -> List[Dict[str, Any]]:
    return _load_jsonl_rows(CHUNKS_FILE)


def load_vector_index() -> VectorIndex:
    loaded = VectorIndex(INDEX_FILE)
    raw = _read_artifact_bytes(INDEX_FILE)
    if raw:
        loaded.load_bytes(raw)
    return loaded


def append_query_log(query_type: str, query: str) -> None:
    row = {"timestamp": utc_now_iso(), "type": query_type, "query": query}
    with query_log_lock:
        rows = _load_jsonl_rows(QUERY_LOG_FILE)
        rows.append(row)
        payload = "".join(json.dumps(item, ensure_ascii=True) + "\n" for item in rows).encode("utf-8")
        staged = _stage_bytes_file(QUERY_LOG_FILE, payload, encrypt=security_manager.configured)
        try:
            os.replace(staged, QUERY_LOG_FILE)
        finally:
            if staged.exists():
                staged.unlink(missing_ok=True)


def read_query_logs() -> List[Dict[str, Any]]:
    with query_log_lock:
        return _load_jsonl_rows(QUERY_LOG_FILE)


def update_job(job_id: str, **kwargs: Any) -> None:
    with jobs_lock:
        job = jobs.get(job_id, {})
        job.update(kwargs)
        jobs[job_id] = job


def _file_name_tokens(source_file: str) -> List[str]:
    stem = Path(source_file).stem.replace("_", " ").replace("-", " ")
    return _query_terms(stem)


def _source_sequence_key(row: Dict[str, Any]) -> tuple[str, int | None]:
    raw_page = row.get("page_number")
    page_number = int(raw_page) if raw_page is not None else None
    return (str(row.get("source_file") or "unknown"), page_number)


def _build_retrieval_runtime(
    rows: Sequence[Dict[str, Any]],
) -> tuple[RetrievalStats, Dict[tuple[str, int | None], List[Dict[str, Any]]], Dict[str, int]]:
    if not rows:
        return _empty_retrieval_stats(), {}, {}

    doc_freqs: Dict[str, int] = {}
    token_counts_by_chunk: Dict[str, Dict[str, int]] = {}
    doc_lengths_by_chunk: Dict[str, int] = {}
    source_tokens_by_chunk: Dict[str, List[str]] = {}
    section_tokens_by_chunk: Dict[str, List[str]] = {}
    block_kind_by_chunk: Dict[str, str] = {}
    grouped_sequences: Dict[tuple[str, int | None], List[Dict[str, Any]]] = {}
    total_doc_length = 0

    for row in rows:
        chunk_id = str(row.get("chunk_id") or "")
        terms = _query_terms(str(row.get("text", "")))
        counts: Dict[str, int] = {}
        for term in terms:
            counts[term] = counts.get(term, 0) + 1

        if chunk_id:
            token_counts_by_chunk[chunk_id] = counts
            doc_lengths_by_chunk[chunk_id] = sum(counts.values())
            total_doc_length += doc_lengths_by_chunk[chunk_id]
            source_tokens_by_chunk[chunk_id] = _file_name_tokens(str(row.get("source_file") or ""))
            section_tokens: List[str] = []
            for item in row.get("section_path") or []:
                section_tokens.extend(_query_terms(str(item)))
            section_tokens_by_chunk[chunk_id] = section_tokens
            block_kind_by_chunk[chunk_id] = str(row.get("block_kind") or "")

        for term in counts:
            doc_freqs[term] = doc_freqs.get(term, 0) + 1

        grouped_sequences.setdefault(_source_sequence_key(row), []).append(row)

    sequence_positions: Dict[str, int] = {}
    for items in grouped_sequences.values():
        items.sort(key=lambda item: (int(item.get("chunk_index", 0)), str(item.get("chunk_id", ""))))
        for index, item in enumerate(items):
            chunk_id = str(item.get("chunk_id") or "")
            if chunk_id:
                sequence_positions[chunk_id] = index

    doc_count = max(1, len(token_counts_by_chunk))
    avg_doc_length = total_doc_length / doc_count if total_doc_length else 1.0
    return (
        RetrievalStats(
            doc_count=len(token_counts_by_chunk),
            avg_doc_length=avg_doc_length,
            doc_freqs=doc_freqs,
            token_counts_by_chunk=token_counts_by_chunk,
            doc_lengths_by_chunk=doc_lengths_by_chunk,
            source_tokens_by_chunk=source_tokens_by_chunk,
            section_tokens_by_chunk=section_tokens_by_chunk,
            block_kind_by_chunk=block_kind_by_chunk,
        ),
        grouped_sequences,
        sequence_positions,
    )


def refresh_memory_maps() -> None:
    global chunk_by_id, retrieval_stats, chunk_sequences, chunk_sequence_positions
    chunk_by_id = {c["chunk_id"]: c for c in chunks_store if "chunk_id" in c}
    retrieval_stats, chunk_sequences, chunk_sequence_positions = _build_retrieval_runtime(chunks_store)


def build_index_map(rows: List[Dict[str, Any]]) -> Dict[str, str]:
    return {str(i): row["chunk_id"] for i, row in enumerate(rows)}


def prepare_index_state(rows: List[Dict[str, Any]], previous_meta: Dict[str, Any], *, last_index_time: str) -> PreparedIndexState:
    texts = [c["text"] for c in rows]
    emb_res = embedding_service.embed_corpus(texts)
    prepared_vector_index = VectorIndex()
    prepared_vector_index.rebuild(emb_res.vectors)
    prepared_graph_cache = graph_builder.build_graph(rows)
    prepared_meta = dict(previous_meta)
    prepared_meta.update(
        {
            "indexed_files": sorted({c["source_file"] for c in rows}),
            "last_index_time": last_index_time,
            "chunking_version": CHUNKING_VERSION,
            "embedding_model": emb_res.model_name,
            "embedding_mode": emb_res.mode,
            "embedding_signature": embedding_service.index_signature(),
            "embedding_dim": int(emb_res.vectors.shape[1]) if emb_res.vectors.ndim == 2 else 0,
            "total_chunks": len(rows),
            "vector_backend": prepared_vector_index.backend_name,
        }
    )
    return PreparedIndexState(
        chunks=list(rows),
        chunk_by_id={c["chunk_id"]: c for c in rows if "chunk_id" in c},
        index_map=build_index_map(rows),
        meta=prepared_meta,
        graph_cache=prepared_graph_cache,
        vector_index=prepared_vector_index,
        index_bytes=prepared_vector_index.dump_bytes(),
    )


def commit_prepared_state(prepared: PreparedIndexState) -> None:
    global chunks_store, chunk_by_id, index_map, meta, graph_cache, vector_index

    encrypt = security_manager.configured
    staged_chunks = _stage_bytes_file(CHUNKS_FILE, _serialize_chunks(prepared.chunks), encrypt=encrypt)
    staged_index_map = _stage_bytes_file(
        INDEX_MAP_FILE,
        json.dumps(prepared.index_map, indent=2, ensure_ascii=True).encode("utf-8"),
        encrypt=encrypt,
    )
    staged_graph = _stage_bytes_file(
        GRAPH_FILE,
        json.dumps(prepared.graph_cache, indent=2, ensure_ascii=True).encode("utf-8"),
        encrypt=encrypt,
    )
    staged_meta = _stage_bytes_file(
        META_FILE,
        json.dumps(prepared.meta, indent=2, ensure_ascii=True).encode("utf-8"),
        encrypt=encrypt,
    )
    staged_index = None
    if prepared.index_bytes is not None:
        staged_index = _stage_bytes_file(INDEX_FILE, prepared.index_bytes, encrypt=encrypt)

    staged_paths = [staged_chunks, staged_index_map, staged_graph, staged_meta]
    if staged_index is not None:
        staged_paths.append(staged_index)

    try:
        if staged_index is None:
            INDEX_FILE.unlink(missing_ok=True)
        else:
            os.replace(staged_index, INDEX_FILE)
        os.replace(staged_index_map, INDEX_MAP_FILE)
        os.replace(staged_graph, GRAPH_FILE)
        os.replace(staged_meta, META_FILE)
        os.replace(staged_chunks, CHUNKS_FILE)
    finally:
        for staged in staged_paths:
            if staged.exists():
                staged.unlink(missing_ok=True)

    chunks_store = prepared.chunks
    chunk_by_id = prepared.chunk_by_id
    index_map = prepared.index_map
    meta = prepared.meta
    graph_cache = prepared.graph_cache
    vector_index = prepared.vector_index
    vector_index.index_path = INDEX_FILE
    refresh_memory_maps()


def rebuild_all_indices(*, last_index_time: str) -> None:
    prepared = prepare_index_state(chunks_store, meta, last_index_time=last_index_time)
    commit_prepared_state(prepared)


def filter_new_documents(docs: List[Any], existing_chunks: List[Dict[str, Any]]) -> tuple[List[Any], List[str]]:
    existing_source_ids = {chunk.get("source_id") for chunk in existing_chunks if chunk.get("source_id")}
    legacy_source_files = {
        chunk.get("source_file")
        for chunk in existing_chunks
        if chunk.get("source_file") and not chunk.get("source_id")
    }
    grouped: Dict[str, List[Any]] = {}
    for doc in docs:
        source_id = getattr(doc, "source_id", None)
        grouped.setdefault(source_id or f"legacy:{doc.source_file}", []).append(doc)

    selected: List[Any] = []
    skipped_files: List[str] = []
    for group_docs in grouped.values():
        first = group_docs[0]
        source_id = getattr(first, "source_id", None)
        source_file = first.source_file
        already_indexed = (source_id and source_id in existing_source_ids) or (source_file in legacy_source_files)
        if already_indexed:
            skipped_files.append(source_file)
            continue
        selected.extend(group_docs)
    return selected, skipped_files


def encrypt_existing_artifacts() -> None:
    if not security_manager.configured or not security_manager.unlocked:
        return
    for path in _managed_artifact_paths():
        if not path.exists():
            continue
        payload = path.read_bytes()
        if security_manager.is_encrypted_blob(payload):
            continue
        staged = _stage_bytes_file(path, payload, encrypt=True)
        try:
            os.replace(staged, path)
        finally:
            if staged.exists():
                staged.unlink(missing_ok=True)


def _prepare_runtime_embeddings(rows: Sequence[Dict[str, Any]]) -> None:
    texts = [str(row.get("text", "")) for row in rows if str(row.get("text", "")).strip()]
    embedding_service.prepare_runtime(texts)


def _persisted_index_needs_rebuild(
    rows: Sequence[Dict[str, Any]],
    current_meta: Dict[str, Any],
    current_vector_index: VectorIndex,
) -> bool:
    if not rows:
        return False
    if current_vector_index.size != len(rows):
        return True
    if str(current_meta.get("chunking_version") or "") != CHUNKING_VERSION:
        return True
    stored_signature = str(current_meta.get("embedding_signature") or "").strip()
    if not stored_signature:
        return True
    return stored_signature != embedding_service.index_signature()


def load_persisted_state() -> None:
    global chunks_store, index_map, meta, graph_cache, vector_index, conversations_store
    chunks_store = load_chunks()
    index_map = _load_json_artifact(INDEX_MAP_FILE, {})
    meta = _load_json_artifact(META_FILE, {})
    graph_cache = _load_json_artifact(GRAPH_FILE, {"nodes": [], "edges": []})
    conversations_store = _load_conversations()
    vector_index = load_vector_index()
    stack = _build_runtime_stack(_load_model_settings(), chunks_store)
    _apply_runtime_stack(stack)
    if _persisted_index_needs_rebuild(chunks_store, meta, vector_index):
        prepared = prepare_index_state(chunks_store, meta, last_index_time=str(meta.get("last_index_time") or utc_now_iso()))
        commit_prepared_state(prepared)
        return
    refresh_memory_maps()


@contextmanager
def materialize_input_paths(file_paths: List[Path]) -> Iterator[List[Path]]:
    if not security_manager.configured:
        yield file_paths
        return

    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        materialized: List[Path] = []
        for source_path in file_paths:
            if _artifact_is_upload(source_path):
                raw = _read_artifact_bytes(source_path) or b""
                target = temp_dir / uuid.uuid4().hex / source_path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                materialized.append(target)
            else:
                materialized.append(source_path)
        yield materialized


def process_ingestion(job_id: str, file_paths: List[Path]) -> None:
    try:
        update_job(job_id, state="processing", step="extracting", progress=10, message="Extracting text")
        with materialize_input_paths(file_paths) as readable_paths:
            docs = extract_many(readable_paths)
        if not docs:
            update_job(job_id, state="error", step="extracting", progress=100, message="No readable text found")
            return

        update_job(job_id, state="processing", step="chunking", progress=35, message="Creating chunks")
        skipped_files: List[str] = []
        new_chunks: List[Dict[str, Any]] = []
        with index_lock:
            docs, skipped_files = filter_new_documents(docs, chunks_store)
            if not docs:
                update_job(
                    job_id,
                    state="done",
                    step="completed",
                    progress=100,
                    message="All selected files were already indexed",
                )
                return

            for doc in docs:
                segments = chunk_document(doc.text, chunk_size=900, overlap=150)
                for idx, segment in enumerate(segments):
                    new_chunks.append(
                        {
                            "chunk_id": f"chunk_{uuid.uuid4().hex[:12]}",
                            "text": segment.text,
                            "source_file": doc.source_file,
                            "source_id": getattr(doc, "source_id", None),
                            "page_number": doc.page_number,
                            "chunk_index": idx,
                            "section_path": segment.section_path,
                            "block_kind": segment.block_kind,
                            "created_at": utc_now_iso(),
                        }
                    )

            if not new_chunks:
                update_job(job_id, state="error", step="chunking", progress=100, message="No chunks created")
                return

            update_job(job_id, state="processing", step="embedding", progress=60, message="Computing embeddings")
            prepared = prepare_index_state(
                [*chunks_store, *new_chunks],
                meta,
                last_index_time=utc_now_iso(),
            )
            commit_prepared_state(prepared)

        update_job(job_id, state="processing", step="graph", progress=90, message="Updating graph")
        message = f"Indexed {len(new_chunks)} chunks"
        if skipped_files:
            message += f" ({len(skipped_files)} file(s) already indexed)"
        update_job(job_id, state="done", step="completed", progress=100, message=message)
    except Exception as exc:
        update_job(job_id, state="error", step="failed", progress=100, message=str(exc))


def process_reindex(job_id: str) -> None:
    try:
        with index_lock:
            if not chunks_store:
                update_job(job_id, state="done", step="completed", progress=100, message="No indexed data to reindex")
                return
            update_job(job_id, state="processing", step="embedding", progress=40, message="Rebuilding embeddings and vector index")
            prepared = prepare_index_state(chunks_store, meta, last_index_time=utc_now_iso())
            commit_prepared_state(prepared)
        update_job(job_id, state="done", step="completed", progress=100, message=f"Reindexed {len(chunks_store)} chunks")
    except Exception as exc:
        update_job(job_id, state="error", step="failed", progress=100, message=str(exc))


def create_job() -> str:
    job_id = uuid.uuid4().hex
    update_job(job_id, state="processing", step="queued", progress=0, message="Queued")
    return job_id


def save_uploads(job_id: str, files: List[UploadFile]) -> List[Path]:
    job_dir = UPLOADS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    for file in files:
        original_name = Path(file.filename or f"file_{uuid.uuid4().hex}.txt").name
        file_dir = job_dir / uuid.uuid4().hex
        file_dir.mkdir(parents=True, exist_ok=True)
        target = file_dir / original_name
        content = file.file.read()
        payload = security_manager.encrypt_bytes(content) if security_manager.configured else content
        target.write_bytes(payload)
        paths.append(target)
    return paths


def startup_load() -> None:
    reset_runtime_state(clear_jobs=True)


def ensure_unlocked() -> None:
    if not security_manager.configured:
        raise HTTPException(status_code=423, detail="Set a passphrase to enable encrypted storage")
    if not security_manager.unlocked:
        raise HTTPException(status_code=423, detail="Backend is locked")


startup_load()


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, **security_manager.status()}


@app.get("/security/status")
def security_status() -> Dict[str, bool]:
    return security_manager.status()


@app.post("/security/setup")
def security_setup(payload: SecurityPassphraseRequest) -> Dict[str, bool]:
    if security_manager.configured:
        raise HTTPException(status_code=400, detail="Security is already configured")
    try:
        security_manager.setup(payload.passphrase)
        with index_lock:
            encrypt_existing_artifacts()
            load_persisted_state()
        return security_manager.status()
    except SecurityError as exc:
        security_manager.lock()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/security/unlock")
def security_unlock(payload: SecurityPassphraseRequest) -> Dict[str, bool]:
    if not security_manager.configured:
        raise HTTPException(status_code=400, detail="Security is not configured")
    try:
        security_manager.unlock(payload.passphrase)
        with index_lock:
            load_persisted_state()
        return security_manager.status()
    except SecurityError as exc:
        security_manager.lock()
        reset_runtime_state(clear_jobs=False)
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.post("/security/lock")
def security_lock() -> Dict[str, bool]:
    with jobs_lock:
        if any(job.get("state") == "processing" for job in jobs.values()):
            raise HTTPException(status_code=409, detail="Cannot lock while ingestion is running")
    with index_lock:
        reset_runtime_state(clear_jobs=True)
        security_manager.lock()
    return security_manager.status()


@app.post("/ingest")
async def ingest(files: List[UploadFile] = File(...), background_tasks: BackgroundTasks = None) -> Dict[str, str]:
    ensure_unlocked()
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    job_id = create_job()
    saved = save_uploads(job_id, files)
    if background_tasks is None:
        process_ingestion(job_id, saved)
    else:
        background_tasks.add_task(process_ingestion, job_id, saved)
    return {"job_id": job_id}


@app.post("/ingest_demo")
def ingest_demo(background_tasks: BackgroundTasks) -> Dict[str, str]:
    ensure_unlocked()
    demo_files = [p for p in DEMO_DATA_DIR.glob("*") if p.is_file()]
    if not demo_files:
        raise HTTPException(status_code=400, detail="No demo data found")
    job_id = create_job()
    background_tasks.add_task(process_ingestion, job_id, demo_files)
    return {"job_id": job_id}


@app.get("/status")
def status(job_id: str) -> Dict[str, Any]:
    ensure_unlocked()
    with jobs_lock:
        if job_id not in jobs:
            return {"state": "error", "step": "unknown", "progress": 100, "message": "Job not found"}
        return jobs[job_id]


def _reindex_recommended(
    current_chunks: Sequence[Dict[str, Any]],
    current_meta: Dict[str, Any],
    current_vector_index: VectorIndex,
) -> bool:
    if not current_chunks:
        return False
    if current_vector_index.size != len(current_chunks):
        return True
    if str(current_meta.get("chunking_version") or "") != CHUNKING_VERSION:
        return True
    stored_signature = str(current_meta.get("embedding_signature") or "").strip()
    if not stored_signature:
        return True
    return stored_signature != embedding_service.index_signature()


@app.get("/stats")
def stats() -> Dict[str, Any]:
    ensure_unlocked()
    with index_lock:
        current_chunks = chunks_store
        current_graph = graph_cache
        current_meta = meta
        current_vector_index = vector_index
    return {
        "indexed_files": len({c.get("source_file") for c in current_chunks}),
        "total_chunks": len(current_chunks),
        "graph_nodes": len(current_graph.get("nodes", [])),
        "last_index_time": current_meta.get("last_index_time", ""),
        "chunking_version": current_meta.get("chunking_version", CHUNKING_VERSION),
        "reindex_recommended": _reindex_recommended(current_chunks, current_meta, current_vector_index),
        "embedding_model": embedding_service.model_name,
        "embedding_mode": embedding_service.mode,
        "vector_backend": current_vector_index.backend_name,
        "reranker_mode": reranker_service.mode,
        "reranker_model": reranker_service.model_name,
        "graph_mode": graph_builder.mode,
        "pdf_backend": detect_pdf_backend(),
        "llm_mode": rag_engine.mode,
        "llm_model": rag_engine.model_name,
        "feature_status": build_feature_status(
            MODELS_DIR,
            embedding_mode=embedding_service.mode,
            embedding_model=embedding_service.model_name,
            vector_backend=current_vector_index.backend_name,
            graph_mode=graph_builder.mode,
            reranker_mode=reranker_service.mode,
            reranker_model=reranker_service.model_name,
            llm_mode=rag_engine.mode,
            llm_model=rag_engine.model_name,
        ),
    }


@app.get("/insights")
def insights() -> Dict[str, Any]:
    ensure_unlocked()
    with index_lock:
        current_graph = graph_cache
    return build_insights(read_query_logs(), current_graph)


@app.get("/catalog")
def catalog() -> Dict[str, Any]:
    ensure_unlocked()
    with index_lock:
        current_chunks = chunks_store
    return {"sources": _build_source_catalog(current_chunks)}


@app.get("/conversations")
def list_conversations() -> Dict[str, Any]:
    ensure_unlocked()
    with index_lock:
        return {"conversations": _conversation_summaries()}


@app.post("/conversations")
def create_conversation() -> Dict[str, Any]:
    ensure_unlocked()
    conversation = {
        "session_id": uuid.uuid4().hex,
        "title": "New chat",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "messages": [],
    }
    with index_lock:
        conversations_store.insert(0, conversation)
        _save_conversations()
        return dict(conversation)


@app.get("/conversations/{session_id}")
def get_conversation(session_id: str) -> Dict[str, Any]:
    ensure_unlocked()
    with index_lock:
        conversation = _find_conversation(session_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return dict(conversation)


@app.delete("/conversations/{session_id}")
def delete_conversation(session_id: str) -> Dict[str, bool]:
    ensure_unlocked()
    with index_lock:
        conversation = _find_conversation(session_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        conversations_store.remove(conversation)
        _save_conversations()
    return {"ok": True}


@app.get("/models")
def get_models() -> Dict[str, Any]:
    ensure_unlocked()
    with index_lock:
        return _build_model_manager_response()


@app.post("/models/apply")
def apply_models(payload: ModelSettingsRequest) -> Dict[str, Any]:
    ensure_unlocked()
    next_settings = dict(model_settings)
    if payload.llm is not None:
        next_settings["llm"] = _normalize_model_choice("llm", payload.llm)
    if payload.embedding is not None:
        next_settings["embedding"] = _normalize_model_choice("embedding", payload.embedding)
    if payload.reranker is not None:
        next_settings["reranker"] = _normalize_model_choice("reranker", payload.reranker)

    with index_lock:
        stack = _build_runtime_stack(next_settings, chunks_store)
        invalid = [name for name, result in stack["validation"].items() if not bool(result.get("ok"))]
        if invalid:
            detail = "; ".join(str(stack["validation"][name]["detail"]) for name in invalid)
            raise HTTPException(status_code=400, detail=detail)
        _apply_runtime_stack(stack)
        _save_model_settings(model_settings)
        return _build_model_manager_response(validation=stack["validation"])


@app.post("/models/validate")
def validate_models(payload: ModelSettingsRequest) -> Dict[str, Any]:
    ensure_unlocked()
    next_settings = dict(model_settings)
    if payload.llm is not None:
        next_settings["llm"] = _normalize_model_choice("llm", payload.llm)
    if payload.embedding is not None:
        next_settings["embedding"] = _normalize_model_choice("embedding", payload.embedding)
    if payload.reranker is not None:
        next_settings["reranker"] = _normalize_model_choice("reranker", payload.reranker)

    with index_lock:
        stack = _build_runtime_stack(next_settings, chunks_store)
        response = _build_model_manager_response(validation=stack["validation"])
        response["llm"]["selected"] = next_settings["llm"]
        response["embedding"]["selected"] = next_settings["embedding"]
        response["reranker"]["selected"] = next_settings["reranker"]
        return response


@app.post("/reindex")
def reindex(background_tasks: BackgroundTasks = None) -> Dict[str, str]:
    ensure_unlocked()
    with index_lock:
        if not chunks_store:
            raise HTTPException(status_code=400, detail="No indexed data to reindex")
    job_id = create_job()
    if background_tasks is None:
        process_reindex(job_id)
    else:
        background_tasks.add_task(process_reindex, job_id)
    return {"job_id": job_id}


@app.get("/evaluate")
def evaluate() -> Dict[str, Any]:
    ensure_unlocked()
    with index_lock:
        current_chunks = list(chunks_store)
    return _evaluate_retrieval(current_chunks)


def _tokenize_query_text(text: str) -> List[str]:
    return SEARCH_TOKEN_RE.findall(text.lower())


def _query_terms(text: str) -> List[str]:
    return [token for token in _tokenize_query_text(text) if token not in SEARCH_STOPWORDS and len(token) > 2]


def _normalized_source_scope(source_files: Sequence[str] | None) -> List[str]:
    cleaned: List[str] = []
    seen: set[str] = set()
    for raw in source_files or []:
        value = raw.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned


def _file_kind(source_file: str) -> str:
    suffix = Path(source_file).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".txt", ".md"}:
        return "text"
    if suffix in {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cpp", ".h"}:
        return "code"
    if suffix in {".json", ".yaml", ".yml"}:
        return "data"
    return "file"


def _build_source_catalog(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        source_file = str(row.get("source_file") or "unknown")
        entry = grouped.setdefault(
            source_file,
            {
                "source_file": source_file,
                "chunks": 0,
                "pages": set(),
                "kind": _file_kind(source_file),
                "last_added_at": row.get("created_at") or "",
            },
        )
        entry["chunks"] += 1
        page_number = row.get("page_number")
        if page_number:
            entry["pages"].add(int(page_number))
        created_at = str(row.get("created_at") or "")
        if created_at and created_at > str(entry["last_added_at"]):
            entry["last_added_at"] = created_at

    catalog = []
    for entry in grouped.values():
        catalog.append(
            {
                "source_file": entry["source_file"],
                "chunks": entry["chunks"],
                "pages": len(entry["pages"]),
                "kind": entry["kind"],
                "last_added_at": entry["last_added_at"],
            }
        )
    catalog.sort(key=lambda item: (-int(item["chunks"]), str(item["source_file"]).lower()))
    return catalog


def _local_model_inventory() -> Dict[str, List[str]]:
    embedding_root = MODELS_DIR / "embeddings"
    reranker_root = MODELS_DIR / "rerankers"
    return {
        "llm_files": [path.name for path in sorted(MODELS_DIR.glob("*.gguf"))],
        "embedding_folders": [path.name for path in sorted(embedding_root.iterdir())] if embedding_root.exists() else [],
        "reranker_folders": [path.name for path in sorted(reranker_root.iterdir())] if reranker_root.exists() else [],
    }


def _evaluation_keywords(row: Dict[str, Any]) -> List[str]:
    tokens: List[str] = []
    for item in row.get("section_path") or []:
        tokens.extend(_query_terms(str(item)))
    tokens.extend(_file_name_tokens(str(row.get("source_file") or "")))
    tokens.extend(_query_terms(str(row.get("text", "")))[:10])

    unique: List[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        unique.append(token)
    return unique[:6]


def _evaluation_query(row: Dict[str, Any]) -> str:
    keywords = _evaluation_keywords(row)
    if keywords:
        return f"Explain {' '.join(keywords)}"
    return str(row.get("source_file") or "document")


def _benchmark_rows(rows: Sequence[Dict[str, Any]], limit: int = 12) -> List[Dict[str, Any]]:
    candidates = [
        row
        for row in rows
        if str(row.get("chunk_id") or "").strip() and len(str(row.get("text") or "").strip()) >= 80
    ]
    if not candidates:
        return []

    selected: List[Dict[str, Any]] = []
    seen_sources: set[str] = set()
    for row in candidates:
        source_file = str(row.get("source_file") or "")
        if source_file in seen_sources:
            continue
        seen_sources.add(source_file)
        selected.append(row)
        if len(selected) >= limit:
            return selected

    for row in candidates:
        if row in selected:
            continue
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def _evaluate_retrieval(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    benchmark_rows = _benchmark_rows(rows)
    inventory = _local_model_inventory()
    if not benchmark_rows:
        return {
            "total_cases": 0,
            "retrieval_top1": 0.0,
            "retrieval_top3": 0.0,
            "retrieval_top5": 0.0,
            "mean_reciprocal_rank": 0.0,
            "avg_query_terms": 0.0,
            "stack": {
                "llm_mode": rag_engine.mode,
                "llm_model": rag_engine.model_name,
                "embedding_mode": embedding_service.mode,
                "embedding_model": embedding_service.model_name,
                "reranker_mode": reranker_service.mode,
                "reranker_model": reranker_service.model_name,
            },
            "available_models": inventory,
            "cases": [],
        }

    cases: List[Dict[str, Any]] = []
    top1_hits = 0
    top3_hits = 0
    top5_hits = 0
    reciprocal_rank_sum = 0.0
    total_query_terms = 0

    for row in benchmark_rows:
        query = _evaluation_query(row)
        total_query_terms += len(_query_terms(query))
        results = _search_for_answer(query, 5)
        rank = None
        for index, result in enumerate(results, start=1):
            if str(result.get("chunk_id")) == str(row.get("chunk_id")):
                rank = index
                break

        top1_hits += 1 if rank == 1 else 0
        top3_hits += 1 if rank is not None and rank <= 3 else 0
        top5_hits += 1 if rank is not None and rank <= 5 else 0
        reciprocal_rank_sum += 1.0 / rank if rank is not None else 0.0

        top_hit = results[0] if results else {}
        cases.append(
            {
                "query": query,
                "source_file": row.get("source_file"),
                "expected_chunk_id": row.get("chunk_id"),
                "top_hit_chunk_id": top_hit.get("chunk_id", ""),
                "top_hit_source_file": top_hit.get("source_file", ""),
                "rank": rank,
                "hit_in_top_1": rank == 1,
                "hit_in_top_3": rank is not None and rank <= 3,
                "hit_in_top_5": rank is not None and rank <= 5,
            }
        )

    total_cases = len(cases)
    return {
        "total_cases": total_cases,
        "retrieval_top1": round(top1_hits / max(1, total_cases), 4),
        "retrieval_top3": round(top3_hits / max(1, total_cases), 4),
        "retrieval_top5": round(top5_hits / max(1, total_cases), 4),
        "mean_reciprocal_rank": round(reciprocal_rank_sum / max(1, total_cases), 4),
        "avg_query_terms": round(total_query_terms / max(1, total_cases), 2),
        "stack": {
            "llm_mode": rag_engine.mode,
            "llm_model": rag_engine.model_name,
            "embedding_mode": embedding_service.mode,
            "embedding_model": embedding_service.model_name,
            "reranker_mode": reranker_service.mode,
            "reranker_model": reranker_service.model_name,
        },
        "available_models": inventory,
        "cases": cases,
    }


def _normalize_answer_mode(mode: str) -> str:
    allowed = {"answer", "study_guide", "flashcards", "quiz"}
    cleaned = mode.strip().lower().replace("-", "_")
    return cleaned if cleaned in allowed else "answer"


def _assess_evidence(question: str, sources: Sequence[Dict[str, Any]], source_scope: Sequence[str] | None = None) -> Dict[str, Any]:
    if not sources:
        follow_up = "Try selecting a relevant file or asking a narrower question."
        if source_scope:
            follow_up = "No evidence was found inside the selected files. Clear the scope or pick a more relevant file."
        return {
            "confidence": 0.0,
            "confidence_label": "low",
            "evidence_status": "insufficient",
            "follow_up_question": follow_up,
        }

    query_terms = set(_query_terms(question))
    source_blob = " ".join(str(source.get("text", "")).lower() for source in sources[:6])
    coverage = 1.0
    missing_terms: List[str] = []
    if query_terms:
        matched_terms = [term for term in query_terms if term in source_blob]
        coverage = len(matched_terms) / len(query_terms)
        missing_terms = [term for term in query_terms if term not in source_blob][:3]

    top_scores = [float(source.get("score", 0.0)) for source in sources[: min(4, len(sources))]]
    avg_score = sum(top_scores) / max(1, len(top_scores))
    source_count_score = min(1.0, len(sources) / 4.0)
    source_diversity = min(1.0, len({source.get("source_file") for source in sources}) / 3.0)
    confidence = min(0.99, round((avg_score * 0.48) + (coverage * 0.32) + (source_count_score * 0.12) + (source_diversity * 0.08), 4))

    if coverage >= 0.55 and confidence >= 0.7:
        return {
            "confidence": confidence,
            "confidence_label": "high",
            "evidence_status": "grounded",
            "follow_up_question": "",
        }

    if coverage >= 0.3 and confidence >= 0.45:
        return {
            "confidence": confidence,
            "confidence_label": "medium",
            "evidence_status": "limited",
            "follow_up_question": "I found partial evidence. Check the cited sources before relying on this answer.",
        }

    if source_scope:
        follow_up = "The selected files do not cover this question well. Clear the file scope or pick a more relevant file."
    elif missing_terms:
        follow_up = f"Try narrowing the question around {', '.join(missing_terms)} or select the most relevant file."
    else:
        follow_up = "Try asking a narrower question or selecting the most relevant file."

    return {
        "confidence": confidence,
        "confidence_label": "low",
        "evidence_status": "insufficient",
        "follow_up_question": follow_up,
    }


def _insufficient_evidence_answer(question: str, sources: Sequence[Dict[str, Any]], assessment: Dict[str, Any]) -> str:
    if not sources:
        return "I do not have enough evidence in your local data to answer that confidently."

    highlights = []
    for source in sources[:2]:
        label = str(source.get("source_file") or "unknown")
        page_number = source.get("page_number")
        if page_number:
            label = f"{label} p.{page_number}"
        highlights.append(f"- {label}")

    lines = [
        "I do not have enough evidence in your local data to answer that confidently.",
        "",
        "Closest supporting sources:",
        *highlights,
    ]
    follow_up = str(assessment.get("follow_up_question") or "").strip()
    if follow_up:
        lines.extend(["", f"Next step: {follow_up}"])
    return "\n".join(lines)


def _retrieval_queries(text: str) -> List[str]:
    normalized = text.strip()
    if not normalized:
        return []

    variants = [normalized]
    terms = _query_terms(normalized)
    if terms:
        keyword_query = " ".join(terms[:8])
        if keyword_query and keyword_query.lower() != normalized.lower():
            variants.append(keyword_query)

        if len(terms) >= 3:
            focused_query = " ".join(terms[:5])
            if focused_query and focused_query.lower() not in {item.lower() for item in variants}:
                variants.append(focused_query)

    return variants


def _semantic_score(vector_score: float) -> float:
    return round(max(0.0, min(1.0, (float(vector_score) + 1.0) / 2.0)), 4)


def _retrieval_intent(query: str) -> str:
    lowered = query.lower()
    if any(token in lowered for token in ["compare", "difference", "different", "vs", "versus"]):
        return "compare"
    if any(token in lowered for token in ["plan", "schedule", "roadmap", "revise", "revision"]):
        return "plan"
    if any(token in lowered for token in ["list", "points", "steps", "bullets"]):
        return "list"
    return "answer"


def _metadata_match_score(query_terms: Sequence[str], chunk_id: str | None, intent: str) -> float:
    if not chunk_id or not query_terms:
        return 0.0

    query_term_set = set(query_terms)
    source_tokens = set(retrieval_stats.source_tokens_by_chunk.get(chunk_id, []))
    section_tokens = set(retrieval_stats.section_tokens_by_chunk.get(chunk_id, []))
    block_kind = retrieval_stats.block_kind_by_chunk.get(chunk_id, "")

    source_overlap = len(query_term_set & source_tokens) / max(1, len(query_term_set))
    section_overlap = len(query_term_set & section_tokens) / max(1, len(query_term_set))

    intent_bonus = 0.0
    if intent in {"list", "plan"} and block_kind == "list":
        intent_bonus += 0.14
    if intent == "compare" and any(token in section_tokens or token in source_tokens for token in {"compare", "comparison", "difference", "versus", "vs"}):
        intent_bonus += 0.12

    return round(min(1.0, (source_overlap * 0.45) + (section_overlap * 0.55) + intent_bonus), 4)


def _normalized_lexical_score(raw_score: float, query_term_count: int) -> float:
    if raw_score <= 0.0:
        return 0.0
    scale = max(1.2, query_term_count * 0.85)
    return round(min(1.0, raw_score / (raw_score + scale)), 4)


def _raw_bm25_score(query_terms: Sequence[str], text: str, *, chunk_id: str | None = None) -> float:
    if not query_terms or retrieval_stats.doc_count <= 0:
        return 0.0

    counts = retrieval_stats.token_counts_by_chunk.get(chunk_id or "")
    if counts is None:
        counts = {}
        for term in _query_terms(text):
            counts[term] = counts.get(term, 0) + 1

    doc_length = retrieval_stats.doc_lengths_by_chunk.get(chunk_id or "", sum(counts.values()))
    if doc_length <= 0:
        return 0.0

    k1 = 1.5
    b = 0.75
    avg_doc_length = max(1.0, retrieval_stats.avg_doc_length)
    score = 0.0
    for term in dict.fromkeys(query_terms):
        freq = counts.get(term, 0)
        if freq <= 0:
            continue
        df = retrieval_stats.doc_freqs.get(term, 0)
        idf = math.log(1.0 + ((retrieval_stats.doc_count - df + 0.5) / (df + 0.5)))
        denom = freq + (k1 * (1.0 - b + (b * (doc_length / avg_doc_length))))
        score += idf * (((k1 + 1.0) * freq) / denom)
    return round(score, 4)


def _relevance_signals(query: str, text: str, vector_score: float, *, chunk_id: str | None = None) -> Dict[str, float]:
    semantic_score = _semantic_score(vector_score)
    query_terms = _query_terms(query)
    intent = _retrieval_intent(query)
    lexical_score = _normalized_lexical_score(_raw_bm25_score(query_terms, text, chunk_id=chunk_id), len(query_terms))
    metadata_score = _metadata_match_score(query_terms, chunk_id, intent)
    base_signals = {
        "score": round(semantic_score, 4),
        "semantic_score": round(semantic_score, 4),
        "lexical_score": lexical_score,
        "metadata_score": metadata_score,
        "coverage": 0.0,
        "bigram_score": 0.0,
        "phrase_match": 0.0,
        "lead_match": 0.0,
        "query_term_count": float(len(query_terms)),
    }
    if not query_terms:
        return base_signals

    text_tokens = _tokenize_query_text(text)
    if not text_tokens:
        return base_signals

    text_token_set = set(text_tokens)
    query_term_set = set(query_terms)
    coverage = len(query_term_set & text_token_set) / max(1, len(query_term_set))

    query_bigrams = list(zip(query_terms, query_terms[1:]))
    text_bigrams = set(zip(text_tokens, text_tokens[1:]))
    bigram_score = 0.0
    if query_bigrams:
        matched_bigrams = sum(1 for bigram in query_bigrams if bigram in text_bigrams)
        bigram_score = matched_bigrams / len(query_bigrams)

    normalized_query = " ".join(query_terms)
    normalized_text = " ".join(text_tokens)
    phrase_match = 1.0 if len(query_terms) >= 2 and normalized_query in normalized_text else 0.0

    lead_window = " ".join(text_tokens[: min(28, len(text_tokens))])
    lead_match = 1.0 if any(term in lead_window for term in query_term_set) else 0.0

    blended = (
        (semantic_score * 0.34)
        + (lexical_score * 0.23)
        + (metadata_score * 0.12)
        + (coverage * 0.17)
        + (bigram_score * 0.10)
        + (phrase_match * 0.03)
        + (lead_match * 0.01)
    )
    return {
        "score": round(min(1.0, blended), 4),
        "semantic_score": round(semantic_score, 4),
        "lexical_score": lexical_score,
        "metadata_score": metadata_score,
        "coverage": round(coverage, 4),
        "bigram_score": round(bigram_score, 4),
        "phrase_match": phrase_match,
        "lead_match": lead_match,
        "query_term_count": float(len(query_terms)),
    }


def _passes_relevance_threshold(query: str, text: str, vector_score: float, *, chunk_id: str | None = None) -> bool:
    signals = _relevance_signals(query, text, vector_score, chunk_id=chunk_id)
    query_term_count = int(signals["query_term_count"])
    score = float(signals["score"])
    if query_term_count == 0:
        return score >= 0.12

    if (
        float(signals["lexical_score"]) > 0.0
        or float(signals["metadata_score"]) > 0.0
        or signals["coverage"] > 0.0
        or signals["bigram_score"] > 0.0
        or signals["phrase_match"] > 0.0
    ):
        return score >= 0.16

    return float(signals["semantic_score"]) >= 0.86 and score >= 0.26


def _hybrid_relevance_score(query: str, text: str, vector_score: float, *, chunk_id: str | None = None) -> float:
    return float(_relevance_signals(query, text, vector_score, chunk_id=chunk_id)["score"])


def _candidate_preview(text: str) -> str:
    return text[:220] + ("..." if len(text) > 220 else "")


def _lexical_candidate_rows(
    query: str,
    rows: Sequence[Dict[str, Any]],
    *,
    source_scope: set[str],
    top_k: int,
) -> List[Dict[str, Any]]:
    query_terms = _query_terms(query)
    if not query_terms:
        return []

    lexical_candidates: List[Dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()
    for row in rows:
        if source_scope and str(row.get("source_file") or "") not in source_scope:
            continue

        chunk_id = str(row.get("chunk_id") or "")
        if not chunk_id or chunk_id in seen_chunk_ids:
            continue

        text = str(row.get("text") or "")
        raw_score = _raw_bm25_score(query_terms, text, chunk_id=chunk_id)
        if raw_score <= 0.0:
            continue

        seen_chunk_ids.add(chunk_id)
        lexical_candidates.append(
            {
                "chunk_id": chunk_id,
                "raw_lexical_score": raw_score,
                "source_file": row.get("source_file"),
                "page_number": row.get("page_number"),
                "chunk_index": row.get("chunk_index", 0),
                "text": text,
            }
        )

    lexical_candidates.sort(key=lambda row: float(row["raw_lexical_score"]), reverse=True)
    return lexical_candidates[:top_k]


def _candidate_diversity_adjustment(candidate: Dict[str, Any], selected: Sequence[Dict[str, Any]]) -> float:
    if len(selected) < 2:
        return 0.0

    candidate_tokens = set(_query_terms(str(candidate.get("text", "")))) or set(
        _tokenize_query_text(str(candidate.get("text", "")))[:80]
    )
    novelty_bonus = 0.0
    if candidate_tokens:
        max_overlap = 0.0
        for row in selected:
            selected_tokens = set(_query_terms(str(row.get("text", "")))) or set(
                _tokenize_query_text(str(row.get("text", "")))[:80]
            )
            if not selected_tokens:
                continue
            overlap = len(candidate_tokens & selected_tokens) / max(1, len(candidate_tokens | selected_tokens))
            max_overlap = max(max_overlap, overlap)
        novelty_bonus = max(0.0, 1.0 - max_overlap) * 0.05

    adjacency_penalty = 0.0
    for row in selected:
        same_source = str(row.get("source_file") or "") == str(candidate.get("source_file") or "")
        same_page = row.get("page_number") == candidate.get("page_number")
        chunk_gap = abs(int(row.get("chunk_index", 0)) - int(candidate.get("chunk_index", 0)))
        if same_source and same_page and chunk_gap <= 1:
            adjacency_penalty = max(adjacency_penalty, 0.04)
        elif same_source:
            adjacency_penalty = max(adjacency_penalty, 0.01)
    return round(novelty_bonus - adjacency_penalty, 4)


def _select_diverse_results(candidates: Sequence[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    pool = [dict(candidate) for candidate in candidates]
    selected: List[Dict[str, Any]] = []
    while pool and len(selected) < top_k:
        best_index = 0
        best_value = float("-inf")
        for index, candidate in enumerate(pool):
            value = float(candidate.get("score", 0.0)) + _candidate_diversity_adjustment(candidate, selected)
            if value > best_value:
                best_value = value
                best_index = index
        selected.append(pool.pop(best_index))
    return selected


def _rerank_candidates(query: str, candidates: Sequence[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    if reranker_service.mode != "cross-encoder" or len(candidates) < 2:
        return [dict(candidate) for candidate in candidates]

    rerank_limit = min(len(candidates), max(top_k * 6, 18))
    reranked_head = reranker_service.rerank(query, candidates[:rerank_limit])
    reranked_by_id = {str(candidate.get("chunk_id")): candidate for candidate in reranked_head}

    blended: List[Dict[str, Any]] = []
    for candidate in candidates:
        row = dict(candidate)
        reranked = reranked_by_id.get(str(candidate.get("chunk_id")))
        reranker_score = float(reranked.get("reranker_score", 0.0)) if reranked else 0.0
        if reranked is not None:
            row["reranker_score"] = reranker_score
            row["score"] = round(min(1.0, (float(candidate.get("score", 0.0)) * 0.58) + (reranker_score * 0.42)), 4)
        blended.append(row)

    blended.sort(
        key=lambda row: (
            float(row.get("score", 0.0)),
            float(row.get("reranker_score", 0.0)),
            float(row.get("vector_score", 0.0)),
        ),
        reverse=True,
    )
    return blended


def _expanded_chunk_text(hit: Dict[str, Any], *, max_neighbors: int = 1, max_chars: int = 1600) -> str:
    chunk_id = str(hit.get("chunk_id") or "")
    sequence_key = _source_sequence_key(hit)
    sequence = chunk_sequences.get(sequence_key)
    center_position = chunk_sequence_positions.get(chunk_id)
    if not sequence or center_position is None:
        return str(hit.get("text", ""))

    chosen_positions = {center_position}
    total_chars = len(str(sequence[center_position].get("text", "")))
    for offset in range(1, max_neighbors + 1):
        for next_position in (center_position - offset, center_position + offset):
            if not (0 <= next_position < len(sequence)):
                continue
            candidate = sequence[next_position]
            candidate_text = str(candidate.get("text", "")).strip()
            if not candidate_text:
                continue
            if total_chars + len(candidate_text) > max_chars:
                continue
            chosen_positions.add(next_position)
            total_chars += len(candidate_text)

    parts: List[str] = []
    seen_parts: set[str] = set()
    for position in sorted(chosen_positions):
        chunk_text_value = str(sequence[position].get("text", "")).strip()
        if not chunk_text_value or chunk_text_value in seen_parts:
            continue
        seen_parts.add(chunk_text_value)
        parts.append(chunk_text_value)
    return "\n".join(parts) if parts else str(hit.get("text", ""))


def _expand_answer_hits(hits: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    expanded: List[Dict[str, Any]] = []
    for hit in hits:
        row = dict(hit)
        row["text"] = _expanded_chunk_text(row)
        row["preview"] = _candidate_preview(str(row["text"]))
        expanded.append(row)
    return expanded


def _rrf_bonus(*ranks: int | None, k: int = 60) -> float:
    total = 0.0
    for rank in ranks:
        if rank is None or rank < 1:
            continue
        total += 1.0 / (k + rank)
    return round(total, 6)


def _answer_context_limit(top_k: int) -> int:
    return max(4, min(8, top_k + 2))


def _search_internal(query: str, top_k: int, source_files: Sequence[str] | None = None) -> List[Dict[str, Any]]:
    with index_lock:
        current_chunks = chunks_store
        current_chunk_by_id = chunk_by_id
        current_index_map = index_map
        current_vector_index = vector_index

    if not current_chunks:
        return []

    source_scope = set(_normalized_source_scope(source_files))
    q_vec = embedding_service.embed_query(query)
    max_candidates = max(len(current_chunks), getattr(current_vector_index, "size", len(current_chunks)))
    candidate_k = max_candidates if source_scope else min(max_candidates, max(12, top_k * 5))
    hits = current_vector_index.search(q_vec, candidate_k)

    merged_candidates: Dict[str, Dict[str, Any]] = {}
    for semantic_rank, (row_id, score) in enumerate(hits, start=1):
        chunk_id = current_index_map.get(str(row_id))
        if not chunk_id:
            if 0 <= row_id < len(current_chunks):
                chunk = current_chunks[row_id]
            else:
                continue
        else:
            chunk = current_chunk_by_id.get(chunk_id)
            if chunk is None:
                continue

        if source_scope and str(chunk.get("source_file") or "") not in source_scope:
            continue

        resolved_chunk_id = str(chunk.get("chunk_id") or chunk_id or f"row_{row_id}")
        text = str(chunk.get("text", ""))
        if not _passes_relevance_threshold(query, text, float(score), chunk_id=resolved_chunk_id):
            continue
        merged_candidates[resolved_chunk_id] = {
            "chunk_id": resolved_chunk_id,
            "score": _hybrid_relevance_score(query, text, float(score), chunk_id=resolved_chunk_id),
            "vector_score": round(float(score), 4),
            "preview": _candidate_preview(text),
            "source_file": chunk.get("source_file"),
            "page_number": chunk.get("page_number"),
            "chunk_index": chunk.get("chunk_index", 0),
            "section_path": chunk.get("section_path", []),
            "block_kind": chunk.get("block_kind", ""),
            "text": text,
            "semantic_rank": semantic_rank,
        }

    lexical_limit = max(top_k * 6, 18)
    for lexical_rank, lexical_row in enumerate(
        _lexical_candidate_rows(query, current_chunks, source_scope=source_scope, top_k=lexical_limit),
        start=1,
    ):
        resolved_chunk_id = str(lexical_row["chunk_id"])
        text = str(lexical_row["text"])
        vector_score = float(merged_candidates.get(resolved_chunk_id, {}).get("vector_score", 0.0))
        if not _passes_relevance_threshold(query, text, vector_score, chunk_id=resolved_chunk_id):
            continue

        score = _hybrid_relevance_score(query, text, vector_score, chunk_id=resolved_chunk_id)
        existing = merged_candidates.get(resolved_chunk_id)
        if existing is None or score > float(existing.get("score", 0.0)):
            merged_candidates[resolved_chunk_id] = {
                "chunk_id": resolved_chunk_id,
                "score": score,
                "vector_score": round(vector_score, 4),
                "preview": _candidate_preview(text),
                "source_file": lexical_row.get("source_file"),
                "page_number": lexical_row.get("page_number"),
                "chunk_index": lexical_row.get("chunk_index", 0),
                "section_path": current_chunk_by_id.get(resolved_chunk_id, {}).get("section_path", []),
                "block_kind": current_chunk_by_id.get(resolved_chunk_id, {}).get("block_kind", ""),
                "text": text,
                "semantic_rank": existing.get("semantic_rank") if existing else None,
                "lexical_rank": lexical_rank,
            }
        elif existing is not None:
            existing["lexical_rank"] = lexical_rank

    for candidate in merged_candidates.values():
        fusion_bonus = _rrf_bonus(candidate.get("semantic_rank"), candidate.get("lexical_rank"))
        candidate["score"] = round(min(1.0, float(candidate["score"]) + (fusion_bonus * 2.5)), 4)

    candidates = sorted(
        merged_candidates.values(),
        key=lambda row: (float(row["score"]), float(row.get("vector_score", 0.0))),
        reverse=True,
    )
    candidates = _rerank_candidates(query, candidates, top_k)
    return _select_diverse_results(candidates, top_k)


def _search_for_answer(question: str, top_k: int, source_files: Sequence[str] | None = None) -> List[Dict[str, Any]]:
    variants = _retrieval_queries(question)
    if not variants:
        return []

    per_query_limit = max(top_k, min(12, top_k + 4))
    merged: Dict[str, Dict[str, Any]] = {}
    variant_hits: Dict[str, int] = {}

    for variant in variants:
        results = _search_internal(variant, per_query_limit, source_files=source_files)
        for row in results:
            chunk_id = str(row["chunk_id"])
            refreshed = dict(row)
            refreshed["score"] = _hybrid_relevance_score(
                question,
                str(row.get("text", "")),
                float(row.get("vector_score", row["score"])),
                chunk_id=chunk_id,
            )
            existing = merged.get(chunk_id)
            if existing is None or float(refreshed["score"]) > float(existing["score"]):
                merged[chunk_id] = refreshed
            variant_hits[chunk_id] = variant_hits.get(chunk_id, 0) + 1

    ranked = sorted(
        merged.values(),
        key=lambda row: (
            float(row["score"]) + max(0, variant_hits.get(str(row["chunk_id"]), 1) - 1) * 0.05,
            float(row.get("vector_score", row["score"])),
        ),
        reverse=True,
    )
    return _select_diverse_results(ranked, top_k)


@app.post("/search")
def search(payload: SearchRequest) -> Dict[str, Any]:
    ensure_unlocked()
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    append_query_log("search", query)
    results = _search_for_answer(question=query, top_k=payload.top_k, source_files=payload.source_files)
    return {
        "results": [
            {
                "chunk_id": r["chunk_id"],
                "score": r["score"],
                "preview": r["preview"],
                "text": r["text"],
                "source_file": r["source_file"],
                "page_number": r["page_number"],
                "chunk_index": r["chunk_index"],
                "section_path": r.get("section_path", []),
                "block_kind": r.get("block_kind", ""),
            }
            for r in results
        ]
    }


@app.post("/ask")
def ask(payload: AskRequest) -> Dict[str, Any]:
    ensure_unlocked()
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    answer_mode = _normalize_answer_mode(payload.mode)
    source_scope = _normalized_source_scope(payload.source_files)
    with index_lock:
        conversation = _find_conversation(payload.session_id) if payload.session_id else None
        if payload.session_id and conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        history = list(conversation.get("messages") or []) if conversation else []

    retrieval_question = _conversation_followup_query(question, history)
    append_query_log("ask", retrieval_question)
    hits = _search_for_answer(retrieval_question, _answer_context_limit(payload.top_k), source_files=source_scope)
    answer_hits = _expand_answer_hits(hits[: _answer_context_limit(payload.top_k)])
    assessment = _assess_evidence(retrieval_question, answer_hits, source_scope)
    sources = [
        {
            "citation": f"S{index}",
            "chunk_id": r["chunk_id"],
            "score": r["score"],
            "retrieval_score": r.get("vector_score", r["score"]),
            "text": r["text"],
            "source_file": r["source_file"],
            "page_number": r["page_number"],
            "section_path": r.get("section_path", []),
            "block_kind": r.get("block_kind", ""),
        }
        for index, r in enumerate(answer_hits, start=1)
    ]
    if payload.trust_mode and assessment["evidence_status"] == "insufficient":
        answer = _insufficient_evidence_answer(question, sources, assessment)
    elif payload.trust_mode and assessment["evidence_status"] == "limited" and answer_mode in {"answer", "study_guide"}:
        answer = extractive_answer(question=question, sources=sources, answer_mode=answer_mode)
    else:
        answer = rag_engine.generate_answer(question=question, sources=sources, answer_mode=answer_mode)
    response = {
        "answer": answer,
        "sources": sources,
        "confidence": assessment["confidence"],
        "confidence_label": assessment["confidence_label"],
        "evidence_status": assessment["evidence_status"],
        "follow_up_question": assessment["follow_up_question"],
        "used_scope": source_scope,
        "answer_mode": answer_mode,
        "trust_mode": payload.trust_mode,
    }
    if conversation is not None:
        with index_lock:
            stored = _find_conversation(str(conversation.get("session_id")))
            if stored is not None:
                stored["messages"].append(_serialize_conversation_message(role="user", text=question))
                stored["messages"].append(
                    _serialize_conversation_message(
                        role="assistant",
                        text=answer,
                        answer_mode=answer_mode,
                        sources=sources,
                        confidence=float(assessment["confidence"]),
                        confidence_label=str(assessment["confidence_label"]),
                        evidence_status=str(assessment["evidence_status"]),
                        follow_up_question=str(assessment["follow_up_question"]),
                        used_scope=source_scope,
                        trust_mode=payload.trust_mode,
                    )
                )
                if str(stored.get("title") or "New chat") == "New chat":
                    stored["title"] = _conversation_title(question)
                stored["updated_at"] = utc_now_iso()
                _save_conversations()
        response["session_id"] = str(conversation.get("session_id"))
    return response


@app.get("/graph")
def graph() -> Dict[str, Any]:
    ensure_unlocked()
    with index_lock:
        return graph_cache
