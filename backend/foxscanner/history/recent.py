"""Лента «Recently scanned»: SQLite, тот же файл, что у розыгрыша (DRAW_DB_PATH, по умолчанию ./data/draw.db),
таблица recent_scans. Один токен — одна запись: новый скан того же токена обновляет её и поднимает наверх.
Пишется только завершённый скан с вердиктом (ошибки и «not a token address» сюда не попадают).
launchpad — "flap" / "bankr" у токенов Flap и Bankr (result["launchpad"]), иначе NULL; колонка добавляется в старую базу при старте.
"""
import os, time

from foxscanner import db

from foxscanner.draw.store import DEFAULT_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS recent_scans (
  token TEXT PRIMARY KEY, chain TEXT NOT NULL, ticker TEXT, name TEXT,
  score INTEGER, band TEXT NOT NULL, rug INTEGER NOT NULL, ts INTEGER NOT NULL, mcap_usd REAL);
CREATE INDEX IF NOT EXISTS recent_scans_ts ON recent_scans(ts DESC);
CREATE TABLE IF NOT EXISTS token_views (
  token TEXT NOT NULL, chain TEXT NOT NULL, ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS token_views_ts ON token_views(ts);
"""
MAX_LIMIT = 50
WINDOWS = {"5m": 300, "30m": 1800, "1h": 3600, "6h": 21600, "24h": 86400}


def entry(result, ts=None):
    """Результат engine.scan → запись ленты или None (нет токена или вердикта)."""
    if not isinstance(result, dict) or not result.get("token") or not result.get("band"):
        return None
    h = result.get("header") or {}
    score = result.get("score")
    mcap = h.get("mcap_usd")
    return {"token": result["token"], "chain": result.get("chain") or "robinhood", "launchpad": result.get("launchpad"),
            "ticker": h.get("ticker") or None, "name": h.get("name") or None,
            "score": int(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else None,
            "band": result["band"], "rug": bool(result.get("rug")),
            "mcap_usd": float(mcap) if isinstance(mcap, (int, float)) and not isinstance(mcap, bool) else None,
            "ts": int(ts if ts is not None else time.time())}


class RecentStore:
    def __init__(self, path=None):
        self.path = path or os.environ.get("DRAW_DB_PATH") or DEFAULT_PATH
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self._lock = db.lock_for(self.path)   # один замок на файл для всех хранилищ
        self.db = db.connect(self.path)
        with self._lock, self.db:
            self.db.executescript(SCHEMA)
            cols = {r[1] for r in self.db.execute("PRAGMA table_info(recent_scans)")}
            if "launchpad" not in cols:
                self.db.execute("ALTER TABLE recent_scans ADD COLUMN launchpad TEXT")
            if "mcap_usd" not in cols:
                self.db.execute("ALTER TABLE recent_scans ADD COLUMN mcap_usd REAL")
            # один раз: у уже сохранённых сканов ещё нет строки просмотра
            if not self.db.execute("SELECT 1 FROM token_views LIMIT 1").fetchone():
                self.db.execute("INSERT INTO token_views(token, chain, ts) "
                                "SELECT token, chain, ts FROM recent_scans")

    def close(self):
        with self._lock:
            self.db.close()

    def record(self, result, ts=None):
        """Сохранить скан (или обновить запись токена). → запись или None, если сохранять нечего."""
        e = entry(result, ts)
        if e is None:
            return None
        with self._lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO recent_scans(token, chain, launchpad, ticker, name, score, band, rug, mcap_usd, ts) "
                            "VALUES (:token, :chain, :launchpad, :ticker, :name, :score, :band, :rug, :mcap_usd, :ts)",
                            {**e, "rug": int(e["rug"])})
            self.db.execute("INSERT INTO token_views(token, chain, ts) VALUES (:token, :chain, :ts)", e)
        return e

    def stats(self):
        """{"tokens_scanned", "danger"}: уникальных токенов в ленте и сколько из них с последним вердиктом DANGER."""
        with self._lock:
            n, danger = self.db.execute("SELECT COUNT(*), COALESCE(SUM(band = 'DANGER'), 0) FROM recent_scans").fetchone()
        return {"tokens_scanned": int(n), "danger": int(danger)}

    def recent(self, limit=12, band=None):
        """Последние уникальные токены, новые сверху. band DANGER или CLEAN — только этот вердикт."""
        limit = min(MAX_LIMIT, max(1, int(limit)))
        with self._lock:
            if band in ("DANGER", "CLEAN"):
                rows = self.db.execute("SELECT * FROM recent_scans WHERE band = ? ORDER BY ts DESC, rowid DESC LIMIT ?",
                                       (band, limit)).fetchall()
            else:
                rows = self.db.execute("SELECT * FROM recent_scans ORDER BY ts DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(r), "rug": bool(r["rug"])} for r in rows]

    def radar(self, window_s=7 * 86400, limit=24):
        """CLEAN-токены BNB за окно (по умолчанию 7 дней), новые сверху.
        Час слишком короткий: сайт не сканирует запуски сам, и лента тогда пустая."""
        limit = min(MAX_LIMIT, max(1, int(limit)))
        since = int(time.time()) - max(1, int(window_s))
        with self._lock:
            rows = self.db.execute(
                "SELECT * FROM recent_scans WHERE band = 'CLEAN' AND chain IN ('bnb', 'bsc') AND ts >= ? "
                "ORDER BY ts DESC, rowid DESC LIMIT ?",
                (since, limit)).fetchall()
        return [{**dict(r), "rug": bool(r["rug"])} for r in rows]

    def viewed(self, window="24h", limit=12):
        """Сколько раз токен BNB проверяли за окно. Одна строка на токен, самые частые сверху.
        recent_scans хранит только последний скан, поэтому счётчик живёт в token_views."""
        span = WINDOWS.get(window, WINDOWS["24h"])
        limit = min(MAX_LIMIT, max(1, int(limit)))
        since = int(time.time()) - span
        with self._lock:
            rows = self.db.execute(
                "SELECT v.token AS token, v.chain AS chain, COUNT(*) AS checks, MAX(v.ts) AS ts, "
                "r.ticker AS ticker, r.name AS name, r.band AS band, r.launchpad AS launchpad "
                "FROM token_views v LEFT JOIN recent_scans r ON r.token = v.token "
                "WHERE v.ts >= ? AND v.chain IN ('bnb', 'bsc') "
                "GROUP BY v.token, v.chain ORDER BY checks DESC, ts DESC LIMIT ?",
                (since, limit)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["checks"] = int(d["checks"])
            d["ts"] = int(d["ts"])
            out.append(d)
        return out
