"""
fetch_history.py
Pull REAL daily price history (CoinGecko, no key) for backtests and save to history.json.
BTC + ETH, last 120 days by default.
"""
import json
import os
import datetime
import urllib.request

HIST_FILE = os.path.join(os.path.dirname(__file__), "history.json")
SYMS = {"BTC": "bitcoin", "ETH": "ethereum"}
DAYS = 120


def _get(u):
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def fetch():
    out = {}
    for sym, cid in SYMS.items():
        d = _get(f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart?vs_currency=usd&days={DAYS}&interval=daily")
        prices = d.get("prices", [])
        out[sym] = {"series": [{"t": datetime.datetime.utcfromtimestamp(p[0] / 1000).strftime("%Y-%m-%d"),
                                 "c": p[1]} for p in prices]}
        print(sym, "points:", len(out[sym]["series"]))
    json.dump(out, open(HIST_FILE, "w"), indent=2)
    print("WROTE", HIST_FILE)


if __name__ == "__main__":
    fetch()
