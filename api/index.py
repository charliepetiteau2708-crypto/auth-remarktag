import copy
import hashlib
import json
import logging
import os
import random
import secrets
import string
import time
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from json import dumps, loads
from threading import Thread
from typing import Dict, List, Optional

import requests
from flask import Flask, jsonify, request

try:
    from jose import jwt as jose_jwt
    JOSE_AVAILABLE = True
except ImportError:
    JOSE_AVAILABLE = False
    jose_jwt = None

try:
    from pymongo import MongoClient
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False
    MongoClient = None

try:
    from cryptography.hazmat.primitives import serialization
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    serialization = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GameInfo:
    def __init__(self):
        self.TitleId:   str = "88DAF"
        self.SecretKey: str = "H8NWNQDOXNUZYI8M3P7RHZ3BEIIGUAM4D6RMNC5ASICMY86TC3"
        self.ApiKey:    str = "OC|1365689723299907|6cbb75dc9a87f431a12d4aaf5bcf6cfd"

        self.photon_webhook_url:    str = ""
        self.ban_webhook_url:       str = ""
        self.vote_webhook_url:      str = ""
        self.code_webhook_url:      str = ""
        self.analytics_webhook_url: str = ""
        self.name_webhook_url:      str = ""
        self.auth_webhook_url:      str = ""
        self.general_webhook_url:   str = ""

        self.discord_bot_token: str = ""

    def get_auth_headers(self) -> dict:
        return {"Content-Type": "application/json", "X-SecretKey": self.SecretKey}

    @staticmethod
    def privacy_state_id_to_name(name: str) -> int:
        return {"VISIBLE": 0, "PUBLIC_ONLY": 1, "HIDDEN": 2}.get(name, -1)

    PrivacyStateIDtoName = privacy_state_id_to_name

settings = GameInfo()
app      = Flask(__name__)

PLAYFAB_TITLE_ID  = settings.TitleId
PLAYFAB_SECRET_KEY = settings.SecretKey
META_ACCESS_TOKEN  = "OC|1195445090309956|e1354077cff33d48a40588b28a5556d2"
MOTHERSHIP_WEBHOOK_URL = ""
MONGO_URI          = "mongodb+srv://TPHMikey:Microsoft1537215@mothership.fxwdhnd.mongodb.net/?appName=Mothership"

MOTHERSHIP_PRIVATE_KEY_PEM = b"""
-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIC1Ga7aaSAwfRBkU8abgOuAzOFxAIgm9oyEWnEbWrRQPoAoGCCqGSM49
AwEHoUQDQgAEMZ7rjMaW1C8N6jLjpczkGSXKLqOdMJsan5r1NgT/rY7Hs0xAknx8
iXfYkGMrrHs05NiqxnIUr6gJj/8HPI/2bg==
-----END EC PRIVATE KEY-----
"""

MOTHERSHIP_SECRET = None
if CRYPTO_AVAILABLE and MOTHERSHIP_PRIVATE_KEY_PEM.strip():
    try:
        MOTHERSHIP_SECRET = serialization.load_pem_private_key(
            MOTHERSHIP_PRIVATE_KEY_PEM, password=None
        )
    except Exception as e:
        logger.warning(f"[Mothership] Could not load EC private key: {e}")

ALLOWED_PACKAGE_IDS  = ["com.TPH.TPHTaggers"]
RIFT_ACCOUNT_USER_ID = "25254486430909610"
DEBUG_HTTP_LOGGING   = False

db = gorilla_db = None
tokens_collection = title_data_collection = user_data_collection = None
users_collection = progression_trees_collection = None

if MONGO_AVAILABLE and MONGO_URI:
    try:
        _client = MongoClient(MONGO_URI)
        db       = _client.get_database("mothership_db")
        gorilla_db = _client.get_database("gorilla_tag_db")
        tokens_collection           = db["mothership_tokens"]
        title_data_collection       = db["playfab_title_data"]
        user_data_collection        = db["playfab_user_data"]
        users_collection            = gorilla_db["users"]
        progression_trees_collection = gorilla_db["progression_trees"]
        logger.info("✅ MongoDB connected")
    except Exception:
        logger.warning("❌ MongoDB connection failed — Mothership DB features disabled")
        db = gorilla_db = None

PLAYERS_FILE   = "players.json"
CODES_FILE     = "codes.json"
VOTES_FILE     = "votes.json"
ROOMCODES_FILE = "roomcodes.json"

playfab_cache:  dict = {}
mute_cache:     dict = {}
poll_cache:     list = []
pending_nonces: dict = {}

BAD_WORDS = {
    "KKK", "KKX", "XKK", "KXK", "KXX", "XXK", "LEADEROFKKK", "KKKOFFICIAL",
    "KKKLORD", "KKKMEMBER", "KKKMAN", "KKKMASTER", "KKKLEADER",
    "PENIS", "DICK", "PUSSY", "VAGINA", "COCK", "CUM", "SEX", "PORN",
    "DILDO", "BIGBLACKCOCK", "FUCK", "FAG", "FAGGOT", "TRANNY", "QUEER",
    "NIG", "NIIG", "NIGG", "NIGA", "NIGGA", "NIGGER", "NIGGGER",
    "NIGER", "NIGERZ", "NIGUR", "NIGAR", "NIGR", "N1G", "N1GA", "N1GGA",
    "N1GGER", "N1GG3R", "N1GUR", "N1GER", "NI66ER", "NI99ER", "NI99",
    "N199A", "N199ER", "N199GE", "N1663R", "N1993R", "N166ER", "NIG2MONKE",
    "NIGG3R", "NIG3R", "NIG3ER", "NIG4R", "NIG5ER", "NIGEER", "NIGHER",
    "NIGYR", "NIGCER", "NIGQER", "NIGKER", "NIGCKER", "NIGIR", "NIG33R",
    "NIGAB", "NIGAMO", "NIGAS", "NIGBA", "NIGBALLS", "NIGBALL", "NIGILLA",
    "NIGZILLA", "NIGMON", "NIGNOG", "NIGSY", "NIGRE", "NIGKEY", "NIGSLAVE",
    "NIGTARD", "NIGTURD", "NIGWORD", "NIGLIT", "NIGLER", "NIGSBALL",
    "NIGVR", "NIGBOT", "NIGBOB", "NIGFART", "NIGMAN", "NIGWAD", "NIGWERD",
    "NIGUH", "NIGK", "NIGWARD", "NIQQA", "NIGDIRT", "NIBBA", "NIBBER",
    "NIGLET", "NIGOR", "NIQQER", "NIGHKA", "NIGHUR", "NIQQA", "NAGGI",
    "NEGRO", "KNEEGROW", "NATEHIG", "NATEHIGGERS", "IHATENIGGERS",
    "IHATENIG", "FUCKALLNIGGERS", "FUCKYOUNIGGA", "FUCKTHENIGGERS",
    "IHATEBLACKS", "FUCKBLACK", "PICKCOTTON", "NIGGR", "NIGGERS",
    "SANDNIG", "SNOWNIG", "DIRTYNIG", "LITTLENIG", "MASTERNIG",
    "GORILLANIG", "MONKEYNIG", "SPIDERNIG", "SPIDANIGA", "BLACKNIG",
    "BLACKNIGA", "DADDYNIGA", "GORNIGA", "WARNIG", "MYNIGA",
    "GAYNIG", "NIGAB", "NIGHA",
    "NEG", "NIGE", "NI6", "NII", "NICKER", "NICKA", "NICGER", "NICKG",
    "NIKGU", "NIKGE", "N199GE",
    "MONKEYSLAVE", "SLAVE",
    "HITLER", "HAILHITLER", "HITTLER", "H1TLER", "HITL3R", "H1TL3R", "NAZI",
    "JEW", "STINKYJEW", "GASJEW", "KILLJEW", "JEWSLAYER", "JEWSSUCK",
    "GASTHEJEW", "FUCKJEW", "KIKE", "IH8JEW",
    "CHINK",
    "GEORGEFL", "GEORGFL",
    "KYS",
    "FUCKLGBT", "FVCKLGBT", "HATELGBT", "IHATEGAY", "IH8GAY",
    "IH8LGBT", "IH8BLACK", "FUCKGAYS",
    "RACIST", "@HERE", "@EVERYONE",
    "VIPERISASKID", "SKIDDEDGAME", "SKIDDER", "VIPERISANIG",
}

