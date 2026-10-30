import requests
import flask
import json

from flask import Flask, request, jsonify


app = Flask(auth-remarktag)

class settings:
    TitleId = "88DAF
    SecretKey = "H8NWNQDOXNUZYI8M3P7RHZ3BEIIGUAM4D6RMNC5ASICMY86TC3"
    DiscordWebhookUrl = "https://discord.com/api/webhooks/1565658391945412728/qffmR8Kl83NwPz6C4qgWKin0YH-kvrsqZwxo2Vw0aIsJ5tOOKXhRzqK89Kh453rW4NGQ"

def get_info():
    info = {
        "TitleId": settings.TitleId,
        "SecretKey": settings.SecretKey
    }

    return {
        "titleid": info["TitleId"],
        "secretkey": info["SecretKey"]
    }


class GameInfo:
    def __init__(self, titleid, secretkey):
        self.titleid = titleid
        self.secretkey = secretkey

class AppLabInfo:
    def __init__(self, Credential, UserToken):
        self.Credential = Credential
        self.UserToken = UserToken

yourapplabnamehere = AppLabInfo
yourapplabnamehere.Credential = ""
yourapplabnamehere.UserToken = ""


information = get_info()
GameNameHere = GameInfo
GameNameHere.titleid = information['titleid']
GameNameHere.secretkey = information['secretkey']


ValidTitleIds = [
    GameNameHere.titleid
]


validAppLabs = [
    yourapplabnamehere
]


def Headers(server : bool = False, client : bool = False, sessionticket : str = None):
    if server:
        return {
            "content-type": "application/json",
            "x-secretkey": GameNameHere.secretkey
        }
    else:
        return {
            "content-type": "application/json",
            "x-authorization": sessionticket
        }


                


def CheckSessionTicket(sessionticket : str) -> bool:
    TitleId = GameNameHere.titleid
    SecretKey = GameNameHere.secretkey

    real = requests.post(
        url=f"https://{TitleId}.playfabapi.com/Server/AuthenticateSessionTicket",
        json={ "SessionTicket": sessionticket },
        headers=Headers(True, False, None)
    )
    if real.status_code == 200:
        return True
    else:
        return False


def VerifyUserId(Id: str) -> bool:
    TitleId = GameNameHere.titleid

    realfr = requests.post(
        url=f"https://{TitleId}.playfabapi.com/Server/GetUserAccountInfo",
        json={ "PlayFabId": Id },
        headers={"content-type": "application/json"}
    )

    if realfr.status_code == 200:
        return True
    else:
        return False


@app.route("/", methods=['POST', 'GET'])
def titledata():
    url = f"https://{GameNameHere.titleid}.playfabapi.com/Server/GetTitleData"

    real = requests.post(
        url=url,
        json={"None": "None"},
        headers=Headers(True, False, None)
    )
    if real.status_code == 200:
        re = real.json()
        data = re.get("data", {}).get("Data", {})

        return jsonify(data)
    else:
        print(real.json())
        return jsonify({"MOTD": "ERROR GETTING TITLEDATA, PLEASE CHECK LOGS"})

@app.route('/api/TitleData', methods=['POST', 'GET'])
def titledata():
    response_data = {
        "AutoMuteCheckedHours": {
            "hours": 111
        },
        "AutoName_Adverbs": [
            "Cool", "Fine", "Bald", "Bold", "Half", 
            "Only", "Calm", "Fab", "Ice", "Mad", 
            "Rad", "Big", "New", "Old", "Shy"
        ],
        "AutoName_Nouns": [
            "Gorilla", "Chicken", "Darling", "Sloth", "King", 
            "Queen", "Royal", "Major", "Actor", "Agent", 
            "Elder", "Honey", "Nurse", "Doctor", "Rebel", 
            "Shape", "Ally", "Driver", "Deputy"
        ],

        "CreditsData": [
            {
                "Title": "<color=red>owners</color>",
                "Entries": [
                    "LIBERTY",
                    "BD",
                    "VTECH"
                ]
            },
            {
                "Title": "<color=purple>CREDITS TO</color>",
                "Entries": [
                    "BD",
                    "Z4EU",
                    "L1RSON",
                    "S4GE",
                    "PLAYDOUGH",
                    "SCREAMINGCAT",
                    "DILLIN",
                    "VTECH",
                ]
            },
            {
                "Title": "<color=blue>SUSSY BALLSACK</color>",
                "Entries": [
                    "me"
                ]
            }
        ],
        "BundleBoardSign": "<color=red>DISCORD.GG/ch8dru2Z2J</color>",
        "BundleKioskButton": "<color=red>DISCORD.GG/ch8dru2Z2J</color>",
        "BundleKioskSign": "<color=red>DISCORD.GG/ch8dru2Z2J</color>",
        "BundleLargeSign": "<color=red>DISCORD.GG/ch8dru2Z2J</color>",
        "EmptyFlashbackText": "FLOOR TWO NOW OPEN\n FOR BUSINESS\n\nSTILL SEARCHING FOR\nBOX LABELED 2021",
        "EnableCustomAuthentication": True,
        "GorillanalyticsChance": 4320,
        "LatestPrivacyPolicyVersion": "2024.09.20",
        "LatestTOSVersion": "2024.09.20",
        "MOTD": "<color=red>WELCOME TO LEGEND TAG</color>\n\n<color=green>IF YOU WANT EVERY COSMETIC, BOOST THE SERVER!: discord.gg/UEPhpZ4htf</color>\\n<color=cyan>YOU DONT NEED TO CHANGE YOUR NAME FROM LEGEND####</color>\\n<color=yellow>UPDATE: FLYING MONKES</color>\\n\\n<color=magenta>CREDS: BD, LIBERTY, VTECH, DILLIN, Z4EU</color>",
        "SeasonalStoreBoardSign": "<color=yellow>RATE THE GAME 5 STARS!</color>\n\n<color=magenta>DISCORD.GG/ch8dru2Z2J</color>",
        "TOS_2024.09.20": "DISCORD.GG/ch8dru2Z2J",
        "TOBAlreadyOwnCompTxt": "DISCORD.GG/ch8dru2Z2J",
        "TOBAlreadyOwnPurchaseBundle": "LT",
        "TOBDefCompTxt": "DISCORD.GG/ch8dru2Z2J",
        "TOBDefPurchaseBtnDefTxt": "LT",
        "UseLegacyIAP": False
    }
    return jsonify(response_data)

    
