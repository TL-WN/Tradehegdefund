"""
book.py
Paper-equity engine for the firm. Each persona runs a notional book (simulated, no
real money). The CIO's daily decision deploys a paper position sized to the mandate;
at CLOSE we mark it to market vs the real price and book the day's P&L.

FIRM CONSTRAINTS (wired into the book, mechanically enforced):
  - LEVERAGE: up to 1:100. Notional = margin% of equity x leverage.
  - MAX DRAWDOWN: -7% from peak equity is a HARD STOP-OUT. If the account value
    (equity + unrealized) would fall more than 7% below its peak, every open
    position is force-closed and the book is HALTED for the rest of the month.
  - OBJECTIVE: +1.0% net return per calendar month.

Nothing here touches a broker. It is a ledger for the boss to read.
"""
import json
import os
import datetime

BOOK_FILE = os.path.join(os.path.dirname(__file__), "paper_book.json")

STARTING_EQUITY = 1_000_000.0
MONTHLY_OBJECTIVE_PCT = 1.0
MAX_LEVERAGE = 100
MAX_DRAWDOWN_PCT = 7.0          # hard stop-out threshold
HALT_COOLDOWN_H = 48             # after a -7% halt, book auto-resumes after this many hours


def _default_book():
    today = datetime.date.today().isoformat()
    return {
        "starting_equity": STARTING_EQUITY,
        "equity": STARTING_EQUITY,           # realized book value (cash after closed trades)
        "peak_equity": STARTING_EQUITY,       # peak account value this month (for dd)
        "open_position": None,                # {instrument, side, margin_pct, leverage, notional, entry, opened}
        "month": today[:7],                   # YYYY-MM
        "month_start_equity": STARTING_EQUITY,
        "realized_mtd": 0.0,
        "max_leverage_used": 0,
        "max_drawdown_mtd": 0.0,              # worst peak-to-trough % this month
        "drawdown_halts": 0,
        "halted": False,
        "halted_at": None,                   # ISO timestamp when the halt triggered
        "trades": [],
        "updated": today,
    }


def load():
    if not os.path.exists(BOOK_FILE):
        b = _default_book()
        save(b)
        return b
    return json.load(open(BOOK_FILE))


def save(b):
    json.dump(b, open(BOOK_FILE, "w"), indent=2)


# ---------------- pricing ----------------
def price_for(instrument, snap):
    if not snap:
        return None
    c = snap.get("crypto", {})
    sym = (instrument or "").upper()
    if sym in c:
        return c[sym].get("price")
    for k in c:
        if k.startswith(sym[:3]):
            return c[k].get("price")
    return None


# ---------------- valuation ----------------
def _unrealized(op, snap):
    if not op:
        return 0.0
    px = price_for(op["instrument"], snap)
    if not px or not op.get("entry"):
        return 0.0
    if op["side"] == "LONG":
        ret = (px - op["entry"]) / op["entry"]
    else:
        ret = (op["entry"] - px) / op["entry"]
    return op["notional"] * ret


def account_value(b, snap):
    return b["equity"] + _unrealized(b.get("open_position"), snap)


def _update_peak(b, snap):
    av = account_value(b, snap)
    if av > b["peak_equity"]:
        b["peak_equity"] = av
    dd = (b["peak_equity"] - av) / b["peak_equity"] * 100.0 if b["peak_equity"] else 0.0
    if dd > b["max_drawdown_mtd"]:
        b["max_drawdown_mtd"] = dd
    return dd


# ---------------- month rollover ----------------
def _rollover_month(b):
    today = datetime.date.today()
    ym = today.strftime("%Y-%m")
    if b.get("month") != ym:
        b["month"] = ym
        b["month_start_equity"] = b["equity"]
        b["realized_mtd"] = 0.0
        # monthly trackers are reset by monthly_scorecard(); default-safe here too
        b["max_leverage_used"] = 0
        b["max_drawdown_mtd"] = 0.0
        b["drawdown_halts"] = 0
        b["halted"] = False
    return b


