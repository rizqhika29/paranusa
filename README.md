# 🌋 ParaNusa — Parametric Disaster Insurance for the Archipelago

> **Drought, flood, and earthquake coverage that pays automatically from real-world data — no adjusters, no interpretation disputes, no centralized oracles.**

[![GenLayer](https://img.shields.io/badge/GenLayer-Studionet-F5A524)](https://studio.genlayer.com/)
[![Contract](https://img.shields.io/badge/contract-0xc683...ccF62-2DD4BF)](https://explorer-studio.genlayer.com/contracts/0xc6837aaa90070729d41c6FC9543A1508902ccF62)
[![Tests](https://img.shields.io/badge/direct--tests-38%20passed-34D399)](#-testing)
[![Frontend](https://img.shields.io/badge/frontend-Next.js_15-black)](./frontend)

**ParaNusa** (Parametrik Nusantara) is a parametric insurance protocol on
[GenLayer](https://docs.genlayer.com) — a blockchain whose consensus runs on
**AI validators**, not just deterministic computation. A policy locks one
objective trigger (rainfall / magnitude) + threshold + coordinate. When
disaster strikes, the contract reads real-world weather and seismic APIs, a
panel of AI validators reaches consensus, and GEN payout flows straight to the
holder's wallet.

No claim forms. No "under review". Data says yes → money moves.

---

## 🔴 Live on Studionet

| | |
|---|---|
| **Contract** | [`0xc6837aaa90070729d41c6FC9543A1508902ccF62`](https://explorer-studio.genlayer.com/contracts/0xc6837aaa90070729d41c6FC9543A1508902ccF62) |
| **Network** | GenLayer Studionet (chain `61999`) |
| **Frontend** | [`/app`](./frontend) — auto-connected via `.env.production` |

**Live test record (assess logic verified 2026-10-08 on the previous revision —
comment-only changes since, behavior identical):** fund 5 GEN, 3 policies,
3 assesses MAJORITY_AGREE (drought 59.2mm False, flood 63.4mm False,
quake M6.5 True + Cugenang locality), 0.5 GEN claim delivered, failed-claim
revert agreed by validators, cancel, withdraw. Fund conservation held.

---

## ❓ Why legacy insurance fails — and why parametric + GenLayer wins

| Traditional insurance | ParaNusa |
|---|---|
| Claims need weeks of surveying | On-chain assessment in ~30 minutes |
| Rubber clauses → interpretation disputes | Single numeric trigger, deterministic verdict |
| Centralized oracle (one feed = single point of failure) | 5+ validators re-measure independently |
| Opaque funds, hard audits | Pool, premiums, payouts, locked — all publicly readable |

**Why can't this be built on plain Ethereum?** Solidity contracts are blind to
the internet — they need centralized, expensive Chainlink oracles. GenLayer
Intelligent Contracts (Python, running on GenVM) **read the web and call LLMs
natively**, then force AI validators to verify each other before state changes.

---

## ⚙️ How it works (4 steps)

```
fund_pool()                        — insurer locks GEN as payout reserve
  → create_policy(...)             — policy issued, premium in, payout LOCKED
  → assess_claim(policy_id)         — API fetch + LLM + validator consensus
  → claim_payout(policy_id)        — GEN flows to holder if trigger_met
```

### Inside `assess_claim` — 4 stages

1. **Fetch stable data.** Drought/flood → Open-Meteo
   (`precipitation_sum`, `past_days=30/7`, free, keyless, stable JSON).
   Quakes → USGS catalog (GeoJSON, 200 km radius). Bonus: BigDataCloud
   reverse-geocoding binds coordinates to a place name (best-effort, into evidence).
2. **Compute programmatically (grounding).** Rainfall totals are summed **in
   code**, max magnitude taken from GeoJSON, injected into the prompt as ground
   truth — the LLM is forbidden from doing its own math, so it cannot
   hallucinate numbers.
3. **The LLM only reports, the contract decides.** The model returns
   `measured_value` + `evidence`. `trigger_met` is computed deterministically
   by the contract (`_decide_trigger`) — **even a lying model cannot force a
   payout** (proven by adversarial tests).
4. **Validators agree independently.** Each validator repeats the fetch + LLM,
   then compares only the measured number within tolerance
   (rain ±2 mm, magnitude ±0.3). Evidence wording may differ — what is agreed
   on is the decision.

### Fund safety nets

- **Locked payouts:** every active policy locks its `payout_amount` in
  `total_locked`. The owner can only withdraw **surplus** above the lock
  (`withdraw_surplus`).
- **One-time settlement:** `paid` flag, auto-deactivation, double-claim /
  cancel-then-claim rejected.
- **Assess ≠ pay:** assessment and payment are separated (human-in-the-loop),
  per GenLayer security guidance.

---

## ✨ Technical highlights

- 🎯 **Deterministic verdict from authoritative data** — not from model opinion.
- 🔒 **Rogue-LLM proof** — the LLM's `trigger_met` is fully ignored by the contract.
- 🌍 **Coordinates bound to independent locality** — "location X" claims are
  cross-checked against geocoding, not taken on faith.
- 💰 **Proven fund conservation** — pool = funded − payouts − withdrawals, always.
- 🧾 **Everything auditable** — `get_policy` / `get_stats` / `preview_url`
  (the data-source URL!) open without login.
- ⚠️ **Honest errors** — `[EXPECTED]` / `[EXTERNAL]` / `[TRANSIENT]` taxonomy
  translated by the UI into suggested actions, not stack traces.
- 🚫 **Never double-submit** — issued hashes are tracked; UNCONFIRMED status is
  never blindly marked success/failure.

---

## 🗂️ Project structure

```
paramatic-insurance/
├── contracts/paranusa.py      # ParaNusa contract (9 methods: 6 write, 3 view)
├── tests/direct/              # 38 direct-mode tests (mocked web + LLM)
├── frontend/                  # Next.js 15 + genlayer-js (landing, how-it-works, app, profile)
├── AGENTS.md                  # Dev source of truth (read before coding)
└── requirements.txt
```

**Contract methods:** `fund_pool` · `create_policy` · `assess_claim` ·
`claim_payout` · `cancel_policy` · `withdraw_surplus` (owner) ·
`get_policy` · `get_stats` · `preview_url`.

**Frontend:** landing + `/how-it-works` + `/app` (pool, create policy, track &
act, tx tracker + explorer links, success/failure handling) + `/profile`
(per-wallet policy history, filters, stats).

---

## 🚀 Quickstart

### 1. Contract (Python 3.12+)

```bash
pip install -r requirements.txt
genvm-lint check contracts/paranusa.py   # must be {"ok":true}
pytest tests/direct/ -v                  # 38 passed, ~1 second
```

### 2. Frontend

```bash
cd frontend && npm install
npm run dev    # http://localhost:3000  (live contract prefilled)
```

Vercel deploy: import the repo, **Root Directory = `frontend`**, deploy —
live env is baked in via `.env.production`.

### 3. Try it live (needs wallet + Studionet GEN)

1. Open `/app` → connect MetaMask (Studionet chain `61999`).
2. Create a policy (Grobogan/Karawang/Jakarta/Cianjur presets included).
3. `Assess` → wait ~30 min for consensus (track the hash in the explorer).
4. Trigger met → `Claim`. Not met → try the Cianjur quake scenario.

---

## 🧪 Testing

- **Direct-mode (38 tests):** every method + negative paths — duplicate IDs,
  garbage coordinates/thresholds, API 5xx → TRANSIENT, malformed payloads,
  empty USGS, **lying LLM** (fake trigger claim → rejected),
  garbage measurement (computation fallback), cancel-then-claim, withdraw
  guards, fund conservation, ASCII-guard (on-chain loader rejects non-ASCII!).
- **Live Studionet:** the table above — real data + real LLM + real consensus.

---

## 🗺️ Roadmap

- [x] Phase 1 — research + MVP contract + tests
- [x] Phase 2 — green lint + Studionet deploy + live tests
- [x] Phase 3 — frontend (landing, app, profile)
- [ ] **Phase 4 — disputes/challenges:** challenge window + expiry/refund,
      unilateral recovery, authenticated dispute parties, appeals that validate
      evidence claims (not raw reasoning), percentage consensus for partial
      payouts. Required by GenLayer staff review.
- [ ] Phase 5 — Bradbury/main testnet + final audit

---

## 📚 References

- [GenLayer Docs](https://docs.genlayer.com) · [Skills](https://skills.genlayer.com/)
- [GenLayer Project Boilerplate](https://github.com/genlayerlabs/genlayer-project-boilerplate)
- [genlayer-oracles](https://github.com/Usman3801/genlayer-oracles) (oracle patterns)
- Project ground rules: [`AGENTS.md`](./AGENTS.md) — read before coding.
