/*
 Fan-game backend (Node.js 18+): PlayFab + Photon auth, polls, cosmetics.

 Environment variables:
   TITLE_ID          PlayFab title id
   PLAYFAB_SECRET    PlayFab secret key (use a NEW one, rotate the old one)
   DISCORD_WEBHOOK   optional, general log webhook
   PHOTON_WEBHOOK    optional, photon auth log webhook
   CATALOG_VERSION   optional, default "Cosmetics"
   CURRENCY_CODE     optional, default "SR"
   PORT              optional, default 8080
*/
const express = require("express");
const crypto = require("crypto");

const TITLE_ID = process.env.TITLE_ID || "7410A";
const SECRET_KEY = process.env.PLAYFAB_SECRET || "YQTCJTHXITO5I1XCX7RSZA3WMC6R16J8RKEY5MH11EQ4DSZPGI";
const DISCORD_WEBHOOK = process.env.DISCORD_WEBHOOK || "https://discord.com/api/webhooks/1566549583650095124/vMl_vwS6eZ7E1OdKvhw-tzlcKlhsXd2e3L3Xz478tFPuJDGyptwlcgR-3SHZdc2JSV0H";
const PHOTON_WEBHOOK = process.env.PHOTON_WEBHOOK || "https://discord.com/api/webhooks/1567328180589822123/gvYn4gRdC3bJYQypCzYpw8nnyQ3y3PXqDLChP69rsQyV3EZEvp_J-wrDyLihKFOsjL2R";
const CATALOG_VERSION = process.env.CATALOG_VERSION || "DLC";
const CURRENCY_CODE = process.env.CURRENCY_CODE || "SR";
const PORT = process.env.PORT || 8080;

if (!TITLE_ID || !SECRET_KEY) {
  console.error("Set TITLE_ID and PLAYFAB_SECRET environment variables.");
  process.exit(1);
}

const PF = `https://${TITLE_ID}.playfabapi.com`;
const app = express();
app.use(express.json());

// ------------------------------------------------------------ helpers
async function pf(path, body = {}) {
  const r = await fetch(PF + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-SecretKey": SECRET_KEY },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(8000),
  });
  if (!r.ok) throw new Error(`PlayFab ${path} -> ${r.status}`);
  return (await r.json()).data || {};
}

// fire-and-forget so logging never slows a player down
function webhook(url, payload) {
  if (!url) return;
  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(5000),
  }).catch((e) => console.log("[WEBHOOK ERROR]", e.message));
}

function log(message, level = "INFO") {
  console.log(`[${level}] ${message}`);
  webhook(DISCORD_WEBHOOK, {
    embeds: [{ title: level, description: message, color: level === "INFO" ? 3066993 : 15158332 }],
  });
}

async function validateTicket(ticket) {
  if (!ticket) return null;
  try {
    const d = await pf("/Server/AuthenticateSessionTicket", { SessionTicket: ticket });
    return d.UserInfo.PlayFabId;
  } catch (e) {
    console.log("[TICKET INVALID]", e.message);
    return null;
  }
}

// ------------------------------------------------------------ nonces
const nonces = new Map();
const NONCE_TTL = 300_000;

function generateNonce() {
  const n = crypto.randomUUID().replace(/-/g, "");
  nonces.set(n, Date.now());
  return n;
}
function consumeNonce(n) {
  const t = nonces.get(n);
  nonces.delete(n);
  return t !== undefined && Date.now() - t < NONCE_TTL;
}
setInterval(() => {
  const now = Date.now();
  for (const [k, t] of nonces) if (now - t > NONCE_TTL) nonces.delete(k);
}, 60_000).unref();

app.all("/", (req, res) => res.send("Backend is running :)"));

app.get("/api/GenerateNonce", (req, res) => res.json({ nonce: generateNonce() }));

