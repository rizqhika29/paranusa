"use client";
// ParaNusa dashboard: pool, create policy, track + act on policies, tx history.
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useApp, useContractReady } from "@/state/AppContext";
import {
  DISASTER_META,
  LOCATION_PRESETS,
  NETWORKS,
  type DisasterType,
  type NetworkKey,
} from "@/lib/config";
import {
  policyStatusLabel,
  readOnlyClient,
  readPolicy,
  readPreviewUrl,
  readStats,
  walletClient,
  writeWithLifecycle,
  type PolicyView,
  type PoolStats,
  type TxStage,
} from "@/lib/genlayer";
import { classifyWriteError, genToWei, shortAddress, shortHash, weiToGen } from "@/lib/format";
import { fetchPolicyProofTxs } from "@/lib/explorer";
import { SectionHeading } from "@/components/ui";
import TxTracker from "@/components/TxTracker";
import TxConsensus from "@/components/TxConsensus";

type Tab = "create" | "track" | "pool";

const STAGE_LABEL: Record<TxStage, string> = {
  estimating: "Estimating fees…",
  "awaiting-signature": "Waiting for wallet signature…",
  submitted: "Submitted to consensus…",
  decided: "Validator decision reached…",
  finalizing: "Finalizing…",
  done: "Done",
};

export default function AppDashboard() {
  const app = useApp();
  const { network, contract, wallet, provider, pushToast, trackTx, updateTx } = app;
  const { ready, hint } = useContractReady();
  const [tab, setTab] = useState<Tab>("create");
  const [stats, setStats] = useState<PoolStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  const refreshStats = useCallback(async () => {
    if (!ready) return;
    setStatsLoading(true);
    try {
      const s = await readStats(readOnlyClient(network), contract);
      setStats(s);
    } catch (e) {
      pushToast({
        tone: "error",
        title: "Failed to read pool stats",
        message: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setStatsLoading(false);
    }
  }, [ready, network, contract, pushToast]);

  useEffect(() => {
    refreshStats();
  }, [refreshStats]);

  return (
    <div className="wrap">
      <section className="section">
        <SectionHeading
          kicker="Application"
          title="Manage your protection"
          desc="Create policies, track status, assess claims, and receive payouts — all on-chain and explorer-verifiable."
        />

        {!ready && (
          <div className="alert alert-warn">
            <strong>Contract not connected.</strong> {hint} You can still explore the
            UI, but reads and writes need a valid contract address.
          </div>
        )}

        {/* Pool stats */}
        <div className="grid grid-2" style={{ marginBottom: 16 }}>
          <PoolNumber label="Pool Balance" value={stats ? `${weiToGen(stats.pool_balance)} GEN` : "—"} loading={statsLoading} />
          <PoolNumber label="Locked for Active Policies" value={stats ? `${weiToGen(stats.total_locked)} GEN` : "—"} loading={statsLoading} />
          <PoolNumber label="Total Premiums In" value={stats ? `${weiToGen(stats.total_premiums)} GEN` : "—"} loading={statsLoading} />
          <PoolNumber label="Total Payouts Out" value={stats ? `${weiToGen(stats.total_payouts)} GEN` : "—"} loading={statsLoading} />
        </div>
        <div style={{ marginBottom: 16, display: "flex", gap: 10, alignItems: "center" }}>
          <button className="btn btn-ghost btn-sm" onClick={refreshStats} disabled={!ready || statsLoading}>
            {statsLoading ? "Loading…" : "↻ Refresh"}
          </button>
          {stats && (
            <span className="muted">
              {stats.policy_count} policies · owner {shortAddress(stats.owner)}
            </span>
          )}
        </div>

        <div className="tabs">
          <button className={tab === "create" ? "active" : ""} onClick={() => setTab("create")}>
            ＋ Create Policy
          </button>
          <button className={tab === "track" ? "active" : ""} onClick={() => setTab("track")}>
            ◉ Track & Act
          </button>
          <button className={tab === "pool" ? "active" : ""} onClick={() => setTab("pool")}>
            ◆ Fund Pool
          </button>
        </div>
        <Suspense>
          <TabInit setTab={setTab} />
        </Suspense>

        {tab === "create" && <CreateForm onDone={refreshStats} />}
        {tab === "track" && (
          <Suspense>
            <TrackTab onDone={refreshStats} goTrack={() => setTab("track")} />
          </Suspense>
        )}
        {tab === "pool" && <FundPanel onDone={refreshStats} />}

        <div style={{ marginTop: 20 }}>
          <TxTracker />
        </div>
      </section>
    </div>
  );
}

function PoolNumber({ label, value, loading }: { label: string; value: string; loading: boolean }) {
  return (
    <div className="card">
      <div className="muted" style={{ fontSize: 12.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>
        {label}
      </div>
      <div style={{ fontSize: 26, fontWeight: 800, marginTop: 6 }}>{loading ? "…" : value}</div>
    </div>
  );
}

/** Best-effort chain switch so writes land on the selected network. */
async function ensureChain(provider: unknown, network: NetworkKey): Promise<void> {
  try {
    const req = provider as {
      request: (a: { method: string; params?: unknown }) => Promise<unknown>;
    };
    if (!req || typeof req.request !== "function") return;
    await req.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: `0x${NETWORKS[network].chainId.toString(16)}` }],
    });
  } catch {
    /* user may switch manually — continue anyway */
  }
}

