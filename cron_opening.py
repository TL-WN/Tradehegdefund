"""
cron_opening.py  --  AI Hedge Fund OPENING meeting (scheduled cron).
Dry-run. Plays the 5 personas + CIO on the SAME real data/news/research,
writes meeting_logs/opening_<date>.json, and prints the MORNING OPENING REPORT.

The LLM key is absent in this environment, so the on-host brain (Hermes) plays
each persona from the real snapshot + news + backtest, exactly as schedule.py
documents ("if absent, the orchestrator plays the personas").
"""
import json
import os
import re
import datetime
import requests

import news as news_mod
import research as research_mod
import schedule
from data_provider import build_briefing, load_snapshot
from report import boss_report

ROOT = os.path.dirname(os.path.abspath(__file__))
TODAY = datetime.date.today().isoformat()

# ---------------------------------------------------------------------------
# (1) NEWS REPORTER  --  live headline scrape (browser tool was down -> HTTP)
# ---------------------------------------------------------------------------
def scrape_cryptopanic():
    import html as _html
    url = "https://cryptopanic.com/news/"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        html_text = r.text
    except Exception as e:
        return [], f"scrape failed: {e}"
    anchors = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html_text, re.S)
    seen, out = set(), []
    JUNK = ["upgrade your browser", "joy of a hard-earned", "cookie", "privacy policy",
            "accept", "subscribe", "sign up", "log in", "terms of", "newsletter"]
    for href, txt in anchors:
        t = _html.unescape(re.sub(r"<[^>]+>", "", txt)).strip()
        if len(t) < 24 or len(t) > 165:
            continue
        if "/news/" not in href:          # real CryptoPanic story links only
            continue
        low = t.lower()
        if any(j in low for j in JUNK):
            continue
        if low in seen:
            continue
        seen.add(low)
        out.append(t)
    out = out[:15]
    return out, f"https://cryptopanic.com/news/ ({len(out)} items)"

raw_headlines, src_url = scrape_cryptopanic()
print(f"[NEWS] scraped {len(raw_headlines)} headlines from {src_url}")
for h in raw_headlines:
    print("   -", h)

news_brief = news_mod.ingest(
    raw_headlines,
    source="CryptoPanic (live)",
    requested_by="Nick Reed, News Reporter",
)
news_text = news_mod.format_for_meeting(news_brief)

