from flask import Flask, request, jsonify
import json
import hashlib
import requests
import uuid
import time
import os

app = Flask(__name__)

TITLE_ID = ("7410A")
SECRET_KEY = ("YQTCJTHXITO5I1XCX7RSZA3WMC6R16J8RKEY5MH11EQ4DSZPGI")
DISCORD_WEBHOOK = ("https://discord.com/api/webhooks/1566549583650095124/vMl_vwS6eZ7E1OdKvhw-tzlcKlhsXd2e3L3Xz478tFPuJDGyptwlcgR-3SHZdc2JSV0H")
PHOTON_WEBHOOK_URL = ("https://discord.com/api/webhooks/1567328180589822123/gvYn4gRdC3bJYQypCzYpw8nnyQ3y3PXqDLChP69rsQyV3EZEvp_J-wrDyLihKFOsjL2R")

@app.route("/", methods=["POST", "GET"])
def main():
    return "Backends For depso ty for being with the server :)"

def Tippys_Fetch_Poll():
    global poll_shit

    whatsabool = request.get_json()

    TitleId = whatsabool.get("settings.TitleId")
    PlayFabId = whatsabool.get("PlayFabId")
    PlayFabTicket = whatsabool.get("PlayFabTicket")

    vote_stuff = [
        {
            "PollId": 2,
            "Question": "ARE YOU IN THE DISCORD YET?",
            "VoteOptions": ["YES", "NO"],
            "VoteCount": [],
            "PredictionCount": [],
            "StartTime": f"{date.today().strftime('%Y-%m-%d')}",
            "EndTime": "2025-08-17T17:00:00",
            "isActive": True
        },
        {
            "PollId": 3,
            "Question": "AM I SIGMA?",
            "VoteOptions": ["YESSS", "NO!"],
            "VoteCount": [184439, 0],
            "PredictionCount": [102522, 110490],
            "StartTime": "2025-03-07T18:00:00",
            "EndTime": "2025-03-14T17:00:00",
            "isActive": False
        }
    ]

    poll_shit = vote_stuff

    return jsonify(vote_stuff), 200

@app.route("/api/Vote", methods=["POST"])
def Tippys_VoteApi():
    VOTING_WEBHOOK = ""

    get = request.get_json()

    PollId = get.get("PollId")
    TitleId = get.get("TitleId")
    PlayFabId = get.get("PlayFabId")
    OculusId = get.get("OculusId")
    UserNonce = get.get("UserNonce")
    UserPlatform = get.get("UserPlatform")
    OptionIndex = get.get("OptionIndex")
    IsPrediction = get.get("IsPrediction")
    PlayFabTicket = get.get("PlayFabTicket")
    AppVersion = get.get("AppVersion")

    if get is None:
        return jsonify({"Message": "Something Happened"}), 400

    find = next((p for p in poll_shit if p["PollId"] == PollId), None)

    if not find:
        return jsonify({"Message": "Poll not found"}), 404

    embed = {
        "embeds": [
            {
                "title": "** A PLAYER HAS VOTED 📝 **",
                "description": (
                    "\n\n**↓ Vote Details ↓**\n\n"
                    ""
                    f"VOTE QUESTION: {find['Question']}\n"
                    f"VOTING FOR: {find['VoteOptions'][OptionIndex]}\n"
                    f"PREDICTION: {str(IsPrediction)}\n"
                    f"PollId: {str(PollId)}\n"
                    "\n\n"
                    "**↓ Player Details ↓**\n\n"
                    f"USER ID: {str(PlayFabId)}\n"
                    f"OCULUS ID: {str(OculusId)}\n"
                    f"PLATFORM: {str(UserPlatform)}\n"
                    f"PlayFabTicket: {str(PlayFabTicket)}\n"
                    f"NONCE: {str(UserNonce)}\n"
                    f"APPVERSION: {str(AppVersion)}\n"
                    f"Finally, Game Is {str(setttings.TitleId)}"
                ),
                "color": 63488
            }
        ]
    }

    requests.post(url=VOTING_WEBHOOK, json=embed)

    return jsonify({"Message": "Yay Votes Are Fixed, Very Cool"}), 200

nonces = {}

def discord_log(message, level="INFO"):
    payload = {
        "content": message,
        "embeds": [{"title": level, "description": message, "color": 3066993}]
    }
    try:
        print(f"[DISCORD LOG] Sending message: {message}")
        requests.post(DISCORD_WEBHOOK, json=payload)
    except Exception as e:
        print(f"[DISCORD LOG ERROR] {e}")
        
