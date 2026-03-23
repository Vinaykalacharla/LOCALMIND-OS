"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { getSecurityStatus, lockSecurity, SecurityStatus, setupSecurity, unlockSecurity } from "@/lib/api";

interface SecurityContextValue {
  status: SecurityStatus | null;
  loading: boolean;
  busy: boolean;
  error: string | null;
  refreshStatus: () => Promise<void>;
  setup: (passphrase: string) => Promise<void>;
  unlock: (passphrase: string) => Promise<void>;
  lock: () => Promise<void>;
}

const SecurityContext = createContext<SecurityContextValue | null>(null);

export function useSecurity() {
  const ctx = useContext(SecurityContext);
  if (!ctx) {
    throw new Error("useSecurity must be used within SecurityProvider");
  }
  return ctx;
}

export default function SecurityProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<SecurityStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshStatus() {
    setLoading(true);
    try {
      const nextStatus = await getSecurityStatus();
      setStatus(nextStatus);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to read backend security status");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshStatus();
  }, []);

  async function setup(passphrase: string) {
    setBusy(true);
    try {
      const nextStatus = await setupSecurity(passphrase);
      setStatus(nextStatus);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to configure security");
      throw nextError;
    } finally {
      setBusy(false);
    }
  }

  async function unlock(passphrase: string) {
    setBusy(true);
    try {
      const nextStatus = await unlockSecurity(passphrase);
      setStatus(nextStatus);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to unlock backend");
      throw nextError;
    } finally {
      setBusy(false);
    }
  }

  async function lock() {
    setBusy(true);
    try {
      const nextStatus = await lockSecurity();
      setStatus(nextStatus);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to lock backend");
      throw nextError;
    } finally {
      setBusy(false);
    }
  }

  return (
    <SecurityContext.Provider value={{ status, loading, busy, error, refreshStatus, setup, unlock, lock }}>
      {children}
    </SecurityContext.Provider>
  );
}
