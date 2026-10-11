"""ParaNusa direct-mode tests — underwriting v2 flow:
request (create, min 1% premium) -> approve (owner, solvency + window) ->
assess (one-time, in-window) -> claim. Plus negative + adversarial paths.
Run: pytest tests/direct/ -v
"""
import json


# ---------- mock builders ----------

def _mock_drought(direct_vm, total_mm):
    daily = {"daily": {"precipitation_sum": [total_mm / 30.0] * 30}}
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=30.*",
        {"status": 200, "body": json.dumps(daily)},
    )
    direct_vm.mock_llm(
        r".*30-day rainfall.*",
        json.dumps({
            "measured_value": str(total_mm),
            "evidence": f"30d rainfall {total_mm}mm",
        }),
    )


def _mock_flood(direct_vm, total_mm):
    daily = {"daily": {"precipitation_sum": [total_mm / 7.0] * 7}}
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=7.*",
        {"status": 200, "body": json.dumps(daily)},
    )
    direct_vm.mock_llm(
        r".*7-day rainfall.*",
        json.dumps({
            "measured_value": str(total_mm),
            "evidence": f"7d rainfall {total_mm}mm",
        }),
    )


def _mock_quake(direct_vm, max_mag):
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
            "measured_value": str(max_mag),
            "evidence": f"max M{max_mag} within 200km",
        }),
    )


def _deploy_as_owner(direct_vm, direct_deploy, owner):
    direct_vm.sender = owner
    direct_vm.value = 0
    return direct_deploy("contracts/paranusa.py")


def _fund(direct_vm, amount):
    # Direct mode never credits payable `value` to balance; deal() simulates it.
    direct_vm.deal(direct_vm._contract_address, amount)


def _request(direct_vm, c, pid, premium, payout, dtype="drought",
             lat="-7.0", lon="110.6", loc="Grobogan", thr="20.0"):
    direct_vm.value = premium
    c.create_policy(pid, lat, lon, loc, dtype, thr, payout)
    direct_vm.value = 0


def _approve(direct_vm, c, owner, pid, days=30):
    direct_vm.sender = owner
    c.approve_policy(pid, days)


def _request_and_approve(direct_vm, c, owner, pid, premium, payout, **kw):
    sender = direct_vm.sender
    _request(direct_vm, c, pid, premium, payout, **kw)
    _approve(direct_vm, c, owner, pid, kw.get("days", 30))
    direct_vm.sender = sender


# ---------- create (request) ----------

def test_create_request_pending(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "POL-1", 100, 1000)
    p = c.get_policy("POL-1")
    assert p["active"] is False
    assert p["approved"] is False
    assert p["premium"] == 100
    assert c.get_stats()["policy_count"] == 1
    assert c.get_stats()["total_locked"] == 0  # nothing locked pre-approval


def test_reject_zero_premium(direct_vm, direct_deploy, direct_owner, direct_alice):
    # Staff rejection fix: no zero-premium self-issue.
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Premium below"):
        _request(direct_vm, c, "ZP-1", 0, 1000)
    with direct_vm.expect_revert("Premium below"):
        _request(direct_vm, c, "ZP-2", 9, 1000)  # 0.9% < 1% floor


def test_reject_duplicate_policy_id(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "DUP", 100, 1000)
    with direct_vm.expect_revert("already exists"):
        _request(direct_vm, c, "DUP", 100, 1000)


