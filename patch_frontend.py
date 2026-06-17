import sys

path = "frontend/src/lib/api.ts"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

new_api = """
export interface Collection {
  id: string;
  name: string;
  files: string[];
  created_at: string;
}

export async function getCollections(): Promise<{ collections: Collection[] }> {
  return req<{ collections: Collection[] }>("/collections");
}

export async function createCollection(payload: { name: string; files: string[] }): Promise<Collection> {
  return req<Collection>("/collections", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function deleteCollection(id: string): Promise<{ ok: boolean }> {
  return req<{ ok: boolean }>(`/collections/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function rebuildKnowledgeBase(): Promise<IngestResponse> {
  return req<IngestResponse>("/rebuild_index", { method: "POST" });
}
"""

if "rebuildKnowledgeBase" not in content:
    content = content.replace("export async function reindexKnowledgeBase(): Promise<IngestResponse> {", new_api + "\nexport async function reindexKnowledgeBase(): Promise<IngestResponse> {")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched api.ts successfully")
