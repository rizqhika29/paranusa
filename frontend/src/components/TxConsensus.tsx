"use client";
// Consensus proof for a finalized tx: result, rounds, validator votes,
// leader verdict + explorer link. Answers "what just happened on-chain?".
import { useEffect, useState } from "react";
import { useApp } from "@/state/AppContext";
import { NETWORKS, type NetworkKey } from "@/lib/config";
import { readOnlyClient } from "@/lib/genlayer";
import { shortHash } from "@/lib/format";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function firstLeader(tx: any): any {
  const r = tx?.consensus_data?.leader_receipt;
  if (Array.isArray(r) && r.length > 0) return r[0];
  const lr = tx?.last_round;
  if (lr && Array.isArray(lr.leader_receipt) && lr.leader_receipt.length > 0)
    return lr.leader_receipt[0];
  return null;
}

function voteCounts(tx: unknown): { agree: number; idle: number; other: number } {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const t = tx as any;
  const names: string[] =
    t?.last_round?.validator_votes_name ??
    (t?.consensus_data?.votes ? Object.values(t.consensus_data.votes) : []);
  let agree = 0, idle = 0, other = 0;
  for (const v of names.map((x) => String(x).toLowerCase())) {
    if (v === "agree") agree++;
    else if (v === "idle") idle++;
    else other++;
  }
  return { agree, idle, other };
}

export default function TxConsensus({ hash, network }: { hash: string; network: NetworkKey }) {
  const { pushToast } = useApp();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [tx, setTx] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setErr("");
      // Retry a few times — fresh txs may not be indexed yet.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let last: any = null;
      for (let i = 0; i < 6 && !cancelled; i++) {
        try {
          last = await readOnlyClient(network).getTransaction({ hash });
          if (last) break;
        } catch (e) {
          last = null;
          if (i === 5) setErr(e instanceof Error ? e.message : String(e));
        }
        await new Promise((r) => setTimeout(r, 8000));
      }
      if (!cancelled) {
        setTx(last);
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [hash, network]);

  const url = NETWORKS[network].explorerTx(hash);

  if (loading) return <p className="muted">Reading consensus proof…</p>;
  if (err && !tx) return <div className="alert alert-err" style={{ marginBottom: 0 }}>Could not load proof: {err}</div>;
  if (!tx) return null;

  const votes = voteCounts(tx);
  const leader = firstLeader(tx);
  const cd = leader?.calldata;
  let verdict: { trigger_met?: boolean; measured_value?: string } | null = null;
  try {
    const raw = typeof cd === "string" ? cd : cd?.readable ?? cd?.calldata ?? "";
    const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (parsed && typeof parsed === "object") verdict = parsed;
  } catch {
    /* not JSON — skip */
  }
  const execStatus = leader?.result?.status ?? leader?.execution_result ?? "";
  const payload =
    typeof leader?.result?.payload === "string" ? leader.result.payload : "";

  return (
    <div>
      <div className="kv"><span className="k">Consensus</span><span className="v">{String(tx.result_name ?? "—")}</span></div>
      <div className="kv"><span className="k">Status</span><span className="v">{String(tx.statusName ?? tx.status_name ?? "—")}</span></div>
      <div className="kv"><span className="k">Rounds</span><span className="v">{String(tx.num_of_rounds ?? "—")}</span></div>
      <div className="kv">
        <span className="k">Validator votes</span>
        <span className="v">{votes.agree} agree · {votes.idle} idle{votes.other ? ` · ${votes.other} other` : ""}</span>
      </div>
      {verdict && (verdict.trigger_met !== undefined || verdict.measured_value) && (
        <div className="kv">
          <span className="k">Leader verdict</span>
          <span className="v">
            trigger {verdict.trigger_met ? "MET" : "not met"}
            {verdict.measured_value ? ` · measured ${verdict.measured_value}` : ""}
          </span>
        </div>
      )}
      {execStatus && execStatus !== "return" && (
        <div className="kv"><span className="k">Execution</span><span className="v">{String(execStatus)}{payload ? ` — ${payload}` : ""}</span></div>
      )}
      <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center" }}>
        {url && (
          <a className="tx-hash" href={url} target="_blank" rel="noreferrer">
            Full proof in explorer: {shortHash(hash)} ↗
          </a>
        )}
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => {
            pushToast({ tone: "info", title: "Hash copied", message: hash });
            navigator.clipboard.writeText(hash).catch(() => undefined);
          }}
        >
          Copy hash
        </button>
      </div>
    </div>
  );
}
