import json, datetime
from datetime import date
from execution import place_order, save_position

base = r"C:\Users\Eze\Downloads\ai_hedge_fund\meeting_logs\opening_%s.json" % date.today().isoformat()
m = json.load(open(base))

risk = ("Sentiment wants to fade fear and nibble long — I don't buy it. Fear sits at 29 "
 "with majors flat and breadth rotting: XRP -8%, HYPE -18% over thirty days is alt "
 "capitulation, not a dip. Quant's BNB/ETH long versus XRP/HYPE short still carries net "
 "beta when correlations snap to one in a cascade. ZEC -3.5% flags privacy-coin regulatory "
 "tail risk. Stance: defensive — size down, no new gross.")
m["speakers"].append({"id": "risk", "name": "Dmitri Sokolov", "role": "Head of Risk", "view": risk})

cio_raw = ("DECISION: FLAT\nINSTRUMENT: crypto basket\n"
 "THESIS: Risk-off macro regime and unquantified tail-risk/invalidation risk outweigh a "
 "low-conviction contrarian fade-the-fear signal, so we stand aside until equities unblock "
 "and BTC reclaims $65,147 resistance.\n"
 "ENTRY: none\nSTOP: none\nTARGET: n/a\nSIZE: flat\nCONVICTION: 2\n"
 "DESK DISSENT: Macro and Risk saw a risk-off, tail-risk tape while Sentiment argued to "
 "fade Fear-29 with a small long.")
m["cio_raw"] = cio_raw
m["cio_call"] = {"DECISION": "FLAT", "INSTRUMENT": "crypto basket",
    "THESIS": "Risk-off macro + tail risk outweigh low-conviction sentiment fade; stand aside until BTC reclaims $65,147.",
    "ENTRY": "none", "STOP": "none", "TARGET": "n/a", "SIZE": "flat", "CONVICTION": "2",
    "DESK DISSENT": "Macro/Risk risk-off vs Sentiment's small long fade."}

json.dump(m, open(base, "w"), indent=2)

# execution (dry-run) + position of the day
receipt = place_order(m["cio_call"])
position = dict(m["cio_call"]); position["_execution"] = receipt
save_position(position, path=r"C:\Users\Eze\Downloads\ai_hedge_fund\position_of_the_day.json")
print("OPENING finalized. Decision:", m["cio_call"]["DECISION"], "| exec:", receipt["mode"])
