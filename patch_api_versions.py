import sys

path = "frontend/src/lib/api.ts"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

new_api = """
export interface FileVersion {
  version_id: string;
  timestamp: number;
}

export async function getFileVersions(sourceFile: string): Promise<{ versions: FileVersion[] }> {
  return req<{ versions: FileVersion[] }>(`/versions?source_file=${encodeURIComponent(sourceFile)}`);
}

export async function getFileDiff(sourceFile: string, v1: string, v2: string): Promise<{ diff: string }> {
  return req<{ diff: string }>(`/diff?source_file=${encodeURIComponent(sourceFile)}&v1=${encodeURIComponent(v1)}&v2=${encodeURIComponent(v2)}`);
}
"""

if "getFileVersions" not in content:
    content = content.replace("export async function rebuildKnowledgeBase(): Promise<IngestResponse> {", new_api + "\nexport async function rebuildKnowledgeBase(): Promise<IngestResponse> {")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched api.ts successfully")
