"use client";
// Session transaction history: stages, hash/explorer links, actionable errors,
// and expandable on-chain consensus proof per tx.
import { useState } from "react";
import { useApp } from "@/state/AppContext";
import { NETWORKS } from "@/lib/config";
import { formatTime, shortHash } from "@/lib/format";
import TxConsensus from "@/components/TxConsensus";

const STAGES = ["estimating", "submitted", "decided", "finalizing", "done"] as const;

function stageIndex(stage: string): number {
  const i = STAGES.indexOf(stage as (typeof STAGES)[number]);
  return i === -1 ? 0 : i;
}

export default function TxTracker() {
  const { txs, network } = useApp();
  const explorer = NETWORKS[network].explorerTx;
  const [openId, setOpenId] = useState<number | null>(null);

  if (txs.length === 0) {
    return (
      <div className="card">
        <h3>Transaction history</h3>
        <p className="muted" style={{ margin: 0 }}>
          No transactions this session yet. Every on-chain action (create policy,
          assess claim, claim payout, fund pool) will be recorded here with proof.
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3>Transaction history (this session)</h3>
      <p className="muted">
        Once a hash exists, never re-submit the same action blindly — track it first.
      </p>
      {txs.map((t) => {
        const url = t.hash ? explorer(t.hash) : null;
        return (
          <div key={t.id} className="tx">
            <div className="tx-head">
              <strong>{t.label}</strong>
              <span className="muted">{formatTime(t.time)}</span>
              {t.ok === true && <span className="pill pill-paid">FINAL · SUCCESS</span>}
              {t.ok === false && <span className="pill" style={{ color: "var(--danger)", background: "rgba(248,113,113,.12)" }}>FAILED</span>}
              {t.ok === null && <span className="pill pill-active">PENDING</span>}
              {t.hash && url && (
                <a className="tx-hash" href={url} target="_blank" rel="noreferrer">
                  {shortHash(t.hash)} ↗
                </a>
              )}
              {t.hash && !url && <span className="tx-hash">{shortHash(t.hash)}</span>}
            </div>
            <div className="stage-dots">
              {STAGES.map((s, i) => (
                <span key={s} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <span
                    className={`stage-dot ${i < stageIndex(t.stage) ? "done" : ""} ${i === stageIndex(t.stage) ? "on" : ""}`}
                  />
                  <span>{s}</span>
                  {i < STAGES.length - 1 && <span style={{ margin: "0 4px" }}>·</span>}
                </span>
              ))}
            </div>
            {t.error && <div className="tx-err">{t.error}</div>}
            {t.hash && (
              <div style={{ marginTop: 8 }}>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => setOpenId(openId === t.id ? null : t.id)}
                >
                  {openId === t.id ? "Hide consensus proof" : "Show consensus proof"}
                </button>
                {openId === t.id && (
                  <div style={{ marginTop: 10 }}>
                    <TxConsensus hash={t.hash} network={t.network} />
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
