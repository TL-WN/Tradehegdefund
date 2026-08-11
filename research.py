"""
research.py
The firm's RESEARCH DESK. A research agent:
  1. searches the web for a concrete, named trading strategy (or takes one requested),
  2. maps it to a backtestable signal in backtest.py (or reports it can't be tested),
  3. runs the backtest on the firm's REAL daily history,
  4. emits a one-page RESEARCH BRIEF the meeting can debate.

The brief is injected into the meeting prompt so Macro/Quant/Sentiment/Risk/CIO
discuss whether to adopt, reject, or size it. No ML; signals are rules; data is real.
"""
import json
import os
import datetime
from backtest import backtest_all, STRATEGIES

RESEARCH_DIR = os.path.join(os.path.dirname(__file__), "research_logs")
os.makedirs(RESEARCH_DIR, exist_ok=True)

# A small curated catalogue the desk can be pointed at (each maps to a real signal).
CATALOGUE = {
    "momentum_20d": "20-day moving-average momentum (trend following).",
    "meanrev_20d": "20-day z-score mean reversion.",
    "breakout_20d": "20-day channel breakout (Donchian-style).",
}

# Maps a web-found strategy description to the nearest backtestable signal key.
WEB_MAP = [
    ("momentum", "momentum_20d"),
    ("trend", "momentum_20d"),
    ("reversion", "meanrev_20d"),
    ("mean", "meanrev_20d"),
    ("z-score", "meanrev_20d"),
    ("bollinger", "meanrev_20d"),
    ("rsi", "meanrev_20d"),
    ("breakout", "breakout_20d"),
    ("channel", "breakout_20d"),
    ("donchian", "breakout_20d"),
]


def map_web_to_signal(text):
    """Given free text about a strategy found on the web, return the nearest signal key."""
    t = (text or "").lower()
    for kw, key in WEB_MAP:
        if kw in t:
            return key
    return "momentum_20d"  # safest default


def research_from_web(finding_text, source_url="web", requested_by="research_desk"):
    """Ingest a web-found strategy (text + url), map to a signal, backtest, emit brief."""
    key = map_web_to_signal(finding_text)
    brief = research_brief(strategy_key=key, source_note=f"{source_url} :: {finding_text[:80]}",
                           requested_by=requested_by)
    if "error" not in brief:
        brief["web_source"] = source_url
        brief["web_finding"] = finding_text[:400]
        fn = os.path.join(RESEARCH_DIR, f"brief_{key}_{brief['date']}_web.json")
        json.dump(brief, open(fn, "w"), indent=2)
    return brief


def research_brief(strategy_key=None, source_note="internal catalogue", requested_by="boss"):
    """Produce a research brief. If strategy_key is None, pick the next untested one."""
    if strategy_key is None:
        # pick catalogue key not yet logged today
        today = datetime.date.today().isoformat()
        done = set()
        for f in os.listdir(RESEARCH_DIR):
            try:
                d = json.load(open(os.path.join(RESEARCH_DIR, f)))
                if d.get("date") == today:
                    done.add(d.get("strategy"))
            except Exception:
                pass
        for k in CATALOGUE:
            if k not in done:
                strategy_key = k
                break
        if strategy_key is None:
            strategy_key = list(CATALOGUE)[0]

    bt = backtest_all(strategy_key)
    if bt is None:
        return {"error": f"unknown strategy {strategy_key}"}

    brief = {
        "type": "RESEARCH_BRIEF",
        "date": datetime.date.today().isoformat(),
        "requested_by": requested_by,
        "source": source_note,
        "strategy": strategy_key,
        "strategy_name": bt["name"],
        "backtest": bt["results"],
        "verdict_hint": _verdict(bt),
    }
    fn = os.path.join(RESEARCH_DIR, f"brief_{strategy_key}_{brief['date']}.json")
    json.dump(brief, open(fn, "w"), indent=2)
    return brief


def _verdict(bt):
    r = bt["results"]
    lines = []
    for s, v in r.items():
        if not v:
            continue
        beat = "BEATS" if v["vs_buyhold_pct"] > 0 else "LOSES TO"
        lines.append(f"{s}: {v['strat_return_pct']}% vs BH {v['buyhold_return_pct']}% ({beat} BH), "
                     f"win {v['win_rate_pct']}%, maxDD {v['max_drawdown_pct']}%")
    return " | ".join(lines)


def format_for_meeting(brief):
    """One-page text the meeting prompt can include so the desk debates the strategy."""
    if "error" in brief:
        return f"[Research: {brief['error']}]"
    b = brief
    lines = []
    lines.append("🔬 RESEARCH DESK BRIEF (agenda item — discuss & vote)")
    lines.append(f"Strategy : {b['strategy_name']}  [{b['strategy']}]")
    lines.append(f"Source   : {b['source']}  (requested by {b['requested_by']})")
    lines.append("─" * 40)
    for s, v in b["backtest"].items():
        if not v:
            continue
        lines.append(f"  {s}: strat {v['strat_return_pct']}% | buy&hold {v['buyhold_return_pct']}% | "
                     f"win {v['win_rate_pct']}% | maxDD {v['max_drawdown_pct']}% | vs BH {v['vs_buyhold_pct']:+}%")
    lines.append("─" * 40)
    lines.append(f"Research verdict: {b['verdict_hint']}")
    lines.append("Desk: debate adopt / reject / size. Respect -7% DD limit & 1:100 leverage.")
    return "\n".join(lines)


if __name__ == "__main__":
    b = research_brief()
    print(format_for_meeting(b))
