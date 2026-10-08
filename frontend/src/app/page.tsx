import Link from "next/link";
import { SectionHeading, StatCard, TriggerBadge } from "@/components/ui";
import { DISASTER_META, LOCATION_PRESETS, type DisasterType } from "@/lib/config";

const TRIGGERS: { type: DisasterType; example: string; how: string }[] = [
  {
    type: "drought",
    example: "Grobogan · payout if 30-day rain < 20 mm",
    how: "Open-Meteo 30-day precipitation total is summed programmatically, then the LLM writes a one-sentence proof.",
  },
  {
    type: "flood",
    example: "Jakarta · payout if 7-day rain > 150 mm",
    how: "Built for tidal floods + extreme rain. Thresholds can be tuned per district or watershed.",
  },
  {
    type: "earthquake",
    example: "Cianjur · payout if M ≥ 5.0 within 200 km",
    how: "Maximum magnitude from the USGS catalog (GeoJSON) around the policy point.",
  },
];

export default function Home() {
  return (
    <div className="topo">
      <div className="glow-amber" />
      {/* HERO */}
      <section className="wrap hero">
        <span className="eyebrow">● Live on GenLayer · Studionet & Bradbury</span>
        <h1>
          Disaster insurance that pays <span className="accent">without paperwork.</span>
        </h1>
        <p className="lead">
          ParaNusa is parametric cover for drought, flood, and earthquakes. No
          adjusters, no interpretation disputes — GenLayer AI validators read
          real-world weather and seismic data, reach consensus, and the contract
          sends GEN payouts straight to your wallet.
        </p>
        <div className="hero-cta">
          <Link href="/app" className="btn btn-primary">
            Open the App →
          </Link>
          <Link href="/how-it-works" className="btn btn-ghost">
            How It Works
          </Link>
        </div>
        <div className="hero-meta">
          <div className="item">
            <strong>3</strong>
            <span>covered disaster types</span>
          </div>
          <div className="item">
            <strong>0</strong>
            <span>centralized oracles — reads the web directly</span>
          </div>
          <div className="item">
            <strong>5+</strong>
            <span>AI validators per consensus</span>
          </div>
          <div className="item">
            <strong>~30 min</strong>
            <span>on-chain claim assessment</span>
          </div>
        </div>
      </section>

      {/* TRIGGERS */}
      <section className="wrap section">
        <SectionHeading
          kicker="Coverage"
          title="Three disasters, three measurable triggers"
          desc="Every policy locks one objective trigger + threshold + coordinate. No rubber clauses."
        />
        <div className="grid grid-3">
          {TRIGGERS.map((t) => {
            const meta = DISASTER_META[t.type];
            return (
              <div className="card" key={t.type}>
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 12,
                    display: "grid",
                    placeItems: "center",
                    background: `${meta.color}22`,
                    border: `1px solid ${meta.color}66`,
                    fontSize: 20,
                    marginBottom: 12,
                  }}
                >
                  {t.type === "drought" ? "☀" : t.type === "flood" ? "🌊" : "🌋"}
                </div>
                <h3>{meta.label}</h3>
                <div style={{ marginBottom: 10 }}>
                  <TriggerBadge type={t.type} />
                </div>
                <p className="muted" style={{ margin: "0 0 10px" }}>{t.example}</p>
                <p className="muted" style={{ margin: 0 }}>{t.how}</p>
                <div className="code" style={{ marginTop: 12 }}>{meta.unit}</div>
              </div>
            );
          })}
        </div>
      </section>

      {/* FLOW */}
      <section className="wrap section">
        <SectionHeading
          kicker="Flow"
          title="From policy to payout in 4 steps"
          desc="Assessment and payment are separated — humans stay in control of large funds."
        />
        <div className="grid grid-2">
          <div className="card">
            <div className="steps">
              <div className="step">
                <div>
                  <h4>1 · Fund the liquidity pool</h4>
                  <p className="muted" style={{ margin: 0 }}>
                    Insurers call <span className="code">fund_pool()</span> — GEN is
                    locked in the contract as payout reserve.
                  </p>
                </div>
              </div>
              <div className="step">
                <div>
                  <h4>2 · Create a policy</h4>
                  <p className="muted" style={{ margin: 0 }}>
                    Pick a point + disaster + threshold + payout. Premium is paid via{" "}
                    <span className="code">create_policy()</span>.
                  </p>
                </div>
              </div>
              <div className="step">
                <div>
                  <h4>3 · Assess the claim on-chain</h4>
                  <p className="muted" style={{ margin: 0 }}>
                    <span className="code">assess_claim()</span> fetches
                    Open-Meteo/USGS data, an LLM judges it, validators agree.
                  </p>
                </div>
              </div>
              <div className="step">
                <div>
                  <h4>4 · Claim the payout</h4>
                  <p className="muted" style={{ margin: 0 }}>
                    If the trigger is met, <span className="code">claim_payout()</span>{" "}
                    transfers GEN to the holder. Everything is on the explorer.
                  </p>
                </div>
              </div>
            </div>
          </div>
          <div>
            <div className="card" style={{ marginBottom: 16 }}>
              <h3>Why consensus instead of one oracle?</h3>
              <p className="muted">
                A single feed can be wrong, late, or manipulated. GenLayer appoints
                one Leader to propose a result, then Validators independently repeat
                the measurement. Results are accepted only when the majority agrees —
                with ±2 mm rain and ±0.3 magnitude tolerance for timing drift
                between nodes.
              </p>
              <Link href="/how-it-works" className="btn btn-ghost btn-sm">
                Technical details →
              </Link>
            </div>
            <div className="card">
              <h3>Curated starting points</h3>
              {LOCATION_PRESETS.map((p) => (
                <div className="kv" key={p.id}>
                  <span className="k">{p.name}</span>
                  <span className="v">
                    {p.lat}, {p.lon} · {p.threshold} {p.unit}
                  </span>
                </div>
              ))}
              <div style={{ marginTop: 14 }}>
                <Link href="/app" className="btn btn-primary btn-sm">
                  Create a policy at these points →
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* TRANSPARENCY */}
      <section className="wrap section">
        <SectionHeading
          kicker="Transparency"
          title="Every number is verifiable"
          desc="Pool balance, collected premiums, and payouts live in contract state — read them directly, no login needed."
        />
        <div className="grid grid-3">
          <StatCard label="Pool Balance" value="— GEN" sub="Connect a contract on the App page" />
          <StatCard label="Total Premiums" value="— GEN" sub="Accumulated across all policies" />
          <StatCard label="Total Payouts" value="— GEN" sub="Paid to policy holders" />
        </div>
      </section>

      {/* FAQ */}
      <section className="wrap section faq">
        <SectionHeading kicker="FAQ" title="Frequently asked questions" />
        <details>
          <summary>Is this real, legal insurance?</summary>
          <p>
            ParaNusa is a technical prototype on GenLayer testnets using valueless
            test GEN. Production would need a legal entity, licensing, and audits —
            this contract only proves the assessment mechanism.
          </p>
        </details>
        <details>
          <summary>Where does the data come from? Can it be manipulated?</summary>
          <p>
            Drought/flood use Open-Meteo (free, keyless, stable JSON); quakes use the
            USGS catalog. Validators fetch data independently — a deviating source
            gets rejected by the majority during consensus.
          </p>
        </details>
        <details>
          <summary>How long does claim assessment take?</summary>
          <p>
            Around 30 minutes on testnet (multi-validator LLM consensus). In the UI,
            you can close the tab — just save the transaction hash and check the
            explorer later.
          </p>
        </details>
        <details>
          <summary>Is the premium lost if no disaster happens?</summary>
          <p>
            Yes — like parametric insurance generally. The premium buys protection
            for the cover period; it is not savings.
          </p>
        </details>
        <div style={{ marginTop: 26 }}>
          <Link href="/app" className="btn btn-primary">
            Start — create your first policy →
          </Link>
        </div>
      </section>
    </div>
  );
}
