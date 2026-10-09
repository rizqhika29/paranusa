"use client";
// Global state: network, contract, wallet, toasts, session tx history,
// and recently-used policy IDs (per contract).
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  NETWORKS,
  contractAddressFor,
  isZeroAddress,
  type NetworkKey,
} from "@/lib/config";
import { readOnlyClient } from "@/lib/genlayer";

export interface Toast {
  id: number;
  tone: "success" | "error" | "info";
  title: string;
  message: string;
  txHash?: string;
}

export interface RecentPolicy {
  id: string;
  holder: string;
  time: number;
}

export interface TrackedTx {
  id: number;
  label: string;
  hash: string | null;
  stage: string;
  ok: boolean | null;
  error?: string;
  time: number;
  network: NetworkKey;
  policyId?: string;
}

interface AppState {
  network: NetworkKey;
  contract: string;
  contractFromEnv: boolean;
  wallet: string | null;
  connecting: boolean;
  connectWallet: () => Promise<void>;
  disconnectWallet: () => void;
  provider: unknown;
  toasts: Toast[];
  pushToast: (t: Omit<Toast, "id">) => void;
  dismissToast: (id: number) => void;
  txs: TrackedTx[];
  trackTx: (t: Omit<TrackedTx, "id" | "time">) => number;
  updateTx: (id: number, patch: Partial<TrackedTx>) => void;
  recentPolicies: RecentPolicy[];
  rememberPolicy: (id: string, holder?: string) => void;
  forgetPolicy: (id: string) => void;
}

const Ctx = createContext<AppState | null>(null);
let seq = 1;

