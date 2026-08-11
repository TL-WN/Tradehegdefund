import json
from datetime import date
from report import boss_report
from news import latest, format_for_meeting
from book import _default_book, save, deploy, mtd_progress

# reset book for clean demo
save(_default_book())

M = date.today().isoformat()
# captured live persona views (news-aware)
views = {
 "macro": "Liquidity regime remains deflationary near-term: Riot's forced BTC sale to fund a $9.1B AI pivot plus Saylor distribution adds supply just as L2 TVL hits a two-year low — a structural demand warning for ETH. BlackRock's bottom signal and persistent 29 Fear noted, but the regime is still risk-off.",
 "quant": "BTC 64,155, -1.0% 24h, pinned in 63,771–65,147 band (mid 64,459), -49% vs ATH 126,080. FNG 29 = fear. Bear flows dominate: Riot + Saylor supply = ~4–6k BTC overhang; ETH L2 TVL 2-yr low = structural ETH drag. Bulls: BlackRock bottom signal, Strategy bid. Range intact.",
 "news": "Three stories move the tape today. Supply overhang first: Riot selling BTC to fund its $9.1B AI deal, plus reports Saylor trimmed — real near-term pressure, though 'Saylor dumped' is partly FUD; Strategy calls itself an 'amplified Bitcoin play' and will resume buying. Second: BlackRock's bullish bottom signal + Strategy bid = genuine demand. Third: ETH L2 TVL 2-yr low is structural, slower-burn. Debanking + Kazakhstan are watch-items, not today's movers.",
 "sentiment": "Fear 29 with Riot dumping and Saylor trimming — the crowd's already positioned for pain, not discovering it. That's the setup I fade: real distribution is happening, but the panic's priced, and BlackRock's bottom signal plus Strategy still buying tells me smart money isn't capitulating. Crowd's bearish, flows washing.",
 "risk": "Supply overhang is the live risk: Riot's $9.1B AI pivot plus Saylor trimming could hit the tape faster than BlackRock's 'bottom signal' absorbs it. I don't trust FNG 29 — fear can deepen. Tail I'm watching: UK debanking contagion and ETH L2 TVL at a 2-yr low signal broader risk-off. Invalidation: a clean BTC close below 63,771.",
}
cio_raw = ("DECISION: LONG\nINSTRUMENT: BTC/USD perpetual, 3x\n"
 "THESIS: Range intact; FNG 29 = stale crowd fear. Supply overhang real but Saylor leg partly FUD (Reed); Riot forced sale is the genuine flow. Genuine demand from BlackRock bottom signal + Strategy bid. Range-fade the fear, not a directional bet.\n"
 "ENTRY: market (within range)\nSTOP: 63,771 close (hard invalidation, Sokolov)\nTARGET: 65,147 range high / reclaim\nSIZE: 5% of book margin\nLEVERAGE: 3\nCONVICTION: 3\n"
 "DESK DISSENT: Risk wanted FLAT/defensive on supply overhang; desk split — Macro/Quant neutral-defensive, Sentiment/News more constructive on stale fear + Strategy bid.")

nb = format_for_meeting(latest())
from schedule import _parse_cio
call = _parse_cio(cio_raw)

minutes = {
 "kind":"OPENING","time":"08:00","to_boss":True,
 "ts":f"{M}T08:00:00Z",
 "briefing":"BTC $64,155 (24h -1.0%, range $63,771-$65,147, -49% ATH); ETH $1,887 (30d +4.7%); FNG 29 Extreme Fear.",
 "speakers":[{"id":k,"name":{"macro":"Dr. Helena Voss","quant":"Kenji Arai","news":"Nick Reed","sentiment":"Mara Quinn","risk":"Dmitri Sokolov"}[k],
              "role":{"macro":"Macro Strategist","quant":"Quant / Systematic","news":"News Reporter","sentiment":"Sentiment & Flow","risk":"Head of Risk"}[k],
              "view":v} for k,v in views.items()],
 "cio_call":call,"cio_raw":cio_raw,
 "news_brief":nb,
}
# deploy the paper position
book, note = deploy(call)
mtd = mtd_progress(book)
minutes["paper_equity"]=book["equity"]
minutes["paper_action"]=note
minutes["mtd"]=mtd
minutes["paper_day_pnl"]=0.0

import os
os.makedirs("meeting_logs",exist_ok=True)
json.dump(minutes, open(f"meeting_logs/opening_{M}.json","w"), indent=2)
print(boss_report(minutes,"OPENING"))
