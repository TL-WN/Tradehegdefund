"""
data_provider.py
Loads the market snapshot produced by fetch_snapshot.py and renders a concise,
LLM-friendly briefing string for the fund agents.
All data is real (pulled at fetch time). Equities gracefully degrade if unavailable.
"""
import json, os

SNAP_FILE = os.path.join(os.path.dirname(__file__), "market_snapshot.json")


def load_snapshot():
    with open(SNAP_FILE) as f:
        return json.load(f)


def fmt(v, p=2):
    if v is None:
        return "n/a"
    return f"{v:,.{p}f}"


def build_briefing(snap=None):
    snap = snap or load_snapshot()
    lines = []
    lines.append(f"# DAILY MARKET BRIEFING  ({snap.get('generated_at','?')})")
    lines.append("")

    s = snap.get("sentiment", {})
    if s:
        lines.append(f"FEAR & GREED INDEX: {s.get('fng_value')}  -> {s.get('fng_class')}")

    lines.append("")
    lines.append("== CRYPTO (top caps) ==")
    for sym in ("BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "HYPE", "TRX", "ZEC"):
        c = snap["crypto"].get(sym)
        if not c:
            continue
        extra = ""
        if "high24h" in c:
            extra = f"  | 24h range {fmt(c['low24h'])}–{fmt(c['high24h'])}  | ATH {fmt(c['ath'])} ({fmt(c['ath_chg'],1)}%)"
        lines.append(f"{sym:5} ${fmt(c['price'])}  24h {fmt(c.get('chg24h'),1)}%  7d {fmt(c.get('chg7d'),1)}%  30d {fmt(c.get('chg30d'),1)}%{extra}")

    eq = snap.get("equities", {})
    if eq.get("raw") and "404" not in eq["raw"]:
        lines.append("")
        lines.append("== EQUITIES (Stooq) ==")
        lines.append(eq["raw"].strip())
    else:
        lines.append("")
        lines.append("== EQUITIES: not available in this snapshot (free source blocked) ==")

    return "\n".join(lines)


if __name__ == "__main__":
    print(build_briefing())
