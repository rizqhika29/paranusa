"""ParaNusa direct-mode tests — underwriting + coverage-window + settlement guards.
Flow: request (min 1% premium) -> approve (solvency + window) ->
assess (one-time, in-window, window-filtered data) -> link -> claim.
Run: pytest tests/direct/ -v
"""
import datetime
import json


def _today():
    return datetime.datetime.now(datetime.timezone.utc).date()


def _days_ending_today(n):
    t = _today()
    return [(t - datetime.timedelta(days=n - 1 - i)).isoformat() for i in range(n)]


# ---------- mock builders (with daily.time series!) ----------

def _mock_drought(direct_vm, total_mm):
    # Total concentrated in the 12 completed days before today (today is
    # always excluded as an incomplete observation).
    times = _days_ending_today(31)
    per = total_mm / 12.0
    body = {"daily": {"time": times, "precipitation_sum": [0.0] * 18 + [per] * 12 + [0.0]}}
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=30.*",
        {"status": 200, "body": json.dumps(body)},
    )
    direct_vm.mock_llm(
        r".*rought assessment.*",
        json.dumps({"evidence": f"30d rainfall {total_mm}mm"}),
    )


def _mock_flood(direct_vm, total_mm):
    # Total concentrated in the 6 completed days before today.
    times = _days_ending_today(7)
    per = total_mm / 6.0
    body = {"daily": {"time": times, "precipitation_sum": [per] * 6 + [0.0]}}
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=7.*",
        {"status": 200, "body": json.dumps(body)},
    )
    direct_vm.mock_llm(
        r".*lood assessment.*",
        json.dumps({"evidence": f"7d rainfall {total_mm}mm"}),
    )


def _mock_quake(direct_vm, max_mag, url_pat=r".*earthquake\.usgs\.gov.*", time_ms=None):
    import time as _time
    tms = time_ms if time_ms is not None else int(_time.time() * 1000)
    geojson = {"features": [
        {"properties": {"mag": max_mag, "place": "Cianjur", "time": tms}},
        {"properties": {"mag": 4.2, "place": "noise", "time": tms}},
    ]}
    direct_vm.mock_web(
        url_pat,
        {"status": 200, "body": json.dumps(geojson)},
    )
    direct_vm.mock_llm(
        r".*arthquake assessment.*",
        json.dumps({"evidence": f"max M{max_mag} within 200km"}),
    )


def _deploy_as_owner(direct_vm, direct_deploy, owner):
    direct_vm.sender = owner
    direct_vm.value = 0
    return direct_deploy("contracts/paranusa.py")


def _fund(direct_vm, amount):
    direct_vm.deal(direct_vm._contract_address, amount)


def _request(direct_vm, c, pid, premium, payout, dtype="drought",
             lat="-7.0", lon="110.6", loc="Grobogan", thr="20.0"):
    direct_vm.value = premium
    c.create_policy(pid, lat, lon, loc, dtype, thr, payout)
    direct_vm.value = 0


def _approve(direct_vm, c, owner, pid, days=30, backdate_days=12):
    # NOTE: inside tests datetime.now() returns VM time (patched), so compute
    # BOTH warp targets up front from the pre-warp clock.
    if backdate_days:
        now = datetime.datetime.now(datetime.timezone.utc)
        past_iso = (now - datetime.timedelta(days=backdate_days)).isoformat().replace("+00:00", "Z")
        now_iso = now.isoformat().replace("+00:00", "Z")
        direct_vm.warp(past_iso)
    direct_vm.sender = owner
    c.approve_policy(pid, days)
    if backdate_days:
        direct_vm.warp(now_iso)


def _link(direct_vm, c, sender, pid, h=None):
    direct_vm.sender = sender
    c.link_proof(pid, h or ("0x" + "ab" * 32))


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
    assert c.get_stats()["total_locked"] == 0


def test_reject_zero_premium(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Premium below"):
        _request(direct_vm, c, "ZP-1", 0, 1000)
    with direct_vm.expect_revert("Premium below"):
        _request(direct_vm, c, "ZP-2", 9, 1000)


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
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    direct_vm.value = 50
    c.create_policy("STR-1", "-7.0", "110.0", "Grobogan", "drought", "20.0", "1000")
    direct_vm.value = 0
    assert c.get_policy("STR-1")["payout_amount"] == 1000


# ---------- approve ----------

def test_approve_activates_window_and_locks(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "AP-1", 100, 1000)
    _approve(direct_vm, c, direct_owner, "AP-1", 30)
    p = c.get_policy("AP-1")
    assert p["approved"] is True and p["active"] is True
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
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 500)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "AP-5", 100, 1000)
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("insolvent"):
        c.approve_policy("AP-5", 30)
    assert c.get_policy("AP-5")["approved"] is False


