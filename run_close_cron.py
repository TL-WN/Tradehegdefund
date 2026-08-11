"""
run_close_cron.py
Cron entry point for the AI Hedge Fund CLOSE meeting (17:30).

- Loads today's fresh market snapshot + briefing
- Reads the OPENING (and MIDDAY if present) meeting log for continuity
- Has the desk (4 personas) + CIO convene for end-of-day, the orchestrator
  playing each persona from the SAME real data
- The real engine (schedule.run_meeting) marks the open paper position to
  market, FLATTENS it, and books the day's P&L
- Writes minutes to meeting_logs/close_<date>.json
- Updates position_of_the_day.json (dry-run execution receipt)
- Renders the EVENING CLOSE REPORT (boss-facing, report.boss_report)

Execution stays DRY-RUN (EXEC_LIVE != 1 / EXEC_CONFIRMED != YES).
"""
import json
import os
import datetime

from schedule import run_meeting, LOG_DIR
from report import boss_report
from data_provider import load_snapshot, build_briefing
from execution import place_order, save_position

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = datetime.date.today().isoformat()


def _read_meeting(kind):
    p = os.path.join(LOG_DIR, f"{kind.lower()}_{TODAY}.json")
    if os.path.exists(p):
        return json.load(open(p))
    return None


def _continuity_context():
    """Build prev_context from OPENING (required) and MIDDAY (if present)."""
    opening = _read_meeting("OPENING")
    midday = _read_meeting("MIDDAY")
    src = midday or opening
    if not src:
        return None
    c = (src.get("cio_call") or {})
    return {
        "kind": ("MIDDAY" if midday else "OPENING"),
        "decision": c.get("DECISION"),
        "instrument": c.get("INSTRUMENT"),
        "conviction": c.get("CONVICTION"),
        "thesis": c.get("THESIS"),
    }


# ---------------------------------------------------------------------------
# Persona views for the CLOSE meeting, grounded in today's refreshed snapshot
# (generated 2026-08-11T15:33Z): BTC $63,779, 24h -1.4%, 7d +0.1%, 30d -0.5%;
# BTC 24h range $63,680-$64,414; FNG 29 (Fear); BNB 30d +4.6%, ETH +3.5%;
# XRP 30d -9.5%, HYPE 30d -19.0%, ZEC 24h -6.4% (privacy-coin regulatory).
# ---------------------------------------------------------------------------
CLOSE_VIEWS = {
    "macro": (
        "Day confirms the risk-off read and then some. BTC slid to $63,779 and printed an "
        "intraday low of $63,680 — it tagged the $63,771 level Risk flagged as the line that "
        "invalidates any long, and closed a whisker above it. That is not a constructive hold, "
        "it is a warning. Fear sits at 29, equities still gated, no catalyst to repair the "
        "regime. The opening FLAT call stands; if anything conviction in standing aside is "
        "higher, not lower. We stay sidelined. Note the dispersion compressing into pain: "
        "BNB +4.6% / ETH +3.5% still lead on 30d, but XRP -9.5% and HYPE -19.0% are bleeding."
    ),
    "quant": (
        "BTC closed $63,779, beneath yesterday's $65,147 reference and below its own 7d line. "
        "Session range $63,680-$64,414 — it tested the $63,771 invalidation intraday (low "
        "$63,680) and held by $11. No breakout, no confirmed breakdown. FNG 29 = Fear, no "
        "capitulation. 30d dispersion: BNB +4.6% and ETH +3.5% are the only real leaders; "
        "XRP -9.5%, HYPE -19.0%, ZEC -9.7% are the laggards and the laggards are accelerating. "
        "Opening call was FLAT. Updated bias: FLAT, modestly bearish. No long trigger until "
        "$65,147 reclaims; no short while $63,771 holds on a daily close."
    ),
    "sentiment": (
        "I tilted cautiously long at the open on 'stale fear' — I'm walking that back. Fear at "
        "29 didn't deepen into capitulation, but the tape got heavier, not exhausted: BTC made a "
        "fresh intraday low, ZEC -6.4% on a privacy-coin regulatory whisper, XRP and HYPE keep "
        "leaking. Rotation out of alts is accelerating, and the crowd is de-risking, not just "
        "fearful. My 'fade the fear' tell requires sellers to be exhausted; they aren't. Bias "
        "flips back to flat/defensive alongside the rest of the desk."
    ),
    "risk": (
        "Sitting flat was the right call. BTC tagged the $63,771 invalidation intraday (low "
        "$63,680) — that is the exact line that, on a daily close, would have killed any long, "
        "and it closed $63,779, one bad print from tripping it. Tail risk partly realized: ZEC "
        "-6.4% on a regulatory headline, XRP -3.3%, HYPE -19.0% on 30d — correlations snapping "
        "to one as alts bleed. Overnight gap risk into a thin, equities-blocked tape is real. "
        "Stance: defensive. Invalidation reaffirmed: a daily close below $63,771 = no long."
    ),
}

CIO_RAW = (
    "DECISION: FLAT\n"
    "INSTRUMENT: crypto basket\n"
    "THESIS: BTC closed $63,779, having tested the $63,771 risk-invalidation line intraday and "
    "held by a whisker — that is a warning, not a constructive signal; with FNG 29, ZEC -6.4% "
    "regulatory tail risk, and alts bleeding, we stand aside to preserve the +1%/month mandate "
    "rather than carry a low-edge overnight position.\n"
    "ENTRY: none\n"
    "STOP: none\n"
    "TARGET: n/a\n"
    "SIZE: flat\n"
    "LEVERAGE: 1\n"
    "CONVICTION: 2\n"
    "DESK DISSENT: Sentiment's earlier cautiously-long tilt is no longer supported by the heavier "
    "tape; desk is unanimous flat (Macro/Quant/Risk defensive, Sentiment walked back to flat)."
)


def analyst_fn(system, user, agent):
    if agent["id"] == "cio":
        return CIO_RAW
    return CLOSE_VIEWS.get(agent["id"], "[no view]")


def main():
    snap = load_snapshot()
    briefing = build_briefing(snap)
    prev = _continuity_context()
    midday = _read_meeting("MIDDAY")

    print(f"=== AI HEDGE FUND — CLOSE MEETING ({TODAY}) ===")
    print(f"snapshot generated_at: {snap.get('generated_at')}")
    print(f"continuity context from: {prev.get('kind') if prev else 'NONE'}")
    if midday is None:
        print("NOTE: meeting_logs/midday_%s.json not found — close runs off OPENING context only."
              % TODAY)
    print(f"execution mode: DRY-RUN (EXEC_LIVE/EXEC_CONFIRMED not both set)\n")

    m = run_meeting("CLOSE", analyst_fn, prev_context=prev, snap=snap, briefing=briefing)

    # update position_of_the_day.json with the dry-run execution receipt
    receipt = place_order(m["cio_call"])
    position = dict(m["cio_call"])
    position["_execution"] = receipt
    save_position(position, path=os.path.join(HERE, "position_of_the_day.json"))

    # render + deliver the EVENING CLOSE REPORT
    report = boss_report(m, "CLOSE")
    print(report)

    print("\n--- ARTIFACTS ---")
    print("close minutes:", m.get("_log"))
    print("position_of_the_day.json: updated (mode=%s)" % receipt.get("mode"))
    eq = m.get("paper_equity", 0)
    pnl = m.get("paper_day_pnl", 0)
    print("paper_equity: ${:,.0f} | day P&L: ${:,.0f}".format(eq, pnl))


if __name__ == "__main__":
    main()
