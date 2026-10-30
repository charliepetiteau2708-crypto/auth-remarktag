import requests
import random
from flask import Flask, jsonify, request

app = Flask(__name__)


titleider = "88DAF"
secretkey = "H8NWNQDOXNUZYI8M3P7RHZ3BEIIGUAM4D6RMNC5ASICMY86TC3"
ApiKey = "OC|1365689723299907|6cbb75dc9a87f431a12d4aaf5bcf6cfd"


def GetAuthHeaders() -> dict:
    return {"content-type": "application/json", "X-SecretKey": secretkey}


def GetTitle() -> str:
    return titleider


@app.route("/api/GetAcceptedAgreements", methods=['POST'])
def GetAcceptedAgreements():
    received_data = request.get_json()

    return jsonify({
        "ResultCode": 1,
        "StatusCode": 200,
        "Message": '',
        "result": 0,
        "CallerEntityProfile": received_data['CallerEntityProfile'],
        "TitleAuthenticationContext": received_data['TitleAuthenticationContext']
    })

@app.route("/api/SubmitAcceptedAgreements", methods=['POST'])
def SubmitAcceptedAgreements():
    received_data = request.get_json()

    return jsonify({
        "ResultCode": 1,
        "StatusCode": 200,
        "Message": '',
        "result": 0,
        "CallerEntityProfile": received_data['CallerEntityProfile'],
        "TitleAuthenticationContext": received_data['TitleAuthenticationContext'],
        "FunctionArgument": received_data['FunctionArgument']
    })

def save_accepted_agreements(agreements):
    with open('accepted_agreements.json', 'w') as file:
        json.dump(agreements, file)

@app.route("/api/CachePlayFabId", methods=["POST"])
def cacheplayfabid():
    idfk = request.get_json()
    playfabid = idfk.get("SessionTicket").split("-")[0]
    actually = ["SessionTicket", "Platform"]
    if actually not in idfk:
        return jsonify({"Message": "Try Again Later."}), 404

    else:
        return jsonify({"Message": "Authed", "PlayFabId": playfabid}), 200


@app.route("/", methods=["POST", "GET"])
def Rizz():
    return "backend good"


@app.route("/api/td", methods=["POST", "GET"])
def bel():
    realshit = f"https://{titleider}.playfabapi.com/Server/GetTitleData"
    blah = {"X-SecretKey": secretkey, "Content-Type": "application/json"}
    e = requests.post(url=realshit, headers=blah)
    sigmarizzauth = e.json().get("data", "").get("Data", "")

    return jsonify(sigmarizzauth)

@app.route("/api/GetRandomName", methods=["POST", "GET"])
def get_random_name():
    return jsonify({"result": f"gorilla{random.randint(1000, 9999)}"})

@app.route("/api/ConsumeOculusIAP", methods=["POST"])
def consume_oculus_iap():
    rjson = request.get_json()

    access_token = rjson.get("userToken")
    user_id = rjson.get("userID")
    nonce = rjson.get("nonce")
    sku = rjson.get("sku")

    response = requests.post(
        url=f"https://graph.oculus.com/consume_entitlement?nonce={nonce}&user_id={user_id}&sku={sku}&access_token={ApiKey}",
        headers={"content-type": "application/json"}
    )

    if response.json().get("success"):
        return jsonify({"result": True})
    else:
        return jsonify({"error": True})

