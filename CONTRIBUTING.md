# Contributing

Thanks for helping improve FoxScanner.

## Run locally

Requirements: Python 3.12, no third-party packages.

```sh
echo "BNB_RPC=https://bnb-mainnet.g.alchemy.com/v2/<your-key>" > .env   # any BSC RPC with eth_getLogs
cd backend
python3 -m foxscanner
```

Backend commands below run from `backend/`. The `.env` file and the `data/` folder stay in the repository root.

Open http://localhost:8000 and paste a four.meme token address, or go straight to `http://localhost:8000/?ca=0x...&chain=bnb`.

To work on the frontend without an RPC, run the preview server. It serves the real pages and API with a fake scanner: addresses ending in `1` return DANGER, `2` CLEAN and `3` too established.

```sh
python3 scripts/preview.py   # http://localhost:8765
```

Optional environment variables: `PORT` (default 8000), `BNB_RPS` / `ROBINHOOD_RPS` (requests per second to the BNB Chain / Robinhood Chain RPC), `MAX_CONCURRENT` (scans at the same time, default 3), `BACKGROUND_RPS` (separate request rate for background work such as reward checks and alert rechecks, which always waits for live scans; default 2, `0` turns it off) and `TRANSFER_CACHE_ENABLED` (keep token transfer history between scans and read only the new part; off by default, `TRANSFER_CACHE_MAX` caps the number of cached transfers, default 200000). Robinhood Chain (`ROBINHOOD_ENABLED`, `ROBINHOOD_RPC`) and Solana (`SOLANA_ENABLED`, `SOLANA_RPC`) stay in the code and are off by default.

To run a scan from the terminal and watch the events:

```sh
python3 scripts/run_scan.py 0x...
```

## Tests

```sh
python3 -m unittest discover -s tests -v
```

Tests run on mocked chain adapters: no network and no RPC key are needed. Every push and pull request to `main` runs them in GitHub Actions.

## Project layout

The repository has two parts: `backend/` (the `foxscanner` Python package, its scripts and tests) and `frontend/` (the pages and static files the backend serves).

Backend, `backend/foxscanner/`:

| Path | Role |
|---|---|
| `server.py` | HTTP server (standard library), API, pages and `/static/` files from `frontend/`. |
| `scan/engine.py` | Picks the chain, runs a scan step by step and emits events under a hard time budget. |
| `scan/detect.py` | Detectors: pure functions, no network. Holders, signals, links, operators, score. |
| `scan/early.py`, `scan/market.py` | Early buyers; prices, market cap and chart (GeckoTerminal, DexScreener). |
| `chains/fourmeme.py` | BNB Chain adapter for four.meme tokens (bonding curve and PancakeSwap after graduation). |
| `chains/evm.py` | Shared JSON-RPC client for EVM chains. |
| `chains/robinhood.py`, `chains/solana.py` | Robinhood Chain and Solana adapters (off by default). |
| `alerts/` | Telegram alerts: `logic` (snapshots and changes), `store`, `notify`, `recheck`. |
| `draw/`, `rewards/` | Holder draw and Token Burn & Holder Rewards, each split into `logic` (pure), `service` and `store`. |
| `history/` | `recent` (recently scanned feed), `opmem` (operator memory), `replay` (Rug Replay). |
| `bot/` | Telegram bot, a separate service (`python3 -m foxscanner.bot`). |
| `paths.py`, `env.py`, `db.py`, `memguard.py`, `trade.py` | Project paths, `.env` loading, SQLite setup, memory guard, Trade links. |

Other backend folders: `backend/scripts/` (`preview.py` runs the site with a fake scanner, plus one-off draw, rewards and scan tools) and `backend/tests/`.

Frontend, `frontend/`:

| Path | Role |
|---|---|
| `index.html`, `replay.html` | Page markup. Edit by hand; `/static/...?v=` links get the file's content hash when served. |
| `static/` | `css/app.css`, `js/*.js` (plain scripts sharing `window.FS`), self-hosted fonts and images. |
| `design-src/`, `scripts/brand_assets.py` | Brand source images and the script that builds `static/img` from them. |

## Pull requests

- Keep the standard library only and keep everything read-only.
- Add or update tests for behaviour changes; detectors are tested in `backend/tests/test_detect.py`, the frontend contract in `backend/tests/test_frontend.py`.
- Never commit `.env` or any RPC key.
