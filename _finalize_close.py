import json
from datetime import date
from execution import place_order, save_position

path = r"C:\Users\Eze\Downloads\ai_hedge_fund\meeting_logs\close_%s.json" % date.today().isoformat()
m = {
    "kind": "CLOSE", "time": "17:30", "to_boss": True,
    "ts": "2026-08-11T17:30:00Z",
    "briefing": open(r"C:\Users\Eze\Downloads\ai_hedge_fund\briefing.txt").read(),
    "speakers": [
        {"id": "macro", "name": "Dr. Helena Voss", "role": "Macro Strategist",
         "view": ("Day confirms the risk-off read. BTC closed at $64,155 — never reclaimed "
                  "$65,147, the line that would have flipped us constructive. Fear gauge sits "
                  "at 29, equities still gated, no catalyst to repair the regime. The opening "
                  "FLAT call stands; conviction unchanged at 2. We stay sidelined. Note the "
                  "dispersion — BNB +5.1%, ETH +4.7% holding, but XRP -8.2% and HYPE -18.1% bleed.")},
        {"id": "quant", "name": "Kenji Arai", "role": "Quant / Systematic",
         "view": ("BTC held the range. $63,771 support intact; $65,147 resistance never "
                  "reclaimed — no break either side. FNG 29 = Fear, no capitulation. Internals "
                  "diverging: BNB 30d +5.1% strongest, ETH +4.7%; XRP -8.2%, HYPE -18.1% weakest. "
                  "Opening call FLAT. Bias: neutral-defensive. Triggers: lose $63,771 = downside; "
                  "reclaim $65,147 = breakout. Until one prints, position flat, wait for range to resolve.")},
        {"id": "sentiment", "name": "Mara Quinn", "role": "Sentiment & Flow Analyst",
         "view": ("Fear at 29 didn't deepen into capitulation — it's stale fear, the kind that "
                  "sits while weak hands bleed out quietly. BTC range-bound, no $65,147 reclaim, "
                  "but the lack of a flush tells me sellers are exhausted, not strong. BNB/ETH "
                  "quietly outperforming while XRP/HYPE leak — that rotation is my tell. End-of-day: "
                  "desks aren't adding, they're rotating. My bias flips from flat to cautiously long.")},
        {"id": "risk", "name": "Dmitri Sokolov", "role": "Head of Risk",
         "view": ("Sitting flat was the right call — no overnight gap risk taken into a gapped, "
                  "half-blind tape (equities still blocked). Tail risks overnight: a macro headline "
                  "or a privacy-coin regulatory print (ZEC -3.5%) could snap correlations to one. "
                  "Stance stays defensive. Invalidation of any future long: a daily close below "
                  "$63,771 on BTC.")},
    ],
    "cio_raw": ("DECISION: FLAT\nINSTRUMENT: crypto basket\n"
                "THESIS: BTC never reclaimed the $65,147 line that flips us constructive and the "
                "range structure remains intact, so Macro and Quant keep us flat despite Sentiment's "
                "stale-fear long tilt — we express only dispersion (BNB/ETH over XRP/HYPE) at the margin.\n"
                "ENTRY: none\nSTOP: none\nTARGET: n/a\nSIZE: flat\nCONVICTION: 2\n"
                "DESK DISSENT: Sentiment (Quinn) flips to cautiously long on stale fear; Macro/Quant/Risk hold flat."),
}
m["cio_call"] = {"DECISION": "FLAT", "INSTRUMENT": "crypto basket",
    "THESIS": "BTC never reclaimed $65,147; range intact. Flat stands, express only BNB/ETH-over-XRP/HYPE dispersion at margin.",
    "ENTRY": "none", "STOP": "none", "TARGET": "n/a", "SIZE": "flat", "CONVICTION": "2",
    "DESK DISSENT": "Sentiment flips cautiously long; Macro/Quant/Risk hold flat."}

json.dump(m, open(path, "w"), indent=2)
receipt = place_order(m["cio_call"])
position = dict(m["cio_call"]); position["_execution"] = receipt
save_position(position, path=r"C:\Users\Eze\Downloads\ai_hedge_fund\position_of_the_day.json")
print("CLOSE finalized. Decision:", m["cio_call"]["DECISION"], "| exec:", receipt["mode"])