@app.route("/api/PlayFabAuthentication", methods=["POST"])
def playfab_authentication():
    rjson = request.get_json()
    if not rjson:
        return jsonify({
            "Message": "Invalid JSON in request body",
            "Error": "BadRequest-InvalidJSON"
        }), 400

    required_fields = ["CustomId", "Nonce", "AppId", "Platform", "OculusId"]
    missing_fields = [field for field in required_fields if not rjson.get(field)]

    if missing_fields:
        return jsonify({
            "Message": f"Missing parameter(s): {', '.join(missing_fields)}",
            "Error": f"BadRequest-No{missing_fields[0]}"
        }), 400

    if rjson.get("AppId") != titleider:
        return jsonify({
            "Message": "Request sent for the wrong App ID",
            "Error": "BadRequest-AppIdMismatch"
        }), 400

    custom_id = rjson.get("CustomId", "")
    if not custom_id.startswith(("OC", "PI")):
        return jsonify({
            "Message": "Bad request",
            "Error": "BadRequest-NoOCorPIPrefix"
        }), 400

    url = f"https://{titleider}.playfabapi.com/Server/LoginWithServerCustomId"
    login_request = requests.post(
        url=url,
        json={
            "ServerCustomId": custom_id,
            "CreateAccount": True
        },
        headers=GetAuthHeaders()
    )

    if login_request.status_code == 200:
        data = login_request.json().get("data", {})
        session_ticket = data.get("SessionTicket")
        entity_token_data = data.get("EntityToken", {})
        entity_token = entity_token_data.get("EntityToken")
        playfab_id = data.get("PlayFabId")
        entity_data = entity_token_data.get("Entity", {})
        entity_type = entity_data.get("Type"),
        entity_id = entity_data.get("Id"),

        link_response = requests.post(
            url=f"https://{titleider}.playfabapi.com/Server/LinkServerCustomId",
            json={
                "ForceLink": True,
                "PlayFabId": playfab_id,
                "ServerCustomId": custom_id,
            },
            headers=GetAuthHeaders()
        )

        if link_response.status_code != 200:
            link_response_json = link_response.json()
            error_message = link_response_json.get('errorMessage', 'Unknown error')
            error_details = link_response_json.get('errorDetails', {})
            return jsonify({
                "ErrorMessage": error_message,
                "ErrorDetails": error_details
            }), link_response.status_code

        return jsonify({
            "PlayFabId": playfab_id,
            "SessionTicket": session_ticket,
            "EntityToken": entity_token,
            "EntityId": entity_id,
            "EntityType": entity_type,
        }), 200
    else:
        if login_request.status_code == 403:
            ban_info = login_request.json()
            if ban_info.get('errorCode') == 1002:
                ban_message = ban_info.get('errorMessage', "No ban message provided.")
                ban_details = ban_info.get('errorDetails', {})
                ban_expiration_key = next(iter(ban_details.keys()), None)
                ban_expiration_list = ban_details.get(ban_expiration_key, [])
                ban_expiration = ban_expiration_list[0] if len(ban_expiration_list) > 0 else "No expiration date provided."
                print(ban_info)
                return jsonify({
                    'BanMessage': ban_expiration_key,
                    'BanExpirationTime': ban_expiration
                }), 403
            else:
                error_message = ban_info.get('errorMessage', 'Forbidden without ban information.')
                return jsonify({
                    'Error': 'PlayFab Error',
                    'Message': error_message
                }), 403
        else:
            error_info = login_request.json()
            error_message = error_info.get('errorMessage', 'An error occurred.')
            return jsonify({
                'Error': 'PlayFab Error',
                'Message': error_message
            }), login_request.status_code

