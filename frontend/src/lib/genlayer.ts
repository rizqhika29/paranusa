"use client";
// GenLayer access layer (genlayer-js v1 — the Studionet-compatible line).
// v2 RC reads/writes are not processed by current Studionet validators
// (0 rounds, NO_MAJORITY), so the app pins v1: plain readContract,
// fee-less writeContract (node assigns fees, CLI-style), and polling
// getTransaction until FINALIZED + leader-result verification.
import { createClient } from "genlayer-js";
import { localnet, studionet, testnetBradbury } from "genlayer-js/chains";
import type { NetworkKey } from "./config";

const CHAIN_MAP = {
  studionet: studionet,
  bradbury: testnetBradbury,
  localnet: localnet,
} as const;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type GenClient = any;

export function getChain(network: NetworkKey) {
  return CHAIN_MAP[network];
}

/** Read-only client (no wallet). */
export function readOnlyClient(network: NetworkKey): GenClient {
  return createClient({ chain: getChain(network) });
}

/** Client with a browser wallet (EIP-1193) for writes. */
export function walletClient(network: NetworkKey, address: string, provider: unknown): GenClient {
  return createClient({
    chain: getChain(network),
    account: address as `0x${string}`,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    provider: provider as any,
  });
}

export interface PolicyView {
  holder: string;
  location: string;
  lat: string;
  lon: string;
  disaster_type: string;
  threshold: string;
  premium: string;
  payout_amount: string;
  active: boolean;
  assessed: boolean;
  trigger_met: boolean;
  measured_value: string;
  evidence: string;
  paid: boolean;
  assess_tx: string;
}

export interface PoolStats {
  owner: string;
  policy_count: number;
  total_premiums: string;
  total_payouts: string;
  total_locked: string;
  pool_balance: string;
}

export async function readPolicy(
  client: GenClient,
  contract: string,
  policyId: string
): Promise<PolicyView> {
  const r = (await client.readContract({
    address: contract,
    functionName: "get_policy",
    args: [policyId],
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  })) as any;
  return {
    holder: String(r.holder ?? r[0] ?? ""),
    location: String(r.location ?? r[1] ?? ""),
    lat: String(r.lat ?? r[2] ?? ""),
    lon: String(r.lon ?? r[3] ?? ""),
    disaster_type: String(r.disaster_type ?? r[4] ?? ""),
    threshold: String(r.threshold ?? r[5] ?? ""),
    premium: String(r.premium ?? r[6] ?? "0"),
    payout_amount: String(r.payout_amount ?? r[7] ?? "0"),
    active: Boolean(r.active ?? r[8] ?? false),
    assessed: Boolean(r.assessed ?? r[9] ?? false),
    trigger_met: Boolean(r.trigger_met ?? r[10] ?? false),
    measured_value: String(r.measured_value ?? r[11] ?? ""),
    evidence: String(r.evidence ?? r[12] ?? ""),
    paid: Boolean(r.paid ?? r[13] ?? false),
    assess_tx: String(r.assess_tx ?? r[14] ?? ""),
  };
}

export async function readStats(client: GenClient, contract: string): Promise<PoolStats> {
  const r = (await client.readContract({
    address: contract,
    functionName: "get_stats",
    args: [],
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  })) as any;
  return {
    owner: String(r.owner ?? r[0] ?? ""),
    policy_count: Number(r.policy_count ?? r[1] ?? 0),
    total_premiums: String(r.total_premiums ?? r[2] ?? "0"),
    total_payouts: String(r.total_payouts ?? r[3] ?? "0"),
    total_locked: String(r.total_locked ?? r[4] ?? "0"),
    pool_balance: String(r.pool_balance ?? r[5] ?? r[4] ?? "0"),
  };
}

export type TxStage =
  | "estimating"
  | "awaiting-signature"
  | "submitted"
  | "decided"
  | "finalizing"
  | "done";

