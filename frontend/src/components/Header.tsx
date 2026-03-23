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

  const securityTone = loading
    ? "status-pill"
    : !status?.configured || !status.unlocked
      ? "status-pill warn"
      : "status-pill";

  return (
    <header className="sticky top-0 z-30 border-b border-white/6 bg-[#0d1322]/88 backdrop-blur-xl">
      <div className="px-4 py-5 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <div className="eyebrow">{meta.eyebrow}</div>
            <h1 className="mt-2 max-w-4xl font-display text-3xl font-semibold text-white sm:text-[2.15rem]">
              {meta.title}
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-7 text-zinc-400">{meta.description}</p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <span className={securityTone}>{securityLabel}</span>
            {status?.configured && status.unlocked ? (
              <button onClick={onLock} disabled={busy} className="btn-secondary disabled:opacity-60">
                {busy ? "Locking..." : "Lock"}
              </button>
            ) : null}
          </div>
        </div>

        <div className="mt-4 overflow-x-auto xl:hidden">
          <div className="flex min-w-max gap-2 pb-1">
            {navItems.map((item) => {
              const active = isActivePath(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={clsx(
                    "rounded-full border px-4 py-2 text-sm transition",
                    active
                      ? "border-white/10 bg-white/[0.07] text-white"
                      : "border-white/8 bg-transparent text-zinc-300 hover:bg-white/[0.04] hover:text-white"
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </header>
  );
}
