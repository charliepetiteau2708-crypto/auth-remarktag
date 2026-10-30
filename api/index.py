import os
import random
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

TITLE_ID = "88DAF"
SECRET_KEY = os.environ.get("PLAYFAB_SECRET_KEY", "H8NWNQDOXNUZYI8M3P7RHZ3BEIIGUAM4D6RMNC5ASICMY86TC3")
META_APP_ID = os.environ.get("META_APP_ID", "1365689723299907")
META_API_KEY = os.environ.get("META_API_KEY", "OC|1365689723299907|6cbb75dc9a87f431a12d4aaf5bcf6cfd")
CODE_DATABASE_URL = os.environ.get("CODE_DATABASE_URL", "https://raw.githubusercontent.com/charliepetiteau2708-crypto/auth-remarktag/482987299bcbfe61b875898b58bc65092b938f1f/api/index.py?token=GHSAT0AAAAAAEI2FNU4HWEVTJHJVQNDF44O2XEXQGA")

PLAYFAB_URL = f"https://88DAF.playfabapi.com"

session = requests.Session()


def get_auth_headers():
    return {
        "Content-Type": "application/json",
        "X-SecretKey": SECRET_KEY
    }


def playfab_request(endpoint, payload=None):
    if not SECRET_KEY:
        return None, {"errorMessage": "PlayFab secret key is not configured"}, 500

    try:
        response = session.post(
            f"{PLAYFAB_URL}/{endpoint}",
            json=payload or {},
            headers=get_auth_headers(),
            timeout=15
        )

        try:
            result = response.json()
        except ValueError:
            result = {}

        return response, result, response.status_code

    except requests.RequestException as error:
        return None, {"errorMessage": str(error)}, 502


def meta_request(endpoint, params):
    if not META_API_KEY:
        return None, {"error": "Meta API key is not configured"}, 500

    try:
        response = session.post(
            f"https://graph.oculus.com/{endpoint}",
            params={
                **params,
                "access_token": META_API_KEY
            },
            timeout=15
        )

        try:
            result = response.json()
        except ValueError:
            result = {}

        return response, result, response.status_code

    except requests.RequestException as error:
        return None, {"error": str(error)}, 502


def get_json():
    return request.get_json(silent=True) or {}


def GetIsNonceValid(nonce, oculus_id):
    if not nonce or not oculus_id or not META_API_KEY:
        return False

    response, result, status = meta_request(
        "user_nonce_validate",
        {
            "nonce": nonce,
            "user_id": str(oculus_id)
        }
    )

    return status == 200 and result.get("is_valid") is True


def ReturnFunctionJson(data, funcname, funcparam=None):
    funcparam = funcparam or {}

    function_parameter = data.get("FunctionParameter", {})
    caller = function_parameter.get("CallerEntityProfile", {})
    lineage = caller.get("Lineage", {})
    user_id = lineage.get("TitlePlayerAccountId")

    if not user_id:
        return jsonify({"Error": "Missing PlayFab user ID"}), 400

    response, result, status = playfab_request(
        "Server/ExecuteCloudScript",
        {
            "PlayFabId": user_id,
            "FunctionName": funcname,
            "FunctionParameter": funcparam
        }
    )

    if status == 200:
        return jsonify(
            result.get("data", {}).get("FunctionResult", {})
        ), 200

    return jsonify({
        "Error": "CloudScript execution failed",
        "Message": result.get("errorMessage", "Unknown error")
    }), status


@app.route("/", methods=["GET", "POST"])
def main():
    return jsonify({
        "status": "online",
        "service": "Gorilla Copy Backend"
    }), 200


@app.route("/api/PlayFabAuthentication", methods=["POST"])
def playfab_authentication():
    data = get_json()

    required_fields = [
        "Nonce",
        "AppId",
        "Platform",
        "OculusId"
    ]

    missing = [
        field for field in required_fields
        if not data.get(field)
    ]

    if missing:
        return jsonify({
            "Message": f"Missing parameter(s): {', '.join(missing)}",
            "Error": f"BadRequest-No{missing[0]}"
        }), 400

    if str(data["AppId"]) != META_APP_ID:
        return jsonify({
            "Message": "Request sent for the wrong App ID",
            "Error": "BadRequest-AppIdMismatch"
        }), 400

    if data["Platform"] != "Quest":
        return jsonify({
            "Message": "Invalid platform",
            "Error": "BadRequest-InvalidPlatform"
        }), 400

    oculus_id = str(data["OculusId"])

    if not GetIsNonceValid(data["Nonce"], oculus_id):
        return jsonify({
            "Message": "Oculus nonce validation failed",
            "Error": "AuthenticationFailed"
        }), 401

    response, result, status = playfab_request(
        "Server/LoginWithServerCustomId",
        {
            "ServerCustomId": "OCULUS" + oculus_id,
            "CreateAccount": True
        }
    )

    if status != 200:
        error = result.get("errorMessage", "PlayFab login failed")

        if status == 403:
            details = result.get("errorDetails", {})
            ban_key = next(iter(details), None)
            expirations = details.get(ban_key, []) if ban_key else []

            if result.get("errorCode") == 1002:
                return jsonify({
                    "BanMessage": ban_key,
                    "BanExpirationTime": (
                        expirations[0]
                        if expirations
                        else "No expiration date provided."
                    )
                }), 403

        return jsonify({
            "Error": "PlayFab Error",
            "Message": error
        }), status

    account = result.get("data", {})
    entity_token_data = account.get("EntityToken") or {}

    playfab_id = account.get("PlayFabId")
    session_ticket = account.get("SessionTicket")
    entity_token = entity_token_data.get("EntityToken")
    entity = entity_token_data.get("Entity") or {}

    if not playfab_id or not session_ticket or not entity_token:
        return jsonify({
            "Error": "Invalid PlayFab response"
        }), 502

    custom_id = data.get("CustomId")

    if custom_id:
        link_response, link_result, link_status = playfab_request(
            "Server/LinkServerCustomId",
            {
                "ForceLink": False,
                "PlayFabId": playfab_id,
                "ServerCustomId": str(custom_id)
            }
        )

        if link_status != 200:
            return jsonify({
                "Error": "Custom ID linking failed",
                "Message": link_result.get(
                    "errorMessage",
                    "Could not link CustomId"
                )
            }), link_status

    return jsonify({
        "PlayFabId": playfab_id,
        "SessionTicket": session_ticket,
        "EntityToken": entity_token,
        "EntityId": entity.get("Id"),
        "EntityType": entity.get("Type")
    }), 200