@app.route("/api/photon", methods=["POST"])
def photonauth():
    print(f"Received {request.method} request at /api/photon")
    getjson = request.get_json()
    Ticket = getjson.get("Ticket")
    Nonce = getjson.get("Nonce")
    AppVersion = getjson.get("AppVersion")
    Platform = getjson.get("Platform")
    UserId = getjson.get("UserId")
    nickName = getjson.get("username")
    if request.method.upper() == "GET":
        rjson = request.get_json()
        print(f"{request.method} : {rjson}")

        userId = Ticket.split('-')[0] if Ticket else None
        print(f"Extracted userId: {UserId}")

        if userId is None or len(userId) != 16:
            print("Invalid userId")
            return jsonify({
                'resultCode': 2,
                'message': 'Invalid token',
                'userId': None,
                'nickname': None
            })

        if Platform != 'Quest':
            return jsonify({'Error': 'Bad request', 'Message': 'Invalid platform!'}),403

        if Nonce is None:
            return jsonify({'Error': 'Bad request', 'Message': 'Not Authenticated!'}),304

        req = requests.post(
            url=f"https://{titleider}.playfabapi.com/Server/GetUserAccountInfo",
            json={"PlayFabId": userId},
            headers={
                "content-type": "application/json",
                "X-SecretKey": secretkey
            })

        print(f"Request to PlayFab returned status code: {req.status_code}")

        if req.status_code == 200:
            nickName = req.json().get("UserInfo",
                                      {}).get("UserAccountInfo",
                                              {}).get("Username")
            if not nickName:
                nickName = None

            print(
                f"Authenticated user {userId.lower()} with nickname: {nickName}"
            )

            return jsonify({
                'resultCode': 1,
                'message':
                f'Authenticated user {userId.lower()} title {titleider.lower()}',
                'userId': f'{userId.upper()}',
                'nickname': nickName
            })
        else:
            print("Failed to get user account info from PlayFab")
            return jsonify({
                'resultCode': 0,
                'message': "Something went wrong",
                'userId': None,
                'nickname': None
            })

    elif request.method.upper() == "POST":
        rjson = request.get_json()
        print(f"{request.method} : {rjson}")

        ticket = rjson.get("Ticket")
        userId = ticket.split('-')[0] if ticket else None
        print(f"Extracted userId: {userId}")

        if userId is None or len(userId) != 16:
            print("Invalid userId")
            return jsonify({
                'resultCode': 2,
                'message': 'Invalid token',
                'userId': None,
                'nickname': None
            })

        req = requests.post(
             url=f"https://{titleider}.playfabapi.com/Server/GetUserAccountInfo",
             json={"PlayFabId": userId},
             headers={
                 "content-type": "application/json",
                 "X-SecretKey": secretkey
             })

        print(f"Authenticated user {userId.lower()}")
        print(f"Request to PlayFab returned status code: {req.status_code}")

        if req.status_code == 200:
             nickName = req.json().get("UserInfo",
                                       {}).get("UserAccountInfo",
                                               {}).get("Username")
             if not nickName:
                 nickName = None
             return jsonify({
                 'resultCode': 1,
                 'message':
                 f'Authenticated user {userId.lower()} title {titleider.lower()}',
                 'userId': f'{userId.upper()}',
                 'nickname': nickName
             })
        else:
             print("Failed to get user account info from PlayFab")
             successJson = {
                 'resultCode': 0,
                 'message': "Something went wrong",
                 'userId': None,
                 'nickname': None
             }
             authPostData = {}
             for key, value in authPostData.items():
                 successJson[key] = value
             print(f"Returning successJson: {successJson}")
             return jsonify(successJson)
    else:
         print(f"Invalid method: {request.method.upper()}")
         return jsonify({
             "Message":
             "Use a POST or GET Method instead of " + request.method.upper()
         })

def ReturnFunctionJson(data, funcname, funcparam={}):
    print(f"Calling function: {funcname} with parameters: {funcparam}")
    rjson = data.get("FunctionParameter", {})
    userId = rjson.get("CallerEntityProfile",
                       {}).get("Lineage", {}).get("TitlePlayerAccountId")

    print(f"UserId: {userId}")

    req = requests.post(
        url=f"https://{titleider}.playfabapi.com/Server/ExecuteCloudScript",
        json={
            "PlayFabId": userId,
            "FunctionName": funcname,
            "FunctionParameter": funcparam
        },
        headers={
            "content-type": "application/json",
            "X-SecretKey": secretkey
        })

    if req.status_code == 200:
        result = req.json().get("data", {}).get("FunctionResult", {})
        print(f"Function result: {result}")
        return jsonify(result), req.status_code
    else:
        print(f"Function execution failed, status code: {req.status_code}")
        return jsonify({}), req.status_code

