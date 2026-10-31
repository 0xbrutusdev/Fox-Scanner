const WBNB = "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c";
const GT = "https://api.geckoterminal.com/api/v2/networks/bsc";
const FOUR = "https://four.meme/meme-api/v1/public/token/search";
const FOUR_IMG = "https://static.four.meme";
const DS = "https://api.dexscreener.com/latest/dex/search";

const memory = new Map();

function num(value) {
  const n = typeof value === "number" ? value : Number.parseFloat(value);
  return Number.isFinite(n) ? n : null;
}

function httpsImage(img) {
  return typeof img === "string" && img.startsWith("https://") ? img : "";
}

function fourImage(img) {
  if (typeof img !== "string" || !img) return "";
  if (img.startsWith("https://")) return img;
  if (img.startsWith("/")) return FOUR_IMG + img;
  if (img.startsWith("market/")) return FOUR_IMG + "/" + img;
  return "";
}

function unixSeconds(value) {
  if (typeof value === "string" && /^\d+$/.test(value)) value = Number(value);
  if (typeof value !== "number" || value <= 0) return null;
  return value > 1e12 ? Math.floor(value / 1000) : Math.floor(value);
}

function includedTokens(data) {
  const included = new Map();
  for (const item of data?.included || []) {
    if (item?.type === "token" && item.id) included.set(item.id, item.attributes || {});
  }
  return included;
}

function tokenAddress(pool, included) {
  const rel = pool?.relationships?.base_token?.data || {};
  const tid = rel.id || "";
  const attrs = included.get(tid) || {};
  let addr = String(attrs.address || "").trim();
  if (!addr && tid.includes("_")) addr = tid.split("_").slice(1).join("_");
  return { addr, attrs };
}

function parseTrending(data, limit = 20) {
  const included = includedTokens(data);
  const out = [];
  const seen = new Set();
  for (const pool of data?.data || []) {
    const { addr, attrs } = tokenAddress(pool, included);
    const key = addr.toLowerCase();
    if (!addr || seen.has(key)) continue;
    seen.add(key);
    const pa = pool.attributes || {};
    out.push({
      token: addr,
      symbol: attrs.symbol || "",
      name: attrs.name || "",
      image: httpsImage(attrs.image_url),
      mcap_usd: num(pa.market_cap_usd) || num(pa.fdv_usd),
      price_usd: num(pa.base_token_price_usd),
    });
    if (out.length >= limit) break;
  }
  return out;
}

function parseNewPools(data, limit = 20) {
  const included = includedTokens(data);
  const by = new Map();
  for (const pool of data?.data || []) {
    const { addr, attrs } = tokenAddress(pool, included);
    const key = addr.toLowerCase();
    if (!addr || key === WBNB) continue;
    const created = Date.parse(pool.attributes?.pool_created_at || pool.attributes?.created_at || "") / 1000;
    const stamp = Number.isFinite(created) ? Math.floor(created) : null;
    const prev = by.get(key);
    if (prev && (prev.created || 0) >= (stamp || 0)) continue;
    by.set(key, {
      token: addr,
      symbol: attrs.symbol || "",
      name: attrs.name || "",
      image: httpsImage(attrs.image_url),
      created: stamp,
    });
  }
  return [...by.values()].sort((a, b) => (b.created || 0) - (a.created || 0)).slice(0, limit);
}

function parseFour(data, limit = 30) {
  let rows = data?.data ?? data;
  if (rows && !Array.isArray(rows) && typeof rows === "object") {
    rows = Object.values(rows).find((value) => Array.isArray(value)) || [];
  }
  if (!Array.isArray(rows)) return [];
  const by = new Map();
  for (const row of rows) {
    if (!row || typeof row !== "object") continue;
    const addr = String(row.tokenAddress || row.address || "").trim();
    const key = addr.toLowerCase();
    if (!key.startsWith("0x") || key.length !== 42 || key === WBNB) continue;
    const created = unixSeconds(row.createDate || row.launchTime);
    const next = {
      token: addr,
      symbol: row.shortName || "",
      name: row.name || "",
      image: fourImage(row.img || row.image || ""),
      created,
    };
    const prev = by.get(key);
    if (!prev || (created || 0) > (prev.created || 0)) {
      if (prev) {
        next.image = next.image || prev.image;
        next.symbol = next.symbol || prev.symbol;
        next.name = next.name || prev.name;
      }
      by.set(key, next);
    } else if (!prev.image && next.image) {
      prev.image = next.image;
    }
  }
  return [...by.values()].sort((a, b) => (b.created || 0) - (a.created || 0)).slice(0, limit);
}

