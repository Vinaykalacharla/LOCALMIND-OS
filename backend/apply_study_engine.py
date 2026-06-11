import os

MAIN_FILE = r"d:\OneDrive\Desktop\LOCALMIND OS\backend\main.py"

with open(MAIN_FILE, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add STUDY_FILE
if "STUDY_FILE = DATA_DIR / \"study.json\"" not in content:
    content = content.replace(
        "CONVERSATIONS_FILE = DATA_DIR / \"conversations.json\"",
        "CONVERSATIONS_FILE = DATA_DIR / \"conversations.json\"\nSTUDY_FILE = DATA_DIR / \"study.json\""
    )

# 2. Add Models
if "class ReviewOutcomeRequest(BaseModel):" not in content:
    models = """class ModelSettingsRequest(BaseModel):
    llm: Optional[str] = None
    embedding: Optional[str] = None
    reranker: Optional[str] = None

class ReviewOutcomeRequest(BaseModel):
    chunk_id: str
    quality: int = Field(ge=0, le=5)

class ExamGenerateRequest(BaseModel):
    topic: str
    num_questions: int = Field(default=5, ge=1, le=20)

class ExamSubmitRequest(BaseModel):
    exam_id: str
    answers: Dict[str, str]"""
    content = content.replace(
        "class ModelSettingsRequest(BaseModel):\n    llm: Optional[str] = None\n    embedding: Optional[str] = None\n    reranker: Optional[str] = None",
        models
    )

# 3. Add study_store globals
if "study_store: Dict[str, Any]" not in content:
    content = content.replace(
        "conversations_store: List[Dict[str, Any]] = []",
        "conversations_store: List[Dict[str, Any]] = []\nstudy_store: Dict[str, Any] = {\"reviews\": {}, \"exams\": []}"
    )

# 4. reset_runtime_state
if "study_store = {\"reviews\": {}, \"exams\": []}" not in content:
    content = content.replace(
        "global chunks_store, chunk_by_id, index_map, meta, graph_cache, vector_index, retrieval_stats, chunk_sequences, chunk_sequence_positions, conversations_store",
        "global chunks_store, chunk_by_id, index_map, meta, graph_cache, vector_index, retrieval_stats, chunk_sequences, chunk_sequence_positions, conversations_store, study_store\n    study_store = {\"reviews\": {}, \"exams\": []}"
    )

# 5. _load_study_data / _save_study_data
if "_load_study_data" not in content:
    funcs = """def _save_conversations() -> None:
    payload = json.dumps(conversations_store, indent=2, ensure_ascii=True).encode("utf-8")
    staged = _stage_bytes_file(CONVERSATIONS_FILE, payload, encrypt=security_manager.configured)
    try:
        os.replace(staged, CONVERSATIONS_FILE)
    finally:
        if staged.exists():
            staged.unlink(missing_ok=True)

def _load_study_data() -> None:
    global study_store
    raw = _load_json_artifact(STUDY_FILE, {"reviews": {}, "exams": []})
    if isinstance(raw, dict):
        study_store["reviews"] = raw.get("reviews", {})
        study_store["exams"] = raw.get("exams", [])

def _save_study_data() -> None:
    payload = json.dumps(study_store, indent=2, ensure_ascii=True).encode("utf-8")
    staged = _stage_bytes_file(STUDY_FILE, payload, encrypt=security_manager.configured)
    try:
        os.replace(staged, STUDY_FILE)
    finally:
        if staged.exists():
            staged.unlink(missing_ok=True)"""
    
    content = content.replace(
        """def _save_conversations() -> None:
    payload = json.dumps(conversations_store, indent=2, ensure_ascii=True).encode("utf-8")
    staged = _stage_bytes_file(CONVERSATIONS_FILE, payload, encrypt=security_manager.configured)
    try:
        os.replace(staged, CONVERSATIONS_FILE)
    finally:
        if staged.exists():
            staged.unlink(missing_ok=True)""",
        funcs
    )

# 6. Call _load_study_data in load_persisted_state
if "_load_study_data()" not in content:
    content = content.replace(
        "conversations_store = _load_conversations()",
        "conversations_store = _load_conversations()\n    _load_study_data()"
    )

# 7. Endpoints
ENDPOINTS = """

@app.get("/study/reviews")
def get_due_reviews() -> Dict[str, Any]:
    ensure_unlocked()
    with index_lock:
        now = datetime.now(timezone.utc).timestamp()
        due_chunks = []
        # Find chunks that are due
        for chunk in chunks_store:
            chunk_id = chunk.get("chunk_id")
            if not chunk_id: continue
            review_data = study_store["reviews"].get(chunk_id, {})
            next_review = review_data.get("next_review", 0)
            if next_review <= now:
                due_chunks.append({
                    "chunk_id": chunk_id,
                    "text": chunk.get("text", ""),
                    "source_file": chunk.get("source_file", ""),
                    "page_number": chunk.get("page_number", ""),
                    "easiness": review_data.get("easiness", 2.5),
                    "repetitions": review_data.get("repetitions", 0),
                    "interval": review_data.get("interval", 0)
                })
                if len(due_chunks) >= 20:
                    break
        return {"due_reviews": due_chunks}

@app.post("/study/review")
def submit_review(req: ReviewOutcomeRequest) -> Dict[str, Any]:
    ensure_unlocked()
    with index_lock:
        chunk_id = req.chunk_id
        q = req.quality
        
        review_data = study_store["reviews"].get(chunk_id, {
            "easiness": 2.5,
            "repetitions": 0,
            "interval": 0,
            "next_review": 0
        })
        
        if q >= 3:
            if review_data["repetitions"] == 0:
                interval = 1
            elif review_data["repetitions"] == 1:
                interval = 6
            else:
                interval = round(review_data["interval"] * review_data["easiness"])
            repetitions = review_data["repetitions"] + 1
        else:
            repetitions = 0
            interval = 1
            
        easiness = review_data["easiness"] + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        easiness = max(1.3, easiness)
        
        now = datetime.now(timezone.utc).timestamp()
        next_review = now + (interval * 86400)
        
        study_store["reviews"][chunk_id] = {
            "easiness": easiness,
            "repetitions": repetitions,
            "interval": interval,
            "next_review": next_review
        }
        _save_study_data()
        return {"status": "ok", "next_review": next_review}

@app.post("/study/exams/generate")
def generate_exam(req: ExamGenerateRequest) -> Dict[str, Any]:
    ensure_unlocked()
    search_query = req.topic
    with index_lock:
        res = vector_index.search(embedding_service.embed_query(search_query), top_k=10)
        context_texts = []
        for doc_idx in res.indices:
            chunk_id = index_map.get(str(doc_idx))
            if chunk_id and chunk_id in chunk_by_id:
                context_texts.append(chunk_by_id[chunk_id]["text"])
        
    if not context_texts:
        raise HTTPException(status_code=400, detail="No relevant context found for this topic.")
        
    # Generate mock questions based on the retrieved text since LLM JSON generation can be flaky
    # We will build a simple robust generator
    questions = []
    for i, text in enumerate(context_texts[:req.num_questions]):
        words = text.split()
        if len(words) < 5:
            continue
        # simple mock question
        topic_snippet = " ".join(words[:10])
        questions.append({
            "question": f"According to the text regarding '{topic_snippet}...', what is the key takeaway?",
            "options": [
                "It describes " + " ".join(words[10:15]),
                "It is completely unrelated",
                "None of the above",
                "All of the above"
            ],
            "correct_answer": "It describes " + " ".join(words[10:15]),
            "explanation": "Based directly on the source document."
        })
        
    exam_id = uuid.uuid4().hex[:10]
    exam_data = {
        "id": exam_id,
        "topic": req.topic,
        "created_at": utc_now_iso(),
        "questions": questions,
        "score": None,
        "completed_at": None
    }
    with index_lock:
        study_store["exams"].append(exam_data)
        _save_study_data()
        
    return exam_data

@app.get("/study/exams")
def get_exams() -> Dict[str, Any]:
    ensure_unlocked()
    with index_lock:
        return {"exams": study_store["exams"]}

@app.post("/study/exams/submit")
def submit_exam(req: ExamSubmitRequest) -> Dict[str, Any]:
    ensure_unlocked()
    with index_lock:
        for exam in study_store["exams"]:
            if exam["id"] == req.exam_id:
                correct = 0
                for q in exam["questions"]:
                    ans = req.answers.get(q["question"])
                    if ans == q["correct_answer"]:
                        correct += 1
                score_pct = int((correct / max(1, len(exam["questions"]))) * 100)
                exam["score"] = f"{score_pct}%"
                exam["completed_at"] = utc_now_iso()
                _save_study_data()
                return exam
        raise HTTPException(status_code=404, detail="Exam not found")

"""

if "@app.get(\"/study/reviews\")" not in content:
    content = content.replace(
        "if __name__ == \"__main__\":",
        ENDPOINTS + "\nif __name__ == \"__main__\":"
    )

with open(MAIN_FILE, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated main.py")
