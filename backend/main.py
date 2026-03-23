from __future__ import annotations

import json
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
from services.chunking import chunk_text
from services.embeddings import EmbeddingService
from services.graph import GraphBuilder
from services.ingestion import extract_many
from services.insights import build_insights
from services.rag import RAGEngine
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


class SecurityPassphraseRequest(BaseModel):
    passphrase: str = Field(min_length=8, max_length=512)


jobs: Dict[str, Dict[str, Any]] = {}
jobs_lock = threading.Lock()
index_lock = threading.Lock()
query_log_lock = threading.Lock()

chunks_store: List[Dict[str, Any]] = []
chunk_by_id: Dict[str, Dict[str, Any]] = {}
index_map: Dict[str, str] = {}
meta: Dict[str, Any] = {}
graph_cache: Dict[str, List[Dict[str, Any]]] = {"nodes": [], "edges": []}

security_manager = SecurityManager(SECURITY_FILE)
embedding_service = EmbeddingService()
vector_index = VectorIndex()
graph_builder = GraphBuilder()
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
    global chunks_store, chunk_by_id, index_map, meta, graph_cache, vector_index
    chunks_store = []
    chunk_by_id = {}
    index_map = {}
    meta = {}
    graph_cache = {"nodes": [], "edges": []}
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
    paths = [CHUNKS_FILE, INDEX_FILE, INDEX_MAP_FILE, META_FILE, GRAPH_FILE, QUERY_LOG_FILE]
    if UPLOADS_DIR.exists():
        paths.extend(p for p in UPLOADS_DIR.rglob("*") if p.is_file())
    return paths


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


def refresh_memory_maps() -> None:
    global chunk_by_id
    chunk_by_id = {c["chunk_id"]: c for c in chunks_store if "chunk_id" in c}


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
            "embedding_model": emb_res.model_name,
            "embedding_mode": emb_res.mode,
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


def load_persisted_state() -> None:
    global chunks_store, index_map, meta, graph_cache, vector_index
    chunks_store = load_chunks()
    index_map = _load_json_artifact(INDEX_MAP_FILE, {})
    meta = _load_json_artifact(META_FILE, {})
    graph_cache = _load_json_artifact(GRAPH_FILE, {"nodes": [], "edges": []})
    vector_index = load_vector_index()
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
                pieces = chunk_text(doc.text, chunk_size=900, overlap=150)
                for idx, piece in enumerate(pieces):
                    new_chunks.append(
                        {
                            "chunk_id": f"chunk_{uuid.uuid4().hex[:12]}",
                            "text": piece,
                            "source_file": doc.source_file,
                            "source_id": getattr(doc, "source_id", None),
                            "page_number": doc.page_number,
                            "chunk_index": idx,
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
        "embedding_model": current_meta.get("embedding_model", embedding_service.model_name),
        "embedding_mode": embedding_service.mode,
        "vector_backend": current_vector_index.backend_name,
        "graph_mode": graph_builder.mode,
        "pdf_backend": detect_pdf_backend(),
        "llm_mode": rag_engine.mode,
        "feature_status": build_feature_status(
            MODELS_DIR,
            embedding_mode=embedding_service.mode,
            vector_backend=current_vector_index.backend_name,
            graph_mode=graph_builder.mode,
            llm_mode=rag_engine.mode,
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


def _hybrid_relevance_score(query: str, text: str, vector_score: float) -> float:
    semantic_score = max(0.0, min(1.0, (float(vector_score) + 1.0) / 2.0))
    query_terms = _query_terms(query)
    if not query_terms:
        return round(semantic_score, 4)

    text_tokens = _tokenize_query_text(text)
    if not text_tokens:
        return round(semantic_score, 4)

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
    phrase_bonus = 0.18 if len(query_terms) >= 2 and normalized_query in normalized_text else 0.0

    lead_window = " ".join(text_tokens[: min(28, len(text_tokens))])
    lead_bonus = 0.05 if any(term in lead_window for term in query_term_set) else 0.0

    blended = (semantic_score * 0.52) + (coverage * 0.28) + (bigram_score * 0.15) + phrase_bonus + lead_bonus
    return round(min(1.0, blended), 4)


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
    candidates: List[Dict[str, Any]] = []
    for row_id, score in hits:
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
        text = chunk.get("text", "")
        preview = text[:220] + ("..." if len(text) > 220 else "")
        candidates.append(
            {
                "chunk_id": resolved_chunk_id,
                "score": _hybrid_relevance_score(query, text, float(score)),
                "vector_score": round(float(score), 4),
                "preview": preview,
                "source_file": chunk.get("source_file"),
                "page_number": chunk.get("page_number"),
                "chunk_index": chunk.get("chunk_index", 0),
                "text": text,
            }
        )

    candidates.sort(key=lambda row: (float(row["score"]), float(row.get("vector_score", 0.0))), reverse=True)

    out: List[Dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()
    for candidate in candidates:
        chunk_id = str(candidate["chunk_id"])
        if chunk_id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(chunk_id)
        out.append(candidate)
        if len(out) >= top_k:
            break
    return out


@app.post("/search")
def search(payload: SearchRequest) -> Dict[str, Any]:
    ensure_unlocked()
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    append_query_log("search", query)
    results = _search_internal(query=query, top_k=payload.top_k, source_files=payload.source_files)
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
    append_query_log("ask", question)
    hits = _search_internal(question, _answer_context_limit(payload.top_k), source_files=source_scope)
    answer_hits = hits[: _answer_context_limit(payload.top_k)]
    assessment = _assess_evidence(question, answer_hits, source_scope)
    sources = [
        {
            "citation": f"S{index}",
            "chunk_id": r["chunk_id"],
            "score": r["score"],
            "retrieval_score": r.get("vector_score", r["score"]),
            "text": r["text"],
            "source_file": r["source_file"],
            "page_number": r["page_number"],
        }
        for index, r in enumerate(answer_hits, start=1)
    ]
    if payload.trust_mode and assessment["evidence_status"] == "insufficient":
        answer = _insufficient_evidence_answer(question, sources, assessment)
    else:
        answer = rag_engine.generate_answer(question=question, sources=sources, answer_mode=answer_mode)
    return {
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


@app.get("/graph")
def graph() -> Dict[str, Any]:
    ensure_unlocked()
    with index_lock:
        return graph_cache
