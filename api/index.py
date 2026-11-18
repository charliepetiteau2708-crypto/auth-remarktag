import argparse
import base64
import datetime as dt
import gzip
import hashlib
import json
import os
import random
import re
import secrets
import sqlite3
import threading
import time
import uuid

from flask import Flask, Response, request

CFG = {
    "host": "0.0.0.0",
    "port": 9090,
    "db": os.path.join(os.path.dirname(os.path.abspath(__file__)), "gorilla_tag_backend.db"),
    "title_id": "63FDD",
    "mothership_title_id": "f3e9fb19",
    "mothership_env_id": "7f3a99dd-5598-4725-98cf-6538d28feb9f",
    "mothership_deployment_id": "2277bc1d-1242-499d-8c89-167a7085c373",
    "client_version": "live1.1.1.143",
    "strict_auth": False,
    "kid_mode": "adult",
    "starting_shiny_rocks": 500,
    "daily_login_shiny_rocks": 100,
    "opt_in_reward_shiny_rocks": 500,
    "starting_shift_credits": 1000,
    "shift_credit_cap_increases_max": 10,
    "shift_credit_refill_cost_sr": 100,
    "shift_credit_cap_increase_cost_juice": 2,
    "overdrive_cost_sr": 250,
    "overdrive_cap": 600,
    "core_processing_time_sec": 600,
    "juicer_seed_cap": 10,
    "credits_per_core": 5,
    "credits_per_supercore": 15,
    "drill_upgrade_cost_sr": 2500,
    "tech_point_cost_sr": 100,
    "resources_purchase_cost_sr": 500,
    "si_resource_cap": 30,
    "daily_quest_points": 1,
    "weekly_quest_points": 2,
    "weekly_quest_cap": 25,
    "dear_lemming_cooldown_sec": 86400,
    "ccu_window_sec": 600,
    "match_ping_timeout_sec": 300,
    "friend_request_ttl_sec": 600,
    "nonce_ttl_sec": 600,
    "analytics_max_records": 1000,
}

APP_VERSION = "gtag-backend/2.0"
UTC = dt.timezone.utc


def utcnow():
    return dt.datetime.now(UTC)


def iso(d=None):
    d = d or utcnow()
    return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f0Z")


def iso_short(d=None):
    d = d or utcnow()
    return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        d = dt.datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=UTC)
        return d
    except Exception:
        return None


class Store:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS kv (ns TEXT NOT NULL, k TEXT NOT NULL, v TEXT NOT NULL,"
            " updated REAL NOT NULL, PRIMARY KEY (ns, k))"
        )
        self.conn.commit()

    def get(self, ns, k, default=None):
        with self.lock:
            row = self.conn.execute("SELECT v FROM kv WHERE ns=? AND k=?", (ns, str(k))).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, ns, k, v):
        with self.lock:
            self.conn.execute(
                "INSERT INTO kv(ns,k,v,updated) VALUES(?,?,?,?) ON CONFLICT(ns,k) DO UPDATE SET v=excluded.v, updated=excluded.updated",
                (ns, str(k), json.dumps(v, separators=(",", ":")), time.time()),
            )
            self.conn.commit()
        return v

    def delete(self, ns, k):
        with self.lock:
            self.conn.execute("DELETE FROM kv WHERE ns=? AND k=?", (ns, str(k)))
            self.conn.commit()

    def items(self, ns):
        with self.lock:
            rows = self.conn.execute("SELECT k, v FROM kv WHERE ns=?", (ns,)).fetchall()
        return [(k, json.loads(v)) for k, v in rows]

    def keys(self, ns):
        with self.lock:
            rows = self.conn.execute("SELECT k FROM kv WHERE ns=?", (ns,)).fetchall()
        return [r[0] for r in rows]

    def count(self, ns):
        with self.lock:
            return self.conn.execute("SELECT COUNT(*) FROM kv WHERE ns=?", (ns,)).fetchone()[0]

    def oldest_keys(self, ns, n):
        with self.lock:
            rows = self.conn.execute("SELECT k FROM kv WHERE ns=? ORDER BY updated ASC LIMIT ?", (ns, n)).fetchall()
        return [r[0] for r in rows]


DB: Store = Store(CFG["db"])
LOCK = threading.RLock()

app = Flask(__name__)
app.url_map.strict_slashes = False


class ApiError(Exception):
    def __init__(self, status, message="", payload=None, text=False):
        super().__init__(message)
        self.status = status
        self.message = message
        self.payload = payload
        self.text = text


def J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":")), status=status, mimetype="application/json")


def T(text, status=200):
    return Response(text, status=status, mimetype="text/plain")


def body():
    b = getattr(request, "_cached_body", None)
    if b is not None:
        return b
    raw = request.get_data(cache=True) or b""
    data = {}
    if raw.strip():
        try:
            data = json.loads(raw.decode("utf-8-sig"))
        except Exception:
            data = dict(request.form) if request.form else {}
    if not isinstance(data, dict):
        data = {"_raw": data}
    if request.args:
        for k, v in request.args.items():
            data.setdefault(k, v)
    if "FunctionArgument" in data and isinstance(data.get("FunctionArgument"), (dict, str)):
        env = data
        fa = data.get("FunctionArgument")
        data = dict(fa) if isinstance(fa, dict) else {"_raw": fa}
        data["_playfab_envelope"] = env
        cep = env.get("CallerEntityProfile") or {}
        lineage = cep.get("Lineage") or {}
        if lineage.get("MasterPlayerAccountId"):
            data.setdefault("PlayFabId", lineage["MasterPlayerAccountId"])
    request._cached_body = data
    return data


def field(d, *names, default=None):
    if not isinstance(d, dict):
        return default
    lower = {k.lower(): v for k, v in d.items()}
    for n in names:
        if n in d and d[n] not in (None, ""):
            return d[n]
    for n in names:
        v = lower.get(n.lower())
        if v not in (None, ""):
            return v
    return default


def as_int(v, default=0):
    try:
        if isinstance(v, bool):
            return int(v)
        return int(float(v))
    except Exception:
        return default


def as_bool(v, default=False):
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def rand_playfab_id():
    return secrets.token_hex(8).upper()


def rand_ticket(pfid):
    return "%s-%s-%s-%s-%s" % (pfid, secrets.token_hex(4).upper(), secrets.token_hex(4).upper(),
                               secrets.token_hex(4).upper(), secrets.token_hex(12).upper())


def rand_entity_token():
    return base64.b64encode(secrets.token_bytes(48)).decode()


def rand_mothership_token():
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"iat": int(time.time()), "exp": int(time.time()) + 86400 * 7,
                                                   "jti": uuid.uuid4().hex}).encode()).decode().rstrip("=")
    return "%s.%s.%s" % (header, payload, secrets.token_urlsafe(32))


KID_PERMISSIONS = ["multiplayer", "mods", "join-groups", "voice-chat", "custom-username"]
GR_TRACK_ID = "a0208736-e696-489b-81cd-c0c772489cc5"
SI_RESOURCE_TYPES = ["TechPoint", "StrangeWood", "WeirdGear", "VibratingSpring", "BouncySand", "FloppyMetal"]
SI_ENTITLEMENT = {"TechPoint": "SI_TechPoints", "StrangeWood": "SI_StrangeWood", "WeirdGear": "SI_WeirdGear",
                  "VibratingSpring": "SI_VibratingSpring", "BouncySand": "SI_BouncySand", "FloppyMetal": "SI_FloppyMetal"}


def new_player(playfab_id=None, mothership_id=None, platform="Steam", external_id=None):
    pfid = (playfab_id or rand_playfab_id()).upper()
    msid = mothership_id or str(uuid.uuid4())
    now = iso()
    p = {
        "PlayFabId": pfid,
        "MothershipId": msid,
        "SessionTicket": rand_ticket(pfid),
        "EntityToken": rand_entity_token(),
        "EntityId": secrets.token_hex(8).upper(),
        "EntityType": "title_player_account",
        "MothershipToken": rand_mothership_token(),
        "Platform": platform or "Steam",
        "ExternalId": external_id or "",
        "SteamAuthIdForPhoton": "gtag-" + secrets.token_hex(6),
        "DisplayName": "gorilla" + str(random.randint(1000, 9999)),
        "Nickname": "gorilla",
        "Created": now,
        "LastSeen": now,
        "Banned": None,
        "Currency": {"SR": CFG["starting_shiny_rocks"], "RM": 0, "TC": 0},
        "Inventory": {},
        "Entitlements": {},
        "ReadOnlyData": {},
        "UserData": {},
        "SharedGroup": {},
        "Privacy": "VISIBLE",
        "Presence": {"RoomId": "", "Zone": "", "SubZone": "", "Region": "", "IsPublic": False, "Nickname": ""},
        "Ranked": {"PC": {"elo": 100.0}, "Quest": {"elo": 100.0}},
        "CompetitiveUnlocked": False,
        "Progression": {},
        "Trees": {"GRTools": [], "SI_Gadgets": []},
        "GR": {
            "ShiftCredits": CFG["starting_shift_credits"],
            "CapIncreases": 0,
            "CapIncreasesMax": CFG["shift_credit_cap_increases_max"],
            "Juicer": {"queue": 0, "processing_started": None, "overdrive": 0, "processed_by_overdrive": 0},
            "DockWrist": {"u1": 0, "u2": 0, "u3": 0},
            "MaxDepthReached": 0,
            "InventoryJson": "",
            "Shifts": {},
        },
        "SI": {"day": si_day_key(), "TodayClaimableQuests": 3, "TodayClaimableBonus": 1, "TodayClaimableIdol": 1},
        "Quests": {"dailyPoints": {}, "weeklyPoints": {}, "userPointsTotal": 0, "completed": []},
        "KID": None,
        "Subscription": None,
        "Redeemed": {},
        "DearLemming": {"last": None, "messages": []},
        "Votes": {},
        "Agreements": {},
        "AutomuteLevel": "none",
    }
    if CFG["kid_mode"] == "adult":
        p["KID"] = kid_default_session_adult()
    DB.set("players", pfid, p)
    DB.set("idx_ms", msid, pfid)
    DB.set("idx_ticket", p["SessionTicket"], pfid)
    DB.set("idx_mstoken", p["MothershipToken"], pfid)
    if external_id:
        DB.set("idx_ext", "%s:%s" % (platform, external_id), pfid)
    return p


def save_player(p):
    p["LastSeen"] = iso()
    DB.set("players", p["PlayFabId"], p)
    return p


def get_player(pfid):
    return DB.get("players", (pfid or "").upper())


def player_by_ms(msid):
    pfid = DB.get("idx_ms", msid)
    return get_player(pfid) if pfid else None


def player_by_ext(platform, ext):
    pfid = DB.get("idx_ext", "%s:%s" % (platform, ext))
    return get_player(pfid) if pfid else None


def touch(p):
    last = parse_iso(p.get("LastSeen"))
    if not last or (utcnow() - last).total_seconds() > 30:
        save_player(p)


def resolve_player(create=True, require=True):
    b = body()
    h = request.headers
    ms_id = field(b, "mothershipId", "MothershipId", "MothershipPlayerId") or h.get("X-Mothership-Player-Id")
    ms_tok = field(b, "mothershipToken", "MothershipToken") or h.get("X-Mothership-Token")
    pf_id = field(b, "PlayFabId", "playFabID", "playFabId", "playfabId") or h.get("X-PlayerId")
    pf_tk = field(b, "PlayFabTicket", "SessionTicket", "playFabSessionTicket", "Ticket") or h.get("X-Authorization")
    strict = CFG["strict_auth"]

    p = None
    if pf_id:
        p = get_player(pf_id)
    if p is None and ms_id:
        p = player_by_ms(ms_id)
    if p is None and pf_tk:
        pfid = DB.get("idx_ticket", pf_tk)
        p = get_player(pfid) if pfid else None
    if p is None and ms_tok:
        pfid = DB.get("idx_mstoken", ms_tok)
        p = get_player(pfid) if pfid else None

    if p is None:
        if not create or (not ms_id and not pf_id):
            if require:
                raise ApiError(401, "Unauthorized: unknown player")
            return None
        if strict:
            raise ApiError(401, "Unauthorized: unknown player")
        p = new_player(playfab_id=pf_id, mothership_id=ms_id)
    else:
        changed = False
        if ms_id and p.get("MothershipId") != ms_id and not player_by_ms(ms_id):
            DB.set("idx_ms", ms_id, p["PlayFabId"])
            p["MothershipId"] = ms_id
            changed = True
        if strict:
            if ms_tok and ms_tok != p.get("MothershipToken"):
                raise ApiError(401, "Unauthorized: bad mothership token")
            if pf_tk and pf_tk != p.get("SessionTicket"):
                raise ApiError(401, "Unauthorized: bad session ticket")
        else:
            if ms_tok and ms_tok != p.get("MothershipToken"):
                DB.set("idx_mstoken", ms_tok, p["PlayFabId"])
                p["MothershipToken"] = ms_tok
                changed = True
            if pf_tk and pf_tk != p.get("SessionTicket"):
                DB.set("idx_ticket", pf_tk, p["PlayFabId"])
                p["SessionTicket"] = pf_tk
                changed = True
        if changed:
            save_player(p)
    if p.get("Banned") and is_ban_active(p["Banned"]):
        raise ApiError(403, "Banned", {"BanMessage": p["Banned"].get("BanMessage", "You are banned."),
                                       "BanExpirationTime": p["Banned"].get("BanExpirationTime", "Indefinite")})
    touch(p)
    return p


def is_ban_active(ban):
    exp = ban.get("BanExpirationTime")
    if not exp or exp == "Indefinite":
        return True
    d = parse_iso(exp)
    return d is None or d > utcnow()


def ent_get(p, name):
    return int(p["Entitlements"].get(name, 0))


def ent_add(p, name, delta):
    p["Entitlements"][name] = max(0, ent_get(p, name) + int(delta))
    return p["Entitlements"][name]


def sr_get(p):
    return int(p["Currency"].get("SR", 0))


def sr_add(p, delta):
    p["Currency"]["SR"] = max(0, sr_get(p) + int(delta))
    return p["Currency"]["SR"]


def grant_item(p, item_id, catalog="DLC"):
    if item_id and item_id not in p["Inventory"]:
        p["Inventory"][item_id] = {"ItemId": item_id, "CatalogVersion": catalog, "PurchaseDate": iso(),
                                   "ItemInstanceId": secrets.token_hex(8).upper()}
        rebuild_shared_group(p)
        return True
    return False


def revoke_item(p, item_id):
    if item_id in p["Inventory"]:
        p["Inventory"].pop(item_id, None)
        rebuild_shared_group(p)
        return True
    return False