// ------------------------------------------------------------ login
app.post("/api/PlayFabAuthentication", async (req, res) => {
  const { CustomId: customId, Nonce: nonce, OculusAccessToken: oculusToken, Platform: platform } =
    req.body || {};

  if (!customId || !nonce || !oculusToken || !platform)
    return res.status(400).json({ error: "Missing parameters" });
  if (!consumeNonce(nonce)) return res.status(403).json({ error: "Invalid nonce" });
  if (String(platform).toLowerCase() !== "quest")
    return res.status(403).json({ error: "Platform not allowed" });

  let orgScopedId;
  try {
    const ov = await fetch(
      `https://graph.oculus.com/me?access_token=${encodeURIComponent(oculusToken)}`,
      { signal: AbortSignal.timeout(8000) }
    );
    if (!ov.ok) throw new Error(`status ${ov.status}`);
    orgScopedId = (await ov.json()).id;
  } catch (e) {
    log(`Oculus verification failed for ${customId}: ${e.message}`, "ERROR");
    return res.status(403).json({ error: "Oculus token verification failed" });
  }

  let login;
  try {
    login = await pf("/Server/LoginWithServerCustomId", {
      ServerCustomId: customId,
      CreateAccount: true,
    });
  } catch (e) {
    log(`PlayFab login failed for ${customId}: ${e.message}`, "ERROR");
    return res.status(403).json({ error: "PlayFab login failed" });
  }

  const sessionTicket = login.SessionTicket;

  // link in the background so login responds faster
  fetch(`${PF}/Client/LinkCustomID`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Authorization": sessionTicket },
    body: JSON.stringify({ CustomId: orgScopedId, ForceLink: true }),
    signal: AbortSignal.timeout(8000),
  }).catch((e) => console.log("[LINK ERROR]", e.message));

  log(`Login OK: ${customId} / ${orgScopedId}`);

  // Full ticket must be returned (old code truncated it, which breaks the client)
  res.json({
    PlayFabId: login.PlayFabId,
    SessionTicket: sessionTicket,
    EntityToken: login.EntityToken.EntityToken,
    NonceUsed: nonce,
    OrgScopedId: orgScopedId,
  });
});

// ------------------------------------------------------------ photon
app.all("/api/v3/Photon", async (req, res) => {
  const j = Object.keys(req.body || {}).length ? req.body : req.query;
  const { Ticket, Nonce, AppId, Platform, CustomId, OrgScopedId, AppVersion = "Unknown" } = j;

  // Photon custom auth: ResultCode 1 = success, 2 = failed
  const fail = (msg) =>
    res.status(403).json({ ResultCode: 2, Message: msg, status: "error", message: msg });

  if (AppId !== TITLE_ID) return fail("Invalid App ID");
  if (Platform !== "Android") return fail("Invalid platform");
  if (!Nonce || !consumeNonce(Nonce)) return fail("Invalid nonce");
  if (!CustomId || !(CustomId.startsWith("OC") || CustomId.startsWith("PI")))
    return fail("Invalid Custom ID");

  const playfabId = await validateTicket(Ticket);
  if (!playfabId) return fail("Invalid session ticket");

  webhook(PHOTON_WEBHOOK, {
    username: "Photon AuthBot",
    embeds: [
      {
        title: "Photon Auth",
        color: 0x00ff99,
        fields: [
          { name: "CustomId", value: String(CustomId), inline: true },
          { name: "AppVersion", value: String(AppVersion), inline: true },
          { name: "PlayFabId", value: playfabId, inline: true },
        ],
      },
    ],
  });

  res.json({
    ResultCode: 1,
    Message: "Authenticated",
    UserId: playfabId,
    status: "success",
    message: "Session validated",
  });
});

// ------------------------------------------------------------ title data (cached 60s)
let tdCache = { data: null, t: 0 };
app.all("/api/td", async (req, res) => {
  if (tdCache.data && Date.now() - tdCache.t < 60_000) return res.json(tdCache.data);
  try {
    const d = (await pf("/Server/GetTitleData")).Data || {};
    tdCache = { data: d, t: Date.now() };
    res.json(d);
  } catch {
    res.json(tdCache.data || {});
  }
});

// ------------------------------------------------------------ cosmetics
let catalogCache = { items: null, t: 0 };
async function getCatalog() {
  if (!catalogCache.items || Date.now() - catalogCache.t > 120_000) {
    const d = await pf("/Server/GetCatalogItems", { CatalogVersion: CATALOG_VERSION });
    const items = {};
    for (const i of d.Catalog || []) items[i.ItemId] = i;
    catalogCache = { items, t: Date.now() };
  }
  return catalogCache.items;
}