function mergeNew(rows, limit = 20) {
  const by = new Map();
  for (const row of rows) {
    const addr = String(row?.token || "").trim();
    const key = addr.toLowerCase();
    if (!key.startsWith("0x") || key.length !== 42 || key === WBNB) continue;
    const created = typeof row.created === "number" && row.created > 0 ? Math.floor(row.created) : null;
    const image = httpsImage(row.image);
    const prev = by.get(key);
    if (!prev) {
      by.set(key, { token: addr, symbol: row.symbol || "", name: row.name || "", image, created });
      continue;
    }
    if (created && (!prev.created || created < prev.created)) prev.created = created;
    if (!prev.image && image) prev.image = image;
    if (!prev.symbol && row.symbol) prev.symbol = row.symbol;
    if (!prev.name && row.name) prev.name = row.name;
  }
  return [...by.values()].sort((a, b) => (b.created || 0) - (a.created || 0)).slice(0, limit);
}

function parseSearch(data, limit = 20) {
  const pairs = [...(data?.pairs || [])].sort((a, b) => (num(b?.liquidity?.usd) || 0) - (num(a?.liquidity?.usd) || 0));
  const out = [];
  const seen = new Set();
  for (const pair of pairs) {
    if (pair?.chainId !== "bsc") continue;
    const base = pair.baseToken || {};
    const addr = String(base.address || "").trim();
    const key = addr.toLowerCase();
    if (!addr || seen.has(key)) continue;
    seen.add(key);
    out.push({
      token: addr,
      symbol: base.symbol || "",
      name: base.name || "",
      image: httpsImage(pair.info?.imageUrl),
      mcap_usd: num(pair.marketCap) || num(pair.fdv),
      price_usd: num(pair.priceUsd),
    });
    if (out.length >= limit) break;
  }
  return out;
}

async function fetchJSON(url, options = {}) {
  let response;
  for (let attempt = 0; attempt < 2; attempt++) {
    response = await fetch(url, {
      ...options,
      headers: {
        accept: "application/json",
        "user-agent": "foxscanner/0.1",
        ...(options.headers || {}),
      },
    });
    if (response.status !== 429 || attempt === 1) break;
    await new Promise((resolve) => setTimeout(resolve, 800));
  }
  if (!response.ok) throw new Error(String(response.status));
  return response.json();
}

async function remember(key, seconds, load) {
  const hit = memory.get(key);
  if (hit && Date.now() - hit.at < seconds * 1000) return hit.value;
  const value = await load();
  if (Array.isArray(value) && value.length) memory.set(key, { at: Date.now(), value });
  return value;
}

async function trending() {
  return remember("trending", 60, async () => {
    const data = await fetchJSON(`${GT}/trending_pools?include=base_token&page=1`);
    return parseTrending(data, 20);
  });
}

async function newTokens() {
  return remember("new", 15, async () => {
    const [four, pools] = await Promise.all([
      fetchJSON(FOUR, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ type: "NEW", pageIndex: 1, pageSize: 30, status: "ALL", sort: "DESC" }),
      }).then((data) => parseFour(data, 30)).catch(() => []),
      fetchJSON(`${GT}/new_pools?include=base_token&page=1`).then((data) => parseNewPools(data, 20)).catch(() => []),
    ]);
    return mergeNew([...four, ...pools], 20).slice(0, 7);
  });
}

async function search(query) {
  const q = query.trim().replace(/\s+/g, " ");
  if (q.length < 2 || q.length > 80) return [];
  return remember(`search:${q.toLowerCase()}`, 30, async () => {
    const data = await fetchJSON(`${DS}?q=${encodeURIComponent(q)}`);
    return parseSearch(data, 20);
  });
}

function feed(body, seconds) {
  return Response.json(body, { headers: { "cache-control": `public, max-age=${seconds}` } });
}

const EVM = /^0x[0-9a-fA-F]{40}$/;
const JOB_TTL = 180;
const CONFIG = {
  chains: { bnb: true, robinhood: false, solana: false },
  default_chain: "bnb",
  chain_names: { bnb: "BNB Chain", robinhood: "Robinhood Chain", solana: "Solana" },
  explorers: {
    bnb: "https://bscscan.com",
    robinhood: "https://robinhoodchain.blockscout.com",
    solana: "https://solscan.io",
  },
  solana: false,
  alerts: false,
  flap: false,
  flap_bnb: true,
  genius_bnb: true,
  bankr: false,
  replay: false,
  trade: {
    bnb: "https://four.meme/token/{address}",
    robinhood: "https://axiom.trade/t/{address}/@foxscan?chain=robinhood",
    solana: "https://axiom.trade/t/{address}/@foxscan",
  },
};