def generate_nonce():
    nonce = uuid.uuid4().hex
    nonces[nonce] = time.time()
    print(f"[NONCE GENERATED] {nonce}")
    return nonce

def is_nonce_valid(nonce):
    valid = nonce in nonces and time.time() - nonces[nonce] < 300  
    print(f"[NONCE VALIDATION] Nonce: {nonce}, Valid: {valid}")
    if valid:
        del nonces[nonce]  
    return valid
    
@app.route('/api/GenerateNonce', methods=['GET'])
def get_nonce():
    print("[REQUEST] /api/GenerateNonce")
    return jsonify({"nonce": generate_nonce()}), 200

def auth_headers():
    if not SECRET_KEY:
        raise ValueError("PlayFab Secret Key is not set in the environment variables")

    return {
        "Content-Type": "application/json",
        "X-Request-ID": hashlib.sha256(str(time.time()).encode('utf-8')).hexdigest(),
        "X-Authorization": SECRET_KEY 
    }

@app.route('/api/PlayFabAuthentication', methods=['POST'])
def playfab_auth():
    data = request.get_json()

    custom_id = data.get("CustomId")
    nonce = data.get("Nonce")
    oculus_token = data.get("OculusAccessToken")
    platform = data.get("Platform")

    if not all([custom_id, nonce, oculus_token, platform]):
        discord_log(f"Missing parameters for CustomId: {custom_id}", "ERROR")
        return jsonify({"error": "Missing parameters"}), 400

    if not is_nonce_valid(nonce):
        discord_log(f"Invalid nonce for CustomId: {custom_id}", "ERROR")
        return jsonify({"error": "Invalid nonce"}), 403

    if platform.lower() != "quest":
        discord_log(f"Platform not allowed for CustomId: {custom_id}", "ERROR")
        return jsonify({"error": "Platform not allowed"}), 403

    try:
        oculus_verify = requests.get(f"https://graph.oculus.com/me?access_token={oculus_token}")
        oculus_verify.raise_for_status()
    except requests.exceptions.RequestException as e:
        discord_log(f"Oculus token verification failed for CustomId: {custom_id}. Error: {e}", "ERROR")
        return jsonify({"error": "Oculus token verification failed"}), 403

    user_data = oculus_verify.json()
    org_scoped_id = user_data.get("id")

    try:
        login_response = requests.post(
            f"https://{TITLE_ID}.playfabapi.com/Server/LoginWithServerCustomId",
            json={"ServerCustomId": custom_id, "CreateAccount": True},
            headers=auth_headers()
        )
        login_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        discord_log(f"PlayFab login failed for CustomId: {custom_id}. Error: {e}", "ERROR")
        return jsonify({"error": "PlayFab login failed"}), 403

    login_data = login_response.json().get("data")
    session_ticket = login_data["SessionTicket"]
    entity_token = login_data["EntityToken"]["EntityToken"]

    try:
        requests.post(
            f"https://{TITLE_ID}.playfabapi.com/Client/LinkCustomID",
            json={"CustomId": org_scoped_id, "ForceLink": True},
            headers={"content-type": "application/json", "x-authorization": session_ticket}
        )
    except requests.exceptions.RequestException as e:
        discord_log(f"Failed to link OrgScopedId for CustomId: {custom_id}. Error: {e}", "ERROR")

    discord_log(f"Successful login for CustomId: {custom_id} with OrgScopedId: {org_scoped_id}", "INFO")

    return jsonify({
        "PlayFabId": login_data["PlayFabId"],
        "SessionTicket": session_ticket[:32] + "...",  
        "EntityToken": entity_token,
        "NonceUsed": nonce,
        "OrgScopedId": org_scoped_id
    }), 200