OFFENSIVE_PATTERNS = [
    "FUCK CAM", "CAMRACIST", "ICAMTRUMP", "RACISTCAM", "FUCKCAM",
    "RACNSTCAM", "UACISTCAM",
]

DISCORD_API_BASE = "https://discord.com/api/v10"

def execute_cloud_script(playfab_id: str, funcname: str, funcparam: dict = {}):
    """Execute a PlayFab Cloud Script and return jsonified FunctionResult."""
    response = requests.post(
        url=f"https://{settings.TitleId}.playfabapi.com/Server/ExecuteCloudScript",
        json={"PlayFabId": playfab_id, "FunctionName": funcname, "FunctionParameter": funcparam},
        headers=settings.get_auth_headers(),
    )
    if response.status_code == 200:
        return jsonify(response.json().get("data", {}).get("FunctionResult")), 200
    return jsonify({}), response.status_code

def return_function_json(data: dict, funcname: str, funcparam: dict = {}):
    """Legacy wrapper — extracts TitlePlayerAccountId from a PlayFab webhook payload."""
    try:
        user_id = data["FunctionParameter"]["CallerEntityProfile"]["Lineage"]["TitlePlayerAccountId"]
    except (KeyError, TypeError):
        user_id = data.get("CallerEntityProfile", {}).get("Lineage", {}).get("TitlePlayerAccountId")
    return execute_cloud_script(user_id, funcname, funcparam)

def authenticate_ticket(ticket: str, expected_id: str = None) -> Optional[str]:
    """Validate a PlayFab session ticket. Returns PlayFabId on success, None on failure."""
    try:
        res = requests.post(
            f"https://{settings.TitleId}.playfabapi.com/Server/AuthenticateSessionTicket",
            json={"SessionTicket": ticket},
            headers=settings.get_auth_headers(),
        )
        if res.status_code != 200:
            return None
        user_id = res.json().get("data", {}).get("UserInfo", {}).get("PlayFabId")
        if not user_id:
            return None
        if expected_id and user_id != expected_id:
            return None
        return user_id
    except requests.exceptions.RequestException as e:
        logger.error(f"[Auth] Error: {e}")
        return None

def ban_user(playfab_id: str, name: str = None,
             reason: str = "CHEATING. PERMANENT BAN, THIS IS NOT APPEALABLE",
             duration_hours: int = 0):
    """Ban a player via PlayFab Admin API and post a Discord embed."""
    response = requests.post(
        f"https://{settings.TitleId}.playfabapi.com/Admin/BanUsers",
        headers=settings.get_auth_headers(),
        json={"Bans": [{"PlayFabId": playfab_id, "Reason": reason, "DurationInHours": duration_hours}]},
    )
    if response.status_code == 200:
        logger.info(f"[Ban] Banned {playfab_id}: {reason}")
        _send_ban_embed(playfab_id, name, reason, duration_hours)
    else:
        logger.error(f"[Ban] Failed to ban {playfab_id}: {response.text}")
    return response

def grant_cosmetic_to_player(playfab_id: str, cosmetic_id: str):
    """Grant a DLC item to a player via PlayFab Admin API."""
    return requests.post(
        f"https://{settings.TitleId}.playfabapi.com/Admin/GrantItemsToUsers",
        headers=settings.get_auth_headers(),
        json={
            "CatalogVersion": "DLC",
            "ItemGrants": [{"PlayFabId": playfab_id, "ItemId": cosmetic_id,
                            "CatalogVersion": "DLC", "Annotation": "Redeeming Code"}],
        },
    )

def get_user_internal_data(playfab_id: str, keys: list = None) -> dict:
    body = {"PlayFabId": playfab_id}
    if keys:
        body["Keys"] = keys
    return requests.post(
        f"https://{settings.TitleId}.playfabapi.com/Server/GetUserInternalData",
        headers=settings.get_auth_headers(),
        json=body,
    ).json()

def update_user_internal_data(playfab_id: str, data_dict: dict):
    return requests.post(
        f"https://{settings.TitleId}.playfabapi.com/Server/UpdateUserInternalData",
        headers=settings.get_auth_headers(),
        json={"PlayFabId": playfab_id, "Data": data_dict},
    )

def get_is_nonce_valid(nonce: str, oculus_id: str) -> bool:
    if not settings.ApiKey:
        return False
    req = requests.post(
        url=f"https://graph.oculus.com/user_nonce_validate?nonce={nonce}&user_id={oculus_id}&access_token={settings.ApiKey}",
        headers={"content-type": "application/json"},
    )
    return req.json().get("is_valid", False)

def get_client_ip() -> str:
    """Return the real client IP, respecting X-Forwarded-For proxies."""
    forwarded = request.environ.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.environ.get("REMOTE_ADDR", "unknown")