function fraction(value) {
  const n = num(value);
  if (n == null) return null;
  return n > 1 ? n / 100 : n;
}

function ageHours(stamp) {
  const ms = typeof stamp === "number" ? stamp : Date.parse(stamp || "");
  if (!Number.isFinite(ms) || ms <= 0) return null;
  const hours = (Date.now() - ms) / 3600000;
  return hours > 0 ? Math.round(hours * 10) / 10 : null;
}

function jobRequest(origin, id) {
  return new Request(`${origin}/__job/${id}`);
}

async function saveJob(origin, id, payload) {
  memory.set(`job:${id}`, { at: Date.now(), value: payload });
  try {
    await caches.default.put(
      jobRequest(origin, id),
      new Response(JSON.stringify(payload), {
        headers: { "content-type": "application/json", "cache-control": `public, max-age=${JOB_TTL}` },
      }),
    );
  } catch (error) {
    console.log(`job cache: ${error instanceof Error ? error.message : "failed"}`);
  }
}

async function loadJob(origin, id) {
  if (!id) return null;
  const hit = memory.get(`job:${id}`);
  if (hit && Date.now() - hit.at < JOB_TTL * 1000) return hit.value;
  try {
    const cached = await caches.default.match(jobRequest(origin, id));
    if (!cached) return null;
    const payload = await cached.json();
    memory.set(`job:${id}`, { at: Date.now(), value: payload });
    return payload;
  } catch (error) {
    console.log(`job read: ${error instanceof Error ? error.message : "failed"}`);
    return null;
  }
}

function bestPool(data) {
  let pool = null;
  let created = null;
  for (const row of data?.data || []) {
    const attrs = row?.attributes || {};
    const at = Date.parse(attrs.pool_created_at || "");
    if (!pool) pool = attrs.address || null;
    if (Number.isFinite(at) && (created == null || at < created)) {
      created = at;
      if (attrs.address) pool = attrs.address;
    }
  }
  return { pool, age_h: ageHours(created) };
}

function dexPair(data, token) {
  const pairs = (data?.pairs || []).filter(
    (pair) => pair?.chainId === "bsc" && String(pair.baseToken?.address || "").toLowerCase() === token,
  );
  pairs.sort((a, b) => (num(b?.liquidity?.usd) || 0) - (num(a?.liquidity?.usd) || 0));
  return pairs[0] || null;
}

async function snapshot(address) {
  const token = address.toLowerCase();
  const started = Date.now();
  const [gt, pools, security, dex] = await Promise.all([
    fetchJSON(`${GT}/tokens/${token}`).catch(() => null),
    fetchJSON(`${GT}/tokens/${token}/pools?page=1`).catch(() => null),
    fetchJSON(`https://api.gopluslabs.io/api/v1/token_security/56?contract_addresses=${token}`).catch(() => null),
    fetchJSON(`https://api.dexscreener.com/latest/dex/tokens/${token}`).catch(() => null),
  ]);
  const attrs = gt?.data?.attributes || {};
  const pair = dexPair(dex, token);
  const market = bestPool(pools);
  if (market.pool) memory.set(`pool:${token}`, { at: Date.now(), value: market.pool });
  const row = security?.result?.[token] || {};
  const creator = EVM.test(row.creator_address || "") ? row.creator_address.toLowerCase() : null;
  const holders = (Array.isArray(row.holders) ? row.holders : [])
    .map((holder) => {
      const wallet = String(holder?.address || "").trim();
      const share = fraction(holder?.percent);
      return {
        wallet,
        share,
        share_supply: share,
        signals: { is_deployer: !!(creator && wallet.toLowerCase() === creator) },
      };
    })
    .filter((holder) => EVM.test(holder.wallet))
    .sort((a, b) => (b.share || 0) - (a.share || 0))
    .slice(0, 10);
  const volume = attrs.volume_usd && typeof attrs.volume_usd === "object" ? attrs.volume_usd.h24 : null;
  const header = {
    name: attrs.name || pair?.baseToken?.name || row.token_name || null,
    ticker: attrs.symbol || pair?.baseToken?.symbol || row.token_symbol || null,
    price_usd: num(attrs.price_usd) || num(pair?.priceUsd),
    mcap_usd: num(attrs.market_cap_usd) || num(pair?.marketCap),
    fdv_usd: num(attrs.fdv_usd) || num(pair?.fdv),
    liquidity_usd: num(attrs.total_reserve_in_usd) || num(pair?.liquidity?.usd),
    vol24h_usd: num(volume) || num(pair?.volume?.h24),
    age_h: market.age_h || ageHours(pair?.pairCreatedAt),
  };
  const headline = "Market snapshot. Holder wallets were not traced.";
  return {
    token: address,
    chain: "bnb",
    header,
    launch: creator ? { deployer: creator } : {},
    score: null,
    band: null,
    headline,
    reason: "Top holders are a public list. This host does not read transfer history, so there is no holder score.",
    gates: ["No holder score: transfer history is not read on this host."],
    parts: {},
    metrics: {},
    notes: [],
    holders,
    holders_total: num(row.holder_count) == null ? null : Math.round(num(row.holder_count)),
    operators: [],
    links: [],
    packs: [],
    unread: [],
    rug: null,
    limited: true,
    partial_scan: {
      message: "Top holders only. Wallet links, snipers, and fresh-wallet checks need the full scanner.",
    },
    market_source: attrs.price_usd ? "gt" : pair ? "dexscreener" : null,
    market_pool: market.pool,
    elapsed_s: Math.round((Date.now() - started) / 100) / 10,
  };
}

