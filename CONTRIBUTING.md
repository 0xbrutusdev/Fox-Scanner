# Contributing

Thanks for helping improve FoxScanner.

## Run locally

Requirements: Python 3.12, no third-party packages.

```sh
echo "BNB_RPC=https://bnb-mainnet.g.alchemy.com/v2/<your-key>" > .env   # any BSC RPC with eth_getLogs
python3 server.py
```

Open http://localhost:8000 and paste a four.meme token address, or go straight to `http://localhost:8000/?ca=0x...&chain=bnb`.

To work on the frontend without an RPC, run the preview server. It serves the real pages and API with a fake scanner: addresses ending in `1` return DANGER, `2` CLEAN and `3` too established.

```sh
python3 scripts/preview.py   # http://localhost:8765
```

Optional environment variables: `PORT` (default 8000), `BNB_RPS` / `CRAWLER_RPS` (requests per second to the BNB Chain / Robinhood Chain RPC), `MAX_CONCURRENT` (scans at the same time, default 3), `BACKGROUND_RPS` (separate request rate for background work such as reward checks and alert rechecks, which always waits for live scans; default 2, `0` turns it off) and `TRANSFER_CACHE_ENABLED` (keep token transfer history between scans and read only the new part; off by default, `TRANSFER_CACHE_MAX` caps the number of cached transfers, default 200000). Robinhood Chain (`ROBINHOOD_ENABLED`, `CRAWLER_RPC`) and Solana (`SOLANA_ENABLED`, `SOLANA_RPC`) stay in the code and are off by default.

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

| Path | Role |
|---|---|
| `chains/fourmeme.py` | BNB Chain adapter for four.meme tokens (bonding curve and PancakeSwap after graduation). |
| `chains/evm.py` | Shared JSON-RPC client for EVM chains. |
| `chains/robinhood.py`, `chains/solana.py` | Robinhood Chain and Solana adapters (off by default). |
| `detect.py` | Detectors: pure functions, no network. Holders, signals, links, operators, score. |
| `engine.py` | Picks the chain, runs a scan step by step and emits events under a hard time budget. |
| `server.py` | HTTP server (standard library), API and `/static/` files. |
| `index.html` | Page markup. Edit it by hand; `/static/...?v=` links get the file's content hash when served. |
| `static/` | `css/app.css`, `js/*.js` (plain scripts sharing `window.FS`), self-hosted fonts and images. |
| `scripts/preview.py` | Local preview of the frontend with a fake scanner. |

## Pull requests

- Keep the standard library only and keep everything read-only.
- Add or update tests for behaviour changes; detectors are tested in `tests/test_detect.py`, the frontend contract in `tests/test_frontend.py`.
- Never commit `.env` or any RPC key.
