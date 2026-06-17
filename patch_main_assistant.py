import sys

path = "backend/main.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

import_stmt = "from services.assistant import assistant_service\n"
if "from services.assistant import assistant_service" not in content:
    content = content.replace("from services.versioning import VersioningService", import_stmt + "from services.versioning import VersioningService")

startup_hook = """    # Start Assistant Thread
    assistant_service.start()
"""
if "assistant_service.start()" not in content:
    content = content.replace("def startup_load() -> None:", "def startup_load() -> None:\n" + startup_hook)

endpoints = """
@app.post("/assistant/toggle")
def toggle_assistant(payload: Dict[str, Any]) -> Dict[str, Any]:
    ensure_unlocked()
    enabled = bool(payload.get("enabled", False))
    assistant_service.toggle(enabled)
    return {"ok": True, "enabled": enabled}

@app.get("/assistant/status")
def assistant_status() -> Dict[str, Any]:
    ensure_unlocked()
    return {"enabled": getattr(assistant_service, "enabled", False)}
"""
if "@app.post(\"/assistant/toggle\")" not in content:
    content = content.replace("@app.get(\"/models\")", endpoints + "\n@app.get(\"/models\")")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched main.py for assistant successfully")
