<div align="center">

<img src="frontend/static/img/logo.png" width="96" alt="FoxScanner">

# FoxScanner

**Spot the rug before it hits.**

Multichain meme token checker. BNB Chain (four.meme) first; Solana and Robinhood Chain next.

[![chains](https://img.shields.io/badge/live-BNB_Chain-FFD800?style=flat-square\&labelColor=0B0B0B)](#supported-chains-and-launchpads)
![launchpads](https://img.shields.io/badge/launchpad-four.meme-FFD800?style=flat-square\&labelColor=0B0B0B)
![next](https://img.shields.io/badge/next-Solana_%C2%B7_Robinhood-2A2A2A?style=flat-square\&labelColor=0B0B0B)
![read-only](https://img.shields.io/badge/read--only-no_keys-FFD800?style=flat-square\&labelColor=0B0B0B)
![python](https://img.shields.io/badge/python-3.12-2A2A2A?style=flat-square\&labelColor=0B0B0B)
![runtime deps](https://img.shields.io/badge/runtime_deps-0-FFD800?style=flat-square\&labelColor=0B0B0B)
[![license](https://img.shields.io/badge/license-MIT-2A2A2A?style=flat-square\&labelColor=0B0B0B)](LICENSE)

</div>

## What is FoxScanner?

**FoxScanner is an on-chain token checker that finds hidden wallet concentration, coordinated buying and suspicious holder behaviour in seconds.**

Instead of only showing how many holders a token has, FoxScanner answers the question that actually matters:

> **How many real participants are behind those wallets?**

A token can show hundreds of holders while a large part of its supply is controlled by one person, one group, or a network of connected wallets. FoxScanner reads the token's on-chain activity, analyses its top holders, follows transfers and trades, links related wallets and turns the result into a simple **0-100 score**.

### The core idea

Paste a token address. FoxScanner detects the launchpad and returns a verdict such as:

> **20 wallets -> 4 operators, biggest holds 38% of float (9% of supply), could move price -45% if sold**

## Supported chains and launchpads

| Chain | Status | Launchpads | Explorer |
| --- | --- | --- | --- |
| **BNB Chain** | live | **four.meme** (bonding curve, then PancakeSwap after graduation) | BscScan |
| **Solana** | coming soon (`SOLANA_ENABLED`) | pump.fun (bonding curve, PumpSwap and Raydium after migration) | Solscan |
| **Robinhood Chain** | coming soon (`ROBINHOOD_ENABLED`) | Pons V2, Flap, Bankr | Robinhood explorer |

For **four.meme** tokens the result also shows the bonding curve progress, a price read from the curve while GeckoTerminal doesn't list the token yet, and early buyers through the curve and the pair. A `0x...` address goes to BNB Chain by default (`DEFAULT_EVM_CHAIN`); `?chain=` picks a chain explicitly.

## What FoxScanner checks

The token's holder picture is rebuilt from on-chain data. Bonding curves, liquidity pools, lockers, routers and other infrastructure are excluded, and ownership is measured against the **real circulating float**, not raw supply locked in a curve or pool.

Each top holder is analysed for:

* **Bought vs received**: did the wallet buy on the market, or receive tokens by transfer? Buys are recognised at the transaction level, even through trading bots and routers.
* **Virgin wallets**: wallets that never traded a token before this one.
* **History depth**: how much trading activity a wallet had before entry.
* **Snipers**: wallets entering in the first seconds after launch, and how much they still hold.
* **Deployer**: what the creator still holds.
* **Locked tokens**: tokens sent to a known locker are shown as locked, not as moved.

The biggest holders are read first. If a wallet's entry cannot be read reliably, it is marked **unread** and left out of the signals instead of being guessed.

### How wallets are linked

**Proven links**: wallets in the same buy transaction, tokens distributed from the same ordinary wallet, and direct transfers between holders. Wallets with proven links are merged into one **operator**.

**Behavioural packs**: fresh wallets that enter together, buy near-identical amounts and have no history before the launch. Packs are signals, not proof, so they weigh less than proven links.

Exchanges, bridges, routers and other high-traffic addresses are never used to link wallets.

## Verdict

All signals are combined into a score from **0 to 100**, where **100 is the cleanest distribution**.

| Signal | What it measures |
| --- | --- |
| **Operator** | How far the price could fall if the largest operator sold everything into the liquidity |
| **Virgin** | The share of virgin wallets among the top holders |
| **Transfer** | How much of the float was received rather than bought |
| **Sniper** | How much float early snipers still hold |
| **Concentration** | How much of the float sits with the top holders |

Hard rules cover cases a weighted score would get wrong:

* an operator of **linked wallets** able to crash the price by 50% or more forces `DANGER`, and so does a deployer, fresh wallet or transfer-funded holder that can;
* a **single independent holder** with a trading history caps the result at `RISKY` (*one holder could move price -X% (thin liquidity)*);
* an unread holder, multi-wallet operators, suspicious packs or thin liquidity cap the result at `RISKY`;
* too few holders returns `TOO EARLY`; large, old, liquid tokens return `TOO ESTABLISHED`.

## Price chart and probably rug

Every result has a price chart from GeckoTerminal, with DexScreener as a fallback; it loads after the verdict so it never slows a scan down.

When the verdict is `DANGER` because of linked wallets, fresh wallets or transfer supply, FoxScanner adds a **probably rug** level: how far the price would fall if all of that suspicious supply were sold into the current liquidity. At 40% or more the chart shows a red dashed arrow labelled `probably rug -X%`, with the reasons below. It is not a prediction of when a dump happens, only how much damage the suspicious holders could do right now.

## Early buyers

The first 20 buyers after launch: how many seconds after launch each one bought, how much, and what they did since (holding, added, sold part, sold all, moved, locked or burned). Early buyers that sent tokens to the same wallet are grouped.

## Built for speed and traffic

FoxScanner reads wallets in parallel under a hard time budget and streams every step of the scan to the page live. Under load it protects itself: a scan queue with *Scanner is busy, try again in a few seconds*, a per-address limit on new scans, bounded caches and a memory guard.

* **Python 3.12**, **standard library only**: zero runtime dependencies.
* **Backend** in `backend/`: the `foxscanner` package with one adapter per chain and launchpad (`foxscanner/chains/`) and shared chain-agnostic detectors and scoring (`foxscanner/scan/`).
* **Frontend** in `frontend/`: plain HTML, CSS and JS (`index.html`, `replay.html`, `static/`), self-hosted fonts, no build step. The backend serves it.
* **No private keys**: FoxScanner never signs transactions or touches funds.

## Project layout

```text
backend/
  foxscanner/        Python package (standard library only)
    server.py        HTTP server: API, pages and /static/ from frontend/
    scan/            engine, detectors, early buyers, market data and chart
    chains/          chain and launchpad adapters, shared EVM JSON-RPC client
    alerts/          Telegram alerts: snapshots, storage, sending, rechecks
    draw/, rewards/  holder draw and Token Burn & Holder Rewards
    history/         recently scanned feed, operator memory, Rug Replay
    bot/             Telegram bot (separate service)
  scripts/           preview server, one-off draw / rewards runs, terminal scan
  tests/             unit and API tests on mocked chains
frontend/
  index.html, replay.html
  static/            css/, js/, fonts/, img/, favicons
  design-src/        brand source images; scripts/brand_assets.py builds static/img from them
data/                SQLite databases (not in git)
```

## Run locally

```sh
cp .env.example .env
# BNB_RPC=https://bnb-mainnet.g.alchemy.com/v2/<your-key>   # any BSC RPC with eth_getLogs
cd backend
python3 -m foxscanner
```

Open `http://localhost:8000`, or go straight to `http://localhost:8000/?ca=0x...&chain=bnb`.

Frontend preview with a fake scanner, no RPC needed (addresses ending in `1` give DANGER, `2` CLEAN, `3` too established):

```sh
python3 backend/scripts/preview.py   # http://localhost:8765
```

Run the tests:

```sh
cd backend
python3 -m unittest discover -s tests -v
```

## Telegram bot

A separate service in `backend/foxscanner/bot/` (standard library only) and a thin client of the FoxScanner API: it starts a scan on the website and turns the result into a short verdict with a link to the full report and a Trade button.

* In a private chat: send a token address, or `/scan <address>`. `/start` and `/help` explain the bot and the verdict.
* **Alerts** (`ALERTS_ENABLED`): tap **Watch** under a verdict to get a message when it moves into or out of `DANGER`, a probably rug warning appears, the biggest operator starts selling, or the early buyers exit.

```sh
# .env
# TG_BOT_TOKEN=<token from @BotFather>
# FOXSCANNER_API=https://your-site
# SITE_URL=https://your-site         # links to the site in bot and alert messages
cd backend
python3 -m foxscanner.bot
```

Only one copy of the bot can poll Telegram at a time.

## Roadmap

* [x] Holder scanner with operator clustering, probably rug warning and early buyers
* [x] **BNB Chain with four.meme**
* [ ] **Solana** with pump.fun (the adapter is in the code, behind `SOLANA_ENABLED`)
* [ ] **Robinhood Chain** with Pons, Flap and Bankr (behind `ROBINHOOD_ENABLED`)
* [ ] Repeat operator detection across launches
* [ ] Wallet profiler and launch radar

## License

[MIT](LICENSE)
