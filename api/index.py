import requests
import random
from flask import Flask, jsonify, request
import json
import os
import base64
import hashlib
import secrets
from datetime import datetime, timedelta

class GameInfo:
    def __init__(self):
        self.ApiKey: str = "OC|1393855260483353|c0fdb9b3d2a235223cfbc905388eb33f"

    def get_auth_headers(self):
        return {"content-type": "application/json", "X-Api-Key": self.ApiKey}

settings = GameInfo()
app = Flask(__name__)

Valid_Package = "com.company.product"
Cert = "your hash thingy"
currentNonces = {}

def AttestationAuthentication(AttestationToken):
    url = (
        "https://graph.oculus.com/platform_integrity/verify"
        f"?token={AttestationToken}&access_token={settings.ApiKey}"
    )
    resp = requests.get(url)
    return resp.json()

def VerifyOculusStandards(userId, nonce):
    validate_url = "https://graph.oculus.com/user_nonce_validate"
    validate_payload = {
        "access_token": settings.ApiKey,
        "nonce": nonce,
        "user_id": userId
    }

    try:
        response = requests.post(validate_url, data=validate_payload)
        response.raise_for_status()
        validation_data = response.json()
    except Exception as e:
        return {"is_valid": False, "org_scoped_id": None, "error": str(e)}

    if not validation_data.get("is_valid"):
        return {"is_valid": False, "org_scoped_id": None}

    org_id_url = f"https://graph.oculus.com/{userId}"
    org_id_params = {
        "access_token": settings.ApiKey,
        "fields": "org_scoped_id"
    }

    try:
        org_response = requests.get(org_id_url, params=org_id_params)
        org_response.raise_for_status()
        org_data = org_response.json()
        org_scoped_id = org_data.get("org_scoped_id")
    except Exception as e:
        return {"is_valid": True, "org_scoped_id": None, "error": str(e)}

    return {"is_valid": True, "org_scoped_id": org_scoped_id}


@app.route("/api/authenticate/attestation/getNonce", methods=["POST"])
def GetNonce():
    data = request.get_json()

    user_id = data.get("UserId")
    nonce = data.get("Nonce")

    if not user_id:
        return jsonify({"error": "The user id provided is null, empty or undefined"}), 400

    if not nonce:
        return jsonify({"error": "The nonce provided is null, empty or undefined"}), 400

    verification = VerifyOculusStandards(user_id, nonce)

    if not verification["is_valid"]:
        return jsonify({
            "error": "The user information details provided are invalid and or undefined"
    }), 403

    challengeNonce = secrets.token_urlsafe(16)
    currentNonces[user_id] = challengeNonce

    return jsonify({
        "challenge_nonce": challengeNonce,
        "org_scoped_id": verification["org_scoped_id"]
    })

