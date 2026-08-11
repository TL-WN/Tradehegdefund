"""
backtest.py
A small, honest vectorized backtester over the firm's REAL daily price history.
Strategies are expressed as signal functions on a close series. It reports return,
win-rate, max drawdown, and a buy&hold baseline so the desk can argue from evidence.

No ML. No lookahead (signals use only data available up to each bar).
"""
import json
import os

HIST_FILE = os.path.join(os.path.dirname(__file__), "history.json")


def load_history():
    if not os.path.exists(HIST_FILE):
        return {}
    return json.load(open(HIST_FILE))


def closes(sym):
    h = load_history()
    s = h.get(sym, {}).get("series", [])
    return [x["c"] for x in s], [x["t"] for x in s]


# ---------------- signal library ----------------
def sig_momentum(c, lookback=20):
    """1 if price above its lookback-mean (trend up), else -1. No position on first bars."""
    out = [0] * len(c)
    for i in range(lookback, len(c)):
        mean = sum(c[i - lookback:i]) / lookback
        out[i] = 1 if c[i] > mean else -1
    return out


def sig_meanreversion(c, lookback=20, z=1.5):
    out = [0] * len(c)
    for i in range(lookback, len(c)):
        win = c[i - lookback:i]
        m = sum(win) / lookback
        var = sum((x - m) ** 2 for x in win) / lookback
        sd = var ** 0.5
        if sd == 0:
            continue
        if c[i] < m - z * sd:
            out[i] = 1
        elif c[i] > m + z * sd:
            out[i] = -1
    return out


def sig_breakout(c, lookback=20):
    out = [0] * len(c)
    for i in range(lookback, len(c)):
        hi = max(c[i - lookback:i])
        lo = min(c[i - lookback:i])
        if c[i] > hi:
            out[i] = 1
        elif c[i] < lo:
            out[i] = -1
    return out


STRATEGIES = {
    "momentum_20d": ("20-day momentum (long when price > 20d mean, else flat/short)", sig_momentum),
    "meanrev_20d": ("20-day z-score mean reversion (long below -1.5σ, short above +1.5σ)", sig_meanreversion),
    "breakout_20d": ("20-day channel breakout (long new high, short new low)", sig_breakout),
}


def run(sym, signal_fn, fee_bps=5):
    """Daily rebalance to signal. Long/flat/short on close-to-close. Returns stats dict."""
    c, t = closes(sym)
    if len(c) < 30:
        return None
    sig = signal_fn(c)
    pos = 0          # current position (-1,0,1)
    ret = 0.0
    trades = 0
    wins = 0
    eq = [1.0]
    peak = 1.0
    maxdd = 0.0
    for i in range(1, len(c)):
        # entry/pnl from previous position using last bar's signal vs this bar's move
        target = sig[i - 1]
        if target != pos:
            if pos != 0:
                trades += 1
                # close previous at this open (approx via return)
            pos = target
        if pos != 0:
            r = (c[i] - c[i - 1]) / c[i - 1] * pos
            r -= (abs(pos) * fee_bps / 10000)
            ret += r
            eq.append(eq[-1] * (1 + r))
        else:
            eq.append(eq[-1])
        peak = max(peak, eq[-1])
        maxdd = max(maxdd, (peak - eq[-1]) / peak)
    # buy&hold baseline
    bh = (c[-1] - c[0]) / c[0]
    # win-rate: count positive signal periods
    pos_rets = []
    p = 0
    for i in range(1, len(c)):
        tg = sig[i - 1]
        if tg != p:
            p = tg
        if p != 0:
            rr = (c[i] - c[i - 1]) / c[i - 1] * p
            pos_rets.append(rr)
    wins = sum(1 for x in pos_rets if x > 0)
    return {
        "sym": sym,
        "bars": len(c),
        "strat_return_pct": round(ret * 100, 2),
        "buyhold_return_pct": round(bh * 100, 2),
        "trades": trades,
        "win_rate_pct": round(wins / len(pos_rets) * 100, 1) if pos_rets else 0.0,
        "max_drawdown_pct": round(maxdd * 100, 2),
        "vs_buyhold_pct": round((ret - bh) * 100, 2),
        "final_equity": round(eq[-1], 4),
    }


def backtest_all(strategy_key, syms=("BTC", "ETH")):
    if strategy_key not in STRATEGIES:
        return None
    name, fn = STRATEGIES[strategy_key]
    return {"strategy": strategy_key, "name": name, "results": {s: run(s, fn) for s in syms}}


if __name__ == "__main__":
    for k in STRATEGIES:
        print(k, "->", backtest_all(k))
