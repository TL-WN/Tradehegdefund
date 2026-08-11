"""
demo_desk.py  —  SAFE PAPER-ONLY demo trader for the dashboard chart.

Why this exists:
  The hedge-fund personas (CIO/Macro/etc.) only run on the laptop cron. On the
  cloud (Render / GitHub Action) there is no LLM, so the paper book stays flat and
  the dashboard's equity curve + position overlay never move. This module opens and
  closes *clearly-labeled* paper positions using simple, deterministic rules so the
  chart is visually alive 24/7.

Safety rails (all inherited from book.py):
  - PAPER ONLY. Never touches a real exchange. No EXEC_LIVE path exists.
  - Respects the -7% drawdown HALT (book.deploy / close_position refuse when halted).
  - Leverage capped at MAX_LEVERAGE (100x) — demo uses <=3x.
  - Every action is logged with a "DEMO" tag so it is never confused with the personas.

Rules (mean-reversion on sentiment):
  - Flat + Fear&Greed < 35  -> LONG  3% margin x3, stop -2%, target +4%
  - Flat + Fear&Greed > 70  -> SHORT 2% margin x2, stop +2%, target -4%
  - In position: exit on stop/target hit, or after holding >= 5 closes (trailing scratch)
"""
import json
import datetime
import book

LOG_FILE = "demo_logs/demo_tape.jsonl"


def _log(msg):
    import os
    os.makedirs("demo_logs", exist_ok=True)
    line = {"ts": datetime.datetime.utcnow().isoformat() + "Z", "msg": msg}
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(line) + "\n")
    print("[demo]", msg)


def _snap():
    # reuse the dashboard's price source, wrapped in the shape book.price_for expects
    try:
        from dashboard_app import refresh_prices
        prices, _ = refresh_prices()
        return {"crypto": {s: {"price": (p or {}).get("price")} for s, p in (prices or {}).items()}}
    except Exception:
        return {}


def _fng():
    try:
        from dashboard_app import refresh_prices
        _, fng = refresh_prices()
        v = (fng or {}).get("value")
        if v is not None:
            return int(v)
    except Exception:
        pass
    try:
        from dashboard_app import _load_json
        v = _load_json("market_snapshot.json", {}).get("fng", {}).get("value")
        return int(v) if v is not None else None
    except Exception:
        return None


def run_once():
    """One demo tick: open, manage, or close a paper position."""
    snap = _snap()
    fng = _fng()
    b = book.load()
    op = b.get("open_position")

    if b.get("halted"):
        _log("book HALTED — demo stands aside (auto-resumes after cooldown).")
        return b

    if not op:
        # ---- entry logic ----
        if fng is None:
            _log("no FNG sentiment — standing aside.")
            return b
        if fng < 35:
            decision = {"DECISION": "LONG", "INSTRUMENT": "BTC", "SIZE": "3%",
                        "LEVERAGE": "3", "STOP": None, "TARGET": None}
            # compute stop/target from live BTC entry
            px = book.price_for("BTC", snap)
            if px:
                decision["STOP"] = round(px * 0.98, 2)
                decision["TARGET"] = round(px * 1.04, 2)
            b, note = book.deploy(decision, snap)
            _log(f"DEMO OPEN LONG (FNG {fng}=fear): {note}")
        elif fng > 70:
            decision = {"DECISION": "SHORT", "INSTRUMENT": "BTC", "SIZE": "2%",
                        "LEVERAGE": "2", "STOP": None, "TARGET": None}
            px = book.price_for("BTC", snap)
            if px:
                decision["STOP"] = round(px * 1.02, 2)
                decision["TARGET"] = round(px * 0.96, 2)
            b, note = book.deploy(decision, snap)
            _log(f"DEMO OPEN SHORT (FNG {fng}=greed): {note}")
        else:
            _log(f"FNG {fng} neutral — demo flat, no new position.")
        return b

    # ---- manage open position ----
    px = book.price_for(op.get("symbol") or op.get("instrument"), snap)
    if px is None:
        _log("price unavailable — holding position.")
        return b
    entry = op.get("entry")
    stop = op.get("stop")
    target = op.get("target")
    side = op.get("side")
    hit = None
    if side == "LONG":
        if stop and px <= stop: hit = f"stop {stop}"
        elif target and px >= target: hit = f"target {target}"
    else:  # SHORT
        if stop and px >= stop: hit = f"stop {stop}"
        elif target and px <= target: hit = f"target {target}"

    # holding-period scratch exit
    opened = op.get("opened", "")
    held_days = 0
    try:
        d0 = datetime.date.fromisoformat(opened)
        held_days = (datetime.date.today() - d0).days
    except Exception:
        held_days = 0

    if hit:
        b, note = book.close_position(reason=f"DEMO {hit}")
        _log(f"DEMO CLOSE ({hit}): {note}")
    elif held_days >= 5:
        b, note = book.close_position(reason="DEMO holding-period scratch")
        _log(f"DEMO CLOSE (scratch after {held_days}d): {note}")
    else:
        _log(f"DEMO HOLD {side} {op.get('symbol')} @ {entry} | now {px} | "
             f"stop {stop} target {target}")
    return b


if __name__ == "__main__":
    run_once()
