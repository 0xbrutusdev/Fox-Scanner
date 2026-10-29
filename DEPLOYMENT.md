# FoxScanner deployment guide

## Architecture and deployment model

- `frontend/`: plain HTML, CSS, JavaScript, fonts and images; no Node or build step.
- `backend/foxscanner/server.py`: Python `ThreadingHTTPServer`; serves the frontend, JSON API and scan event stream. Entry point: `python -m foxscanner` from `backend/`.
- `backend/foxscanner/scan/` and `chains/`: scoring, market data and RPC adapters.
- `history/`, `alerts/`, `draw/`, `rewards/`: SQLite-backed features and optional background work.
- `backend/foxscanner/bot/`: optional separate Telegram polling process.
- `backend/tests/`: unittest suite. CI targets Python 3.12; the local machine currently has 3.14.2.

Deploy the entire repository as one long-running Python web service. Keep `frontend/` alongside `backend/`. Static-only hosting cannot run the scanner. Start with ONE instance and ONE Python process: scan jobs/caches are in memory, SQLite is local, and optional schedulers run inside the web process.

## Local UI review

Real application, from the repository root:

```powershell
cd backend
python -m foxscanner
```

Open http://localhost:8000/. Live scanning requires a working BNB RPC endpoint.

Mock preview, from the repository root in another terminal:

```powershell
python backend/scripts/preview.py
```

Open http://localhost:8765/. The preview mocks scanning, chart data and early buyers; it is not a complete mock of every external API. It disables draws, rewards and alerts. Replay remains feature-gated.

Review `/`, `/tokens`, `/radar`, `/about`, `/api`, and `/token-management`. Try these scan links:

- DANGER: http://localhost:8765/?ca=0x0000000000000000000000000000000000000001&chain=bnb
- CLEAN: http://localhost:8765/?ca=0x0000000000000000000000000000000000000002&chain=bnb
- TOO ESTABLISHED: http://localhost:8765/?ca=0x0000000000000000000000000000000000000003&chain=bnb
- Error state: use the same address ending in `4`.

Check desktop/mobile navigation, scan progress, holder/operator sections, chart, early buyers, empty states, and error states. Demo feed entries are not all valid mock scan targets; use the explicit addresses above.

## Recommended initial hosting: Render Python web service

