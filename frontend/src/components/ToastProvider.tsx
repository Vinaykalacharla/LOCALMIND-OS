"use client";

import React, { createContext, useContext, useMemo, useState } from "react";

type ToastKind = "success" | "error" | "info";

interface ToastItem {
  id: string;
  kind: ToastKind;
  message: string;
}

interface ToastContextValue {
  pushToast: (kind: ToastKind, message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return ctx;
}

function kindClass(kind: ToastKind): string {
  if (kind === "success") return "border-emerald-200/24 bg-emerald-200/10 text-emerald-50";
  if (kind === "error") return "border-rose-200/24 bg-rose-200/10 text-rose-50";
  return "border-sky-200/24 bg-sky-200/10 text-sky-50";
}

function kindLabel(kind: ToastKind): string {
  if (kind === "success") return "Success";
  if (kind === "error") return "Error";
  return "Notice";
}

export default function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const value = useMemo<ToastContextValue>(
    () => ({
      pushToast: (kind, message) => {
        const id = Math.random().toString(36).slice(2);
        setItems((prev) => [...prev, { id, kind, message }]);
        setTimeout(() => {
          setItems((prev) => prev.filter((t) => t.id !== id));
        }, 3500);
      }
    }),
    []
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
        {items.map((item) => (
          <div
            key={item.id}
            className={`rounded-[22px] border px-4 py-3 text-sm shadow-panel backdrop-blur-xl ${kindClass(item.kind)}`}
          >
            <div className="text-[11px] font-semibold uppercase tracking-[0.24em] opacity-80">{kindLabel(item.kind)}</div>
            <div className="mt-1 leading-6">{item.message}</div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
