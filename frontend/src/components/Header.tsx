"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { useSecurity } from "@/components/SecurityProvider";
import { useToast } from "@/components/ToastProvider";
import { getPageMeta, isActivePath, navItems } from "@/lib/navigation";

export default function Header() {
  const pathname = usePathname();
  const { status, loading, busy, lock } = useSecurity();
  const { pushToast } = useToast();
  const meta = getPageMeta(pathname);

  async function onLock() {
    try {
      await lock();
      pushToast("info", "LocalMind OS locked");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to lock backend";
      pushToast("error", message);
    }
  }

  const securityLabel = loading
    ? "Checking vault"
    : !status?.configured
      ? "Setup required"
      : status.unlocked
        ? "Vault unlocked"
        : "Vault locked";

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-x-4 border-b border-[var(--line)] bg-[var(--bg-subtle)]/80 px-4 shadow-sm backdrop-blur-xl sm:gap-x-6 sm:px-6 lg:px-8">
      <div className="flex flex-1 items-center gap-x-4 lg:gap-x-6">
        <div className="flex items-baseline gap-2">
          <h1 className="text-lg font-semibold leading-6 text-[var(--text-main)]">
            {meta.title}
          </h1>
          <span className="hidden sm:block text-sm text-[var(--text-muted)]">
            / {meta.eyebrow}
          </span>
        </div>
      </div>
      
      <div className="flex items-center gap-x-4 lg:gap-x-6">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-full border border-[var(--line)] bg-[var(--panel-soft)] px-3 py-1.5 text-xs font-medium text-[var(--text-muted)]">
            <span className="relative flex h-2 w-2">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${loading || (!status?.configured || !status.unlocked) ? 'bg-[var(--warning)]' : 'bg-[var(--success)]'}`}></span>
              <span className={`relative inline-flex rounded-full h-2 w-2 ${loading || (!status?.configured || !status.unlocked) ? 'bg-[var(--warning)]' : 'bg-[var(--success)]'}`}></span>
            </span>
            {securityLabel}
          </div>
          {status?.configured && status.unlocked ? (
            <button onClick={onLock} disabled={busy} className="btn-secondary h-8 px-3 py-1 text-xs disabled:opacity-60">
              {busy ? "Locking..." : "Lock"}
            </button>
          ) : null}
        </div>
      </div>

      {/* Mobile Nav Overflows */}
      <div className="absolute top-16 left-0 right-0 border-b border-[var(--line)] bg-[var(--bg-base)] px-4 py-2 overflow-x-auto xl:hidden">
        <div className="flex min-w-max gap-2 pb-1">
          {navItems.map((item) => {
            const active = isActivePath(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  "rounded-full border px-4 py-1.5 text-xs font-medium transition",
                  active
                    ? "border-[var(--accent-dim)] bg-[var(--accent-dim)] text-[var(--accent-bright)]"
                    : "border-[var(--line)] bg-transparent text-[var(--text-muted)] hover:bg-[var(--panel-hover)] hover:text-[var(--text-main)]"
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </div>
    </header>
  );
}
