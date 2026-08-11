import json
from datetime import datetime, date

briefing = open(r"C:\Users\Eze\Downloads\ai_hedge_fund\briefing.txt").read()

macro = ("Morning. Fear & Greed at 29 — that's a risk-off regime, not a dip to buy. "
 "I lived through 2008 and 2022; this smells like the late-cycle grind where liquidity "
 "is quietly leaving the room. Biggest macro risk today is real rates and a strong dollar "
 "choking speculative assets — equities data's blocked, so we're flying half-blind. My "
 "directional bias on crypto is bearish-to-neutral: with BTC still 49% off its ATH and HYPE "
 "down 18% on the month, I'm not catching this falling knife. Defensive positioning.")

quant = ("BTC $64,155 mid-range, 24h band $63,771–$65,147 — mean-reverting, support "
 "$63,771, resistance $65,147. 7d +0.6%, 30d +0.3%: flat. ETH 30d +4.7% mild uptrend. "
 "BNB strongest, 7d +3.4%, 30d +5.1% — trending. SOL 7d +3.1% vs 30d -1.5%: bounce inside "
 "downtrend. XRP 7d -6.3%, 30d -8.2% and HYPE 30d -18.1%: clean bear trends. ZEC -3.5%, "
 "DOGE +1.4% noise. Fear & Greed 29 = risk-off. Bias: neutral — mean-reverting tape, "
 "long BNB/ETH, short XRP/HYPE.")

sentiment = ("Fear at 29 is cautious, not panic — the crowd's already de-risked, so most "
 "of the pain is positioned-for, not ahead. Look at the dispersion: BNB and ETH are showing "
 "real relative strength while XRP bleeds out and HYPE is down 18% on the month — that's "
 "rotation, not a flee. My read: fade the fear. Mildly bullish. Small long bias, trail your "
 "stops, and don't catch the HYPE knife — forced selling isn't done.")

minutes = {
    "kind": "OPENING",
    "time": "08:00",
    "to_boss": True,
    "ts": datetime.utcnow().isoformat() + "Z",
    "briefing": briefing,
    "speakers": [
        {"id": "macro", "name": "Dr. Helena Voss", "role": "Macro Strategist", "view": macro},
        {"id": "quant", "name": "Kenji Arai", "role": "Quant / Systematic", "view": quant},
        {"id": "sentiment", "name": "Mara Quinn", "role": "Sentiment & Flow Analyst", "view": sentiment},
    ],
    # risk + cio filled after subagents return
}
json.dump(minutes, open(r"C:\Users\Eze\Downloads\ai_hedge_fund\meeting_logs\opening_%s.json" % date.today().isoformat(), "w"), indent=2)
print("opening base written; awaiting risk + cio")