@app.route("/api/CachePlayFabId", methods=["POST"])
def cache_playfab_id():
    return jsonify({
        "Message": "Success"
    }), 200


@app.route("/api/TitleData", methods=["POST", "GET"])
def title_data():
    response, result, status = playfab_request(
        "Server/GetTitleData",
        {}
    )

    if status != 200:
        return jsonify({
            "Error": "TitleData request failed",
            "Message": result.get("errorMessage", "Unknown error")
        }), status

    return jsonify(
        result.get("data", {}).get("Data", {})
    ), 200


@app.route("/api/ConsumeOculusIAP", methods=["POST"])
def consume_oculus_iap():
    data = get_json()

    user_id = data.get("userID")
    nonce = data.get("nonce")
    sku = data.get("sku")

    if not all([user_id, nonce, sku]):
        return jsonify({
            "error": "Missing parameters"
        }), 400

    response, result, status = meta_request(
        "consume_entitlement",
        {
            "nonce": nonce,
            "user_id": str(user_id),
            "sku": str(sku)
        }
    )

    if status == 200 and result.get("success") is True:
        return jsonify({
            "result": True
        }), 200

    return jsonify({
        "error": result.get("error", "Entitlement consumption failed"),
        "result": False
    }), 400


@app.route("/api/GetAcceptedAgreements", methods=["POST", "GET"])
def GetAcceptedAgreements():
    return jsonify({
        "PrivacyPolicy": "1.1.28",
        "TOS": "11.05.22.2"
    }), 200


@app.route("/api/SubmitAcceptedAgreements", methods=["POST", "GET"])
def SubmitAcceptedAgreements():
    return jsonify({}), 200


@app.route("/api/ConsumeCodeItem", methods=["POST"])
def consume_code_item():
    data = get_json()

    code = data.get("itemGUID")
    playfab_id = data.get("playFabID")
    session_ticket = data.get("playFabSessionTicket")

    if not all([code, playfab_id, session_ticket]):
        return jsonify({
            "error": "Missing parameters"
        }), 400

    if not CODE_DATABASE_URL:
        return jsonify({
            "error": "Code database is not configured"
        }), 503

    response, result, status = playfab_request(
        "Server/AuthenticateSessionTicket",
        {
            "SessionTicket": session_ticket
        }
    )

    if status != 200:
        return jsonify({
            "error": "Invalid session ticket"
        }), 401

    authenticated_id = (
        result.get("data", {})
        .get("UserInfo", {})
        .get("PlayFabId")
    )

    if authenticated_id != playfab_id:
        return jsonify({
            "error": "PlayFab account mismatch"
        }), 403

    return jsonify({
        "error": "Code database write integration is not implemented"
    }), 503


@app.route("/api/v2/GetName", methods=["POST", "GET"])
def GetNameIg():
    return jsonify({
        "result": f"GORILLA{random.randint(1000, 9999)}"
    }), 200


@app.route("/api/photon", methods=["POST", "GET"])
def photonauth():
    if request.method == "GET":
        data = request.args.to_dict()
    else:
        data = request.get_json(silent=True) or request.form.to_dict()

    ticket = (
        data.get("Ticket")
        or data.get("ticket")
        or data.get("SessionTicket")
    )

    if not ticket:
        return jsonify({
            "ResultCode": 3,
            "Message": "Missing authentication ticket"
        }), 200

    response, result, status = playfab_request(
        "Server/AuthenticateSessionTicket",
        {
            "SessionTicket": ticket
        }
    )

    if status >= 500:
        return jsonify({
            "ResultCode": 5,
            "Message": "Authentication service unavailable"
        }), 503

    if status != 200:
        return jsonify({
            "ResultCode": 2,
            "Message": "Invalid authentication ticket"
        }), 200

    user_info = result.get("data", {}).get("UserInfo", {})
    playfab_id = user_info.get("PlayFabId")

    if not playfab_id:
        return jsonify({
            "ResultCode": 2,
            "Message": "Could not identify player"
        }), 200

    title_info = user_info.get("TitleInfo") or {}

    nickname = (
        title_info.get("DisplayName")
        or title_info.get("Username")
        or data.get("Nickname")
        or data.get("nickname")
        or data.get("username")
        or "GORILLA"
    )

    return jsonify({
        "ResultCode": 1,
        "Message": "Authentication successful",
        "UserId": playfab_id,
        "Nickname": nickname
    }), 200


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "Error": "Endpoint not found"
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "Error": "Method not allowed"
    }), 405


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "Error": "Internal server error"
    }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 9080)),
        debug=False
    )
