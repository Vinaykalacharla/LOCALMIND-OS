import sys

path = "backend/main.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

import_stmt = "from services.contradiction import detect_contradictions\n"

if "from services.contradiction import detect_contradictions" not in content:
    content = content.replace("from services.rag import RAGEngine", import_stmt + "from services.rag import RAGEngine")

new_endpoint = """
class ContradictionRequest(BaseModel):
    source_files: List[str] = Field(default_factory=list)

@app.post("/detect_contradictions")
def api_detect_contradictions(payload: ContradictionRequest) -> Dict[str, Any]:
    ensure_unlocked()
    with index_lock:
        if not chunks_store:
            raise HTTPException(status_code=400, detail="No indexed data available")
        
        target_chunks = chunks_store
        if payload.source_files:
            allowed = set(payload.source_files)
            target_chunks = [c for c in chunks_store if c.get("source_file") in allowed]
            
        if not target_chunks:
            raise HTTPException(status_code=400, detail="No chunks found for specified files")
            
    # We run the detection outside the lock to avoid blocking other requests during LLM generation
    return detect_contradictions(rag_engine, target_chunks)
"""

if "@app.post(\"/detect_contradictions\")" not in content:
    content = content.replace("@app.get(\"/evaluate\")", new_endpoint + "\n@app.get(\"/evaluate\")")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched main.py for contradictions successfully")