export interface StageCallback {
  (stage: TxStage, hash?: string): void;
}

export interface WriteOptions {
  value?: bigint;
  onStage?: StageCallback;
  timeoutMs?: number;
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function leaderResultOf(tx: any): any {
  const receipts = tx?.consensus_data?.leader_receipt;
  if (Array.isArray(receipts) && receipts.length > 0) return receipts[0]?.result;
  return undefined;
}

function successError(tx: unknown, hash: string): Error | null {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const t = tx as any;
  if (t?.result_name && t.result_name !== "MAJORITY_AGREE") {
    return new Error(`Consensus not reached: ${String(t.result_name)}`);
  }
  const res = leaderResultOf(t);
  if (res && typeof res === "object") {
    if (res.status === "rollback") {
      const msg = typeof res.payload === "string" ? res.payload : "Contract reverted execution";
      return new Error(msg);
    }
    if (res.status && res.status !== "return") {
      return new Error(`Contract execution failed: ${String(res.status)}`);
    }
  }
  if (t?.result_name !== "MAJORITY_AGREE") {
    return new Error(`Consensus not reached: ${String(t?.result_name ?? "unknown")}`);
  }
  return null;
}

/**
 * Write lifecycle on Studionet (v1 lib):
 * writeContract (no explicit fees — node assigns them) -> poll getTransaction
 * until FINALIZED -> verify MAJORITY_AGREE + leader return (not rollback).
 * A poll timeout after submit does NOT mean failure — the hash stays tracked.
 */
export async function writeWithLifecycle(
  client: GenClient,
  call: { address: string; functionName: string; args: unknown[]; value?: bigint },
  opts: WriteOptions = {}
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): Promise<{ hash: string; receipt: any }> {
  const { onStage, value, timeoutMs = 50 * 60 * 1000 } = opts;
  const payload = { ...call, ...(value !== undefined ? { value } : {}) };

  onStage?.("awaiting-signature");
  const hash: string = await client.writeContract({ ...payload });

  onStage?.("submitted", hash);
  const deadline = Date.now() + timeoutMs;
  let decided = false;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let tx: any = null;
  for (;;) {
    try {
      tx = await client.getTransaction({ hash });
    } catch {
      tx = null;
    }
    if (tx) {
      const rounds = Number(tx.num_of_rounds ?? 0);
      if (!decided && (rounds > 0 || tx.last_leader)) {
        decided = true;
        onStage?.("decided", hash);
      }
      if (tx.statusName === "FINALIZED" || tx.status_name === "FINALIZED") {
        break;
      }
    }
    if (Date.now() > deadline) {
      const err = new Error(
        "Confirmation timeout — the tx was submitted but finalization was not observed in time."
      );
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (err as any).txHash = hash;
      throw err;
    }
    await sleep(15000);
  }
  onStage?.("finalizing", hash);
  const fail = successError(tx, hash);
  if (fail) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (fail as any).txHash = hash;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (fail as any).receipt = tx;
    throw fail;
  }
  onStage?.("done", hash);
  return { hash, receipt: tx };
}

export function policyStatusLabel(p: PolicyView): { text: string; tone: string } {
  if (p.paid) return { text: "Payout sent", tone: "paid" };
  if (p.assessed && p.trigger_met) return { text: "Trigger met — ready to claim", tone: "claimable" };
  if (p.assessed && !p.trigger_met) return { text: "Trigger not met", tone: "idle" };
  if (!p.active) return { text: "Inactive", tone: "idle" };
  return { text: "Active — not assessed", tone: "active" };
}

/** Data-source URL the contract will fetch for this policy (transparency). */
export async function readPreviewUrl(
  client: GenClient,
  contract: string,
  policyId: string
): Promise<string> {
  const r = await client.readContract({
    address: contract,
    functionName: "preview_url",
    args: [policyId],
  });
  return String(r ?? "");
}
