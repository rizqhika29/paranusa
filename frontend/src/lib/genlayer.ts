"use client";
// GenLayer access layer: clients, reads, writes with the correct lifecycle
// estimate -> submit -> decision -> finalization + isSuccessful verification.
import { createClient, isSuccessful } from "genlayer-js";
import { localnet, studionet, testnetBradbury } from "genlayer-js/chains";
import { TransactionHashVariant } from "genlayer-js/types";
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

/** Client read-only (tanpa wallet). */
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
    transactionHashVariant: TransactionHashVariant.LATEST_FINAL,
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
  };
}

export async function readStats(client: GenClient, contract: string): Promise<PoolStats> {  const r = (await client.readContract({
    address: contract,
    functionName: "get_stats",
    args: [],
    transactionHashVariant: TransactionHashVariant.LATEST_FINAL,
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
}

/**
 * Correct write lifecycle (docs: writing-data):
 * estimate -> writeContract(+fees) -> waitForDecision -> waitForFinalization
 * -> isSuccessful. ALWAYS check isSuccessful, not just ACCEPTED/FINALIZED status.
 * A timeout after submit does NOT mean failure — the hash is still tracked.
 */
export async function writeWithLifecycle(
  client: GenClient,
  call: { address: string; functionName: string; args: unknown[]; value?: bigint },
  opts: WriteOptions = {}
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): Promise<{ hash: string; receipt: any }> {
  const { onStage, value } = opts;
  onStage?.("estimating");
  const payload = { ...call, ...(value !== undefined ? { value } : {}) };
  // Fee estimation needs Studio-only sim_* RPCs — unavailable on public
  // testnets. Fall back to fee-less submission (node assigns fees, CLI-style).
  let fees: { distribution: unknown; feeValue: unknown } | undefined;
  try {
    const estimate = await client.estimateTransactionFeesForWrite(payload);
    fees = { distribution: estimate.distribution, feeValue: estimate.feeValue };
  } catch {
    fees = undefined;
  }

  onStage?.("awaiting-signature");
  const hash: string = await client.writeContract({
    ...payload,
    ...(fees ? { fees } : {}),
  });

  onStage?.("submitted", hash);
  await client.waitForDecision({ hash });
  onStage?.("decided", hash);
  onStage?.("finalizing", hash);
  const receipt = await client.waitForFinalization({ hash });
  if (!isSuccessful(receipt)) {
    const err = new Error(
      `Contract execution failed: ${String(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (receipt as any).statusName ?? (receipt as any).status ?? "UNKNOWN"
      )} / ${String(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (receipt as any).txExecutionResultName ?? (receipt as any).txExecutionResult ?? "UNKNOWN"
      )}`
    );
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (err as any).receipt = receipt;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (err as any).txHash = hash;
    throw err;
  }
  onStage?.("done", hash);
  return { hash, receipt };
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
    transactionHashVariant: TransactionHashVariant.LATEST_FINAL,
  });
  return String(r ?? "");
}
