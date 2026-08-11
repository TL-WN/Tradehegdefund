"""
run_ci.py
Offline engine run for CI / cloud (no browser, no LLM, no subagents).
Runs the deterministic parts of the firm so the dashboard stays data-live 24/7:
  - fetch market snapshot + price history (stdlib HTTP, multi-source fallback)
  - refresh research backtests (real historical data)
  - generate offline news brief from live prices + F&G
  - mark the paper book to market
  - write a rule-based CIO call (clearly labelled "automated") so the desk panel
    is never empty even when the laptop personas aren't running.
No network credentials, no ML. Safe to run on GitHub Actions / Render cron.
"""
import os
import sys
import json
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

sys.path.insert(0, HERE)


def main():
    from dashboard_app import refresh_prices
    import research
    import news
    import book

    print("[ci] refreshing live prices...")
    prices, fng = refresh_prices()
    fng_val = (fng or {}).get("value")

    # --- research backtests (offline, real history) ---
    print("[ci] running research backtests...")
    try:
        # ensure we have recent history to backtest on
        try:
            import fetch_history
            fetch_history.main() if hasattr(fetch_history, "main") else None
        except Exception as e:
            print("[ci] history fetch skipped:", e)
        if hasattr(research, "backtest_all"):
            for key in getattr(research, "CATALOGUE", {}):
                try:
                    research.backtest_all(key)
                except Exception as e:
                    print("[ci] backtest skipped for", key, ":", e)
        elif hasattr(research, "refresh_all"):
            research.refresh_all() if hasattr(research, "refresh_all") else None
    except Exception as e:
        print("[ci] research refresh skipped:", e)

    # --- offline news brief ---
    print("[ci] generating offline news brief...")
    news.offline_brief(prices=prices, fng_value=fng_val)

    # --- mark book to market ---
    print("[ci] marking book to market...")
    b = book.load()
    price_map = {s: (prices.get(s, {}) or {}).get("price") for s in ("BTC", "ETH", "BNB", "SOL", "XRP")}
    res = book.mark_to_market(b, price_map)
    book.save(res[0])

    # --- rule-based CIO call (automated, not persona) ---
    print("[ci] synthesizing automated CIO call...")
    _write_automated_meeting(prices, fng_val, b)

    print("[ci] done. Artifacts written.")


def _write_automated_meeting(prices, fng_val, book_state):
    """Simple deterministic CIO heuristic so the desk panel is never empty.
    NOT the persona meeting — clearly labelled automated/rule-based."""
    btc = (prices.get("BTC") or {}).get("price")
    eth = (prices.get("ETH") or {}).get("price")
    chg = (prices.get("BTC") or {}).get("chg24h") or 0
    fng = int(fng_val) if fng_val else 50

    if chg <= -3 and fng < 40:
        dec, conv, thesis = "SHORT", 3, "Risk-off: BTC down >3% and F&G in fear. Fade rallies."
    elif chg >= 3 and fng > 55:
        dec, conv, thesis = "LONG", 3, "Momentum + crowd greed. Trend-follow with a tight stop."
    elif fng < 40:
        dec, conv, thesis = "FLAT", 3, "Fear regime, no edge. Stay flat, preserve capital."
    elif fng > 60:
        dec, conv, thesis = "LONG", 2, "Greed regime, cautious long into strength."
    else:
        dec, conv, thesis = "FLAT", 2, "Range/neutral regime. No edge, stay flat."

    today = datetime.date.today().isoformat()
    meeting = {
        "kind": "OPENING",
        "date": today,
        "generated_by": "ci_automated",
        "note": "Automated rule-based call (no LLM). Persona meetings run on the laptop.",
        "decision": dec,
        "conviction": conv,
        "thesis": thesis,
        "prices": {s: (prices.get(s) or {}).get("price") for s in ("BTC", "ETH", "BNB", "SOL", "XRP")},
        "fng": fng_val,
        "speakers": [
            {"role": "Automated Engine", "view": thesis}
        ],
    }
    os.makedirs("meeting_logs", exist_ok=True)
    fn = os.path.join("meeting_logs", f"opening_{today}.json")
    # don't overwrite a real persona meeting from the same day
    if os.path.exists(fn):
        existing = json.load(open(fn))
        if existing.get("generated_by") != "ci_automated":
            print("[ci] keeping laptop persona meeting; skipping automated overwrite.")
            return
    json.dump(meeting, open(fn, "w"), indent=2)


if __name__ == "__main__":
    main()
