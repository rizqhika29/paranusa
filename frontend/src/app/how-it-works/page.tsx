import Link from "next/link";
import { SectionHeading } from "@/components/ui";

export default function HowItWorks() {
  return (
    <div className="wrap">
      <section className="section">
        <SectionHeading
          kicker="Documentation"
          title="How ParaNusa works"
          desc="From raw data to payout — who judges, what is agreed on, and what happens on failure."
        />

        <div className="card" style={{ marginBottom: 16 }}>
          <h3>1 · Policy lifecycle</h3>
          <div className="code">
            fund_pool() [payable, insurer]{"\n"}
            → create_policy(id, lat, lon, location, disaster, threshold, payout) [payable, premium]{"\n"}
            → assess_claim(id) [non-deterministic: web + LLM + consensus]{"\n"}
            → claim_payout(id) [GEN transfer to holder if trigger_met]{"\n"}
            → cancel_policy(id) [owner / holder, before payout]{"\n"}
            → withdraw_surplus(amount) [owner only, surplus above locked payouts]
          </div>
          <p className="muted">
            Assessment (<span className="code">assess</span>) and payment (
            <span className="code">claim</span>) are deliberately separated. This is
            the human-in-the-loop pattern GenLayer recommends for critical
            operations: no automatic transfers inside AI functions.
          </p>
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <h3>2 · Inside assess_claim</h3>
          <div className="steps">
            <div className="step">
              <div>
                <h4>Fetch stable data</h4>
                <p className="muted" style={{ margin: 0 }}>
                  Drought/flood: <span className="code">api.open-meteo.com … past_days=30/7</span>.
                  Earthquake: <span className="code">earthquake.usgs.gov … maxradiuskm=200</span>.
                  Chosen because they are free, keyless, and return stable JSON across requests.
                </p>
              </div>
            </div>
            <div className="step">
              <div>
                <h4>Compute programmatically (grounding)</h4>
                <p className="muted" style={{ margin: 0 }}>
                  Rainfall totals are summed in code; max magnitude is taken from
                  GeoJSON. The number is injected into the prompt as ground truth —
                  the LLM is forbidden from doing its own math, so it cannot hallucinate.
                </p>
              </div>
            </div>
            <div className="step">
              <div>
                <h4>LLM reports the number, the contract decides</h4>
                <p className="muted" style={{ margin: 0 }}>
                  The LLM returns only <span className="code">measured_value</span> +{" "}
                  <span className="code">evidence</span>. The verdict (
                  <span className="code">trigger_met</span>) is computed
                  deterministically by the contract from the agreed measurement —
                  the model cannot force a payout, even if it claims otherwise.
                </p>
              </div>
            </div>
            <div className="step">
              <div>
                <h4>Validators verify independently</h4>
                <p className="muted" style={{ margin: 0 }}>
                  Each validator repeats the fetch + LLM itself, then compares only{" "}
                  <span className="code">trigger_met</span> (must match exactly) and{" "}
                  <span className="code">measured_value</span> within tolerance
                  (rain ±2 mm, magnitude ±0.3). Proof wording may differ — what is
                  agreed on is the decision.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <h3>3 · Contract error taxonomy</h3>
          <p className="muted">The UI translates these prefixes into suggested actions:</p>
          <div className="kv"><span className="k">[EXPECTED]</span><span className="v">business-logic error — fix the input, do not blindly retry</span></div>
          <div className="kv"><span className="k">[EXTERNAL]</span><span className="v">API 4xx / broken payload — check the source, try later</span></div>
          <div className="kv"><span className="k">[TRANSIENT]</span><span className="v">timeout / 5xx — safe to retry</span></div>
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <h3>4 · Prompt security</h3>
          <p className="muted" style={{ margin: 0 }}>
            Prompts are built inside the contract. Users only supply coordinates, a
            location name, disaster type, and threshold — no free text is ever
            concatenated into prompts. Extra LLM fields are ignored; only the three
            standard fields are stored (evidence truncated to ≤2000 chars).
          </p>
        </div>

        <div className="card">
          <h3>5 · Reading proof in the explorer</h3>
          <p className="muted">
            Every write produces a transaction hash. In the explorer (Studionet /
            Bradbury) you can see consensus status (ACCEPTED → FINALIZED),
            execution result (must be FINISHED_WITH_RETURN), and fresh policy state
            via <span className="code">get_policy</span>. Never re-submit the same
            hash — track, don&apos;t duplicate.
          </p>
          <Link href="/app" className="btn btn-primary btn-sm">
            Try it in the App →
          </Link>
        </div>
      </section>
    </div>
  );
}