@app.route("/api/authenticate/attestation/mothershipAuth", methods=["POST"])
def MotherShipAuth():
    rjson = request.get_json()
    user_id = rjson.get("UserId")
    attestation_token = rjson.get("AttestationToken")

    if not attestation_token or attestation_token.strip() == "":
        return jsonify({
            "BanMessage": "OCULUS INTEGRITY AUTHENTICATION FAILED. REASON: The mothership authentication attestation token is null or empty.",
            "BanExpirationTime": "Unkown"
        }), 403

    data = AttestationAuthentication(attestation_token)

    if "data" not in data or len(data["data"]) == 0:
        return jsonify({
            "BanMessage": "OCULUS INTEGRITY AUTHENTICATION FAILED. REASON: The mothership authentication responded with a value less then 1, the attestation authentication must return a value greater then 0 and not less then 0, example: 1, 2, 3, 4. But the response is less then 1. eg: the Validation responded with null or empty data.",
            "BanExpirationTime": "Unkown"
        }), 403

    response_data = data["data"][0]

    if response_data.get("message") == "invalid signature":
        return jsonify({
            "BanMessage": "OCULUS INTEGRITY AUTHENTICATION FAILED. REASON: The mothership attestation authentication responded with a invalid attestation token authentication signature, please check you are on the latest version of the game. The attestation authentication has refused your authentication request due to you token having an invalid signature.",
            "BanExpirationTime": "Unkown"
        }), 403

    if response_data.get("message") == "token expired":
        return jsonify({
            "BanMessage": "OCULUS INTEGRITY AUTHENTICATION FAILED. REASON: The mothership attestation authentication responded with your attestation token authentication being expired, please check you are on the latest version of the game. The attestation authentication has refused your authentication request due to your token being expired.",
            "BanExpirationTime": "Unkown"
        }), 403

    if response_data.get("message") != "success":
        return jsonify({
            "BanMessage": "OCULUS INTEGRITY AUTHENTICATION FAILED. REASON: The mothership attestation authentication responded with your attestation token authentication being a invalid token, please check you are on the latest version of the game. The attestation authentication has refused your authentication request due to your token being invalid and not a valid attestation authentication request.",
            "BanExpirationTime": "Unkown"
        }), 403

    claims = response_data.get("claims")
    decoded_bytes = base64.urlsafe_b64decode(claims + "==")
    claims_json = json.loads(decoded_bytes)

    request_details = claims_json.get("request_details", {})
    app_state = claims_json.get("app_state", {})
    device_state = claims_json.get("device_state", {})
    device_ban = claims_json.get("device_ban", {})
    security_state = claims_json.get("device_state", {})

    unique_id = device_state.get("unique_id") if device_state else None
    device_integrity_state = device_state.get("device_integrity_state") if device_state else None
    StoreRecognized = app_state.get("app_integrity_state") if app_state else None
    securityUpdate = security_state.get("security_update_pending_days") if security_state else None
    packageId = app_state.get("package_id") if app_state else None
    Sha256Sig = app_state.get("package_cert_sha256_digest") if app_state else None
    device_ban_status = device_ban.get("is_banned") if device_ban else False

    if Sha256Sig is None or Cert not in Sha256Sig:
        return jsonify({
            "BanMessage": "OCULUS INTEGRITY AUTHENTICATION FAILED. REASON: The mothership attestation authentication has rejected your request due to your package cert being unrecognized.",
            "BanExpirationTime": "Unknown"
        }), 403

    if device_ban_status:
        return jsonify({
            "BanMessage": "Your device is currently banned from this application.",
            "BanExpirationTime": device_ban.get("remaining_ban_time", "Unknown")
        }), 403

    if unique_id is None or device_integrity_state is None or StoreRecognized is None or packageId is None or Sha256Sig is None:
            return jsonify({
                "BanMessage": "OCULUS INTEGRITY AUTHENTICATION FAILED. REASON: The mothership attestation authentication responded with no data. the data must be greater then 0, please check you are on the latest version of the game. The attestation authentication has refused your authentication request due to the authentication response return is null or empty or less then 1.",
                "BanExpirationTime": "Unkown"
            }), 403

    if packageId != Valid_Package:
            return jsonify({
                "BanMessage": "OCULUS INTEGRITY AUTHENTICATION FAILED. REASON: The mothership attestation authentication responded with your package id being a unkown package cert, please check you are on the latest version of the game. The attestation authentication has refused your authentication request due to the authentication response returning a unkown package cert.",
                "BanExpirationTime": "Unkown"
            }), 403

    if device_integrity_state != "Advanced":
            return jsonify({
                "BanMessage": "OCULUS INTEGRITY AUTHENTICATION FAILED. REASON: The mothership attestation authentication responded with your device integrity state being untrusted, please check you are on the latest version of the game. The attestation authentication has refused your authentication request due to the authentication response returning your device integrity state being untrusted.",
                "BanExpirationTime": "Unkown"
            }), 403

    if StoreRecognized != "StoreRecognized":
            return jsonify({
                "BanMessage": "OCULUS INTEGRITY AUTHENTICATION FAILED. REASON: The mothership attestation authentication responded with your download source being a invalid download director source, please check you are on the latest version of the game. The attestation authentication has refused your authentication request due to the authentication response returning your download source being unrecongnised.",
                "BanExpirationTime": "Unkown"
            }), 403

    return jsonify({
            "Success!": "OCULUS INTEGRITY AUTHENTICATION PASSED. REASON: The mothership attestation authentication responded with your authentication validation being valid"
            })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7080)