// Body: { PlayFabTicket }
app.post("/api/GetCosmetics", async (req, res) => {
  const pid = await validateTicket((req.body || {}).PlayFabTicket);
  if (!pid) return res.status(403).json({ Message: "Invalid ticket" });
  try {
    const inv = await pf("/Server/GetUserInventory", { PlayFabId: pid });
    res.json({ Inventory: inv.Inventory || [], VirtualCurrency: inv.VirtualCurrency || {} });
  } catch (e) {
    res.status(502).json({ Message: `PlayFab error: ${e.message}` });
  }
});

// Body: { PlayFabTicket, ItemId }
app.post("/api/PurchaseCosmetic", async (req, res) => {
  const { PlayFabTicket, ItemId } = req.body || {};
  const pid = await validateTicket(PlayFabTicket);
  if (!pid) return res.status(403).json({ Message: "Invalid ticket" });
  if (!ItemId) return res.status(400).json({ Message: "Missing ItemId" });

  try {
    const item = (await getCatalog())[ItemId];
    if (!item) return res.status(404).json({ Message: "Item not found" });

    const price = (item.VirtualCurrencyPrices || {})[CURRENCY_CODE];
    if (price === undefined)
      return res.status(400).json({ Message: "Item not purchasable with this currency" });

    const inv = await pf("/Server/GetUserInventory", { PlayFabId: pid });
    if ((inv.Inventory || []).some((i) => i.ItemId === ItemId))
      return res.status(409).json({ Message: "Already owned" });
    if (((inv.VirtualCurrency || {})[CURRENCY_CODE] || 0) < price)
      return res.status(402).json({ Message: "Not enough currency" });

    await pf("/Server/SubtractUserVirtualCurrency", {
      PlayFabId: pid,
      VirtualCurrency: CURRENCY_CODE,
      Amount: price,
    });
    try {
      await pf("/Server/GrantItemsToUser", {
        PlayFabId: pid,
        CatalogVersion: CATALOG_VERSION,
        ItemIds: [ItemId],
      });
    } catch (e) {
      // refund if the grant failed
      await pf("/Server/AddUserVirtualCurrency", {
        PlayFabId: pid,
        VirtualCurrency: CURRENCY_CODE,
        Amount: price,
      });
      throw e;
    }
    res.json({ Message: "Purchased", ItemId });
  } catch (e) {
    res.status(502).json({ Message: `PlayFab error: ${e.message}` });
  }
});

// ------------------------------------------------------------ polls
const polls = [
  {
    PollId: 2,
    Question: "ARE YOU IN THE DISCORD YET?",
    VoteOptions: ["YES", "NO"],
    VoteCount: [0, 0],
    PredictionCount: [0, 0],
    StartTime: new Date().toISOString().slice(0, 10),
    EndTime: "2030-01-01T17:00:00",
    isActive: true,
  },
];

app.all("/api/FetchPoll", (req, res) => res.json(polls));

app.post("/api/Vote", (req, res) => {
  const { PollId, OptionIndex, IsPrediction } = req.body || {};
  const poll = polls.find((p) => p.PollId === PollId);
  if (!poll) return res.status(404).json({ Message: "Poll not found" });
  if (!Number.isInteger(OptionIndex) || OptionIndex < 0 || OptionIndex >= poll.VoteOptions.length)
    return res.status(400).json({ Message: "Bad option" });

  poll[IsPrediction ? "PredictionCount" : "VoteCount"][OptionIndex]++;
  res.json({ Message: "Vote counted" });
});

// ------------------------------------------------------------ misc
const playfabCache = {};
const nameSaves = {};

app.post("/api/CachePlayFabId", (req, res) => {
  const j = req.body;
  if (!j || !j.PlayFabId) return res.status(400).json({ Message: "Missing PlayFabId parameter" });
  playfabCache[j.PlayFabId] = j;
  res.json({ Message: "Success" });
});

app.post("/api/CheckForBadName", (req, res) => {
  const arg = (req.body || {}).FunctionArgument || {};
  if (!("name" in arg) || !("forRoom" in arg))
    return res.status(400).json({ error: "Invalid input format" });
  nameSaves[arg.name] = arg.forRoom;
  res.json({ name: arg.name, forRoom: arg.forRoom });
});

app.listen(PORT, () => console.log(`Listening on ${PORT}`));
