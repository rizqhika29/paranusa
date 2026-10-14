# ParaNusa — Information Needed (Steward Verification Pack)

Live contract (current revision): [`0xbCAba0D0F3750e463d41646F93C420A6E35dfa44`](https://explorer-studio.genlayer.com/contracts/0xbCAba0D0F3750e463d41646F93C420A6E35dfa44)
Network: GenLayer Studionet (chain 61999). All txs below are FINALIZED.
Explorer base: `https://explorer-studio.genlayer.com/tx/<hash>`

> Note on payout delivery: pure EOA value-transfers execute without validator
> rounds (child shows 0 rounds / NO_MAJORITY by design — there is nothing to
> vote on). Delivery is proven by recipient-balance change, verified below.

## 1. Full write-method matrix (current contract, all MAJORITY_AGREE)

| Method | Policy | Tx | Result |
|---|---|---|---|
| `fund_pool` 3 GEN | — | `0x4f3c4a37d500390e9781166ef29ac35eca1940ef3155b2cc99e4ec157249fb49` | pool funded |
| `create_policy` | SMOKE-2 | `0x8db06a3f896add1c88b13a88aa77ce31fd4de41df829124238adfd4d56471a2c` | requested (pending) |
| `create_policy` | EQ-PROBE | `0x168416c1516973e7744013e1010a1632c309dd8a1b09634c498c4f355af74f26` | requested |
| `create_policy` | FLD-AGE | `0x7617bd177505f3716794e88f9be568ed715b6e2bedb204c93acf81c086f6ed8e` | requested |
| `approve_policy` 30d | SMOKE-2 | `0x52362cff8507341a2d523c94587a9907beb3db6ad6f4eeb2df232ca3f742eb65` | window set |
| `approve_policy` 30d | EQ-PROBE | `0x751cd3b6d85a56adcd058b6f74c4c27c53d9223cc8d945e5f67971272f18f71c` | window set |
| `approve_policy` 30d | FLD-AGE | `0x8a28b50da41c3b0ab60bddb70574eb98cafaf726c792b8673070276c5bced119` | window set |
| `assess_claim` quake | EQ-PROBE | `0xff755baceb1ad6ce021c2abf1ab8770387c3e2c08edf4e875797e19638fc5c7c` | 0.0, False (real windowed USGS, exact ISO bounds in evidence) |
| `link_proof` | EQ-PROBE | `0x196ca27ea202bd9b0fc76aa7dfeb80b70ca5874d55afa1eb5874da53ac7b0e71` | `assess_tx` readable via `get_policy` |
| `assess_claim` 2nd | EQ-PROBE | `0x125c4aa001d9a9c80682cf0422937fb7465f1066693932a3cc3ea96e12d0e859` | agreed revert `Already assessed (one-time)` |
| `claim_payout` unmet | EQ-PROBE | `0xbddc92913d18b506c4e805dd4789204e06341b62ea316f771f29a9bfadf6fff8` | agreed revert `Trigger not met` |
| `cancel_policy` | EQ-PROBE | `0x23703d4c89a6fac2a36f51325306efda09e0a83287bc71ff33751f00b92544db` | inactive |
| `create_policy` | M-1 | `0x4a6c259ef70e6b87af8ec4b54a26677947d43750c21e24a49a5767ba7c7d8fba` | requested |
| `approve_policy` 30d | M-1 | `0x90a86be3d08fb8d0bcb308ea4d73d63861319cb1911806fc149275b19140fb13` | approved |
| `assess_claim` fresh drought | M-1 | `0x50979094f757c1b1af225d826a7850ea7a745b8055e4ff486fb01ab4e21ba514` | agreed revert `Insufficient in-window observations` (sparse guard live) |
| `cancel_policy` + refund | M-1 | `0xd5552723ca8c1a8354eff0379cf5d573fd863aed279b6baafdd7c47c327aa5ed` | inactive + refunded (`total_refunds` up) |
| `withdraw_surplus` 0.1 | — | `0xd4f32d3c19ef6d867eed725a2c19e0ca5d6ff1f154e2803ed4f293ebca5b73d2` | state success (see §2) |
| `create_policy` | FLD-PAY2 | `0xd39acb6e940e5b30087953345f189f2610223168b42e5237c87f982fc92b7f8e` | requested |
| `approve_policy` 30d | FLD-PAY2 | `0x388238493dad67ce709f97a291598c9908aa40e4e1d96655fb7cf5edce88` | approved, aging for payout demo |

## 2. Actual GEN movement (recipient-balance proof)

Withdraw 0.1 GEN on current contract, tx `0x16d9c8772723534dd7ca0fdebfcf3a1042888f857d54ecdce69fb84646552330`
(child `0x57889a3bf3a11aab81af28d5288911ea73988472de8ca6a896f3ce1b3358c7fe`):

- Owner balance before: `42999999999999999998` wei
- Owner balance after: `43099999999999999998` wei
- **Credited exactly +0.1 GEN.** Pure EOA value moves need no validator
  rounds; the 0-round child status is normal, balance change is the proof.

Prior revision claim (same `_pay_eoa` primitive): EQ-LIVE claim
`0x67c1622b5f315655a43e1deb90c5130b6a575dd62413ecd979a8abbb156fd489`
on `0x3FA88596a9b88E1Ea81bbD5D90313d9d2C1e2599` — pool 5.15 → 4.65 GEN,
`paid=true`.

## 3. Guards proven live (agreed reverts)

- Owner cancelling another holder's active policy → `[EXPECTED] Only holder
  can cancel` (tx `0x5be3e7fb94880be4bc0ca177dae57735a39927fe74d3f0aea739e112236930e0`
  on `0x4Df6BCEBd759477d57678773Fc1F2A8e555D318a`).
- Double assessment, unmet claim, sparse-data assessment, zero-premium
  request, insolvent approval — all covered live above + in 65 direct tests.

## 4. Honestly time-locked (direct-test covered, live pending)

- Full drought payout: needs a 10-day-old coverage window (live window ages
  daily; warp-covered in direct tests).
- Flood payout: FLD-AGE / FLD-PAY2 windows age in ~3–4 days, then assess →
  link → claim → balance proof will be appended here.
- Expiry + post-expiry recovery: needs a past-end window (warp-covered in
  direct tests: payable survives, unassessed refunds + releases, unmet
  releases without refund).

## 5. Conservation (live state, current contract)

`get_stats`: pool 7.55, locked 1.5, premiums 0.25, payouts 0, refunds 0.15 —
every movement accounted across fund / premium / refund / withdraw flows.

## 6. Frontend writes

All dashboard writes use the same `genlayer-js` v1 calls/params as the
script-driven matrix above (identical code path, MetaMask signing instead of
keystore). Reads verified in-browser; writes verified live via scripts.
