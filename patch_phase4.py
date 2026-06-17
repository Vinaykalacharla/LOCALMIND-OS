import sys

# 1. Patch main.py
path1 = "backend/main.py"
with open(path1, "r", encoding="utf-8") as f:
    content1 = f.read()

hardware_block = """
        "hardware": system_info(),
"""
if "\"hardware\": system_info()" not in content1:
    content1 = content1.replace("\"indexed_chunks\": len(chunks_store),", "\"indexed_chunks\": len(chunks_store),\n" + hardware_block)

with open(path1, "w", encoding="utf-8") as f:
    f.write(content1)

# 2. Patch api.ts
path2 = "frontend/src/lib/api.ts"
with open(path2, "r", encoding="utf-8") as f:
    content2 = f.read()

hardware_interface = """
export interface HardwareRecommendation {
  ollama_id: string;
  label: string;
  size_gb: number;
  quality: string;
  speed: string;
  description: string;
  recommended: boolean;
}

export interface HardwareInfo {
  ram_gb: number;
  ram_detected: boolean;
  platform: string;
  tier: string;
  recommendations: HardwareRecommendation[];
}
"""
if "HardwareRecommendation" not in content2:
    content2 = content2.replace("export interface ModelManagerResponse {", hardware_interface + "\nexport interface ModelManagerResponse {")
    content2 = content2.replace("indexed_chunks: number;", "indexed_chunks: number;\n  hardware: HardwareInfo;")

with open(path2, "w", encoding="utf-8") as f:
    f.write(content2)

# 3. Patch models/page.tsx
path3 = "frontend/src/app/models/page.tsx"
with open(path3, "r", encoding="utf-8") as f:
    content3 = f.read()

hardware_ui = """
        {manager?.hardware && (
          <div className="shell-panel p-5 sm:p-6 mt-6">
            <div className="eyebrow">Hardware Analysis</div>
            <div className="mt-2 text-2xl font-semibold text-white">Detected RAM: {manager.hardware.ram_gb} GB</div>
            <div className="mt-2 text-sm leading-7 text-zinc-400">
              Based on your system resources ({manager.hardware.tier} tier), here are the best models we recommend running locally via Ollama:
            </div>
            <div className="mt-4 space-y-3">
              {manager.hardware.recommendations.map(rec => (
                <div key={rec.ollama_id} className={`p-4 rounded-xl border ${rec.recommended ? 'border-sky-500/50 bg-sky-500/10' : 'border-white/8 bg-white/[0.02]'}`}>
                  <div className="flex items-center justify-between mb-1">
                    <h4 className="font-semibold text-white">{rec.label}</h4>
                    {rec.recommended && <span className="status-pill text-sky-200">Recommended</span>}
                  </div>
                  <p className="text-sm text-zinc-300">{rec.description}</p>
                  <div className="mt-2 flex gap-3 text-xs font-medium text-zinc-500">
                    <span>Size: {rec.size_gb} GB</span>
                    <span>Quality: {rec.quality}</span>
                    <span>Speed: {rec.speed}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
"""

if "Hardware Analysis" not in content3:
    content3 = content3.replace("<div className=\"shell-panel p-5 sm:p-6\">", hardware_ui + "\n          <div className=\"shell-panel p-5 sm:p-6\">")

with open(path3, "w", encoding="utf-8") as f:
    f.write(content3)

print("Patched Phase 4 successfully")
