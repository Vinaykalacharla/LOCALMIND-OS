import sys

# 1. Patch api.ts
path1 = "frontend/src/lib/api.ts"
with open(path1, "r", encoding="utf-8") as f:
    content1 = f.read()

new_api = """
export async function toggleAssistant(enabled: boolean): Promise<{ ok: boolean; enabled: boolean }> {
  return req<{ ok: boolean; enabled: boolean }>('/assistant/toggle', {
    method: 'POST',
    body: JSON.stringify({ enabled })
  });
}

export async function getAssistantStatus(): Promise<{ enabled: boolean }> {
  return req<{ enabled: boolean }>('/assistant/status');
}
"""

if "toggleAssistant" not in content1:
    content1 = content1.replace("export async function rebuildKnowledgeBase(): Promise<IngestResponse> {", new_api + "\nexport async function rebuildKnowledgeBase(): Promise<IngestResponse> {")

with open(path1, "w", encoding="utf-8") as f:
    f.write(content1)

# 2. Patch models/page.tsx
path2 = "frontend/src/app/models/page.tsx"
with open(path2, "r", encoding="utf-8") as f:
    content2 = f.read()

assistant_import = "import { getModels, applyModels, validateModels, ModelManagerResponse, ModelKey, rebuildKnowledgeBase, reindexKnowledgeBase, toggleAssistant, getAssistantStatus } from \"@/lib/api\";"
if "toggleAssistant" not in content2:
    content2 = content2.replace("import { getModels, applyModels, validateModels, ModelManagerResponse, ModelKey, rebuildKnowledgeBase, reindexKnowledgeBase } from \"@/lib/api\";", assistant_import)

state_vars = """  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [assistantEnabled, setAssistantEnabled] = useState(false);"""
if "assistantEnabled" not in content2:
    content2 = content2.replace("const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);", state_vars)

load_hook = """        const [response, asstStatus] = await Promise.all([getModels(), getAssistantStatus()]);
        setManager(response);
        setAssistantEnabled(asstStatus.enabled);"""
if "asstStatus" not in content2:
    content2 = content2.replace("const response = await getModels();\n        setManager(response);", load_hook)

toggle_func = """
  async function onToggleAssistant() {
    try {
      const res = await toggleAssistant(!assistantEnabled);
      setAssistantEnabled(res.enabled);
      pushToast("success", res.enabled ? "Global Voice Assistant Enabled" : "Global Voice Assistant Disabled");
    } catch (e) {
      pushToast("error", "Failed to toggle assistant");
    }
  }
"""
if "onToggleAssistant" not in content2:
    content2 = content2.replace("async function onRebuild() {", toggle_func + "\n  async function onRebuild() {")

ui_block = """
        <div className="shell-panel p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="eyebrow">LocalMind Vision</div>
              <div className="mt-2 text-2xl font-semibold text-white">Global Voice Assistant</div>
              <div className="mt-2 text-sm leading-7 text-zinc-400">
                Press <code className="text-sky-300">Ctrl+Shift+Space</code> anywhere on your computer. LocalMind will take a screenshot, analyze it using the local vision model, and speak the answer out loud.
              </div>
            </div>
            <button 
              onClick={onToggleAssistant} 
              className={`px-4 py-2 rounded-xl font-medium transition ${assistantEnabled ? 'bg-sky-500 text-white' : 'bg-white/10 text-zinc-300 hover:bg-white/20'}`}
            >
              {assistantEnabled ? "Enabled" : "Disabled"}
            </button>
          </div>
        </div>
"""
if "Global Voice Assistant" not in content2:
    content2 = content2.replace("<section className=\"grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]\">", ui_block + "\n      <section className=\"grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]\">")

with open(path2, "w", encoding="utf-8") as f:
    f.write(content2)

print("Patched frontend for assistant successfully")
