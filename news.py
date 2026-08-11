"""
news.py
The firm's NEWS REPORTER. Scans Bitcoin / crypto news sources via the browser (real web),
extracts fresh headlines with timestamps, tags a rough sentiment, dedupes, and emits a
DAILY NEWS BRIEF the desk reads before deciding.

The actual fetching is done through the browser tool (browser_exec) by the orchestrator,
because the browser harness is a runtime tool, not an importable library. This module
provides:
  - SOURCES: the curated list of URLs the reporter should scan
  - ingest(headlines): take raw scraped headlines -> clean/dedupe/tag -> news brief
  - format_for_meeting(brief): one-page text injected into the meeting prompt
  - save/load helpers + a simple sentiment tagger

No ML. Sentiment is a keyword heuristic (bullish/bearish/neutral) so the desk can react.
"""
import json
import os
import datetime
import re

NEWS_DIR = os.path.join(os.path.dirname(__file__), "news_logs")
os.makedirs(NEWS_DIR, exist_ok=True)

# Curated, server-rendered BTC/crypto news sources (no API key).
SOURCES = [
    ("CryptoPanic", "https://cryptopanic.com/news/"),
    ("Cointelegraph", "https://cointelegraph.com/"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/"),
    ("CoinGecko News", "https://www.coingecko.com/en/coins/bitcoin/news"),
]

BULL = ["surge", "rally", "gain", "bull", "bullish", "record", "high", "approval", "adopt",
        "inflow", "etf", "buy", "breakout", "upgrade", "positive", "soar", "jump", "hop", "moon"]
BEAR = ["crash", "drop", "fall", "bear", "bearish", "ban", "lawsuit", "sec", "hack", "sell",
        "dump", "liquidat", "warn", "risk", "fear", "down", "low", "cut", "fud", "fraud", "slump"]


def tag_sentiment(text):
    t = (text or "").lower()
    b = sum(1 for w in BULL if w in t)
    r = sum(1 for w in BEAR if w in t)
    if b > r:
        return "BULLISH"
    if r > b:
        return "BEARISH"
    return "NEUTRAL"


def _clean(headline):
    h = re.sub(r"\s+", " ", headline).strip()
    return h


def ingest(raw_items, source="mixed", requested_by="news_reporter"):
    """
    raw_items: list of strings (headlines, possibly with source/timestamp suffixes).
    Returns a news brief dict and saves it.
    """
    seen = {}
    for item in raw_items:
        h = _clean(item)
        if len(h) < 15:
            continue
        # core headline = text before a '[' or '(' or 'http' or long timestamp
        core = re.split(r"\s[\(\[]|https?://", h)[0].strip()
        if len(core) < 15:
            core = h
        if core.lower() in seen:
            continue
        seen[core.lower()] = {
            "headline": core,
            "sentiment": tag_sentiment(core),
            "raw": h,
        }
    items = list(seen.values())
    # sort: bullish/bearish first (actionable), then neutral
    rank = {"BEARISH": 0, "BULLISH": 1, "NEUTRAL": 2}
    items.sort(key=lambda x: rank.get(x["sentiment"], 3))
    brief = {
        "type": "NEWS_BRIEF",
        "date": datetime.date.today().isoformat(),
        "source": source,
        "requested_by": requested_by,
        "count": len(items),
        "items": items[:15],
    }
    fn = os.path.join(NEWS_DIR, f"news_{brief['date']}.json")
    json.dump(brief, open(fn, "w"), indent=2)
    return brief


def format_for_meeting(brief):
    if not brief or "items" not in brief:
        return "[News: none today]"
    lines = []
    lines.append("📰 NEWS REPORTER BRIEF (read before you decide)")
    lines.append(f"Sources scanned: {brief.get('source','?')}  |  {brief['count']} items")
    lines.append("─" * 42)
    for it in brief["items"]:
        s = it["sentiment"]
        icon = "▲" if s == "BULLISH" else "▼" if s == "BEARISH" else "•"
        lines.append(f"  {icon} [{s[:4]}] {it['headline']}")
    lines.append("─" * 42)
    lines.append("Desk: fold these into your read. A headline can flip the call.")
    return "\n".join(lines)


def latest():
    files = sorted([f for f in os.listdir(NEWS_DIR) if f.startswith("news_")])
    if not files:
        return None
    return json.load(open(os.path.join(NEWS_DIR, files[-1])))


def offline_brief(prices=None, fng_value=None):
    """
    Fallback used when no browser is available (CI / cloud). Builds a short,
    data-driven market-context brief from live prices + F&G so the news panel
    is never empty. Clearly labelled as automated (not a web scrape).
    """
    items = []
    if prices:
        for sym, d in prices.items():
            if sym == "_error":
                continue
            chg = d.get("chg24h")
            if chg is None:
                continue
            if chg <= -3:
                items.append({"headline": f"{sym} down {abs(chg):.1f}% in 24h — risk-off pressure",
                              "sentiment": "BEARISH", "raw": ""})
            elif chg >= 3:
                items.append({"headline": f"{sym} up {chg:.1f}% in 24h — bid momentum",
                              "sentiment": "BULLISH", "raw": ""})
        # sort actionable first
        rank = {"BEARISH": 0, "BULLISH": 1, "NEUTRAL": 2}
        items.sort(key=lambda x: rank.get(x["sentiment"], 3))
    if fng_value is not None:
        cls = "FEAR" if int(fng_value) < 45 else "GREED" if int(fng_value) > 55 else "NEUTRAL"
        items.insert(0, {"headline": f"Fear & Greed at {fng_value} ({cls}) — crowd sentiment gauge",
                         "sentiment": "BEARISH" if cls == "FEAR" else "BULLISH" if cls == "GREED" else "NEUTRAL",
                         "raw": ""})
    brief = {
        "type": "NEWS_BRIEF",
        "date": datetime.date.today().isoformat(),
        "source": "offline-data-fallback",
        "requested_by": "ci_engine",
        "count": len(items),
        "items": items[:15],
    }
    fn = os.path.join(NEWS_DIR, f"news_{brief['date']}.json")
    json.dump(brief, open(fn, "w"), indent=2)
    return brief


def weekly_digest():
    """Aggregate this week's daily news logs into one narrative-arc digest.
    Returns a dict; also writes news_logs/weekly_<isoweek>.json + a rendered text."""
    files = sorted([f for f in os.listdir(NEWS_DIR)
                    if f.startswith("news_") and f.endswith(".json")])
    # last 7 days of logs
    import datetime as _dt
    cutoff = (_dt.date.today() - _dt.timedelta(days=7)).isoformat()
    week = []
    for f in files:
        try:
            d = json.load(open(os.path.join(NEWS_DIR, f)))
            if d.get("date", "") >= cutoff:
                week.append(d)
        except Exception:
            pass
    if not week:
        return {"error": "no news logs this week"}

    # tally sentiment + most-seen headline stems
    from collections import Counter
    sent = Counter()
    headlines = []
    for b in week:
        for it in b.get("items", []):
            sent[it["sentiment"]] += 1
            headlines.append(it["headline"])
    # top repeated themes (by first 6 words)
    stems = Counter(" ".join(h.lower().split()[:6]) for h in headlines)
    top_themes = [s for s, _ in stems.most_common(6)]

    iso_week = _dt.date.today().strftime("%G-W%V")
    digest = {
        "type": "WEEKLY_NEWS_DIGEST",
        "week": iso_week,
        "generated": _dt.date.today().isoformat(),
        "days_covered": len(week),
        "sentiment_tally": dict(sent),
        "top_themes": top_themes,
        "raw_days": [b["date"] for b in week],
    }
    fn = os.path.join(NEWS_DIR, f"weekly_{iso_week}.json")
    json.dump(digest, open(fn, "w"), indent=2)
    return digest


def format_weekly(digest):
    if not digest or "error" in digest:
        return "[Weekly news digest: no data]"
    s = digest.get("sentiment_tally", {})
    lines = []
    lines.append("🗞️  WEEKLY NEWS DIGEST  (week " + digest.get("week", "?") + ")")
    lines.append(f"Days covered: {digest.get('days_covered')}  |  sentiment mix: "
                 f"▲{s.get('BULLISH',0)}  ▼{s.get('BEARISH',0)}  •{s.get('NEUTRAL',0)}")
    lines.append("─" * 46)
    lines.append("Recurring themes this week:")
    for t in digest.get("top_themes", []):
        lines.append(f"  • {t}...")
    lines.append("─" * 46)
    lines.append("Use this arc to frame next week's regime read.")
    return "\n".join(lines)


if __name__ == "__main__":
    b = latest()
    print(format_for_meeting(b) if b else "No news logged yet.")