# ---------------- deploy (OPENING) ----------------
def _parse_margin_pct(s, default=0.0):
    if not s:
        return default
    s = str(s).lower()
    try:
        if "%" in s:
            return float(s.replace("%", "").strip())
        if "flat" in s or "none" in s:
            return 0.0
        return float(s.split()[0])
    except Exception:
        return default


def _parse_leverage(s):
    try:
        lev = int(float(str(s).split()[0]))
    except Exception:
        lev = 1
    return max(1, min(MAX_LEVERAGE, lev))


def deploy(decision, snap=None):
    b = load()
    _rollover_month(b)
    # auto-resume a halt if the cooldown has elapsed (so the next opening can trade)
    _maybe_resume(b)
    snap = snap or {}
    d = decision or {}

    if b["halted"]:
        save(b)
        return b, "BOOK HALTED after -7% drawdown — no new positions until the cooldown clears."

    # close any prior open position before a fresh deploy
    if b["open_position"]:
        b = _realize(b, snap, reason="replaced by new opening decision")

    side = (d.get("DECISION") or "FLAT").upper()
    instr = d.get("INSTRUMENT") or "crypto basket"
    margin_pct = _parse_margin_pct(d.get("SIZE"), default=0.0 if side == "FLAT" else 2.0)
    lev = _parse_leverage(d.get("LEVERAGE", "1"))

    if side == "FLAT" or margin_pct <= 0:
        b["open_position"] = None
        note = "Flat — no paper capital deployed."
    else:
        px = price_for(instr, snap)
        notional = b["equity"] * (margin_pct / 100.0) * lev
        b["open_position"] = {
            "instrument": instr, "symbol": instr.upper(), "side": side, "margin_pct": margin_pct, "leverage": lev,
            "notional": notional, "entry": px,
            "qty": (notional / px) if px else 0.0,
            "stop": d.get("STOP"), "target": d.get("TARGET"),
            "opened": datetime.date.today().isoformat(),
        }
        b["max_leverage_used"] = max(b["max_leverage_used"], lev)
        note = (f"Opened paper {side} {instr} @ {px} | margin {margin_pct}% x{lev} "
                f"| notional ${notional:,.0f} ({(margin_pct*lev):.0f}% gross exposure)")
    _update_peak(b, snap)
    save(b)
    return b, note


def _realize(b, snap, reason="close"):
    op = b.get("open_position")
    if not op:
        return b
    pnl = _unrealized(op, snap)
    b["equity"] += pnl
    b["realized_mtd"] += pnl
    b["trades"].append({
        "instrument": op["instrument"], "side": op["side"], "notional": op["notional"],
        "leverage": op.get("leverage"), "entry": op["entry"],
        "exit": price_for(op["instrument"], snap), "pnl": pnl, "reason": reason,
        "closed": datetime.date.today().isoformat(),
    })
    b["open_position"] = None
    return b


# ---------------- mark to market (MIDDAY / CLOSE) ----------------
def _maybe_resume(b):
    """Auto-clear a halt once HALT_COOLDOWN_H has elapsed since halted_at."""
    if b["halted"] and b["halted_at"]:
        try:
            t = datetime.datetime.fromisoformat(b["halted_at"].replace("Z", ""))
        except Exception:
            t = None
        if t and (datetime.datetime.utcnow() - t).total_seconds() >= HALT_COOLDOWN_H * 3600:
            b["halted"] = False
            b["halted_at"] = None
            return True
    return False


