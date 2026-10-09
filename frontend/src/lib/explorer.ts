// On-chain tx index via the network explorer API (no browser storage).
// Answers "which assessment tx belongs to this policy?" for ANY client:
// list the contract's txs, decode GenVM calldata (method + policy ID),
// and bind assess/claim hashes to the policy being viewed.
import type { NetworkKey } from "./config";

const API_BASE: Record<NetworkKey, string | null> = {
  studionet: "https://explorer-studio.genlayer.com",
  bradbury: "https://explorer-bradbury.genlayer.com",
  localnet: null,
};

export const KNOWN_METHODS = [
  "fund_pool",
  "create_policy",
  "assess_claim",
  "claim_payout",
  "cancel_policy",
  "withdraw_surplus",
];

export interface IndexedTx {
  hash: string;
  method: string;
  policyId: string;
  status: string;
  /** Raw calldata text — caller matches the policy ID by substring. */
  raw: string;
}

/** Extract the called method from raw calldata text. The GenVM binary format
 *  embeds method names and string args in the clear, so substring matching
 *  is sufficient and robust (no full binary decoder needed). */
export function extractMethod(b64: string): string {
  let text: string;
  try {
    const bin = atob(b64);
    text = Array.from(bin, (c) => (c.charCodeAt(0) < 128 ? c : " ")).join("");
  } catch {
    return "";
  }
  return KNOWN_METHODS.find((m) => text.includes(m)) ?? "";
}

/** Raw calldata text for substring checks (policy ID binding). */
export function calldataText(b64: string): string {
  try {
    const bin = atob(b64);
    return Array.from(bin, (c) => (c.charCodeAt(0) < 128 ? c : " ")).join("");
  } catch {
    return "";
  }
}

/** All indexed txs for a contract (paginated, newest first). */
export async function fetchContractTxs(
  network: NetworkKey,
  contract: string,
  maxPages = 5
): Promise<IndexedTx[]> {
  const base = API_BASE[network];
  if (!base) throw new Error("No explorer API for this network");
  const out: IndexedTx[] = [];
  for (let page = 1; page <= maxPages; page++) {
    const url = `${base}/api/transactions?limit=50&address=${contract}&page=${page}`;
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`Explorer API ${res.status}`);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const data = (await res.json()) as any;
    const list = (data?.transactions ?? []) as Array<{
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      hash?: string; status?: string; data?: any;
    }>;
    for (const t of list) {
      if (!t?.hash) continue;
      const cd = t?.data?.calldata;
      if (typeof cd !== "string" || !cd) continue;
      const method = extractMethod(cd);
      if (!KNOWN_METHODS.includes(method)) continue;
      const text = calldataText(cd);
      out.push({
        hash: t.hash,
        method,
        policyId: "", // bound by caller via substring match (see below)
        status: String(t.status ?? ""),
        raw: text,
      });
    }
    const totalPages = Number(data?.pagination?.totalPages ?? 1);
    if (page >= totalPages) break;
  }
  return out;
}

/** assess/claim txs for one policy, newest first. Binding is by substring:
 *  the policy ID must appear in the raw calldata text. */
export async function fetchPolicyProofTxs(
  network: NetworkKey,
  contract: string,
  policyId: string
): Promise<IndexedTx[]> {
  const all = await fetchContractTxs(network, contract);
  return all.filter(
    (t) =>
      (t.method === "assess_claim" || t.method === "claim_payout") &&
      t.raw.includes(policyId)
  );
}
