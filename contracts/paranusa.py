# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json
from dataclasses import dataclass
import datetime

# ParaNusa - Parametric Disaster Insurance for the Archipelago (GenLayer).
# Trigger: drought | flood | earthquake. Data: Open-Meteo + USGS.


ERROR_EXPECTED = "[EXPECTED]"
ERROR_EXTERNAL = "[EXTERNAL]"
ERROR_TRANSIENT = "[TRANSIENT]"

ALLOWED_DISASTERS = ("drought", "flood", "earthquake")

# Holders and the owner are EOAs on the chain layer. Value sent to them MUST
# travel the EXTERNAL message path (via the ghost contract). The internal IC
# path (gl.get_contract_at(...).emit_transfer) never activates for EOAs:
# funds leave the pool but never arrive (proven live on Studionet).
@gl.evm.contract_interface
class _EoaRecipient:
    class View:
        pass

    class Write:
        pass


def _pay_eoa(dest: Address, amount: u256) -> None:
    _EoaRecipient(dest).emit_transfer(value=amount)

# Underwriting: premium must be >= 1% of payout (in basis points of 10000).
MIN_PREMIUM_BPS = 100

# Coverage window bounds (days) settable by the insurer at approval.
MIN_COVER_DAYS = 7
MAX_COVER_DAYS = 365

# Sparse-data guard: minimum in-window daily observations, else assessment
# is rejected instead of triggering on ~nothing.
DROUGHT_MIN_DAYS = 10
FLOOD_MIN_DAYS = 3


def _now_ts() -> int:
    # Deterministic tx timestamp (same for all validators).
    return int(datetime.datetime.now(datetime.timezone.utc).timestamp())


def _day_str(ts: int) -> str:
    # YYYY-MM-DD UTC. ISO dates compare lexicographically.
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%d")


def _iso_str(ts: int) -> str:
    # Full UTC timestamp for APIs accepting datetime bounds (USGS).
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _parse_threshold(raw: str) -> float:
    try:
        return float(raw)
    except Exception:
        raise gl.vm.UserError(f"{ERROR_EXPECTED} Invalid threshold format")


def _validate_coords(lat: str, lon: str) -> None:
    try:
        la, lo = float(lat), float(lon)
    except Exception:
        raise gl.vm.UserError(f"{ERROR_EXPECTED} Invalid lat/lon")
    if not (-90.0 <= la <= 90.0 and -180.0 <= lo <= 180.0):
        raise gl.vm.UserError(f"{ERROR_EXPECTED} lat/lon out of range")


def _as_u256(v, what: str) -> u256:
    # JS clients often send u256 args as decimal strings; direct-mode tests
    # send native ints. Accept both, reject everything else. Without this,
    # a str amount crashes the storage setter (no implicit coercion on-chain).
    try:
        n = None if isinstance(v, bool) else int(v)
    except Exception:
        n = None
    if n is None or n < 0:
        raise gl.vm.UserError(f"{ERROR_EXPECTED} Invalid {what}")
    return u256(n)


def _decide_trigger(disaster_type: str, measured: float, threshold: float) -> bool:
    # Verdict is ALWAYS computed deterministically by the contract from the measured number.
    # The LLM only writes evidence; it MUST NOT decide trigger_met.
    if disaster_type == "drought":
        return measured < threshold
    if disaster_type == "flood":
        return measured > threshold
    return measured >= threshold  # earthquake


def _fetch_locality(lat: str, lon: str) -> str:    # Best-effort: bind coordinates to a place name via an independent source.
    # Failure (rate-limit/offline) -> "" and assessment still proceeds.
    try:
        res = gl.nondet.web.get(
            "https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=" + lat
            + "&longitude=" + lon + "&localityLanguage=en"
        )
        if res.status != 200 or res.body is None:
            return ""
        data = json.loads(res.body.decode("utf-8"))
        parts = [
            str(data.get("city", "") or ""),
            str(data.get("principalSubdivision", "") or ""),
            str(data.get("countryName", "") or ""),
        ]
        return ", ".join(x for x in parts if x)[:120]
    except Exception:
        return ""