async function chartPool(token) {
  const hit = memory.get(`pool:${token}`);
  if (hit && Date.now() - hit.at < 60000) return hit.value || null;
  const data = await fetchJSON(`${GT}/tokens/${token}/pools?page=1`).catch(() => null);
  const pool = bestPool(data).pool;
  memory.set(`pool:${token}`, { at: Date.now(), value: pool });
  return pool;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health") {
      return Response.json({ ok: true, scanner: false, feeds: true });
    }
    if (url.pathname === "/api/stats") {
      return Response.json({ tokens_scanned: 0, danger: 0 });
    }
    if (url.pathname === "/api/config") {
      return Response.json(CONFIG);
    }
    if (url.pathname === "/api/scan" && request.method === "POST") {
      let body = {};
      try {
        body = await request.json();
      } catch {
        return Response.json({ error: "bad json" }, { status: 400 });
      }
      const token = String(body?.token || "").trim();
      if (!EVM.test(token)) {
        return Response.json({ error: "not a BNB token address" }, { status: 400 });
      }
      const result = await snapshot(token);
      const id = crypto.randomUUID();
      await saveJob(url.origin, id, {
        events: [{ type: "done", limited: true, headline: result.headline }],
        result,
      });
      return Response.json({ job: id });
    }
    if (url.pathname === "/api/events" || url.pathname === "/api/result") {
      const job = await loadJob(url.origin, url.searchParams.get("job") || "");
      if (!job) return Response.json({ error: "not found" }, { status: 404 });
      if (url.pathname === "/api/result") return Response.json({ done: true, result: job.result });
      const after = Math.max(0, Number(url.searchParams.get("after")) || 0);
      return Response.json({ events: job.events.slice(after), done: true });
    }
    if (url.pathname === "/api/chart") {
      const token = String(url.searchParams.get("token") || "").trim().toLowerCase();
      const pool = EVM.test(token) ? await chartPool(token) : null;
      return Response.json({ candles: [], pool });
    }
    if (url.pathname === "/api/early") {
      return Response.json({
        available: false,
        reason: "Early buyers need transfer history, which this host does not read.",
      });
    }
    try {
      if (url.pathname === "/api/trending") {
        return feed({ chain: "bnb", items: await trending() }, 60);
      }
      if (url.pathname === "/api/tokens/new") {
        return feed({ chain: "bnb", items: await newTokens() }, 15);
      }
      if (url.pathname === "/api/search") {
        return feed({ chain: "bnb", items: await search(url.searchParams.get("q") || "") }, 30);
      }
    } catch (error) {
      console.log(`${url.pathname}: ${error instanceof Error ? error.message : "failed"}`);
      return feed({ chain: "bnb", items: [] }, 15);
    }
    if (url.pathname === "/api/recent" || url.pathname === "/api/radar" || url.pathname === "/api/tokens/viewed") {
      return feed({ items: [] }, 15);
    }
    if (url.pathname.startsWith("/api/")) {
      return Response.json(
        {
          error: "unavailable",
          message: "This endpoint needs the Python service. This free host only serves the site and market lists.",
        },
        { status: 503 },
      );
    }
    return env.ASSETS.fetch(request);
  },
};