/** Generic write runner: lifecycle + tracking + toasts + explorer links. */
async function runWrite(opts: {
  app: ReturnType<typeof useApp>;
  label: string;
  call: { functionName: string; args: unknown[]; value?: bigint };
  successTitle: string;
  successMessage: string;
  policyId?: string;
  onDone?: () => void;
  onStarted?: () => void;
}): Promise<string | null> {
  const { app, label, call, successTitle, successMessage, policyId, onDone, onStarted } = opts;
  const { network, contract, wallet, provider, pushToast, trackTx, updateTx } = app;
  if (!wallet || !provider) {
    pushToast({ tone: "error", title: "Wallet not connected", message: "Connect a wallet first to submit writes." });
    return null;
  }
  await ensureChain(provider, network);
  const id = trackTx({ label, hash: null, stage: "estimating", ok: null, network, policyId });
  onStarted?.();
  try {
    const client = walletClient(network, wallet, provider);
    try {
      await client.connect(network);
    } catch {
      /* continue — some setups need no explicit handshake */
    }
    const { hash } = await writeWithLifecycle(
      client,
      { address: contract, ...call },
      {
        value: call.value,
        onStage: (stage: TxStage, h?: string) =>
          updateTx(id, { stage, hash: h ?? null }),
      }
    );
    updateTx(id, { stage: "done", ok: true, hash });
    const url = NETWORKS[network].explorerTx(hash);
    pushToast({
      tone: "success",
      title: successTitle,
      message: url ? `${successMessage} Proof: ${shortHash(hash)} (click for explorer).` : `${successMessage} Hash: ${hash}`,
      txHash: hash,
    });
    onDone?.();
    return hash;
  } catch (e) {
    const c = classifyWriteError(e);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const maybeHash = (e as any)?.txHash as string | undefined;
    if (maybeHash) {
      // Submitted but confirmation lost: NEVER mark success OR failure.
      // Track as unconfirmed and let the user verify in the explorer.
      updateTx(id, {
        stage: "finalizing",
        ok: null,
        error: `Unconfirmed: submitted as ${shortHash(maybeHash)} but confirmation was lost (${c.title}). Verify in the explorer before retrying.`,
        hash: maybeHash,
      });
      pushToast({
        tone: "error",
        title: `${label} — status unknown`,
        message: `The tx was submitted (${shortHash(maybeHash)}) but confirmation failed. Check the explorer — do not blindly re-submit.`,
        txHash: maybeHash,
      });
      return null;
    }
    updateTx(id, {
      stage: "done",
      ok: false,
      error: `${c.title}: ${c.message}`,
      hash: null,
    });
    pushToast({
      tone: "error",
      title: `${label} — ${c.title}`,
      message: c.retryable ? `${c.message} Safe to try again.` : c.message,
    });
    return null;
  }
}