@app.route("/api/ReturnMyOculusHashV2")
def return_my_oculus_hash_v2():
    settings.GetAuthHeaders()
    return ReturnFunctionJson(request.get_json(), "ReturnMyOculusHash")

@app.route("/api/ReturnCurrentVersionV2", methods=["POST", "GET"])
def return_current_version_v2():
    settings.GetAuthHeaders()
    return ReturnFunctionJson(request.get_json(), "ReturnCurrentVersion")

@app.route("/api/TryDistributeCurrencyV2", methods=["POST", "GET"])
def try_distribute_currency_v2():
    settings.GetAuthHeaders()
    return ReturnFunctionJson(request.get_json(), "TryDistributeCurrency")

@app.route("/api/AddOrRemoveDLCOwnershipV2", methods=["POST", "GET"])
def add_or_remove_dlc_ownership_v2():
    settings.GetAuthHeaders()
    return ReturnFunctionJson(request.get_json(), "AddOrRemoveDLCOwnership")

@app.route("/api/UpdatePersonalCosmeticsList", methods=["POST", "GET"])
def update_personal_cosmetics_list():
    settings.GetAuthHeaders()
    return ReturnFunctionJson(request.get_json(), "UpdatePersonalCosmeticsList")

@app.route("/api/UpdateUserCosmetics", methods=["POST", "GET"])
def update_user_cosmetics():
    settings.GetAuthHeaders()
    return ReturnFunctionJson(request.get_json(), "UpdateUserCosmetics")

@app.route("/api/UploadGorillanalytics", methods=["POST", "GET"])
def upload_gorilla_analytics():
    settings.GetAuthHeaders()
    return ReturnFunctionJson(request.get_json(), "UploadGorillanalytics")

@app.route("/api/Gorillanalytics", methods=["POST", "GET"])
def gorilla_analytics():
    settings.GetAuthHeaders()
    return ReturnFunctionJson(request.get_json(), "Gorillanalytics")

@app.route("/api/UpdatePersonalCosmetics", methods=["POST", "GET"])
def update_personal_cosmetics():
    settings.GetAuthHeaders()
    return ReturnFunctionJson(request.get_json(), "UpdatePersonalCosmetics")

@app.route("/api/ConsumeItem", methods=["POST", "GET"])
def consume_item():
    settings.GetAuthHeaders()
    return ReturnFunctionJson(request.get_json(), "ConsumeItem")

@app.route("/api/NewCosmeticsPath", methods=["POST", "GET"])
def new_cosmetics_path():
    settings.GetAuthHeaders()
    return ReturnFunctionJson(request.get_json(), "NewCosmeticsPath")

@app.route("/api/BroadcastMyRoomV2", methods=["POST", "GET"])
def broadcast_my_room_v2():
    settings.GetAuthHeaders()
    return ReturnFunctionJson(request.get_json(), "BroadCastMyRoom", request.get_json()["FunctionParameter"])

@app.route("/api/ShouldUserAutomutePlayer", methods=["POST", "GET"])
def should_user_automute_player():
    return jsonify(mute_cache)

@app.route("/api/ReturnQueueStats", methods=["POST", "GET"])
def return_queue_stats():
    return ReturnFunctionJson(request.get_json(), "ReturnQueueStats",)

@app.route("/api/ConsumeCodeItem", methods=["POST", "GET"])
def consume_code_item():
    return ReturnFunctionJson(request.get_json(), "ConsumeCodeItem",)

@app.route("/api/CosmeticsAuthenticationV2", methods=["POST", "GET"])
def cosmetic_auth():
    settings.GetAuthHeaders()
    return ReturnFunctionJson(request.get_json(), "CosmeticsAuthentication")

@app.route("/api/KIDIntegrationV1", methods=["POST", "GET"])
def kid_intergration():
    settings.GetAuthHeaders()
    return ReturnFunctionJson(request.get_json(), "KIDIntegration")

if __name__ == "__main__":

 app.run("0.0.0.0", 8080)
