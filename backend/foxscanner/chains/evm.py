"""Общий слой EVM-сетей (Robinhood Chain, BNB Smart Chain): JSON-RPC с ретраями и бэкоффом, признаки rate-limit
и ошибки размера окна getLogs, keccak256 для селекторов и топиков, ABI-декод, разбор Transfer.

Robinhood (chains/robinhood.py) берёт отсюда помощники и post_json, но держит свои модульные функции
(rpc, iter_logs, ...): тесты и лаунчпады Flap/Bankr подменяют именно их. Новые сети работают через Client —
один объект на RPC со своим лимитером, счётчиками и кэшами.
Read-only: ни ключей, ни подписи, ни отправки транзакций.
"""
import json, random, re, threading, time, urllib.error, urllib.request

from foxscanner.chains import priority

ZERO = "0x" + "0" * 40
DEAD = "0x000000000000000000000000000000000000dead"
LOG_CAP = 10_000          # провайдеры молча обрезают ответ eth_getLogs на стольких логах
CACHE_MAX = 50_000        # записей в кэшах клиента (время блоков, чеки, код)
DELEGATION_PREFIX = "0xef0100"   # EIP-7702: код делегирования у обычного кошелька, не контракт


# --------------------------------------------------------------------------- keccak256 (стандартной библиотеки нет)
_RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B,
       0x0000000080000001, 0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088,
       0x0000000080008009, 0x000000008000000A, 0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
       0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
       0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
_ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
_M64 = (1 << 64) - 1


def _rol(x, n):
    return ((x << n) | (x >> (64 - n))) & _M64 if n else x


