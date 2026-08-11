"""
dashboard_app.py
Self-contained hedge-fund dashboard web app (Python stdlib only — no pip needed).
Serves a Bloomberg/hedge-fund styled UI that shows LIVE crypto prices, paper-book
positions (history + open), the desk's analysis, research, and news — all read from
the firm's real files plus live CoinGecko ticks.

Run:  python dashboard_app.py [port]      (default 8765)
Then open the printed URL. For a public link, tunnel it (see README).

Endpoints:
  GET /                -> index.html (the SPA)
  GET /api/state       -> JSON: live prices + book + meetings + research + news
  GET /api/history     -> JSON: price history for charts
"""
import json
import os
import sys
import time
import datetime
import urllib.request
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(__import__("os").environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8765))

# ---------- live price cache (refreshed in background) ----------
PRICE_CACHE = {"updated": 0, "data": {}, "fng": {}}
CACHE_TTL = 20  # seconds
_LOCK = threading.Lock()

COINS = {
    "BTC": ("bitcoin", "BTC/USD"),
    "ETH": ("ethereum", "ETH/USD"),
    "BNB": ("binancecoin", "BNB/USD"),
    "SOL": ("solana", "SOL/USD"),
    "XRP": ("ripple", "XRP/USD"),
}

# Binance fallback symbols (no key, generous limits) in case CoinGecko rate-limits.
BINANCE = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "BNB": "BNBUSDT", "SOL": "SOLUSDT", "XRP": "XRPUSDT"}


def _get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _binance_prices():
    """Fallback live prices from Binance public API (no key). Raises on failure."""
    out = {}
    for sym, bsym in BINANCE.items():
        t = _get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={bsym}")
        out[sym] = {
            "pair": sym + "/USD",
            "price": float(t.get("lastPrice", 0)),
            "chg24h": float(t.get("priceChangePercent", 0)),
            "chg7d": None, "chg30d": None, "mcap": None, "ath": None,
        }
    return out


def _kraken_prices():
    """Fallback via Kraken public ticker (very permissive, cloud-friendly)."""
    pair_map = {"BTC": "XBTUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT", "XRP": "XRPUSDT", "BNB": "BNBUSDT"}
    out = {}
    for sym, kp in pair_map.items():
        t = _get(f"https://api.kraken.com/0/public/Ticker?pair={kp}")
        res = (t.get("result") or {}).get(kp)
        if not res:
            continue
        last = float(res["c"][0])
        chg = float(res["P"][1])  # 24h pct change (quote)
        out[sym] = {
            "pair": sym + "/USD",
            "price": last,
            "chg24h": chg,
            "chg7d": None, "chg30d": None, "mcap": None, "ath": None,
        }
    if not out:
        raise RuntimeError("kraken returned no pairs")
    return out


def _coinbase_prices():
    """Fallback via Coinbase spot prices (cloud-friendly)."""
    out = {}
    for sym in BINANCE:
        p = _get(f"https://api.coinbase.com/v2/prices/{sym}-USD/spot")
        out[sym] = {
            "pair": sym + "/USD",
            "price": float(p["data"]["amount"]),
            "chg24h": None, "chg7d": None, "chg30d": None, "mcap": None, "ath": None,
        }
    return out


def refresh_prices():
    now = time.time()
    with _LOCK:
        if now - PRICE_CACHE["updated"] < CACHE_TTL:
            return PRICE_CACHE["data"], PRICE_CACHE["fng"]
        out = {}
        try:
            ids = ",".join(c[0] for c in COINS.values())
            d = _get(f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"
                     f"&ids={ids}&price_change_percentage=24h,7d,30d")
            by_id = {x["id"]: x for x in d}
            for sym, (cid, pair) in COINS.items():
                x = by_id.get(cid, {})
                out[sym] = {
                    "pair": pair,
                    "price": x.get("current_price"),
                    "chg24h": x.get("price_change_percentage_24h"),
                    "chg7d": x.get("price_change_percentage_7d_in_currency"),
                    "chg30d": x.get("price_change_percentage_30d_in_currency"),
                    "mcap": x.get("market_cap"),
                    "ath": x.get("ath"),
                }
        except Exception:
            # CoinGecko down/rate-limited -> try fallbacks in order
            out = {}
            for fn in (_binance_prices, _kraken_prices, _coinbase_prices):
                try:
                    out = fn()
                    break
                except Exception:
                    continue
            if not out:
                out["_error"] = "all price sources unavailable"
        try:
            fng = _get("https://api.alternative.me/fng/?limit=1")
            PRICE_CACHE["fng"] = {
                "value": fng["data"][0]["value"],
                "value_classification": fng["data"][0]["value_classification"],
                "timestamp": fng["data"][0]["timestamp"],
            }
        except Exception:
            pass
        PRICE_CACHE["data"] = out
        PRICE_CACHE["updated"] = now
        return out, PRICE_CACHE["fng"]


