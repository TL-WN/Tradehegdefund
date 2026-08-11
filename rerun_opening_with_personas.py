"""
rerun_opening_with_personas.py
Re-runs today's OPENING meeting with the ALREADY-CAPTURED real persona views
(from the live subagents earlier), pushes them through the schedule engine so the
paper book deploys and the boss report includes the PAPER BOOK / +1% section.
"""
import json, datetime
from datetime import date
from schedule import run_meeting, MEETINGS
from report import boss_report
from data_provider import load_snapshot, build_briefing

snap = load_snapshot()
briefing = build_briefing(snap)

views = {
    "macro": ("Morning. Fear & Greed at 29 — that's a risk-off regime, not a dip to buy. "
              "I lived through 2008 and 2022; this smells like the late-cycle grind where "
              "liquidity is quietly leaving the room. Biggest macro risk today is real rates "
              "and a strong dollar choking speculative assets. My directional bias on crypto "
              "is bearish-to-neutral: with BTC still 49% off its ATH and HYPE down 18% on the "
              "month, I'm not catching this falling knife. Defensive positioning."),
    "quant": ("BTC $64,155 mid-range, 24h band $63,771–$65,147 — mean-reverting, support "
              "$63,771, resistance $65,147. 7d +0.6%, 30d +0.3%: flat. ETH 30d +4.7% mild "
              "uptrend. BNB strongest, 7d +3.4%, 30d +5.1% — trending. SOL 7d +3.1% vs 30d "
              "-1.5%: bounce inside downtrend. XRP 7d -6.3%, 30d -8.2% and HYPE 30d -18.1%: "
              "clean bear trends. Bias: neutral — mean-reverting tape, long BNB/ETH, short XRP/HYPE."),
    "sentiment": ("Fear at 29 is cautious, not panic — the crowd's already de-risked, so most "
                  "of the pain is positioned-for, not ahead. BNB and ETH show real relative "
                  "strength while XRP bleeds and HYPE is down 18% on the month — rotation, not "
                  "a flee. My read: fade the fear. Mildly bullish. Small long bias, trail stops."),
    "risk": ("Sentiment wants to fade fear and nibble long — I don't buy it. Fear sits at 29 "
             "with majors flat and breadth rotting: XRP -8%, HYPE -18% over thirty days is alt "
             "capitulation, not a dip. Quant's BNB/ETH long vs XRP/HYPE short still carries net "
             "beta when correlations snap to one. Stance: defensive — size down, no new gross. "
             "Hard invalidation: BTC closing below $63,771, I cut everything."),
}

cio_raw = ("DECISION: FLAT\nINSTRUMENT: crypto basket\n"
           "THESIS: Risk-off macro + tail risk outweigh a low-conviction sentiment fade; stand "
           "aside until BTC reclaims $65,147 — preserves the +1%/month mandate by not forcing a "
           "low-edge trade.\nENTRY: none\nSTOP: none\nTARGET: n/a\nSIZE: flat\nCONVICTION: 2\n"
           "DESK DISSENT: Macro/Risk risk-off vs Sentiment's small long fade.")

def analyst_fn(system, user, agent):
    if agent["id"] == "cio":
        return cio_raw
    return views.get(agent["id"], "[no view]")

m = run_meeting("OPENING", analyst_fn, snap=snap, briefing=briefing)
print(boss_report(m, "OPENING"))