def test_reject_unknown_type(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    direct_vm.value = 100
    with direct_vm.expect_revert("disaster_type"):
        c.create_policy("BAD-1", "0", "0", "X", "tsunami", "5.0", 100)
    direct_vm.value = 0


def test_reject_bad_coords(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    direct_vm.value = 100
    with direct_vm.expect_revert("lat/lon"):
        c.create_policy("BAD-2", "not-a-number", "107.6", "X", "drought", "20.0", 100)
    with direct_vm.expect_revert("lat/lon"):
        c.create_policy("BAD-3", "-95.0", "107.6", "X", "drought", "20.0", 100)
    direct_vm.value = 0


def test_reject_bad_threshold_and_payout(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    direct_vm.value = 100
    with direct_vm.expect_revert("threshold"):
        c.create_policy("BAD-4", "-6.9", "107.6", "X", "drought", "abc", 100)
    with direct_vm.expect_revert("payout"):
        c.create_policy("BAD-5", "-6.9", "107.6", "X", "drought", "20.0", 0)
    direct_vm.value = 0


def test_get_missing_policy_reverts(direct_vm, direct_deploy, direct_owner):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    with direct_vm.expect_revert("not found"):
        c.get_policy("NOPE")


def test_string_amount_args_coerced(direct_vm, direct_deploy, direct_owner, direct_alice):
    # JS clients send u256 as decimal strings; direct tests send ints.
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    direct_vm.value = 50
    c.create_policy("STR-1", "-7.0", "110.0", "Grobogan", "drought", "20.0", "1000")
    direct_vm.value = 0
    assert c.get_policy("STR-1")["payout_amount"] == 1000


# ---------- approve (underwriting) ----------

def test_approve_activates_window_and_locks(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "AP-1", 100, 1000)
    _approve(direct_vm, c, direct_owner, "AP-1", 30)
    p = c.get_policy("AP-1")
    assert p["approved"] is True
    assert p["active"] is True
    assert p["end_ts"] - p["start_ts"] == 30 * 86400
    assert c.get_stats()["total_locked"] == 1000


def test_approve_by_stranger_reverts(direct_vm, direct_deploy, direct_owner, direct_alice, direct_bob):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "AP-2", 100, 1000)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only insurer"):
        c.approve_policy("AP-2", 30)


def test_approve_twice_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "AP-3", 100, 1000)
    _approve(direct_vm, c, direct_owner, "AP-3")
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("Already approved"):
        c.approve_policy("AP-3", 30)


def test_approve_bad_window_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "AP-4", 100, 1000)
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("7-365"):
        c.approve_policy("AP-4", 3)
    with direct_vm.expect_revert("7-365"):
        c.approve_policy("AP-4", 400)


def test_approve_insolvent_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    # Solvency: pool must cover ALL locked payouts including the new one.
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 500)  # payout 1000 > balance 500
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "AP-5", 100, 1000)
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("insolvent"):
        c.approve_policy("AP-5", 30)
    assert c.get_policy("AP-5")["approved"] is False


# ---------- fund_pool ----------

def test_fund_pool_tracks_balance(direct_vm, direct_deploy, direct_owner):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_owner
    direct_vm.value = 5000
    c.fund_pool()
    direct_vm.value = 0
    _fund(direct_vm, 5000)
    assert c.get_stats()["pool_balance"] == 5000


def test_fund_pool_zero_reverts(direct_vm, direct_deploy, direct_owner):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_owner
    direct_vm.value = 0
    with direct_vm.expect_revert("Send some GEN"):
        c.fund_pool()


# ---------- assess ----------