def mark_to_market(snap=None, flatten=False):
    b = load()
    _rollover_month(b)
    resumed = _maybe_resume(b)
    snap = snap or {}
    dd = _update_peak(b, snap)

    # HARD STOP-OUT: if account value is >7% below peak, force-close + halt
    halt_note = None
    if resumed:
        halt_note = f"HALT auto-cleared after {HALT_COOLDOWN_H}h cooldown — book resumed."
    if dd >= MAX_DRAWDOWN_PCT and b["open_position"]:
        b = _realize(b, snap, reason=f"DRAWDOWN HALT (-{dd:.2f}% >= -{MAX_DRAWDOWN_PCT}%)")
        b["halted"] = True
        b["halted_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        b["drawdown_halts"] += 1
        halt_note = f"DRAWDOWN HALT triggered at -{dd:.2f}%: all positions closed, book halted (auto-resumes after {HALT_COOLDOWN_H}h)."
    elif flatten:
        b = _realize(b, snap, reason="end-of-day mark")

    _update_peak(b, snap)
    save(b)
    return b, dd, halt_note


def close_position(reason="demo close", snap=None):
    """Public helper: realize the open paper position (books pnl + appends a trade).
    Respects an active drawdown halt (won't open, and will not clear a halt)."""
    b = load()
    _rollover_month(b)
    _maybe_resume(b)
    snap = snap or {}
    if b["halted"]:
        save(b)
        return b, "BOOK HALTED — position not closed until cooldown clears."
    if not b["open_position"]:
        save(b)
        return b, "No open position to close."
    b = _realize(b, snap, reason=reason)
    _update_peak(b, snap)
    save(b)
    return b, f"Closed paper position ({reason})."


def mtd_progress(b=None, account_value_override=None):
    b = b or load()
    av = account_value_override if account_value_override is not None else b["equity"]
    mtd_ret = (av - b["month_start_equity"]) / b["month_start_equity"] * 100.0
    obj = MONTHLY_OBJECTIVE_PCT
    return {
        "month": b["month"],
        "equity": round(b["equity"], 2),
        "account_value": round(av, 2),
        "month_start_equity": b["month_start_equity"],
        "mtd_return_pct": round(mtd_ret, 3),
        "objective_pct": obj,
        "progress_pct_of_target": round(mtd_ret / obj * 100.0, 1) if obj else 0.0,
        "gap_to_target_pct": round(obj - mtd_ret, 3),
        "max_leverage_used": b["max_leverage_used"],
        "max_drawdown_mtd": round(b["max_drawdown_mtd"], 2),
        "halted": b["halted"],
        "drawdown_halts": b["drawdown_halts"],
    }


# ---------------- monthly scorecard ----------------
def monthly_scorecard():
    """Report the month that just ended, then reset monthly trackers. Boss-facing."""
    b = load()
    ym = b["month"]
    month_trades = [t for t in b.get("trades", []) if t.get("closed", "").startswith(ym)]
    wins = [t for t in month_trades if t["pnl"] > 0]
    losses = [t for t in month_trades if t["pnl"] <= 0]
    gross = sum(t["pnl"] for t in month_trades)
    ret_pct = (b["equity"] - b["month_start_equity"]) / b["month_start_equity"] * 100.0

    card = {
        "month_reported": ym,
        "return_pct": round(ret_pct, 3),
        "objective_pct": MONTHLY_OBJECTIVE_PCT,
        "hit": ret_pct >= MONTHLY_OBJECTIVE_PCT,
        "trades": len(month_trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(month_trades) * 100.0, 1) if month_trades else 0.0,
        "gross_pnl": round(gross, 2),
        "realized_mtd": round(b["realized_mtd"], 2),
        "max_leverage_used": b["max_leverage_used"],
        "max_drawdown_mtd_pct": round(b["max_drawdown_mtd"], 2),
        "drawdown_halts": b["drawdown_halts"],
        "halted": b["halted"],
        "equity": round(b["equity"], 2),
        "leverage_ceiling": MAX_LEVERAGE,
        "drawdown_limit_pct": MAX_DRAWDOWN_PCT,
    }
    # reset monthly trackers for the new month
    _rollover_month(b)
    b["max_leverage_used"] = 0
    b["max_drawdown_mtd"] = 0.0
    b["drawdown_halts"] = 0
    b["halted"] = False
    save(b)
    return card


if __name__ == "__main__":
    b = load()
    print(json.dumps(b, indent=2))
    print("MTD:", mtd_progress(b))
