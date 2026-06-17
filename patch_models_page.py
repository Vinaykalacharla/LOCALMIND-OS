import sys

path = "frontend/src/app/models/page.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add rebuildKnowledgeBase import
if "rebuildKnowledgeBase" not in content:
    content = content.replace("reindexKnowledgeBase,", "rebuildKnowledgeBase,\n  reindexKnowledgeBase,")

# 2. Add onRebuild function
if "async function onRebuild" not in content:
    onRebuild = """
  async function onRebuild() {
    if (jobId && jobStatus?.state === "processing") return;
    if (!confirm("This will clear the current index and re-ingest all files from the uploads folder. Continue?")) return;
    setJobStatus(initialJobStatus);
    try {
      const response = await rebuildKnowledgeBase();
      setJobId(response.job_id);
      pushToast("info", "Full rebuild started");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to start rebuild";
      pushToast("error", message);
    }
  }
"""
    content = content.replace("async function onReindex() {", onRebuild + "\n  async function onReindex() {")

# 3. Add Rebuild Button
if "Full rebuild" not in content:
    rebuild_button = """
              <button onClick={onRebuild} disabled={jobStatus?.state === "processing"} className="btn-secondary text-red-400 border-red-500/30 hover:bg-red-500/10 disabled:opacity-60">
                Full rebuild (Wipe & Ingest)
              </button>
"""
    content = content.replace("Open evaluation\n              </Link>", "Open evaluation\n              </Link>\n" + rebuild_button)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched models page successfully")