function recentKey(contract: string): string {
  return `paranusa:recent:${contract.toLowerCase()}`;
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [network] = useState<NetworkKey>(() => {
    const d = process.env.NEXT_PUBLIC_DEFAULT_NETWORK;
    return d === "bradbury" || d === "localnet" ? d : "studionet";
  });
  const [wallet, setWallet] = useState<string | null>(null);
  const [provider, setProvider] = useState<unknown>(null);
  const [connecting, setConnecting] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  // Session tx history, persisted so assessment proofs survive reloads.
  const [txs, setTxs] = useState<TrackedTx[]>(() => {
    try {
      const raw = localStorage.getItem("paranusa:txs");
      if (!raw) return [];
      const arr = JSON.parse(raw) as TrackedTx[];
      return Array.isArray(arr) ? arr.filter((t) => t && t.label).slice(0, 20) : [];
    } catch {
      return [];
    }
  });
  const [recentPolicies, setRecentPolicies] = useState<RecentPolicy[]>([]);

  // Note: network + contract are deployment-pinned (env only).
  // No UI may change them; stale localStorage overrides are ignored.
  useEffect(() => {
    try {
      localStorage.removeItem("paranusa:network");
      localStorage.removeItem("paranusa:contract");
    } catch {
      /* ignore */
    }
  }, []);

  const envAddr = contractAddressFor(network);
  const contract = envAddr;
  const contractFromEnv = true;

  useEffect(() => {
    if (!contract || isZeroAddress(contract)) {
      setRecentPolicies([]);
      return;
    }
    try {
      const raw = localStorage.getItem(recentKey(contract));
      if (!raw) {
        setRecentPolicies([]);
        return;
      }
      const parsed = JSON.parse(raw) as (RecentPolicy | string)[];
      // Migrate legacy plain-string entries (holder unknown -> "").
      const norm: RecentPolicy[] = parsed
        .map((x) =>
          typeof x === "string"
            ? { id: x, holder: "", time: 0 }
            : { id: String(x.id), holder: String(x.holder ?? ""), time: Number(x.time ?? 0) }
        )
        .filter((x) => x.id);
      setRecentPolicies(norm.slice(0, 24));
    } catch {
      setRecentPolicies([]);
    }
  }, [contract]);

  const rememberPolicy = useCallback(
    (id: string, holder = "") => {
      const pid = id.trim();
      if (!pid || !contract || isZeroAddress(contract)) return;
      setRecentPolicies((prev) => {
        const entry: RecentPolicy = {
          id: pid,
          holder: holder.trim(),
          time: Date.now(),
        };
        const next = [entry, ...prev.filter((x) => x.id !== pid)].slice(0, 24);
        try {
          localStorage.setItem(recentKey(contract), JSON.stringify(next));
        } catch {
          /* ignore */
        }
        return next;
      });
    },
    [contract]
  );

  const forgetPolicy = useCallback(
    (id: string) => {
      if (!contract) return;
      setRecentPolicies((prev) => {
        const next = prev.filter((x) => x.id !== id);
        try {
          localStorage.setItem(recentKey(contract), JSON.stringify(next));
        } catch {
          /* ignore */
        }
        return next;
      });
    },
    [contract]
  );

  const pushToast = useCallback((t: Omit<Toast, "id">) => {
    const id = seq++;
    setToasts((prev) => [...prev.slice(-3), { ...t, id }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((x) => x.id !== id));
    }, 9000);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((x) => x.id !== id));
  }, []);

  const trackTx = useCallback((t: Omit<TrackedTx, "id" | "time">) => {
    const id = seq++;
    setTxs((prev) => {
      const next = [{ ...t, id, time: Date.now() }, ...prev].slice(0, 20);
      try {
        localStorage.setItem("paranusa:txs", JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
    return id;
  }, []);

  const updateTx = useCallback((id: number, patch: Partial<TrackedTx>) => {
    setTxs((prev) => {
      const next = prev.map((x) => (x.id === id ? { ...x, ...patch } : x)).slice(0, 20);
      try {
        localStorage.setItem("paranusa:txs", JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const connectWallet = useCallback(async () => {
    const eth = (window as unknown as { ethereum?: unknown }).ethereum;
    if (!eth) {
      pushToast({
        tone: "error",
        title: "No wallet found",
        message: "Install MetaMask (or any EIP-1193 wallet) first, then refresh this page.",
      });
      return;
    }
    setConnecting(true);
    try {
      const req = eth as {
        request: (a: { method: string; params?: unknown }) => Promise<unknown>;
      };
      const accounts = (await req.request({ method: "eth_requestAccounts" })) as string[];
      if (!accounts || accounts.length === 0) throw new Error("Wallet did not expose any account.");
      const addr = accounts[0];
      // Move the wallet to the selected GenLayer chain (best effort)
      try {
        await req.request({
          method: "wallet_switchEthereumChain",
          params: [{ chainId: `0x${NETWORKS[network].chainId.toString(16)}` }],
        });
      } catch {
        /* user can switch manually — continue anyway */
      }
      setWallet(addr);
      setProvider(eth);
      pushToast({
        tone: "success",
        title: "Wallet connected",
        message: `Active on ${NETWORKS[network].label}.`,
      });
    } catch (e) {
      pushToast({
        tone: "error",
        title: "Failed to connect wallet",
        message: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setConnecting(false);
    }
  }, [network, pushToast]);

  const disconnectWallet = useCallback(() => {
    setWallet(null);
    setProvider(null);
  }, []);

  // Lightweight RPC reachability probe when the network changes (best effort)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const c = readOnlyClient(network);
        await c.getChainId();
      } catch {
        if (!cancelled)
          pushToast({
            tone: "info",
            title: `${NETWORKS[network].label} RPC`,
            message: "The node is not responding yet — check your connection or switch networks.",
          });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [network, pushToast]);

  const value = useMemo<AppState>(
    () => ({
      network,
      contract,
      contractFromEnv,
      wallet,
      connecting,
      connectWallet,
      disconnectWallet,
      provider,
      toasts,
      pushToast,
      dismissToast,
      txs,
      trackTx,
      updateTx,
      recentPolicies,
      rememberPolicy,
      forgetPolicy,
    }),
    [
      network, contract, contractFromEnv,
      wallet, connecting, connectWallet, disconnectWallet, provider,
      toasts, pushToast, dismissToast, txs, trackTx, updateTx,
      recentPolicies, rememberPolicy, forgetPolicy,
    ]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useApp outside AppProvider");
  return ctx;
}

export function useContractReady(): { ready: boolean; hint: string } {
  const { contract } = useApp();
  if (!contract || isZeroAddress(contract)) {
    return {
      ready: false,
      hint: "Contract address not set — deploy via Studio, then paste it in Settings / .env.",
    };
  }
  if (!/^0x[0-9a-fA-F]{40}$/.test(contract.trim())) {
    return { ready: false, hint: "Invalid contract address format (must be 0x + 40 hex chars)." };
  }
  return { ready: true, hint: "" };
}