# ---------- fund ----------

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


# ---------- assess (window-filtered) ----------

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
    assert p["assessed"] is True and p["trigger_met"] is True
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
    assert p["assessed"] is True and p["trigger_met"] is False
    direct_vm.clear_mocks()


def test_pre_coverage_rain_excluded_v2(direct_vm, direct_deploy, direct_owner, direct_alice):
    # Window 2026-03-01..03-31. Assess on 03-15: 15 dry in-window days.
    # 20 pre-window wet days (10mm) must NOT count.
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.warp("2026-03-01T00:00:00Z")
    direct_vm.sender = direct_alice
    base = datetime.date(2026, 3, 1)
    pre = [(base - datetime.timedelta(days=20 - i)).isoformat() for i in range(20)]
    inn = [(base + datetime.timedelta(days=i)).isoformat() for i in range(15)]
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=30.*",
        {"status": 200, "body": json.dumps({
            "daily": {"time": pre + inn,
                      "precipitation_sum": [10.0] * 20 + [0.0] * 15},
        })},
    )
    direct_vm.mock_llm(r".*", json.dumps({"evidence": "dry in window"}))
    _request(direct_vm, c, "WIN-2", 50, 500)
    _approve(direct_vm, c, direct_owner, "WIN-2", days=30, backdate_days=0)
    direct_vm.sender = direct_alice
    direct_vm.warp("2026-03-15T00:00:00Z")
    c.assess_claim("WIN-2")
    p = c.get_policy("WIN-2")
    assert p["measured_value"] == "0.0"  # 200mm pre-window excluded
    assert p["trigger_met"] is True
    direct_vm.clear_mocks()


def test_sparse_data_rejected(direct_vm, direct_deploy, direct_owner, direct_alice):
    # Only 5 in-window days (< 10 minimum) -> EXPECTED, not a false trigger.
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.warp("2026-03-01T00:00:00Z")
    direct_vm.sender = direct_alice
    base = datetime.date(2026, 3, 1)
    inn = [(base + datetime.timedelta(days=i)).isoformat() for i in range(5)]
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=30.*",
        {"status": 200, "body": json.dumps({
            "daily": {"time": inn, "precipitation_sum": [0.0] * 5},
        })},
    )
    direct_vm.mock_llm(r".*", json.dumps({"evidence": "x"}))
    _request(direct_vm, c, "WIN-3", 50, 500)
    _approve(direct_vm, c, direct_owner, "WIN-3", days=30, backdate_days=0)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Insufficient in-window"):
        c.assess_claim("WIN-3")
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
    assert p["assessed"] is True and p["trigger_met"] is True
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


def test_usgs_window_params_exclude_history(direct_vm, direct_deploy, direct_owner, direct_alice):
    # The contract MUST send starttime/endtime = coverage window, so the
    # server (not just our filter) excludes historical quakes. Prove the
    # params flow by serving data only to the windowed URL.
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.warp("2030-05-01T00:00:00Z")
    direct_vm.sender = direct_alice
    _mock_quake(direct_vm, 5.6, url_pat=r".*starttime=2030-05-01.*",
                time_ms=int(datetime.datetime(2030, 5, 1, tzinfo=datetime.timezone.utc).timestamp() * 1000))
    direct_vm.mock_web(
        r".*earthquake\.usgs\.gov.*",
        {"status": 200, "body": json.dumps({"features": []})},
    )
    direct_vm.mock_llm(r".*", json.dumps({"evidence": "windowed"}))
    _request(direct_vm, c, "EQW-1", 50, 900,
             dtype="earthquake", lat="-6.8", lon="107.1", loc="Cianjur", thr="5.0")
    _approve(direct_vm, c, direct_owner, "EQW-1", days=7, backdate_days=0)
    direct_vm.sender = direct_alice
    c.assess_claim("EQW-1")
    # If the contract queried WITHOUT starttime, the generic empty mock would
    # win only when patterns mismatch... specific-first ordering proves params.
    assert c.get_policy("EQW-1")["measured_value"] == "5.6"
    assert c.get_policy("EQW-1")["trigger_met"] is True
    direct_vm.clear_mocks()