def rebuild_shared_group(p):
    ids = list(p["Inventory"].keys())
    p["SharedGroup"]["Inventory"] = "".join(ids)
    p["SharedGroup"]["InventoryDict"] = json.dumps({i: 1 for i in ids}, separators=(",", ":"))
    if p.get("Subscription"):
        s = p["Subscription"]
        p["SharedGroup"]["subscriptions.fan_club"] = json.dumps(
            {"Sku": s.get("Sku", "fan_club"), "ExpirationTime": s.get("End"),
             "TotalLifetimeSeconds": subscription_lifetime_seconds(s)}, separators=(",", ":"))
    else:
        p["SharedGroup"].pop("subscriptions.fan_club", None)


_J = lambda o: json.dumps(o, separators=(",", ":"))
DEFAULT_TITLE_DATA = {
    "KIDData": _J({"KIDEnabled": "true", "KIDPhase": 5,
                   "KIDNewPlayerIsoTimestamp": "2025-04-01T00:00:00Z",
                   "KIDSetupConfirmation": "k-ID setup is now complete. Thanks and have fun in Gorilla World!"}),
    "DeployFeatureFlags": _J({"flags": [
        {"name": "2025-04-KIDOptIn", "value": 100, "valueType": "percent", "alwaysOnForUsers": []},
        {"name": "2025-04-KIDRequired", "value": 0, "valueType": "percent", "alwaysOnForUsers": []},
        {"name": "2026-05-RoomControlsEnabled", "value": 100, "valueType": "percent", "alwaysOnForUsers": []},
        {"name": "2026-04-VStumpGrabbablesFix", "value": 100, "valueType": "percent", "alwaysOnForUsers": []},
        {"name": "2026-04-SuppressZonesInVStump", "value": 100, "valueType": "percent", "alwaysOnForUsers": []},
    ]}),
    "HowManyMonkeCheck": "300",
    "SharedBlocksStartingMapConfig": _J({"pageNumber": 0, "pageSize": 50, "sortMethod": "Top",
                                         "useMapID": False, "mapID": ""}),
    "EnableLckCosmetics": "true",
    "EnableTempCosmeticUnlocks": "true",
    "BacktraceSampleRate": "0.0",
    "GorillanalyticsChance": "4320",
    "PublicCrittersGrabSettings": "7",
    "PrivateCrittersGrabSettings": "7",
    "LatestPrivacyPolicyVersion": "1",
    "PrivacyPolicy_1": _J({"English": "PRIVACY POLICY\r\nThis is a private server. Have fun.",
                           "French": "", "German": "", "Spanish": "", "Italian": "", "Japanese": ""}),
    "AnnouncementData": _J({"ShowAnnouncement": "false", "AnnouncementID": "none",
                            "AnnouncementTitle": "", "Message": ""}),
    "BundleData": _J({"Items": []}),
    "TOTD": "[]",
    "CreditsData": _J([{"Title": "PRIVATE SERVER", "Entries": ["gorilla_tag_backend.py"]}]),
    "AllActiveQuests": _J({
        "DailyQuests": [{"selectCount": 3, "name": "Daily", "quests": [
            {"disable": False, "questID": 1001, "weight": 1.0, "category": "Tag", "questName": "TAG 5 PLAYERS",
             "questType": "gameModeObjective", "questOccurenceFilter": "Tag", "requiredOccurenceCount": 5, "requiredZones": ["none"]},
            {"disable": False, "questID": 1002, "weight": 1.0, "category": "Exploration", "questName": "VISIT THE CAVES",
             "questType": "enterLocation", "questOccurenceFilter": "cave", "requiredOccurenceCount": 1, "requiredZones": ["none"]},
            {"disable": False, "questID": 1003, "weight": 1.0, "category": "Gameplay", "questName": "PLAY 3 ROUNDS",
             "questType": "gameModeRound", "questOccurenceFilter": "", "requiredOccurenceCount": 3, "requiredZones": ["none"]},
            {"disable": False, "questID": 1004, "weight": 1.0, "category": "Social", "questName": "MOVE 500 METERS",
             "questType": "moveDistance", "questOccurenceFilter": "", "requiredOccurenceCount": 500, "requiredZones": ["none"]},
        ]}],
        "WeeklyQuests": [{"selectCount": 2, "name": "Weekly", "quests": [
            {"disable": False, "questID": 2001, "weight": 1.0, "category": "Tag", "questName": "TAG 50 PLAYERS",
             "questType": "gameModeObjective", "questOccurenceFilter": "Tag", "requiredOccurenceCount": 50, "requiredZones": ["none"]},
            {"disable": False, "questID": 2002, "weight": 1.0, "category": "Gameplay", "questName": "PLAY 25 ROUNDS",
             "questType": "gameModeRound", "questOccurenceFilter": "", "requiredOccurenceCount": 25, "requiredZones": ["none"]},
        ]}],
    }),
}


def title_data_all():
    d = dict(DEFAULT_TITLE_DATA)
    for k, v in DB.items("titledata"):
        d[k] = v
    return d


def title_data_get(key, default=None):
    v = DB.get("titledata", key)
    if v is None:
        v = DEFAULT_TITLE_DATA.get(key, default)
    return v


def _node(name, cost=None, prereq_nodes=None, prereq_ents=None):
    return {"name": name, "cost": cost or {}, "prereq_nodes": prereq_nodes or [], "prereq_ents": prereq_ents or []}


GR_TREE = [
    _node("ChargeBaton", {}),
    _node("BatonDamage1", {"GR_ResearchPoints": 1}, ["ChargeBaton"]),
    _node("BatonDamage2", {"GR_ResearchPoints": 2}, ["BatonDamage1"], ["Intern"]),
    _node("BatonDamage3", {"GR_ResearchPoints": 3}, ["BatonDamage2"], ["PartTime"]),
    _node("EnergyEfficiency", {}),
    _node("EnergyEff1", {"GR_ResearchPoints": 1}, ["EnergyEfficiency"]),
    _node("EnergyEff2", {"GR_ResearchPoints": 2}, ["EnergyEff1"], ["Intern"]),
    _node("EnergyEff3", {"GR_ResearchPoints": 3}, ["EnergyEff2"], ["PartTime"]),
    _node("Collector", {}),
    _node("CollectorBonus1", {"GR_ResearchPoints": 1}, ["Collector"]),
    _node("CollectorBonus2", {"GR_ResearchPoints": 2}, ["CollectorBonus1"], ["Intern"]),
    _node("CollectorBonus3", {"GR_ResearchPoints": 3}, ["CollectorBonus2"], ["PartTime"]),
    _node("Lantern", {}),
    _node("LanternIntensity1", {"GR_ResearchPoints": 1}, ["Lantern"]),
    _node("LanternIntensity2", {"GR_ResearchPoints": 2}, ["LanternIntensity1"], ["Intern"]),
    _node("LanternIntensity3", {"GR_ResearchPoints": 3}, ["LanternIntensity2"], ["PartTime"]),
    _node("FlashTool", {"GR_ResearchPoints": 2}),
    _node("FlashDamage1", {"GR_ResearchPoints": 1}, ["FlashTool"]),
    _node("FlashDamage2", {"GR_ResearchPoints": 2}, ["FlashDamage1"], ["Intern"]),
    _node("FlashDamage3", {"GR_ResearchPoints": 3}, ["FlashDamage2"], ["PartTime"]),
    _node("Revive", {"GR_ResearchPoints": 2}, [], ["Intern"]),
    _node("ShieldGun", {"GR_ResearchPoints": 3}, [], ["Intern"]),
    _node("ShieldGunStrength1", {"GR_ResearchPoints": 1}, ["ShieldGun"]),
    _node("ShieldGunStrength2", {"GR_ResearchPoints": 2}, ["ShieldGunStrength1"], ["PartTime"]),
    _node("ShieldGunStrength3", {"GR_ResearchPoints": 3}, ["ShieldGunStrength2"], ["FullTime"]),
    _node("DirectionalShield", {"GR_ResearchPoints": 3}, [], ["PartTime"]),
    _node("DirectionalShieldSize1", {"GR_ResearchPoints": 1}, ["DirectionalShield"]),
    _node("DirectionalShieldSize2", {"GR_ResearchPoints": 2}, ["DirectionalShieldSize1"], ["PartTime"]),
    _node("DirectionalShieldSize3", {"GR_ResearchPoints": 3}, ["DirectionalShieldSize2"], ["FullTime"]),
    _node("DockWrist", {"GR_ResearchPoints": 2}, [], ["Intern"]),
    _node("StatusWatch", {"GR_ResearchPoints": 1}),
    _node("RattyBackpack", {"GR_ResearchPoints": 2}, [], ["PartTime"]),
    _node("DropPodBasic", {}),
    _node("DropPodChassis01", {"GR_ResearchPoints": 3}, ["DropPodBasic"], ["Intern"]),
    _node("DropPodChassis02", {"GR_ResearchPoints": 4}, ["DropPodChassis01"], ["PartTime"]),
    _node("DropPodChassis03", {"GR_ResearchPoints": 5}, ["DropPodChassis02"], ["FullTime"]),
]

SI_UPGRADES = [
    "Thruster_Unlock", "Thruster_Jet", "Thruster_Prop", "Thruster_Jet_Duration", "Thruster_Jet_Accel",
    "Thruster_Prop_Duration", "Thruster_Prop_Speed", "Thruster_Jet_Tag", "Thruster_Prop_Knockback",
    "Thruster_Fuel_Grounding", "Thruster_Throttle_Control",
    "Stilt_Unlock", "Stilt_Tag_Tip", "Stilt_Retractable", "Stilt_Adjustable_Length", "Stilt_Retract_Speed",
    "Stilt_Max_Length", "Stilt_Stun_Tip", "Stilt_Muscle_Fusion", "Stilt_Short", "Stilt_Long", "Stilt_Motorized",
    "Stilt_Motorized_Triple", "Stilt_Turkey_Coma",
    "Grenade_Concussion_Unlock", "Grenade_Antigravity_Unlock", "Grenade_Concussion_Stun", "Grenade_Concussion_Radius",
    "Grenade_Antigravity_Persists", "Grenade_Antigravity_Cooldown", "Grenade_Concussion_Self_Boost",
    "Grenade_Concussion_Overcharge", "Grenade_Antigravity_Pro_Gravity", "Grenade_Concussion_Impact_Accelerant",
    "Grenade_Antigravity_Gravity_Bomb", "Grenade_Antigravity_Black_Hole", "Grenade_Holster_Unlock",
    "Grenade_Stun_Unlock", "Grenade_Puller_Unlock", "Grenade_Disrupter_Unlock",
    "Dash_Yoyo_Unlock", "Dash_Yoyo_Range", "Dash_Yoyo_Speed", "Dash_Yoyo_Cooldown", "Dash_Yoyo_Dynamic",
    "Dash_Yoyo_Stun", "Dash_Yoyo_Tag",
    "Platform_Unlock", "Platform_Cooldown", "Platform_Duration", "Platform_Capacity", "Platform_SpeedBoost",
    "Tapteleport_Unlock", "Tapteleport_Zone", "Tapteleport_Stealth", "Tapteleport_Portal_Selection",
    "Tapteleport_Keep_Velocity", "Tapteleport_Infinite_Use",
    "Tentacle_Unlock", "Tentacle_Power_Claw", "Tentacle_Charge_Rate", "Tentacle_Efficiency", "Tentacle_Crawler",
    "Tentacle_Strider",
    "AirControl_AirJuke_Unlock", "AirControl_AirJuke_Speed", "AirControl_AirGrab_Unlock", "AirControl_AirGrab_Speed",
    "AirControl_AirGrab_HoldTime", "AirControl_Zipline_Unlock", "AirControl_Zipline_Speed",
]


def _si_tree():
    nodes = [_node("Initialize", {})]
    roots = {}
    for name in SI_UPGRADES:
        family = name.split("_")[0]
        is_unlock = name.endswith("_Unlock")
        if is_unlock and family not in roots:
            roots[family] = name
            nodes.append(_node(name, {"SI_TechPoints": 1}, ["Initialize"]))
        elif is_unlock:
            nodes.append(_node(name, {"SI_TechPoints": 1}, [roots[family]]))
        else:
            cost = {"SI_TechPoints": 1}
            res = ["SI_StrangeWood", "SI_WeirdGear", "SI_VibratingSpring", "SI_BouncySand", "SI_FloppyMetal"]
            cost[res[len(nodes) % 5]] = 3
            nodes.append(_node(name, cost, [roots.get(family, "Initialize")]))
    return nodes


SI_TREE = _si_tree()
TREES = {"GRTools": GR_TREE, "SI_Gadgets": SI_TREE}
TREE_IDS = {"GRTools": "5c1f0a2e-0001-4a3b-9c1d-47725f736f6c", "SI_Gadgets": "5c1f0a2e-0002-4a3b-9c1d-53495f676164"}


def node_id(tree, name):
    return "%s:%s" % (tree, name)


def hydrated_tree(p, tree_name):
    tree = TREES[tree_name]
    unlocked = set(p["Trees"].get(tree_name, []))
    nodes = []
    for n in tree:
        nodes.append({
            "id": node_id(tree_name, n["name"]),
            "name": n["name"],
            "unlocked": n["name"] in unlocked,
            "cost": {"items": {k: {"Delta": v} for k, v in n["cost"].items()}},
            "prerequisite_entitlements": [{"name": e} for e in n["prereq_ents"]],
            "prerequisite_nodes": {"nodes": [{"node_id": node_id(tree_name, x)} for x in n["prereq_nodes"]]},
        })
    return {"Tree": {"name": tree_name, "id": TREE_IDS[tree_name]}, "Track": GR_TRACK_ID if tree_name == "GRTools" else "",
            "Nodes": nodes}


def find_node(tree_name, node_ref):
    for n in TREES.get(tree_name, []):
        if node_ref in (n["name"], node_id(tree_name, n["name"])):
            return n
    return None


def unlock_node(p, tree_name, node_ref, charge=True):
    n = find_node(tree_name, node_ref)
    if n is None:
        raise ApiError(404, "Unknown node")
    unlocked = p["Trees"].setdefault(tree_name, [])
    if n["name"] in unlocked:
        return False
    if charge:
        for k, v in n["cost"].items():
            if ent_get(p, k) < v:
                raise ApiError(400, "Insufficient %s" % k)
        for k, v in n["cost"].items():
            ent_add(p, k, -v)
    unlocked.append(n["name"])
    if tree_name == "SI_Gadgets" and n["name"] == "Initialize":
        for e in ["SI_TechPoints"]:
            ent_add(p, e, 3)
    return True


def inventory_response(p):
    ents = [{"entitlement_id": hashlib.md5(k.encode()).hexdigest(), "in_game_id": k, "name": k, "quantity": int(v)}
            for k, v in p["Entitlements"].items()]
    plat = (p.get("Platform") or "steam").lower()
    return {"Results": {plat: {"platform": plat, "isPrimary": True, "entitlements": ents}}}


