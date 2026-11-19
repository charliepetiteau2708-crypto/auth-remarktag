import requests
import random
from flask import Flask, jsonify, request

class GameInfo():
    def __init__(self):
        self.TitleId : str = "1E73C"
        self.SecretKey : str = "XJUNZO7QM9W8E19GM1P98PPUIX5GBQMGRHJYFDB7ESYR9U9BGM"
        self.ApiKey : str = "e3649fc133c83c9a86fcdb739344ea43"

    def GetAuthHeaders(self) -> dict:
        return {
            "content-type": "application/json",
            "X-SecretKey": self.SecretKey
        }

    def GetTitle(self) -> str:
        return self.TitleId


settings : GameInfo = GameInfo()
app : Flask = Flask(__name__)
playfabCache : dict = {}
muteCache : dict = {}

settings.TitleId = ""
settings.SecretKey = ""
settings.ApiKey = ""

def ReturnFunctionJson(data, funcname, funcparam = {}):
    rjson = data["FunctionParameter"]

    userId : str = rjson.get("CallerEntityProfile").get("Lineage").get("TitlePlayerAccountId")

    req = requests.post(
        url = f"https://{settings.TitleId}.playfabapi.com/Server/ExecuteCloudScript",
        json = {
            "PlayFabId": userId,
            "FunctionName": funcname,
            "FunctionParameter": funcparam
        },
        headers = settings.GetAuthHeaders()
    )

    if req.status_code == 200:
        return jsonify(req.json().get("data").get("FunctionResult")), req.status_code
    else:
        return jsonify({}), req.status_code

def GetIsNonceValid(nonce : str, oculusId : str):
    req = requests.post(
        url = f'https://graph.oculus.com/user_nonce_validate?nonce=' + nonce + '&user_id=' + oculusId  + '&access_token=' + settings.ApiKey,
        headers = {
            "content-type": "application/json"
        }
    )
    return req.json().get("is_valid")

@app.route("/", methods = ["POST", "GET"])
def main():
    return "Made By cycy"

#replace https://auth-prod.gtag-cf.com/api/PlayFabAuthentication with this endpoint
@app.route("/api/PlayFabAuthentication", methods = ["POST", "GET"])
def playfabauthentication():
    rjson = request.get_json()

    if rjson.get("CustomId") is None:
        return jsonify({"Message":"Missing CustomId parameter","Error":"BadRequest-NoCustomId"})
    if rjson.get("Nonce") is None:
        return jsonify({"Message":"Missing Nonce parameter","Error":"BadRequest-NoNonce"})
    if rjson.get("AppId") is None:
        return jsonify({"Message":"Missing AppId parameter","Error":"BadRequest-NoAppId"})
    if rjson.get("Platform") is None:
        return jsonify({"Message":"Missing Platform parameter","Error":"BadRequest-NoPlatform"})
    if rjson.get("OculusId") is None:
        return jsonify({"Message":"Missing OculusId parameter","Error":"BadRequest-NoOculusId"})

    if rjson.get("AppId") != settings.TitleId:
        return jsonify({"Message":"Request sent for the wrong App ID","Error":"BadRequest-AppIdMismatch"})
    if not rjson.get("CustomId").startswith("OC") and not rjson.get("CustomId").startswith("PI"):
        return jsonify({"Message":"Bad request","Error":"BadRequest-No OC or PI Prefix"})

    #goodNonce : bool = GetIsNonceValid(str(rjson.get("Nonce")), str(rjson.get("OculusId")))

    #if bool(goodNonce) == False:
    #    return jsonify({"Message":"Bad request","Error":"BadRequest-BadRequest-InvalidNonce"})


    url = f"https://{settings.TitleId}.playfabapi.com/Server/LoginWithServerCustomId"
    login_request = requests.post(
        url = url,
        json = {
            "ServerCustomId": rjson.get("CustomId"),
            "CreateAccount": True
        },
        headers = settings.GetAuthHeaders()
    )
    if login_request.status_code == 200:
        data =  login_request.json().get("data")
        sessionTicket = data.get("SessionTicket")
        entityToken = data.get("EntityToken").get("EntityToken")
        playFabId = data.get("PlayFabId")
        entityType = data.get("EntityToken").get("Entity").get("Type")
        entityId = data.get("EntityToken").get("Entity").get("Id")


        print(requests.post(
            url = f"https://{settings.TitleId}.playfabapi.com/Client/LinkCustomID",
            json = {
                "ForceLink": True,
                "CustomId": rjson.get("CustomId")
            },
            headers = settings.GetAuthHeaders()
        ).json())

        return jsonify({
            "PlayFabId": playFabId,
            "SessionTicket": sessionTicket,
            "EntityToken": entityToken,
            "EntityId": entityId,
            "EntityType": entityTypeO
        })
    else:
        errorDetails = login_request.json().get('errorDetails')
        firstBan = next(iter(errorDetails))
        return jsonify({
            "BanMessage": str(firstBan),
            "BanExpirationTime": str(errorDetails[firstBan])
        })

#replace https://auth-prod.gtag-cf.com/api/CachePlayFabId with this endpoint
@app.route("/api/CachePlayFabId", methods = ["POST","GET"])
def cacheplatfabid():
    rjson = request.get_json()

    playfabCache[rjson.get("PlayFabId")] = rjson

    return jsonify({"Message":"Success"}), 200

#replace https://title-data.gtag-cf.com with this endpoint
@app.route("/api/TitleData", methods = ["POST", "GET"])
def titledata():

    req = requests.post(
        url = f"https://{settings.TitleId}.playfabapi.com/Server/GetTitleData",
        headers = settings.GetAuthHeaders()
    )

    if req.status_code == 200:
        return jsonify(req.json().get("data").get("Data"))
    else:
        return jsonify({})