This is a deployment recommendation, not a completed cloud deployment. Use a paid service with a persistent disk for retained scan history. See [Render disk documentation](https://render.com/docs/disks).

1. Review and commit the intended changes to your remote repository. The inspected checkout contains substantial existing uncommitted work. Do not commit `.env`, API credentials, or local database contents.
2. Add a root `.python-version` containing `3.12` to match CI. Render supports a minor version in this file; a `PYTHON_VERSION` environment override requires a full patch version. See [Python version configuration](https://render.com/docs/python-version). Do not assume `backend/runtime.txt` configures Render.
3. Create a **Web Service**, connect the repository, and select **Python 3**. Leave Root Directory empty so both backend and frontend are available.
4. Build command: `pip install -r backend/requirements.txt` (currently no third-party runtime dependencies).
5. Start command: `cd backend && python -u -m foxscanner`.
6. Health check path: `/health`. The server already binds to `0.0.0.0` and reads the platform's `PORT` variable. See [health checks](https://render.com/docs/health-checks).
7. Attach a persistent disk at `/var/data`. Set the environment below in the hosting dashboard.
8. Deploy a single instance. Test the generated HTTPS URL before adding a custom domain and updating `SITE_URL`.

```dotenv
BNB_RPC=https://YOUR-BSC-RPC-ENDPOINT
BNB_RPS=10
BNB_ENABLED=true
DEFAULT_EVM_CHAIN=bnb
FLAP_BNB_ENABLED=true
GENIUS_BNB_ENABLED=true
ROBINHOOD_ENABLED=false
SOLANA_ENABLED=false
DRAW_DB_PATH=/var/data/draw.db
OPMEM_DB_PATH=/var/data/memory.db
SITE_URL=https://YOUR-SERVICE.onrender.com
DRAW_ENABLED=false
REWARDS_ENABLED=false
ALERTS_ENABLED=false
REPLAY_ENABLED=false
OPMEM_ENABLED=false
BANKR_ENABLED=false
BANKR_INDEX_ENABLED=false
MAX_CONCURRENT=1
SCAN_QUEUE_MAX=2
SCAN_RATE_PER_MIN=10
```

The reduced concurrency is a conservative initial setting, not a measured capacity recommendation. Select memory/CPU based on representative scan measurements; monitor RSS, queue rejections, latency and RPC throttling before increasing concurrency. Match `BNB_RPS` to your RPC allowance and ensure the provider supports the required historical log queries.

The application loads only the repository-root `.env`; `backend/.env` is not loaded by its dotenv helper. Hosting environment variables take precedence. Set secrets in the hosting dashboard. Keep optional features disabled until their configuration and authorization are verified. The current local configuration reports a draw enabled without a mint; do not copy that configuration blindly.

Render disks preserve only files below the mount point and require a single instance; disk-backed deployments have brief downtime. See [deployment behavior](https://render.com/docs/deploys).

## Public-launch checks

1. Run `python -m unittest discover -s tests -v` from `backend/`, preferably on Python 3.12 as in CI. Resolve failures before calling the release verified.
2. Verify `/health`, `/api/config`, all public pages and static assets over HTTPS. Health alone does not prove RPC functionality. Perform a real BNB scan and verify streamed progress, result, chart and early buyers.
3. Address proxy trust in `server.py:scan_client`: it trusts `CF-Connecting-IP` without checking the connecting proxy, ignores ordinary forwarded-IP headers, and grants a higher quota to a matching bot User-Agent. Behind some proxies visitors can share a quota; a supplied header/User-Agent can evade the intended limit. Establish trusted ingress/client-IP handling and authenticated bot quotas before public exposure.
4. Keep the Python HTTP server behind managed HTTPS ingress or a reverse proxy. Verify event-stream delivery and long-request behavior; an Nginx proxy would need buffering disabled for `/api/events` and a timeout that accommodates scans. Load-test connection/thread limits; this is a standard-library HTTP server, not a hardened application server.
5. Verify recent history survives a restart/redeploy. Back up SQLite using its backup API or a stopped-process copy; copying only an active WAL database file can omit recent writes. Test restoration.
6. Configure uptime checks, error logs and memory/RPC monitoring. Do not expose credentials in logs. Review admin/optional-feature access before enabling those endpoints.

## Optional Telegram bot

Run a separate worker using `cd backend && python -u -m foxscanner.bot`, with `TG_BOT_TOKEN`, `FOXSCANNER_API` and `SITE_URL` set. Enable alerts only after configuring the same strong `ALERTS_API_SECRET` on the web service and bot. Run only one Telegram poller per bot token. Never use the mock preview as its backend.

## Release and rollback

Record the deployed commit and take a consistent database backup before updates. Deploy, then repeat health, scan and persistence checks. If the release fails, redeploy the prior known-good commit. Code rollback does not undo database changes; assess schema compatibility and restore the backup only if necessary, accepting loss of writes since that backup. Keep a maintenance window for disk-backed restarts.

## Inspection verification (2026-10-28)

The mock preview returned HTTP 200 for all six public pages listed above, `/health`, `/api/config` and the main CSS file. This is HTTP verification, not a complete visual or live-RPC acceptance test.

The existing suite on Windows/Python 3.14.2 ran 677 tests with 2 failures and 22 errors. The output includes SQLite temporary-file cleanup locks on Windows, a POSIX-path expectation in `test_default_path_next_to_draw_db`, and a frontend string expectation in `test_bankr_behind_flag`. See `backend/test-results-local.log`. Recheck on CI's Linux/Python 3.12 environment and investigate remaining failures before release. No application code was changed during this inspection.
