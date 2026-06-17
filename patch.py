import sys

path = "backend/main.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add COLLECTIONS_FILE
if "COLLECTIONS_FILE =" not in content:
    content = content.replace(
        "CONVERSATIONS_FILE = DATA_DIR / \"conversations.json\"",
        "CONVERSATIONS_FILE = DATA_DIR / \"conversations.json\"\nCOLLECTIONS_FILE = DATA_DIR / \"collections.json\""
    )

# 2. Add collections_store
if "collections_store: List" not in content:
    content = content.replace(
        "conversations_store: List[Dict[str, Any]] = []",
        "conversations_store: List[Dict[str, Any]] = []\ncollections_store: List[Dict[str, Any]] = []"
    )

# 3. Add to reset_runtime_state
if "collections_store" not in content.split("def reset_runtime_state")[1].split("def ")[0]:
    content = content.replace(
        "global chunks_store, chunk_by_id, index_map, meta, graph_cache, vector_index, retrieval_stats, chunk_sequences, chunk_sequence_positions, conversations_store, study_store",
        "global chunks_store, chunk_by_id, index_map, meta, graph_cache, vector_index, retrieval_stats, chunk_sequences, chunk_sequence_positions, conversations_store, study_store, collections_store"
    )
    content = content.replace(
        "conversations_store = []",
        "conversations_store = []\n    collections_store = []"
    )

# 4. Add _load_collections and _save_collections
if "def _load_collections" not in content:
    functions = """
def _load_collections() -> List[Dict[str, Any]]:
    raw = _load_json_artifact(COLLECTIONS_FILE, [])
    return raw if isinstance(raw, list) else []

def _save_collections() -> None:
    payload = json.dumps(collections_store, indent=2, ensure_ascii=True).encode("utf-8")
    staged = _stage_bytes_file(COLLECTIONS_FILE, payload, encrypt=security_manager.configured)
    try:
        import os
        os.replace(staged, COLLECTIONS_FILE)
    finally:
        if staged.exists():
            staged.unlink(missing_ok=True)
"""
    content = content.replace("def _load_conversations()", functions + "\ndef _load_conversations()")

# 5. Add to load_persisted_state
if "collections_store = _load_collections()" not in content:
    content = content.replace(
        "conversations_store = _load_conversations()",
        "conversations_store = _load_conversations()\n    global collections_store\n    collections_store = _load_collections()"
    )

# 6. Add API endpoints
if "@app.get(\"/collections\")" not in content:
    api_endpoints = """
@app.get("/collections")
def list_collections() -> Dict[str, Any]:
    ensure_unlocked()
    with index_lock:
        return {"collections": collections_store}

@app.post("/collections")
def create_collection(payload: Dict[str, Any]) -> Dict[str, Any]:
    ensure_unlocked()
    collection = {
        "id": uuid.uuid4().hex,
        "name": payload.get("name", "New Workspace"),
        "files": payload.get("files", []),
        "created_at": utc_now_iso(),
    }
    with index_lock:
        collections_store.append(collection)
        _save_collections()
        return collection

@app.delete("/collections/{collection_id}")
def delete_collection(collection_id: str) -> Dict[str, bool]:
    ensure_unlocked()
    with index_lock:
        global collections_store
        collections_store = [c for c in collections_store if c.get("id") != collection_id]
        _save_collections()
    return {"ok": True}

@app.post("/rebuild_index")
def rebuild_index(background_tasks: BackgroundTasks = None) -> Dict[str, str]:
    ensure_unlocked()
    with index_lock:
        # clear FAISS and chunks to trigger full ingestion of existing uploads
        global chunks_store, chunk_by_id, index_map, meta, graph_cache, vector_index, retrieval_stats
        chunks_store = []
        chunk_by_id = {}
        index_map = {}
        meta = {}
        graph_cache = {"nodes": [], "edges": []}
        retrieval_stats = _empty_retrieval_stats()
        vector_index = VectorIndex()
        # write the empty state
        commit_prepared_state(PreparedIndexState([], {}, {}, {}, {"nodes": [], "edges": []}, vector_index, None))
        
    job_id = create_job()
    uploads = [p for p in UPLOADS_DIR.rglob("*") if p.is_file()]
    if background_tasks is None:
        process_ingestion(job_id, uploads)
    else:
        background_tasks.add_task(process_ingestion, job_id, uploads)
    return {"job_id": job_id}
"""
    content = content.replace("@app.post(\"/reindex\")", api_endpoints + "\n@app.post(\"/reindex\")")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched main.py successfully")
