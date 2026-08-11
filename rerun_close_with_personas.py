"""rerun_close_with_personas.py — proves the CLOSE meeting + paper book mark-to-market."""
import json
from schedule import run_meeting
from report import boss_report
from data_provider import load_snapshot, build_briefing

snap = load_snapshot()
briefing = build_briefing(snap)

close_views = {
    "macro": ("Day confirms the risk-off read. BTC closed at $64,155 — never reclaimed $65,147, "
              "the line that would have flipped us constructive. Fear gauge sits at 29, equities "
              "still gated, no catalyst to repair the regime. The opening FLAT call stands; "
              "conviction unchanged at 2. We stay sidelined. Dispersion: BNB +5.1%, ETH +4.7% "
              "holding, XRP -8.2% and HYPE -18.1% bleed."),
    "quant": ("BTC held the $63,771–$65,147 range into the close. Never reclaimed $65,147, "
              "printing -1.0% on 24h; lower bound $63,771 intact. FNG 29 sub-30 extreme fear. "
              "30d dispersion: BNB +5.1% leader, ETH +4.7%, XRP -8.2%, HYPE -18.1% laggard. "
              "Opening FLAT. Updated bias: FLAT, modestly bearish. No long trigger until $65,147 reclaim."),
    "sentiment": ("Fear at 29 didn't deepen into capitulation; stale fear, sellers exhausted not "
                  "strong. BNB/ETH quietly outperforming while XRP/HYPE leak — rotation is my tell. "
                  "End-of-day desks rotating, not adding. Bias flips from flat to cautiously long into weakness."),
    "risk": ("Sitting flat was the right call — no overnight gap risk into a half-blind tape. Tail "
             "risks overnight: macro headline or privacy-coin regulatory print (ZEC -3.5%) could snap "
             "correlations. Stance defensive. Invalidation of any future long: daily close below $63,771."),
}
cio_raw = ("DECISION: FLAT\nINSTRUMENT: crypto basket\n"
           "THESIS: BTC never reclaimed $65,147 and the range held, so Macro/Quant keep us flat "
           "despite Sentiment's stale-fear long tilt — preserves the +1%/month mandate by avoiding "
           "a low-edge overnight position.\nENTRY: none\nSTOP: none\nTARGET: n/a\nSIZE: flat\n"
           "CONVICTION: 2\nDESK DISSENT: Sentiment flips cautiously long; Macro/Quant/Risk hold flat.")

prev = {"kind": "OPENING", "decision": "FLAT", "instrument": "crypto basket",
        "conviction": "2", "thesis": "risk-off macro + tail risk; stand aside until BTC reclaims $65,147"}

def analyst_fn(system, user, agent):
    if agent["id"] == "cio":
        return cio_raw
    return close_views.get(agent["id"], "[no view]")

m = run_meeting("CLOSE", analyst_fn, prev_context=prev, snap=snap, briefing=briefing)
print(boss_report(m, "CLOSE"))