/* ---------------- CREATE POLICY ---------------- */

function CreateForm({ onDone }: { onDone: () => void }) {
  const app = useApp();
  const { ready } = useContractReady();
  const [presetId, setPresetId] = useState(LOCATION_PRESETS[0].id);
  const preset = useMemo(
    () => LOCATION_PRESETS.find((p) => p.id === presetId) ?? LOCATION_PRESETS[0],
    [presetId]
  );
  const [custom, setCustom] = useState(false);
  const [policyId, setPolicyId] = useState("DRO-GROBOGAN-01");
  const [lat, setLat] = useState(preset.lat);
  const [lon, setLon] = useState(preset.lon);
  const [location, setLocation] = useState(preset.name);
  const [disaster, setDisaster] = useState<DisasterType>(preset.disaster);
  const [threshold, setThreshold] = useState(preset.threshold);
  const [payout, setPayout] = useState("1");
  const [premium, setPremium] = useState("0.01");
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState("");

  useEffect(() => {
    if (!custom) {
      setLat(preset.lat);
      setLon(preset.lon);
      setLocation(preset.name);
      setDisaster(preset.disaster);
      setThreshold(preset.threshold);
    }
  }, [preset, custom]);

  const meta = DISASTER_META[disaster];

  async function submit() {
    setFormErr("");
    if (!ready) return setFormErr("Contract address is not valid yet.");
    if (!policyId.trim() || policyId.length > 64) return setFormErr("Policy ID must be 1–64 characters.");
    const la = Number(lat), lo = Number(lon);
    if (!Number.isFinite(la) || !Number.isFinite(lo) || Math.abs(la) > 90 || Math.abs(lo) > 180)
      return setFormErr("Invalid coordinates (lat −90…90, lon −180…180).");
    if (!Number.isFinite(Number(threshold))) return setFormErr("Threshold must be a number.");
    let payoutWei: bigint, premiumWei: bigint;
    try {
      payoutWei = genToWei(payout);
      premiumWei = genToWei(premium);
    } catch (e) {
      return setFormErr(e instanceof Error ? e.message : String(e));
    }
    if (payoutWei <= BigInt(0)) return setFormErr("Payout must be greater than 0.");
    setBusy(true);
    const pid = policyId.trim();
    const hash = await runWrite({
      app,
      label: `Create policy ${pid}`,
      policyId: pid,
      call: {
        functionName: "create_policy",
        args: [pid, lat.trim(), lon.trim(), location.trim(), disaster, threshold.trim(), payoutWei],
        value: premiumWei,
      },
      successTitle: "Policy issued",
      successMessage: `Policy ${pid} is active. Save its ID for tracking.`,
      onDone,
    });
    if (hash) app.rememberPolicy(pid, app.wallet ?? "");
    setBusy(false);
  }

  return (
    <div className="grid grid-2">
      <div className="card">
        <h3>New policy form</h3>
        <div className="field">
          <label>Curated point</label>
          <select className="select" value={presetId} onChange={(e) => { setPresetId(e.target.value); setCustom(false); }} disabled={custom}>
            {LOCATION_PRESETS.map((p) => (
              <option key={p.id} value={p.id}>{p.name} — {DISASTER_META[p.disaster].label}</option>
            ))}
          </select>
          <span className="hint">{preset.blurb}</span>
        </div>
        <label className="muted" style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 14 }}>
          <input type="checkbox" checked={custom} onChange={(e) => setCustom(e.target.checked)} />
          Manual coordinates (outside presets)
        </label>
        <div className="field">
          <label>Policy ID <span className="req">*</span></label>
          <input className="input" value={policyId} onChange={(e) => setPolicyId(e.target.value)} placeholder="DRO-GROBOGAN-01" spellCheck={false} />
          <span className="hint">Unique, max 64 chars. Used for tracking & claims.</span>
        </div>
        <div className="row-2">
          <div className="field">
            <label>Latitude <span className="req">*</span></label>
            <input className="input" value={lat} onChange={(e) => setLat(e.target.value)} disabled={!custom} />
          </div>
          <div className="field">
            <label>Longitude <span className="req">*</span></label>
            <input className="input" value={lon} onChange={(e) => setLon(e.target.value)} disabled={!custom} />
          </div>
        </div>
        <div className="field">
          <label>Location name</label>
          <input className="input" value={location} onChange={(e) => setLocation(e.target.value)} disabled={!custom} />
        </div>
        <div className="row-2">
          <div className="field">
            <label>Disaster type <span className="req">*</span></label>
            <select className="select" value={disaster} onChange={(e) => setDisaster(e.target.value as DisasterType)} disabled={!custom}>
              <option value="drought">Drought</option>
              <option value="flood">Flood</option>
              <option value="earthquake">Earthquake</option>
            </select>
          </div>
          <div className="field">
            <label>Threshold <span className="req">*</span></label>
            <input className="input" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
            <span className="hint">{meta.unit}</span>
          </div>
        </div>
        <div className="row-2">
          <div className="field">
            <label>Payout (GEN) <span className="req">*</span></label>
            <input className="input" value={payout} onChange={(e) => setPayout(e.target.value)} inputMode="decimal" />
          </div>
          <div className="field">
            <label>Premium (GEN)</label>
            <input className="input" value={premium} onChange={(e) => setPremium(e.target.value)} inputMode="decimal" />
            <span className="hint">Sent as transaction value.</span>
          </div>
        </div>
        {formErr && <div className="alert alert-err" style={{ marginBottom: 12 }}>{formErr}</div>}
        <button className="btn btn-primary" onClick={submit} disabled={busy || !ready}>
          {busy ? "Processing…" : "Issue Policy →"}
        </button>
        {!app.wallet && <p className="muted">A connected wallet is required to submit.</p>}
      </div>
      <div>
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Protection summary</h3>
          <div className="kv"><span className="k">Disaster</span><span className="v">{meta.label}</span></div>
          <div className="kv"><span className="k">Point</span><span className="v">{lat}, {lon}</span></div>
          <div className="kv"><span className="k">Payout condition</span><span className="v">{threshold} {meta.unit}</span></div>
          <div className="kv"><span className="k">Data source</span><span className="v">{meta.source}</span></div>
          <div className="kv"><span className="k">Tolerance</span><span className="v">{meta.tolerance}</span></div>
        </div>
        <div className="alert alert-info" style={{ marginBottom: 0 }}>
          <strong>Fee note.</strong> Besides the premium, your wallet needs GEN for
          consensus fees (auto-estimated before submit). Total required = premium +
          fee deposit.
        </div>
      </div>
    </div>
  );
}

