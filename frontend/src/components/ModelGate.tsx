"use client";

import React, { useEffect, useState } from "react";
import { getModelManager, applyModelManagerSettings } from "@/lib/api";

export default function ModelGate({ children }: { children: React.ReactNode }) {
  const [checking, setChecking] = useState(true);
  const [hasModel, setHasModel] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState("Idle");
  const [error, setError] = useState<string | null>(null);

  async function checkModels() {
    setChecking(true);
    try {
      const manager = await getModelManager();
      // If there are any models starting with "ollama/" or custom GGUF models (besides auto and extractive-fallback)
      const options = manager.llm.options || [];
      const actualModels = options.filter(
        (opt) => opt.id !== "auto" && opt.id !== "extractive-fallback"
      );
      
      if (actualModels.length > 0) {
        setHasModel(true);
      } else {
        setHasModel(false);
      }
    } catch (err) {
      console.error("Failed to check models:", err);
      // Fail-safe: let user in if API fails
      setHasModel(true);
    } finally {
      setChecking(false);
    }
  }

  useEffect(() => {
    void checkModels();
  }, []);

  async function startDownload() {
    setDownloading(true);
    setError(null);
    setProgress(0);
    setStatusText("Initializing download...");

    try {
      // Get dynamic API base port from localStorage
      const storedPort = typeof window !== "undefined" ? window.localStorage.getItem("localmind_api_port") : null;
      const apiBase = storedPort ? `http://127.0.0.1:${storedPort}` : "http://127.0.0.1:8000";

      const response = await fetch(`${apiBase}/models/pull`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ llm: "qwen2.5:1.5b" })
      });

      if (!response.ok) {
        throw new Error(`Download failed: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("Failed to read download stream");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const update = JSON.parse(line);
            if (update.error) {
              throw new Error(update.error);
            }
            if (update.total > 0) {
              const pct = Math.round((update.completed / update.total) * 100);
              setProgress(pct);
              setStatusText(update.status || "Downloading...");
            } else {
              setStatusText(update.status || "Downloading...");
            }
          } catch (e) {
            console.warn("Failed to parse progress update:", e);
          }
        }
      }

      setStatusText("Applying settings...");
      // Apply the newly downloaded Qwen model as the active LLM
      await applyModelManagerSettings({
        llm: "ollama/qwen2.5:1.5b"
      });

      setStatusText("Complete!");
      setHasModel(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
      setDownloading(false);
    }
  }

  if (checking) {
    return (
      <div className="flex min-h-[calc(100vh-12rem)] items-center justify-center">
        <div className="shell-panel w-full max-w-lg p-6 text-center sm:p-8">
          <div className="eyebrow">Models</div>
          <div className="mt-3 text-2xl font-semibold text-white">Scanning local model stack</div>
          <div className="mt-3 text-sm leading-7 text-zinc-400">Locating Ollama models...</div>
        </div>
      </div>
    );
  }

  if (hasModel) {
    return <>{children}</>;
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-12rem)] max-w-5xl items-center py-8">
      <div className="grid w-full gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="shell-panel p-6 sm:p-8">
          <div className="eyebrow">First-Time Setup</div>
          <div className="mt-3 font-display text-3xl font-semibold text-white sm:text-4xl">
            Download your local AI model
          </div>
          <div className="mt-3 max-w-2xl text-sm leading-7 text-zinc-400">
            LocalMind OS runs completely offline. To enable smart grounded answers, study guides, and quizzes, we need to download a lightweight local language model (**Qwen 2.5 1.5B**, approx. 1.2 GB) into your embedded Ollama server.
          </div>

          <div className="mt-6 rounded-[16px] border border-white/8 bg-white/[0.02] p-4 text-xs leading-6 text-zinc-500">
            💡 **Why Qwen 2.5 1.5B?** It is highly optimized for 8GB RAM laptops, running extremely fast on your CPU while maintaining high quality logic for citations.
          </div>
        </div>

        <div className="shell-panel flex flex-col justify-center p-6 sm:p-8">
          {!downloading ? (
            <div className="space-y-4">
              <div className="text-center">
                <div className="text-xs uppercase tracking-[0.18em] text-zinc-400">Model size</div>
                <div className="mt-2 text-3xl font-bold text-white">1.2 GB</div>
              </div>

              {error ? (
                <div className="rounded-[12px] border border-rose-300/20 bg-rose-300/6 px-4 py-3 text-sm leading-6 text-rose-100">
                  ⚠️ {error}
                </div>
              ) : null}

              <button
                onClick={startDownload}
                className="btn-primary w-full py-4 text-base font-semibold"
              >
                Download & Setup
              </button>

              <button
                onClick={() => setHasModel(true)}
                className="btn-secondary w-full"
              >
                Skip (Use Extractive Fallback Only)
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              <div className="text-center">
                <div className="text-xs uppercase tracking-[0.18em] text-zinc-400">Status</div>
                <div className="mt-2 text-lg font-medium text-white capitalize">{statusText}</div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-zinc-500">Progress</span>
                  <span className="font-medium text-white">{progress}%</span>
                </div>
                <div className="h-3 w-full overflow-hidden rounded-full bg-white/8">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-sky-400 to-sky-300 transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>

              <div className="text-center text-xs leading-6 text-zinc-500">
                Please do not close the application. This process may take a few minutes depending on your internet connection.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