# ---------- read firm files ----------
def _load_json(path, default=None):
    p = os.path.join(HERE, path)
    if not os.path.exists(p):
        return default
    try:
        return json.load(open(p))
    except Exception:
        return default


def latest_meeting(kind):
    """Return the most recent meeting log of a kind (opening/closing/midday)."""
    logs = os.path.join(HERE, "meeting_logs")
    if not os.path.isdir(logs):
        return None
    cands = [f for f in os.listdir(logs) if f.startswith(kind.lower()) and f.endswith(".json")]
    if not cands:
        return None
    cands.sort()
    return _load_json(os.path.join("meeting_logs", cands[-1]))


def build_series(sym="BTC"):
    """Build a TradingView-style candle series for the chart from history.json closes,
    the live price, and the paper book's open position levels (entry/stop/target).
    Candles are synthesized from the daily close series (no real OHLC available):
    open = prev close, close = day close, high/low = close +/- a deterministic wick
    derived from the day index so the chart looks like real candles but is our own data.
    Volume is deterministically synthesized from the day's price move so the bars look
    realistic (our own data, not a real exchange feed)."""
    import math
    hist = _load_json("history.json", {})
    node = (hist.get(sym) or hist.get(sym.lower()) or {})
    series = node.get("series", []) if isinstance(node, dict) else []
    prices, _ = refresh_prices()
    live = (prices.get(sym) or {}).get("price")

    candles = []
    prev = None
    for i, pt in enumerate(series):
        c = pt.get("c")
        if c is None:
            continue
        o = prev if prev is not None else c
        seed = (math.sin(i * 12.9898) * 43758.5453) % 1
        wick = abs(c) * 0.012
        hi = max(o, c) + wick * seed
        lo = min(o, c) - wick * (1 - seed)
        move = abs(c - o) / (o or 1)
        vol = round(800 + 5200 * seed + 30000 * move, 0)  # synthetic BTC-ish volume
        candles.append({"t": pt.get("t"), "o": round(o, 2), "h": round(hi, 2),
                        "l": round(lo, 2), "c": round(c, 2), "v": vol})
        prev = c
    # live tail candle (today, updating)
    if live is not None:
        o = prev if prev is not None else live
        candles.append({"t": "live", "o": round(o, 2), "h": round(max(o, live), 2),
                        "l": round(min(o, live), 2), "c": round(live, 2), "v": 1200, "live": True})

    # paper position levels for overlay
    book = {}
    try:
        from book import load as _bl
        book = _bl() or {}
    except Exception:
        book = _load_json("paper_book.json", {})
    op = book.get("open_position") or {}
    pos_sym = (op.get("symbol") or "").upper()
    levels = None
    if op and op.get("qty") and (pos_sym == sym or not pos_sym):
        levels = {
            "side": op.get("side"),
            "entry": op.get("entry"),
            "stop": op.get("stop"),
            "target": op.get("target"),
            "lev": op.get("leverage"),
        }

    # equity curve (paper book: start -> each closed trade pnl -> current equity)
    eq_curve = []
    try:
        start = book.get("starting_equity") or 1000000
        eq_curve = [{"t": "start", "v": start, "peak": start}]
        eq = start
        peak = start
        for t in (book.get("trades") or []):
            eq += (t.get("realized_pnl") or 0)
            peak = max(peak, eq)
            eq_curve.append({"t": (t.get("ts") or "")[:10], "v": round(eq, 0), "peak": round(peak, 0)})
        cur = book.get("equity") or eq
        peak = max(peak, cur)
        eq_curve.append({"t": "now", "v": round(cur, 0), "peak": round(peak, 0)})
    except Exception:
        pass

    return {"sym": sym, "candles": candles[-200:], "live": live, "levels": levels,
            "equity_curve": eq_curve, "chg24h": (prices.get(sym) or {}).get("chg24h")}