def test_assess_unapproved_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "NA-1", 50, 500)
    with direct_vm.expect_revert("not approved"):
        c.assess_claim("NA-1")


def test_assess_twice_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
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


# ---------- adversarial: measurement always programmatic ----------

def test_llm_cannot_force_payout(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    times = _days_ending_today(31)
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=30.*",
        {"status": 200, "body": json.dumps(
            {"daily": {"time": times, "precipitation_sum": [0.0] * 18 + [10.0] * 12 + [0.0]}})},
    )
    direct_vm.mock_llm(
        r".*",
        json.dumps({"trigger_met": True, "measured_value": "999.9", "evidence": "lies"}),
    )
    _request(direct_vm, c, "ADV-1", 50, 500)
    _approve(direct_vm, c, direct_owner, "ADV-1")
    direct_vm.sender = direct_alice
    c.assess_claim("ADV-1")
    p = c.get_policy("ADV-1")
    assert p["measured_value"] == "120.0"  # parsed API value, never the LLM's
    assert p["trigger_met"] is False
    direct_vm.clear_mocks()


def test_usgs_empty_features_no_trigger(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    direct_vm.mock_web(
        r".*earthquake\.usgs\.gov.*",
        {"status": 200, "body": json.dumps({"features": []})},
    )
    direct_vm.mock_llm(r".*", json.dumps({"evidence": "quiet"}))
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


# ---------- claim (link required) ----------

def test_claim_full_cycle(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    _request(direct_vm, c, "PAY-1", 50, 500)
    _approve(direct_vm, c, direct_owner, "PAY-1")
    direct_vm.sender = direct_alice
    c.assess_claim("PAY-1")
    _link(direct_vm, c, direct_alice, "PAY-1")
    c.claim_payout("PAY-1")
    p = c.get_policy("PAY-1")
    assert p["paid"] is True and p["active"] is False
    assert c.get_stats()["total_payouts"] == 500
    assert c.get_stats()["total_locked"] == 0
    direct_vm.clear_mocks()


def test_claim_without_link_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    # Assessment proof must be bound on-chain before any payout.
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    _request(direct_vm, c, "PAY-1B", 50, 500)
    _approve(direct_vm, c, direct_owner, "PAY-1B")
    direct_vm.sender = direct_alice
    c.assess_claim("PAY-1B")
    with direct_vm.expect_revert("Link assessment"):
        c.claim_payout("PAY-1B")
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
    _link(direct_vm, c, direct_alice, "PAY-3")
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
    _link(direct_vm, c, direct_alice, "PAY-4")
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
    _link(direct_vm, c, direct_alice, "PAY-5")
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only holder"):
        c.claim_payout("PAY-5")
    direct_vm.clear_mocks()


def test_claim_insufficient_pool_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    _request(direct_vm, c, "PAY-6", 50, 500)
    _approve(direct_vm, c, direct_owner, "PAY-6")
    direct_vm.sender = direct_alice
    c.assess_claim("PAY-6")
    _link(direct_vm, c, direct_alice, "PAY-6")
    direct_vm.deal(direct_vm._contract_address, 0)
    with direct_vm.expect_revert("Pool insufficient"):
        c.claim_payout("PAY-6")
    direct_vm.clear_mocks()


# ---------- cancellation protection + refunds + expiry ----------

def test_payable_claim_cannot_be_cancelled(direct_vm, direct_deploy, direct_owner, direct_alice):
    # Winning assessments stay payable: NOBODY can cancel them away.
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    _request(direct_vm, c, "PC-1", 50, 500)
    _approve(direct_vm, c, direct_owner, "PC-1")
    direct_vm.sender = direct_alice
    c.assess_claim("PC-1")
    with direct_vm.expect_revert("Payable claim"):
        c.cancel_policy("PC-1")
    # ...and the claim still pays (with proof linked).
    _link(direct_vm, c, direct_alice, "PC-1")
    c.claim_payout("PC-1")
    assert c.get_policy("PC-1")["paid"] is True
    direct_vm.clear_mocks()


def test_owner_cannot_cancel_active(direct_vm, direct_deploy, direct_owner, direct_alice):
    # The insurer cannot unilaterally kill approved cover.
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "PC-2", 50, 500)
    _approve(direct_vm, c, direct_owner, "PC-2")
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("Only holder"):
        c.cancel_policy("PC-2")


def test_reject_pending_refunds_premium(direct_vm, direct_deploy, direct_owner, direct_alice, direct_bob):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "RJ-1", 50, 500)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only insurer"):
        c.reject_policy("RJ-1")
    direct_vm.sender = direct_owner
    c.reject_policy("RJ-1")
    p = c.get_policy("RJ-1")
    assert p["active"] is False and p["approved"] is False
    assert p["refunded"] is True
    assert c.get_stats()["total_refunds"] == 50
    # double reject cannot double-pay
    c.reject_policy("RJ-1")
    assert c.get_stats()["total_refunds"] == 50


