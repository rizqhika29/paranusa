# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json
from dataclasses import dataclass

# ParaNusa - Parametric Insurance Bencana Alam Nusantara (GenLayer).
# Trigger: drought | flood | earthquake. Data: Open-Meteo + USGS.


ERROR_EXPECTED = "[EXPECTED]"
ERROR_EXTERNAL = "[EXTERNAL]"
ERROR_TRANSIENT = "[TRANSIENT]"

ALLOWED_DISASTERS = ("drought", "flood", "earthquake")


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
    # Verdict SELALU dihitung kontrak secara deterministik dari angka terukur.
    # LLM hanya menulis evidence; ia TIDAK boleh menentukan trigger_met.
    if disaster_type == "drought":
        return measured < threshold
    if disaster_type == "flood":
        return measured > threshold
    return measured >= threshold  # earthquake


def _fetch_locality(lat: str, lon: str) -> str:    # Best-effort: ikat koordinat ke nama wilayah via sumber independen.
    # Gagal (rate-limit/offline) -> "" dan assessment tetap jalan.
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
    # Module-level (bukan method) agar validator_fn tidak menangkap `self`
    # (instance kontrak = storage class -> warning pickling on-chain).
    msg = leader_res.message if hasattr(leader_res, "message") else str(leader_res)
    try:
        leader_fn()
        return False
    except gl.vm.UserError as e:
        vmsg = e.message if hasattr(e, "message") else str(e)
        # error deterministik harus sama persis, transient cukup sama-sama transient
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
    # threshold disimpan sebagai string agar stabil di calldata,
    # contoh: drought "20.0" (mm/30hari), flood "150.0" (mm/7hari),
    # earthquake "5.0" (magnitudo)
    threshold: str
    premium: u256
    payout_amount: u256
    active: bool
    assessed: bool
    trigger_met: bool
    measured_value: str
    evidence: str
    paid: bool