/* ---------------- TRACK & ACT ---------------- */

// Deep-link helpers: /app?tab=track&policy=ID opens the track tab pre-loaded
// (used by the Profile page).
function TabInit({ setTab }: { setTab: (t: Tab) => void }) {
  const params = useSearchParams();
  useEffect(() => {
    const t = params.get("tab");
    if (t === "track" || t === "create" || t === "pool") setTab(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}

// Deep-link entry: /app?policy=ID opens the track tab pre-loaded.
function TrackTab({ onDone, goTrack }: { onDone: () => void; goTrack: () => void }) {
  const params = useSearchParams();
  const pid = params.get("policy") ?? undefined;
  useEffect(() => {
    goTrack();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <TrackPanel key={pid ?? "track"} onDone={onDone} initialId={pid} />;
}

function TrackPanel({ onDone, initialId }: { onDone: () => void; initialId?: string }) {
  const app = useApp();
  const { network, contract, pushToast, recentPolicies, rememberPolicy, txs } = app;
  const { ready } = useContractReady();
  const [qid, setQid] = useState("");
  const [policy, setPolicy] = useState<PolicyView | null>(null);
  const [sourceUrl, setSourceUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [lookupErr, setLookupErr] = useState("");
  const [lastHash, setLastHash] = useState<string | null>(null);
  const [lastLabel, setLastLabel] = useState("");

  async function lookup(id?: string) {
    const pid = (id ?? qid).trim();
    setLookupErr("");
    setLastHash(null);
    if (!ready) return setLookupErr("Contract address is not valid yet.");
    if (!pid) return setLookupErr("Enter a policy ID first.");
    setLoading(true);
    try {
      const p = await readPolicy(readOnlyClient(network), contract, pid);
      setPolicy(p);
      setQid(pid);
      rememberPolicy(pid, p.holder);
      try {
        setSourceUrl(await readPreviewUrl(readOnlyClient(network), contract, pid));
      } catch {
        setSourceUrl("");
      }
    } catch (e) {
      setPolicy(null);
      setSourceUrl("");
      setLookupErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  // Deep link: /app?policy=ID auto-looks-up (used by the Profile page).
  useEffect(() => {
    if (initialId && initialId.trim()) lookup(initialId.trim());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialId]);

  async function act(kind: "assess_claim" | "claim_payout" | "cancel_policy", confirmMsg?: string) {
    if (!policy) return;
    if (confirmMsg && !window.confirm(confirmMsg)) return;
    if (!app.wallet) {
      pushToast({ tone: "error", title: "Wallet not connected", message: "Connect a wallet first to submit this action." });
      return;
    }
    const pid = qid.trim();
    setBusy(kind);
    const actionLabel = kind === "assess_claim" ? "Assess claim" : kind === "claim_payout" ? "Claim payout" : "Cancel policy";
    const hash = await runWrite({
      app,
      label: `${actionLabel} ${pid}`,
      policyId: pid,
      call: { functionName: kind, args: [pid] },
      successTitle: kind === "claim_payout" ? "Payout sent" : kind === "assess_claim" ? "Assessment finalized" : "Policy cancelled",
      successMessage:
        kind === "claim_payout"
          ? "GEN has been transferred to the holder."
          : kind === "assess_claim"
            ? "Consensus result stored. Re-read the policy to see the trigger."
            : "The policy is now inactive.",
      onStarted:
        kind === "assess_claim"
          ? () =>
              pushToast({
                tone: "info",
                title: "Assessment running",
                message: "AI consensus takes a while (~30 min on testnet). You can close this tab — track the hash below.",
              })
          : undefined,
      onDone: async () => {
        onDone();
        await lookup(pid);
      },
    });
    if (hash) {
      setLastHash(hash);
      setLastLabel(actionLabel);
    }
    setBusy(null);
  }

  const st = policy ? policyStatusLabel(policy) : null;

  return (
    <div className="grid grid-2">
      <div className="card">
        <h3>Find a policy</h3>
        <div className="field">
          <label>Policy ID</label>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              className="input"
              value={qid}
              onChange={(e) => setQid(e.target.value)}
              placeholder="DRO-GROBOGAN-01"
              spellCheck={false}
              onKeyDown={(e) => e.key === "Enter" && lookup()}
            />
            <button className="btn btn-primary" onClick={() => lookup()} disabled={loading || !ready}>
              {loading ? "…" : "Search"}
            </button>
          </div>
          {lookupErr && <span className="err">{lookupErr}</span>}
        </div>
        {recentPolicies.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div className="muted" style={{ marginBottom: 6, fontWeight: 700 }}>Recent on this contract</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {recentPolicies.map((rp) => (
                <button key={rp.id} className="btn btn-ghost btn-sm" onClick={() => lookup(rp.id)}>
                  {rp.id}
                </button>
              ))}
            </div>
          </div>
        )}
        {policy && st && (
          <>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
              <span className={`pill pill-${st.tone}`}>{st.text}</span>
            </div>
            <div className="kv"><span className="k">Location</span><span className="v">{policy.location} ({policy.lat}, {policy.lon})</span></div>
            <div className="kv"><span className="k">Holder</span><span className="v" title={policy.holder}>{shortAddress(policy.holder, 8)}</span></div>
            <div className="kv"><span className="k">Threshold</span><span className="v">{policy.threshold}</span></div>
            <div className="kv"><span className="k">Premium</span><span className="v">{weiToGen(policy.premium)} GEN</span></div>
            <div className="kv"><span className="k">Payout</span><span className="v">{weiToGen(policy.payout_amount)} GEN</span></div>
            {policy.assessed && (
              <>
                <div className="kv"><span className="k">Measured</span><span className="v">{policy.measured_value || "—"}</span></div>
                <div className="kv"><span className="k">Trigger</span><span className="v">{policy.trigger_met ? "MET" : "not met"}</span></div>
              </>
            )}
            {sourceUrl && (
              <div className="kv">
                <span className="k">Source data</span>
                <span className="v">
                  <a className="tx-hash" href={sourceUrl} target="_blank" rel="noreferrer">
                    open API response ↗
                  </a>
                </span>
              </div>
            )}
            {policy.evidence && (
              <div style={{ marginTop: 12 }}>
                <div className="muted" style={{ marginBottom: 6, fontWeight: 700 }}>Consensus evidence</div>
                <div className="evidence">{policy.evidence}</div>
              </div>
            )}
            <PolicyProofs policyId={qid.trim()} assessed={policy.assessed} txs={txs} network={network} contract={contract} />
          </>
        )}
      </div>
      <div>
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Policy actions</h3>
          {!policy && <p className="muted" style={{ margin: 0 }}>Find a policy first to unlock actions.</p>}
          {policy && (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <button
                className="btn btn-primary"
                disabled={busy !== null || policy.paid || !policy.active || policy.assessed}
                onClick={() => act("assess_claim")}
                title={policy.assessed ? "Already assessed — result below" : "Run on-chain AI assessment"}
              >
                {busy === "assess_claim"
                  ? "Assessing… (waiting for finality)"
                  : policy.assessed
                    ? "1 · Already Assessed ✓"
                    : "1 · Assess Claim On-Chain"}
              </button>
              <button
                className="btn btn-ghost"
                disabled={busy !== null || !policy.assessed || !policy.trigger_met || policy.paid}
                onClick={() => act("claim_payout")}
              >
                {busy === "claim_payout" ? "Sending…" : "2 · Claim Payout"}
              </button>
              <button
                className="btn btn-danger"
                disabled={busy !== null || policy.paid || !policy.active}
                onClick={() => act("cancel_policy", `Cancel policy ${qid.trim()}?`)}
              >
                {busy === "cancel_policy" ? "Cancelling…" : "Cancel Policy"}
              </button>
              <p className="muted" style={{ margin: 0 }}>
                Payout is enabled only when the policy is <em>assessed</em> and the
                trigger is met. Only the holder or the contract owner can execute.
              </p>
            </div>
          )}
        </div>
        <div className="alert alert-info" style={{ marginBottom: 0 }}>
          <strong>Transparent.</strong> Every action below is recorded as a tx with
          hash + explorer link. Keep your assessment hash — it is your official proof.
        </div>
        {lastHash && (
          <div className="card" style={{ marginTop: 16 }}>
            <h3>What just happened — {lastLabel}</h3>
            <TxConsensus hash={lastHash} network={network} />
          </div>
        )}
      </div>
    </div>
  );
}

/* Proof of what the AI consensus decided for THIS policy: the assess and
   claim transactions bound to the policy ID (persisted across reloads). */
function PolicyProofs({
  policyId,
  assessed,
  txs,
  network,
  contract,
}: {
  policyId: string;
  assessed: boolean;
  txs: ReturnType<typeof useApp>["txs"];
  network: NetworkKey;
  contract: string;
}) {
  const [open, setOpen] = useState(false);
  const [manual, setManual] = useState("");
  const [attached, setAttached] = useState<string[]>([]);
  const [chain, setChain] = useState<{ hash: string; label: string }[]>([]);
  const [chainLoading, setChainLoading] = useState(false);
  const [chainErr, setChainErr] = useState("");

  // On-chain proof: ask the explorer index which assess/claim txs touched
  // THIS policy. Works on any device — no browser storage involved.
  useEffect(() => {
    let cancelled = false;
    setChain([]);
    setChainErr("");
    if (!assessed || !policyId) return;
    setChainLoading(true);
    fetchPolicyProofTxs(network, contract, policyId)
      .then((list) => {
        if (cancelled) return;
        setChain(
          list.map((t) => ({
            hash: t.hash,
            label: `${t.method === "assess_claim" ? "Assess claim" : "Claim payout"} ${policyId}`,
          }))
        );
      })
      .catch((e) => {
        if (!cancelled) setChainErr(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setChainLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [assessed, policyId, network, contract]);
  // Primary: txs explicitly bound to this policy. Fallback: parse the
  // "<Action> <POLICY_ID>" label format of txs tracked before binding existed.
  const related = txs.filter((t) => {
    if (!t.hash || !/assess|claim/i.test(t.label)) return false;
    if (t.policyId === policyId) return true;
    const m = t.label.match(/^(?:Assess claim|Claim payout) (.+)$/i);
    return m !== null && m[1] === policyId;
  });
  const hashes: string[] = [
    ...new Set([...related.map((t) => t.hash as string), ...attached]),
  ];
  // Merge: on-chain index first (works on any device), then local session
  // txs, then manually attached hashes. Dedupe by hash.
  const entries: { hash: string; label: string }[] = [];
  const seen = new Set<string>();
  const push = (hash: string, label: string) => {
    if (hash && !seen.has(hash)) {
      seen.add(hash);
      entries.push({ hash, label });
    }
  };
  for (const c of chain) push(c.hash, `${c.label} · on-chain`);
  for (const t of related) push(t.hash as string, `${t.label} · this browser`);
  for (const h of attached) push(h, "Manual hash");
  const latest = related[0];

  const proofBody = (
    <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 10 }}>
      {entries.map((e) => (
        <div key={e.hash} className="card" style={{ padding: 16 }}>
          <div className="muted" style={{ fontWeight: 700, marginBottom: 6 }}>{e.label}</div>
          <TxConsensus hash={e.hash} network={network} />
        </div>
      ))}
      {latest && latest.ok === false && (
        <p className="muted" style={{ margin: 0 }}>
          Latest action did not finalize — check its error in the tracker below.
        </p>
      )}
    </div>
  );

  return (
    <div style={{ marginTop: 12 }}>
      <div className="muted" style={{ marginBottom: 6, fontWeight: 700 }}>AI consensus proof</div>
      {chainLoading && entries.length === 0 && attached.length === 0 && (
        <p className="muted" style={{ margin: "0 0 8px" }}>Searching on-chain assessment txs…</p>
      )}
      {chainErr && entries.length === 0 && (
        <p className="muted" style={{ margin: "0 0 8px" }}>
          On-chain index unreachable ({chainErr}). Showing browser-tracked txs only.
        </p>
      )}
      {entries.length > 0 ? (
        <>
          <button className="btn btn-ghost btn-sm" onClick={() => setOpen(!open)}>
            {open ? "Hide" : "Show"} AI consensus proof ({entries.length} tx{entries.length > 1 ? "s" : ""})
          </button>
          {open && proofBody}
        </>
      ) : (
        !chainLoading && (
          <>
            <p className="muted" style={{ margin: "0 0 8px" }}>
              No assessment tx found for this policy yet. If it was assessed in
              another session, paste the tx hash to inspect the validator votes:
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                className="input"
                value={manual}
                onChange={(e) => setManual(e.target.value)}
                placeholder="0x…"
                spellCheck={false}
              />
              <button
                className="btn btn-ghost btn-sm"
                disabled={!/^0x[0-9a-fA-F]{64}$/.test(manual.trim())}
                onClick={() => {
                  setAttached((prev) => [manual.trim(), ...prev].slice(0, 3));
                  setManual("");
                  setOpen(true);
                }}
              >
                Inspect
              </button>
            </div>
          </>
        )
      )}
    </div>
  );
}

/* ---------------- FUND POOL ---------------- */
function FundPanel({ onDone }: { onDone: () => void }) {
  const app = useApp();
  const { ready } = useContractReady();
  const [amount, setAmount] = useState("5");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [wAmount, setWAmount] = useState("1");
  const [wBusy, setWBusy] = useState(false);
  const [wErr, setWErr] = useState("");

  async function submit() {
    setErr("");
    if (!ready) return setErr("Contract address is not valid yet.");
    let wei: bigint;
    try {
      wei = genToWei(amount);
    } catch (e) {
      return setErr(e instanceof Error ? e.message : String(e));
    }
    if (wei <= BigInt(0)) return setErr("Amount must be greater than 0.");
    setBusy(true);
    await runWrite({
      app,
      label: `Fund pool with ${amount} GEN`,
      call: { functionName: "fund_pool", args: [], value: wei },
      successTitle: "Pool funded",
      successMessage: `${amount} GEN entered the payout reserve.`,
      onDone,
    });
    setBusy(false);
  }

  async function withdraw() {
    setWErr("");
    if (!ready) return setWErr("Contract address is not valid yet.");
    let wei: bigint;
    try {
      wei = genToWei(wAmount);
    } catch (e) {
      return setWErr(e instanceof Error ? e.message : String(e));
    }
    if (wei <= BigInt(0)) return setWErr("Amount must be greater than 0.");
    setWBusy(true);
    await runWrite({
      app,
      label: `Owner withdraw ${wAmount} GEN`,
      call: { functionName: "withdraw_surplus", args: [wei] },
      successTitle: "Withdrawal sent",
      successMessage: `${wAmount} GEN surplus withdrawn to the owner.`,
      onDone,
    });
    setWBusy(false);
  }

  return (
    <div className="grid grid-2">
      <div className="card">
        <h3>Add pool liquidity</h3>
        <p className="muted">
          Anyone (especially insurers) can top up the reserve. Payouts can only
          execute when the pool balance covers the policy payout.
        </p>
        <div className="field">
          <label>Amount (GEN)</label>
          <input className="input" value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" />
        </div>
        {err && <div className="alert alert-err">{err}</div>}
        <button className="btn btn-primary" onClick={submit} disabled={busy || !ready}>
          {busy ? "Processing…" : "Send to Pool →"}
        </button>
      </div>
      <div className="card">
        <h3>Pool rules</h3>
        <div className="kv"><span className="k">Payout vs balance</span><span className="v">claim fails if the pool is short</span></div>
        <div className="kv"><span className="k">Premiums</span><span className="v">enter the contract on create_policy</span></div>
        <div className="kv"><span className="k">Locked funds</span><span className="v">active-policy payouts cannot be withdrawn</span></div>
        <div className="kv"><span className="k">Withdrawals</span><span className="v">owner-only, surplus above locked total</span></div>
        <div className="field" style={{ marginTop: 12 }}>
          <label>Owner withdraw surplus (GEN)</label>
          <div style={{ display: "flex", gap: 8 }}>
            <input className="input" value={wAmount} onChange={(e) => setWAmount(e.target.value)} inputMode="decimal" />
            <button className="btn btn-ghost" onClick={withdraw} disabled={wBusy || !ready}>
              {wBusy ? "…" : "Withdraw"}
            </button>
          </div>
          {wErr && <span className="err">{wErr}</span>}
        </div>
        <p className="muted" style={{ marginBottom: 0 }}>
          GEN leaves only through proven claim payouts or owner surplus
          withdrawal. Locked payouts are untouchable.
        </p>
      </div>
    </div>
  );
}