def _keccak_f(a):
    for rc in _RC:
        c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
        dd = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        a = [[a[x][y] ^ dd[x] for y in range(5)] for x in range(5)]
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                b[y][(2 * x + 3 * y) % 5] = _rol(a[x][y], _ROT[x][y])
        a = [[b[x][y] ^ (~b[(x + 1) % 5][y] & b[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        a[0][0] ^= rc
    return a


def keccak256(data):
    """Keccak-256 (как в Ethereum, паддинг 0x01, не SHA3-256) -> bytes."""
    if isinstance(data, str):
        data = data.encode()
    rate = 136
    pad = rate - len(data) % rate
    msg = bytearray(data) + (b"\x81" if pad == 1 else b"\x01" + b"\x00" * (pad - 2) + b"\x80")
    a = [[0] * 5 for _ in range(5)]
    for off in range(0, len(msg), rate):
        block = msg[off:off + rate]
        for i in range(rate // 8):
            a[i % 5][i // 5] ^= int.from_bytes(block[8 * i:8 * i + 8], "little")
        a = _keccak_f(a)
    return b"".join(a[i % 5][i // 5].to_bytes(8, "little") for i in range(4))


def topic(signature):
    """topic0 события: keccak256("Event(type,...)")."""
    return "0x" + keccak256(signature).hex()


def selector(signature):
    """4 байта селектора функции: "0x" + 8 hex."""
    return "0x" + keccak256(signature).hex()[:8]


TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


# --------------------------------------------------------------------------- ABI и логи
def u256(data, i):
    return int(data[2 + i * 64: 2 + (i + 1) * 64], 16)


def words(h):
    """ABI-ответ eth_call -> список uint256 по словам ([] для пустого)."""
    h = (h or "0x")[2:]
    return [int(h[i:i + 64], 16) for i in range(0, len(h) - len(h) % 64, 64)]


def word_addr(w):
    return "0x" + f"{w:064x}"[-40:]


def arg_addr(a):
    return "0" * 24 + a.lower()[2:]


def arg_uint(n):
    return f"{n:064x}"


def topic_for(address):
    return "0x" + "0" * 24 + address[2:].lower()


def addr_from_topic(t):
    return "0x" + t[-40:].lower()


def signed(x):
    return x - (1 << 256) if x >= (1 << 255) else x


def abi_string(h):
    """Декод string из ответа eth_call (ABI) или bytes32; пусто — ''."""
    if not h or h == "0x":
        return ""
    b = bytes.fromhex(h[2:])
    if len(b) >= 96:
        n = int.from_bytes(b[32:64], "big")
        return b[64:64 + n].decode(errors="replace")
    return b.rstrip(b"\0").decode(errors="replace")


def parse_transfer(log):
    tp = log.get("topics") or []
    if len(tp) < 3 or tp[0].lower() != TRANSFER_TOPIC:
        return None
    return {"token": log["address"].lower(), "frm": addr_from_topic(tp[1]), "to": addr_from_topic(tp[2]),
            "tx": log["transactionHash"], "block": int(log["blockNumber"], 16)}


# --------------------------------------------------------------------------- транспорт
def is_rate_limited(body):
    """True, если ответ ноды = rate-limit. Только настоящие признаки: "exceeded"/"too many"/"capacity" бывают и
    в ошибке размера окна getLogs, которую лечит деление окна, а не ретрай."""
    def hit(err):
        if not isinstance(err, dict):
            return False
        msg = str(err.get("message", "")).lower()
        return err.get("code") == 429 or any(k in msg for k in (
            "rate limit", "rate-limit", "per second", "too many requests"))
    if isinstance(body, dict) and "error" in body:
        return hit(body["error"])
    if isinstance(body, list):
        return any(isinstance(x, dict) and hit(x.get("error", {})) for x in body)
    return False


def is_window_error(msg):
    """Ошибка размера окна/ответа getLogs: лечится делением окна."""
    return any(k in msg for k in ("range", "too large", "too many", "limited", "response", "size", "exceed",
                                  "more than", "block range"))


def log_span_limit(msg):
    """Сколько блоков узел пускает в один eth_getLogs («up to a 10 block range») или None."""
    m = re.search(r"up to a (\d+) block range", msg)
    return int(m.group(1)) if m else None


def _addr_set(spec):
    """None, один адрес или список → множество нижнего регистра, либо None (фильтра нет)."""
    if spec is None:
        return None
    if isinstance(spec, str):
        return {spec.lower()}
    return {a.lower() for a in spec}


def post_json(url, payload, limit, requests, rate_limited, tries=5, agent="foxscanner"):
    """POST JSON-RPC с ретраями и бэкоффом на rate-limit и сбой: один отбитый запрос под нагрузкой не роняет скан.
    limit(n) — пауза лимитера (n — вес батча), requests / rate_limited — счётчики [int]."""
    if not url:
        raise RuntimeError("RPC url is not configured")
    last = None
    for a in range(tries):
        limit(len(payload) if isinstance(payload, list) else 1)
        requests[0] += 1
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"content-type": "application/json", "User-Agent": f"Mozilla/5.0 {agent}"})
        pause = 0.35 * (2 ** a) + random.random() * 0.3
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                body = json.loads(r.read())
            if is_rate_limited(body):
                rate_limited[0] += 1
                if a < tries - 1:
                    last = body
                    time.sleep(pause)
                    continue
            return body
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read())
            except Exception:
                body = None
            limited = e.code == 429 or (body is not None and is_rate_limited(body))
            if limited:
                rate_limited[0] += 1
                if a < tries - 1:
                    last = body if body is not None else e
                    time.sleep(pause)
                    continue
            if body is not None:
                return body
            raise
        except Exception as e:
            last = e
            if a < tries - 1:
                time.sleep(pause)
                continue
            raise
    if isinstance(last, Exception):
        raise last
    return last if last is not None else {}


class HistoryTooLarge(Exception):
    """История токена длиннее потолка переводов скана."""


# --------------------------------------------------------------------------- клиент сети
class Client:
    """JSON-RPC клиент одной EVM-сети: свой лимитер RPS (фон и критичная работа — через chains.priority, как у
    Robinhood), счётчики запросов и кэши (время блоков, чеки, код адресов). url_fn — функция, а не строка:
    RPC читается из env в момент запроса (адаптер импортируется и без ключа сети)."""

    def __init__(self, url_fn, rps=8, agent="foxscanner"):
        self.url_fn, self.agent = url_fn, agent
        self.limit = priority.Throttle(rps)
        self.bg_limit = priority.Throttle(priority.background_rps())
        self.crit_limit = priority.Throttle(priority.critical_rps())
        self.requests, self.rate_limited = [0], [0]
        self.log_cap = LOG_CAP
        self._ts, self._receipts, self._code = {}, {}, {}
        self._lock = threading.Lock()

    # транспорт
    def _rate(self, n=1):
        priority.rate_limit(self.limit, self.bg_limit, n, crit=self.crit_limit)

    def post(self, payload):
        return post_json(self.url_fn(), payload, self._rate, self.requests, self.rate_limited, agent=self.agent)

    def rpc(self, method, params):
        d = self.post({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        if "error" in d:
            raise RuntimeError(d["error"].get("message", str(d["error"])))
        return d["result"]

    def rpc_batch(self, calls):
        """Много вызовов одним HTTP: [(method, params)] -> [result | None] в исходном порядке."""
        if not calls:
            return []
        resp = self.post([{"jsonrpc": "2.0", "id": i, "method": m, "params": p} for i, (m, p) in enumerate(calls)])
        if isinstance(resp, dict):
            resp = [resp]
        by_id = {r.get("id"): r for r in resp}
        return [by_id.get(i, {}).get("result") for i in range(len(calls))]

    def call(self, to, data, block="latest"):
        return self.rpc("eth_call", [{"to": to, "data": data}, block])

    def call_batch(self, calls, block="latest"):
        """[(to, data)] -> [hex | None] одним HTTP (revert — None)."""
        return self.rpc_batch([("eth_call", [{"to": to, "data": data}, block]) for to, data in calls])

    def block_number(self):
        return int(self.rpc("eth_blockNumber", []), 16)

    # логи
    def iter_logs(self, lo, hi, address=None, topics=None):
        """Страницы getLogs по порядку блоков с адаптивным окном: ошибка окна или упор в log_cap — окно пополам."""
        stack = [(lo, hi)]
        while stack:
            a, b = stack.pop()
            flt = {"fromBlock": hex(a), "toBlock": hex(b)}
            if address:
                flt["address"] = address
            if topics:
                flt["topics"] = topics
            try:
                logs = self.rpc("eth_getLogs", [flt])
            except RuntimeError as e:
                if is_window_error(str(e).lower()) and b > a:
                    logs = None
                else:
                    raise
            if logs is not None and (len(logs) < self.log_cap or b <= a):
                yield logs
                continue
            mid = (a + b) // 2
            stack.append((mid + 1, b))
            stack.append((a, mid))

    def get_logs(self, lo, hi, address=None, topics=None):
        return [lg for page in self.iter_logs(lo, hi, address, topics) for lg in page]

    def _logs_filter(self, lo, hi, address, topics):
        flt = {"fromBlock": hex(lo), "toBlock": hex(hi) if isinstance(hi, int) else hi}
        if address:
            flt["address"] = address
        if topics:
            flt["topics"] = topics
        return flt

    def get_logs_once(self, lo, hi, address=None, topics=None):
        """Один eth_getLogs. None, если узел отверг ширину окна: страницы по 10 блоков здесь не листаем."""
        try:
            return self.rpc("eth_getLogs", [self._logs_filter(lo, hi, address, topics)]) or []
        except RuntimeError as e:
            if is_window_error(str(e).lower()):
                span = log_span_limit(str(e).lower())
                if span:
                    self._log_span = span
                return None
            raise

    def nearest_logs(self, center, head, address=None, topics=None, radius=4000, page_budget=48):
        """Логи рядом с center. Широкое окно — один запрос. Узел с потолком в N блоков — страницы от center
        наружу, не дальше page_budget запросов: весь диапазон по 10 блоков не читаем."""
        center = min(max(0, center), head)
        lo, hi = max(0, center - radius), min(head, center + radius)
        once = self.get_logs_once(lo, hi, address, topics)
        if once is not None:
            return once
        span = max(1, getattr(self, "_log_span", None) or 10)
        pages, k = 0, 0
        while pages < page_budget:
            starts = [center] if k == 0 else [center - k * span, center + k * span]
            k += 1
            moved = False
            for start in starts:
                a = max(lo, start)
                b = min(hi, a + span - 1)
                if a > hi or b < lo or b < a:
                    continue
                moved = True
                pages += 1
                hit = self.get_logs_once(a, b, address, topics)
                if hit:
                    return hit
                if pages >= page_budget:
                    break
            if not moved or (center - (k - 1) * span <= lo and center + (k - 1) * span >= hi):
                break
        return []

    def earliest_erc20_mint(self, token):
        """Первый минт ERC-20 (Transfer с 0x0) одним alchemy_getAssetTransfers или None (метод узла не умеет)."""
        try:
            res = self.rpc("alchemy_getAssetTransfers", [{
                "fromBlock": "0x0", "toBlock": "latest", "fromAddress": ZERO,
                "contractAddresses": [token.lower()], "category": ["erc20"],
                "order": "asc", "maxCount": "0x1", "excludeZeroValue": False,
            }])
        except (RuntimeError, OSError):
            return None
        rows = (res or {}).get("transfers") or []
        if not rows or not rows[0].get("hash"):
            return None
        block = rows[0].get("blockNum")
        try:
            block = int(block, 16) if isinstance(block, str) else int(block)
        except (TypeError, ValueError):
            return None
        return {"block": block, "tx": rows[0]["hash"]}

    def _alchemy_row(self, row, i):
        """Строка alchemy_getAssetTransfers → перевод или None. Сумма — rawContract.value, не float value."""
        raw = (row.get("rawContract") or {}).get("value")
        tx = row.get("hash")
        if not raw or not tx:
            return None
        uid = row.get("uniqueId") or ""
        try:
            log_index = int(uid.rsplit(":log:", 1)[1]) if ":log:" in uid else i
        except ValueError:
            log_index = i
        block = row.get("blockNum")
        try:
            block = int(block, 16) if isinstance(block, str) else int(block)
        except (TypeError, ValueError):
            return None
        return {"frm": (row.get("from") or ZERO).lower(), "to": (row.get("to") or ZERO).lower(),
                "amount": int(raw, 16), "tx": tx, "block": block, "log_index": log_index}

    def _alchemy_transfers(self, token, lo, hi, cap, frm, to):
        """Все ERC-20 переводы страницами по 1000. None — узел не умеет alchemy_getAssetTransfers
        (тогда вызывающий читает eth_getLogs). Первый промах запоминается."""
        if getattr(self, "_no_asset_transfers", False):
            return None
        want_from, want_to = _addr_set(frm), _addr_set(to)
        params = {"fromBlock": hex(lo), "toBlock": hex(hi) if isinstance(hi, int) else hi,
                  "contractAddresses": [token.lower()], "category": ["erc20"], "order": "asc",
                  "maxCount": "0x3e8", "excludeZeroValue": False}
        out, seen = [], set()
        try:
            while True:
                res = self.rpc("alchemy_getAssetTransfers", [params])
                if not isinstance(res, dict):
                    self._no_asset_transfers = True
                    return None
                for i, row in enumerate(res.get("transfers") or []):
                    t = self._alchemy_row(row, i)
                    if t is None:
                        continue
                    key = (t["tx"], t["log_index"])
                    if key in seen:
                        continue
                    seen.add(key)
                    if want_from is not None and t["frm"] not in want_from:
                        continue
                    if want_to is not None and t["to"] not in want_to:
                        continue
                    out.append(t)
                    if cap and len(out) > cap:
                        raise HistoryTooLarge(len(out))
                page = res.get("pageKey")
                if not page:
                    break
                params["pageKey"] = page
        except RuntimeError:
            if out:
                raise
            self._no_asset_transfers = True
            return None
        out.sort(key=lambda t: (t["block"], t["log_index"]))
        return out

    def token_transfers(self, token, lo, hi=None, cap=0, frm=None, to=None):
        """Переводы токена в [lo, hi] в порядке чейна: [{"frm", "to", "amount", "tx", "block", "log_index"[, "ts"]}].
        cap > 0 — больше переводов не читаем: HistoryTooLarge. frm / to — фильтр по адресу или списку (OR внутри поля).
        Alchemy отдаёт всю историю страницами по 1000. eth_getLogs — запасной путь, на узле с окном в 10 блоков
        он режет диапазон на страницы и для длинной истории не успевает."""
        hi = self.block_number() if hi is None else hi
        if isinstance(hi, int) and hi < lo:
            return []
        got = self._alchemy_transfers(token, lo, hi, cap, frm, to)
        if got is not None:
            return got
        pick = lambda x: None if x is None else [topic_for(v) for v in ([x] if isinstance(x, str) else sorted(x))]
        topics = [TRANSFER_TOPIC, pick(frm), pick(to)]
        while topics[-1] is None:
            topics.pop()
        out, seen, same = [], 0, {}
        for page in self.iter_logs(lo, hi, address=token.lower(), topics=topics):
            seen += len(page)
            if cap and seen > cap:
                raise HistoryTooLarge(seen)
            for lg in page:
                p = parse_transfer(lg)
                if not p or len(lg["data"]) <= 2:
                    continue
                t = {"frm": same.setdefault(p["frm"], p["frm"]), "to": same.setdefault(p["to"], p["to"]),
                     "amount": int(lg["data"][:66], 16), "tx": same.setdefault(p["tx"], p["tx"]),
                     "block": p["block"], "log_index": int(lg["logIndex"], 16)}
                if lg.get("blockTimestamp"):
                    t["ts"] = int(lg["blockTimestamp"], 16)
                out.append(t)
        out.sort(key=lambda t: (t["block"], t["log_index"]))
        return out

    # блоки и адреса
    def block_timestamps(self, blocks, chunk=100):
        blocks = sorted(set(blocks))
        out = {b: self._ts[b] for b in blocks if b in self._ts}
        need = [b for b in blocks if b not in out]
        for i in range(0, len(need), chunk):
            part = need[i:i + chunk]
            for b, blk in zip(part, self.rpc_batch([("eth_getBlockByNumber", [hex(b), False]) for b in part])):
                if blk:
                    out[b] = int(blk["timestamp"], 16)
        with self._lock:
            if len(self._ts) > CACHE_MAX:
                self._ts.clear()
            self._ts.update(out)
        return out

    def block_info(self, block):
        b = self.rpc("eth_getBlockByNumber", [hex(block) if isinstance(block, int) else block, False])
        return {"number": int(b["number"], 16), "timestamp": int(b["timestamp"], 16)}

    def block_at_time(self, ts, tries=24):
        """Первый блок с timestamp >= ts: интерполяцией по времени (блоки BSC идут почти ровно), затем
        бинарным поиском в оставшемся отрезке. Голова раньше ts — номер головы."""
        head = self.block_info("latest")
        if head["timestamp"] <= ts:
            return head["number"]
        lo, hi = {"number": 0, "timestamp": 0}, head
        for _ in range(tries):
            if hi["number"] - lo["number"] <= 1:
                break
            span_t = hi["timestamp"] - lo["timestamp"]
            guess = lo["number"] + int((hi["number"] - lo["number"]) * (ts - lo["timestamp"]) / span_t) if span_t else 0
            guess = min(hi["number"] - 1, max(lo["number"] + 1, guess))
            if hi["number"] - lo["number"] < 64:   # близко: делим пополам, интерполяция тут пляшет
                guess = (lo["number"] + hi["number"]) // 2
            b = self.block_info(guess)
            if b["timestamp"] >= ts:
                hi = b
            else:
                lo = b
        return hi["number"]

    def is_contract(self, addresses, chunk=100):
        addrs = {a.lower() for a in addresses}
        need = sorted(addrs - self._code.keys())
        for i in range(0, len(need), chunk):
            part = need[i:i + chunk]
            for a, code in zip(part, self.rpc_batch([("eth_getCode", [a, "latest"]) for a in part])):
                if code is not None:
                    code = code.lower()
                    self._code[a] = code not in ("0x", "0x0", "") and not code.startswith(DELEGATION_PREFIX)
        with self._lock:
            if len(self._code) > CACHE_MAX:
                self._code.clear()
        return {a: self._code.get(a, False) for a in addrs}

    def nonces_at(self, pairs, chunk=100):
        """{(wallet, block): число исходящих транзакций кошелька к началу блока} (eth_getTransactionCount на
        block − 1, нужен архивный RPC). Нет ответа — None."""
        pairs = sorted(set(pairs))
        out = {}
        for i in range(0, len(pairs), chunk):
            part = pairs[i:i + chunk]
            res = self.rpc_batch([("eth_getTransactionCount", [w, hex(max(0, b - 1))]) for w, b in part])
            for k, r in zip(part, res):
                out[k] = int(r, 16) if r else None
        return out

    def receipt_logs(self, txs, chunk=50):
        """{tx: логи чека}; чек не получен — [] (не кэшируется)."""
        out = {h: self._receipts[h] for h in txs if h in self._receipts}
        need = [h for h in txs if h not in out]
        for i in range(0, len(need), chunk):
            part = need[i:i + chunk]
            for h, rc in zip(part, self.rpc_batch([("eth_getTransactionReceipt", [h]) for h in part])):
                out[h] = (rc or {}).get("logs", [])
                if rc:
                    with self._lock:
                        if len(self._receipts) > CACHE_MAX:
                            self._receipts.clear()
                        self._receipts[h] = out[h]
        return out

    def tx_sender(self, tx):
        t = self.rpc("eth_getTransactionByHash", [tx])
        return (t or {}).get("from", "").lower() or None

    # токен
    def token_supply(self, token):
        return int(self.call(token.lower(), "0x18160ddd"), 16)

    def token_meta(self, token):
        t = token.lower()
        name, sym = self.call_batch([(t, "0x06fdde03"), (t, "0x95d89b41")])
        return {"name": abi_string(name), "symbol": abi_string(sym)}

    def drop_caches(self):
        with self._lock:
            self._receipts.clear()
            self._ts.clear()