def kid_session_obj(age_status, managed_by, perms, dob, etag, session_id, kid_status="ACTIVE"):
    cat = {"LEGAL_ADULT": "adult", "DIGITAL_YOUTH": "digital-youth", "DIGITAL_MINOR": "digital-minor"}[age_status]
    return {
        "status": kid_status,
        "ageStatus": age_status,
        "ageCategory": cat,
        "managedBy": managed_by,
        "sessionId": session_id,
        "kuid": "kuid-" + session_id[:8],
        "etag": str(etag),
        "permissions": [{"name": n, "enabled": bool(en), "managedBy": mb} for (n, en, mb) in perms],
        "dateOfBirth": dob,
        "jurisdiction": "US",
    }


def kid_default_session_adult():
    sid = str(uuid.uuid4())
    perms = [(n, True, "PLAYER") for n in KID_PERMISSIONS]
    return {
        "OptedIn": True,
        "Status": 0,
        "Session": kid_session_obj("LEGAL_ADULT", "PLAYER", perms, "1990-01-01", 1, sid),
        "DefaultSession": None,
        "OptInPermissions": list(KID_PERMISSIONS),
        "HasConfirmedSetup": True,
        "Email": "",
        "Age": 30,
        "Etag": 1,
    }


def kid_state(p):
    if p.get("KID") is None:
        p["KID"] = {"OptedIn": False, "Status": None, "Session": None, "DefaultSession": None,
                    "OptInPermissions": [], "HasConfirmedSetup": False, "Email": "", "Age": 0, "Etag": 0}
    return p["KID"]


def kid_requirements():
    return {"shouldDisplay": True, "ageAssuranceRequired": False, "digitalConsentAge": 13, "civilAge": 18,
            "minimumAge": 13, "approvedAgeCollectionMethods": ["age-gate"]}


def kid_build_session_for_age(k, age):
    req = kid_requirements()
    k["Etag"] = int(k.get("Etag", 0)) + 1
    k["Age"] = age
    sid = str(uuid.uuid4())
    year = utcnow().year - age
    dob = "%04d-01-01" % max(1900, year)
    if age < req["minimumAge"]:
        k["Status"] = 1
        perms = [(n, False, "PROHIBITED") for n in KID_PERMISSIONS]
        k["Session"] = kid_session_obj("DIGITAL_MINOR", "GUARDIAN", perms, dob, k["Etag"], sid, "HOLD")
    elif age < req["civilAge"]:
        k["Status"] = 0
        perms = [(n, True, "PLAYER") for n in KID_PERMISSIONS]
        k["Session"] = kid_session_obj("DIGITAL_YOUTH", "PLAYER", perms, dob, k["Etag"], sid)
    else:
        k["Status"] = 0
        perms = [(n, True, "PLAYER") for n in KID_PERMISSIONS]
        k["Session"] = kid_session_obj("LEGAL_ADULT", "PLAYER", perms, dob, k["Etag"], sid)
    k["OptInPermissions"] = [pn for (pn, en, mb) in perms if en]
    k["OptedIn"] = True
    return k


MIN_ELO, MAX_ELO, DEFAULT_ELO = 100.0, 4000.0, 100.0
MAX_ELO_CONSTANT = 90.0
TIERS = [
    ("Low", [("Wood", 200.0), ("Rock", 700.0)]),
    ("Medium", [("Bronze", 1200.0), ("Silver", 1700.0), ("Gold", 2200.0)]),
    ("High", [("Platinum", 2850.0), ("Crystal", 3500.0), ("Banana", 4000.0)]),
]


def tier_for_elo(elo):
    elo = max(MIN_ELO, min(MAX_ELO, float(elo)))
    lo = MIN_ELO
    for mi, (mname, subs) in enumerate(TIERS):
        for si, (sname, smax) in enumerate(subs):
            last = (mi == len(TIERS) - 1 and si == len(subs) - 1)
            if elo < smax or last:
                span = max(1.0, smax - lo)
                prog = max(0.0, min(1.0, (elo - lo) / span))
                return mi, si, prog, mname, sname
            lo = smax
    return 0, 0, 0.0, "Low", "Wood"


def platform_data(p, plat):
    elo = float(p["Ranked"].get(plat, {}).get("elo", DEFAULT_ELO))
    mi, si, prog, _, _ = tier_for_elo(elo)
    return {"platform": plat, "elo": round(elo, 2), "majorTier": mi, "minorTier": si, "rankProgress": round(prog, 4)}


def apply_match_elo(match, scores):
    plat = match.get("platform") or "PC"
    entries = []
    for s in scores:
        pl = get_player(s.get("playfabId") or "")
        if pl is None:
            continue
        entries.append((pl, float(s.get("gameScore") or 0.0)))
    n = len(entries)
    if n < 2:
        return {}
    k = MAX_ELO_CONSTANT / (n - 1)
    old = [float(pl["Ranked"].setdefault(plat, {"elo": DEFAULT_ELO})["elo"]) for pl, _ in entries]
    deltas = []
    for i, (pi, si) in enumerate(entries):
        d = 0.0
        for j, (pj, sj) in enumerate(entries):
            if i == j:
                continue
            expected = 1.0 / (1.0 + 10 ** ((old[j] - old[i]) / 400.0))
            actual = 1.0 if si > sj else (0.5 if si == sj else 0.0)
            d += k * (actual - expected)
        deltas.append(d)
    result = {}
    for (pl, _), o, d in zip(entries, old, deltas):
        new = max(MIN_ELO, min(MAX_ELO, o + d))
        pl["Ranked"][plat]["elo"] = new
        pl["Ranked"][plat]["matches"] = int(pl["Ranked"][plat].get("matches", 0)) + 1
        save_player(pl)
        result[pl["PlayFabId"]] = {"old": o, "new": new}
    return result


def _nth_sunday(year, month, n):
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(6 - d.weekday()) % 7)
    return d + dt.timedelta(days=7 * (n - 1))


def us_pacific_dst(now):
    y = now.year
    start = dt.datetime.combine(_nth_sunday(y, 3, 2), dt.time(10, 0), tzinfo=UTC)
    end = dt.datetime.combine(_nth_sunday(y, 11, 1), dt.time(9, 0), tzinfo=UTC)
    return start <= now < end


def daily_quest_set_id(now=None):
    now = now or utcnow()
    epoch = dt.datetime(2025, 1, 10, 18, 0, tzinfo=UTC)
    if us_pacific_dst(now):
        epoch -= dt.timedelta(hours=1)
    return (now - epoch).days


def weekly_quest_set_id(now=None):
    return daily_quest_set_id(now) // 7


def quest_status_payload(p):
    q = p["Quests"]
    return {"dailyPoints": dict(q.get("dailyPoints") or {}),
            "weeklyPoints": {str(k): v for k, v in (q.get("weeklyPoints") or {}).items()},
            "userPointsTotal": int(q.get("userPointsTotal", 0))}


def weekly_points_sum(p):
    q = p["Quests"]
    return sum((q.get("dailyPoints") or {}).values()) + sum((q.get("weeklyPoints") or {}).values())


def all_quest_ids():
    try:
        d = json.loads(title_data_get("AllActiveQuests", "{}"))
    except Exception:
        return None
    ids = {"daily": set(), "weekly": set()}
    for g in d.get("DailyQuests") or []:
        for q in g.get("quests") or []:
            ids["daily"].add(as_int(q.get("questID")))
    for g in d.get("WeeklyQuests") or []:
        for q in g.get("quests") or []:
            ids["weekly"].add(as_int(q.get("questID")))
    return ids


def si_day_key(now=None):
    now = now or utcnow()
    return (now - dt.timedelta(hours=1)).strftime("%Y-%m-%d")


def si_state(p):
    s = p["SI"]
    day = si_day_key()
    if s.get("day") != day:
        s["day"] = day
        s["TodayClaimableQuests"] = min(6, int(s.get("TodayClaimableQuests", 0)) + 3)
        s["TodayClaimableBonus"] = min(2, int(s.get("TodayClaimableBonus", 0)) + 1)
        s["TodayClaimableIdol"] = 1
    return s


def si_status(p):
    s = si_state(p)
    return {"TodayClaimableQuests": int(s["TodayClaimableQuests"]), "TodayClaimableBonus": int(s["TodayClaimableBonus"]),
            "TodayClaimableIdol": int(s["TodayClaimableIdol"])}


def si_active_quests():
    stored = DB.get("config", "SIQuests")
    if stored:
        return stored
    quests = []
    defs = [
        ("Tag", "TAG 3 PLAYERS", "gameModeObjective", "Tag", 3),
        ("Exploration", "VISIT 2 ZONES", "enterLocation", "", 2),
        ("Gameplay", "PLAY 2 ROUNDS", "gameModeRound", "", 2),
        ("Social", "GRAB 10 OBJECTS", "grabObject", "", 10),
        ("GameRound", "SURVIVE A ROUND", "gameModeRound", "Survive", 1),
        ("Tag", "TAG 10 PLAYERS", "gameModeObjective", "Tag", 10),
    ]
    for i, (cat, name, qtype, filt, cnt) in enumerate(defs):
        quests.append({"disable": False, "questID": i, "weight": 1.0, "category": cat, "questName": name,
                       "questType": qtype, "questOccurenceFilter": filt, "requiredOccurenceCount": cnt,
                       "requiredZones": ["none"]})
    return quests


def subscription_lifetime_seconds(s):
    start = parse_iso(s.get("Start")) or utcnow()
    end = min(parse_iso(s.get("End")) or utcnow(), utcnow())
    return int(s.get("LifetimeSeconds", 0)) + max(0, int((end - start).total_seconds()))


def subscription_payload(p):
    s = p.get("Subscription")
    if not s:
        return {"Subscriptions": [], "PreviouslyGrantedBenefitsBySubscriptionSku": {},
                "NewlyGrantedBenefitsBySubscriptionSku": {}, "SharedGroupDataUpdateSucceeded": True}
    end = parse_iso(s.get("End")) or utcnow()
    start = parse_iso(s.get("Start")) or utcnow()
    active = end > utcnow()
    sub = {
        "SubscriptionId": s.get("SubscriptionId") or "sub_" + p["PlayFabId"].lower(),
        "EarliestStartDate": start.isoformat(),
        "CurrentStartDate": start.isoformat(),
        "MostRecentBillingCycleStartDate": (parse_iso(s.get("CycleStart")) or start).isoformat(),
        "MostRecentBillingCycleEndDate": end.isoformat(),
        "TotalLifetimeSeconds": subscription_lifetime_seconds(s),
        "IsActive": active,
        "IsCancelling": bool(s.get("Cancelling", False)),
        "Sku": s.get("Sku", "fan_club"),
        "PlayerId": p["MothershipId"],
        "TrialType": None,
        "ExternalServiceName": s.get("ExternalServiceName", "Steam"),
        "ExternalSubscriptionId": s.get("ExternalSubscriptionId", "40494"),
        "SubscriptionCatalogItemId": s.get("SubscriptionCatalogItemId", "fan_club_monthly"),
    }
    return {"Subscriptions": [sub],
            "PreviouslyGrantedBenefitsBySubscriptionSku": {sub["Sku"]: s.get("Benefits", [])},
            "NewlyGrantedBenefitsBySubscriptionSku": {},
            "SharedGroupDataUpdateSucceeded": True}


MAP_ID_ALPHABET = "CFGHKMNPRTWXZ256789"
MAP_ID_RE = re.compile(r"^[CFGHKMNPRTWXZ256789]{8}$")


def new_map_id():
    while True:
        mid = "".join(secrets.choice(MAP_ID_ALPHABET) for _ in range(8))
        if DB.get("maps", mid) is None:
            return mid


def decode_map_data(s):
    if not s:
        return None
    s = s.strip()
    if s.startswith("{"):
        return json.loads(s)
    raw = base64.b64decode(s)
    return json.loads(gzip.decompress(raw).decode("utf-8"))


def encode_map_data(obj):
    js = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(gzip.compress(js)).decode()


def ccu_count():
    override = DB.get("config", "CCUOverride")
    if override is not None:
        return int(override)
    window = CFG["ccu_window_sec"]
    n = 0
    for _, pl in DB.items("players"):
        if _recently_seen(pl, window):
            n += 1
    return n


@app.before_request
def _lock_in():
    LOCK.acquire()
    request._locked = True


@app.teardown_request
def _lock_out(exc):
    if getattr(request, "_locked", False):
        request._locked = False
        try:
            LOCK.release()
        except RuntimeError:
            pass


def _with_reason(resp, status, message):
    msg = (message or "").strip()
    if msg and len(msg) < 120 and all(32 <= ord(c) < 127 for c in msg):
        resp.status = "%d %s" % (status, msg)
    return resp


@app.errorhandler(ApiError)
def _api_error(e):
    if e.text:
        return _with_reason(T(e.message or "", e.status), e.status, e.message)
    if e.payload is not None:
        return _with_reason(J(e.payload, e.status), e.status, e.message)
    return _with_reason(J({"StatusCode": e.status, "Error": e.message or "", "Message": e.message or "",
                           "error": e.message or ""}, e.status), e.status, e.message)


@app.errorhandler(404)
def _nf(e):
    return J({"StatusCode": 404, "Error": "Not Found: %s %s" % (request.method, request.path)}, 404)


