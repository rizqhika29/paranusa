# AGENTS.md — Parametric Insurance (Natural Disasters) on GenLayer

> MUST READ BEFORE CODING. This is a long project. All code MUST follow the
> official GenLayer docs patterns (https://docs.genlayer.com). Never invent
> your own API. When in doubt, check the docs first — don't guess.

## 1. Project Identity

- **Name:** ParaNusa — Parametric Insurance for the Archipelago
  (decided by user 2026-10-07; rejected alternatives: SIGAP, TANGGUH,
  PayungBadai, BumiGuard, NusaSafe)
- **Location:** `E:\Project Genlayer\paramatic-insurance`
- **Theme (LOCKED, decided by user 2026-10-07):** Natural Disasters Only.
  No expansion into flight delay / generic events unless the user reopens it.
- **Supported triggers:** `drought`, `flood`, `earthquake` only.
- **Contract language:** Python GenVM (`from genlayer import *`, `class X(gl.Contract)`).
- **Repo language:** English, concise, technical.

## 2. Status & Activity Log (update every session)

### 2026-10-07 — Session 1: Research + Scaffold
- [x] Docs research: introduction, web-access, equivalence-principle, crafting-prompts,
      tooling-setup, storage, prompt-injection, typical-use-cases, value-transfers.
- [x] Reference research: `Usman3801/genlayer-oracles` (weather_insurance.py),
      `thorbh2/sibyl`, `thorbh2/aegis`, SimpleInsurance tutorial.
- [x] Theme decision: Natural Disasters Only (via user question).
- [x] Scaffold: `contracts/paranusa.py`, `tests/direct/test_insurance.py`,
      `README.md`, `requirements.txt`. Passed `py_compile`.
- [ ] Next: lint (`genvm-lint check`), direct tests (`pytest`), Studio deploy,
      Next.js frontend + genlayer-js (awaiting user direction).

### 2026-10-07 — Session 2: Lint + Direct Tests GREEN ✅
- [x] Lint fixes: added `# { "Depends": "py-genlayer:1jb45aa8..." }` header (W010),
      moved `_parse_threshold`/`_validate_coords` to module level (E022).
- [x] `genvm-lint check`: `{"ok":true, methods:8, view:3, write:5, ctor:0}`.
      I200 warning (newer runner available) ignored — old runner pinned on purpose.
- [x] `pytest tests/direct/`: **4 passed** (create, drought, flood, reject-bad-type).
- [x] Test fixes: web mocks use `{"status":200,...}`, LLM mocks use JSON strings.
- [ ] Next: Studio/Studionet deploy + live `assess_claim` test, then frontend.

### 2026-10-07 — Session 3: Rename to ParaNusa ✅
- [x] User picked the name **ParaNusa** (Parametrik Nusantara).
- [x] Rename: `contracts/parametric_insurance.py` -> `contracts/paranusa.py`,
      class `ParametricInsurance` -> `ParaNusa` (+ branding header comment).
- [x] Updated references in `tests/direct/test_insurance.py`, `README.md`, `AGENTS.md`.
- [x] Re-verified: lint `{"ok":true, contract:"ParaNusa"}` + pytest **4 passed**.

### 2026-10-07 — Session 4: ParaNusa Frontend ✅
- [x] Next.js 15 + React 19 + `genlayer-js@2.0.0-rc.1` (docs pattern: estimate ->
      writeContract(+fees) -> waitForDecision -> waitForFinalization -> isSuccessful).
- [x] Pages: `/` landing, `/cara-kerja`, `/aplikasi` (pool, create policy,
      track+act, fund pool, tx tracker). Chains: studionet/bradbury/localnet.
- [x] Classified errors (user-rejected/[EXPECTED]/[EXTERNAL]/[TRANSIENT]/
      balance/RPC) + success toasts + explorer links. Contract via env/localStorage.
- [x] `npm run build` OK, smoke test `/`, `/cara-kerja`, `/aplikasi` = 200.
- [ ] Next: fill `NEXT_PUBLIC_CONTRACT_*` after Studio deploy, live test.

### 2026-10-07 — Session 5: Full English + Audit ✅
- [x] Entire UI in English. Routes: `/cara-kerja` -> `/how-it-works`,
      `/aplikasi` -> `/app`. `lang="en"`, `en-US` dates.
- [x] Audit bugfixes: tx stage order (decided after waitForDecision),
      double assess toast without wallet, automatic chain-switch per write,
      mobile menu (hamburger), TriggerBadge used on trigger cards.
- [x] New features: recent policy IDs (per contract, localStorage), CopyBtn
      (wallet/contract), `preview_url` link (API data source), rememberPolicy
      after successful create/lookup.
- [x] `npm run build` OK, smoke test `/`, `/how-it-works`, `/app` = 200.

### 2026-10-07 — Session 6: Full method test 26/26 ✅
- [x] `pytest tests/direct/`: **26 passed** — all 8 methods + negative paths:
      fund (balance/zero), create (duplicate/type/coords/threshold/payout),
      get (missing), assess drought/flood/earthquake (met + not-met),
      assess 5xx -> [TRANSIENT], full-cycle claim, pre-assess claim,
      failed-trigger claim, double claim, stranger claim, short pool,
      cancel (holder/stranger/already-cancelled), preview_url, aggregate stats.
- [x] Direct-mode finding: `direct_vm.value` does NOT credit `self.balance`
      automatically — pool tests use `direct_vm.deal(contract_addr, amt)`.
      `emit_transfer` in direct mode is fire-and-forget (PostMessage dropped),
      so payout tests assert state (`paid`, `total_payouts`), not balance moves.
- [ ] Next: Studio/Studionet deploy + LIVE `assess_claim` test
      (real web + LLM), fill `NEXT_PUBLIC_CONTRACT_*` in frontend.

### 2026-10-07 — Session 7: Global GenLayer Skills ✅
- [x] Cloned `genlayerlabs/skills`, installed 6 skills to
      `~/.config/opencode/skills/`: write-contract, genlayer-cli, genvm-lint,
      direct-tests, integration-tests, genlayernode (verbatim upstream).
- [x] Registered `genlayer-docs` MCP (remote `https://docs-mcp.genlayer.com/mcp`)
      in `~/.config/opencode/opencode.jsonc`.
- [x] User MUST restart opencode for skills + MCP to load.

### 2026-10-07 — Session 8: Staff-feedback hardening ✅
- [x] Contract: `withdraw_surplus` (owner-only, `total_locked` guard),
      deterministic verdict (`_decide_trigger`, LLM evidence-only),
      best-effort `_fetch_locality` (BigDataCloud → evidence),
      claim rejects inactive policies (closes cancel-then-claim), `paid` checked first.
- [x] `pytest tests/direct/`: **36 passed** (+10 adversarial: lying LLM,
      garbage measurement, malformed payload, empty USGS, locality,
      cancel-then-claim, locked lifecycle, withdraw guards, conservation).
- [x] Frontend: UNCONFIRMED tx status (never blindly marks success/failure),
      Locked card, owner withdraw, how-it-works update.
- [x] Lint `{"ok":true, methods:9}`.
- [ ] Phase 4 requirements (from staff): challenge-expiry/refund, unilateral
      recovery, authenticated dispute parties, appeal without raw reasoning,
      percentage consensus for partial payouts.

### 2026-10-08 — Session 9: Studionet Deploy + Full Live Test ✅
- [x] Account `paranusa-deployer` (`0xdfc3...34f2`), 100 GEN faucet. Keystore in
      `~/.genlayer/keystores/`, password in `.deployer-pass` (NEVER commit).
- [x] **LIVE:** `0xc6837aaa90070729d41c6FC9543A1508902ccF62`
      (deploy tx `0x160d2a4c...`). Explorer: explorer-studio.genlayer.com.
- [x] Verified live: fund 5 GEN, create x3 (DRO/FLD/EQ-LIVE),
      assess x3 (MAJORITY_AGREE: drought 59.2mm False, flood 63.4mm False,
      quake M6.5 True + Cugenang locality!), claim 0.5 GEN (pool 5.15->4.65),
      failed claim ([EXPECTED] agreed), cancel, withdraw 1 GEN. Conservation holds.
- [x] Live findings (IMPORTANT):
  1. Comment directly under the runner header = `invalid_contract` (14 deploys burned).
     Header MUST be immediately followed by code/import. ASCII-guard test exists.
  2. JS clients send u256 as strings -> storage setter crash. Contract now
     coerces via `_as_u256` (string-args tests exist). Direct tests do NOT catch
     this (proxy auto-roundtrips int->u256).
  3. `genlayer-js@2.0.0-rc.1` writes get 0-round NO_MAJORITY on Studionet.
     Use the CLI (bundled 1.1.8, value:0n without fees) or a v1 script + value.
     `estimate*Fees*` needs `sim_*` (Studio-only).
  4. Always check `isSuccessful`/execution, not just FINALIZED (first deploy was
     FINALIZED but `invalid_contract`).
- [x] Filled `NEXT_PUBLIC_CONTRACT_STUDIONET=0xc683...ccF62` in frontend, tested UI.
- [x] `frontend/.env.local` holds the live contract; root + frontend READMEs
      list address + explorer. Fix: fee-less writes when `sim_*` is missing
      (CLI-style fallback). Build OK, 3 pages return 200.
- [ ] Next: end-to-end dashboard test (needs browser wallet + GEN),
      then Phase 4 (disputes/challenges) if requested.

### 2026-10-08 — Session 12: GitHub Push + Vercel Ready ✅
- [x] Repo `rizqhika29/paranusa` (main). `.gitignore` protects
      `.deployer-pass`/`.env*`/pycache/node_modules.
- [x] `frontend/.env.production` holds the live contract (public, safe to commit).
- [ ] Vercel: import repo, **Root Directory = `frontend`**, deploy
      (env already baked via `.env.production`).

### 2026-10-08 — Session 11: Profile page ✅
- [x] Per-wallet policy index in localStorage (`{id, holder, time}`, auto-migrates
      legacy entries) + `forgetPolicy`. Network/contract stay locked.
- [x] `/profile` page: stats (policies/claimable/received), filters
      (all/active/claimable/paid/inactive), policy cards + evidence +
      `Open & Act` button (deep link `/app?tab=track&policy=ID`).
- [x] Track tab supports `?policy=` (auto-lookup) + `?tab=` via Suspense.
      Navbar/footer + mobile menu include Profile.
- [x] Build OK, `/profile` + deep link return 200.
- [ ] Note: on-chain per-holder index needs a redeploy (batch with Phase 4);
      local index is enough for single-browser demos.

### 2026-10-08 — Session 13: Full English + comment-only redeploy ✅
- [x] Everything in English: root README, AGENTS.md, contract comments
      (ASCII-only, verified). User-facing contract strings were already English.
- [x] Redeployed (new address `0xc683...ccF62`) to keep repo/live parity.
      Verified live: fund (plain transfer), create DRO-EN (BigInt args OK),
      get_policy/get_stats. Assess logic byte-identical to the verified
      revision — no 30-min re-assess needed.
- [x] Updated `.env.local`/`.env.production`, both READMEs, session 9 record.
- [ ] Push + Vercel redeploy (env changed).

### 2026-10-08 — Session 10: Storage-pickling warning (benign) ✅
- [x] `Detected pickling storage class... nondet not supported` warning appears
      in validator stderr. Cause: nondet closures capturing `self` (via
      `self._compare_errors`) + `Policy` instances (storage class).
- [x] RULED BENIGN: 3 live assesses reached MAJORITY_AGREE with correct measured
      numbers (59.2mm, 63.4mm, M6.5) — proof validators read & agreed. The warning
      does not break consensus.
- [x] Local hardening (lint OK, 38 passed): `_compare_errors` moved to
      module level, `_assess_*` extract primitives (`lat/lon/loc/threshold`)
      so nondet closures are storage-class-free and `self`-free.
- [ ] NO redeploy for now (zero behavior change). Batch with the next
      functional redeploy. Live contract `0xc683...ccF62` stays valid.

## 3. Architecture (MVP)

```
fund_pool() [payable] — insurer funds GEN liquidity
  -> create_policy(policy_id, lat, lon, location_name, disaster_type, threshold, payout) [payable]
  -> assess_claim(policy_id) [NONDET]
  -> claim_payout(policy_id) [transfer GEN to holder]
  -> cancel_policy / get_policy / get_stats / preview_url
```

- Policy = `@allow_storage @dataclass Policy` in `TreeMap[str, Policy]`.
- Threshold stored as `str`, parsed to `float` inside the contract.
- Payout via `gl.get_contract_at(holder).emit_transfer(value=...)`. NEVER use
  `self.transfer` (old API).
- `assess` and `payout` are SEPARATED (human-in-the-loop, per security docs).

## 4. GENLAYER GOLDEN RULES (do not break!)

### 4.1 New vs old API — use ONLY the new one
| Need | ✅ Correct (2026) | ❌ Wrong / outdated, NEVER use |
|---|---|---|
| Web GET | `gl.nondet.web.get(url)` | `gl.get_webpage`, bare `gl.nondet.web.request` |
| Web render | `gl.nondet.web.render(url, mode='text')` | manual scraping |
| LLM | `gl.nondet.exec_prompt(prompt, response_format="json")` | `gl.exec_prompt` without format |
| Consensus | `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)` | `gl.eq_principle.*`, `eq_principle_prompt_comparative` |
| Error | `gl.vm.UserError("...")` | bare `Exception`, `ValueError` |
| Copy storage into nondet | `gl.storage.copy_to_memory(obj)` | accessing `self.x` directly inside `leader_fn` |
| Balance | `self.balance`, `gl.message.value` (only in `@payable`) | anything else |

### 4.1b Field findings (IMPORTANT — don't touch without reason)
- **Pin the runner:** header MUST be `# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }`.
  The newer `1zr6nqk5...` runner has a new SDK layout (`genlayer/vm` directly, no
  `genlayer/py/get_schema`), so `genvm-linter 0.11.0 validate` fails with E101.
  Ignore the I200 warning about a newer runner.
- **A comment DIRECTLY under the header = `invalid_contract`.** The runner header
  MUST be immediately followed by code/import (blank line OK, comment NOT).
  Found via 14x deploy bisection. The ASCII-guard test exists but doesn't catch
  this — manually review the header on every edit.
- **Web response = `.status`, NOT `.status_code`** on this runner
  (newer docs say `status_code` — that's for the new SDK, don't follow it).
- **Calldata does NOT support `float`.** Every number crossing the nondet boundary
  (`exec_prompt` returns, `leader_fn` returns) MUST be `bool`/`int`/`str`.
  Standard pattern: the LLM returns `measured_value` as a **string** (`"5.0"`),
  the contract parses via `float(...)` for tolerance comparison.
  LLM mocks in tests must also use strings, not JSON numbers.
- **u256 args from JS arrive as `str`.** The storage setter crashes
  (`str has no to_bytes`). The contract coerces via `_as_u256` on all u256
  entries (payout, withdraw). Direct tests don't catch this — string-args
  tests are mandatory. The frontend sends native BigInt.
- **`@staticmethod` helpers inside the Contract class are FORBIDDEN** (E022).
  Put pure helpers at module level.

### 4.2 Storage
- Persistent fields MUST be declared in the class body with type annotations.
- `dict` -> `TreeMap[K, V]`, `list` -> `DynArray[T]`, bare `int` FORBIDDEN -> `u256`/`i32`/`bigint`.
- Generics must be complete: `TreeMap[str, Policy]` ✅, `TreeMap` ❌.
- Storage dataclasses REQUIRE `@allow_storage`.
- Never store raw web bodies / long LLM reasoning. Store only:
  `trigger_met: bool`, `measured_value`, `evidence` (truncated to ≤2000 chars).

### 4.3 Consensus patterns (from equivalence-principle + crafting-prompts)
1. **Always return JSON + `response_format="json"`.** Define the schema in the prompt.
2. **Extract stable fields.** Never return timestamps, view counts, cache headers.
3. **Compare derived status, not raw data.** Validators only match
   `trigger_met` (+ numeric tolerance), not `evidence`/`analysis` text.
4. **Grounding:** compute numbers programmatically (rain sums, max magnitude),
   inject into the prompt as ground truth. Never let the LLM do raw math.
5. **Validators must verify independently** (re-run `leader_fn` + compare).
   A validator that only checks JSON shape is NOT VALID — it breaks consensus.
6. Project-standard tolerances: rain ±2.0 mm, magnitude ±0.3.
7. Error prefixes: `[EXPECTED]` (business logic, must match exactly),
   `[EXTERNAL]` (API 4xx/broken payload), `[TRANSIENT]` (timeout/5xx, retryable).
   The `_compare_errors` helper already exists in the contract — keep using it.

### 4.4 Prompt injection (security-and-best-practices)
- Prompts are built INSIDE the contract. Users only supply: lat, lon, place name,
  disaster_type, threshold. Never concatenate free-form user text into prompts.
- LLM output is restricted to fixed-field JSON. Ignore any extra LLM fields.
- Large payouts must flow `assess` -> human review -> `claim_payout`.
  Never auto-transfer inside `leader_fn`.

### 4.5 Official project data sources
- Drought/flood: `https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=precipitation_sum&past_days=30|7&timezone=auto`
  (free, keyless, stable JSON).
- Earthquake: `https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&latitude={lat}&longitude={lon}&maxradiuskm=200&minmagnitude=4&limit=20&orderby=magnitude`
- No keyed / login / heavy-HTML APIs for the MVP.
- No `datetime.now()` for time windows — use `past_days` / `limit+orderby`.

## 5. Standard Workflow (tooling-setup)

```bash
# 1. Lint — mandatory before testing
genvm-lint check contracts/paranusa.py

# 2. Direct tests — fast, serverless (mocked web + llm)
pytest tests/direct/ -v

# 3. Sim / local (Docker needed for Studio)
glsim --port 4000 --validators 5
# or: genlayer up  -> Studio http://localhost:8080

# 4. Integration tests
gltest tests/integration/ -v -s --network localnet   # or studionet / testnet_bradbury

# 5. Fast manual deploy
# studio.genlayer.com -> paste contract -> Deploy (empty constructor)
```

- Direct-test mocks: `direct_vm.mock_web(regex_url, {...})`,
  `direct_vm.mock_llm(regex_prompt, json_string)`, close with `clear_mocks()`.
- Frontend: Next.js + `genlayer-js` (`readContract`, `writeContract({value})`,
  `waitForFinalization`). See `developers/decentralized-applications/*`.

## 6. Roadmap

- **Phase 1 (DONE):** research + MVP contract + direct tests + README.
- **Phase 2 (DONE):** green lint + Studionet deploy + live `assess_claim` tests.
- **Phase 3 (DONE):** frontend (create policy, assess, claim, status views, profile).
- **Phase 4 (NEXT):** hardening a la Aegis/Sibyl — challenge window, appeal,
  reputation, audit trail. Plus: English comments + on-chain holder index
  (batch with the required redeploy).
- **Phase 5:** Bradbury testnet (chain 4221), final docs.

## 7. Reference Test Coordinates (Indonesia)

- Karawang drought: `-6.3`, `107.3`, threshold `20.0`
- Grobogan drought: `-7.0`, `110.6`, threshold `20.0`
- Jakarta flood: `-6.2`, `106.8`, threshold `150.0`
- Cianjur earthquake: `-6.8`, `107.1`, threshold `5.0`

## 8. Mandatory References (do not delete)

- Docs: https://docs.genlayer.com/developers/intelligent-contracts/introduction
- Web access: .../features/web-access
- Equivalence: .../equivalence-principle
- Prompts: .../crafting-prompts
- Storage: .../storage
- Security: .../security-and-best-practices/prompt-injection
- Value transfers: .../features/value-transfers
- Use cases: /understand-genlayer-protocol/typical-use-cases
- Boilerplate: https://github.com/genlayerlabs/genlayer-project-boilerplate
- Oracle example: https://github.com/Usman3801/genlayer-oracles

## 9. How To Update This File

- Every session: add a dated entry in §2, move Phase checklists in §6.
- Every user decision (theme, scope, API): record in §1/§4 + date.
- This file + the contract are the source of truth. README = user-facing summary.
