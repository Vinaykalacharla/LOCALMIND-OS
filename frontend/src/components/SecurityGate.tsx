"use client";

import React, { useState } from "react";
import { usePathname } from "next/navigation";
import { useSecurity } from "@/components/SecurityProvider";
import { getPageMeta } from "@/lib/navigation";

export default function SecurityGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { status, loading, busy, error: providerError, refreshStatus, setup, unlock } = useSecurity();
  const [passphrase, setPassphrase] = useState("");
  const [confirmPassphrase, setConfirmPassphrase] = useState("");
  const [error, setError] = useState<string | null>(null);
  const pageMeta = getPageMeta(pathname);

  if (!loading && providerError && status === null) {
    return (
      <div className="flex min-h-[calc(100vh-12rem)] items-center justify-center">
        <div className="shell-panel w-full max-w-lg p-8 text-center">
          <div className="eyebrow">Backend</div>
          <div className="mt-3 text-2xl font-semibold text-white">Backend unavailable</div>
          <div className="mt-3 text-sm leading-7 text-zinc-400">{providerError}</div>
          <button onClick={() => void refreshStatus()} className="btn-secondary mt-6">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (loading || status === null) {
    return (
      <div className="flex min-h-[calc(100vh-12rem)] items-center justify-center">
        <div className="shell-panel w-full max-w-lg p-8 text-center">
          <div className="eyebrow">Vault</div>
          <div className="mt-3 text-2xl font-semibold text-white">Checking status</div>
          <div className="mt-3 text-sm leading-7 text-zinc-400">Waiting for backend security status.</div>
        </div>
      </div>
    );
  }

  if (status.configured && status.unlocked) {
    return <>{children}</>;
  }

  const currentStatus = status;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = passphrase.trim();
    if (!trimmed) {
      setError("Passphrase is required");
      return;
    }

    if (trimmed.length < 8) {
      setError("Passphrase must be at least 8 characters");
      return;
    }

    if (!currentStatus.configured && trimmed !== confirmPassphrase.trim()) {
      setError("Passphrases do not match");
      return;
    }

    setError(null);
    try {
      if (currentStatus.configured) {
        await unlock(trimmed);
      } else {
        await setup(trimmed);
      }
      setPassphrase("");
      setConfirmPassphrase("");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Security action failed");
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-12rem)] max-w-5xl items-center py-8">
      <div className="grid w-full gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="shell-panel p-8">
          <div className="eyebrow">{currentStatus.configured ? "Unlock" : "Setup"}</div>
          <div className="mt-3 font-display text-4xl font-semibold text-white">
            {currentStatus.configured ? "Unlock your vault" : "Create your vault"}
          </div>
          <div className="mt-3 max-w-2xl text-sm leading-7 text-zinc-400">
            {currentStatus.configured
              ? "Enter your passphrase to continue."
              : "Set a passphrase to enable the local vault and continue to the app."}
          </div>

          <div className="mt-6 shell-panel-soft p-4">
            <div className="text-sm font-medium text-white">{pageMeta.title}</div>
            <div className="mt-1 text-sm leading-6 text-zinc-400">{pageMeta.description}</div>
          </div>
        </div>

        <div className="shell-panel p-8">
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="mb-2 block text-xs uppercase tracking-[0.18em] text-zinc-400">Passphrase</label>
              <input
                type="password"
                value={passphrase}
                onChange={(event) => setPassphrase(event.target.value)}
                className="input-shell"
                placeholder="Enter passphrase"
              />
            </div>

            {!currentStatus.configured ? (
              <div>
                <label className="mb-2 block text-xs uppercase tracking-[0.18em] text-zinc-400">Confirm passphrase</label>
                <input
                  type="password"
                  value={confirmPassphrase}
                  onChange={(event) => setConfirmPassphrase(event.target.value)}
                  className="input-shell"
                  placeholder="Confirm passphrase"
                />
              </div>
            ) : null}

            {error ? (
              <div className="rounded-[12px] border border-rose-300/20 bg-rose-300/6 px-4 py-3 text-sm text-rose-100">
                {error}
              </div>
            ) : null}

            <button type="submit" disabled={busy} className="btn-primary w-full disabled:opacity-60">
              {busy
                ? currentStatus.configured
                  ? "Unlocking..."
                  : "Setting up..."
                : currentStatus.configured
                  ? "Unlock vault"
                  : "Create vault"}
            </button>
          </form>

          <div className="mt-5 text-xs leading-6 text-zinc-500">
            Minimum 8 characters. The same passphrase is required in later sessions.
          </div>
        </div>
      </div>
    </div>
  );
}
