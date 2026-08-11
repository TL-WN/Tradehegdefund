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


def _get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


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
        except Exception as e:
            out["_error"] = str(e)
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


def build_state():
    prices, fng = refresh_prices()
    book = _load_json("paper_book.json", {})
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