def get_org_scoped_id(oculus_id: str) -> Optional[str]:
    """Fetch the org-scoped ID for an Oculus user (used for account linking)."""
    if not settings.ApiKey:
        return None
    try:
        res = requests.get(
            f"https://graph.oculus.com/{oculus_id}?access_token={settings.ApiKey}&fields=org_scoped_id",
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        if res.status_code == 200:
            return res.json().get("org_scoped_id")
    except Exception as e:
        logger.warning(f"[OrgScope] Error fetching org_scoped_id: {e}")
    return None

def get_meta_alias(oculus_id: str) -> Optional[str]:
    """Fetch the Meta Quest alias (display name) for an Oculus user."""
    if not settings.ApiKey:
        return None
    try:
        res = requests.get(
            f"https://graph.oculus.com/{oculus_id}?access_token={settings.ApiKey}&fields=alias",
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        if res.status_code == 200:
            return res.json().get("alias")
    except Exception as e:
        logger.warning(f"[MetaAlias] Error fetching alias: {e}")
    return None

def check_session_ticket(session_ticket: str) -> bool:
    """Validate a PlayFab session ticket against the AuthenticateSessionTicket endpoint."""
    try:
        res = requests.post(
            f"https://{settings.TitleId}.playfabapi.com/Server/AuthenticateSessionTicket",
            json={"SessionTicket": session_ticket},
            headers=settings.get_auth_headers(),
            timeout=5,
        )
        return res.status_code == 200
    except Exception:
        return False

def verify_user_id(playfab_id: str) -> bool:
    """Verify that a PlayFab ID exists via GetUserAccountInfo."""
    try:
        res = requests.post(
            f"https://{settings.TitleId}.playfabapi.com/Server/GetUserAccountInfo",
            json={"PlayFabId": playfab_id},
            headers=settings.get_auth_headers(),
            timeout=5,
        )
        return res.status_code == 200
    except Exception:
        return False

def send_auth_webhook(success: bool, player_ip: str, custom_id: str = None,
                      playfab_id: str = None, oculus_id: str = None,
                      error_message: str = None, meta_alias: str = None):
    """Send a Discord embed for auth events (success or failure)."""
    if success:
        embed = {
            "color": 0x00FF00,
            "fields": [{
                "name": "✅ Player Authenticated",
                "value": (f"```ini\n"
                          f"[ IP ]: {player_ip}\n"
                          f"[CustomId]: {custom_id or 'N/A'}\n"
                          f"[PlayFabId]: {playfab_id or 'N/A'}\n"
                          f"[OculusId]: {oculus_id or 'N/A'}\n"
                          f"[MetaAlias]: {meta_alias or 'N/A'}```"),
            }],
            "author": {"name": "PlayFab Auth"},
        }
    else:
        embed = {
            "color": 0xFF0000,
            "fields": [{
                "name": "❌ Auth Failure",
                "value": (f"```ini\n"
                          f"[ IP ]: {player_ip}\n"
                          f"[CustomId]: {custom_id or 'N/A'}\n"
                          f"[OculusId]: {oculus_id or 'N/A'}\n"
                          f"[Error]: {error_message or 'Unknown'}```"),
            }],
            "author": {"name": "PlayFab Auth"},
        }

    webhook_url = getattr(settings, "auth_webhook_url", "") or settings.photon_webhook_url
    _post_discord_embed(webhook_url, embed)

def validate_input(data: dict, required_fields: List[str]) -> List[str]:
    return [f for f in required_fields if not data.get(f)]

def generate_session_id() -> str:
    return str(uuid.uuid4())

def _post_discord_embed(webhook_url: str, embed: dict):
    if not webhook_url:
        return
    try:
        res = requests.post(webhook_url, json={"embeds": [embed]},
                            headers={"Content-Type": "application/json"}, timeout=5)
        if res.status_code not in (200, 204):
            logger.warning(f"[Discord] Failed: {res.text}")
    except Exception as e:
        logger.warning(f"[Discord] Error: {e}")

def _send_ban_embed(playfab_id: str, name, reason: str, duration_hours: int):
    _post_discord_embed(settings.ban_webhook_url, {
        "title": "🔨 User Banned",
        "color": 0xFF0000,
        "fields": [
            {"name": "PlayFab ID", "value": playfab_id,                     "inline": True},
            {"name": "Duration",   "value": f"{duration_hours}h (0=perm)",  "inline": True},
            {"name": "Reason",     "value": reason,                          "inline": False},
            {"name": "Name",       "value": name or "*Unknown*",             "inline": False},
        ],
        "footer":    {"text": "Auto-issued ban"},
        "timestamp": datetime.utcnow().isoformat(),
    })

def get_discord_username(discord_id: str) -> Optional[str]:
    if not settings.discord_bot_token:
        return None
    try:
        r = requests.get(f"{DISCORD_API_BASE}/users/{discord_id}",
                         headers={"Authorization": f"Bot {settings.discord_bot_token}"})
        if r.status_code == 200:
            u = r.json()
            return u.get("global_name") or f"{u['username']}#{u.get('discriminator','0')}"
    except Exception as e:
        logger.warning(f"[Discord] Error fetching user: {e}")
    return None

def _load_json(path: str, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def _save_json(path: str, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

def load_votes():
    return _load_json(VOTES_FILE, [
        {"pollId": 2, "question": "IS TPHTAGGERS ON APPLAB BEST GAME",
         "voteOptions": ["YES", "NO"], "voteCount": [100, 150], "predictionCount": [100, 150],
         "startTime": "2025-03-17T18:00:00", "endTime": "2025-03-24T17:00:00", "isActive": False},
        {"pollId": 3, "question": "IS TPHTAGGERS THE BEST GAME ON APPLAB?",
         "voteOptions": ["YES", "NO"], "voteCount": [0, 0], "predictionCount": [0, 0],
         "startTime": "2025-03-24T18:00:00", "endTime": "2025-04-27T17:00:00", "isActive": True},
    ])

def save_votes(polls): _save_json(VOTES_FILE, polls)

def load_codes() -> list: return _load_json(CODES_FILE, [])

def save_codes(codes): _save_json(CODES_FILE, codes)

def find_code(codes: list, code_id: str):
    for c in codes:
        if c["id"].upper() == code_id.upper():
            return c
    return None

def load_room_data() -> dict:
    return _load_json(ROOMCODES_FILE, {})

def save_token_to_db(user_id: str, mothership_id: str, token: str, expiration_ms: int) -> bool:
    if tokens_collection is None:
        logger.warning("[Mothership] Mongo unavailable — skipping token save")
        return False
    try:
        tokens_collection.update_one(
            {"user_id": user_id},
            {"$set": {"mothership_token": token, "expiration_time": expiration_ms,
                      "last_updated": datetime.now(timezone.utc)},
             "$setOnInsert": {"mothership_id": mothership_id,
                              "created_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        return True
    except Exception:
        logger.warning("[Mothership] MongoDB write failed:\n" + traceback.format_exc())
        return False

def get_title_data_from_mongo(keys: list = None):
    if title_data_collection is None:
        return None
    try:
        doc = title_data_collection.find_one({}, sort=[("last_updated", -1)])
        if not doc:
            return None
        results = doc.get("Results", [])
        if keys:
            results = [r for r in results if r.get("key") in keys]
        return results
    except Exception:
        logger.warning("[Mothership] Mongo title data fetch failed:\n" + traceback.format_exc())
        return None

def get_user_data_from_mongo(user_id: str, key_name: str):
    if user_data_collection is None:
        return None
    try:
        return user_data_collection.find_one({"user_id": user_id, "key_name": key_name})
    except Exception:
        logger.warning("[Mothership] Mongo user data fetch failed:\n" + traceback.format_exc())
        return None

def save_user_data_to_mongo(user_id: str, key_name: str, value) -> bool:
    if user_data_collection is None:
        return False
    try:
        metadata_id = str(uuid.uuid4())
        user_data_collection.update_one(
            {"user_id": user_id, "key_name": key_name},
            {"$set": {"value": value, "last_written_by": user_id,
                      "last_updated": datetime.now(timezone.utc)},
             "$inc": {"generation": 1},
             "$setOnInsert": {"id": "", "metadata_id": metadata_id,
                              "created_by": user_id, "created_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        return True
    except Exception:
        logger.warning("[Mothership] Mongo user data save failed:\n" + traceback.format_exc())
        return False

def send_mothership_webhook(title: str, claims: dict, user_id: str,
                            error: str = None, color: int = 3447003):
    if not MOTHERSHIP_WEBHOOK_URL:
        return
    desc = f"**User ID:** {user_id}\n"
    if error:
        desc += f"**Error:** {error}\n"
    try:
        requests.post(MOTHERSHIP_WEBHOOK_URL, json={"embeds": [{
            "title":       title,
            "description": desc + "\n```json\n" + json.dumps(claims, indent=2)[:1800] + "\n```",
            "color":       color,
        }]}, timeout=5)
    except Exception as e:
        logger.warning(f"[Mothership] Webhook failed: {e}")

def issue_mothership_token(user_id: str, claims: dict):
    if not JOSE_AVAILABLE or MOTHERSHIP_SECRET is None:
        return jsonify({"error": "Mothership JWT not configured"}), 500

    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "sub":             user_id,
        "externalService": "QUEST",
        "nbf":             int(datetime.now(timezone.utc).timestamp()),
        "iat":             int(datetime.now(timezone.utc).timestamp()),
        "exp":             int(expiration.timestamp()),
    }
    token = jose_jwt.encode(payload, MOTHERSHIP_SECRET, algorithm="ES256")
    save_token_to_db(user_id, user_id, token, int(expiration.timestamp() * 1000))
    send_mothership_webhook("✅ Mothership Token Issued", claims, user_id)

    return jsonify({
        "MothershipToken":          token,
        "MothershipId":             user_id,
        "ExpirationTime":           int(expiration.timestamp() * 1000),
        "ExternalProviderId":       user_id,
        "ExternalProviderUsername": "",
        "IsPrimaryId":              True,
        "PlayerId":                 user_id,
        "Tags":                     None,
        "Token":                    token,
    }), 200

def _decode_mothership_token(token: str) -> Optional[str]:
    """Decode JWT and return sub (user_id), or None on failure."""
    if not JOSE_AVAILABLE:
        return None
    try:
        decoded = jose_jwt.decode(token, None, options={"verify_signature": False})
        return decoded.get("sub")
    except Exception:
        return None

ENTITLEMENTS = {
    "SI_TechPoints":     {"entitlement_id": "d4a0fad9-4602-435d-b379-cd5f69fb4321", "name": "SI_TechPoints",     "in_game_id": "SI_TECH_POINTS",       "title_id": "f3e9fb19", "env_id": "7f3a99dd-5598-4725-98cf-6538d28feb9f", "type": "CURRENCY",              "tags": None},
    "SI_StrangeWood":    {"entitlement_id": "078b85fb-c0d9-44d5-a3ca-e325819b13cd", "name": "SI_StrangeWood",    "in_game_id": "SI_STRANGE_WOOD",      "title_id": "f3e9fb19", "env_id": "7f3a99dd-5598-4725-98cf-6538d28feb9f", "type": "CURRENCY_LOW_SCRUTINY", "tags": None},
    "SI_VibratingSpring":{"entitlement_id": "5150d276-db1a-4263-bff4-edbe7b55f841", "name": "SI_VibratingSpring","in_game_id": "SI_VIBRATING_SPRING", "title_id": "f3e9fb19", "env_id": "7f3a99dd-5598-4725-98cf-6538d28feb9f", "type": "CURRENCY_LOW_SCRUTINY", "tags": None},
    "SI_WeirdGear":      {"entitlement_id": "427839b6-58a4-4e8b-9cb4-3d48cb1fb513", "name": "SI_WeirdGear",      "in_game_id": "SI_WEIRD_GEAR",        "title_id": "f3e9fb19", "env_id": "7f3a99dd-5598-4725-98cf-6538d28feb9f", "type": "CURRENCY_LOW_SCRUTINY", "tags": None},
    "SI_FloppyMetal":    {"entitlement_id": "11844689-b2d0-4f02-923f-3bf49ba3aac6", "name": "SI_FloppyMetal",    "in_game_id": "SI_FLOPPY_METAL",      "title_id": "f3e9fb19", "env_id": "7f3a99dd-5598-4725-98cf-6538d28feb9f", "type": "CURRENCY_LOW_SCRUTINY", "tags": None},
    "SI_BouncySand":     {"entitlement_id": "8040ba58-afaa-44d3-bc0a-4d7864abf45d", "name": "SI_BouncySand",     "in_game_id": "SI_BOUNCY_SAND",       "title_id": "f3e9fb19", "env_id": "7f3a99dd-5598-4725-98cf-6538d28feb9f", "type": "CURRENCY_LOW_SCRUTINY", "tags": None},
    "GR_ResearchPoints": {"entitlement_id": "88342aff-549c-42dc-9998-ccc8160ba254", "name": "GR_ResearchPoints", "in_game_id": "GR_RESEARCH_POINTS",   "title_id": "f3e9fb19", "env_id": "7f3a99dd-5598-4725-98cf-6538d28feb9f", "type": "CURRENCY",              "tags": None},
}

DEFAULT_PROGRESSION_TREE_DATA = {
    "data": {"trees": [
        {"id": "f1e898ab-9c13-47f5-a044-cd7be3f51246", "name": "SI_Gadgets", "track_id": None,
         "created_at": "2025-10-02T15:53:15.278Z",
         "NodeDefinitions": [
             {"id": "408cc525-5013-4fe3-849a-ae90cca3294b", "name": "Initialize",
              "tree_id": "f1e898ab-9c13-47f5-a044-cd7be3f51246",
              "prerequisite_entitlements": None, "prerequisite_levels": None, "prerequisite_nodes": None,
              "transaction": {"transaction_id": "dee9bc37-5d7b-425f-8fed-4abb09a47ad8", "name": "T_SI_Initialize",
                              "inventory_changes": {"SI_TechPoints": {"Delta": 8}, "SI_StrangeWood": {"Delta": 8}, "SI_VibratingSpring": {"Delta": 8}}},
              "cost": None, "unlocked": True},
             {"id": "1001f2a8-1555-4356-bac0-ad5dc85038d2", "name": "Stilt_Unlock",
              "tree_id": "f1e898ab-9c13-47f5-a044-cd7be3f51246",
              "prerequisite_entitlements": None, "prerequisite_levels": None, "prerequisite_nodes": None,
              "transaction": None, "cost": {"SI_TechPoints": {"Delta": 8}, "SI_StrangeWood": {"Delta": 8}}, "unlocked": False},
             {"id": "1fb647a1-dcb5-48ea-ac60-59e59f49e89b", "name": "Thruster_Unlock",
              "tree_id": "f1e898ab-9c13-47f5-a044-cd7be3f51246",
              "prerequisite_entitlements": None, "prerequisite_levels": None, "prerequisite_nodes": None,
              "transaction": None, "cost": {"SI_TechPoints": {"Delta": 8}, "SI_VibratingSpring": {"Delta": 8}}, "unlocked": False},
             {"id": "81e9c384-9b08-4349-8039-ab2eda3e7c20", "name": "Platform_Unlock",
              "tree_id": "f1e898ab-9c13-47f5-a044-cd7be3f51246",
              "prerequisite_entitlements": None, "prerequisite_levels": None, "prerequisite_nodes": None,
              "transaction": None, "cost": {"SI_TechPoints": {"Delta": 8}, "SI_StrangeWood": {"Delta": 8}}, "unlocked": False},
             {"id": "90d1fddd-9a7c-4799-9f5f-75615a9820ec", "name": "Blaster_Standard_Unlock",
              "tree_id": "f1e898ab-9c13-47f5-a044-cd7be3f51246",
              "prerequisite_entitlements": None, "prerequisite_levels": None, "prerequisite_nodes": None,
              "transaction": None, "cost": {"SI_WeirdGear": {"Delta": 12}, "SI_TechPoints": {"Delta": 16}}, "unlocked": False},
         ]},
        {"id": "fcf4207d-399d-4678-a2a5-f204dbe3df6a", "name": "GRTools", "track_id": None,
         "created_at": "2025-07-22T18:07:38.310Z",
         "NodeDefinitions": [
             {"id": "9acd1c2c-c122-40c1-8a5c-4e10610711b1", "name": "EnergyEfficiency",
              "tree_id": "fcf4207d-399d-4678-a2a5-f204dbe3df6a",
              "prerequisite_entitlements": None, "prerequisite_levels": None, "prerequisite_nodes": None,
              "transaction": None, "cost": None, "unlocked": True},
             {"id": "d4f88967-e507-44a8-9ef3-cd2f598ed1de", "name": "ChargeBaton",
              "tree_id": "fcf4207d-399d-4678-a2a5-f204dbe3df6a",
              "prerequisite_entitlements": None, "prerequisite_levels": None, "prerequisite_nodes": None,
              "transaction": None, "cost": None, "unlocked": True},
             {"id": "40c36a94-de4f-4298-bc08-e4e0128499ee", "name": "FlashTool",
              "tree_id": "fcf4207d-399d-4678-a2a5-f204dbe3df6a",
              "prerequisite_entitlements": None, "prerequisite_levels": None, "prerequisite_nodes": None,
              "transaction": None, "cost": {"GR_ResearchPoints": {"Delta": 4}}, "unlocked": False},
         ]},
    ]}
}

def transform_cost_format(cost_dict: dict):
    if cost_dict is None:
        return None
    result = {}
    for currency, data in cost_dict.items():
        delta = data.get("Delta", 0) if isinstance(data, dict) else data
        ent = ENTITLEMENTS.get(currency)
        result[currency] = {"Entitlement": ent.copy(), "Delta": delta} if ent else {"Delta": delta}
    return result

def transform_transaction_format(txn: dict, title_id: str, env_id: str):
    if txn is None:
        return None
    t = txn.copy()
    t.setdefault("title_id", title_id)
    t.setdefault("env_id", env_id)
    for k in ("external_service_name", "external_service_entitlement_id",
              "revokable", "requires_external_fulfillment", "repeatable", "real_money_price"):
        t.setdefault(k, None)
    t.setdefault("sunset", False)
    if t.get("inventory_changes"):
        t["inventory_changes"] = transform_cost_format(t["inventory_changes"])
    return t

def get_progression_tree_data() -> dict:
    if progression_trees_collection is None:
        return DEFAULT_PROGRESSION_TREE_DATA
    try:
        doc = progression_trees_collection.find_one({"_id": "progression_trees"})
        if doc:
            doc.pop("_id", None)
            return doc
    except Exception:
        pass
    return DEFAULT_PROGRESSION_TREE_DATA

@app.before_request
def log_request_in():
    if not DEBUG_HTTP_LOGGING:
        return
    logger.info(f"\n📥 {request.method} {request.path}")
    for k, v in request.headers.items():
        logger.info(f"  {k}: {v}")
    body = request.get_data(as_text=True)
    if body:
        logger.info(f"Body: {body[:500]}")

@app.after_request
def log_response_out(response):
    if DEBUG_HTTP_LOGGING:
        logger.info(f"📤 {response.status}")
    return response

@app.route("/", methods=["POST", "GET"])
def main():
    return "Hello"

@app.route("/api/PlayFabAuthentication",    methods=["POST", "GET"])
@app.route("/re/api/PlayFabAuthentication", methods=["POST"])
@app.route("/pf/api/PlayFabAuthentication", methods=["POST"])
@app.route("/reals/api/PlayFabAuthentication", methods=["POST"])
@app.route("/rea/api/PlayFabAuthentication",  methods=["POST"])
@app.route("/real/api/PlayFabAuthentication", methods=["POST"])
def playfab_authentication():
    rjson     = request.get_json(silent=True) or {}
    client_ip = get_client_ip()

    required_fields = ["Nonce", "AppId", "Platform", "OculusId"]
    missing = [f for f in required_fields if not rjson.get(f)]
    if missing:
        send_auth_webhook(False, client_ip, oculus_id=rjson.get("OculusId"),
                          error_message=f"Missing parameter(s): {', '.join(missing)}")
        return jsonify({"Message": f"Missing parameter(s): {', '.join(missing)}",
                        "Error": f"BadRequest-No{missing[0]}"}), 401

    if rjson.get("AppId") != settings.TitleId:
        send_auth_webhook(False, client_ip, oculus_id=rjson.get("OculusId"),
                          error_message="App ID mismatch")
        return jsonify({"Message": "Request sent for the wrong App ID",
                        "Error": "BadRequest-AppIdMismatch"}), 400

    platform = rjson.get("Platform", "")
    if platform == "Windows":
        send_auth_webhook(False, client_ip, oculus_id=rjson.get("OculusId"),
                          error_message="Windows platform blocked")
        return jsonify({"Message": "Forbidden platform", "Error": "Forbidden-Platform"}), 403

    custom_id = rjson.get("CustomId", "")
    if custom_id and not custom_id.startswith(("OC", "PI")):
        send_auth_webhook(False, client_ip, custom_id=custom_id,
                          error_message="Invalid CustomId prefix")
        return jsonify({"Message": "Bad request", "Error": "BadRequest-IncorrectPrefix"}), 400

    oculus_id = rjson["OculusId"]

    org_scoped_id = get_org_scoped_id(oculus_id)
    if not org_scoped_id:
        send_auth_webhook(False, client_ip, custom_id=custom_id, oculus_id=oculus_id,
                          error_message="Invalid Oculus ID or org-scoped ID lookup failed")
        return jsonify({"Message": "Invalid Oculus ID",
                        "Error": "BadRequest-InvalidOculusId"}), 400

    server_custom_id = f"OCULUS{org_scoped_id}"
    if server_custom_id == "OCULUS0":
        ban_req = requests.post(
            f"https://{settings.TitleId}.playfabapi.com/Admin/BanUsers",
            json={"Bans": [{"PlayFabId": rjson.get("currentPlayerId", ""),
                            "DurationInHours": None, "Reason": "CHEATING - FAKE ORG SCOPED ID"}]},
            headers=settings.get_auth_headers(),
        )
        send_auth_webhook(False, client_ip, custom_id=custom_id, oculus_id=oculus_id,
                          error_message="OCULUS0 anti-cheat triggered")
        return jsonify({"Message": "Banned for cheating", "Error": "Banned"}), 403

    meta_alias = get_meta_alias(oculus_id)

    login_req = requests.post(
        url=f"https://{settings.TitleId}.playfabapi.com/Server/LoginWithServerCustomId",
        json={"ServerCustomId": server_custom_id, "CreateAccount": True},
        headers=settings.get_auth_headers(),
    )

    if login_req.status_code == 200:
        data         = login_req.json().get("data", {})
        playfab_id   = data.get("PlayFabId")
        session      = data.get("SessionTicket")
        entity       = data.get("EntityToken", {})
        entity_token = entity.get("EntityToken")
        entity_id    = entity.get("Entity", {}).get("Id")
        entity_type  = entity.get("Entity", {}).get("Type")

        if custom_id:
            try:
                requests.post(
                    f"https://{settings.TitleId}.playfabapi.com/Server/LinkServerCustomId",
                    json={"ForceLink": True, "PlayFabId": playfab_id, "ServerCustomId": custom_id},
                    headers=settings.get_auth_headers(),
                )
            except Exception as e:
                logger.warning(f"[Auth] LinkServerCustomId failed: {e}")

        try:
            requests.post(
                f"https://{settings.TitleId}.playfabapi.com/Client/LinkCustomID",
                json={"CustomId": server_custom_id, "ForceLink": True},
                headers={"Content-Type": "application/json", "X-Authorization": session},
            )
        except Exception as e:
            logger.warning(f"[Auth] LinkCustomID failed: {e}")

        send_auth_webhook(True, client_ip, custom_id=custom_id, playfab_id=playfab_id,
                          oculus_id=oculus_id, meta_alias=meta_alias)

        session_id = generate_session_id()
        return jsonify({
            "PlayFabId":     playfab_id,
            "SessionTicket": session,
            "EntityToken":   entity_token,
            "EntityId":      entity_id,
            "EntityType":    entity_type,
            "SessionId":     session_id,
        }), 200

    else:
        if login_req.status_code == 403:
            ban_info = login_req.json()
            if ban_info.get("errorCode") == 1002:
                details = ban_info.get("errorDetails", {})
                key     = next(iter(details.keys()), None)
                exp     = (details.get(key, []) or ["Indefinite"])[0]
                send_auth_webhook(False, client_ip, custom_id=custom_id, oculus_id=oculus_id,
                                  error_message=f"Banned: {key}")
                return jsonify({"BanMessage": key, "BanExpirationTime": exp}), 403
            err_msg = ban_info.get("errorMessage", "Forbidden")
            send_auth_webhook(False, client_ip, custom_id=custom_id, oculus_id=oculus_id,
                              error_message=err_msg)
            return jsonify({"Error": "PlayFab Error", "Message": err_msg}), 403

        err = login_req.json()
        err_msg = err.get("errorMessage", "An error occurred.")
        send_auth_webhook(False, client_ip, custom_id=custom_id, oculus_id=oculus_id,
                          error_message=err_msg)
        return jsonify({"Error": "PlayFab Error", "Message": err_msg}), login_req.status_code

@app.route("/api/CachePlayFabId", methods=["POST", "GET"])
def cache_playfab_id():
    rjson = request.get_json(silent=True) or {}

    if "SessionTicket" in rjson and "PlayFabId" not in rjson:
        rjson["PlayFabId"] = rjson["SessionTicket"].split("-")[0]
    pid = rjson.get("PlayFabId")
    if not pid:
        return jsonify({"Message": "Try Again Later."}), 404
    playfab_cache[pid] = rjson
    logger.info(f"[Cache] Cached PlayFabId: {pid}")
    return jsonify({"Message": "Authed", "PlayFabId": pid}), 200

@app.route("/nonce", methods=["GET"])
def nonce_endpoint():
    try:
        value = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        return jsonify({"Nonce": value}), 200
    except Exception as e:
        return jsonify({"Error": str(e)}), 500

@app.route("/api/TitleData", methods=["POST", "GET"])
def title_data():
    response = requests.post(
        url=f"https://{settings.TitleId}.playfabapi.com/Server/GetTitleData",
        headers=settings.get_auth_headers(),
    )
    if response.status_code == 200:
        raw  = response.json().get("data", {}).get("Data", {})
        data = json.loads(json.dumps(raw).replace("\\\\", "\\"))
        return jsonify(data)
    return jsonify({}), response.status_code

@app.route("/api/CheckForBadName", methods=["POST", "GET"])
def check_for_bad_name():
    body      = request.get_json(silent=True) or {}
    func_arg  = body.get("FunctionArgument") or body.get("FunctionResult") or {}
    name      = (func_arg.get("name") or "").upper().strip()
    playfab_id = body.get("CallerEntityProfile", {}).get("Lineage", {}).get("MasterPlayerAccountId")

    logger.info(f"[NameCheck] name={name!r} playfab_id={playfab_id}")

    banned     = False
    ban_reason = "No ban"

    for pattern in OFFENSIVE_PATTERNS:
        if pattern in name:
            ban_reason = "DEFAMATION DETECTED. CONTINUED USE WILL RESULT IN LEGAL ACTION"
            if playfab_id:
                ban_user(playfab_id, name=name, reason=ban_reason)
            banned = True
            break

    if not banned:
        for word in BAD_WORDS:
            if word in name:
                ban_reason = f"BAD NAME DETECTED: {name}"
                if playfab_id:
                    ban_user(playfab_id, name=name, reason=ban_reason, duration_hours=1)
                banned = True
                break

    _post_discord_embed(settings.name_webhook_url, {
        "title": "Name Entry",
        "color": 0xFF5733 if banned else 0x4CAF50,
        "fields": [
            {"name": "Entry",      "value": name or "N/A",           "inline": True},
            {"name": "PlayFab ID", "value": playfab_id or "Unknown", "inline": True},
            {"name": "Action",     "value": ban_reason,              "inline": False},
        ],
    })

    return jsonify({"result": 2 if banned else 0, "banLength": -1})

@app.route("/api/GetRandomName", methods=["POST", "GET"])
@app.route("/api/GetName",       methods=["POST", "GET"])
@app.route("/api/v2/GetName",    methods=["POST", "GET"])
def get_random_name():
    return jsonify({"result": f"GORILLA{random.randint(1000, 9999)}"})

@app.route("/api/GetAcceptedAgreements", methods=["POST", "GET"])
def get_accepted_agreements():
    body = request.get_json(silent=True) or {}
    func_result = body.get("FunctionResult", {})
    if func_result:
        return jsonify(func_result)
    return jsonify({"PrivacyPolicy": "2024.09.20", "TOS": "2024.09.20", "EULA": "2024.09.20"}), 200

@app.route("/api/SubmitAcceptedAgreements", methods=["POST", "GET"])
def submit_accepted_agreements():
    rjson      = request.get_json(silent=True) or {}
    ticket     = rjson.get("PlayFabTicket")
    agreements = rjson.get("Agreements", {})

    if ticket:
        auth = requests.post(
            f"https://{settings.TitleId}.playfabapi.com/Server/AuthenticateSessionTicket",
            json={"SessionTicket": ticket},
            headers=settings.get_auth_headers(),
        )
        if auth.status_code != 200:
            return "", 400

        playfab_id = auth.json().get("data", {}).get("UserInfo", {}).get("PlayFabId")
        for key, val in agreements.items():
            requests.post(
                f"https://{settings.TitleId}.playfabapi.com/Server/UpdateUserData",
                headers=settings.get_auth_headers(),
                json={"PlayFabId": playfab_id, "Data": {f"accepted_agreement:{key}": val}},
            )

    func_result = rjson.get("FunctionResult", {})
    if func_result:
        return jsonify(func_result)
    return jsonify({"status": "ok", "PrivacyPolicy": "2024.09.20", "TOS": "2024.09.20"}), 200

@app.route("/api/ConsumeOculusIAP", methods=["POST", "GET"])
def consume_oculus_iap():
    rjson   = request.get_json(silent=True) or {}
    missing = validate_input(rjson, ["userID", "nonce", "sku"])
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    user_id = rjson.get("userID")
    nonce   = rjson.get("nonce")
    sku     = rjson.get("sku")

    response = requests.post(
        url=f"https://graph.oculus.com/consume_entitlement?nonce={nonce}&user_id={user_id}&sku={sku}&access_token={settings.ApiKey}",
        headers={"content-type": "application/json"},
    )
    if response.json().get("success"):
        return jsonify({"result": True})
    return jsonify({"error": True, "message": response.json().get("message", "Consume failed")})

@app.route("/api/ConsumeCodeItem",       methods=["POST"])
@app.route("/re/api/ConsumeCodeItem",    methods=["POST"])
@app.route("/pf/api/ConsumeCodeItem",    methods=["POST"])
@app.route("/reals/api/ConsumeCodeItem", methods=["POST"])
@app.route("/rea/api/ConsumeCodeItem",   methods=["POST"])
@app.route("/real/api/ConsumeCodeItem",  methods=["POST"])
def consume_code_item():
    try:
        data       = request.get_json()
        code_id    = (data.get("itemGUID") or "").upper()
        playfab_id = data.get("playFabID")

        codes      = load_codes()
        code_entry = find_code(codes, code_id)

        if not code_entry:
            return jsonify({"result": "CodeNotFound"}), 404

        if code_entry.get("redeemed"):
            return jsonify({"result": "AlreadyRedeemed",
                            "playFabItemName": code_entry.get("cosmetic")}), 200

        grant_resp = grant_cosmetic_to_player(playfab_id, code_entry["cosmetic"])
        if grant_resp.status_code != 200:
            return jsonify({"result": "GrantFailed", "error": grant_resp.text}), 500

        code_entry["redeemed"] = True
        save_codes(codes)

        _post_discord_embed(settings.code_webhook_url, {
            "title": "🎁 Code Redeemed",
            "description": (f"**PlayFab ID**: {playfab_id}\n"
                            f"**Code**: `{code_id}`\n"
                            f"**Cosmetic**: `{code_entry['cosmetic']}`"),
            "color": 0x00FF00,
        })

        return jsonify({"result": "Success", "itemID": code_id,
                        "playFabItemName": code_entry["cosmetic"]}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/SetPrivacyState",    methods=["POST"])
@app.route("/re/api/SetPrivacyState", methods=["POST"])
def set_privacy_state():
    rjson      = request.get_json()
    playfab_id = rjson.get("PlayFabId", "")
    privacy    = rjson.get("PrivacyState", "VISIBLE")
    ticket     = rjson.get("PlayFabTicket", "")

    if not playfab_id or not ticket or settings.privacy_state_id_to_name(privacy) == -1:
        return "", 400

    auth = requests.post(
        f"https://{settings.TitleId}.playfabapi.com/Server/AuthenticateSessionTicket",
        json={"SessionTicket": ticket},
        headers=settings.get_auth_headers(),
    )
    if (auth.status_code != 200
            or auth.json()["data"]["UserInfo"]["PlayFabId"] != playfab_id):
        return "", 400

    requests.post(
        f"https://{settings.TitleId}.playfabapi.com/Server/UpdateUserInternalData",
        headers=settings.get_auth_headers(),
        json={"PlayFabId": playfab_id, "Data": {"PrivacyState": privacy}},
    )
    return jsonify({"statusCode": 200, "error": None}), 200

@app.route("/api/GetFriendsV2", methods=["POST"])
def get_friends_v2():
    rjson      = request.get_json()
    playfab_id = rjson.get("PlayFabId", "")
    ticket     = rjson.get("PlayFabTicket", "")

    if not playfab_id or not ticket:
        return "Missing fields", 400

    auth = requests.post(
        f"https://{settings.TitleId}.playfabapi.com/Server/AuthenticateSessionTicket",
        json={"SessionTicket": ticket},
        headers=settings.get_auth_headers(),
    )
    if (auth.status_code != 200
            or auth.json()["data"]["UserInfo"]["PlayFabId"] != playfab_id):
        return "", 400

    internal = get_user_internal_data(playfab_id).get("data", {}).get("Data", {})
    friend_str        = internal.get("Friends",      {}).get("Value", "")
    privacy_state_str = internal.get("PrivacyState", {}).get("Value", "VISIBLE")
    room_data         = load_room_data()

    friends = []
    for fid in friend_str.split(","):
        fid = fid.strip()
        if not fid:
            continue
        fd_resp = get_user_internal_data(fid)
        if fd_resp.get("code") != 200 and "data" not in fd_resp:
            continue

        d = fd_resp.get("data", {}).get("Data", {})

        def clean(x): return None if x in ("null", "") else x

        nickname     = clean(d.get("Nickname", {}).get("Value", ""))
        zone         = clean(d.get("Zone",     {}).get("Value", ""))
        region       = clean(d.get("Region",   {}).get("Value", ""))
        is_public    = d.get("IsPublic", {}).get("Value", "false")
        friend_priv  = d.get("PrivacyState", {}).get("Value", "VISIBLE")
        room_id      = room_data.get(fid)

        presence = {"friendLinkId": fid, "userName": nickname,
                    "roomId": None, "zone": None, "region": None, "isPublic": is_public}

        if friend_priv == "VISIBLE":
            presence.update({"roomId": room_id, "zone": zone, "region": region, "isPublic": is_public})
        elif friend_priv == "PUBLIC_ONLY" and is_public == "true":
            presence.update({"roomId": room_id, "zone": zone, "region": region, "isPublic": is_public})

        friends.append({"presence": presence, "created": datetime.now().isoformat()})

    return jsonify({
        "result": {"friends": friends,
                   "myPrivacyState": settings.privacy_state_id_to_name(privacy_state_str)},
        "statusCode": 200,
        "error": None,
    })

@app.route("/api/RequestFriend",    methods=["POST"])
@app.route("/re/api/RequestFriend", methods=["POST"])
def request_friend():
    rjson          = request.get_json()
    playfab_id     = rjson.get("PlayFabId", "")
    friend_link_id = rjson.get("FriendFriendLinkId", "")
    ticket         = rjson.get("PlayFabTicket", "")

    if not playfab_id:     return "Must supply a valid PlayFab ID", 400
    if not friend_link_id: return "Must supply a valid FriendFriendLinkId", 400
    if authenticate_ticket(ticket, playfab_id) is None:
        return "", 500

    data = get_user_internal_data(playfab_id)
    friends_str = data.get("data", {}).get("Data", {}).get("Friends", {}).get("Value", "")
    friends = set(friends_str.split(",")) if friends_str else set()
    friends.add(friend_link_id)
    update_user_internal_data(playfab_id, {"Friends": ",".join(friends)})
    return jsonify({"statusCode": 200, "error": None}), 200

@app.route("/api/RemoveFriend",    methods=["POST"])
@app.route("/re/api/RemoveFriend", methods=["POST"])
def remove_friend():
    rjson          = request.get_json()
    playfab_id     = rjson.get("PlayFabId", "")
    friend_link_id = rjson.get("FriendFriendLinkId", "")
    my_link_id     = rjson.get("MyFriendLinkId", "")
    ticket         = rjson.get("PlayFabTicket", "")

    if not playfab_id:     return "Must supply a valid PlayFab ID", 400
    if not friend_link_id: return "Must supply a valid FriendFriendLinkId", 400
    if authenticate_ticket(ticket, playfab_id) is None:
        return "Unauthorized", 403

    for a, b in [(playfab_id, friend_link_id), (friend_link_id, my_link_id)]:
        d = get_user_internal_data(a)
        fs = d.get("data", {}).get("Data", {}).get("Friends", {}).get("Value", "")
        friends = set(fs.split(",")) if fs else set()
        friends.discard(b)
        update_user_internal_data(a, {"Friends": ",".join(friends)})

    return jsonify({"statusCode": 200, "error": None}), 200

@app.route("/api/GetQuestStatus",    methods=["POST"])
@app.route("/re/api/GetQuestStatus", methods=["POST"])
def get_quest_status():
    rjson      = request.get_json()
    playfab_id = rjson.get("PlayFabId")
    ticket     = rjson.get("PlayFabTicket")

    if authenticate_ticket(ticket, playfab_id) is None:
        return "", 400

    try:
        val_str = requests.post(
            f"https://{settings.TitleId}.playfabapi.com/Server/GetUserData",
            headers=settings.get_auth_headers(),
            json={"PlayFabId": playfab_id, "Keys": ["progression_v1"]},
        ).json()["data"]["Data"]["progression_v1"]["Value"]
        result = loads(val_str)
    except Exception:
        result = {"dailyPoints": {}, "weeklyPoints": {}, "userPointsTotal": 0}

    return jsonify({"result": result, "statusCode": 200, "error": None})

@app.route("/api/SetQuestComplete", methods=["POST"])
def set_quest_complete():
    rjson      = request.get_json()
    playfab_id = rjson.get("PlayFabId")
    ticket     = rjson.get("PlayFabTicket")

    if authenticate_ticket(ticket, playfab_id) is None:
        return "", 400

    try:
        val_str = requests.post(
            f"https://{settings.TitleId}.playfabapi.com/Admin/GetUserData",
            headers=settings.get_auth_headers(),
            json={"PlayFabId": playfab_id, "Keys": ["progression_v1"]},
        ).json()["data"]["Data"]["progression_v1"]["Value"]
        current = loads(val_str)
    except Exception:
        current = {"dailyPoints": {}, "weeklyPoints": {}, "userPointsTotal": 0}

    today   = datetime.utcnow().strftime("%m/%d/%Y")
    week... (33 KB left)
