"""ParaNusa direct-mode tests — semua method + negative paths.
Jalankan: pytest tests/direct/ -v  (tanpa server, web & LLM di-mock)
"""
import json


# ---------- mock builders ----------

def _mock_drought(direct_vm, total_mm, trigger):
    daily = {"daily": {"precipitation_sum": [total_mm / 30.0] * 30}}
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=30.*",
        {"status": 200, "body": json.dumps(daily)},
    )
    direct_vm.mock_llm(
        r".*30-day rainfall.*",
        json.dumps({
            "trigger_met": trigger,
            "measured_value": str(total_mm),
            "evidence": f"30d rainfall {total_mm}mm",
        }),
    )


def _mock_flood(direct_vm, total_mm, trigger):
    daily = {"daily": {"precipitation_sum": [total_mm / 7.0] * 7}}
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=7.*",
        {"status": 200, "body": json.dumps(daily)},
    )
    direct_vm.mock_llm(
        r".*7-day rainfall.*",
        json.dumps({
            "trigger_met": trigger,
            "measured_value": str(total_mm),
            "evidence": f"7d rainfall {total_mm}mm",
        }),
    )


def _mock_quake(direct_vm, max_mag, trigger):
    geojson = {"features": [
        {"properties": {"mag": max_mag, "place": "Cianjur"}},
        {"properties": {"mag": 4.2, "place": "noise"}},
    ]}
    direct_vm.mock_web(
        r".*earthquake\.usgs\.gov.*",
        {"status": 200, "body": json.dumps(geojson)},
    )
    direct_vm.mock_llm(
        r".*earthquake magnitude.*",
        json.dumps({
            "trigger_met": trigger,
            "measured_value": str(max_mag),
            "evidence": f"max M{max_mag} within 200km",
        }),
    )


def _deploy_as_owner(direct_vm, direct_deploy, owner):
    direct_vm.sender = owner
    direct_vm.value = 0
    return direct_deploy("contracts/paranusa.py")


# ---------- create / get ----------