def test_drought_trigger_met(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    _request(direct_vm, c, "DRO-1", 50, 500)
    _approve(direct_vm, c, direct_owner, "DRO-1")
    direct_vm.sender = direct_alice
    c.assess_claim("DRO-1")
    p = c.get_policy("DRO-1")
    assert p["assessed"] is True
    assert p["trigger_met"] is True
    assert p["measured_value"] == "5.0"
    direct_vm.clear_mocks()


def test_drought_trigger_not_met(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 120.0)
    _request(direct_vm, c, "DRO-2", 50, 500)
    _approve(direct_vm, c, direct_owner, "DRO-2")
    direct_vm.sender = direct_alice
    c.assess_claim("DRO-2")
    p = c.get_policy("DRO-2")
    assert p["assessed"] is True
    assert p["trigger_met"] is False
    direct_vm.clear_mocks()


def test_flood_trigger_met(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_flood(direct_vm, 280.0)
    _request(direct_vm, c, "FLD-1", 50, 800,
             dtype="flood", lat="-6.2", lon="106.8", loc="Jakarta", thr="150.0")
    _approve(direct_vm, c, direct_owner, "FLD-1")
    direct_vm.sender = direct_alice
    c.assess_claim("FLD-1")
    p = c.get_policy("FLD-1")
    assert p["trigger_met"] is True
    assert p["measured_value"] == "280.0"
    direct_vm.clear_mocks()


def test_earthquake_trigger_met(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_quake(direct_vm, 5.6)
    _request(direct_vm, c, "EQ-1", 50, 900,
             dtype="earthquake", lat="-6.8", lon="107.1", loc="Cianjur", thr="5.0")
    _approve(direct_vm, c, direct_owner, "EQ-1")
    direct_vm.sender = direct_alice
    c.assess_claim("EQ-1")
    p = c.get_policy("EQ-1")
    assert p["assessed"] is True
    assert p["trigger_met"] is True
    assert p["measured_value"] == "5.6"
    direct_vm.clear_mocks()


def test_earthquake_trigger_not_met(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_quake(direct_vm, 4.3)
    _request(direct_vm, c, "EQ-2", 50, 900,
             dtype="earthquake", lat="-6.8", lon="107.1", loc="Cianjur", thr="5.0")
    _approve(direct_vm, c, direct_owner, "EQ-2")
    direct_vm.sender = direct_alice
    c.assess_claim("EQ-2")
    assert c.get_policy("EQ-2")["trigger_met"] is False
    direct_vm.clear_mocks()


def test_assess_unapproved_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "NA-1", 50, 500)
    with direct_vm.expect_revert("not approved"):
        c.assess_claim("NA-1")


def test_assess_twice_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    # One-time assessment: second run is rejected contract-side.
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    _request(direct_vm, c, "NA-2", 50, 500)
    _approve(direct_vm, c, direct_owner, "NA-2")
    direct_vm.sender = direct_alice
    c.assess_claim("NA-2")
    with direct_vm.expect_revert("Already assessed"):
        c.assess_claim("NA-2")
    direct_vm.clear_mocks()


def test_assess_expired_window_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    # Coverage window is immutable and binding: assess after end_ts fails.
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    _request(direct_vm, c, "NA-3", 50, 500)
    _approve(direct_vm, c, direct_owner, "NA-3", days=7)
    direct_vm.sender = direct_alice
    direct_vm.warp("2031-06-01T00:00:00Z")
    with direct_vm.expect_revert("expired"):
        c.assess_claim("NA-3")
    direct_vm.clear_mocks()


def test_assess_missing_policy_reverts(direct_vm, direct_deploy, direct_owner):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    with direct_vm.expect_revert("not found"):
        c.assess_claim("GHOST")


def test_assess_api_5xx_is_transient(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    direct_vm.mock_web(r".*api\.open-meteo\.com.*", {"status": 503, "body": "{}"})
    _request(direct_vm, c, "DRO-X", 50, 500)
    _approve(direct_vm, c, direct_owner, "DRO-X")
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("TRANSIENT"):
        c.assess_claim("DRO-X")
    direct_vm.clear_mocks()


# ---------- adversarial: LLM cannot decide ----------

def test_llm_cannot_force_payout(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    daily = {"daily": {"precipitation_sum": [4.0] * 30}}
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=30.*",
        {"status": 200, "body": json.dumps(daily)},
    )
    direct_vm.mock_llm(
        r".*30-day rainfall.*",
        json.dumps({"trigger_met": True, "measured_value": "120.0", "evidence": "lies"}),
    )
    _request(direct_vm, c, "ADV-1", 50, 500)
    _approve(direct_vm, c, direct_owner, "ADV-1")
    direct_vm.sender = direct_alice
    c.assess_claim("ADV-1")
    p = c.get_policy("ADV-1")
    assert p["measured_value"] == "120.0"
    assert p["trigger_met"] is False
    direct_vm.clear_mocks()


def test_llm_garbage_measurement_falls_back(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    daily = {"daily": {"precipitation_sum": [0.0] * 30}}
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=30.*",
        {"status": 200, "body": json.dumps(daily)},
    )
    direct_vm.mock_llm(
        r".*30-day rainfall.*",
        json.dumps({"measured_value": "not-a-number", "evidence": "garbage"}),
    )
    _request(direct_vm, c, "ADV-2", 50, 500)
    _approve(direct_vm, c, direct_owner, "ADV-2")
    direct_vm.sender = direct_alice
    c.assess_claim("ADV-2")
    p = c.get_policy("ADV-2")
    assert p["measured_value"] == "0.0"
    assert p["trigger_met"] is True
    direct_vm.clear_mocks()


def test_malformed_api_payload(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*",
        {"status": 200, "body": json.dumps({"weird": "shape"})},
    )
    direct_vm.mock_llm(r".*", json.dumps({"measured_value": "0.0", "evidence": "x"}))
    _request(direct_vm, c, "ADV-3", 50, 500)
    _approve(direct_vm, c, direct_owner, "ADV-3")
    direct_vm.sender = direct_alice
    c.assess_claim("ADV-3")
    assert c.get_policy("ADV-3")["trigger_met"] is True
    direct_vm.clear_mocks()


def test_usgs_empty_features_no_trigger(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    direct_vm.mock_web(
        r".*earthquake\.usgs\.gov.*",
        {"status": 200, "body": json.dumps({"features": []})},
    )
    direct_vm.mock_llm(r".*", json.dumps({"measured_value": "0.0", "evidence": "quiet"}))
    _request(direct_vm, c, "ADV-4", 50, 500,
             dtype="earthquake", lat="-6.8", lon="107.1", loc="Cianjur", thr="5.0")
    _approve(direct_vm, c, direct_owner, "ADV-4")
    direct_vm.sender = direct_alice
    c.assess_claim("ADV-4")
    p = c.get_policy("ADV-4")
    assert p["measured_value"] == "0.0"
    assert p["trigger_met"] is False
    direct_vm.clear_mocks()


def test_locality_appended_to_evidence(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    direct_vm.mock_web(
        r".*bigdatacloud\.net.*",
        {"status": 200, "body": json.dumps({
            "city": "Grobogan", "principalSubdivision": "Central Java",
            "countryName": "Indonesia",
        })},
    )
    _request(direct_vm, c, "ADV-5", 50, 500)
    _approve(direct_vm, c, direct_owner, "ADV-5")
    direct_vm.sender = direct_alice
    c.assess_claim("ADV-5")
    assert "Grobogan" in c.get_policy("ADV-5")["evidence"]
    direct_vm.clear_mocks()


# ---------- claim_payout ----------

def test_claim_full_cycle(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    _request(direct_vm, c, "PAY-1", 50, 500)
    _approve(direct_vm, c, direct_owner, "PAY-1")
    direct_vm.sender = direct_alice
    c.assess_claim("PAY-1")
    c.claim_payout("PAY-1")
    p = c.get_policy("PAY-1")
    assert p["paid"] is True
    assert p["active"] is False
    assert c.get_stats()["total_payouts"] == 500
    direct_vm.clear_mocks()


def test_claim_before_assess_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "PAY-2", 50, 500)
    _approve(direct_vm, c, direct_owner, "PAY-2")
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("not assessed"):
        c.claim_payout("PAY-2")


def test_claim_unapproved_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "PAY-2B", 50, 500)
    with direct_vm.expect_revert("not approved"):
        c.claim_payout("PAY-2B")


def test_claim_when_trigger_not_met_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 120.0)
    _request(direct_vm, c, "PAY-3", 50, 500)
    _approve(direct_vm, c, direct_owner, "PAY-3")
    direct_vm.sender = direct_alice
    c.assess_claim("PAY-3")
    with direct_vm.expect_revert("Trigger not met"):
        c.claim_payout("PAY-3")
    direct_vm.clear_mocks()


def test_claim_twice_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    _request(direct_vm, c, "PAY-4", 50, 500)
    _approve(direct_vm, c, direct_owner, "PAY-4")
    direct_vm.sender = direct_alice
    c.assess_claim("PAY-4")
    c.claim_payout("PAY-4")
    with direct_vm.expect_revert("Already paid"):
        c.claim_payout("PAY-4")
    direct_vm.clear_mocks()


def test_claim_by_stranger_reverts(direct_vm, direct_deploy, direct_owner, direct_alice, direct_bob):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    _request(direct_vm, c, "PAY-5", 50, 500)
    _approve(direct_vm, c, direct_owner, "PAY-5")
    direct_vm.sender = direct_alice
    c.assess_claim("PAY-5")
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only holder"):
        c.claim_payout("PAY-5")
    direct_vm.clear_mocks()


def test_claim_insufficient_pool_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    # Approve first with funds, then drain the pool to simulate shortfall.
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    _request(direct_vm, c, "PAY-6", 50, 500)
    _approve(direct_vm, c, direct_owner, "PAY-6")
    direct_vm.sender = direct_alice
    c.assess_claim("PAY-6")
    direct_vm.deal(direct_vm._contract_address, 0)
    with direct_vm.expect_revert("Pool insufficient"):
        c.claim_payout("PAY-6")
    direct_vm.clear_mocks()


def test_cancel_then_claim_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    _request(direct_vm, c, "CX-4", 50, 500)
    _approve(direct_vm, c, direct_owner, "CX-4")
    direct_vm.sender = direct_alice
    c.assess_claim("CX-4")
    c.cancel_policy("CX-4")
    with direct_vm.expect_revert("not active"):
        c.claim_payout("CX-4")
    direct_vm.clear_mocks()


# ---------- cancel_policy ----------

def test_cancel_by_holder(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "CX-1", 50, 500)
    c.cancel_policy("CX-1")
    assert c.get_policy("CX-1")["active"] is False


def test_cancel_by_stranger_reverts(direct_vm, direct_deploy, direct_owner, direct_alice, direct_bob):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "CX-2", 50, 500)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Not authorized"):
        c.cancel_policy("CX-2")


def test_assess_cancelled_policy_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "CX-3", 50, 500)
    _approve(direct_vm, c, direct_owner, "CX-3")
    direct_vm.sender = direct_alice
    c.cancel_policy("CX-3")
    with direct_vm.expect_revert("not active"):
        c.assess_claim("CX-3")


# ---------- link_proof ----------

def test_link_proof_flow(direct_vm, direct_deploy, direct_owner, direct_alice, direct_bob):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    _request(direct_vm, c, "LP-1", 50, 500)
    with direct_vm.expect_revert("not assessed"):
        c.link_proof("LP-1", "0x" + "ab" * 32)
    _approve(direct_vm, c, direct_owner, "LP-1")
    direct_vm.sender = direct_alice
    c.assess_claim("LP-1")
    with direct_vm.expect_revert("Invalid tx hash"):
        c.link_proof("LP-1", "not-a-hash")
    with direct_vm.expect_revert("Invalid tx hash"):
        c.link_proof("LP-1", "0x1234")
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Not authorized"):
        c.link_proof("LP-1", "0x" + "ab" * 32)
    direct_vm.sender = direct_alice
    c.link_proof("LP-1", "0x" + "ab" * 32)
    assert c.get_policy("LP-1")["assess_tx"] == "0x" + "ab" * 32
    direct_vm.sender = direct_owner
    c.link_proof("LP-1", "0x" + "cd" * 32)
    assert c.get_policy("LP-1")["assess_tx"] == "0x" + "cd" * 32
    direct_vm.clear_mocks()


# ---------- locked accounting + withdraw ----------

def test_locked_tracks_lifecycle(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "LK-1", 50, 300)
    _request(direct_vm, c, "LK-2", 50, 700)
    assert c.get_stats()["total_locked"] == 0  # requests lock nothing
    _approve(direct_vm, c, direct_owner, "LK-1")
    _approve(direct_vm, c, direct_owner, "LK-2")
    assert c.get_stats()["total_locked"] == 1000
    direct_vm.sender = direct_alice
    c.cancel_policy("LK-1")
    assert c.get_stats()["total_locked"] == 700
    c.cancel_policy("LK-2")
    c.cancel_policy("LK-2")
    assert c.get_stats()["total_locked"] == 0


def test_withdraw_surplus_guards(direct_vm, direct_deploy, direct_owner, direct_alice, direct_bob):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "WD-1", 50, 1000)
    _approve(direct_vm, c, direct_owner, "WD-1")
    assert c.get_stats()["total_locked"] == 1000
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only owner"):
        c.withdraw_surplus(100)
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("> 0"):
        c.withdraw_surplus(0)
    with direct_vm.expect_revert("surplus"):
        c.withdraw_surplus(4001)
    c.withdraw_surplus(4000)
    assert c.get_stats()["total_locked"] == 1000


def test_withdraw_fully_locked_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "WD-2", 250, 5000)
    _approve(direct_vm, c, direct_owner, "WD-2")
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("surplus"):
        c.withdraw_surplus(1)


