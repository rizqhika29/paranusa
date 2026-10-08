"use client";
// Profile: every policy this wallet ever touched (indexed locally per
// contract), with live status, filters, and one-click actions.
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useApp, useContractReady } from "@/state/AppContext";
import { shortAddress, weiToGen } from "@/lib/format";
import {
  policyStatusLabel,
  readOnlyClient,
  readPolicy,
  type PolicyView,
} from "@/lib/genlayer";
import { SectionHeading, StatCard, TriggerBadge } from "@/components/ui";
import CopyBtn from "@/components/CopyBtn";

type Filter = "all" | "active" | "claimable" | "paid" | "inactive";

interface Loaded {
  id: string;
  policy: PolicyView | null;
  error: string;
}

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "active", label: "Active" },
  { key: "claimable", label: "Ready to claim" },
  { key: "paid", label: "Paid out" },
  { key: "inactive", label: "Inactive" },
];

function toneOf(p: PolicyView): string {
  return policyStatusLabel(p).tone;
}

export default function Profile() {
  const app = useApp();
  const { network, contract, wallet, connecting, connectWallet, recentPolicies, forgetPolicy, pushToast } = app;
  const { ready } = useContractReady();
  const [loaded, setLoaded] = useState<Loaded[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");

  const mine = useMemo(() => {
    if (!wallet) return [];
    const w = wallet.toLowerCase();
    const own = recentPolicies.filter((r) => r.holder && r.holder.toLowerCase() === w);
    const unknown = recentPolicies.filter((r) => !r.holder);
    return [...own, ...unknown];
  }, [recentPolicies, wallet]);

  const refresh = useCallback(async () => {
    if (!ready || mine.length === 0) {
      setLoaded([]);
      return;
    }
    setLoading(true);
    const client = readOnlyClient(network);
    const results = await Promise.all(
      mine.map(async (r): Promise<Loaded> => {
        try {
          const policy = await readPolicy(client, contract, r.id);
          return { id: r.id, policy, error: "" };
        } catch (e) {
          return { id: r.id, policy: null, error: e instanceof Error ? e.message : String(e) };
        }
      })
    );
    setLoaded(results);
    setLoading(false);
  }, [ready, mine, network, contract]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const ok = useMemo(() => loaded.filter((l) => l.policy), [loaded]);
  const stats = useMemo(() => {
    let active = 0, claimable = 0, paid = 0, received = 0n;
    for (const l of ok) {
      const p = l.policy as PolicyView;
      const t = toneOf(p);
      if (t === "active") active++;
      if (t === "claimable") claimable++;
      if (p.paid) {
        paid++;
        try {
          received += BigInt(p.payout_amount);
        } catch {
          /* ignore */
        }
      }
    }
    return { total: ok.length, active, claimable, paid, received: received.toString() };
  }, [ok]);

  const visible = useMemo(() => {
    if (filter === "all") return loaded;
    return loaded.filter((l) => {
      if (!l.policy) return filter === "inactive";
      const t = toneOf(l.policy);
      if (filter === "claimable") return t === "claimable";
      if (filter === "paid") return l.policy.paid;
      if (filter === "active") return t === "active";
      return t === "idle";
    });
  }, [loaded, filter]);

  return (
    <div className="wrap">
      <section className="section">
        <SectionHeading
          kicker="Profile"
          title="Your policies"
          desc="Everything this wallet ever created or opened on the connected contract — live status, no searching by ID."
        />

        {!wallet ? (
          <div className="card">
            <h3>Connect your wallet</h3>
            <p className="muted">
              Your policy history is tied to your wallet address. Connect to see
              your coverage at a glance.
            </p>
            <button className="btn btn-primary" onClick={connectWallet} disabled={connecting}>
              {connecting ? "Connecting…" : "Connect Wallet"}
            </button>
          </div>
        ) : (
          <>
            <div className="card" style={{ marginBottom: 16 }}>
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <div>
                  <div className="muted" style={{ fontSize: 12.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>
                    Wallet
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 800 }} title={wallet}>
                    {shortAddress(wallet, 8)}
                  </div>
                </div>
                <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
                  <CopyBtn value={wallet} label="wallet address" />
                  <button className="btn btn-ghost btn-sm" onClick={refresh} disabled={loading}>
                    {loading ? "Loading…" : "↻ Refresh"}
                  </button>
                </div>
              </div>
            </div>

            <div className="grid grid-3" style={{ marginBottom: 16 }}>
              <StatCard label="Policies" value={String(stats.total)} sub={`${stats.active} active`} />
              <StatCard label="Ready to claim" value={String(stats.claimable)} sub="trigger met, payout pending" />
              <StatCard label="Received" value={`${weiToGen(stats.received)} GEN`} sub={`${stats.paid} payout(s)`} />
            </div>

            {mine.length === 0 ? (
              <div className="card">
                <h3>No policies yet</h3>
                <p className="muted">
                  Nothing recorded for this wallet on the connected contract. Create
                  your first policy — it will appear here automatically.
                </p>
                <Link href="/app" className="btn btn-primary btn-sm">
                  Create a policy →
                </Link>
              </div>
            ) : (
              <>
                <div className="tabs">
                  {FILTERS.map((f) => (
                    <button
                      key={f.key}
                      className={filter === f.key ? "active" : ""}
                      onClick={() => setFilter(f.key)}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
                {loading && loaded.length === 0 ? (
                  <p className="muted">Loading policies…</p>
                ) : visible.length === 0 ? (
                  <p className="muted">Nothing in this filter.</p>
                ) : (
                  <div className="grid grid-2">
                    {visible.map((l) => (
                      <PolicyCard
                        key={l.id}
                        entry={l}
                        onForget={() => {
                          forgetPolicy(l.id);
                          pushToast({ tone: "info", title: "Removed", message: `${l.id} removed from this list (on-chain data untouched).` });
                        }}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </>
        )}
      </section>
    </div>
  );
}

function PolicyCard({ entry, onForget }: { entry: Loaded; onForget: () => void }) {
  const { id, policy: p, error } = entry;
  if (!p) {
    return (
      <div className="card">
        <h3 style={{ fontFamily: "var(--mono)", fontSize: 15 }}>{id}</h3>
        <div className="alert alert-err" style={{ marginBottom: 12 }}>Unavailable: {error || "lookup failed"}</div>
        <button className="btn btn-ghost btn-sm" onClick={onForget}>Remove</button>
      </div>
    );
  }
  const st = policyStatusLabel(p);
  return (
    <div className="card">
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <TriggerBadge type={p.disaster_type} />
        <span className={`pill pill-${st.tone}`}>{st.text}</span>
      </div>
      <h3 style={{ fontFamily: "var(--mono)", fontSize: 16 }}>{id}</h3>
      <p className="muted" style={{ margin: "0 0 10px" }}>
        {p.location} ({p.lat}, {p.lon}) · threshold {p.threshold}
      </p>
      <div className="kv"><span className="k">Payout</span><span className="v">{weiToGen(p.payout_amount)} GEN</span></div>
      <div className="kv"><span className="k">Premium</span><span className="v">{weiToGen(p.premium)} GEN</span></div>
      {p.assessed && (
        <div className="kv">
          <span className="k">Measured</span>
          <span className="v">{p.measured_value || "—"}{p.trigger_met ? " · MET" : ""}</span>
        </div>
      )}
      {p.evidence && (
        <div className="evidence" style={{ marginTop: 10, fontSize: 13 }}>
          {p.evidence.length > 220 ? p.evidence.slice(0, 220) + "…" : p.evidence}
        </div>
      )}
      <div style={{ display: "flex", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
        <Link href={`/app?tab=track&policy=${encodeURIComponent(id)}`} className="btn btn-primary btn-sm">
          Open & Act →
        </Link>
        <button className="btn btn-ghost btn-sm" onClick={onForget}>Remove</button>
      </div>
    </div>
  );
}