def _compare_errors(leader_res, leader_fn) -> bool:
    # Module-level (not a method) so validator_fn never captures `self`
    # (contract instance = storage class -> on-chain pickling warning).
    msg = leader_res.message if hasattr(leader_res, "message") else str(leader_res)
    try:
        leader_fn()
        return False
    except gl.vm.UserError as e:
        vmsg = e.message if hasattr(e, "message") else str(e)
        # deterministic errors must match exactly, transient ones only need to both be transient
        if vmsg.startswith(ERROR_TRANSIENT) and msg.startswith(ERROR_TRANSIENT):
            return True
        return vmsg == msg
    except Exception:
        return False


@allow_storage
@dataclass
class Policy:
    holder: Address
    lat: str
    lon: str
    location_name: str
    disaster_type: str
    # threshold stored as string to stay stable in calldata,
    # e.g. drought "20.0" (mm/30days), flood "150.0" (mm/7days),
    # earthquake "5.0" (magnitude)
    threshold: str
    premium: u256
    payout_amount: u256
    active: bool
    assessed: bool
    trigger_met: bool
    measured_value: str
    evidence: str
    paid: bool
    # Tx hash of the assessment that produced the verdict (set via link_proof
    # by holder/owner AFTER assess finalizes). The contract cannot read its own
    # tx hash (not exposed in gl.message), so explicit linking is the pattern.
    # Appended LAST - storage layout is positional, never insert above.
    assess_tx: str
    # Underwriting (set once by the insurer at approval, then immutable):
    # approved flips False->True exactly once; coverage window is fixed.
    approved: bool
    start_ts: u256
    end_ts: u256
    # Premium refund bookkeeping (reject/cancel/expire, once each at most).
    refunded: bool