# ---------------------------------------------------------------------------
# (2) RESEARCH DESK  --  live web find -> mapped backtest (fallback: catalogue)
# ---------------------------------------------------------------------------
def live_research_find():
    try:
        q = "Bitcoin 20 day moving average momentum strategy backtest"
        r = requests.get("https://html.duckduckgo.com/html/",
                         params={"q": q}, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', r.text, re.S)
        snippets = [re.sub(r"<[^>]+>", "", s).strip() for s in snippets]
        snippets = [s for s in snippets if "momentum" in s.lower()][:1]
        if snippets:
            return research_mod.research_from_web(
                snippets[0], source_url="https://html.duckduckgo.com/html/?q=" + q.replace(" ", "+"),
                requested_by="Research Desk (live web find)")
    except Exception as e:
        print(f"[RESEARCH] live find failed ({e}); using catalogue backtest")
    return research_mod.research_brief(requested_by="Research Desk")

research_brief = live_research_find()
research_text = research_mod.format_for_meeting(research_brief)
print("\n[RESEARCH]\n" + research_text)

# ---------------------------------------------------------------------------
# (3) PLAY THE FIVE PERSONAS + CIO  (on-host brain, biased by persona)
#     Grounded in: BTC $63,800 (rng 63,200-64,414, -49% ATH); ETH $1,891 (+5.8% 30d,
#     -62% ATH); FNG 27 Fear; momentum backtest beats BH but 18-20% maxDD vs -7% limit.
# ---------------------------------------------------------------------------
VIEWS = {
    "macro": (
        "Fear at 27 and BTC pinned in a $63,200-$64,414 band screams an unresolved, "
        "risk-off regime. Real rates are still restrictive and there's no fresh easing "
        "impulse, so I treat the CryptoQuant 'early bull signal' as a sentiment flicker, "
        "not a liquidity turn. The real tell is treasury stress: Metaplanet moving $250M of "
        "BTC while sitting on a $1.4B paper loss shows corporate holders are feeling the "
        "squeeze. Bias: defensive -- I'd rather miss the first leg up than eat a forced-sale flush."
    ),
    "quant": (
        "BTC 63,800, 7d -0.6%, 30d +1.2% -- dead flat, no trend. Tape is mean-reverting "
        "inside 63,200 support / 64,414 resistance, not trending. The research desk's 20d "
        "momentum beats buy-&-hold on the 120-day backtest, but its 18-20% max drawdown is "
        "2.5-3x our -7% hard stop -- untradable at size. ETH is marginally firmer (30d +5.8%) "
        "but still range-bound. Bias: neutral; if forced to pick, fade the range extremes, not the midpoint."
    ),
    "sentiment": (
        "Fear 27, but the crowd's already positioned for pain -- that's the fade setup, not a "
        "fresh short. Real accumulation is showing: Amundi lifted its MSTR stake 148% to 1.32M "
        "shares, MoneyGram is backing Solana DeFi liquidity, and CryptoQuant flags a second early "
        "bull signal. XRP holding $1 and SOL's record on-chain activity tell me flows aren't dead. "
        "The panic is priced; smart money is quietly bidding. Bias: cautiously constructive -- fade "
        "the fear, but keep it tiny until the tape confirms."
    ),
    "risk": (
        "The research brief's own backtest admits 18-20% max drawdown -- that's a halt-and-stop-out, "
        "not a strategy we can run at size. Live tail: Metaplanet's $1.4B paper loss and $250M BTC "
        "move is forced-sale supply risk, and Australia's Yepbit takedown with frozen withdrawals is "
        "a contagion/regulatory tail I don't trust. Invalidation is clean: a BTC close below 63,200 "
        "ends the range. Stance: defensive -- max acceptable is a small, hard-stopped probe only."
    ),
    "news": (
        "Three stories move the tape. One -- institutional bid building: Amundi boosted its MSTR "
        "position 148% (1.32M shares) and CryptoQuant flags a second early bull signal, suggesting "
        "bottoming. Two -- treasury stress: Metaplanet shifted $250M in BTC with a $1.4B paper loss, "
        "real supply overhang, not FUD. Three -- regulatory watch: Australia took down Yepbit over "
        "frozen withdrawals. The '330% rally signal' headline is clickbait; the on-chain bottoming "
        "call is the real one to track. No price call from me."
    ),
}

CIO_RAW = (
    "DECISION: LONG\n"
    "INSTRUMENT: BTC\n"
    "THESIS: Range-fade of stale Fear-27 into the lower third of the 63,200-64,414 band. "
    "Small, hard-stopped long sized so a stop-out costs <0.05% of book -- keeps us alive to "
    "compound toward +1%/month without approaching the -7% halt. Institutional bid building "
    "(Amundi +148% MSTR, CryptoQuant early bull signal) offsets treasury-stress supply overhang.\n"
    "ENTRY: market\n"
    "STOP: 63,200 (range low -- hard invalidation)\n"
    "TARGET: 64,414 (range high)\n"
    "SIZE: 2% of book margin\n"
    "LEVERAGE: 2\n"
    "CONVICTION: 2\n"
    "DESK DISSENT: Macro/Risk saw risk-off + treasury-stress tail and wanted smaller/flat; "
    "Sentiment/News more constructive on institutional bid + early bull signal; Quant neutral (range-bound tape)."
)

def analyst_fn(system, user, agent):
    aid = agent["id"]
    return VIEWS.get(aid, CIO_RAW if aid == "cio" else "[unavailable]")

# ---------------------------------------------------------------------------
# (4) RUN THE MEETING  (writes meeting_logs/opening_<date>.json + paper book/MTD)
# ---------------------------------------------------------------------------
snap = load_snapshot()
briefing = build_briefing(snap)
minutes = schedule.run_meeting(
    "OPENING", analyst_fn,
    snap=snap, briefing=briefing,
    research_brief=research_text, news_brief=news_text,
)

# enrich minutes with the raw brief dicts (audit trail)
minutes["news_brief_raw"] = news_brief
minutes["research_brief_raw"] = research_brief
with open(minutes["_log"], "w") as f:
    json.dump(minutes, f, indent=2)

print("\n" + "=" * 60)
print(boss_report(minutes, "OPENING"))
print("=" * 60)
print(f"\n[OK] minutes -> {minutes['_log']}")
