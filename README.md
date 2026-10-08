# 🌋 ParaNusa — Asuransi Parametrik Bencana Alam Nusantara

> **Proteksi drought, banjir, dan gempa yang membayar otomatis berdasarkan data dunia nyata — tanpa adjuster, tanpa sengketa interpretasi, tanpa oracle terpusat.**

[![GenLayer](https://img.shields.io/badge/GenLayer-Studionet-F5A524)](https://studio.genlayer.com/)
[![Contract](https://img.shields.io/badge/contract-0x3FA8...2599-2DD4BF)](https://explorer-studio.genlayer.com/contracts/0x3FA88596a9b88E1Ea81bbD5D90313d9d2C1e2599)
[![Tests](https://img.shields.io/badge/direct--tests-38%20passed-34D399)](#-testing)
[![Frontend](https://img.shields.io/badge/frontend-Next.js_15-black)](./frontend)

**ParaNusa** (Parametrik Nusantara) adalah protokol asuransi parametrik di atas
[GenLayer](https://docs.genlayer.com) — blockchain yang konsensusnya memakai
**validator AI**, bukan sekadar hitungan deterministik. Polis mengunci satu
pemicu objektif (curah hujan / magnitudo) + ambang + titik koordinat. Saat
bencana terjadi, kontrak membaca API cuaca/seismik dunia nyata, panel validator
AI mencapai konsensus, dan payout GEN mengalir langsung ke dompet pemegang polis.

Tidak ada formulir klaim. Tidak ada "sedang kami proses". Data berkata ya → uang jalan.

---

## 🔴 Live di Studionet

| | |
|---|---|
| **Contract** | [`0x3FA88596a9b88E1Ea81bbD5D90313d9d2C1e2599`](https://explorer-studio.genlayer.com/contracts/0x3FA88596a9b88E1Ea81bbD5D90313d9d2C1e2599) |
| **Network** | GenLayer Studionet (chain `61999`) |
| **Frontend** | [`/app`](./frontend) — terhubung otomatis via `.env.production` |

**Rekam jejak uji live (2026-10-08, semua MAJORITY_AGREE):**

| Aksi | Hasil |
|---|---|
| `fund_pool` 5 GEN | Pool terisi (5.15 GEN incl. sisa fee) |
| `create_policy` ×3 | DRO / FLD / EQ-LIVE terbit |
| `assess` drought Grobogan | 59.2 mm vs ambang 20 mm → **False** (+ locality "Guntur"!) |
| `assess` flood Jakarta | 63.4 mm vs ambang 150 mm → **False** (+ locality "Jakarta") |
| `assess` quake Cianjur | **M6.5 vs ambang M5.0 → True** (+ locality "Cugenang"!) |
| `claim_payout` EQ-LIVE | **0.5 GEN terkirim** ke holder (pool 5.15 → 4.65) |
| `claim` saat trigger gagal | Validator AGREE `[EXPECTED] Trigger not met` |
| `cancel_policy`, `withdraw_surplus` | Berhasil, locked 0.5 GEN tetap utuh |

---

## ❓ Kenapa asuransi biasa gagal — dan kenapa parametrik + GenLayer menang

| Asuransi tradisional | ParaNusa |
|---|---|
| Klaim butuh surveyor berminggu-minggu | Penilaian on-chain ±30 menit |
| Klausul karet → sengketa tafsir | Pemicu angka tunggal, verdict deterministik |
| Oracle terpusat (satu feed = satu titik gagal) | 5+ validator ukur ulang independen |
| Uang ngendap, audit susah | Pool, premi, payout, locked — semua terbaca publik |

**Kenapa tidak bisa dibangun di Ethereum biasa?** Smart contract Solidity buta
internet — butuh oracle Chainlink yang terpusat dan mahal. Intelligent Contract
GenLayer (Python, jalan di GenVM) **membaca web + memanggil LLM secara native**,
lalu memaksa para validator AI untuk saling memverifikasi sebelum state berubah.

---

## ⚙️ Cara kerja (4 langkah)

```
fund_pool()                        — insurer mengunci GEN cadangan payout
  → create_policy(...)             — polis terbit, premi masuk, payout TERKUNCI
  → assess_claim(policy_id)         — fetch API + LLM + konsensus validator
  → claim_payout(policy_id)        — GEN mengalir ke holder bila trigger_met
```

### Di dalam `assess_claim` — bedah 4 tahap

1. **Fetch data stabil.** Drought/flood → Open-Meteo
   (`precipitation_sum`, `past_days=30/7`, gratis, tanpa key, JSON stabil).
   Gempa → katalog USGS (GeoJSON, radius 200 km). Bonus: reverse-geocode
   BigDataCloud mengikat koordinat ke nama wilayah (best-effort, masuk evidence).
2. **Hitung programmatic (grounding).** Total hujan dijumlah / magnitudo maks
   diambil **dengan kode**, disuntik ke prompt sebagai ground truth — LLM
   dilarang berhitung sendiri sehingga tidak bisa halusinasi angka.
3. **LLM hanya melapor, kontrak yang memvonis.** Model mengembalikan
   `measured_value` + `evidence` saja. `trigger_met` dihitung kontrak secara
   deterministik (`_decide_trigger`) — **model yang berbohong pun tidak bisa
   memaksa payout** (dibuktikan test adversarial).
4. **Validator setuju independen.** Tiap validator mengulang fetch + LLM
   sendiri, lalu hanya membandingkan angka terukur dalam toleransi
   (hujan ±2 mm, magnitudo ±0.3). Redaksi evidence boleh beda — yang disepakati
   adalah keputusannya.

### Jaring pengaman dana

- **Payout terkunci:** tiap polis aktif mengunci `payout_amount` di `total_locked`.
  Owner hanya bisa withdraw **surplus** di atas kunci (`withdraw_surplus`).
- **Settlement sekali jalan:** flag `paid`, polis nonaktif otomatis, klaim ganda /
  cancel-then-claim ditolak.
- **Assess ≠ bayar:** penilaian dan pembayaran dipisah (human-in-the-loop),
  sesuai anjuran keamanan GenLayer.

---

## ✨ Keunggulan teknis

- 🎯 **Verdict deterministik dari data otoritatif** — bukan dari opini model.
- 🔒 **Anti LLM nakal** — `trigger_met` LLM diabaikan total oleh kontrak.
- 🌍 **Koordinat terikat wilayah independen** — klaim "lokasi X" dicek silang
  ke geocode, bukan percaya begitu saja.
- 💰 **Konservasi dana terbukti** — pool = funded − payout − withdraw, selalu.
- 🧾 **Semua bisa diaudit** — `get_policy` / `get_stats` / `preview_url`
  (URL sumber data!) terbuka tanpa login.
- ⚠️ **Error jujur** — taksonomi `[EXPECTED]` / `[EXTERNAL]` / `[TRANSIENT]`
  diterjemahkan UI menjadi saran aksi, bukan stack trace.
- 🚫 **Tx tidak pernah ganda** — hash yang sudah terbit dilacak, status
  UNCONFIRMED tidak di-mark sukses/gagal buta.

---

## 🗂️ Struktur project

```
paramatic-insurance/
├── contracts/paranusa.py      # Kontrak ParaNusa (9 method: 6 write, 3 view)
├── tests/direct/              # 38 direct-mode tests (mock web + LLM)
├── frontend/                  # Next.js 15 + genlayer-js (landing, how-it-works, app, profile)
├── AGENTS.md                  # Source of truth dev (wajib baca sebelum koding)
└── requirements.txt
```

**Method kontrak:** `fund_pool` · `create_policy` · `assess_claim` ·
`claim_payout` · `cancel_policy` · `withdraw_surplus` (owner) ·
`get_policy` · `get_stats` · `preview_url`.

**Frontend:** landing + `/how-it-works` + `/app` (pool, buat polis, lacak &
aksi, tx tracker + link explorer, handling sukses/gagal) + `/profile`
(riwayat polis per wallet, filter, statistik).

---

## 🚀 Quickstart

### 1. Kontrak (Python 3.12+)

```bash
pip install -r requirements.txt
genvm-lint check contracts/paranusa.py   # harus {"ok":true}
pytest tests/direct/ -v                  # 38 passed, ~1 detik
```

### 2. Frontend

```bash
cd frontend && npm install
npm run dev    # http://localhost:3000  (kontrak live prefill otomatis)
```

Deploy Vercel: import repo, **Root Directory = `frontend`**, deploy —
env live sudah baked via `.env.production`.

### 3. Coba live (butuh wallet + GEN Studionet)

1. Buka `/app` → hubungkan MetaMask (chain Studionet `61999`).
2. Buat polis (preset Grobogan/Karawang/Jakarta/Cianjur tersedia).
3. `Assess` → tunggu konsensus ±30 mnt (hash bisa dilacak di explorer).
4. Trigger met → `Claim`. Tidak met → coba skenario gempa Cianjur.

---

## 🧪 Testing

- **Direct-mode (38 test):** semua method + negative paths — duplikat ID,
  koordinat/threshold ngawur, API 5xx → TRANSIENT, payload malformed,
  USGS kosong, **LLM bohong** (klaim trigger palsu → ditolak),
  garbage measurement (fallback hitungan), cancel-then-claim, guard withdraw,
  konservasi dana, ASCII-guard (loader on-chain tolak non-ASCII!).
- **Live Studionet:** tabel di atas — data + LLM + konsensus beneran.

---

## 🗺️ Roadmap

- [x] Fase 1 — riset + kontrak MVP + test
- [x] Fase 2 — lint hijau + deploy + uji live Studionet
- [x] Fase 3 — frontend (landing, app, profile)
- [ ] **Fase 4 — dispute/challenge:** challenge window + expiry/refund,
      unilateral recovery, authenticated dispute parties, appeal yang
      memvalidasi klaim evidence (bukan reasoning mentah), konsensus persentase
      untuk partial payout. Syarat dari review staff GenLayer.
- [ ] Fase 5 — Bradbury/testnet utama + audit final

---

## 📚 Referensi

- [GenLayer Docs](https://docs.genlayer.com) · [Skills](https://skills.genlayer.com/)
- [GenLayer Project Boilerplate](https://github.com/genlayerlabs/genlayer-project-boilerplate)
- [genlayer-oracles](https://github.com/Usman3801/genlayer-oracles) (pola oracle)
- Aturan main project ini: [`AGENTS.md`](./AGENTS.md) — dibaca sebelum koding.
