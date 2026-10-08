# AGENTS.md — Parametric Insurance (Bencana Alam) di GenLayer

> WAJIB BACA SEBELUM KODING. Project ini panjang. Semua kode HARUS mengikuti pola
> resmi GenLayer docs (https://docs.genlayer.com). Jangan mengarang API sendiri.
> Kalau ragu, cek docs dulu, jangan tebak.

## 1. Identitas Project

- **Nama:** ParaNusa — Parametric Insurance Bencana Alam Nusantara
  (diputuskan user 2026-10-07; opsi lain yang ditolak: SIGAP, TANGGUH,
  PayungBadai, BumiGuard, NusaSafe)
- **Lokasi:** `E:\Project Genlayer\paramatic-insurance`
- **Tema (LOCKED, diputuskan user 2026-10-07):** Bencana Alam Saja.
  Tidak melebar ke flight delay / event generik kecuali user membuka kembali.
- **Trigger yang didukung:** `drought`, `flood`, `earthquake` saja.
- **Bahasa kontrak:** Python GenVM (`from genlayer import *`, `class X(gl.Contract)`).
- **Bahasa komunikasi:** Indonesia, ringkas, teknis.

## 2. Status & Aktivitas (update tiap sesi)

### 2026-10-07 — Sesi 1: Riset + Scaffold
- [x] Riset docs: introduction, web-access, equivalence-principle, crafting-prompts,
      tooling-setup, storage, prompt-injection, typical-use-cases, value-transfers.
- [x] Riset referensi: `Usman3801/genlayer-oracles` (weather_insurance.py),
      `thorbh2/sibyl`, `thorbh2/aegis`, tutorial SimpleInsurance.
- [x] Keputusan tema: Bencana Alam Saja (via tanya user).
- [x] Scaffold: `contracts/paranusa.py`, `tests/direct/test_insurance.py`,
      `README.md`, `requirements.txt`. Lolos `py_compile`.
- [ ] Berikutnya: lint (`genvm-lint check`), direct test (`pytest`), deploy Studio,
      frontend Next.js + genlayer-js (menunggu arahan user).

### 2026-10-07 — Sesi 2: Lint + Direct Test HIJAU ✅
- [x] Fix lint: tambah header `# { "Depends": "py-genlayer:1jb45aa8..." }` (W010),
      pindah `_parse_threshold`/`_validate_coords` ke module-level (E022).
- [x] `genvm-lint check`: `{"ok":true, methods:8, view:3, write:5, ctor:0}`.
      Warning I200 (runner baru tersedia) diabaikan — sengaja pin runner lama.
- [x] `pytest tests/direct/`: **4 passed** (create, drought, flood, reject-bad-type).
- [x] Fix test: mock web pakai `{"status":200,...}`, mock LLM pakai string JSON.
- [ ] Berikutnya: deploy Studio/Studionet + uji `assess_claim` live, lalu frontend.

### 2026-10-07 — Sesi 3: Rename ke ParaNusa ✅
- [x] User pilih nama **ParaNusa** (Parametrik Nusantara).
- [x] Rename: `contracts/parametric_insurance.py` -> `contracts/paranusa.py`,
      class `ParametricInsurance` -> `ParaNusa` (+ header comment branding).
- [x] Update referensi di `tests/direct/test_insurance.py`, `README.md`, `AGENTS.md`.
- [x] Re-verifikasi: lint `{"ok":true, contract:"ParaNusa"}` + pytest **4 passed**.

### 2026-10-07 — Sesi 4: Frontend ParaNusa ✅
- [x] Next.js 15 + React 19 + `genlayer-js@2.0.0-rc.1` (pola docs: estimate ->
      writeContract(+fees) -> waitForDecision -> waitForFinalization -> isSuccessful).
- [x] Halaman: `/` landing, `/cara-kerja`, `/aplikasi` (pool, buat polis,
      lacak+aksi, isi pool, tx tracker). Chain: studionet/bradbury/localnet.
- [x] Error diklasifikasikan (user-rejected/[EXPECTED]/[EXTERNAL]/[TRANSIENT]/
      saldo/RPC) + toast sukses + link explorer. Kontrak via env/localStorage.
- [x] `npm run build` OK, smoke test `/`, `/cara-kerja`, `/aplikasi` = 200.
- [ ] Berikutnya: isi `NEXT_PUBLIC_CONTRACT_*` setelah deploy Studio, uji live.

### 2026-10-07 — Sesi 5: Full English + Audit ✅
- [x] Seluruh UI English. Route: `/cara-kerja` -> `/how-it-works`,
      `/aplikasi` -> `/app`. `lang="en"`, date `en-US`.
- [x] Bugfix audit: urutan stage tx (decided setelah waitForDecision),
      toast ganda assess tanpa wallet, chain-switch otomatis tiap write,
      menu mobile (hamburger), TriggerBadge dipakai di kartu trigger.
- [x] Fitur baru: recent policy IDs (per kontrak, localStorage), CopyBtn
      (wallet/kontrak), link `preview_url` (sumber data API), rememberPolicy
      setelah create/lookup sukses.
- [x] `npm run build` OK, smoke test `/`, `/how-it-works`, `/app` = 200.

### 2026-10-07 — Sesi 6: Full method test 26/26 ✅- [x] `pytest tests/direct/`: **26 passed** — semua 8 method + negative paths:
      fund (saldo/nol), create (duplikat/tipe/koordinat/threshold/payout),
      get (hilang), assess drought/flood/earthquake (met + not-met),
      assess 5xx -> [TRANSIENT], claim full-cycle, claim sebelum-assess,
      claim trigger-gagal, claim ganda, claim orang-asing, pool kurang,
      cancel (holder/asing/sudah-cancel), preview_url, stats agregat.
- [x] Temuan direct-mode: `direct_vm.value` TIDAK menambah `self.balance`
      otomatis — test pool pakai `direct_vm.deal(contract_addr, amt)`.
      `emit_transfer` di direct mode fire-and-forget (PostMessage di-drop),
      jadi test payout assert state (`paid`, `total_payouts`), bukan mutasi saldo.
- [ ] Berikutnya: deploy Studio/Studionet + uji `assess_claim` LIVE
      (web + LLM beneran), isi `NEXT_PUBLIC_CONTRACT_*` di frontend.

### 2026-10-07 — Sesi 7: Skill GenLayer global ✅
- [x] Clone `genlayerlabs/skills`, pasang 6 skill ke
      `~/.config/opencode/skills/`: write-contract, genlayer-cli, genvm-lint,
      direct-tests, integration-tests, genlayernode (verbatim upstream).
- [x] Daftarkan MCP `genlayer-docs` (remote `https://docs-mcp.genlayer.com/mcp`)
      di `~/.config/opencode/opencode.jsonc`.
- [x] User WAJIB restart opencode agar skill + MCP termuat.

### 2026-10-07 — Sesi 8: Staff-feedback hardening ✅
- [x] Kontrak: `withdraw_surplus` (owner-only, guard `total_locked`),
      verdict deterministik (`_decide_trigger`, LLM evidence-only),
      `_fetch_locality` best-effort (BigDataCloud → evidence),
      claim tolak polis nonaktif (tutup cancel-then-claim), cek `paid` dulu.
- [x] `pytest tests/direct/`: **36 passed** (+10 adversarial: LLM bohong,
      garbage measurement, payload malformed, USGS kosong, locality,
      cancel-then-claim, locked lifecycle, withdraw guards, conservation).
- [x] Frontend: status tx UNCONFIRMED (tidak pernah mark sukses/gagal buta),
      kartu Locked, withdraw owner, how-it-works update.
- [x] Lint `{"ok":true, methods:9}`.
- [ ] Fase 4 wajib penuhi (dari staff): challenge-expiry/refund, unilateral
      recovery, authenticated dispute parties, appeal tanpa reasoning mentah,
      consensus persentase bila ada partial payout.

### 2026-10-08 — Sesi 9: Deploy + Full Live Test Studionet ✅
- [x] Akun `paranusa-deployer` (`0xdfc3...34f2`), 100 GEN faucet. Keystore di
      `~/.genlayer/keystores/`, password di `.deployer-pass` (JANGAN commit).
- [x] **LIVE:** `0x3FA88596a9b88E1Ea81bbD5D90313d9d2C1e2599`
      (deploy tx `0x160d2a4c...`). Explorer: explorer-studio.genlayer.com.
- [x] Live terverifikasi: fund 5 GEN, create x3 (DRO/FLD/EQ-LIVE),
      assess x3 (MAJORITY_AGREE: drought 59.2mm False, flood 63.4mm False,
      quake M6.5 True + locality Cugenang!), claim 0.5 GEN (pool 5.15->4.65),
      claim-gagal ([EXPECTED] agreed), cancel, withdraw 1 GEN. Konservasi pas.
- [x] Temuan live (PENTING):
  1. Komentar di bawah header runner = `invalid_contract` (14 deploy hangus).
     Header HARUS langsung diikuti code/import. Test ASCII-guard ada.
  2. JS client kirim u256 sebagai string -> storage setter crash. Kontrak kini
     koersi via `_as_u256` (test string-args ada). Direct test TIDAK menangkap
     ini (proxy roundtrip int->u256 otomatis).
  3. `genlayer-js@2.0.0-rc.1` writes = 0 rounds NO_MAJORITY di Studionet.
     Pakai CLI (bundled 1.1.8, value:0n tanpa fees) atau script v1 + value.
     `estimate*Fees*` butuh `sim_*` (Studio-only).
  4. Selalu cek `isSuccessful`/execution, bukan cuma FINALIZED (deploy pertama
     FINALIZED tapi `invalid_contract`).
- [x] Isi `NEXT_PUBLIC_CONTRACT_STUDIONET=0x3FA8...2599` di frontend, uji UI.
- [x] `frontend/.env.local` terisi kontrak live; README root + frontend
      mencantumkan address + explorer. Fix: write tanpa estimate bila
      `sim_*` tak ada (fallback fee-less ala CLI). Build OK, 3 halaman 200.
- [ ] Berikutnya: uji dashboard end-to-end (butuh wallet browser + GEN),
      lalu Fase 4 (dispute/challenge) bila diminta.

### 2026-10-08 — Sesi 12: Push GitHub + siap Vercel ✅
- [x] Repo `rizqhika29/paranusa` (main). `.gitignore` lindungi
      `.deployer-pass`/`.env*`/pycache/node_modules.
- [x] `frontend/.env.production` terisi kontrak live (public, aman di-commit).
- [ ] Vercel: import repo, **Root Directory = `frontend`**, deploy
      (env sudah baked via `.env.production`).

### 2026-10-08 — Sesi 11: Profile page ✅
- [x] Index polis per wallet di localStorage (`{id, holder, time}`, migrasi
      entri lama otomatis) + `forgetPolicy`. Network/kontrak tetap locked.
- [x] Halaman `/profile`: stats (policies/claimable/received), filter
      (all/active/claimable/paid/inactive), kartu polis + evidence +
      tombol `Open & Act` (deep link `/app?tab=track&policy=ID`).
- [x] Track tab dukung `?policy=` (auto-lookup) + `?tab=` via Suspense.
      Navbar/footer + mobile menu tambah Profile.
- [x] Build OK, `/profile` + deep link 200.
- [ ] Catatan: index on-chain per holder butuh redeploy (batch Fase 4);
      index lokal cukup untuk demo single-browser.

### 2026-10-08 — Sesi 10: Storage-pickling warning (benign) ✅
- [x] Warning `Detected pickling storage class... nondet not supported` muncul
      di stderr validator. Penyebab: closure nondet menangkap `self` (via
      `self._compare_errors`) + instance `Policy` (storage class).
- [x] DINYATAKAN BENIGN: 3 assess live MAJORITY_AGREE + angka terukur benar
      (59.2mm, 63.4mm, M6.5) — bukti validator membaca & setuju. Warning tidak
      menggagalkan konsensus.
- [x] Hardening lokal (lint OK, 38 passed): `_compare_errors` pindah ke
      module-level, `_assess_*` ekstrak primitif (`lat/lon/loc/threshold`)
      sehingga closure nondet bebas storage-class & bebas `self`.
- [ ] TIDAK redeploy sekarang (nol perubahan perilaku). Batch dengan redeploy
      fungsional berikutnya. Live contract `0x3FA8...2599` tetap valid.

## 3. Arsitektur (MVP)

```
fund_pool() [payable] — insurer isi likuiditas GEN
  -> create_policy(policy_id, lat, lon, location_name, disaster_type, threshold, payout) [payable]
  -> assess_claim(policy_id) [NONDET]
  -> claim_payout(policy_id) [transfer GEN ke holder]
  -> cancel_policy / get_policy / get_stats / preview_url
```

- Polis = `@allow_storage @dataclass Policy` di `TreeMap[str, Policy]`.
- Threshold disimpan sebagai `str`, di-parse ke `float` di dalam kontrak.
- Payout via `gl.get_contract_at(holder).emit_transfer(value=...)`. JANGAN pakai
  `self.transfer` (API lama).
- `assess` dan `payout` DIPISAH (human-in-the-loop, sesuai anjuran security docs).

## 4. ATURAN EMAS GENLAYER (jangan dilanggar!)

### 4.1 API baru vs lama — pakai yang BARU saja
| Kebutuhan | ✅ Benar (2026) | ❌ Salah / usang, JANGAN dipakai |
|---|---|---|
| Web GET | `gl.nondet.web.get(url)` | `gl.get_webpage`, `gl.nondet.web.request` tanpa perlu |
| Web render | `gl.nondet.web.render(url, mode='text')` | scraping manual |
| LLM | `gl.nondet.exec_prompt(prompt, response_format="json")` | `gl.exec_prompt` tanpa format |
| Konsensus | `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)` | `gl.eq_principle.*`, `eq_principle_prompt_comparative` |
| Error | `gl.vm.UserError("...")` | `Exception`, `ValueError` polos |
| Copy storage ke nondet | `gl.storage.copy_to_memory(obj)` | akses `self.x` langsung di dalam `leader_fn` |
| Balance | `self.balance`, `gl.message.value` (hanya di `@payable`) | tebakan lain |

### 4.1b Temuan lapangan (PENTING — jangan diutak-atik tanpa alasan)
- **Pin runner:** header HARUS `# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }`.
  Runner baru `1zr6nqk5...` punya layout SDK baru (`genlayer/vm` langsung, tanpa
  `genlayer/py/get_schema`) sehingga `genvm-linter 0.11.0 validate` gagal E101.
  Abaikan warning I200 soal runner baru.
- **Komentar TEPAT di bawah header = `invalid_contract`.** Header runner HARUS
  langsung diikuti code/import (blank line OK, comment TIDAK). Ditemukan via
  14x bisect deploy. Test ASCII-guard ada tapi tidak menangkap ini — review
  manual tiap edit header.
- **Response web = `.status` BUKAN `.status_code`** pada runner ini
  (docs terbaru menulis `status_code`, itu untuk SDK baru — jangan ikut).
- **Calldata TIDAK support `float`.** Semua angka yang melewati batas nondet
  (return `exec_prompt`, return `leader_fn`) HARUS `bool`/`int`/`str`.
  Pola baku: LLM return `measured_value` sebagai **string** (`"5.0"`),
  kontrak parse via `float(...)` untuk perbandingan toleransi.
  Mock LLM di test juga harus pakai string, bukan angka JSON.
- **u256 arg dari JS tiba sebagai `str`.** Storage setter crash
  (`str has no to_bytes`). Kontrak koersi via `_as_u256` di semua entry
  u256 (payout, withdraw). Direct test tidak menangkap ini — test string-args
  wajib ada. Frontend kirim BigInt native.
- **Helper `@staticmethod` di dalam class Kontrak DILARANG** (E022).
  Taruh helper murni di module-level.

### 4.2 Storage
- Field persisten WAJIB deklarasi di body class dengan anotasi tipe.
- `dict` -> `TreeMap[K, V]`, `list` -> `DynArray[T]`, `int` polos DILARANG -> `u256`/`i32`/`bigint`.
- Generic harus full: `TreeMap[str, Policy]` ✅, `TreeMap` ❌.
- Dataclass storage WAJIB `@allow_storage`.
- Jangan simpan body web mentah / reasoning LLM panjang. Simpan hanya:
  `trigger_met: bool`, `measured_value`, `evidence` (dipotong ≤2000 char).

### 4.3 Pola konsensus (dari equivalence-principle + crafting-prompts)
1. **Selalu return JSON + `response_format="json"`.** Definisikan skema di prompt.
2. **Extract stable fields.** Jangan return timestamp, view count, cache header.
3. **Bandingkan derived status, bukan raw data.** Validator hanya cocokkan
   `trigger_met` (+ toleransi angka), bukan teks `evidence`/`analysis`.
4. **Grounding:** hitung angka secara programmatic (sum hujan, max magnitudo),
   suntik ke prompt sebagai ground truth. LLM jangan disuruh hitung mentah.
5. **Validator harus verifikasi independen** (re-run `leader_fn` + bandingkan).
   Validator yang cuma cek format JSON = TIDAK SAH, melanggar konsensus.
6. Toleransi baku project ini: hujan ±2.0 mm, magnitudo ±0.3.
7. Error pakai prefix: `[EXPECTED]` (logika bisnis, harus sama persis),
   `[EXTERNAL]` (API 4xx/payload rusak), `[TRANSIENT]` (timeout/5xx, boleh retry).
   Helper `_compare_errors` sudah ada di kontrak — pakai terus.

### 4.4 Prompt injection (security-and-best-practices)
- Prompt dibangun DI DALAM kontrak. User hanya isi: lat, lon, nama lokasi,
  disaster_type, threshold. Jangan pernah concat deskripsi bebas user ke prompt.
- Output LLM dibatasi JSON dengan field tetap. Abaikan field lain dari LLM.
- Payout besar wajib lewat `assess` -> review manusia -> `claim_payout`.
  Jangan auto-transfer di dalam `leader_fn`.

### 4.5 Data source resmi project
- Drought/flood: `https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=precipitation_sum&past_days=30|7&timezone=auto`
  (gratis, tanpa key, JSON stabil).
- Earthquake: `https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&latitude={lat}&longitude={lon}&maxradiuskm=200&minmagnitude=4&limit=20&orderby=magnitude`
- Jangan pakai API ber-key / login / HTML berat untuk MVP.
- Jangan pakai `datetime.now()` untuk window waktu — pakai `past_days` / `limit+orderby`.

## 5. Workflow Baku (tooling-setup)

```bash
# 1. Lint — wajib sebelum test
genvm-lint check contracts/paranusa.py

# 2. Direct test — cepat, tanpa server (mock web + llm)
pytest tests/direct/ -v

# 3. Sim / lokal (butuh Docker untuk Studio)
glsim --port 4000 --validators 5
# atau: genlayer up  -> Studio http://localhost:8080

# 4. Integration test
gltest tests/integration/ -v -s --network localnet   # atau studionet / testnet_bradbury

# 5. Deploy manual cepat
# studio.genlayer.com -> paste kontrak -> Deploy (constructor kosong)
```

- Mock di direct test: `direct_vm.mock_web(regex_url, {...})`,
  `direct_vm.mock_llm(regex_prompt, json_string)`, tutup dengan `clear_mocks()`.
- Frontend: Next.js + `genlayer-js` (`readContract`, `writeContract({value})`,
  `waitForFinalization`). Lihat `developers/decentralized-applications/*`.

## 6. Roadmap

- **Fase 1 (DONE):** riset + kontrak MVP + direct test + README.
- **Fase 2 (NEXT):** lint + direct test hijau, deploy Studio/Studionet,
  uji `assess_claim` live untuk 1 koordinat per trigger.
- **Fase 3:** frontend (create policy, assess, claim, lihat status).
- **Fase 4:** hardening ala Aegis/Sibyl bila diminta — challenge window, appeal,
  reputasi, audit trail. JANGAN dikerjakan sebelum Fase 2 hijau.
- **Fase 5:** Bradbury testnet (chain 4221), dokumentasi final.

## 7. Contoh Koordinat Uji (Indonesia)

- Karawang drought: `-6.3`, `107.3`, threshold `20.0`
- Grobogan drought: `-7.0`, `110.6`, threshold `20.0`
- Jakarta flood: `-6.2`, `106.8`, threshold `150.0`
- Cianjur earthquake: `-6.8`, `107.1`, threshold `5.0`

## 8. Referensi Wajib (jangan hapus)

- Docs: https://docs.genlayer.com/developers/intelligent-contracts/introduction
- Web access: .../features/web-access
- Equivalence: .../equivalence-principle
- Prompts: .../crafting-prompts
- Storage: .../storage
- Security: .../security-and-best-practices/prompt-injection
- Value transfers: .../features/value-transfers
- Use cases: /understand-genlayer-protocol/typical-use-cases
- Boilerplate: https://github.com/genlayerlabs/genlayer-project-boilerplate
- Contoh oracle: https://github.com/Usman3801/genlayer-oracles

## 9. Cara Update File Ini

- Setiap sesi: tambah entri tanggal di §2, geser checklist Fase di §6.
- Setiap keputusan user (tema, scope, API): catat di §1/§4 + tanggal.
- File ini + kontrak adalah source of truth. README = ringkasan user-facing.