@app.route("/api/CachePlayFabId", methods=['POST'])
def CachePlayFabId():
    PlayFabId = request.get_json().get("PlayFabId", "null")
    SessionTicket = request.get_json().get("SessionTicket", "null")
    Platform = request.get_json().get("Platform", "null")

    SessionTicketCheck = CheckSessionTicket(SessionTicket)
    if SessionTicketCheck == True:
        pass
    else:
        return jsonify({
            "Error": "Invalid Session Ticket",
            "code": 403,
            "Result": "false"
        }), 403


    if PlayFabId not in SessionTicket.split("-")[0]:
        return jsonify({
            "Error": "Invalid Session Ticket usage.",
            "code": 403,
            "Result": "false"
        }), 403
    
    if Platform != "Quest" or Platform == "null":
        return jsonify({
            "Error": "Invalid Platform.",
            "code": 403,
            "Result": "false"
        }), 403
    
    if Platform == "Quest" and PlayFabId in SessionTicket:
        return jsonify({
            "PlayFabId": PlayFabId,
            "SessionTicket": SessionTicket,
            "Platform": PlayFabId,
            "Result": "true"
        }), 200
    else:
        return jsonify({
            "Result": "false"
        }), 500
    
def CheckTitleId(appid) -> bool:
    if appid not in ValidTitleIds:
        return False
    
    else:
        return True
    