class ParaNusa(gl.Contract):
    owner: Address
    policy_count: u256
    policies: TreeMap[str, Policy]
    total_premiums: u256
    total_payouts: u256
    # Jumlah payout polis aktif (belum paid/cancel) - dana ini TERKUNCI,
    # tidak bisa ditarik owner via withdraw_surplus.
    total_locked: u256

    def __init__(self):
        self.owner = gl.message.sender_address
        self.policy_count = u256(0)
        self.total_premiums = u256(0)
        self.total_payouts = u256(0)
        self.total_locked = u256(0)

    # ---------- helpers (deterministik, di luar nondet) ----------

    def _require_policy(self, policy_id: str) -> Policy:
        if policy_id not in self.policies:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Policy not found")
        return self.policies[policy_id]

    # ---------- funding & polis ----------

    @gl.public.write.payable
    def fund_pool(self) -> None:
        # insurer / siapa pun menambah likuiditas pool (saldo kontrak).
        # Saldo bisa dibaca via self.balance di Studio.
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
        _parse_threshold(threshold)  # validasi format saja
        payout_amount = _as_u256(payout_amount, "payout")
        if payout_amount == u256(0):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} payout must be > 0")

        premium = gl.message.value  # boleh 0 untuk demo, >0 untuk produksi
        holder = gl.message.sender_address

        self.policies[policy_id] = Policy(
            holder,
            lat,
            lon,
            location_name,
            disaster_type,
            threshold,
            premium,
            payout_amount,
            True,
            False,
            False,
            "",
            "",
            False,
        )
        self.policy_count = self.policy_count + u256(1)
        self.total_premiums = self.total_premiums + premium
        self.total_locked = self.total_locked + payout_amount

    @gl.public.write
    def withdraw_surplus(self, amount: u256) -> None:
        # Owner menarik dana BEBAS (premi/fee yang tidak menjamin polis aktif).
        # Dana terkunci = total payout polis aktif; tidak bisa disentuh.
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
        gl.get_contract_at(self.owner).emit_transfer(value=amount)

    # ---------- assessment non-deterministik ----------

    @gl.public.write
    def assess_claim(self, policy_id: str) -> None:
        pol_mem = gl.storage.copy_to_memory(self._require_policy(policy_id))
        if not pol_mem.active:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Policy not active")
        if pol_mem.paid:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Already paid")

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

    def _assess_drought(self, pol) -> dict:
        # Ekstrak primitif dulu: closure nondet di bawah TIDAK boleh
        # menangkap objek storage-class (memicu warning pickling on-chain).
        lat, lon = str(pol.lat), str(pol.lon)
        loc = str(pol.location_name)
        threshold = _parse_threshold(pol.threshold)
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
                daily = data.get("daily", {}).get("precipitation_sum", [])
                total = float(sum(x for x in daily if isinstance(x, (int, float))))
            except Exception as e:
                raise gl.vm.UserError(f"{ERROR_EXTERNAL} Bad Open-Meteo payload: {e}")
            # Grounding: hitung programmatic. Verdict dihitung KONTRAK (deterministik),
            # LLM hanya menulis evidence + melaporkan angka. measured_value WAJIB
            # string ("5.0") karena calldata tidak support float.
            prompt = (
                "You are a parametric insurance oracle. Report ONLY the measured "
                f"30-day rainfall total ({total} mm) for {loc} ({lat},{lon}). "
                "You do NOT decide the payout. "
                'Return JSON: {"measured_value": string like "5.0", "evidence": string}. '
                "evidence = 1 sentence summary."
            )
            llm = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(llm, dict):
                llm = {}
            measured_str = str(llm.get("measured_value", str(total)))
            try:
                measured_f = float(measured_str)
            except Exception:
                measured_f, measured_str = total, str(total)
            locality = _fetch_locality(lat, lon)
            evidence = str(llm.get("evidence", f"30d rainfall {total}mm vs threshold {threshold}mm"))
            if locality:
                evidence = evidence + f" Locality: {locality}."
            return {
                "trigger_met": _decide_trigger("drought", measured_f, threshold),
                "measured_value": measured_str,
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
                # decision harus sama, angka toleransi 2mm (drift antar node)
                if bool(l.get("trigger_met")) != bool(v.get("trigger_met")):
                    return False
                return abs(float(l.get("measured_value", 0)) - float(v.get("measured_value", 0))) <= 2.0
            except Exception:
                return False

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    def _assess_flood(self, pol) -> dict:
        # Ekstrak primitif dulu: closure nondet di bawah TIDAK boleh
        # menangkap objek storage-class (memicu warning pickling on-chain).
        lat, lon = str(pol.lat), str(pol.lon)
        loc = str(pol.location_name)
        threshold = _parse_threshold(pol.threshold)
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
                daily = data.get("daily", {}).get("precipitation_sum", [])
                total = float(sum(x for x in daily if isinstance(x, (int, float))))
            except Exception as e:
                raise gl.vm.UserError(f"{ERROR_EXTERNAL} Bad Open-Meteo payload: {e}")
            prompt = (
                "You are a parametric insurance oracle. Report ONLY the measured "
                f"7-day rainfall total ({total} mm) for {loc} ({lat},{lon}). "
                "You do NOT decide the payout. "
                'Return JSON: {"measured_value": string like "280.0", "evidence": string}. '
                "evidence = 1 sentence summary."
            )
            llm = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(llm, dict):
                llm = {}
            measured_str = str(llm.get("measured_value", str(total)))
            try:
                measured_f = float(measured_str)
            except Exception:
                measured_f, measured_str = total, str(total)
            locality = _fetch_locality(lat, lon)
            evidence = str(llm.get("evidence", f"7d rainfall {total}mm vs threshold {threshold}mm"))
            if locality:
                evidence = evidence + f" Locality: {locality}."
            return {
                "trigger_met": _decide_trigger("flood", measured_f, threshold),
                "measured_value": measured_str,
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
        # Ekstrak primitif dulu: closure nondet di bawah TIDAK boleh
        # menangkap objek storage-class (memicu warning pickling on-chain).
        lat, lon = str(pol.lat), str(pol.lon)
        loc = str(pol.location_name)
        threshold = _parse_threshold(pol.threshold)
        url = (
            "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
            + "&latitude=" + lat + "&longitude=" + lon
            + "&maxradiuskm=200&minmagnitude=4&limit=20&orderby=magnitude"
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
                mags = [f.get("properties", {}).get("mag", 0) for f in feats]
                mags = [m for m in mags if isinstance(m, (int, float))]
                max_mag = float(max(mags)) if mags else 0.0
            except Exception as e:
                raise gl.vm.UserError(f"{ERROR_EXTERNAL} Bad USGS payload: {e}")
            prompt = (
                "You are a parametric insurance oracle. Report ONLY the maximum "
                f"recent earthquake magnitude ({max_mag}) near {loc} ({lat},{lon}). "
                "You do NOT decide the payout. "
                'Return JSON: {"measured_value": string like "5.2", "evidence": string}. '
                "evidence = 1 sentence summary."
            )
            llm = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(llm, dict):
                llm = {}
            measured_str = str(llm.get("measured_value", str(max_mag)))
            try:
                measured_f = float(measured_str)
            except Exception:
                measured_f, measured_str = max_mag, str(max_mag)
            locality = _fetch_locality(lat, lon)
            evidence = str(llm.get("evidence", f"max M{max_mag} vs threshold M{threshold} within 200km"))
            if locality:
                evidence = evidence + f" Locality: {locality}."
            return {
                "trigger_met": _decide_trigger("earthquake", measured_f, threshold),
                "measured_value": measured_str,
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
                # magnitudo toleransi 0.3 (beda pembulatan antar node)
                return abs(float(l.get("measured_value", 0)) - float(v.get("measured_value", 0))) <= 0.3
            except Exception:
                return False

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    # ---------- payout (deterministik) ----------

    @gl.public.write
    def claim_payout(self, policy_id: str) -> None:
        pol = self._require_policy(policy_id)
        if pol.holder != gl.message.sender_address and gl.message.sender_address != self.owner:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only holder or owner can claim")
        if pol.paid:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Already paid")
        if not pol.active:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Policy not active")
        if not pol.assessed:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Claim not assessed yet")
        if not pol.trigger_met:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Trigger not met, no payout")
        if self.balance < pol.payout_amount:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Pool insufficient, ask owner to fund_pool")

        self.policies[policy_id].paid = True
        self.policies[policy_id].active = False
        self.total_payouts = self.total_payouts + pol.payout_amount
        self.total_locked = self.total_locked - pol.payout_amount
        gl.get_contract_at(pol.holder).emit_transfer(value=pol.payout_amount)

    @gl.public.write
    def cancel_policy(self, policy_id: str) -> None:
        pol = self._require_policy(policy_id)
        if gl.message.sender_address != self.owner and gl.message.sender_address != pol.holder:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Not authorized")
        if pol.paid:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Already paid")
        if pol.active:
            # bebaskan kunci hanya sekali (cancel ganda tidak double-decrement)
            self.total_locked = self.total_locked - pol.payout_amount
        self.policies[policy_id].active = False

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
        }

    @gl.public.view
    def get_stats(self) -> dict:
        return {
            "owner": self.owner.as_hex,
            "policy_count": int(self.policy_count),
            "total_premiums": int(self.total_premiums),
            "total_payouts": int(self.total_payouts),
            "total_locked": int(self.total_locked),
            "pool_balance": int(self.balance),
        }

    @gl.public.view
    def preview_url(self, policy_id: str) -> str:
        # helper untuk debug: URL apa yang akan di-fetch assess
        pol = self._require_policy(policy_id)
        if pol.disaster_type in ("drought", "flood"):
            days = "30" if pol.disaster_type == "drought" else "7"
            return f"https://api.open-meteo.com/v1/forecast?latitude={pol.lat}&longitude={pol.lon}&daily=precipitation_sum&past_days={days}&timezone=auto"
        return f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&latitude={pol.lat}&longitude={pol.lon}&maxradiuskm=200&minmagnitude=4&limit=20&orderby=magnitude"
