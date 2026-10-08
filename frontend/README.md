# ParaNusa Frontend

Next.js + `genlayer-js` for ParaNusa (parametric disaster insurance for the archipelago).

## Quick start

```bash
npm install
# .env.local is already filled with the live Studionet contract
npm run dev                  # http://localhost:3000
```

## Live contract (Studionet)

- **ParaNusa:** `0xc6837aaa90070729d41c6FC9543A1508902ccF62`
  ([explorer](https://explorer-studio.genlayer.com/contracts/0xc6837aaa90070729d41c6FC9543A1508902ccF62))
- Wired by default via `.env.local` (`NEXT_PUBLIC_CONTRACT_STUDIONET`).
  Override per-session in the App settings (persisted in localStorage).

## Pages

- `/` — landing: hero, 3 disaster triggers, 4-step flow, curated points, FAQ.
- `/how-it-works` — policy lifecycle, inside `assess_claim`, error taxonomy, prompt security.
- `/app` — dashboard: network + contract, wallet, live pool stats, create policy,
  track & act on policies (assess / claim / cancel), fund pool, tx history.
  Deep link: `/app?tab=track&policy=ID` pre-loads a policy.
- `/profile` — your policies: every policy this wallet created or opened
  (indexed locally per contract), live status, filters, totals, one-click
  open in the App. No ID searching.

## Contract configuration

The network + contract are deployment-pinned (env only) and intentionally
**not editable in the UI** — users always talk to the audited deployment:

```
NEXT_PUBLIC_CONTRACT_STUDIONET=0x…
NEXT_PUBLIC_CONTRACT_BRADBURY=0x…
NEXT_PUBLIC_CONTRACT_LOCALNET=0x…
NEXT_PUBLIC_DEFAULT_NETWORK=studionet
```

## Transaction pattern (per GenLayer docs + live findings)

Every write: `writeContract` → `waitForDecision` → `waitForFinalization` →
`isSuccessful` check (not just ACCEPTED/FINALIZED status). On Studionet, writes
go **without** explicit fee estimation (`estimate*Fees*` needs Studio-only
`sim_*` RPCs; the node assigns fees — same as the CLI). Amounts (`u256`) are
sent as native BigInt; the contract also coerces decimal strings via `_as_u256`.
Errors are classified: user-rejected, [EXPECTED], [EXTERNAL], [TRANSIENT],
insufficient funds, RPC — each with a suggested action. A submitted hash is
never blindly re-submitted; unconfirmed txs stay UNCONFIRMED until the explorer
says otherwise (Studionet / Bradbury).
