# ParaNusa — Parametric Insurance Bencana Alam (GenLayer)

Tema: **Bencana Alam Saja** — drought, flood, earthquake.
Kontrak: `contracts/paranusa.py`

## Live di Studionet ✅ (2026-10-08)

- **Contract:** `0x3FA88596a9b88E1Ea81bbD5D90313d9d2C1e2599`
  ([explorer](https://explorer-studio.genlayer.com/contracts/0x3FA88596a9b88E1Ea81bbD5D90313d9d2C1e2599))
- **Hasil uji live:** fund 5 GEN, 3 polis (DRO/FLD/EQ-LIVE), 3 assess
  MAJORITY_AGREE (drought 59.2mm False, flood 63.4mm False,
  quake M6.5 True + locality Cugenang), claim 0.5 GEN, cancel, withdraw.
- **Frontend:** sudah terhubung via `frontend/.env.local`
  (`NEXT_PUBLIC_CONTRACT_STUDIONET`). Buka `/app`, pilih Studionet,
  hubungkan wallet, langsung pakai.

## Alur
```
fund_pool() [payable, owner/insurer]
 -> create_policy(policy_id, lat, lon, location, disaster_type, threshold, payout) [payable, premi]
 -> assess_claim(policy_id) [NONDET: Open-Meteo / USGS + LLM, konsensus validator]
 -> claim_payout(policy_id) [transfer GEN ke holder jika trigger_met]
```

## Threshold
- `drought`: total hujan 30 hari (mm) < threshold. Contoh Grobogan: `"20.0"`
- `flood`: total hujan 7 hari (mm) > threshold. Contoh Jakarta: `"150.0"`
- `earthquake`: magnitudo max radius 200km >= threshold. Contoh Cianjur: `"5.0"`

## Data source (gratis, tanpa API key, JSON stabil)
- Drought/flood: `api.open-meteo.com/v1/forecast?...&daily=precipitation_sum&past_days=30/7`
- Earthquake: `earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&...&maxradiuskm=200`

## Dev
```bash
pip install -r requirements.txt
genvm-lint check contracts/paranusa.py
pytest tests/direct/ -v
```

## Deploy cepat (Studio)
1. Buka https://studio.genlayer.com
2. Paste isi `contracts/paranusa.py`
3. Deploy (constructor kosong)
4. `fund_pool` dengan value, misal 5 GEN
5. `create_policy("DRO-1","-7.0","110.0","Grobogan","drought","20.0", 1000000000000000000)` dengan premi
6. `assess_claim("DRO-1")` -> cek `get_policy`
7. `claim_payout("DRO-1")` jika `trigger_met=true`

## Contoh koordinat Indonesia
- Karawang (drought): -6.3, 107.3
- Grobogan (drought): -7.0, 110.6
- Jakarta (flood): -6.2, 106.8
- Cianjur (earthquake): -6.8, 107.1