def test_reject_approved_reverts(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "RJ-2", 50, 500)
    _approve(direct_vm, c, direct_owner, "RJ-2")
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("Already approved"):
        c.reject_policy("RJ-2")


def test_holder_cancel_pending_refunds(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "CX-0", 50, 500)
    c.cancel_policy("CX-0")
    p = c.get_policy("CX-0")
    assert p["active"] is False and p["refunded"] is True
    assert c.get_stats()["total_locked"] == 0
    assert c.get_stats()["total_refunds"] == 50


def test_cancel_by_holder_releases_lock(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 5.0)
    _request(direct_vm, c, "CX-1", 50, 500)
    _approve(direct_vm, c, direct_owner, "CX-1")
    direct_vm.sender = direct_alice
    assert c.get_stats()["total_locked"] == 500
    c.cancel_policy("CX-1")
    assert c.get_policy("CX-1")["active"] is False
    assert c.get_stats()["total_locked"] == 0
    assert c.get_stats()["total_refunds"] == 50  # unassessed -> premium back
    direct_vm.clear_mocks()


def test_cancel_assessed_unmet_no_refund(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _mock_drought(direct_vm, 120.0)
    _request(direct_vm, c, "CX-1B", 50, 500)
    _approve(direct_vm, c, direct_owner, "CX-1B")
    direct_vm.sender = direct_alice
    c.assess_claim("CX-1B")
    c.cancel_policy("CX-1B")
    p = c.get_policy("CX-1B")
    assert p["active"] is False and p["refunded"] is False  # service rendered
    assert c.get_stats()["total_locked"] == 0
    assert c.get_stats()["total_refunds"] == 0
    direct_vm.clear_mocks()


def test_expire_unassessed_releases_and_refunds(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.warp("2026-04-01T00:00:00Z")
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "EX-1", 50, 500)
    _approve(direct_vm, c, direct_owner, "EX-1", days=7, backdate_days=0)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("not expired"):
        c.expire_policy("EX-1")
    direct_vm.warp("2026-05-01T00:00:00Z")
    c.expire_policy("EX-1")
    p = c.get_policy("EX-1")
    assert p["active"] is False and p["refunded"] is True
    assert c.get_stats()["total_locked"] == 0
    assert c.get_stats()["total_refunds"] == 50


def test_expire_payable_claim_survives(direct_vm, direct_deploy, direct_owner, direct_alice):
    # Window 03-20..04-19 (30d). Assess 04-01 over 13 dry in-window days.
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.warp("2026-03-20T00:00:00Z")
    direct_vm.sender = direct_alice
    days = [(datetime.date(2026, 3, 10) + datetime.timedelta(days=i)).isoformat()
            for i in range(27)]
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=30.*",
        {"status": 200, "body": json.dumps({
            "daily": {"time": days, "precipitation_sum": [0.0] * 27},
        })},
    )
    direct_vm.mock_llm(r".*", json.dumps({"evidence": "dry"}))
    _request(direct_vm, c, "EX-2", 50, 500)
    _approve(direct_vm, c, direct_owner, "EX-2", days=30, backdate_days=0)
    direct_vm.sender = direct_alice
    direct_vm.warp("2026-04-01T00:00:00Z")
    c.assess_claim("EX-2")
    assert c.get_policy("EX-2")["trigger_met"] is True
    direct_vm.warp("2026-05-01T00:00:00Z")
    with direct_vm.expect_revert("survives expiry"):
        c.expire_policy("EX-2")
    # ...and it still pays (with proof linked).
    _link(direct_vm, c, direct_alice, "EX-2")
    c.claim_payout("EX-2")
    assert c.get_policy("EX-2")["paid"] is True
    direct_vm.clear_mocks()