@app.route('/api/v3/Photon', methods=['POST'])
def api_authentication():
    print("[REQUEST] /api/Authentication")
    rjson = request.get_json()

    ticket = rjson.get("Ticket")
    nonce = rjson.get("Nonce")
    title = rjson.get("AppId")
    platform = rjson.get("Platform")
    org_scoped_id = rjson.get("OrgScopedId")
    custom_id = rjson.get("CustomId")
    app_version = rjson.get("AppVersion", "Unknown")

    if title != TITLE_ID:
        print(f"[ERROR] Invalid App ID: {title}")
        return jsonify({'status': 'error', 'message': 'Invalid App ID'}), 403
    if platform != 'Android':
        print(f"[ERROR] Invalid platform: {platform}")
        return jsonify({'status': 'error', 'message': 'Invalid platform'}), 403
    if nonce is None or not is_nonce_valid(nonce):
        print(f"[ERROR] Invalid nonce: {nonce}")
        return jsonify({'status': 'error', 'message': 'Invalid nonce'}), 403
    if not custom_id or not custom_id.startswith(("OC", "PI")):
        print(f"[ERROR] Invalid Custom ID: {custom_id}")
        return jsonify({'status': 'error', 'message': 'Invalid Custom ID'}), 403

    try:
        session_validation_response = requests.post(
            url=f"https://{TITLE_ID}.playfabapi.com/Server/ValidateSessionTicket",
            json={"SessionTicket": ticket},
            headers=auth_headers()
        )
        session_validation_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Session ticket validation failed: {e}")
        return jsonify({'status': 'error', 'message': 'Invalid session ticket'}), 403

    try:
        result = session_validation_response.json()
        playfab_id = result.get("data", {}).get("UserId", "Unknown")
    except Exception as e:
        print(f"[ERROR] Failed to parse session validation response: {e}")
        playfab_id = "Unknown"

    photon_payload = {
        "content": f"🔗 **Photon Session Authenticated :D**",
        "embeds": [{
            "title": "Auth Event",
            "color": 0x00FF99,
            "fields": [
                {"name": "UserId", "value": custom_id, "inline": True},
                {"name": "AppVersion", "value": app_version, "inline": True},
                {"name": "OrgScopedId", "value": org_scoped_id or "N/A", "inline": False},
                {"name": "PlayFabId", "value": playfab_id, "inline": True},
                {"name": "SessionTicket", "value": ticket[:32] + "...", "inline": False}
            ],
            "footer": {"text": "Photon Auth Webhook"}
        }],
        "username": "Photon AuthBot",
        "avatar_url": ""
    }

    try:
        print("[INFO] Sending Photon Auth webhook...")
        requests.post(PHOTON_WEBHOOK_URL, json=photon_payload)
    except Exception as e:
        print(f"[PHOTON WEBHOOK ERROR] {e}")

    print("[SUCCESS] Session validated")
    return jsonify({'status': 'success', 'message': 'Session validated'}), 200

@app.route("/api/td", methods=["POST", "GET"])
def titledata():
    req = requests.post(
        url=f"https://{TITLE_ID}.playfabapi.com/Server/GetTitleData",
        headers=auth_headers()
    )

    if req.status_code == 200:
        return jsonify(req.json().get("data").get("Data"))
    else:
        return jsonify({})

@app.route("/api/CachePlayFabId", methods=["POST"])
def cacheplatfabid():
    print("Received request to cache PlayFab ID")

    if request.content_type != 'application/json':
        print("Unsupported Media Type")
        return jsonify({"Message": "Unsupported Media Type"}), 415

    rjson = request.get_json()
    print(f"Request JSON: {rjson}")

    if not rjson or "PlayFabId" not in rjson:
        print("Missing PlayFabId parameter")
        return jsonify({"Message": "Missing PlayFabId parameter"}), 400

    playfabCache[rjson["PlayFabId"]] = rjson
    print(f"Cached PlayFab ID: {rjson['PlayFabId']}")
    return jsonify({"Message": "Success"})
    
    
@app.route('/api/CheckForBadName', methods=['POST'])
def handle_request():
    try:
        data = request.get_json()

        if 'FunctionArgument' not in data or 'name' not in data[
                'FunctionArgument'] or 'forRoom' not in data[
                    'FunctionArgument']:
            print("Invalid input format")
            raise ValueError("Invalid input format")

        function_argument = data['FunctionArgument']

        name = function_argument['name']
        for_room = function_argument['forRoom']

        name_saves[name] = for_room

        response_data = {'name': name, 'forRoom': for_room}

        print(f"for name {name} for a room is: {for_room}")

        return jsonify(response_data)

    except Exception as e:
        app.logger.error(f"Error handling request: {str(e)}")
        return jsonify({'error': str(e)}), 400

if __name__ == "__main__":
    app.run(debug=True, port=8080)