def test_create_and_get(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    direct_vm.value = 100
    c.create_policy("POL-1", "-6.9", "107.6", "Karawang", "drought", "20.0", 1000)
    direct_vm.value = 0
    p = c.get_policy("POL-1")
    assert p["disaster_type"] == "drought"
    assert p["location"] == "Karawang"
    assert p["active"] is True
    assert p["assessed"] is False
    assert p["paid"] is False
    assert p["premium"] == 100
    assert p["payout_amount"] == 1000
    assert c.get_stats()["policy_count"] == 1


def test_reject_duplicate_policy_id(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    c.create_policy("DUP", "-6.9", "107.6", "Karawang", "drought", "20.0", 100)
    with direct_vm.expect_revert("already exists"):
        c.create_policy("DUP", "-6.9", "107.6", "Karawang", "drought", "20.0", 100)


def test_reject_unknown_type(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("disaster_type"):
        c.create_policy("BAD-1", "0", "0", "X", "tsunami", "5.0", 100)


def test_reject_bad_coords(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("lat/lon"):
        c.create_policy("BAD-2", "not-a-number", "107.6", "X", "drought", "20.0", 100)
    with direct_vm.expect_revert("lat/lon"):
        c.create_policy("BAD-3", "-95.0", "107.6", "X", "drought", "20.0", 100)


def test_reject_bad_threshold_and_payout(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("threshold"):
        c.create_policy("BAD-4", "-6.9", "107.6", "X", "drought", "abc", 100)
    with direct_vm.expect_revert("payout"):
        c.create_policy("BAD-5", "-6.9", "107.6", "X", "drought", "20.0", 0)


def test_get_missing_policy_reverts(direct_vm, direct_deploy, direct_owner):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    with direct_vm.expect_revert("not found"):
        c.get_policy("NOPE")


# ---------- fund_pool ----------

def _fund_contract_pool(direct_vm, amount):
    # Direct mode TIDAK mengkreditkan `value` payable ke balance otomatis,
    # jadi simulasi pool memakai deal() ke address kontrak.
    direct_vm.deal(direct_vm._contract_address, amount)


def test_fund_pool_tracks_balance(direct_vm, direct_deploy, direct_owner):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_owner
    direct_vm.value = 5000
    c.fund_pool()  # tidak revert = value diterima
    direct_vm.value = 0
    _fund_contract_pool(direct_vm, 5000)
    assert c.get_stats()["pool_balance"] == 5000


def test_fund_pool_zero_reverts(direct_vm, direct_deploy, direct_owner):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_owner
    direct_vm.value = 0
    with direct_vm.expect_revert("Send some GEN"):
        c.fund_pool()


# ---------- assess: ketiga trigger ----------

def test_drought_trigger_met(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0, True)
    c.create_policy("DRO-1", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    c.assess_claim("DRO-1")
    p = c.get_policy("DRO-1")
    assert p["assessed"] is True
    assert p["trigger_met"] is True
    assert p["measured_value"] == "5.0"
    assert "5.0" in p["evidence"]
    direct_vm.clear_mocks()


def test_drought_trigger_not_met(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 120.0, False)
    c.create_policy("DRO-2", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    c.assess_claim("DRO-2")
    p = c.get_policy("DRO-2")
    assert p["assessed"] is True
    assert p["trigger_met"] is False
    direct_vm.clear_mocks()


def test_flood_trigger_met(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _mock_flood(direct_vm, 280.0, True)
    c.create_policy("FLD-1", "-6.2", "106.8", "Jakarta", "flood", "150.0", 800)
    c.assess_claim("FLD-1")
    p = c.get_policy("FLD-1")
    assert p["trigger_met"] is True
    assert p["measured_value"] == "280.0"
    direct_vm.clear_mocks()


def test_earthquake_trigger_met(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _mock_quake(direct_vm, 5.6, True)
    c.create_policy("EQ-1", "-6.8", "107.1", "Cianjur", "earthquake", "5.0", 900)
    c.assess_claim("EQ-1")
    p = c.get_policy("EQ-1")
    assert p["assessed"] is True
    assert p["trigger_met"] is True
    assert p["measured_value"] == "5.6"
    direct_vm.clear_mocks()


def test_earthquake_trigger_not_met(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _mock_quake(direct_vm, 4.3, False)
    c.create_policy("EQ-2", "-6.8", "107.1", "Cianjur", "earthquake", "5.0", 900)
    c.assess_claim("EQ-2")
    assert c.get_policy("EQ-2")["trigger_met"] is False
    direct_vm.clear_mocks()


def test_assess_missing_policy_reverts(direct_vm, direct_deploy, direct_owner):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    with direct_vm.expect_revert("not found"):
        c.assess_claim("GHOST")


def test_assess_api_5xx_is_transient(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    direct_vm.mock_web(r".*api\.open-meteo\.com.*", {"status": 503, "body": "{}"})
    c.create_policy("DRO-X", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    with direct_vm.expect_revert("TRANSIENT"):
        c.assess_claim("DRO-X")
    direct_vm.clear_mocks()


# ---------- claim_payout ----------

def test_claim_full_cycle(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    # owner funds pool
    direct_vm.sender = direct_owner
    direct_vm.value = 5000
    c.fund_pool()
    direct_vm.value = 0
    _fund_contract_pool(direct_vm, 5000)
    # alice buys policy
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0, True)
    c.create_policy("PAY-1", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    c.assess_claim("PAY-1")
    # holder claims
    c.claim_payout("PAY-1")
    p = c.get_policy("PAY-1")
    assert p["paid"] is True
    assert p["active"] is False
    assert c.get_stats()["total_payouts"] == 500
    direct_vm.clear_mocks()


def test_claim_before_assess_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    c.create_policy("PAY-2", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    with direct_vm.expect_revert("not assessed"):
        c.claim_payout("PAY-2")


def test_claim_when_trigger_not_met_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 120.0, False)
    c.create_policy("PAY-3", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    c.assess_claim("PAY-3")
    with direct_vm.expect_revert("Trigger not met"):
        c.claim_payout("PAY-3")
    direct_vm.clear_mocks()


def test_claim_twice_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_owner
    direct_vm.value = 5000
    c.fund_pool()
    direct_vm.value = 0
    _fund_contract_pool(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0, True)
    c.create_policy("PAY-4", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    c.assess_claim("PAY-4")
    c.claim_payout("PAY-4")
    with direct_vm.expect_revert("Already paid"):
        c.claim_payout("PAY-4")
    direct_vm.clear_mocks()


def test_claim_by_stranger_reverts(direct_vm, direct_deploy, direct_owner, direct_alice, direct_bob):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_owner
    direct_vm.value = 5000
    c.fund_pool()
    direct_vm.value = 0
    _fund_contract_pool(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0, True)
    c.create_policy("PAY-5", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    c.assess_claim("PAY-5")
    direct_vm.sender = direct_bob  # bukan holder, bukan owner
    with direct_vm.expect_revert("Only holder"):
        c.claim_payout("PAY-5")
    direct_vm.clear_mocks()


def test_claim_insufficient_pool_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    # pool kosong: payout 500 tanpa funding
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0, True)
    c.create_policy("PAY-6", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    c.assess_claim("PAY-6")
    with direct_vm.expect_revert("Pool insufficient"):
        c.claim_payout("PAY-6")
    direct_vm.clear_mocks()


# ---------- cancel_policy ----------

def test_cancel_by_holder(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    c.create_policy("CX-1", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    c.cancel_policy("CX-1")
    assert c.get_policy("CX-1")["active"] is False


def test_cancel_by_stranger_reverts(direct_vm, direct_deploy, direct_owner, direct_alice, direct_bob):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    c.create_policy("CX-2", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Not authorized"):
        c.cancel_policy("CX-2")


def test_assess_cancelled_policy_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    c.create_policy("CX-3", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    c.cancel_policy("CX-3")
    with direct_vm.expect_revert("not active"):
        c.assess_claim("CX-3")


# ---------- views ----------

def test_preview_url_per_trigger(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    c.create_policy("PV-1", "-7.0", "110.0", "Grobogan", "drought", "20.0", 100)
    c.create_policy("PV-2", "-6.2", "106.8", "Jakarta", "flood", "150.0", 100)
    c.create_policy("PV-3", "-6.8", "107.1", "Cianjur", "earthquake", "5.0", 100)
    assert "past_days=30" in c.preview_url("PV-1")
    assert "past_days=7" in c.preview_url("PV-2")
    assert "earthquake.usgs.gov" in c.preview_url("PV-3")


def test_stats_aggregate(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    direct_vm.value = 50
    c.create_policy("ST-1", "-7.0", "110.0", "Grobogan", "drought", "20.0", 100)
    direct_vm.value = 70
    c.create_policy("ST-2", "-6.2", "106.8", "Jakarta", "flood", "150.0", 200)
    direct_vm.value = 0
    s = c.get_stats()
    assert s["policy_count"] == 2
    assert s["total_premiums"] == 120
    assert s["total_payouts"] == 0


# ---------- adversarial: LLM tidak boleh menentukan verdict ----------

def test_llm_cannot_force_payout(direct_vm, direct_deploy, direct_owner, direct_alice):
    # LLM jahat/ngaco mengklaim trigger_met=True padahal angka berkata lain.
    # Kontrak HARUS mengabaikan trigger_met LLM dan menghitung sendiri.
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    daily = {"daily": {"precipitation_sum": [4.0] * 30}}  # total 120mm
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=30.*",
        {"status": 200, "body": json.dumps(daily)},
    )
    direct_vm.mock_llm(
        r".*30-day rainfall.*",
        json.dumps({"trigger_met": True, "measured_value": "120.0", "evidence": "lies"}),
    )
    c.create_policy("ADV-1", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    c.assess_claim("ADV-1")
    p = c.get_policy("ADV-1")
    assert p["measured_value"] == "120.0"
    assert p["trigger_met"] is False  # 120 < 20 adalah False, apapun kata LLM
    direct_vm.clear_mocks()


def test_llm_garbage_measurement_falls_back(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    daily = {"daily": {"precipitation_sum": [0.0] * 30}}  # total 0mm
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=30.*",
        {"status": 200, "body": json.dumps(daily)},
    )
    direct_vm.mock_llm(
        r".*30-day rainfall.*",
        json.dumps({"measured_value": "not-a-number", "evidence": "garbage"}),
    )
    c.create_policy("ADV-2", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    c.assess_claim("ADV-2")
    p = c.get_policy("ADV-2")
    assert p["measured_value"] == "0.0"  # fallback ke hitungan kontrak
    assert p["trigger_met"] is True
    direct_vm.clear_mocks()


def test_malformed_api_payload_is_external(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*",
        {"status": 200, "body": json.dumps({"weird": "shape"})},
    )
    c.create_policy("ADV-3", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    # tanpa field daily -> total 0.0 (aman, bukan crash); LLM mock kosong -> default
    direct_vm.mock_llm(r".*", json.dumps({"measured_value": "0.0", "evidence": "x"}))
    c.assess_claim("ADV-3")
    assert c.get_policy("ADV-3")["trigger_met"] is True
    direct_vm.clear_mocks()


def test_usgs_empty_features_no_trigger(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    direct_vm.mock_web(
        r".*earthquake\.usgs\.gov.*",
        {"status": 200, "body": json.dumps({"features": []})},
    )
    direct_vm.mock_llm(r".*", json.dumps({"measured_value": "0.0", "evidence": "quiet"}))
    c.create_policy("ADV-4", "-6.8", "107.1", "Cianjur", "earthquake", "5.0", 500)
    c.assess_claim("ADV-4")
    p = c.get_policy("ADV-4")
    assert p["measured_value"] == "0.0"
    assert p["trigger_met"] is False
    direct_vm.clear_mocks()


def test_locality_appended_to_evidence(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0, True)
    direct_vm.mock_web(
        r".*bigdatacloud\.net.*",
        {"status": 200, "body": json.dumps({
            "city": "Grobogan", "principalSubdivision": "Central Java",
            "countryName": "Indonesia",
        })},
    )
    c.create_policy("ADV-5", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    c.assess_claim("ADV-5")
    assert "Grobogan" in c.get_policy("ADV-5")["evidence"]
    direct_vm.clear_mocks()


# ---------- cancel-then-claim loophole ----------

def test_cancel_then_claim_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_owner
    direct_vm.value = 5000
    c.fund_pool()
    direct_vm.value = 0
    _fund_contract_pool(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0, True)
    c.create_policy("CX-4", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    c.assess_claim("CX-4")
    c.cancel_policy("CX-4")
    with direct_vm.expect_revert("not active"):
        c.claim_payout("CX-4")
    direct_vm.clear_mocks()


# ---------- locked accounting + withdraw ----------

def test_locked_tracks_lifecycle(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    c.create_policy("LK-1", "-7.0", "110.0", "Grobogan", "drought", "20.0", 300)
    c.create_policy("LK-2", "-6.2", "106.8", "Jakarta", "flood", "150.0", 700)
    assert c.get_stats()["total_locked"] == 1000
    c.cancel_policy("LK-1")
    assert c.get_stats()["total_locked"] == 700
    c.cancel_policy("LK-2")  # cancel ganda aman (guard active)
    c.cancel_policy("LK-2")
    assert c.get_stats()["total_locked"] == 0


def test_withdraw_surplus_guards(direct_vm, direct_deploy, direct_owner, direct_alice, direct_bob):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    c.create_policy("WD-1", "-7.0", "110.0", "Grobogan", "drought", "20.0", 1000)
    _fund_contract_pool(direct_vm, 5000)  # balance 5000, locked 1000 -> surplus 4000
    # orang asing ditolak
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only owner"):
        c.withdraw_surplus(100)
    # nol ditolak
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("> 0"):
        c.withdraw_surplus(0)
    # melebihi surplus ditolak (4001 > 4000)
    with direct_vm.expect_revert("surplus"):
        c.withdraw_surplus(4001)
    # tepat surplus lolos (transfer di-drop di direct mode, tapi guard lolos)
    c.withdraw_surplus(4000)
    assert c.get_stats()["total_locked"] == 1000  # lock tidak tersentuh


def test_withdraw_fully_locked_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    c.create_policy("WD-2", "-7.0", "110.0", "Grobogan", "drought", "20.0", 5000)
    _fund_contract_pool(direct_vm, 5000)  # balance == locked -> surplus 0
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("surplus"):
        c.withdraw_surplus(1)


# ---------- fund conservation ----------
def test_fund_conservation(direct_vm, direct_deploy, direct_owner, direct_alice):
    # premi tercatat penuh + payout tercatat penuh + lock konsisten
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_owner
    direct_vm.value = 5000
    c.fund_pool()
    direct_vm.value = 0
    _fund_contract_pool(direct_vm, 5000)
    direct_vm.sender = direct_alice
    direct_vm.value = 50
    c.create_policy("FC-1", "-7.0", "110.0", "Grobogan", "drought", "20.0", 1000)
    direct_vm.value = 0
    _mock_drought(direct_vm, 5.0, True)
    c.assess_claim("FC-1")
    s = c.get_stats()
    assert s["total_premiums"] == 50
    assert s["total_locked"] == 1000
    c.claim_payout("FC-1")
    s = c.get_stats()
    assert s["total_payouts"] == 1000
    assert s["total_locked"] == 0
    direct_vm.clear_mocks()


def test_contract_source_is_ascii_only():    # Regresi: loader GenVM on-chain menolak source non-ASCII (invalid_contract).
    # Lint + direct test lokal tidak menangkap ini (CPython terima UTF-8).
    import pathlib
    src = pathlib.Path("contracts/paranusa.py").read_text(encoding="utf-8")
    bad = sorted(set(c for c in src if ord(c) > 127))
    assert not bad, f"non-ASCII chars in contract: {[hex(ord(c)) for c in bad]}"


def test_string_amount_args_coerced(direct_vm, direct_deploy, direct_owner, direct_alice):
    # Regresi live: JS client mengirim u256 sebagai string desimal.
    # Tanpa koersi, setter storage crash (str has no to_bytes).
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    c.create_policy("STR-1", "-7.0", "110.0", "Grobogan", "drought", "20.0", "1000")
    assert c.get_policy("STR-1")["payout_amount"] == 1000
    with direct_vm.expect_revert("Invalid payout"):
        c.create_policy("STR-2", "-7.0", "110.0", "Grobogan", "drought", "20.0", "abc")
    direct_vm.sender = direct_owner
    _fund_contract_pool(direct_vm, 2000)
    c.create_policy("STR-3", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    with direct_vm.expect_revert("Invalid amount"):
        c.withdraw_surplus("xyz")


def test_link_proof_flow(direct_vm, direct_deploy, direct_owner, direct_alice, direct_bob):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0, True)
    c.create_policy("LP-1", "-7.0", "110.0", "Grobogan", "drought", "20.0", 500)
    # belum assessed -> tolak
    with direct_vm.expect_revert("not assessed"):
        c.link_proof("LP-1", "0x" + "ab" * 32)
    c.assess_claim("LP-1")
    # format salah -> tolak
    with direct_vm.expect_revert("Invalid tx hash"):
        c.link_proof("LP-1", "not-a-hash")
    with direct_vm.expect_revert("Invalid tx hash"):
        c.link_proof("LP-1", "0x1234")
    # orang asing -> tolak
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Not authorized"):
        c.link_proof("LP-1", "0x" + "ab" * 32)
    # holder sukses; terbaca via get_policy (on-chain binding)
    direct_vm.sender = direct_alice
    c.link_proof("LP-1", "0x" + "ab" * 32)
    assert c.get_policy("LP-1")["assess_tx"] == "0x" + "ab" * 32
    # owner juga boleh (overwrite sah)
    direct_vm.sender = direct_owner
    c.link_proof("LP-1", "0x" + "cd" * 32)
    assert c.get_policy("LP-1")["assess_tx"] == "0x" + "cd" * 32
    direct_vm.clear_mocks()
