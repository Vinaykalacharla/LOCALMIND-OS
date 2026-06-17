import sys

path = "backend/main.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Imports and config
import_stmt = "from services.versioning import VersioningService\n"
if import_stmt not in content:
    content = content.replace("from services.rag import RAGEngine", import_stmt + "from services.rag import RAGEngine")

if "VERSIONS_DIR = DATA_DIR / \"versions\"" not in content:
    content = content.replace("UPLOADS_DIR = DATA_DIR / \"uploads\"", "UPLOADS_DIR = DATA_DIR / \"uploads\"\nVERSIONS_DIR = DATA_DIR / \"versions\"")

if "versioning_service = VersioningService(VERSIONS_DIR)" not in content:
    content = content.replace("rag_engine = RAGEngine(MODELS_DIR, preferred_local_model=\"extractive-fallback\")", "rag_engine = RAGEngine(MODELS_DIR, preferred_local_model=\"extractive-fallback\")\nversioning_service = VersioningService(VERSIONS_DIR)")

# 2. Hook into process_ingestion
extraction_hook = """        if not docs:
            update_job(job_id, state="error", step="extracting", progress=100, message="No readable text found")
            return

        for doc in docs:
            try:
                versioning_service.save_version(doc.source_file, doc.text)
            except Exception as e:
                print(f"Failed to save version for {doc.source_file}: {e}")
"""
if "versioning_service.save_version(doc.source_file, doc.text)" not in content:
    content = content.replace("""        if not docs:
            update_job(job_id, state="error", step="extracting", progress=100, message="No readable text found")
            return""", extraction_hook)

# 3. Endpoints
endpoints = """
@app.get("/versions")
def get_file_versions(source_file: str) -> Dict[str, Any]:
    ensure_unlocked()
    versions = versioning_service.get_versions(source_file)
    return {"versions": versions}

@app.get("/diff")
def get_file_diff(source_file: str, v1: str, v2: str) -> Dict[str, str]:
    ensure_unlocked()
    diff_text = versioning_service.get_diff(source_file, v1, v2)
    return {"diff": diff_text}
"""
if "@app.get(\"/versions\")" not in content:
    content = content.replace("@app.get(\"/evaluate\")", endpoints + "\n@app.get(\"/evaluate\")")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched main.py for versioning successfully")
