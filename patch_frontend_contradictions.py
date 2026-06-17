import sys

# 1. Patch api.ts
path1 = "frontend/src/lib/api.ts"
with open(path1, "r", encoding="utf-8") as f:
    content1 = f.read()

new_api = """
export interface ContradictionResponse {
  has_contradiction: boolean;
  analysis: string;
  scanned_chunks: number;
}

export async function detectContradictions(sourceFiles: string[]): Promise<ContradictionResponse> {
  return req<ContradictionResponse>("/detect_contradictions", {
    method: "POST",
    body: JSON.stringify({ source_files: sourceFiles })
  });
}
"""

if "detectContradictions" not in content1:
    content1 = content1.replace("export async function rebuildKnowledgeBase(): Promise<IngestResponse> {", new_api + "\nexport async function rebuildKnowledgeBase(): Promise<IngestResponse> {")

with open(path1, "w", encoding="utf-8") as f:
    f.write(content1)

# 2. Patch collections page
path2 = "frontend/src/app/collections/page.tsx"
with open(path2, "r", encoding="utf-8") as f:
    content2 = f.read()

# Add detectContradictions to imports
if "detectContradictions" not in content2:
    content2 = content2.replace("getCollections, createCollection, deleteCollection } from \"@/lib/api\";", "getCollections, createCollection, deleteCollection, detectContradictions } from \"@/lib/api\";")

# Add state
if "const [analyzingId" not in content2:
    content2 = content2.replace("const [newWorkspaceName, setNewWorkspaceName] = useState(\"\");", "const [newWorkspaceName, setNewWorkspaceName] = useState(\"\");\n  const [analyzingId, setAnalyzingId] = useState<string | null>(null);\n  const [analysisResult, setAnalysisResult] = useState<Record<string, string>>({});")

# Add handleAnalyze function
handle_analyze = """
  async function handleAnalyze(c: Collection) {
    if (c.files.length === 0) {
      pushToast("error", "Add some files to this workspace first");
      return;
    }
    setAnalyzingId(c.id);
    try {
      const res = await detectContradictions(c.files);
      setAnalysisResult(prev => ({ ...prev, [c.id]: res.analysis }));
      if (res.has_contradiction) {
        pushToast("info", "Contradictions detected!");
      } else {
        pushToast("success", "No contradictions found");
      }
    } catch (error) {
      pushToast("error", "Analysis failed");
    } finally {
      setAnalyzingId(null);
    }
  }
"""

if "async function handleAnalyze" not in content2:
    content2 = content2.replace("async function handleDelete", handle_analyze + "\n  async function handleDelete")

# Add Analyze button and display results
button_and_result = """                  <div className="flex gap-3">
                    <button onClick={() => handleAnalyze(c)} disabled={analyzingId === c.id} className="btn-secondary text-xs disabled:opacity-60">
                      {analyzingId === c.id ? "Analyzing..." : "Analyze Contradictions"}
                    </button>
                    <button onClick={() => handleDelete(c.id)} className="btn-secondary text-xs border-red-500/20 text-red-400 hover:bg-red-500/10">Delete</button>
                  </div>
                </div>
                {analysisResult[c.id] && (
                  <div className="p-4 mt-2 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sm text-sky-100 whitespace-pre-wrap">
                    <div className="font-semibold mb-2 text-sky-300">Contradiction Analysis:</div>
                    {analysisResult[c.id]}
                  </div>
                )}
"""

if "Analyze Contradictions" not in content2:
    content2 = content2.replace("""                  <div className="flex gap-3">
                    <button onClick={() => handleDelete(c.id)} className="btn-secondary text-xs border-red-500/20 text-red-400 hover:bg-red-500/10">Delete</button>
                  </div>
                </div>""", button_and_result)

with open(path2, "w", encoding="utf-8") as f:
    f.write(content2)

print("Patched frontend for contradictions successfully")