def test_expire_unmet_releases_lock(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.warp("2026-03-20T00:00:00Z")
    direct_vm.sender = direct_alice
    days = [(datetime.date(2026, 3, 10) + datetime.timedelta(days=i)).isoformat()
            for i in range(27)]
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=30.*",
        {"status": 200, "body": json.dumps({
            "daily": {"time": days, "precipitation_sum": [10.0] * 27},
        })},
    )
    direct_vm.mock_llm(r".*", json.dumps({"evidence": "wet"}))
    _request(direct_vm, c, "EX-3", 50, 500)
    _approve(direct_vm, c, direct_owner, "EX-3", days=30, backdate_days=0)
    direct_vm.sender = direct_alice
    direct_vm.warp("2026-04-01T00:00:00Z")
    c.assess_claim("EX-3")
    assert c.get_policy("EX-3")["trigger_met"] is False  # 130mm in-window
    direct_vm.warp("2026-05-01T00:00:00Z")
    c.expire_policy("EX-3")
    assert c.get_stats()["total_locked"] == 0
    assert c.get_stats()["total_refunds"] == 0  # assessed: no refund
    direct_vm.clear_mocks()


def test_cancel_by_stranger_reverts(direct_vm, direct_deploy, direct_owner, direct_alice, direct_bob):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "CX-2", 50, 500)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only holder"):
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
    # Proof reference is one-time: it cannot be arbitrarily overwritten,
    # not even by the owner.
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("already linked"):
        c.link_proof("LP-1", "0x" + "cd" * 32)
    assert c.get_policy("LP-1")["assess_tx"] == "0x" + "ab" * 32
    direct_vm.clear_mocks()


def test_rain_today_excluded(direct_vm, direct_deploy, direct_owner, direct_alice):
    # 500mm falls TODAY (incomplete observation) + 12 dry completed days.
    # Today must be ignored -> drought trigger True.
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    times = _days_ending_today(13)
    direct_vm.mock_web(
        r".*api\.open-meteo\.com.*past_days=30.*",
        {"status": 200, "body": json.dumps({
            "daily": {"time": times, "precipitation_sum": [0.0] * 12 + [500.0]},
        })},
    )
    direct_vm.mock_llm(r".*", json.dumps({"evidence": "dry past, wet today"}))
    _request(direct_vm, c, "TOD-1", 50, 500)
    _approve(direct_vm, c, direct_owner, "TOD-1")
    direct_vm.sender = direct_alice
    c.assess_claim("TOD-1")
    p = c.get_policy("TOD-1")
    assert p["measured_value"] == "0.0"
    assert p["trigger_met"] is True
    direct_vm.clear_mocks()


def test_quake_old_event_excluded(direct_vm, direct_deploy, direct_owner, direct_alice):
    # A big historic quake outside the coverage window must not count,
    # even when the (mocked) server returns it: client-side exact filter.
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    old_ms = int(datetime.datetime(2020, 1, 15, tzinfo=datetime.timezone.utc).timestamp() * 1000)
    direct_vm.mock_web(
        r".*earthquake\.usgs\.gov.*",
        {"status": 200, "body": json.dumps({"features": [
            {"properties": {"mag": 7.5, "place": "historic", "time": old_ms}},
        ]})},
    )
    direct_vm.mock_llm(r".*", json.dumps({"evidence": "old"}))
    _request(direct_vm, c, "EQH-1", 50, 500,
             dtype="earthquake", lat="-6.8", lon="107.1", loc="Cianjur", thr="5.0")
    _approve(direct_vm, c, direct_owner, "EQH-1")
    direct_vm.sender = direct_alice
    c.assess_claim("EQH-1")
    p = c.get_policy("EQH-1")
    assert p["measured_value"] == "0.0"
    assert p["trigger_met"] is False
    direct_vm.clear_mocks()


# ---------- locked accounting + withdraw ----------

def test_locked_tracks_lifecycle(direct_vm, direct_deploy, direct_owner, direct_alice):
    c = _deploy_as_owner(direct_vm, direct_deploy, direct_owner)
    _fund(direct_vm, 5000)
    direct_vm.sender = direct_alice
    _request(direct_vm, c, "LK-1", 50, 300)
    _request(direct_vm, c, "LK-2", 50, 700)
    assert c.get_stats()["total_locked"] == 0
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
    _link(direct_vm, c, direct_alice, "FC-1")
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
    import pathlib
    src = pathlib.Path("contracts/paranusa.py").read_text(encoding="utf-8")
    bad = sorted(set(c for c in src if ord(c) > 127))
    assert not bad, f"non-ASCII chars in contract: {[hex(ord(c)) for c in bad]}"