# ---------- views + conservation ----------

def test_preview_url_per_trigger(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "PV-1", 50, 100)
    _request(direct_vm, c, "PV-2", 50, 100,
             dtype="flood", lat="-6.2", lon="106.8", loc="Jakarta", thr="150.0")
    _request(direct_vm, c, "PV-3", 50, 100,
             dtype="earthquake", lat="-6.8", lon="107.1", loc="Cianjur", thr="5.0")
    assert "past_days=30" in c.preview_url("PV-1")
    assert "past_days=7" in c.preview_url("PV-2")
    assert "earthquake.usgs.gov" in c.preview_url("PV-3")


def test_stats_aggregate(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "ST-1", 50, 100)
    _request(direct_vm, c, "ST-2", 70, 200,
             dtype="flood", lat="-6.2", lon="106.8", loc="Jakarta", thr="150.0")
    s = c.get_stats()
    assert s["policy_count"] == 2
    assert s["total_premiums"] == 120
    assert s["total_payouts"] == 0


def test_fund_conservation(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    _request(direct_vm, c, "FC-1", 50, 1000)
    _approve(direct_vm, c, direct_owner, "FC-1")
    direct_vm.sender = direct_alice
    c.assess_claim("FC-1")
    s = c.get_stats()
    assert s["total_premiums"] == 50
    assert s["total_locked"] == 1000
    c.claim_payout("FC-1")
    s = c.get_stats()
    assert s["total_payouts"] == 1000
    assert s["total_locked"] == 0
    direct_vm.clear_mocks()


def test_window_fields_in_policy(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "WN-1", 50, 500)
    p = c.get_policy("WN-1")
    assert p["approved"] is False
    assert p["start_ts"] == 0 and p["end_ts"] == 0
    _approve(direct_vm, c, direct_owner, "WN-1", days=14)
    p = c.get_policy("WN-1")
    assert p["approved"] is True
    assert p["end_ts"] - p["start_ts"] == 14 * 86400


def test_contract_source_is_ascii_only():
    # Regression: the on-chain GenVM loader rejects non-ASCII source
    # (invalid_contract). Local lint + direct tests never catch it.
    import pathlib
    src = pathlib.Path("contracts/paranusa.py").read_text(encoding="utf-8")
    bad = sorted(set(c for c in src if ord(c) > 127))
    assert not bad, f"non-ASCII chars in contract: {[hex(ord(c)) for c in bad]}"