@app.route("/api/CheckForBadName", methods = ["POST", "GET"])
def checkforbadname():
    rjson = request.get_json().get("FunctionResult")

    name : str = rjson.get("name").upper()

    if [
        "NIGGER",
        "NIGGA",
        "FAGGOT",
        "NIGG",
        "NIGGAR"
    ].__contains__(name):
        return jsonify({"result":2})
    else:
        return jsonify({"result":0})

@app.route("/api/GetAcceptedAgreements", methods = ["POST", "GET"])
def getacceptedagreements():
    rjson = request.get_json()["FunctionResult"]

    return jsonify(rjson)

@app.route("/api/SubmitAcceptedAgreements", methods = ["POST", "GET"])
def submitacceptedagreements():
    rjson = request.get_json()["FunctionResult"]

    return jsonify(rjson)

@app.route("/api/GetRandomName", methods = ["POST", "GET"])
def GetRandomName():
    return jsonify({"result": "gorilla" + random.randint(1000, 9999)})

# replace https://iap.gtag-cf.com/api/ConsumeOculusIAP with this endpoint
@app.route("/api/ConsumeOculusIAP", methods = ["POST", "GET"])
def consumeoculusiap():
    rjson = request.get_json()

    accessToken = rjson.get("userToken")
    userId = rjson.get("userID")
    playFabId = rjson.get("playFabId")
    nonce = rjson.get("nonce")
    platform = rjson.get("platform")
    sku = rjson.get("sku")
    debugParams = rjson.get("debugParemeters")

    req = requests.post(
        url = f"https://graph.oculus.com/consume_entitlement?nonce={nonce}&user_id={userId}&sku={sku}&access_token={settings.ApiKey}",
        headers = {
            "content-type": "application/json"
        }
    )

    if bool(req.json().get("success")):
        return jsonify({"result":True})
    else:
        return jsonify({"error":True})

@app.route("/api/ReturnMyOculusHashV2")
def returnmyoculushashv2():
    return ReturnFunctionJson(request.get_json(), "ReturnMyOculusHash")

@app.route("/api/ReturnCurrentVersionV2", methods = ["POST", "GET"])
def returncurrentversionv2():
    return ReturnFunctionJson(request.get_json(), "ReturnCurrentVersion")

@app.route("/api/TryDistributeCurrencyV2", methods = ["POST", "GET"])
def trydistributecurrencyv2():
    return ReturnFunctionJson(request.get_json(), "TryDistributeCurrency")

@app.route("/api/BroadCastMyRoomV2", methods = ["POST", "GET"])
def broadcastmyroomv2():
    return ReturnFunctionJson(request.get_json(), "BroadCastMyRoom", request.get_json()["FunctionParameter"])

@app.route("/api/ShouldUserAutomutePlayer", methods = ["POST", "GET"])
def shoulduserautomuteplayer():
    return jsonify(muteCache)

@app.route("/api/photon/authenticate", methods = ["POST","GET"])
def photonauthenticaet():
    if request.method.upper() == "GET":
        userId = request.args.get("username")
        token = request.args.get("token")

        req = requests.post(
            url = f"https://{settings.TitleId}.playfabapi.com/Server/GetUserAccountInfo",
            json = {
                "PlayFabId": userId
            },
            headers = settings.GetAuthHeaders()
        )

        if req.status_code == 200:
            nickName : str = req.json().get("UserInfo").get("UserAccountInfo").get("Username")
            if nickName == "" or nickName is None:
                nickName = None

            return jsonify({'resultCode': 1, 'message': f'Authenticated user {userId.lower()} title {settings.TitleId.lower()}', 'userId': f'{userId.upper()}', 'nickname': nickName})

        else:
            if len(userId) != 16 or userId is None:
                return jsonify({'resultCode': 2, 'message': 'Invalid token', 'userId': None, 'nickname': None})
            elif token is None:
                return jsonify({'resultCode': 3, 'message': 'Failed to parse token from request', 'userId': None, 'nickname': None})
            else:
                return jsonify({'resultCode': 0, 'message': "Something went wrong", 'userId': None, 'nickname': None})
    elif request.method.upper() == "POST":

        authPostData : dict = request.get_json()

        userId = request.args.get("username")
        token = request.args.get("token")

        req = requests.post(
            url = f"https://{settings.TitleId}.playfabapi.com/Server/GetUserAccountInfo",
            json = {
                "PlayFabId": userId
            },
            headers = settings.GetAuthHeaders()
        )

        if req.status_code == 200:
            nickName : str = req.json().get("UserInfo").get("UserAccountInfo").get("Username")
            if nickName == "" or nickName is None:
                nickName = None

            return jsonify({'resultCode': 1, 'message': f'Authenticated user {userId.lower()} title {settings.TitleId.lower()}', 'userId': f'{userId.upper()}', 'nickname': nickName})

        else:
            if len(userId) != 16 or userId is None:
                return jsonify({'resultCode': 2, 'message': 'Invalid token', 'userId': None, 'nickname': None})
            elif token is None:
                return jsonify({'resultCode': 3, 'message': 'Failed to parse token from request', 'userId': None, 'nickname': None})
            else:
                successJson : dict = {'resultCode': 0, 'message': "Something went wrong", 'userId': None, 'nickname': None}

                for key, value in authPostData.items():
                    successJson[key] = value

                return jsonify(successJson)

    else:
        return jsonify({"Message": "Use a POST or GET Method instead of " + request.method.upper()})

if __name__ == "__main__":

    app.run("0.0.0.0", 8080)