def build_state():
    prices, fng = refresh_prices()
    try:
        from book import load as _book_load
        book = _book_load()
    except Exception:
        book = _load_json("paper_book.json", {})
    if not book or book.get("equity") is None:
        try:
            from book import _default_book
            book = _default_book()
        except Exception:
            book = {}
    opening = latest_meeting("opening")
    closing = latest_meeting("closing")
    midday = latest_meeting("midday")

    # normalize meeting minutes for the UI
    def slim(m):
        if not m:
            return None
        c = m.get("cio_call", {})
        return {
            "kind": m.get("kind"),
            "time": m.get("time"),
            "ts": m.get("ts"),
            "decision": c.get("DECISION"),
            "instrument": c.get("INSTRUMENT"),
            "thesis": c.get("THESIS"),
            "size": c.get("SIZE"),
            "leverage": c.get("LEVERAGE"),
            "conviction": c.get("CONVICTION"),
            "dissent": c.get("DESK DISSENT"),
            "speakers": [
                {"name": s.get("name"), "role": s.get("role"), "view": (s.get("view") or "")[:600]}
                for s in m.get("speakers", [])
            ],
        }

    # research briefs (latest few)
    rlogs = os.path.join(HERE, "research_logs")
    research = []
    if os.path.isdir(rlogs):
        for f in sorted(os.listdir(rlogs)):
            if f.endswith(".json"):
                b = _load_json(os.path.join("research_logs", f))
                if b and "error" not in b:
                    research.append({
                        "strategy": b.get("strategy_name"),
                        "verdict": b.get("verdict_hint"),
                        "source": b.get("source"),
                        "date": b.get("date"),
                    })

    # news (latest daily + weekly digest if present)
    nlogs = os.path.join(HERE, "news_logs")
    news_items = []
    news_week = None
    if os.path.isdir(nlogs):
        dailies = sorted([f for f in os.listdir(nlogs) if f.startswith("news_") and f.endswith(".json")])
        if dailies:
            b = _load_json(os.path.join("news_logs", dailies[-1]))
            news_items = b.get("items", [])[:12]
        weeks = sorted([f for f in os.listdir(nlogs) if f.startswith("weekly_")])
        if weeks:
            news_week = _load_json(os.path.join("news_logs", weeks[-1]))

    # --- open positions blotter (live mark-to-market) ---
    open_positions = []
    try:
        from book import price_for as _pf, _unrealized as _un, account_value as _av
        op = book.get("open_position")
        if op:
            sym = op.get("symbol") or op.get("instrument") or ""
            px = _pf(sym, {"crypto": {s: {"price": (prices.get(s, {}) or {}).get("price")} for s in prices}})
            upnl = _un(op, {"crypto": {s: {"price": (prices.get(s, {}) or {}).get("price")} for s in prices}})
            entry = op.get("entry")
            stop = op.get("stop"); target = op.get("target")
            d_stop = ((px - stop) / entry * 100.0) if (px and entry and stop) else None
            d_tgt = ((target - px) / entry * 100.0) if (px and entry and target) else None
            open_positions.append({
                "symbol": sym, "side": op.get("side"),
                "qty": op.get("qty"), "leverage": op.get("leverage"),
                "margin_pct": op.get("margin_pct"), "notional": op.get("notional"),
                "entry": entry, "mark": px, "stop": stop, "target": target,
                "unrealized_pnl": round(upnl, 2),
                "dist_to_stop_pct": round(d_stop, 2) if d_stop is not None else None,
                "dist_to_target_pct": round(d_tgt, 2) if d_tgt is not None else None,
                "opened": op.get("opened"),
            })
    except Exception as e:
        open_positions = []

    return {
        "server_time": datetime.datetime.utcnow().isoformat() + "Z",
        "prices": prices,
        "fng": fng,
        "book": {
            "equity": book.get("equity"),
            "peak_equity": book.get("peak_equity"),
            "realized_mtd": book.get("realized_mtd"),
            "open_position": book.get("open_position"),
            "max_leverage_used": book.get("max_leverage_used"),
            "max_drawdown_mtd": book.get("max_drawdown_mtd"),
            "halted": book.get("halted"),
            "trades": (book.get("trades") or [])[-25:],  # history, newest last
        },
        "meetings": {
            "opening": slim(opening),
            "midday": slim(midday),
            "closing": slim(closing),
        },
        "open_positions": open_positions,
        "research": research[-6:],
        "news": {"items": news_items, "week": news_week},
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            idx = os.path.join(HERE, "index.html")
            if os.path.exists(idx):
                self._send(200, open(idx, "rb").read(), "text/html")
            else:
                self._send(200, b"<h1>index.html missing</h1>", "text/html")
        elif path == "/api/state":
            try:
                self._send(200, json.dumps(build_state()))
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)}))
        elif path == "/api/history":
            h = _load_json("history.json", {})
            self._send(200, json.dumps(h))
        elif path == "/api/series":
            raw = self.path
            sym = "BTC"
            if "sym=" in raw:
                sym = raw.split("sym=")[1].split("&")[0].upper() or "BTC"
            self._send(200, json.dumps(build_series(sym)))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def log_message(self, *a):
        pass  # quiet


def main():
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Hedge Fund Desk dashboard on http://localhost:{PORT}")
    print("Public link: tunnel with `ssh -R 80:localhost:%d root@localhost.run`" % PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