class ParaNusa(gl.Contract):
    owner: Address
    policy_count: u256
    policies: TreeMap[str, Policy]
    total_premiums: u256
    total_payouts: u256
    total_refunds: u256
    # Total payout of active policies (not paid/cancelled) - these funds are LOCKED,
    # cannot be withdrawn by owner via withdraw_surplus.
    total_locked: u256
    # Last emitted value transfer, "kind:policy_id:amount" (e.g.
    # "claim:DRO-1:500000000000000000"). If the child message errors, the
    # value returns via __on_errored_message__, which uses this record to
    # reverse exactly the right books instead of stranding funds.
    pending_payout: str

    def __init__(self):
        self.owner = gl.message.sender_address
        self.policy_count = u256(0)
        self.total_premiums = u256(0)
        self.total_payouts = u256(0)
        self.total_refunds = u256(0)
        self.total_locked = u256(0)
        self.pending_payout = ""

    # ---------- helpers (deterministic, outside nondet) ----------

    def _require_policy(self, policy_id: str) -> Policy:
        if policy_id not in self.policies:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Policy not found")
        return self.policies[policy_id]

    # ---------- funding & policies ----------

    @gl.public.write.payable
    def fund_pool(self) -> None:
        # insurer / anyone adds pool liquidity (contract balance).
        # Balance readable via self.balance in Studio.
        if gl.message.value == u256(0):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Send some GEN to fund pool")

    @gl.public.write.payable
    def create_policy(
        self,
        policy_id: str,
        lat: str,
        lon: str,
        location_name: str,
        disaster_type: str,
        threshold: str,
        payout_amount: u256,
    ) -> None:
        if not policy_id or len(policy_id) > 64:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invalid policy_id")
        if policy_id in self.policies:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Policy ID already exists")
        if disaster_type not in ALLOWED_DISASTERS:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} disaster_type must be drought/flood/earthquake")
        _validate_coords(lat, lon)
        _parse_threshold(threshold)  # format validation only
        payout_amount = _as_u256(payout_amount, "payout")
        if payout_amount == u256(0):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} payout must be > 0")

        premium = gl.message.value
        # Underwriting floor: premium must price at least MIN_PREMIUM_BPS of
        # the payout. Zero-premium self-issue is rejected contract-side.
        if premium * u256(10000) < payout_amount * u256(MIN_PREMIUM_BPS):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Premium below 1% of payout")
        holder = gl.message.sender_address

        # Request only: NOT active, NOT approved, NOT locked. The insurer
        # activates (with solvency check + immutable window) via approve_policy.
        self.policies[policy_id] = Policy(
            holder,
            lat,
            lon,
            location_name,
            disaster_type,
            threshold,
            premium,
            payout_amount,
            False,
            False,
            False,
            "",
            "",
            False,
            "",
            False,
            u256(0),
            u256(0),
            False,
        )
        self.policy_count = self.policy_count + u256(1)
        self.total_premiums = self.total_premiums + premium

    def _refund_premium(self, policy_id: str) -> None:
        # Returns the premium to the holder exactly once. Transfer itself is
        # fire-and-forget on-chain; total_refunds keeps auditable accounting.
        pol = self.policies[policy_id]
        if pol.refunded:
            return
        self.policies[policy_id].refunded = True
        if pol.premium > u256(0):
            self.total_refunds = self.total_refunds + pol.premium
            self.pending_payout = "refund:" + policy_id + ":" + str(int(pol.premium))
            _pay_eoa(pol.holder, pol.premium)

    @gl.public.write
    def approve_policy(self, policy_id: str, duration_days: u256) -> None:
        # Insurer underwriting: activates a requested policy with an immutable
        # coverage window. Solvency enforced: the pool must cover ALL locked
        # payouts including this one, otherwise the policy stays pending.
        if gl.message.sender_address != self.owner:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only insurer can approve")
        pol = self._require_policy(policy_id)
        if pol.approved:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Already approved")
        if pol.paid:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Already paid")
        duration_days = _as_u256(duration_days, "duration")
        if duration_days < u256(MIN_COVER_DAYS) or duration_days > u256(MAX_COVER_DAYS):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Cover must be 7-365 days")
        if self.balance < self.total_locked + pol.payout_amount:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Pool insolvent for this payout")
        now = u256(_now_ts())
        self.policies[policy_id].approved = True
        self.policies[policy_id].active = True
        self.policies[policy_id].start_ts = now
        self.policies[policy_id].end_ts = now + duration_days * u256(86400)
        self.total_locked = self.total_locked + pol.payout_amount

    @gl.public.write
    def withdraw_surplus(self, amount: u256) -> None:
        # Owner withdraws FREE funds (premiums/fees not backing active policies).
        # Locked funds = total payout of active policies; untouchable.
        if gl.message.sender_address != self.owner:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only owner can withdraw")
        amount = _as_u256(amount, "amount")
        if amount == u256(0):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Amount must be > 0")
        balance = self.balance
        locked = self.total_locked
        if balance < locked:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Pool fully locked by active policies")
        avail = balance - locked
        if amount > avail:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Amount exceeds withdrawable surplus")
        self.pending_payout = "withdraw::" + str(int(amount))
        _pay_eoa(self.owner, amount)

    # ---------- non-deterministic assessment ----------

    @gl.public.write
    def assess_claim(self, policy_id: str) -> None:
        pol_mem = gl.storage.copy_to_memory(self._require_policy(policy_id))
        if not pol_mem.approved:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Policy not approved by insurer")
        if not pol_mem.active:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Policy not active")
        if pol_mem.paid:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Already paid")
        if pol_mem.assessed:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Already assessed (one-time)")
        if u256(_now_ts()) > pol_mem.end_ts:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Coverage window expired")

        if pol_mem.disaster_type == "drought":
            result = self._assess_drought(pol_mem)
        elif pol_mem.disaster_type == "flood":
            result = self._assess_flood(pol_mem)
        elif pol_mem.disaster_type == "earthquake":
            result = self._assess_earthquake(pol_mem)
        else:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Unknown disaster type")

        self.policies[policy_id].assessed = True
        self.policies[policy_id].trigger_met = result["trigger_met"]
        self.policies[policy_id].measured_value = str(result["measured_value"])
        self.policies[policy_id].evidence = result["evidence"][:2000]

    def _window_days(self, pol) -> tuple:
        # Coverage interval as ISO days, computed deterministically OUTSIDE
        # nondet: [start_day, cap_day] where cap = min(today, end_day).
        # Only COMPLETED days count: the tx day itself is still in progress
        # (partial observations + forecast), so cap = min(yesterday, end_day).
        # Observations outside this interval MUST NOT influence the verdict.
        start_day = _day_str(int(pol.start_ts))
        end_day = _day_str(int(pol.end_ts))
        today = _day_str(_now_ts())
        yday = _day_str(_now_ts() - 86400)
        cap_day = end_day if end_day < yday else yday
        return (start_day, cap_day)

    def _assess_drought(self, pol) -> dict:
        # Extract primitives first: the nondet closure below MUST NOT
        # capture storage-class objects (triggers on-chain pickling warning).
        lat, lon = str(pol.lat), str(pol.lon)
        loc = str(pol.location_name)
        threshold = _parse_threshold(pol.threshold)
        win_start, win_cap = self._window_days(pol)
        url = (
            "https://api.open-meteo.com/v1/forecast?latitude=" + lat
            + "&longitude=" + lon
            + "&daily=precipitation_sum&past_days=30&timezone=auto"
        )

        def leader_fn():
            try:
                res = gl.nondet.web.get(url)
            except Exception as e:
                raise gl.vm.UserError(f"{ERROR_TRANSIENT} Open-Meteo unreachable: {e}")
            if res.status >= 500:
                raise gl.vm.UserError(f"{ERROR_TRANSIENT} Open-Meteo 5xx: {res.status}")
            if res.status != 200:
                raise gl.vm.UserError(f"{ERROR_EXTERNAL} Open-Meteo status {res.status}")
            try:
                data = json.loads(res.body.decode("utf-8"))
                daily = data.get("daily", {})
                times = daily.get("time", [])
                vals = daily.get("precipitation_sum", [])
                if not isinstance(times, list) or not isinstance(vals, list):
                    raise gl.vm.UserError(f"{ERROR_EXTERNAL} Bad Open-Meteo payload: missing time/values")
                if len(times) != len(vals) or len(times) == 0:
                    raise gl.vm.UserError(f"{ERROR_EXTERNAL} Bad Open-Meteo payload: bad series shape")
                # ONLY in-coverage observations count. Pre-coverage rain and
                # not-yet-occurred forecast days are excluded by date.
                in_win = [
                    float(v) for t, v in zip(times, vals)
                    if isinstance(t, str) and win_start <= t <= win_cap
                    and isinstance(v, (int, float))
                ]
                if len(in_win) < DROUGHT_MIN_DAYS:
                    raise gl.vm.UserError(
                        f"{ERROR_EXPECTED} Insufficient in-window observations "
                        f"({len(in_win)} days)"
                    )
                total = float(sum(in_win))
                ndays = len(in_win)
            except gl.vm.UserError:
                raise
            except Exception as e:
                raise gl.vm.UserError(f"{ERROR_EXTERNAL} Bad Open-Meteo payload: {e}")
            # The measurement is ALWAYS the programmatically parsed API value.
            # The LLM only writes the evidence sentence; its numbers are ignored,
            # so a false LLM-restated number cannot change the trigger.
            prompt = (
                "You are a parametric insurance oracle. Write ONE sentence of "
                f"evidence for a drought assessment: {total} mm rain over {ndays} "
                f"observed days in coverage {win_start}..{win_cap} near {loc} ({lat},{lon}). "
                "You do NOT decide anything. "
                'Return JSON: {"evidence": string}.'
            )
            llm = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(llm, dict):
                llm = {}
            locality = _fetch_locality(lat, lon)
            evidence = str(llm.get("evidence", f"30d rainfall {total}mm vs threshold {threshold}mm"))
            if locality:
                evidence = evidence + f" Locality: {locality}."
            return {
                "trigger_met": _decide_trigger("drought", total, threshold),
                "measured_value": str(total),
                "evidence": evidence,
            }

        def validator_fn(leader_res) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return _compare_errors(leader_res, leader_fn)
            try:
                v = leader_fn()
            except Exception:
                return False
            l = leader_res.calldata
            try:
                # decision must match, numeric tolerance 2mm (drift between nodes)
                if bool(l.get("trigger_met")) != bool(v.get("trigger_met")):
                    return False
                return abs(float(l.get("measured_value", 0)) - float(v.get("measured_value", 0))) <= 2.0
            except Exception:
                return False

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    def _assess_flood(self, pol) -> dict:
        # Extract primitives first: the nondet closure below MUST NOT
        # capture storage-class objects (triggers on-chain pickling warning).
        lat, lon = str(pol.lat), str(pol.lon)
        loc = str(pol.location_name)
        threshold = _parse_threshold(pol.threshold)
        win_start, win_cap = self._window_days(pol)
        url = (
            "https://api.open-meteo.com/v1/forecast?latitude=" + lat
            + "&longitude=" + lon
            + "&daily=precipitation_sum&past_days=7&timezone=auto"
        )

        def leader_fn():
            try:
                res = gl.nondet.web.get(url)
            except Exception as e:
                raise gl.vm.UserError(f"{ERROR_TRANSIENT} Open-Meteo unreachable: {e}")
            if res.status >= 500:
                raise gl.vm.UserError(f"{ERROR_TRANSIENT} Open-Meteo 5xx: {res.status}")
            if res.status != 200:
                raise gl.vm.UserError(f"{ERROR_EXTERNAL} Open-Meteo status {res.status}")
            try:
                data = json.loads(res.body.decode("utf-8"))
                daily = data.get("daily", {})
                times = daily.get("time", [])
                vals = daily.get("precipitation_sum", [])
                if not isinstance(times, list) or not isinstance(vals, list):
                    raise gl.vm.UserError(f"{ERROR_EXTERNAL} Bad Open-Meteo payload: missing time/values")
                if len(times) != len(vals) or len(times) == 0:
                    raise gl.vm.UserError(f"{ERROR_EXTERNAL} Bad Open-Meteo payload: bad series shape")
                in_win = [
                    float(v) for t, v in zip(times, vals)
                    if isinstance(t, str) and win_start <= t <= win_cap
                    and isinstance(v, (int, float))
                ]
                if len(in_win) < FLOOD_MIN_DAYS:
                    raise gl.vm.UserError(
                        f"{ERROR_EXPECTED} Insufficient in-window observations "
                        f"({len(in_win)} days)"
                    )
                total = float(sum(in_win))
                ndays = len(in_win)
            except gl.vm.UserError:
                raise
            except Exception as e:
                raise gl.vm.UserError(f"{ERROR_EXTERNAL} Bad Open-Meteo payload: {e}")
            # The measurement is ALWAYS the programmatically parsed API value.
            prompt = (
                "You are a parametric insurance oracle. Write ONE sentence of "
                f"evidence for a flood assessment: {total} mm rain over {ndays} "
                f"observed days in coverage {win_start}..{win_cap} near {loc} ({lat},{lon}). "
                "You do NOT decide anything. "
                'Return JSON: {"evidence": string}.'
            )
            llm = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(llm, dict):
                llm = {}
            locality = _fetch_locality(lat, lon)
            evidence = str(llm.get("evidence", f"7d rainfall {total}mm vs threshold {threshold}mm"))
            if locality:
                evidence = evidence + f" Locality: {locality}."
            return {
                "trigger_met": _decide_trigger("flood", total, threshold),
                "measured_value": str(total),
                "evidence": evidence,
            }

        def validator_fn(leader_res) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return _compare_errors(leader_res, leader_fn)
            try:
                v = leader_fn()
            except Exception:
                return False
            l = leader_res.calldata
            try:
                if bool(l.get("trigger_met")) != bool(v.get("trigger_met")):
                    return False
                return abs(float(l.get("measured_value", 0)) - float(v.get("measured_value", 0))) <= 2.0
            except Exception:
                return False

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    def _assess_earthquake(self, pol) -> dict:
        # Extract primitives first: the nondet closure below MUST NOT
        # capture storage-class objects (triggers on-chain pickling warning).
        lat, lon = str(pol.lat), str(pol.lon)
        loc = str(pol.location_name)
        threshold = _parse_threshold(pol.threshold)
        # EXACT coverage bounds (second precision, deterministic tx time).
        # Date-only bounds could include pre-activation events or exclude
        # late-day qualifying events, so both the server query AND a
        # client-side event-time filter use exact timestamps.
        start_ts = int(pol.start_ts)
        now_ts = _now_ts()
        end_ts = int(pol.end_ts)
        cap_ts = end_ts if end_ts < now_ts else now_ts
        url = (
            "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
            + "&latitude=" + lat + "&longitude=" + lon
            + "&maxradiuskm=200&minmagnitude=4&limit=20&orderby=magnitude"
            + "&starttime=" + _iso_str(start_ts) + "&endtime=" + _iso_str(cap_ts)
        )

        def leader_fn():
            try:
                res = gl.nondet.web.get(url)
            except Exception as e:
                raise gl.vm.UserError(f"{ERROR_TRANSIENT} USGS unreachable: {e}")
            if res.status >= 500:
                raise gl.vm.UserError(f"{ERROR_TRANSIENT} USGS 5xx: {res.status}")
            if res.status != 200:
                raise gl.vm.UserError(f"{ERROR_EXTERNAL} USGS status {res.status}")
            try:
                data = json.loads(res.body.decode("utf-8"))
                feats = data.get("features", [])
                mags = []
                for f in feats:
                    props = f.get("properties", {}) if isinstance(f, dict) else {}
                    m = props.get("mag", 0)
                    t = props.get("time", 0)
                    # Only events that actually occurred inside the coverage
                    # interval count. Compare in whole seconds: comparing epoch
                    # milliseconds against second-precision bounds would wrongly
                    # exclude events sharing the boundary second.
                    try:
                        tsecs = int(t) // 1000
                    except Exception:
                        continue
                    if not isinstance(m, (int, float)):
                        continue
                    if start_ts <= tsecs <= cap_ts:
                        mags.append(float(m))
                max_mag = float(max(mags)) if mags else 0.0
            except Exception as e:
                raise gl.vm.UserError(f"{ERROR_EXTERNAL} Bad USGS payload: {e}")
            # The measurement is ALWAYS the programmatically parsed API value.
            prompt = (
                "You are a parametric insurance oracle. Write ONE sentence of "
                f"evidence for an earthquake assessment: max magnitude {max_mag} "
                f"in coverage {_iso_str(start_ts)}..{_iso_str(cap_ts)} near {loc} ({lat},{lon}). "
                "You do NOT decide anything. "
                'Return JSON: {"evidence": string}.'
            )
            llm = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(llm, dict):
                llm = {}
            locality = _fetch_locality(lat, lon)
            evidence = str(llm.get("evidence", f"max M{max_mag} vs threshold M{threshold} within 200km"))
            if locality:
                evidence = evidence + f" Locality: {locality}."
            return {
                "trigger_met": _decide_trigger("earthquake", max_mag, threshold),
                "measured_value": str(max_mag),
                "evidence": evidence,
            }

        def validator_fn(leader_res) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return _compare_errors(leader_res, leader_fn)
            try:
                v = leader_fn()
            except Exception:
                return False
            l = leader_res.calldata
            try:
                if bool(l.get("trigger_met")) != bool(v.get("trigger_met")):
                    return False
                # magnitude tolerance 0.3 (rounding differences between nodes)
                return abs(float(l.get("measured_value", 0)) - float(v.get("measured_value", 0))) <= 0.3
            except Exception:
                return False

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    # ---------- payout (deterministic) ----------

    @gl.public.write
    def link_proof(self, policy_id: str, tx_hash: str) -> None:
        # Binds the assessment tx hash to the policy so ANY client can read
        # the consensus proof on-chain (get_policy.assess_tx). Called by the
        # holder/owner right after the assess tx finalizes. Cheap + deterministic.
        pol = self._require_policy(policy_id)
        if gl.message.sender_address != self.owner and gl.message.sender_address != pol.holder:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Not authorized")
        if not pol.assessed:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Policy not assessed yet")
        h = tx_hash.strip() if isinstance(tx_hash, str) else ""
        if len(h) != 66 or not h.startswith("0x"):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invalid tx hash (0x + 64 hex)")
        try:
            int(h[2:], 16)
        except Exception:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invalid tx hash (0x + 64 hex)")
        if pol.assess_tx:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Proof already linked")
        self.policies[policy_id].assess_tx = h

    @gl.public.write
    def claim_payout(self, policy_id: str) -> None:
        pol = self._require_policy(policy_id)
        if pol.holder != gl.message.sender_address and gl.message.sender_address != self.owner:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only holder or owner can claim")
        if pol.paid:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Already paid")
        if not pol.approved:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Policy not approved by insurer")
        if not pol.active:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Policy not active")
        if not pol.assessed:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Claim not assessed yet")
        if not pol.trigger_met:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Trigger not met, no payout")
        if not pol.assess_tx:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Link assessment proof first")
        if self.balance < pol.payout_amount:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Pool insufficient, ask owner to fund_pool")

        self.policies[policy_id].paid = True
        self.policies[policy_id].active = False
        self.total_payouts = self.total_payouts + pol.payout_amount
        self.total_locked = self.total_locked - pol.payout_amount
        self.pending_payout = "claim:" + policy_id + ":" + str(int(pol.payout_amount))
        _pay_eoa(pol.holder, pol.payout_amount)

    @gl.public.write
    def cancel_policy(self, policy_id: str) -> None:
        # HOLDER ONLY. The insurer cannot unilaterally cancel approved cover
        # (it must use reject_policy for pending requests). A payable claim
        # (assessed + trigger met + unpaid) can NEVER be cancelled away -
        # by anyone - so winning assessments stay payable.
        pol = self._require_policy(policy_id)
        if gl.message.sender_address != pol.holder:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only holder can cancel")
        if pol.paid:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Already paid")
        if pol.assessed and pol.trigger_met:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Payable claim cannot be cancelled")
        if pol.active:
            # release the lock only once (double cancel must not double-decrement)
            self.total_locked = self.total_locked - pol.payout_amount
        self.policies[policy_id].active = False
        if not pol.assessed:
            self._refund_premium(policy_id)

    @gl.public.write
    def reject_policy(self, policy_id: str) -> None:
        # Insurer declines a PENDING request. Premium is refunded in full -
        # rejecting must never be a way to harvest premiums.
        if gl.message.sender_address != self.owner:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only insurer can reject")
        pol = self._require_policy(policy_id)
        if pol.approved:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Already approved, use expiry")
        if pol.paid:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Already paid")
        self.policies[policy_id].active = False
        self._refund_premium(policy_id)

    @gl.public.write
    def expire_policy(self, policy_id: str) -> None:
        # Safe unilateral recovery after the coverage window ends. Releases
        # unused reserves WITHOUT touching legitimate claims: a payable claim
        # (assessed + met + unpaid) stays open and payable forever.
        pol = self._require_policy(policy_id)
        if gl.message.sender_address != self.owner and gl.message.sender_address != pol.holder:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Not authorized")
        if pol.paid:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Already paid")
        if not pol.approved:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Policy never approved")
        if u256(_now_ts()) <= pol.end_ts:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Coverage window not expired")
        if pol.assessed and pol.trigger_met:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Payable claim survives expiry")
        if pol.active:
            self.total_locked = self.total_locked - pol.payout_amount
        self.policies[policy_id].active = False
        if not pol.assessed:
            self._refund_premium(policy_id)

    @gl.public.write.payable
    def __on_errored_message__(self) -> None:
        # A value transfer this contract sent has come back (the child
        # message errored). Reverses exactly the books the matching payout
        # touched, so failed transfers rejoin accounting instead of
        # stranding funds. Anything unmatched is cleared, never guessed.
        value = gl.message.value
        pending = str(self.pending_payout)
        self.pending_payout = ""
        if value == u256(0):
            return
        i = pending.find(":")
        j = pending.rfind(":")
        if i < 0 or j <= i:
            return
        kind = pending[:i]
        pid = pending[i + 1:j]
        try:
            amt = int(pending[j + 1:])
        except Exception:
            return
        if amt <= 0 or int(value) != amt:
            return
        if kind == "claim" and pid in self.policies:
            self.policies[pid].paid = False
            self.policies[pid].active = True
            self.total_locked = self.total_locked + u256(amt)
            cur = self.total_payouts
            self.total_payouts = cur - u256(amt) if cur >= u256(amt) else u256(0)
        elif kind == "refund" and pid in self.policies:
            self.policies[pid].refunded = False
            cur = self.total_refunds
            self.total_refunds = cur - u256(amt) if cur >= u256(amt) else u256(0)
        # withdraw kind touches no totals (balance is chain-level): nothing
        # else to reverse once the value is back.

    # ---------- views ----------

    @gl.public.view
    def get_policy(self, policy_id: str) -> dict:
        pol = self._require_policy(policy_id)
        return {
            "holder": pol.holder.as_hex,
            "location": pol.location_name,
            "lat": pol.lat,
            "lon": pol.lon,
            "disaster_type": pol.disaster_type,
            "threshold": pol.threshold,
            "premium": int(pol.premium),
            "payout_amount": int(pol.payout_amount),
            "active": pol.active,
            "assessed": pol.assessed,
            "trigger_met": pol.trigger_met,
            "measured_value": pol.measured_value,
            "evidence": pol.evidence,
            "paid": pol.paid,
            "assess_tx": pol.assess_tx,
            "approved": pol.approved,
            "start_ts": int(pol.start_ts),
            "end_ts": int(pol.end_ts),
            "refunded": pol.refunded,
        }

    @gl.public.view
    def get_stats(self) -> dict:
        return {
            "owner": self.owner.as_hex,
            "policy_count": int(self.policy_count),
            "total_premiums": int(self.total_premiums),
            "total_payouts": int(self.total_payouts),
            "total_refunds": int(self.total_refunds),
            "total_locked": int(self.total_locked),
            "pool_balance": int(self.balance),
        }

    @gl.public.view
    def preview_url(self, policy_id: str) -> str:
        # debug helper: which URL assess will fetch
        pol = self._require_policy(policy_id)
        if pol.disaster_type in ("drought", "flood"):
            days = "30" if pol.disaster_type == "drought" else "7"
            return f"https://api.open-meteo.com/v1/forecast?latitude={pol.lat}&longitude={pol.lon}&daily=precipitation_sum&past_days={days}&timezone=auto"
        return f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&latitude={pol.lat}&longitude={pol.lon}&maxradiuskm=200&minmagnitude=4&limit=20&orderby=magnitude"