@app.errorhandler(Exception)
def _boom(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return J({"StatusCode": e.code, "Error": e.name, "Message": e.description}, e.code)
    app.logger.exception("Unhandled error on %s %s", request.method, request.path)
    return J({"StatusCode": 500, "Error": "InternalServerError-UnhandledException", "Message": str(e)}, 500)


def route(path, methods=("POST",)):
    def deco(fn):
        paths = [path]
        if path.startswith("/api/"):
            paths.append(path[4:])
        else:
            paths.append("/api" + path)
        for pth in paths:
            ep = re.sub(r"[^A-Za-z0-9_]", "_", fn.__name__ + pth)
            app.add_url_rule(pth, endpoint=ep, view_func=fn, methods=list(methods))
        return fn
    return deco


def _recently_seen(p, window):
    d = parse_iso(p.get("LastSeen"))
    return bool(d) and (utcnow() - d).total_seconds() <= window


def daily_login(p):
    today = utcnow().strftime("%Y-%m-%d")
    if p["ReadOnlyData"].get("DailyLogin") != today:
        p["ReadOnlyData"]["DailyLogin"] = today
        sr_add(p, CFG["daily_login_shiny_rocks"])
        return True
    return False


def _ban_payload(p):
    return {"BanMessage": p["Banned"].get("BanMessage", "You are banned."),
            "BanExpirationTime": p["Banned"].get("BanExpirationTime", "Indefinite")}


def _fresh_session(p):
    DB.delete("idx_ticket", p.get("SessionTicket", ""))
    p["SessionTicket"] = rand_ticket(p["PlayFabId"])
    p["EntityToken"] = rand_entity_token()
    DB.set("idx_ticket", p["SessionTicket"], p["PlayFabId"])


def _nonce_new():
    n = secrets.token_hex(16)
    DB.set("nonces", n, {"created": time.time()})
    for k in DB.oldest_keys("nonces", 50):
        rec = DB.get("nonces", k) or {}
        if time.time() - float(rec.get("created", 0)) > CFG["nonce_ttl_sec"]:
            DB.delete("nonces", k)
    return n


def _mothership_login(platform, ext, ms_id):
    p = player_by_ext(platform, ext) if ext else None
    if p is None and ms_id:
        p = player_by_ms(ms_id)
    if p is None:
        p = new_player(mothership_id=ms_id, platform=platform, external_id=ext)
    if p.get("Banned") and is_ban_active(p["Banned"]):
        raise ApiError(403, "Banned", _ban_payload(p))
    DB.delete("idx_mstoken", p.get("MothershipToken", ""))
    p["MothershipToken"] = rand_mothership_token()
    DB.set("idx_mstoken", p["MothershipToken"], p["PlayFabId"])
    _fresh_session(p)
    daily_login(p)
    save_player(p)
    tok = p["MothershipToken"]
    expires = iso(utcnow() + dt.timedelta(days=7))
    return J({"mothershipToken": tok, "MothershipToken": tok, "token": tok,
              "mothershipId": p["MothershipId"], "MothershipId": p["MothershipId"],
              "PlayerId": p["MothershipId"], "player_id": p["MothershipId"],
              "PlayFabId": p["PlayFabId"], "SessionTicket": p["SessionTicket"], "EntityToken": p["EntityToken"],
              "EntityId": p["EntityId"], "EntityType": p["EntityType"],
              "TitleId": CFG["mothership_title_id"], "EnvId": CFG["mothership_env_id"],
              "DeploymentId": CFG["mothership_deployment_id"],
              "expiresAt": expires, "AccountCreationIsoTimestamp": p["Created"]})


def _playfab_login_data(p, newly):
    ent = {"Id": p["EntityId"], "Type": p["EntityType"], "TypeString": p["EntityType"]}
    return {
        "SessionTicket": p["SessionTicket"],
        "PlayFabId": p["PlayFabId"],
        "NewlyCreated": newly,
        "SettingsForUser": {"NeedsAttribution": False, "GatherDeviceInfo": True, "GatherFocusInfo": True},
        "LastLoginTime": iso_short(),
        "InfoResultPayload": {
            "AccountInfo": {"PlayFabId": p["PlayFabId"], "Created": p["Created"],
                            "TitleInfo": {"DisplayName": p.get("DisplayName"), "Origination": "Steam",
                                          "Created": p["Created"], "LastLogin": iso_short(), "FirstLogin": p["Created"],
                                          "isBanned": False, "TitlePlayerAccount": ent}},
            "UserVirtualCurrency": dict(p["Currency"]),
            "UserInventory": list(p["Inventory"].values()),
            "PlayerProfile": {"PlayerId": p["PlayFabId"], "DisplayName": p.get("DisplayName"), "TitleId": CFG["title_id"]},
        },
        "EntityToken": {"EntityToken": p["EntityToken"],
                        "TokenExpiration": iso_short(utcnow() + dt.timedelta(days=1)),
                        "Entity": ent},
        "TreatmentAssignment": {"Variants": [], "Variables": []},
    }


def self_check():
    checks = {}
    try:
        k = "selfcheck-" + secrets.token_hex(4)
        DB.set("selfcheck", k, {"ok": True})
        checks["database_write"] = DB.get("selfcheck", k) == {"ok": True}
        DB.delete("selfcheck", k)
        checks["database_read"] = DB.get("selfcheck", k) is None
    except Exception as e:
        checks["database_write"] = False
        checks["database_error"] = str(e)
    try:
        needed = ["/CachePlayFabId", "/Client/LoginWithSteam", "/PlayFabAuthentication", "/api/photon", "/api/TitleData",
                  "/v1/userdata/client", "/api/GetFriendsV2", "/api/GetTier", "/api/CCU", "/health"]
        rules = {r.rule for r in app.url_map.iter_rules()}
        checks["routes_registered"] = all(n in rules for n in needed)
    except Exception:
        checks["routes_registered"] = False
    try:
        json.loads(title_data_get("AllActiveQuests", "{}"))
        checks["title_data"] = True
    except Exception:
        checks["title_data"] = False
    return checks


@app.get("/")
def index():
    checks = self_check()
    good = all(v is True for k, v in checks.items() if k != "database_error")
    rules = sorted({r.rule for r in app.url_map.iter_rules() if r.rule != "/static/<path:filename>"})
    status = "ALL GOOD - SERVER RUNNING FULLY" if good else "PROBLEM - SOMETHING IS NOT WORKING"
    if "text/html" in request.headers.get("Accept", ""):
        rows = "".join("<li>%s: %s</li>" % (k, "OK" if v is True else v) for k, v in checks.items())
        html = ("<html><body style='font-family:sans-serif;text-align:center;margin-top:60px'>"
                "<h1 style='color:%s'>%s</h1><p>%s &middot; players: %d &middot; routes: %d</p>"
                "<ul style='display:inline-block;text-align:left'>%s</ul></body></html>"
                % ("green" if good else "red", status, APP_VERSION, DB.count("players"), len(rules), rows))
        return Response(html, status=200 if good else 500, mimetype="text/html")
    return J({"status": status, "ok": good, "checks": checks, "service": APP_VERSION, "time": iso(),
              "players": DB.count("players"), "endpoints": rules}, 200 if good else 500)


@app.get("/health")
def health():
    checks = self_check()
    good = all(v is True for k, v in checks.items() if k != "database_error")
    return J({"ok": good, "status": "All good" if good else "Problem", "checks": checks, "time": iso()}, 200 if good else 500)


@route("/api/CCU", methods=("GET",))
def ccu():
    return J({"CCUTotal": ccu_count(), "ErrorMessage": None})


@route("/CachePlayFabId")
def cache_playfab_id():
    b = body()
    pf_id = field(b, "PlayFabId")
    if not pf_id:
        raise ApiError(400, "PlayFabId required")
    p = get_player(pf_id)
    ms_id = field(b, "MothershipId")
    if p is None:
        p = player_by_ms(ms_id) if ms_id else None
    if p is None:
        p = new_player(playfab_id=pf_id, mothership_id=ms_id, platform=field(b, "Platform", default="Steam"))
    tk = field(b, "SessionTicket")
    if tk and tk != p.get("SessionTicket"):
        DB.set("idx_ticket", tk, p["PlayFabId"])
        p["SessionTicket"] = tk
    tok = field(b, "MothershipToken")
    if tok and tok != p.get("MothershipToken"):
        DB.set("idx_mstoken", tok, p["PlayFabId"])
        p["MothershipToken"] = tok
    if ms_id and p.get("MothershipId") != ms_id:
        DB.set("idx_ms", ms_id, p["PlayFabId"])
        p["MothershipId"] = ms_id
    p["Platform"] = field(b, "Platform", default=p.get("Platform", "Steam"))
    if p.get("Banned") and is_ban_active(p["Banned"]):
        return J({"Message": p["Banned"].get("BanMessage", "You are banned."), "Error": "Banned"}, 403)
    daily_login(p)
    save_player(p)
    return J({"PlayFabId": p["PlayFabId"], "SteamAuthIdForPhoton": p["SteamAuthIdForPhoton"],
              "AccountCreationIsoTimestamp": p["Created"]})


@route("/Client/LoginWithSteam")
def client_login_with_steam():
    b = body()
    ticket = field(b, "SteamTicket", "steamTicket")
    steam_id = field(b, "SteamId", "SteamID", "steamId", "CustomId")
    if not ticket and not steam_id:
        raise ApiError(400, "InvalidSteamTicket", {"code": 400, "status": "BadRequest", "error": "InvalidSteamTicket",
                                                    "errorCode": 1010, "errorMessage": "Steam ticket is required"})
    ext = str(steam_id) if steam_id else hashlib.sha1(str(ticket)[:64].encode()).hexdigest()[:16]
    p = player_by_ext("Steam", ext)
    newly = False
    if p is None:
        p = new_player(platform="Steam", external_id=ext)
        newly = True
    else:
        _fresh_session(p)
    if p.get("Banned") and is_ban_active(p["Banned"]):
        raise ApiError(403, "AccountBanned", {"code": 403, "status": "Forbidden", "error": "AccountBanned",
                                              "errorCode": 1002, "errorMessage": p["Banned"].get("BanMessage", "You are banned."),
                                              "errorDetails": {"Banned": [p["Banned"].get("BanExpirationTime", "Indefinite")]}})
    daily_login(p)
    save_player(p)
    return J({"code": 200, "status": "OK", "data": _playfab_login_data(p, newly)})


@route("/OnLogin")
def on_login():
    p = resolve_player(create=False, require=False)
    if p is not None:
        daily_login(p)
        save_player(p)
    return J({"ResultCode": 0, "Message": "ok"})


@route("/PlayFabAuthentication")
def playfab_authentication():
    b = body()
    platform = field(b, "Platform", default="Quest") or "Quest"
    ext = field(b, "OculusId", "SteamId", "ExternalId")
    ms_id = field(b, "MothershipId")
    p = None
    if ext:
        p = player_by_ext(platform, ext)
    if p is None and ms_id:
        p = player_by_ms(ms_id)
    if p is None:
        p = new_player(mothership_id=ms_id, platform=platform, external_id=ext)
    else:
        _fresh_session(p)
    tok = field(b, "MothershipToken")
    if tok and tok != p.get("MothershipToken"):
        DB.set("idx_mstoken", tok, p["PlayFabId"])
        p["MothershipToken"] = tok
    if field(b, "AgeCategory"):
        p["AgeCategory"] = field(b, "AgeCategory")
    if p.get("Banned") and is_ban_active(p["Banned"]):
        return J(_ban_payload(p), 403)
    daily_login(p)
    save_player(p)
    return J({"SessionTicket": p["SessionTicket"], "EntityToken": p["EntityToken"], "PlayFabId": p["PlayFabId"],
              "EntityId": p["EntityId"], "EntityType": p["EntityType"], "AccountCreationIsoTimestamp": p["Created"]})


@route("/v1/client/player/auth/RIFT")
def v1_auth_rift():
    b = body()
    ext = field(b, "oculus_id", "OculusId", "user_id", "userId", "platform_user_id", "rift_id", "RiftId")
    return _mothership_login("Rift", ext, field(b, "MothershipId", "mothershipId", "player_id"))


@route("/v2/player/client/auth/begin/QUEST")
def v2_auth_begin_quest():
    n = _nonce_new()
    return J({"nonce": n, "Nonce": n})


@route("/v2/player/client/auth/begin/STEAM", methods=("GET",))
def v2_auth_begin_steam():
    n = _nonce_new()
    return J({"nonce": n, "Nonce": n})


@route("/v2/player/client/auth/complete/QUEST")
def v2_auth_complete_quest():
    b = body()
    nonce = field(b, "nonce", "Nonce")
    if nonce:
        DB.delete("nonces", nonce)
    ext = field(b, "oculus_id", "OculusId", "user_id", "userId", "platform_user_id")
    return _mothership_login("Quest", ext, field(b, "MothershipId", "mothershipId", "player_id"))


@route("/v2/player/client/auth/complete/STEAM")
def v2_auth_complete_steam():
    b = body()
    nonce = field(b, "nonce", "Nonce")
    if nonce:
        DB.delete("nonces", nonce)
    ext = field(b, "steam_id", "SteamId", "steamId", "user_id", "userId", "platform_user_id")
    if not ext:
        ticket = field(b, "ticket", "Ticket", "SteamTicket", "auth_ticket")
        ext = hashlib.sha1(str(ticket)[:64].encode()).hexdigest()[:16] if ticket else None
    return _mothership_login("Steam", ext, field(b, "MothershipId", "mothershipId", "player_id"))


def _userdata_record(p, key):
    rec = p["UserData"].get(key)
    if rec is None:
        return None
    return {"id": rec.get("id"), "metadata_id": rec.get("metadata_id", ""), "key_name": key, "user_id": p["MothershipId"],
            "value": rec.get("value", ""), "generation": int(rec.get("generation", 0)),
            "created_by": rec.get("created_by", p["MothershipId"]), "last_written_by": rec.get("last_written_by", p["MothershipId"]),
            "created_time": rec.get("created_time"), "last_updated_time": rec.get("last_updated_time")}


def _userdata_set(p, key, value, generation=-1, writer=None):
    rec = p["UserData"].get(key)
    if rec is None:
        rec = {"id": str(uuid.uuid4()), "metadata_id": hashlib.md5(("%s:%s" % (p["MothershipId"], key)).encode()).hexdigest(),
               "generation": 0, "created_time": iso(), "created_by": writer or p["MothershipId"]}
    if generation not in (None, -1) and int(generation) != int(rec.get("generation", 0)):
        raise ApiError(409, "Generation conflict")
    rec["value"] = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
    rec["generation"] = int(rec.get("generation", 0)) + 1
    rec["last_updated_time"] = iso()
    rec["last_written_by"] = writer or p["MothershipId"]
    p["UserData"][key] = rec
    return rec


@route("/v1/userdata/client", methods=("GET", "POST"))
def v1_userdata_client():
    b = body()
    caller = resolve_player()
    key = field(b, "key_name", "keyName", "key", "Key", "KeyName")
    target_id = field(b, "user_id", "userId", "targetId", "TargetMothershipId")
    target = player_by_ms(target_id) if target_id else caller
    if target is None:
        raise ApiError(404, "Unknown user")
    if request.method == "POST" and field(b, "value", "Value") is not None:
        if not key:
            raise ApiError(400, "key_name required")
        if target["PlayFabId"] != caller["PlayFabId"]:
            raise ApiError(403, "Cannot write another user's data")
        rec = _userdata_set(target, key, field(b, "value", "Value", default=""), field(b, "generation", default=-1),
                            writer=caller["MothershipId"])
        save_player(target)
        return J({"id": rec["id"], "key_name": key, "user_id": target["MothershipId"], "generation": rec["generation"]})
    if key:
        rec = _userdata_record(target, key)
        if rec is None:
            raise ApiError(404, "Key not found")
        return J(rec)
    return J({"Results": [_userdata_record(target, k) for k in target["UserData"].keys()]})


@route("/v1/files/client/download/<file_id>", methods=("GET",))
def v1_files_client_download(file_id):
    resolve_player(require=False)
    rec = DB.get("files", file_id)
    if rec is None:
        raise ApiError(404, "File not found")
    try:
        data = base64.b64decode(rec.get("data", ""))
    except Exception:
        raise ApiError(500, "Stored file is corrupt")
    return Response(data, status=200, mimetype=rec.get("contentType") or "application/octet-stream")


@route("/v1/inventory/client", methods=("GET",))
def v1_inventory_client():
    p = resolve_player()
    return J(inventory_response(p))


@route("/v1/progression-tree/client", methods=("GET",))
def v1_progression_tree_client():
    p = resolve_player()
    return J({"Results": [hydrated_tree(p, name) for name in TREES]})


@route("/api/GetProgression")
def get_progression():
    p = resolve_player()
    track = field(body(), "TrackId") or GR_TRACK_ID
    return T(str(int(p["Progression"].get(track, 0))))


@route("/api/SetProgression")
def set_progression():
    p = resolve_player()
    b = body()
    track = field(b, "TrackId") or GR_TRACK_ID
    delta = as_int(field(b, "Progress"), 0)
    p["Progression"][track] = int(p["Progression"].get(track, 0)) + delta
    prog = p["Progression"][track]
    for name, threshold in (("Intern", 500), ("PartTime", 2500), ("FullTime", 7500)):
        if prog >= threshold and ent_get(p, name) == 0:
            ent_add(p, name, 1)
    save_player(p)
    return J({"Track": track, "Progress": p["Progression"][track], "StatusCode": 200, "Error": None})


def _tree_name_from_id(tree_ref):
    for name, tid in TREE_IDS.items():
        if tree_ref in (name, tid):
            return name
    if tree_ref and ":" in tree_ref:
        return tree_ref.split(":")[0]
    return None


@route("/api/UnlockProgressionTreeNode")
def unlock_progression_tree_node():
    p = resolve_player()
    b = body()
    tree_ref = field(b, "TreeId", "treeId") or ""
    node_ref = field(b, "NodeId", "nodeId") or ""
    tree_name = _tree_name_from_id(tree_ref) or _tree_name_from_id(node_ref)
    if tree_name is None:
        raise ApiError(404, "Unknown tree")
    unlock_node(p, tree_name, node_ref)
    save_player(p)
    return J({"Tree": hydrated_tree(p, tree_name), "StatusCode": 200, "Error": None})


def _shift_credit_cap(p):
    return 1000 + int(p["GR"]["CapIncreases"]) * 100


def _shift_credit_response(p, target=None):
    g = p["GR"]
    return {"StatusCode": 200, "Error": None, "CurrentShiftCredits": int(g["ShiftCredits"]),
            "CurrentShiftCreditCapIncreases": int(g["CapIncreases"]),
            "CurrentShiftCreditCapIncreasesMax": int(g["CapIncreasesMax"]),
            "TargetMothershipId": target or p["MothershipId"]}


@route("/api/GetShiftCredit")
def get_shift_credit():
    caller = resolve_player()
    target_id = field(body(), "TargetMothershipId") or caller["MothershipId"]
    target = player_by_ms(target_id) or caller
    return J(_shift_credit_response(target, target_id))


@route("/api/PurchaseShiftCredit")
def purchase_shift_credit():
    p = resolve_player()
    cap = _shift_credit_cap(p)
    if int(p["GR"]["ShiftCredits"]) >= cap:
        return T("User Already at Max Shift Credit", 400)
    if sr_get(p) < CFG["shift_credit_refill_cost_sr"]:
        return T("Not enough Shiny Rocks", 400)
    sr_add(p, -CFG["shift_credit_refill_cost_sr"])
    p["GR"]["ShiftCredits"] = cap
    save_player(p)
    return J({"StatusCode": 200, "Error": None, "CurrentShiftCredits": cap, "TargetMothershipId": p["MothershipId"]})


@route("/api/PurchaseShiftCreditCapIncrease")
def purchase_shift_credit_cap_increase():
    p = resolve_player()
    g = p["GR"]
    if int(g["CapIncreases"]) >= int(g["CapIncreasesMax"]):
        return T("User Already Has Purchased Max Shift Credit Cap", 400)
    if ent_get(p, "GR_ResearchPoints") < CFG["shift_credit_cap_increase_cost_juice"]:
        return T("Not enough Juice", 400)
    ent_add(p, "GR_ResearchPoints", -CFG["shift_credit_cap_increase_cost_juice"])
    g["CapIncreases"] = int(g["CapIncreases"]) + 1
    save_player(p)
    return J({"StatusCode": 200, "Error": None, "CurrentShiftCreditCapIncreases": int(g["CapIncreases"]),
              "CurrentShiftCreditCapIncreasesMax": int(g["CapIncreasesMax"]), "TargetMothershipId": p["MothershipId"]})


@route("/api/SubtractShiftCredit")
def subtract_shift_credit():
    p = resolve_player()
    amt = as_int(field(body(), "ShiftCreditToRemove"), 0)
    if amt < 0:
        raise ApiError(400, "Negative amount")
    p["GR"]["ShiftCredits"] = max(0, int(p["GR"]["ShiftCredits"]) - amt)
    save_player(p)
    return J(_shift_credit_response(p))


def _juicer_tick(p):
    j = p["GR"]["Juicer"]
    ptime = CFG["core_processing_time_sec"]
    now = time.time()
    processed = 0
    while j["queue"] > 0:
        started = j.get("processing_started")
        if started is None:
            j["processing_started"] = now
            started = now
        if j.get("overdrive", 0) >= 100:
            j["overdrive"] -= 100
            j["queue"] -= 1
            j["processed_by_overdrive"] = j.get("processed_by_overdrive", 0) + 1
            j["processing_started"] = now if j["queue"] > 0 else None
            processed += 1
            continue
        if now - started >= ptime:
            j["queue"] -= 1
            processed += 1
            j["processing_started"] = (started + ptime) if j["queue"] > 0 else None
            continue
        break
    if j["queue"] <= 0:
        j["processing_started"] = None
    if processed:
        ent_add(p, "GR_ResearchPoints", processed)
    return processed


def _juicer_status(p, refresh):
    j = p["GR"]["Juicer"]
    ptime = CFG["core_processing_time_sec"]
    pct = 0.0
    if j["queue"] > 0 and j.get("processing_started"):
        pct = max(0.0, min(1.0, (time.time() - j["processing_started"]) / ptime))
    resp = {"MothershipId": p["MothershipId"], "StatusCode": 200, "Error": None,
            "CurrentCoreCount": int(j["queue"]), "CoreProcessingTimeSec": ptime, "CoreProcessingPercent": round(pct, 4),
            "OverdriveSupply": int(j.get("overdrive", 0)), "OverdriveCap": CFG["overdrive_cap"],
            "CoresProcessedByOverdrive": int(j.get("processed_by_overdrive", 0)), "RefreshJuice": bool(refresh)}
    j["processed_by_overdrive"] = 0
    return resp


@route("/api/GetJuicerStatus")
def get_juicer_status():
    p = resolve_player()
    processed = _juicer_tick(p)
    resp = _juicer_status(p, processed > 0)
    save_player(p)
    return J(resp)


@route("/api/DepositGRCore")
def deposit_gr_core():
    p = resolve_player()
    core = as_int(field(body(), "CoreBeingDeposited"), 0)
    if core == 3:
        _juicer_tick(p)
        j = p["GR"]["Juicer"]
        if j["queue"] >= CFG["juicer_seed_cap"]:
            save_player(p)
            return T("DepositGRCore already at seed cap", 400)
        j["queue"] += 1
        if j.get("processing_started") is None:
            j["processing_started"] = time.time()
        _juicer_tick(p)
        save_player(p)
        return J({"StatusCode": 200, "Error": None, "CurrentShiftCredits": int(p["GR"]["ShiftCredits"])})
    credits = CFG["credits_per_supercore"] if core == 2 else CFG["credits_per_core"]
    p["GR"]["ShiftCredits"] = min(_shift_credit_cap(p), int(p["GR"]["ShiftCredits"]) + credits)
    save_player(p)
    return J({"StatusCode": 200, "Error": None, "CurrentShiftCredits": int(p["GR"]["ShiftCredits"])})


@route("/api/PurchaseOverdrive")
def purchase_overdrive():
    p = resolve_player()
    _juicer_tick(p)
    j = p["GR"]["Juicer"]
    if j.get("overdrive", 0) >= CFG["overdrive_cap"]:
        return T("User Already At Overdrive Cap", 400)
    if j.get("overdrive", 0) > 0:
        return T("User would exceed Overdrive Cap", 400)
    if sr_get(p) < CFG["overdrive_cost_sr"]:
        return T("Not enough Shiny Rocks", 400)
    sr_add(p, -CFG["overdrive_cost_sr"])
    j["overdrive"] = CFG["overdrive_cap"]
    _juicer_tick(p)
    save_player(p)
    return J({"StatusCode": 200, "Error": None})


TOOL_COSTS = {1: 100, 2: 150, 3: 200, 4: 100, 5: 250, 6: 300, 7: 300, 8: 200, 9: 150, 10: 300, 11: 20, 12: 100, 13: 200}


@route("/api/RecycleTool")
def recycle_tool():
    p = resolve_player()
    b = body()
    tool = as_int(field(b, "ToolBeingRecycled"), 0)
    players = max(1, as_int(field(b, "NumberOfPlayers"), 1))
    cost = TOOL_COSTS.get(tool, 100)
    refund = int(10 / players) if tool == 11 else int((cost / 2) / players)
    p["GR"]["ShiftCredits"] = min(_shift_credit_cap(p), int(p["GR"]["ShiftCredits"]) + refund)
    save_player(p)
    return J(_shift_credit_response(p))


@route("/api/StartOfShift")
def start_of_shift():
    p = resolve_player()
    b = body()
    shift_id = field(b, "ShiftId") or str(uuid.uuid4())
    shift = {"ShiftId": shift_id, "Authority": p["MothershipId"], "CoresRequired": as_int(field(b, "CoresRequired"), 0),
             "NumberOfPlayers": as_int(field(b, "NumberOfPlayers"), 1), "Depth": as_int(field(b, "Depth"), 0),
             "Started": iso(), "Rewarded": []}
    DB.set("shifts", shift_id, shift)
    p["GR"]["MaxDepthReached"] = max(int(p["GR"].get("MaxDepthReached", 0)), shift["Depth"])
    save_player(p)
    return J({"StatusCode": 200, "Error": None, "ShiftId": shift_id})


@route("/api/EndOfShiftReward")
def end_of_shift_reward():
    p = resolve_player()
    shift_id = field(body(), "ShiftId") or ""
    shift = DB.get("shifts", shift_id)
    if shift is None:
        r = T("EndOfShiftReward Unknown Shift or Mothership Failure.", 400)
        r.status = "400 EndOfShiftReward Unknown Shift or Mothership Failure."
        return r
    if p["MothershipId"] not in shift["Rewarded"]:
        reward = int(shift.get("CoresRequired", 0)) * 5
        p["GR"]["ShiftCredits"] = min(_shift_credit_cap(p), int(p["GR"]["ShiftCredits"]) + reward)
        p["GR"]["MaxDepthReached"] = max(int(p["GR"].get("MaxDepthReached", 0)), int(shift.get("Depth", 0)))
        shift["Rewarded"].append(p["MothershipId"])
        DB.set("shifts", shift_id, shift)
        save_player(p)
    return J(_shift_credit_response(p))


@route("/api/PurchaseDrillUpgrade")
def purchase_drill_upgrade():
    p = resolve_player()
    level = as_int(field(body(), "Upgrade"), 1)
    node = {1: "DropPodBasic", 2: "DropPodChassis01", 3: "DropPodChassis02", 4: "DropPodChassis03"}.get(level)
    if node is None:
        raise ApiError(400, "Bad upgrade level")
    if node in p["Trees"].get("GRTools", []):
        return J({"StatusCode": 200, "Error": "AlreadyOwned"})
    if level == 1:
        if sr_get(p) < CFG["drill_upgrade_cost_sr"]:
            raise ApiError(400, "Not enough Shiny Rocks")
        sr_add(p, -CFG["drill_upgrade_cost_sr"])
        unlock_node(p, "GRTools", node, charge=False)
    else:
        unlock_node(p, "GRTools", node, charge=True)
    save_player(p)
    return J({"StatusCode": 200, "Error": None})


def _dock_wrist_response(p):
    d = p["GR"]["DockWrist"]
    return {"CurrentUpgrade1Level": int(d.get("u1", 0)), "CurrentUpgrade2Level": int(d.get("u2", 0)),
            "CurrentUpgrade3Level": int(d.get("u3", 0)), "Upgrade1LevelMax": 3, "Upgrade2LevelMax": 3, "Upgrade3LevelMax": 3}


@route("/api/AdvanceDockWristUpgrade")
def advance_dock_wrist_upgrade():
    p = resolve_player()
    up = as_int(field(body(), "Upgrade"), 0)
    if up not in (1, 2, 3):
        raise ApiError(400, "Bad upgrade")
    key = "u%d" % up
    d = p["GR"]["DockWrist"]
    if int(d.get(key, 0)) >= 3:
        return T("Upgrade already at max level", 400)
    if ent_get(p, "GR_ResearchPoints") < 1:
        return T("Not enough Juice", 400)
    ent_add(p, "GR_ResearchPoints", -1)
    d[key] = int(d.get(key, 0)) + 1
    save_player(p)
    return J(_dock_wrist_response(p))


@route("/api/GetDockWristUpgradeStatus")
def get_dock_wrist_upgrade_status():
    p = resolve_player()
    return J(_dock_wrist_response(p))


@route("/api/GetGhostReactorStats")
def get_ghost_reactor_stats():
    p = resolve_player()
    return J({"MothershipId": p["MothershipId"], "MaxDepthReached": int(p["GR"].get("MaxDepthReached", 0))})


@route("/api/GetGhostReactorInventory")
def get_ghost_reactor_inventory():
    p = resolve_player()
    return J({"MothershipId": p["MothershipId"], "InventoryJson": p["GR"].get("InventoryJson", "") or ""})


@route("/api/SetGhostReactorInventory")
def set_ghost_reactor_inventory():
    p = resolve_player()
    inv = field(body(), "InventoryJson")
    if not isinstance(inv, str):
        inv = json.dumps(inv or {}, separators=(",", ":"))
    p["GR"]["InventoryJson"] = inv[:200000]
    save_player(p)
    return J({"MothershipId": p["MothershipId"]})


def _si_inventory(p):
    return {"Result": {"Inventory": {k: int(v) for k, v in p["Entitlements"].items() if k.startswith("SI_")}}}


@route("/api/GetActiveSIQuests")
def get_active_si_quests():
    resolve_player(require=False)
    return J({"Result": {"Quests": si_active_quests()}, "StatusCode": 200, "Error": None})


@route("/api/GetSIQuestsStatus")
def get_si_quests_status():
    p = resolve_player()
    resp = {"Result": si_status(p)}
    save_player(p)
    return J(resp)


@route("/api/SetSIQuestComplete")
def set_si_quest_complete():
    p = resolve_player()
    qid = as_int(field(body(), "QuestID", "QuestId"), -1)
    if qid < 0 or qid >= len(si_active_quests()):
        raise ApiError(404, "Unknown quest")
    s = si_state(p)
    if int(s["TodayClaimableQuests"]) <= 0:
        raise ApiError(409, "No claimable quests left today")
    s["TodayClaimableQuests"] = int(s["TodayClaimableQuests"]) - 1
    ent_add(p, "SI_TechPoints", 1)
    save_player(p)
    return J({"Result": si_status(p)})


@route("/api/SetSIBonusComplete")
def set_si_bonus_complete():
    p = resolve_player()
    s = si_state(p)
    if int(s["TodayClaimableBonus"]) <= 0:
        raise ApiError(409, "No claimable bonus left today")
    s["TodayClaimableBonus"] = int(s["TodayClaimableBonus"]) - 1
    ent_add(p, "SI_TechPoints", 1)
    save_player(p)
    return J({"Result": si_status(p)})


@route("/api/SetSIIdolCollect")
def set_si_idol_collect():
    p = resolve_player()
    s = si_state(p)
    if int(s["TodayClaimableIdol"]) <= 0:
        raise ApiError(409, "Idol already collected today")
    s["TodayClaimableIdol"] = 0
    ent_add(p, "SI_TechPoints", 1)
    save_player(p)
    return J({"Result": si_status(p)})


@route("/api/ResetSIQuestsStatus")
def reset_si_quests_status():
    p = resolve_player()
    p["SI"] = {"day": si_day_key(), "TodayClaimableQuests": 3, "TodayClaimableBonus": 1, "TodayClaimableIdol": 1}
    save_player(p)
    return J({"Result": si_status(p)})


@route("/api/IncrementSIResource")
def increment_si_resource():
    p = resolve_player()
    rtype = field(body(), "ResourceType") or ""
    if rtype not in SI_RESOURCE_TYPES:
        raise ApiError(400, "Unknown resource type")
    ent = SI_ENTITLEMENT[rtype]
    cap = CFG["si_resource_cap"] if rtype != "TechPoint" else 10 ** 9
    if ent_get(p, ent) < cap:
        ent_add(p, ent, 1)
    save_player(p)
    resp = _si_inventory(p)
    resp["ResourceType"] = rtype
    return J(resp)


@route("/api/PurchaseTechPoints")
def purchase_tech_points():
    p = resolve_player()
    n = as_int(field(body(), "TechPointsAmount"), 0)
    if n < 1 or n > 10:
        raise ApiError(400, "TechPointsAmount must be 1..10")
    cost = n * CFG["tech_point_cost_sr"]
    if sr_get(p) < cost:
        raise ApiError(400, "Not enough Shiny Rocks to complete this purchase")
    sr_add(p, -cost)
    ent_add(p, "SI_TechPoints", n)
    save_player(p)
    return J(_si_inventory(p))


@route("/api/PurchaseResources")
def purchase_resources():
    p = resolve_player()
    cap = CFG["si_resource_cap"]
    res = [SI_ENTITLEMENT[r] for r in SI_RESOURCE_TYPES if r != "TechPoint"]
    if all(ent_get(p, r) >= cap for r in res):
        raise ApiError(400, "already maxed resources")
    if sr_get(p) < CFG["resources_purchase_cost_sr"]:
        raise ApiError(400, "Not enough Shiny Rocks to complete this purchase")
    sr_add(p, -CFG["resources_purchase_cost_sr"])
    for r in res:
        p["Entitlements"][r] = cap
    save_player(p)
    return J(_si_inventory(p))


@route("/api/GetQuestStatus")
def get_quest_status():
    p = resolve_player()
    return J({"result": quest_status_payload(p)})


@route("/api/SetQuestComplete")
def set_quest_complete():
    p = resolve_player()
    b = body()
    qid = as_int(field(b, "QuestId", "questId"), -1)
    ids = all_quest_ids()
    is_weekly = None
    if ids and (ids["daily"] or ids["weekly"]):
        if qid in ids["weekly"]:
            is_weekly = True
        elif qid in ids["daily"]:
            is_weekly = False
        else:
            raise ApiError(404, "Unknown quest id")
    else:
        is_weekly = qid >= 2000
    day_id, week_id = daily_quest_set_id(), weekly_quest_set_id()
    q = p["Quests"]
    q["dailyPoints"] = {k: v for k, v in (q.get("dailyPoints") or {}).items() if as_int(k) // 7 == week_id}
    q["weeklyPoints"] = {k: v for k, v in (q.get("weeklyPoints") or {}).items() if as_int(k) == week_id}
    completed_key = "%d:%d" % (week_id if is_weekly else day_id, qid)
    if completed_key in (q.get("completed") or []):
        return J({"result": quest_status_payload(p)})
    if weekly_points_sum(p) >= CFG["weekly_quest_cap"]:
        raise ApiError(403, "User already reached the max number of completion points for this time period!")
    pts = CFG["weekly_quest_points"] if is_weekly else CFG["daily_quest_points"]
    pts = min(pts, CFG["weekly_quest_cap"] - weekly_points_sum(p))
    if is_weekly:
        q["weeklyPoints"][str(week_id)] = int(q["weeklyPoints"].get(str(week_id), 0)) + pts
    else:
        q["dailyPoints"][str(day_id)] = int(q["dailyPoints"].get(str(day_id), 0)) + pts
    q["userPointsTotal"] = int(q.get("userPointsTotal", 0)) + pts
    q.setdefault("completed", []).append(completed_key)
    q["completed"] = q["completed"][-500:]
    save_player(p)
    return J({"result": quest_status_payload(p)})


@route("/api/GetTier")
def get_tier():
    p = resolve_player()
    ids = field(body(), "playfabIds", "playfabIDs", "PlayFabIds", default=None) or [p["PlayFabId"]]
    if isinstance(ids, str):
        ids = [x for x in ids.split(",") if x]
    out = []
    for pid in ids:
        pl = get_player(pid)
        if pl is None:
            if CFG["strict_auth"]:
                continue
            pl = new_player(playfab_id=pid)
        out.append({"playfabID": pl["PlayFabId"], "platformData": [platform_data(pl, "PC"), platform_data(pl, "Quest")]})
    return J(out)


@route("/api/CreateMatchId")
def create_match_id():
    p = resolve_player()
    mid = str(uuid.uuid4())
    plat = field(body(), "platform") or "PC"
    DB.set("matches", mid, {"matchId": mid, "platform": plat, "creator": p["PlayFabId"], "created": iso(),
                            "lastPing": iso(), "players": [p["PlayFabId"]], "scored": False, "submissions": []})
    return T(mid)


@route("/api/ValidateMatchJoin")
def validate_match_join():
    p = resolve_player()
    mid = field(body(), "matchId") or ""
    m = DB.get("matches", mid)
    if m is None:
        return J({"validJoin": False})
    last = parse_iso(m.get("lastPing"))
    if last and (utcnow() - last).total_seconds() > CFG["match_ping_timeout_sec"] * 3:
        return J({"validJoin": False})
    if p["PlayFabId"] not in m["players"]:
        m["players"].append(p["PlayFabId"])
        DB.set("matches", mid, m)
    return J({"validJoin": True})


@route("/api/SubmitMatchScores")
def submit_match_scores():
    p = resolve_player()
    b = body()
    mid = field(b, "matchId") or ""
    scores = field(b, "playerScores", default=[]) or []
    m = DB.get("matches", mid)
    if m is None:
        raise ApiError(404, "Unknown match")
    round_key = hashlib.sha1(json.dumps(sorted([(str(s.get("playfabId")), round(float(s.get("gameScore") or 0), 2)) for s in scores])).encode()).hexdigest()[:16]
    m.setdefault("submissions", [])
    m["submissions"].append({"by": p["PlayFabId"], "time": iso(), "round": round_key})
    m["submissions"] = m["submissions"][-200:]
    rounds = m.setdefault("rounds", {})
    if round_key in rounds:
        DB.set("matches", mid, m)
        return Response("", status=200)
    ids = sorted(str(s.get("playfabId")) for s in scores)
    for rk, r in rounds.items():
        if r.get("ids") == ids and parse_iso(r.get("time")) and (utcnow() - parse_iso(r["time"])).total_seconds() < 60:
            DB.set("matches", mid, m)
            return Response("", status=200)
    changes = apply_match_elo(m, scores)
    rounds[round_key] = {"ids": ids, "time": iso(), "by": p["PlayFabId"], "changes": changes}
    m["scored"] = True
    DB.set("matches", mid, m)
    return Response("", status=200)


@route("/api/PingRoom")
def ping_room():
    p = resolve_player()
    mid = field(body(), "matchId") or ""
    m = DB.get("matches", mid)
    if m is not None:
        m["lastPing"] = iso()
        if p["PlayFabId"] not in m["players"]:
            m["players"].append(p["PlayFabId"])
        DB.set("matches", mid, m)
    return Response("", status=200)


@route("/api/UnlockCompetitiveQueue")
def unlock_competitive_queue():
    p = resolve_player()
    p["CompetitiveUnlocked"] = as_bool(field(body(), "unlocked", default=True), True)
    save_player(p)
    return Response("", status=200)


PHOTON_HOOK_TYPES = ("Create", "Join", "Leave", "Close", "Event", "GameProperties", "ClientDisconnect", "TimeoutDisconnect",
                     "Load", "Save", "Game", "GameEvent", "PathClose", "PathCreate", "PathJoin", "PathLeave")


def _photon_hook(evt):
    b = body()
    uid = field(b, "UserId", "userId")
    game = field(b, "GameId", "gameId") or ""
    p = get_player(uid) if uid else None
    if evt in ("Close", "PathClose") and game:
        for _, pl in DB.items("players"):
            pr = pl.get("Presence") or {}
            if pr.get("RoomId") == game:
                pr["RoomId"] = ""
                pl["Presence"] = pr
                save_player(pl)
        return J({"ResultCode": 0, "Message": "ok"})
    if p is not None:
        pr = p.setdefault("Presence", {})
        if evt in ("Create", "Join", "PathCreate", "PathJoin"):
            pr["RoomId"] = game
            opts = field(b, "CreateOptions", default={}) or {}
            props = (opts.get("CustomProperties") or {}) if isinstance(opts, dict) else {}
            if "IsPublic" in props:
                pr["IsPublic"] = as_bool(props.get("IsPublic"))
            region = field(b, "Region", "region")
            if region:
                pr["Region"] = region
            nick = field(b, "Nickname", "nickname")
            if nick:
                p["Nickname"] = nick
        elif evt in ("Leave", "ClientDisconnect", "TimeoutDisconnect", "PathLeave"):
            if pr.get("RoomId") == game or not game:
                pr["RoomId"] = ""
        elif evt in ("GameProperties", "Event"):
            props = field(b, "Properties", "properties", default={}) or {}
            if isinstance(props, dict):
                custom = props.get("CustomProperties") if isinstance(props.get("CustomProperties"), dict) else props
                if "IsPublic" in custom:
                    pr["IsPublic"] = as_bool(custom.get("IsPublic"))
        save_player(p)
    return J({"ResultCode": 0, "Message": "ok"})


@route("/api/photon")
def photon():
    b = body()
    evt = field(b, "Type", "type")
    if evt in PHOTON_HOOK_TYPES:
        return _photon_hook(evt)
    ticket = field(b, "Ticket", "ticket")
    ms_tok = field(b, "MothershipToken")
    p = None
    if ticket:
        pfid = DB.get("idx_ticket", ticket)
        p = get_player(pfid) if pfid else None
    if p is None and ms_tok:
        pfid = DB.get("idx_mstoken", ms_tok)
        p = get_player(pfid) if pfid else None
    if p is None:
        uid = field(b, "UserId", "userId", "PlayFabId")
        p = get_player(uid) if uid else None
    if p is None:
        if CFG["strict_auth"]:
            return J({"ResultCode": 2, "Message": "Authentication failed"})
        p = new_player()
    if p.get("Banned") and is_ban_active(p["Banned"]):
        return J({"ResultCode": 2, "Message": p["Banned"].get("BanMessage", "Banned")})
    pr = p.setdefault("Presence", {})
    if field(b, "Zone") is not None:
        pr["Zone"] = str(field(b, "Zone") or "")
    if field(b, "SubZone") is not None:
        pr["SubZone"] = str(field(b, "SubZone") or "")
    if field(b, "IsPublic") is not None:
        pr["IsPublic"] = as_bool(field(b, "IsPublic"))
    save_player(p)
    return J({"ResultCode": 1, "UserId": p["PlayFabId"], "Nickname": p.get("Nickname") or p.get("DisplayName") or "gorilla",
              "Data": {"SteamAuthIdForPhoton": p["SteamAuthIdForPhoton"]}, "AuthCookie": {"PlayFabId": p["PlayFabId"]}})


@route("/api/photon/ClientDisconnect")
def photon_client_disconnect():
    return _photon_hook("ClientDisconnect")


@route("/api/photon/Close")
def photon_close():
    return _photon_hook("Close")


@route("/api/photon/Create")
def photon_create():
    return _photon_hook("Create")


@route("/api/photon/Event")
def photon_event():
    return _photon_hook("Event")


@route("/api/photon/GameProperties")
def photon_game_properties():
    return _photon_hook("GameProperties")


@route("/api/photon/Join")
def photon_join():
    return _photon_hook("Join")


@route("/api/photon/TimeoutDisconnect")
def photon_timeout_disconnect():
    return _photon_hook("TimeoutDisconnect")


def _friend_presence(viewer, friend):
    pr = friend.get("Presence") or {}
    privacy = friend.get("Privacy", "VISIBLE")
    room, zone, is_public = pr.get("RoomId") or "", pr.get("Zone") or "", bool(pr.get("IsPublic"))
    online = bool(room) and _recently_seen(friend, CFG["ccu_window_sec"])
    if privacy == "HIDDEN" or not online:
        room, zone = "", ""
    elif privacy == "PUBLIC_ONLY" and not is_public:
        room, zone = "", ""
    return {"FriendLinkId": friend["PlayFabId"], "UserName": friend.get("Nickname") or friend.get("DisplayName") or "GORILLA",
            "RoomId": room, "Zone": zone, "Region": pr.get("Region") or "", "IsPublic": is_public if room else None}


def _friend_pair_key(a, b):
    return ":".join(sorted([a, b]))


@route("/api/GetFriendsV2")
def get_friends_v2():
    p = resolve_player()
    links = DB.get("friends", p["PlayFabId"]) or {}
    friends = []
    for fid, created in links.items():
        f = get_player(fid)
        if f is None:
            continue
        friends.append({"Presence": _friend_presence(p, f), "Created": created})
    return J({"Result": {"Friends": friends, "MyPrivacyState": {"VISIBLE": 0, "PUBLIC_ONLY": 1, "HIDDEN": 2}.get(p.get("Privacy"), 0)},
              "StatusCode": 200, "Error": None})


@route("/api/SetPrivacyState")
def set_privacy_state():
    p = resolve_player()
    st = str(field(body(), "PrivacyState") or "VISIBLE").upper()
    if st in ("0", "1", "2"):
        st = ["VISIBLE", "PUBLIC_ONLY", "HIDDEN"][int(st)]
    if st not in ("VISIBLE", "PUBLIC_ONLY", "HIDDEN"):
        raise ApiError(400, "Bad privacy state")
    p["Privacy"] = st
    save_player(p)
    return J({"StatusCode": 200, "Error": None})


@route("/api/RequestFriend")
def request_friend():
    p = resolve_player()
    b = body()
    me = p["PlayFabId"]
    other = (field(b, "FriendFriendLinkId") or "").upper()
    if not other or other == me:
        raise ApiError(400, "Bad friend id")
    target = get_player(other)
    if target is None:
        if CFG["strict_auth"]:
            raise ApiError(404, "Unknown player")
        target = new_player(playfab_id=other)
    my_links = DB.get("friends", me) or {}
    if other in my_links:
        raise ApiError(409, "Already friends")
    pending = DB.get("friend_requests", _friend_pair_key(me, other)) or {}
    now = utcnow()
    pending = {k: v for k, v in pending.items() if (parse_iso(v) and (now - parse_iso(v)).total_seconds() < CFG["friend_request_ttl_sec"])}
    if me in pending:
        DB.set("friend_requests", _friend_pair_key(me, other), pending)
        raise ApiError(409, "Already requested")
    if other in pending:
        created = iso()
        my_links[other] = created
        their = DB.get("friends", other) or {}
        their[me] = created
        DB.set("friends", me, my_links)
        DB.set("friends", other, their)
        DB.delete("friend_requests", _friend_pair_key(me, other))
        return J({"StatusCode": 200, "Error": None, "Status": "CONFIRMED"})
    pending[me] = iso()
    DB.set("friend_requests", _friend_pair_key(me, other), pending)
    return J({"StatusCode": 200, "Error": None, "Status": "I_REQUESTED"})


@route("/api/RemoveFriend")
def remove_friend():
    p = resolve_player()
    b = body()
    me = p["PlayFabId"]
    other = (field(b, "FriendFriendLinkId") or "").upper()
    my_links = DB.get("friends", me) or {}
    their = DB.get("friends", other) or {}
    my_links.pop(other, None)
    their.pop(me, None)
    DB.set("friends", me, my_links)
    if other:
        DB.set("friends", other, their)
    DB.delete("friend_requests", _friend_pair_key(me, other))
    return J({"StatusCode": 200, "Error": None})


@route("/api/AssociatePlayFabAndModIO")
def associate_modio():
    p = resolve_player()
    b = body()
    p["ModIO"] = {"ModIOId": field(b, "ModIOId"), "Linked": iso()}
    save_player(p)
    return J({"Results": [{"MothershipPlayerId": p["MothershipId"], "AssociationId": str(uuid.uuid4()),
                           "ExternalServiceName": "modio", "ExternalServiceUserId": field(b, "ModIOId") or "",
                           "ExternalServiceOrgScopedId": "", "ExternalServiceUserName": "",
                           "TitleId": CFG["mothership_title_id"], "EnvId": CFG["mothership_env_id"]}]})


@route("/api/ConsumeOculusIAP")
def consume_oculus_iap():
    p = resolve_player()
    b = body()
    sku = field(b, "sku", "Sku", "SKU", "productId", "itemGUID")
    purchase_id = field(b, "purchaseId", "PurchaseId", "purchaseID", "receiptId", "nonce", "Nonce") or ""
    if not sku:
        raise ApiError(400, "sku required")
    key = "%s:%s" % (sku, purchase_id or "single")
    if key in p["Redeemed"]:
        return J({"result": "AlreadyRedeemed", "sku": sku, "itemID": key, "playFabItemName": ""})
    catalog = DB.get("config", "IAPCatalog") or {}
    entry = catalog.get(sku) or {}
    granted = []
    for item in entry.get("items", []):
        if grant_item(p, item):
            granted.append(item)
    if entry.get("shinyRocks"):
        sr_add(p, int(entry["shinyRocks"]))
    if not entry:
        if grant_item(p, sku):
            granted.append(sku)
    p["Redeemed"][key] = iso()
    save_player(p)
    return J({"result": "Success", "sku": sku, "itemID": key, "playFabItemName": granted[0] if granted else "",
              "grantedItems": granted, "shinyRocks": sr_get(p)})


@route("/api/GetMySubscriptionsAndTheirBenefits")
def get_my_subscriptions():
    p = resolve_player()
    rebuild_shared_group(p)
    save_player(p)
    return J(subscription_payload(p))


@route("/api/purchase/cosmetic")
def purchase_cosmetic():
    p = resolve_player()
    b = body()
    item = field(b, "itemId", "ItemId", "playFabItemName", "itemName")
    if not item:
        raise ApiError(400, "itemId required")
    if item in p["Inventory"]:
        return J({"result": "AlreadyOwned", "itemID": item, "playFabItemName": item, "shinyRocks": sr_get(p)})
    catalog = DB.get("config", "Catalog") or []
    price = None
    for c in catalog:
        if c.get("ItemId") == item:
            price = (c.get("VirtualCurrencyPrices") or {}).get("SR")
    if price is None:
        price = as_int(field(b, "price", "Price"), 0)
    if sr_get(p) < int(price):
        raise ApiError(400, "Not enough Shiny Rocks")
    sr_add(p, -int(price))
    grant_item(p, item)
    save_player(p)
    return J({"result": "Success", "itemID": item, "playFabItemName": item, "VirtualCurrency": p["Currency"],
              "shinyRocks": sr_get(p), "Inventory": list(p["Inventory"].values())})


@route("/v1/subscription/client", methods=("GET",))
def v1_subscription_client():
    p = resolve_player()
    return J(subscription_payload(p))


def _redemption_response(p, code_entry, code, item_key):
    now = utcnow()
    st, en = parse_iso(code_entry.get("startTime")), parse_iso(code_entry.get("endTime"))
    resp = {"result": "Success", "itemID": code_entry.get("itemID", code), "playFabItemName": code_entry.get("playFabItemName", ""),
            "startTime": code_entry.get("startTime"), "endTime": code_entry.get("endTime")}
    if st and now < st:
        resp["result"] = "TooEarly"
        return resp
    if en and now > en:
        resp["result"] = "TooLate"
        return resp
    if item_key in p["Redeemed"]:
        resp["result"] = "AlreadyRedeemed"
        return resp
    if code_entry.get("maxUses") and int(code_entry.get("uses", 0)) >= int(code_entry["maxUses"]):
        resp["result"] = "AlreadyRedeemed"
        return resp
    item = code_entry.get("playFabItemName")
    if item and item in p["Inventory"] and not code_entry.get("shinyRocks"):
        resp["result"] = "AlreadyGranted"
        p["Redeemed"][item_key] = iso()
        return resp
    if item:
        grant_item(p, item)
    if code_entry.get("shinyRocks"):
        sr_add(p, int(code_entry["shinyRocks"]))
    code_entry["uses"] = int(code_entry.get("uses", 0)) + 1
    p["Redeemed"][item_key] = iso()
    return resp


@route("/api/ConsumeCodeItem")
def consume_code_item():
    p = resolve_player()
    b = body()
    code = (field(b, "itemGUID", "code") or "").strip()
    if len(code) < 8:
        raise ApiError(400, "Invalid code")
    entry = DB.get("codes", code.upper()) or DB.get("codes", code)
    if entry is None:
        raise ApiError(404, "Invalid code")
    resp = _redemption_response(p, entry, code, "code:" + code.upper())
    DB.set("codes", code.upper(), entry)
    save_player(p)
    return J(resp)


@route("/api/ConsumeItem")
def consume_item():
    p = resolve_player()
    b = body()
    guid = field(b, "itemGUID") or ""
    source = field(b, "launchSource") or ""
    key = "collab:%s:%s" % (source, guid)
    if key in p["Redeemed"]:
        return J({"result": "AlreadyRedeemed", "itemGUID": guid, "launchSource": source})
    collabs = DB.get("config", "Collabs") or {"7221491444554579": ["LMAKT."], "1903584373052985": ["LMALI.", "LHAGS."]}
    for item in collabs.get(source, []):
        grant_item(p, item)
    p["Redeemed"][key] = iso()
    save_player(p)
    return J({"result": "Success", "itemGUID": guid, "launchSource": source, "granted": collabs.get(source, [])})


def poll_payload(poll):
    return {"PollId": int(poll["PollId"]), "Question": poll.get("Question", ""), "VoteOptions": list(poll.get("VoteOptions") or []),
            "VoteCount": list(poll.get("VoteCount") or []), "PredictionCount": list(poll.get("PredictionCount") or []),
            "StartTime": poll.get("StartTime"), "EndTime": poll.get("EndTime"), "isActive": bool(poll.get("isActive"))}


@route("/api/FetchPoll")
def fetch_poll():
    resolve_player(require=False)
    include_inactive = as_bool(field(body(), "IncludeInactive", default=True), True)
    now = utcnow()
    polls = []
    for _, poll in sorted(DB.items("polls"), key=lambda kv: int(kv[1]["PollId"])):
        end = parse_iso(poll.get("EndTime"))
        start = parse_iso(poll.get("StartTime"))
        poll["isActive"] = bool(start and end and start <= now < end and not poll.get("Closed"))
        if poll["isActive"] or include_inactive:
            polls.append(poll_payload(poll))
    return J(polls)


@route("/api/Vote")
def vote():
    p = resolve_player()
    b = body()
    poll_id = as_int(field(b, "PollId"), -1)
    poll = DB.get("polls", poll_id)
    if poll is None:
        raise ApiError(404, "Poll not found")
    idx = as_int(field(b, "OptionIndex"), -1)
    is_pred = as_bool(field(b, "IsPrediction"))
    if idx < 0 or idx >= len(poll.get("VoteOptions") or []):
        raise ApiError(400, "Bad option index")
    now = utcnow()
    st, en = parse_iso(poll.get("StartTime")), parse_iso(poll.get("EndTime"))
    if not st or not en or not (st <= now < en) or poll.get("Closed"):
        raise ApiError(400, "Poll not active")
    my = p["Votes"].setdefault(str(poll_id), {})
    slot = "prediction" if is_pred else "vote"
    if slot in my:
        raise ApiError(429, "User already voted on this poll!")
    my[slot] = idx
    counts = poll.setdefault("PredictionCount" if is_pred else "VoteCount", [0] * len(poll["VoteOptions"]))
    while len(counts) < len(poll["VoteOptions"]):
        counts.append(0)
    counts[idx] += 1
    DB.set("polls", poll_id, poll)
    save_player(p)
    return J({"PollId": poll_id, "TitleId": field(b, "TitleId") or CFG["title_id"], "VoteOptions": poll["VoteOptions"],
              "VoteCount": poll.get("VoteCount", []), "PredictionCount": poll.get("PredictionCount", [])})


def _map_meta(m):
    return {"mapId": m["mapId"], "mothershipId": m.get("mothershipId", ""), "userDataMetadataKey": m.get("userDataMetadataKey", ""),
            "nickname": m.get("nickname", ""), "createdTime": m.get("createdTime"), "updatedTime": m.get("updatedTime"),
            "voteCount": int(m.get("voteCount", 0)), "isActive": bool(m.get("isActive", True))}


@route("/api/MapVote")
def map_vote():
    p = resolve_player()
    b = body()
    mid = (field(b, "mapId") or "").upper()
    v = as_int(field(b, "vote"), 0)
    if not MAP_ID_RE.match(mid) or v not in (1, -1):
        raise ApiError(400, "Bad vote")
    m = DB.get("maps", mid)
    if m is None:
        raise ApiError(404, "Map not found")
    votes = m.setdefault("votes", {})
    prev = votes.get(p["MothershipId"], 0)
    votes[p["MothershipId"]] = v
    m["voteCount"] = int(m.get("voteCount", 0)) - prev + v
    DB.set("maps", mid, m)
    return J({"mapId": mid, "voteCount": m["voteCount"], "yourVote": v})


@route("/api/Publish")
def publish_map():
    p = resolve_player()
    b = body()
    key = field(b, "userdataMetadataKey", "userDataMetadataKey") or ""
    nick = field(b, "playerNickname") or p.get("Nickname") or "GORILLA"
    map_data = field(b, "mapData", "MapData")
    if map_data is None:
        rec = p["UserData"].get(key) if key else None
        map_data = (rec or {}).get("value")
    if not map_data:
        raise ApiError(400, "No map data found for user data key '%s' (write it via /v1/userdata/client first)" % key)
    try:
        decoded = decode_map_data(map_data)
        if not isinstance(decoded, dict) or int(decoded.get("version", 0)) < 4:
            raise ValueError("version")
    except Exception:
        raise ApiError(400, "Map data is not valid BuilderTableData (base64+gzip or JSON, version >= 4)")
    p["Nickname"] = nick
    existing = None
    idx = DB.get("map_index", "%s:%s" % (p["MothershipId"], key)) if key else None
    if idx:
        existing = DB.get("maps", idx)
    now = iso_short()
    if existing:
        existing.update({"mapData": map_data, "nickname": nick, "updatedTime": now, "isActive": True})
        DB.set("maps", existing["mapId"], existing)
        save_player(p)
        return T(existing["mapId"])
    mid = new_map_id()
    m = {"mapId": mid, "mothershipId": p["MothershipId"], "userDataMetadataKey": key, "nickname": nick,
         "createdTime": now, "updatedTime": now, "voteCount": 0, "isActive": True, "mapData": map_data, "votes": {}}
    DB.set("maps", mid, m)
    if key:
        DB.set("map_index", "%s:%s" % (p["MothershipId"], key), mid)
    save_player(p)
    return T(mid)


@route("/api/GetMapData")
def get_map_data():
    resolve_player(require=False)
    mid = (field(body(), "mapId") or "").upper()
    m = DB.get("maps", mid)
    if m is None or not m.get("mapData"):
        raise ApiError(404, "Map not found", text=True)
    return T(m["mapData"])


@route("/api/GetMapDataDecoded")
def get_map_data_decoded():
    resolve_player(require=False)
    mid = (field(body(), "mapId") or "").upper()
    m = DB.get("maps", mid)
    if m is None or not m.get("mapData"):
        raise ApiError(404, "Map not found")
    try:
        decoded = decode_map_data(m["mapData"])
    except Exception as e:
        raise ApiError(500, "Could not decode map data: %s" % e)
    meta = _map_meta(m)
    meta["mapData"] = decoded
    return J(meta)


@route("/api/GetMaps")
def get_maps():
    resolve_player(require=False)
    b = body()
    page = max(0, as_int(field(b, "page"), 0))
    size = max(1, min(500, as_int(field(b, "pageSize"), 50)))
    sort = field(b, "sort") or "Top"
    show_inactive = as_bool(field(b, "ShowInactive", "showInactive"))
    maps = [m for _, m in DB.items("maps") if show_inactive or m.get("isActive", True)]
    if sort == "NewlyCreated":
        maps.sort(key=lambda m: m.get("createdTime") or "", reverse=True)
    elif sort == "RecentlyUpdated":
        maps.sort(key=lambda m: m.get("updatedTime") or "", reverse=True)
    else:
        maps.sort(key=lambda m: (int(m.get("voteCount", 0)), m.get("updatedTime") or ""), reverse=True)
    chunk = maps[page * size:(page + 1) * size]
    return J([_map_meta(m) for m in chunk])


@route("/api/UpdateMapActive")
def update_map_active():
    p = resolve_player()
    b = body()
    key = field(b, "userdataMetadataKey", "userDataMetadataKey") or ""
    active = as_bool(field(b, "setActive"), True)
    mid = field(b, "mapId")
    if not mid and key:
        mid = DB.get("map_index", "%s:%s" % (p["MothershipId"], key))
    m = DB.get("maps", (mid or "").upper()) if mid else None
    if m is None:
        raise ApiError(404, "Map not found")
    if m.get("mothershipId") != p["MothershipId"]:
        raise ApiError(403, "Not your map")
    m["isActive"] = active
    DB.set("maps", m["mapId"], m)
    return J({"mapId": m["mapId"], "isActive": active})


def _kid_player_data(k):
    return {"Status": k.get("Status"), "Session": k.get("Session"), "DefaultSession": k.get("DefaultSession"),
            "Permissions": list(k.get("OptInPermissions") or []), "HasConfirmedSetup": bool(k.get("HasConfirmedSetup"))}


@route("/api/GetPlayerData", methods=("GET",))
def kid_get_player_data():
    p = resolve_player()
    k = kid_state(p)
    if not k.get("OptedIn"):
        save_player(p)
        return Response("", status=204)
    save_player(p)
    return J(_kid_player_data(k))


@route("/api/GetRequirements", methods=("GET",))
def kid_get_requirements():
    resolve_player(require=False)
    return J(kid_requirements())


@route("/api/OptIn")
def kid_opt_in():
    p = resolve_player()
    k = kid_state(p)
    if not k.get("OptedIn"):
        k["OptedIn"] = True
        if not k.get("Rewarded"):
            sr_add(p, CFG["opt_in_reward_shiny_rocks"])
            k["Rewarded"] = True
    save_player(p)
    return Response("", status=200)


@route("/api/VerifyAge")
def kid_verify_age():
    p = resolve_player()
    b = body()
    age = as_int(field(b, "Age"), 0)
    k = kid_state(p)
    kid_build_session_for_age(k, age)
    if p.get("Platform") is None:
        p["Platform"] = "Steam"
    save_player(p)
    return J({"Status": k["Status"], "Session": k["Session"], "DefaultSession": None})


@route("/api/AttemptAgeUpdate")
def kid_attempt_age_update():
    p = resolve_player()
    age = as_int(field(body(), "Age"), 0)
    k = kid_state(p)
    req = kid_requirements()
    if age < req["minimumAge"]:
        k["Status"] = 1
    elif age < req["digitalConsentAge"]:
        k["Status"] = 2
    else:
        k["Status"] = 4
    k["PendingAge"] = age
    save_player(p)
    return J({"Status": k["Status"]})


@route("/api/AppealAge")
def kid_appeal_age():
    p = resolve_player()
    b = body()
    k = kid_state(p)
    k["Email"] = field(b, "Email") or k.get("Email", "")
    age = as_int(field(b, "Age"), k.get("PendingAge", 18))
    kid_build_session_for_age(k, max(age, kid_requirements()["minimumAge"]))
    save_player(p)
    return Response("", status=200)


@route("/api/SendChallengeEmail")
def kid_send_challenge_email():
    p = resolve_player()
    b = body()
    k = kid_state(p)
    email = field(b, "Email")
    if email is not None and email != "" and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(email)):
        return J({"Error": "BadRequest-InvalidEmail", "Message": "Invalid email"}, 400)
    if email:
        k["Email"] = email
    kid_build_session_for_age(k, max(as_int(k.get("PendingAge"), k.get("Age", 13)), 13))
    k["Status"] = 0
    save_player(p)
    return Response("", status=200)


@route("/api/UpgradeSession")
def kid_upgrade_session():
    p = resolve_player()
    b = body()
    k = kid_state(p)
    wanted = [str(x.get("name") if isinstance(x, dict) else x) for x in (field(b, "Permissions", default=[]) or [])]
    if not k.get("Session"):
        kid_build_session_for_age(k, k.get("Age") or 18)
    k["Etag"] = int(k.get("Etag", 0)) + 1
    k["Session"]["etag"] = str(k["Etag"])
    for perm in k["Session"]["permissions"]:
        if perm["name"] in wanted:
            perm["enabled"] = True
            perm["managedBy"] = "PLAYER"
    k["OptInPermissions"] = sorted(set(k.get("OptInPermissions") or []) | set(wanted))
    k["Status"] = 0
    save_player(p)
    return J({"status": 0, "session": k["Session"]})


@route("/api/SetConfirmedStatus")
def kid_set_confirmed_status():
    p = resolve_player()
    kid_state(p)["HasConfirmedSetup"] = True
    save_player(p)
    return Response("", status=200)


@route("/api/SetOptInPermissions")
def kid_set_opt_in_permissions():
    p = resolve_player()
    perms = field(body(), "OptInPermissions", default=[]) or []
    k = kid_state(p)
    k["OptInPermissions"] = [str(x) for x in perms if str(x) in KID_PERMISSIONS]
    if k.get("Session"):
        k["Etag"] = int(k.get("Etag", 0)) + 1
        k["Session"]["etag"] = str(k["Etag"])
        for perm in k["Session"]["permissions"]:
            if perm["managedBy"] == "PLAYER":
                perm["enabled"] = perm["name"] in k["OptInPermissions"]
    save_player(p)
    return Response("", status=200)


def _title_data_filtered():
    b = body()
    keys = field(b, "keys", "Keys", default=None)
    if isinstance(keys, str):
        keys = [k for k in keys.split(",") if k]
    data = title_data_all()
    if keys:
        data = {k: v for k, v in data.items() if k in keys}
    return data


@route("/api/ReturnCurrentVersion")
def return_current_version():
    ver = CFG["client_version"]
    return J({"ResultCode": 0, "Message": "OK", "CurrentVersion": ver, "MinimumVersion": ver, "UpdateRequired": False})


@route("/api/ReturnCurrentVersionV2")
def return_current_version_v2():
    b = body()
    ver = CFG["client_version"]
    client_ver = field(b, "CurrentVersion", "ClientVersion", "AppVersion", "Version")
    return J({"ResultCode": 0, "Message": "OK", "CurrentVersion": ver, "MinimumVersion": ver, "UpdateRequired": False,
              "ClientVersion": client_ver, "IsValid": True})


@route("/api/TitleData")
def title_data():
    return J({"code": 200, "status": "OK", "data": {"Data": _title_data_filtered()}})


@route("/v1/title-data/client", methods=("GET",))
def v1_title_data_client():
    data = _title_data_filtered()
    return J({"Results": [{"key": k, "data": v} for k, v in data.items()]})


@route("/api/AddOrRemoveDLCOwnershipV2")
def add_or_remove_dlc_ownership_v2():
    p = resolve_player()
    b = body()
    items = field(b, "ItemIds", "itemIds", "DLCNames", "dlcs", "ItemId", "itemId", "DLCName", "dlcName", default=[]) or []
    if isinstance(items, str):
        items = [x for x in items.split(",") if x]
    action = str(field(b, "Action", "action", default="") or "").lower()
    remove = as_bool(field(b, "Remove", "remove")) or action == "remove"
    changed = []
    for item in items:
        if remove:
            if revoke_item(p, str(item)):
                changed.append(str(item))
        else:
            if grant_item(p, str(item)):
                changed.append(str(item))
    save_player(p)
    return J({"result": "Success", "Removed" if remove else "Added": changed, "Inventory": list(p["Inventory"].keys())})


@route("/api/BroadcastMyRoomV2")
def broadcast_my_room_v2():
    p = resolve_player()
    b = body()
    pr = p.setdefault("Presence", {})
    room = field(b, "RoomId", "roomId", "GameId")
    if room is not None:
        pr["RoomId"] = str(room)
    for src, dst in (("Zone", "Zone"), ("SubZone", "SubZone"), ("Region", "Region")):
        v = field(b, src, src[0].lower() + src[1:])
        if v is not None:
            pr[dst] = str(v)
    if field(b, "IsPublic", "isPublic") is not None:
        pr["IsPublic"] = as_bool(field(b, "IsPublic", "isPublic"))
    nick = field(b, "Nickname", "nickname")
    if nick:
        p["Nickname"] = str(nick)
        pr["Nickname"] = str(nick)
    save_player(p)
    return J({"result": "Success", "RoomId": pr.get("RoomId", "")})


@route("/api/CheckForBadName")
def check_for_bad_name():
    resolve_player(require=False)
    b = body()
    name = str(field(b, "name", "Name", "playerName", "PlayerName", default="") or "")
    for_room = as_bool(field(b, "forRoom", "ForRoom"))
    limit = 10 if for_room else 12
    bad_words = DB.get("config", "BadWords") or []
    valid = bool(re.match(r"^[A-Za-z0-9]{1,%d}$" % limit, name))
    if valid and any(w and w.lower() in name.lower() for w in bad_words):
        valid = False
    return J({"result": 0 if valid else 2, "Result": 0 if valid else 2, "name": name, "Valid": valid})


@route("/api/GetAcceptedAgreements")
def get_accepted_agreements():
    p = resolve_player()
    return J(dict(p.get("Agreements") or {}))


@route("/api/SubmitAcceptedAgreements")
def submit_accepted_agreements():
    p = resolve_player()
    b = body()
    ag = field(b, "Agreements", "agreements")
    if isinstance(ag, dict):
        for k, v in ag.items():
            p["Agreements"][str(k)] = str(v)
    else:
        key = field(b, "AgreementKey", "agreementKey", "Key")
        ver = field(b, "AgreementVersion", "agreementVersion", "Version", "version", default="1")
        if key:
            p["Agreements"][str(key)] = str(ver)
    save_player(p)
    return J({"result": "Success", "Agreements": p["Agreements"]})


@route("/api/GetRandomName")
def get_random_name():
    adjectives = ["SILLY", "SNEAKY", "HAPPY", "GRUMPY", "SPEEDY", "LAZY", "FUZZY", "TINY", "MIGHTY", "SLEEPY"]
    nouns = ["MONKE", "GORILLA", "BANANA", "APE", "CHIMP", "COCONUT", "JUNGLE", "TREE", "ROCK", "STICK"]
    name = "%s%s%d" % (random.choice(adjectives), random.choice(nouns), random.randint(0, 99))
    b = body()
    if field(b, "PlayFabId", "mothershipId", "MothershipId"):
        try:
            p = resolve_player()
            p["Nickname"] = name
            save_player(p)
        except ApiError:
            pass
    return J({"result": name, "name": name, "Name": name})


@route("/api/ReturnQueueStats")
def return_queue_stats():
    resolve_player(require=False)
    n = ccu_count()
    in_rooms = 0
    for _, pl in DB.items("players"):
        if (pl.get("Presence") or {}).get("RoomId") and _recently_seen(pl, CFG["ccu_window_sec"]):
            in_rooms += 1
    return J({"CCU": n, "PlayersInRooms": in_rooms,
              "Queues": {"DEFAULT": {"Players": max(0, n - in_rooms), "EstimatedWaitSeconds": 0},
                         "COMPETITIVE": {"Players": 0, "EstimatedWaitSeconds": 0},
                         "MINIGAMES": {"Players": 0, "EstimatedWaitSeconds": 0}}})


@route("/api/ReturnVstumpMapStats")
def return_vstump_map_stats():
    resolve_player(require=False)
    maps = [m for _, m in DB.items("maps")]
    active = [m for m in maps if m.get("isActive", True)]
    return J({"MapCount": len(maps), "ActiveMapCount": len(active),
              "TotalVotes": sum(int(m.get("voteCount", 0)) for m in maps)})


@route("/api/ShouldUserAutomutePlayer")
def should_user_automute_player():
    p = resolve_player()
    level = p.get("AutomuteLevel", "none")
    return J({"ShouldAutomute": level != "none", "AutomuteLevel": level, "result": level != "none"})


@route("/api/TryDistributeCurrencyV2")
def try_distribute_currency_v2():
    p = resolve_player()
    granted = daily_login(p)
    save_player(p)
    return J({"result": "Success", "Granted": granted,
              "AmountGranted": CFG["daily_login_shiny_rocks"] if granted else 0,
              "VirtualCurrency": p["Currency"], "shinyRocks": sr_get(p)})


@route("/api/UpdatePersonalCosmeticsList")
def update_personal_cosmetics_list():
    p = resolve_player()
    rebuild_shared_group(p)
    save_player(p)
    return J({"SharedGroupId": p["PlayFabId"] + "Inventory", "Inventory": p["SharedGroup"].get("Inventory", ""),
              "InventoryDict": p["SharedGroup"].get("InventoryDict", "{}"), "Result": "Success"})


def _store_analytics():
    raw = request.get_data(cache=True) or b""
    try:
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
    except Exception:
        pass
    text = raw.decode("utf-8", errors="replace")[:20000]
    DB.set("analytics", str(time.time_ns()), {"path": request.path, "time": iso(), "ip": request.remote_addr, "payload": text})
    excess = DB.count("analytics") - CFG["analytics_max_records"]
    if excess > 0:
        for k in DB.oldest_keys("analytics", excess):
            DB.delete("analytics", k)
    return J({"ok": True})


@route("/api/Gorillanalytics")
def gorillanalytics():
    return _store_analytics()


@route("/api/UploadGorillanalytics")
def upload_gorillanalytics():
    return _store_analytics()


@route("/api/azure/UploadGorillanalytics")
def azure_upload_gorillanalytics():
    return _store_analytics()


@route("/v1/client/analytics/event/batch")
def v1_client_analytics_event_batch():
    return _store_analytics()


def main(argv=None):
    global DB
    ap = argparse.ArgumentParser(description="Gorilla Tag backend re-implementation")
    ap.add_argument("--host", default=CFG["host"])
    ap.add_argument("--port", type=int, default=CFG["port"])
    ap.add_argument("--db", default=CFG["db"])
    ap.add_argument("--strict-auth", action="store_true", help="reject unknown players / mismatched tokens")
    ap.add_argument("--kid-mode", choices=("adult", "agegate"), default=CFG["kid_mode"],
                    help="adult = new players get a passing LEGAL_ADULT k-ID session; agegate = real opt-in + age gate flow")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args(argv)
    CFG.update({"host": a.host, "port": a.port, "db": a.db, "strict_auth": a.strict_auth, "kid_mode": a.kid_mode})
    DB = Store(CFG["db"])
    print("[%s] listening on http://%s:%d  db=%s  strict_auth=%s  kid_mode=%s" %
          (APP_VERSION, a.host, a.port, a.db, a.strict_auth, a.kid_mode))
    print("Routes: %d   Point every *ApiBaseUrl at http://<this-host>:%d (no trailing slash)" %
          (len(list(app.url_map.iter_rules())), a.port))
    app.run(host=a.host, port=a.port, debug=a.debug, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
