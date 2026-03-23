"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { isActivePath, navItems } from "@/lib/navigation";

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 hidden h-screen w-[260px] shrink-0 px-5 py-6 xl:flex">
      <div className="shell-panel flex h-full w-full flex-col p-5">
        <div>
          <div className="text-lg font-semibold text-white">LocalMind OS</div>
          <div className="mt-1 text-sm leading-6 text-zinc-400">Local AI workspace</div>
        </div>

        <nav className="mt-8 space-y-1.5">
          {navItems.map((item) => {
            const active = isActivePath(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  "block rounded-[12px] px-3 py-2.5 transition",
                  active
                    ? "bg-white/[0.06] text-white"
                    : "text-zinc-300 hover:bg-white/[0.03] hover:text-white"
                )}
              >
                <div className="text-sm font-medium">{item.label}</div>
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto text-xs leading-6 text-zinc-500">
          Secure your vault before using protected routes.
        </div>
      </div>
    </aside>
  );
}