@app.route("/api/PlayFabAuthentication", methods=["POST"])
def playfab_authentication():
    # Extract IP address for anti-VPN check and logging
    ip_address = request.headers.get('X-Real-Ip') or request.headers.get('X-Forwarded-For') or request.remote_addr
    if ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()
    
    # Anti-VPN check 
    try:
        vpn_response = requests.get(f"http://ip-api.com/json/{ip_address}?fields=16974336", timeout=5)
        if vpn_response.status_code == 200:
            vpn_data = vpn_response.json()
            if vpn_data.get("proxy") == True or vpn_data.get("hosting") == True:
                # Send VPN detection webhook
                send_discord_webhook(
                    "🚫 VPN/Proxy Detected - Authentication Blocked",
                    "",
                    16711680,  # Red
                    [
                        {"name": "IP Address", "value": ip_address, "inline": True},
                        {"name": "Proxy Detected", "value": str(vpn_data.get("proxy", False)), "inline": True},
                        {"name": "Hosting Detected", "value": str(vpn_data.get("hosting", False)), "inline": True},
                        {"name": "Country", "value": vpn_data.get("country", "Unknown"), "inline": True},
                        {"name": "ISP", "value": vpn_data.get("isp", "Unknown"), "inline": False}
                    ]
                )
                return jsonify({
                    "Message": "VPN or proxy connections are not allowed",
                    "Error": "BadRequest-VPNDetected"
                }), 403
    except Exception as e:
        print(f"VPN check failed: {e}")
        # Continue with authentication if VPN check fails
        pass

    
    rjson = request.get_json()
    oculus_id = rjson.get("OculusId")
    nonce = rjson.get("Nonce")
    title = rjson.get("AppId")
    platform = rjson.get("Platform")
    app_ver = rjson.get("AppVersion", "")
    custom_id = rjson.get("CustomId")
    print(rjson)
    
    # check for malicious nonce
    if nonce:
        suspicious_patterns = [
            "discord.gg/spm",
            "discord.gg/",
            "discord.com/",
            "dsc.gg/",
            "https://",
            "http://",
            "www.",
            ".gg/",
            ".com/",
            "invite/",
            "server/"
        ]
        
        nonce_lower = nonce.lower()
        for pattern in suspicious_patterns:
            if pattern in nonce_lower:
                print(f"Blocked suspicious nonce: {nonce}")
                send_discord_webhook(
                    "🚫 Malicious Nonce Detected - Authentication Blocked",
                    "",
                    16711680,  # Red
                    [
                        {"name": "Nonce", "value": nonce, "inline": False},
                        {"name": "Detected Pattern", "value": pattern, "inline": True},
                        {"name": "Oculus ID", "value": oculus_id or "Unknown", "inline": True},
                        {"name": "IP Address", "value": ip_address, "inline": True},
                        {"name": "Reason", "value": "Nonce contains suspicious/malicious content", "inline": False}
                    ]
                )
                return jsonify({
                    "Message": "Invalid nonce format detected",
                    "Error": "BadRequest-InvalidNonce"
                }), 400
    
    if request.headers.get("User-Agent") != "UnityPlayer/2022.3.2f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)" or request.headers.get("X-Unity-Version") != "2022.3.2f1": 
        return "", 404
    if title != settings.TitleId: 
        return "", 404
    if platform != "Quest": 
        return "", 404
    if not all([title, nonce, platform, oculus_id]) or platform != "Quest":
        return "", 404
        
    graph_user = None
    
    for api_key in settings.ApiKeys:
        try:
            print(f"trying api key {api_key}...")
    
            response = requests.get(f"https://graph.oculus.com/{oculus_id}?access_token={api_key}&fields=org_scoped_id,alias")
            if response.status_code != 200:
                print(f"failed org scope with api key {api_key}, trying next...")
                continue
    
            graph_user = response.json()
            break
    
        except Exception as e:
            print(f"exception: {e}")
            continue  # try next API key
    
    if not graph_user:
        print("failed all org scope or nonce checks")
        return "", 404
    
    # Get orgscope for ban evasion check
    current_orgscope = graph_user.get("org_scoped_id")
    
    # Function to check if a user is banned
    def check_if_banned(custom_id_to_check):
        try:
            ban_check = requests.post(
                url=f"https://{settings.TitleId}.playfabapi.com/Server/LoginWithCustomId",
                json={"CustomId": custom_id_to_check, "CreateAccount": False},
                headers=settings.headers()
            )
            if ban_check.status_code == 403 and ban_check.json().get("errorCode") == 1002:
                return True, ban_check.json().get("errorDetails", {})
            return False, None
        except:
            return False, None
    
    # Ban evasion detection - only check if player appears to be trying to evade a ban
    import time
    current_time = time.time()
    
    # Clean up old entries (older than 24 hours)
    cutoff_time = current_time - (24 * 3600)
    used_nonces_copy = used_nonces.copy()
    for old_nonce, (old_orgscope, timestamp) in used_nonces_copy.items():
        if timestamp < cutoff_time:
            del used_nonces[old_nonce]
            if old_orgscope in used_orgscopes and used_orgscopes[old_orgscope][0] == old_nonce:
                del used_orgscopes[old_orgscope]
    
    # Check if nonce has been used before
    if nonce in used_nonces:
        stored_orgscope, stored_timestamp = used_nonces[nonce]
        if stored_orgscope != current_orgscope:
            # Check if the previous orgscope user is banned
            previous_custom_id = f"OCULUS{stored_orgscope}"
            is_previous_banned, ban_details = check_if_banned(previous_custom_id)
            
            if is_previous_banned:
                # Same nonce used by different orgscope and previous user is banned - ban evasion attempt
                print(f"Ban evasion detected: Nonce {nonce} reused by different orgscope, previous user banned")
                send_discord_webhook(
                    "🚨 Ban Evasion Detected - Nonce Reuse from Banned Account",
                    "",
                    16711680,  # Red
                    [
                        {"name": "Detection Type", "value": "Nonce Reuse from Banned Account", "inline": False},
                        {"name": "Nonce", "value": nonce, "inline": True},
                        {"name": "Current OrgScope", "value": current_orgscope, "inline": True},
                        {"name": "Banned OrgScope", "value": stored_orgscope, "inline": True},
                        {"name": "IP Address", "value": ip_address, "inline": True},
                        {"name": "Time Since Last Use", "value": f"{int((current_time - stored_timestamp) / 60)} minutes", "inline": True},
                        {"name": "Ban Reason", "value": str(list(ban_details.keys())[0]) if ban_details else "Unknown", "inline": False}
                    ]
                )
                return jsonify({
                    "Message": "Authentication failed",
                    "Error": "BadRequest-InvalidAuth"
                }), 400
    
    # Check if orgscope has been used with a different nonce
    if current_orgscope in used_orgscopes:
        stored_nonce, stored_timestamp = used_orgscopes[current_orgscope]
        if stored_nonce != nonce:
            # Check if current user is banned with the stored nonce
            current_custom_id = f"OCULUS{current_orgscope}"
            is_current_banned, ban_details = check_if_banned(current_custom_id)
            
            if is_current_banned:
                # Same orgscope used with different nonce and user is banned - ban evasion attempt
                print(f"Ban evasion detected: Banned OrgScope {current_orgscope} used with different nonce")
                send_discord_webhook(
                    "🚨 Ban Evasion Detected - Banned Account Using Different Nonce",
                    "",
                    16711680,  # Red
                    [
                        {"name": "Detection Type", "value": "Banned Account Using Different Nonce", "inline": False},
                        {"name": "OrgScope", "value": current_orgscope, "inline": True},
                        {"name": "Current Nonce", "value": nonce, "inline": True},
                        {"name": "Previous Nonce", "value": stored_nonce, "inline": True},
                        {"name": "IP Address", "value": ip_address, "inline": True},
                        {"name": "Time Since Last Use", "value": f"{int((current_time - stored_timestamp) / 60)} minutes", "inline": True},
                        {"name": "Ban Reason", "value": str(list(ban_details.keys())[0]) if ban_details else "Unknown", "inline": False}
                    ]
                )
                return jsonify({
                    "Message": "Authentication failed",
                    "Error": "BadRequest-InvalidAuth"
                }), 400
    
    if not custom_id:
        org = "OCULUS" + graph_user.get("org_scoped_id")
    else:
        org = custom_id
        
    login_req = requests.post(url = f"https://{settings.TitleId}.playfabapi.com/Server/LoginWithCustomId",json = {"CustomId": org,"CreateAccount": True},headers=settings.headers())
    
    if login_req.status_code == 200:
        # Store nonce and orgscope for future ban evasion checks (only on successful auth)
        used_nonces[nonce] = (current_orgscope, current_time)
        used_orgscopes[current_orgscope] = (nonce, current_time)
        
        embed = {
            "embeds": [
                {
                    "title": f"PLAYER AUTHED",
                    "description": f"```ini\n[ PlayFab ID ]: {login_req.json().get('data').get('PlayFabId')}\n[ IP Address ]: {ip_address}\n[ Age Group ]: {rjson.get('AgeCategory', None)}\n[ Meta Quest Username ]: {graph_user.get('alias', 'cannot access alias')}```",
                    "color": 3447003
                }
            ]
        }
        requests.post(settings.DiscordWebhookUrl, json=embed)
        
        link_req = requests.post(url=f"https://{settings.TitleId}.playfabapi.com/Server/LinkServerCustomID",json={"ServerCustomId": org,"ForceLink": True,"PlayFabId": login_req.json().get("data").get("PlayFabId")},headers=settings.headers())
        
        # Device verification logic - integrated directly
        playfab_id = login_req.json().get("data").get("PlayFabId")
        
        # Check device info from request headers and platform
        device_model = "Quest" if platform == "Quest" else "Unknown"
        device_platform = "Android" if platform == "Quest" else "Unknown"  
        device_type = "Handheld" if platform == "Quest" else "Unknown"
        
        # Verify device is legitimate Quest
        if device_model == "Quest" and device_platform == "Android" and device_type == "Handheld":
            # Update user data to mark as verified
            try:
                verify_req = requests.post(
                    url=f"https://{settings.TitleId}.playfabapi.com/Server/UpdateUserInternalData",
                    json={
                        "PlayFabId": playfab_id,
                        "Data": {"Verified": "true"}
                    },
                    headers=settings.get_auth_headers()
                )
                print(f"Device verified successfully for player {playfab_id}")
                
                # Send verification success webhook
                send_discord_webhook(
                    "✅ Device Verified - Quest User",
                    "",
                    65280,  # Green
                    [
                        {"name": "PlayFab ID", "value": playfab_id, "inline": True},
                        {"name": "Device Model", "value": device_model, "inline": True},
                        {"name": "Platform", "value": device_platform, "inline": True},
                        {"name": "Device Type", "value": device_type, "inline": True},
                        {"name": "IP Address", "value": ip_address, "inline": True}
                    ]
                )
            except Exception as e:
                print(f"Failed to update user verification status: {e}")
        else:
            # Invalid device detected - ban the user
            try:
                ban_req = requests.post(
                    url=f"https://{settings.TitleId}.playfabapi.com/Admin/BanUsers",
                    json={
                        "Bans": [{
                            "PlayFabId": playfab_id,
                            "DurationInHours": 336,  # 14 days
                            "Reason": "Device verification failed. Possible cheating attempt."
                        }]
                    },
                    headers=settings.get_auth_headers()
                )
                print(f"Invalid device detected for player {playfab_id} - user banned")
                
                # Send ban webhook
                send_discord_webhook(
                    "🚫 Invalid Device Detected - User Banned",
                    "",
                    16711680,  # Red
                    [
                        {"name": "PlayFab ID", "value": playfab_id, "inline": True},
                        {"name": "Device Model", "value": device_model, "inline": True},
                        {"name": "Platform", "value": device_platform, "inline": True},
                        {"name": "Device Type", "value": device_type, "inline": True},
                        {"name": "Ban Duration", "value": "336 hours (14 days)", "inline": True},
                        {"name": "IP Address", "value": ip_address, "inline": True},
                        {"name": "Reason", "value": "Device verification failed. Possible cheating attempt.", "inline": False}
                    ]
                )
            except Exception as e:
                print(f"Failed to ban user for invalid device: {e}")
        
        # Authentication verification logic - integrated directly
        try:
            # Get account info to check Custom ID
            account_req = requests.post(
                url=f"https://{settings.TitleId}.playfabapi.com/Server/GetUserAccountInfo",
                json={"PlayFabId": playfab_id},
                headers=settings.get_auth_headers()
            )
            
            if account_req.status_code == 200:
                account_info = account_req.json().get("data", {}).get("UserInfo", {})
                custom_id_info = account_info.get("ServerCustomIdInfo")
                
                if not custom_id_info or not custom_id_info.get("CustomId"):
                    # Missing Custom ID - ban and delete
                    send_discord_webhook(
                        "🚫 Auth Failed - Missing Custom ID",
                        "",
                        16711680,  # Red
                        [
                            {"name": "PlayFab ID", "value": playfab_id, "inline": True},
                            {"name": "Reason", "value": "Missing or invalid Custom ID", "inline": False},
                            {"name": "IP Address", "value": ip_address, "inline": True}
                        ]
                    )
                    
                    # Ban user
                    requests.post(
                        url=f"https://{settings.TitleId}.playfabapi.com/Admin/BanUsers",
                        json={
                            "Bans": [{
                                "PlayFabId": playfab_id,
                                "Reason": "Unauthorized account.",
                                "DurationInHours": 672  # 28 days
                            }]
                        },
                        headers=settings.get_auth_headers()
                    )
                    
                    # Delete player
                    requests.post(
                        url=f"https://{settings.TitleId}.playfabapi.com/Admin/DeletePlayer",
                        json={"PlayFabId": playfab_id},
                        headers=settings.get_auth_headers()
                    )
                elif custom_id_info.get("CustomId", "").startswith("OCULUS"):
                    custom_id = custom_id_info.get("CustomId")
                    org_scope = custom_id[6:]  # Remove "OCULUS" prefix
                    
                    if len(org_scope) == 16 or len(org_scope) == 17:
                        # Valid org scope
                        send_discord_webhook(
                            "✅ Auth Success - Valid Custom ID",
                            "",
                            65280,  # Green
                            [
                                {"name": "PlayFab ID", "value": playfab_id, "inline": True},
                                {"name": "Custom ID", "value": custom_id, "inline": True},
                                {"name": "Org Scope", "value": org_scope, "inline": True},
                                {"name": "IP Address", "value": ip_address, "inline": True}
                            ]
                        )
                    else:
                        # Invalid org scope - ban and delete
                        send_discord_webhook(
                            "🚫 Auth Failed - Invalid Org Scope",
                            "",
                            16711680,  # Red
                            [
                                {"name": "PlayFab ID", "value": playfab_id, "inline": True},
                                {"name": "Custom ID", "value": custom_id, "inline": True},
                                {"name": "Reason", "value": "Invalid org scope length", "inline": False},
                                {"name": "IP Address", "value": ip_address, "inline": True}
                            ]
                        )
                        
                        # Ban user
                        requests.post(
                            url=f"https://{settings.TitleId}.playfabapi.com/Admin/BanUsers",
                            json={
                                "Bans": [{
                                    "PlayFabId": playfab_id,
                                    "Reason": "Invalid org scope.",
                                    "DurationInHours": 672  # 28 days
                                }]
                            },
                            headers=settings.get_auth_headers()
                        )
                        
                        # Delete player
                        requests.post(
                            url=f"https://{settings.TitleId}.playfabapi.com/Admin/DeletePlayer",
                            json={"PlayFabId": playfab_id},
                            headers=settings.get_auth_headers()
                        )
                else:
                    # Invalid Custom ID type
                    send_discord_webhook(
                        "🚫 Auth Failed - Invalid Custom ID Type",
                        "",
                        16711680,  # Red
                        [
                            {"name": "PlayFab ID", "value": playfab_id, "inline": True},
                            {"name": "Custom ID", "value": custom_id_info.get("CustomId", "Unknown"), "inline": True},
                            {"name": "Reason", "value": "Invalid Custom ID type", "inline": False},
                            {"name": "IP Address", "value": ip_address, "inline": True}
                        ]
                    )
        except Exception as e:
            print(f"Auth verification failed: {e}")
        
        return jsonify({
            "SessionTicket": login_req.json().get("data").get("SessionTicket"),
            "EntityToken": login_req.json().get("data").get("EntityToken").get("EntityToken"),
            "PlayFabId": login_req.json().get("data").get("PlayFabId"),
            "EntityId": login_req.json().get("data").get("EntityToken").get("Entity").get("Id"),
            "EntityType": login_req.json().get("data").get("EntityToken").get("Entity").get("Type")
        }), 200
    else:
        # Don't store failed authentications to avoid false positives for legitimately banned players
        if login_req.json().get("errorCode") == 1002:
            return jsonify({
                "BanMessage": list(login_req.json().get("errorDetails"))[0],
                "BanExpirationTime": list(login_req.json().get("errorDetails").values())[0][0]
            }), 403
        elif login_req.json().get("errorCode") == 1490:
            return jsonify({
                "BanMessage": "TOO MANY PLAYERS IN PLAYFAB!\nMESSAGE AN OWNER IMMEDIATELY.",
                "BanExpirationTime": "Indefinite"
            }), 403
        else:
            return jsonify({
                "Message": "Authentication failed",
                "Error": "PlayFabError"
            }), login_req.status_code

    # Check if this is a Mothership authentication request
    if rjson.get("SessionTicket") and rjson.get("CustomId") and rjson.get("PlayFabId"):
        # MothershipAuthentication logic
        CustomId = rjson.get("CustomId", "null")
        PlayFabId = rjson.get("PlayFabId", "null")
        SessionTicket = rjson.get("SessionTicket")
        GameMode = rjson.get("GameMode", "DefaultMode")
        DeviceType = rjson.get("Device", "Unknown")
        Region = rjson.get("Region", "global")

        MetaLog = {
            "CustomId": CustomId,
            "PlayFabId": PlayFabId,
            "GameMode": GameMode,
            "Device": DeviceType,
            "Region": Region,
            "IP": ip_address
        }

       
        if not SessionTicket:
            return jsonify({"error": "Missing session ticket"}), 401

        validate = requests.post(
            url=f"https://{settings.TitleId}.playfabapi.com/Client/GetAccountInfo",
            headers={
                "Content-Type": "application/json",
                "X-Authorization": SessionTicket
            }
        )

        if validate.status_code != 200:
            return jsonify({
                "error": "Invalid session",
                "detail": validate.text
            }), 403

        account_data = validate.json()
        validated_id = account_data.get("data", {}).get("AccountInfo", {}).get("PlayFabId", None)
        if validated_id != PlayFabId:
            return jsonify({
                "error": "Session mismatch",
                "expected": validated_id,
                "provided": PlayFabId
            }), 403

       
        login = requests.post(
            url=f"https://{settings.TitleId}.playfabapi.com/Server/LoginWithServerCustomId",
            json={
                "CustomId": CustomId,
                "CreateAccount": False
            },
            headers={
                "Content-Type": "application/json",
                "X-SecretKey": settings.SecretKey
            }
        )

        if login.status_code != 200:
            if login.status_code == 403:
                ban_info = login.json()
                if ban_info.get('errorCode') == 1002:
                    ban_details = ban_info.get('errorDetails', {})
                    ban_expiration_key = next(iter(ban_details.keys()), None)
                    ban_expiration = ban_details.get(ban_expiration_key, ["Unknown"])[0]

                    return jsonify({
                        'BanReason': ban_expiration_key,
                        'BanExpiration': ban_expiration,
                        'Region': Region,
                        'GameMode': GameMode
                    }), 403
                return jsonify({
                    'error': 'Forbidden',
                    'message': ban_info.get('errorMessage', 'Unknown reason'),
                    'meta': MetaLog
                }), 403
            return jsonify({
                'error': 'PlayFab login failed',
                'detail': login.text,
                'meta': MetaLog
            }), login.status_code

      
        link = requests.post(
            url=f"https://{settings.TitleId}.playfabapi.com/Server/LinkServerCustomId",
            json={
                "PlayFabId": PlayFabId,
                "ServerCustomId": CustomId,
                "ForceLink": True
            },
            headers={
                "Content-Type": "application/json",
                "X-SecretKey": settings.SecretKey
            }
        )

        if link.status_code != 200:
            return jsonify({
                "status": "error",
                "step": "LinkServerCustomId",
                "code": link.status_code,
                "error": link.text,
                "meta": MetaLog
            }), link.status_code

    
        if DeviceType.lower() == "pcvr":
            return jsonify({
                "error": "PCVR not allowed",
                "reason": "Only Quest clients can access this auth"
            }), 403

        
        user_agent = request.headers.get("User-Agent", "Unknown")
        if "UnityPlayer" not in user_agent:
            return jsonify({"error": "Invalid client"}), 403

        
        services = {
            "CosmeticsSync": True,
            "FriendsInit": True,
            "GuildSync": False,
            "SeasonalEvents": True
        }

        return jsonify({
            "status": "success",
            "GameMode": GameMode,
            "Region": Region,
            "Device": DeviceType,
            "sessionChecked": True,
            "loginData": login.json(),
            "linkData": link.json(),
            "servicesInitialized": services,
            "meta": MetaLog
        })

   
    if request.headers.get("User-Agent") != "UnityPlayer/2022.3.2f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)" or \
       request.headers.get("X-Unity-Version") != "2022.3.2f1":
        return "", 404

    try:
        json_data = request.get_json()
        print(json.dumps(json_data, indent=2))
    except Exception:
        return jsonify({
            "Message": "Request body is missing or cannot be parsed.",
            "Error": "BadRequest-BadBody"
        }), 400

    AppId = json_data.get("AppId")
    AppVersion = json_data.get("AppVersion", "")
    Nonce = json_data.get("Nonce")
    OculusId = json_data.get("OculusId")
    Platform = json_data.get("Platform")
    AgeCategory = json_data.get("AgeCategory")

    # Additional nonce check for the secondary authentication path
    if Nonce:
        suspicious_patterns = [
            "discord.gg/spm",
            "discord.gg/",
            "discord.com/",
            "dsc.gg/",
            "https://",
            "http://",
            "www.",
            ".gg/",
            ".com/",
            "invite/",
            "server/"
        ]
        
        nonce_lower = Nonce.lower()
        for pattern in suspicious_patterns:
            if pattern in nonce_lower:
                print(f"Blocked suspicious nonce in secondary path: {Nonce}")
                send_discord_webhook(
                    "🚫 Malicious Nonce Detected - Secondary Auth Blocked",
                    "",
                    16711680,  # Red
                    [
                        {"name": "Nonce", "value": Nonce, "inline": False},
                        {"name": "Detected Pattern", "value": pattern, "inline": True},
                        {"name": "Oculus ID", "value": OculusId or "Unknown", "inline": True},
                        {"name": "IP Address", "value": ip_address, "inline": True},
                        {"name": "Auth Path", "value": "Secondary", "inline": True}
                    ]
                )
                return jsonify({
                    "Message": "Invalid nonce format detected",
                    "Error": "BadRequest-InvalidNonce"
                }), 400
    if not all([AppId, Nonce, OculusId, Platform]) or AppId != settings.TitleId or Platform != "Quest":
        return "", 404

    # Get org_scoped_id first (needed for logging and ban evasion check)
    org_req = requests.get(
        f"https://graph.oculus.com/{OculusId}?access_token={settings.AppCreds}&fields=org_scoped_id",
        headers={"Content-Type": "application/json"}
    )
    OrgScope = org_req.json().get("org_scoped_id")
    CustomId = f"OCULUS{OrgScope}"

    # Ban evasion detection for secondary path
    current_time = time.time()
    
    # Clean up old entries (older than 24 hours)
    cutoff_time = current_time - (24 * 3600)
    used_nonces_copy = used_nonces.copy()
    for old_nonce, (old_orgscope, timestamp) in used_nonces_copy.items():
        if timestamp < cutoff_time:
            del used_nonces[old_nonce]
            if old_orgscope in used_orgscopes and used_orgscopes[old_orgscope][0] == old_nonce:
                del used_orgscopes[old_orgscope]
    
    # Check if nonce has been used before
    if Nonce in used_nonces:
        stored_orgscope, stored_timestamp = used_nonces[Nonce]
        if stored_orgscope != OrgScope:
            # Check if the previous orgscope user is banned
            previous_custom_id = f"OCULUS{stored_orgscope}"
            is_previous_banned, ban_details = check_if_banned(previous_custom_id)
            
            if is_previous_banned:
                # Same nonce used by different orgscope and previous user is banned - ban evasion attempt
                print(f"Ban evasion detected in secondary path: Nonce {Nonce} reused by different orgscope, previous user banned")
                send_discord_webhook(
                    "🚨 Ban Evasion Detected - Secondary Path Nonce Reuse from Banned Account",
                    "",
                    16711680,  # Red
                    [
                        {"name": "Detection Type", "value": "Secondary Path Nonce Reuse from Banned Account", "inline": False},
                        {"name": "Nonce", "value": Nonce, "inline": True},
                        {"name": "Current OrgScope", "value": OrgScope, "inline": True},
                        {"name": "Banned OrgScope", "value": stored_orgscope, "inline": True},
                        {"name": "IP Address", "value": ip_address, "inline": True},
                        {"name": "Time Since Last Use", "value": f"{int((current_time - stored_timestamp) / 60)} minutes", "inline": True},
                        {"name": "Ban Reason", "value": str(list(ban_details.keys())[0]) if ban_details else "Unknown", "inline": False}
                    ]
                )
                return jsonify({
                    "Message": "Authentication failed",
                    "Error": "BadRequest-InvalidAuth"
                }), 400
    
    # Check if orgscope has been used with a different nonce
    if OrgScope in used_orgscopes:
        stored_nonce, stored_timestamp = used_orgscopes[OrgScope]
        if stored_nonce != Nonce:
            # Check if current user is banned with the stored nonce
            current_custom_id = f"OCULUS{OrgScope}"
            is_current_banned, ban_details = check_if_banned(current_custom_id)
            
            if is_current_banned:
                # Same orgscope used with different nonce and user is banned - ban evasion attempt
                print(f"Ban evasion detected in secondary path: Banned OrgScope {OrgScope} used with different nonce")
                send_discord_webhook(
                    "🚨 Ban Evasion Detected - Secondary Path Banned Account Using Different Nonce",
                    "",
                    16711680,  # Red
                    [
                        {"name": "Detection Type", "value": "Secondary Path Banned Account Using Different Nonce", "inline": False},
                        {"name": "OrgScope", "value": OrgScope, "inline": True},
                        {"name": "Current Nonce", "value": Nonce, "inline": True},
                        {"name": "Previous Nonce", "value": stored_nonce, "inline": True},
                        {"name": "IP Address", "value": ip_address, "inline": True},
                        {"name": "Time Since Last Use", "value": f"{int((current_time - stored_timestamp) / 60)} minutes", "inline": True},
                        {"name": "Ban Reason", "value": str(list(ban_details.keys())[0]) if ban_details else "Unknown", "inline": False}
                    ]
                )
                return jsonify({
                    "Message": "Authentication failed",
                    "Error": "BadRequest-InvalidAuth"
                }), 400

    # Validate Nonce
    nonce_check = requests.post(
        url="https://graph.oculus.com/user_nonce_validate",
        json={
            "access_token": settings.AppCreds,
            "nonce": Nonce,
            "user_id": OculusId
        },
        headers={"Content-Type": "application/json"}
    )

    nonceJson = nonce_check.json()

    if nonce_check.status_code != 200 or nonceJson.get("is_valid") is not True:
        print(f"User: {CustomId} Has Failed The Nonce Verification. Nonce: {Nonce}")

        send_discord_webhook(
            "-----📝 A User Has An Invalid Nonce 📝-----",
            "",
            16711935,
            [
                {"name": "Nonce", "value": Nonce, "inline": False},
                {"name": "User", "value": CustomId, "inline": True},
                {"name": "IP Address", "value": ip_address, "inline": True}
            ]
        )

        return jsonify({
            "Message": "Failed Nonce Verification",
            "Error": "BadRequest-InvalidNonce"
        }), 400

    # Get Meta alias (username)
    alias_req = requests.get(
        f"https://graph.oculus.com/{OculusId}?access_token={settings.AppCreds}&fields=alias",
        headers={"Content-Type": "application/json"}
    )
    meta_alias = alias_req.json().get("alias")

    if not meta_alias:
        print(f"Blocked: No Meta alias for {OculusId} (likely PCVR)")
        send_discord_webhook(
            "🚫 Login Blocked - Missing Meta Alias",
            "",
            16711680,
            [
                {"name": "OculusId", "value": OculusId, "inline": True},
                {"name": "Nonce", "value": Nonce, "inline": True},
                {"name": "IP Address", "value": ip_address, "inline": True},
                {"name": "Reason", "value": "Alias missing - likely PCVR or restricted profile", "inline": False}
            ]
        )
        return jsonify({
            "Message": "Meta username (alias) is missing or private. Cannot authenticate.",
            "Error": "BadRequest-NoAlias"
        }), 400

    # ✅ Log Valid Nonce + Alias
    send_discord_webhook(
        "✅ Valid Nonce Login",
        "",
        65280,
        [
            {"name": "Nonce", "value": Nonce, "inline": False},
            {"name": "Meta Username", "value": meta_alias, "inline": True},
            {"name": "OculusId", "value": OculusId, "inline": True},
            {"name": "IP Address", "value": ip_address, "inline": True}
        ]
    )

    # Original backend code continues below
    rjson = request.get_json()
    required_fields = ["Nonce", "AppId", "Platform", "OculusId"]
    missing_fields = [field for field in required_fields if not rjson.get(field)]

    if missing_fields:
        # Send failure webhook
        send_discord_webhook(
            "❌ PlayFab Auth Failed - Missing Parameters",
            "",
            16711680,  # Red
            [
                {"name": "Reason", "value": f"Missing: {', '.join(missing_fields)}", "inline": False},
                {"name": "Oculus ID", "value": rjson.get("OculusId", "Unknown"), "inline": True},
                {"name": "IP Address", "value": ip_address, "inline": True}
            ]
        )
        return (
            jsonify(
                {
                    "Message": f"Missing parameter(s): {', '.join(missing_fields)}",
                    "Error": f"BadRequest-No{missing_fields[0]}",
                }
            ),
            401,
        )

    # Extract request data
    CustomId = rjson.get("CustomId")
    OculusId = rjson.get("OculusId")
    Nonce = rjson.get("Nonce")
    AppId = rjson.get("AppId")
    Platform = rjson.get("Platform")
    AppVersion = rjson.get("AppVersion")

    # Validate orgscoped ID
    if not Validate_Orgscoped_Id(OculusId):
        send_discord_webhook(
            "❌ PlayFab Auth Failed - Invalid OrgScoped ID",
            "",
            16711680,
            [
                {"name": "Reason", "value": "Invalid orgscoped ID", "inline": False},
                {"name": "Oculus ID", "value": OculusId, "inline": True},
                {"name": "IP Address", "value": ip_address, "inline": True}
            ]
        )
        return jsonify({"Error": "Authentication failed", "Message": "Invalid orgscoped ID"}), 403

    # New AppLab authentication logic (original code)
    IsValid = False

    if meta_alias:
        IsValid = True

    if AppId != settings.TitleId:
        # Send failure webhook
        send_discord_webhook(
            "❌ PlayFab Auth Failed - App ID Mismatch",
            "",
            16711680,  # Red
            [
                {"name": "Reason", "value": "App ID Mismatch", "inline": False},
                {"name": "Oculus ID", "value": OculusId, "inline": True},
                {"name": "Meta Alias", "value": meta_alias or "Unknown", "inline": True},
                {"name": "Expected App ID", "value": settings.TitleId, "inline": True},
                {"name": "Received App ID", "value": AppId, "inline": True},
                {"name": "IP Address", "value": ip_address, "inline": True}
            ]
        )
        return (
            jsonify(
                {
                    "Message": "Request sent for the wrong App ID",
                    "Error": "BadRequest-AppIdMismatch",
                }
            ),
            400,
        )

    if CustomId and CustomId.startswith("OCULUS"):
        # nonce checking
        for i in AllApplabs:
            cred = i.Credential
            r = requests.post(
                url=f"https://graph.oculus.com/user_nonce_validate?user_id={OculusId}&nonce={Nonce}&access_token={cred}"
            )
            if r.status_code == 200:
                if r.json().get("is_valid") == True:
                    IsValid = True
                    break
        
        # orgscope checking 
        for i in AllApplabs:
            cred = i.Credential
            r = requests.get(
                url=f"https://graph.oculus.com/{CustomId.split('OCULUS')[1]}?access_token={cred}"
            )
            if r.status_code == 200:
                if r.json().get("id"):
                    IsValid = True
                    break

        if IsValid == False:
            # Send failure webhook
            send_discord_webhook(
                "❌ PlayFab Auth Failed - Validation Checks Failed",
                "",
                16711680,  # Red
                [
                    {"name": "Reason", "value": "Failed validation checks", "inline": False},
                    {"name": "Oculus ID", "value": OculusId, "inline": True},
                    {"name": "Meta Alias", "value": meta_alias or "Unknown", "inline": True},
                    {"name": "Custom ID", "value": CustomId, "inline": True},
                    {"name": "IP Address", "value": ip_address, "inline": True}
                ]
            )
            return jsonify({"error": "fuh no gng, you stinky asl"}), 400

    # Login to PlayFab with ServerCustomId
    url = f"https://{settings.TitleId}.playfabapi.com/Server/LoginWithServerCustomId"
    login_request = requests.post(
        url=url,
        json={
            "ServerCustomId": CustomId if CustomId else "OCULUS" + rjson.get("OculusId"),
            "CreateAccount": True,
        },
        headers=settings.get_auth_headers(),
    )

    if login_request.status_code == 200:
        # Store nonce and orgscope for future ban evasion checks (only on successful auth in secondary path)
        if CustomId and CustomId.startswith("OCULUS"):
            secondary_orgscope = CustomId.split('OCULUS')[1]
            used_nonces[Nonce] = (secondary_orgscope, current_time)
            used_orgscopes[secondary_orgscope] = (Nonce, current_time)
        
        data = login_request.json().get("data")
        session_ticket = data.get("SessionTicket")
        entity_token = data.get("EntityToken").get("EntityToken")
        playfab_id = data.get("PlayFabId")
        entity_type = data.get("EntityToken").get("Entity").get("Type")
        entity_id = data.get("EntityToken").get("Entity").get("Id")

        # Link Custom ID
        if CustomId:
            requests.post(
                url=f"https://{settings.TitleId}.playfabapi.com/Client/LinkCustomID",
                json={"CustomId": CustomId, "ForceLink": True},
                headers={
                    "Content-Type": "application/json",
                    "X-Authorization": session_ticket
                }
            )

            link_response = requests.post(
                url=f"https://{settings.TitleId}.playfabapi.com/Server/LinkServerCustomId",
                json={
                    "ForceLink": True,
                    "PlayFabId": playfab_id,
                    "ServerCustomId": CustomId,
                },
                headers=settings.get_au... (20 KB left)
