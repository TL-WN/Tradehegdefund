"""
report.py
Renders the two boss-facing reports (OPENING at 08:00, CLOSE at 17:30) and the
internal MIDDAY note. MIDDAY is NOT sent to the boss.
"""
import datetime


def _speakers_lines(minutes):
    out = []
    for s in minutes.get("speakers", []):
        out.append(f"• {s['name']} ({s['role']}): {s['view'].strip()}")
    return "\n".join(out)


def boss_report(minutes, kind):
    """Return a clean, boss-facing markdown string for OPENING/CLOSE."""
    meta = {"OPENING": "MORNING OPENING REPORT", "CLOSE": "EVENING CLOSE REPORT"}[kind]
    c = minutes.get("cio_call", {})
    icon = "📈" if kind == "OPENING" else "🌙"
    lines = []
    lines.append(f"{icon} {meta}")
    lines.append(f"Firm: AI Hedge Desk · {minutes.get('ts','')[:10]} · meeting {minutes.get('time')}")
    lines.append("─" * 42)
    lines.append("DESK ROUND:")
    lines.append(_speakers_lines(minutes))
    if "news_brief" in minutes:
        lines.append("─" * 42)
        lines.append("📰 DAILY NEWS (News Reporter):")
        # show the formatted brief (already one-page); trim to keep report tight
        nb = minutes["news_brief"]
        lines.append(nb)
    lines.append("─" * 42)
    lines.append("CIO DECISION:")
    lines.append(f"  Decision : {c.get('DECISION','?')}")
    lines.append(f"  Instrument: {c.get('INSTRUMENT','?')}")
    lines.append(f"  Thesis   : {c.get('THESIS','?')}")
    lines.append(f"  Entry    : {c.get('ENTRY','?')}")
    lines.append(f"  Stop     : {c.get('STOP','?')}")
    lines.append(f"  Target   : {c.get('TARGET','?')}")
    lines.append(f"  Size     : {c.get('SIZE','?')}")
    lines.append(f"  Conviction: {c.get('CONVICTION','?')}/5")
    lines.append(f"  Desk dissent: {c.get('DESK DISSENT','?')}")
    # paper book + objective
    lines.append("─" * 42)
    lines.append("PAPER BOOK & MONTHLY OBJECTIVE (+1%):")
    if "paper_equity" in minutes:
        lines.append(f"  Paper equity : ${minutes['paper_equity']:,.0f}")
    if "paper_day_pnl" in minutes:
        lines.append(f"  Day P&L      : ${minutes['paper_day_pnl']:,.0f}")
    if "paper_action" in minutes:
        lines.append(f"  Action       : {minutes['paper_action']}")
    if "drawdown_halt" in minutes:
        lines.append(f"  ⚠ HALT       : {minutes['drawdown_halt']}")
    mtd = minutes.get("mtd") or {}
    if mtd:
        lines.append(f"  MTD return   : {mtd.get('mtd_return_pct')}%  (target +{mtd.get('objective_pct')}%)")
        lines.append(f"  Progress     : {mtd.get('progress_pct_of_target')}% of monthly target")
        lines.append(f"  Gap to target: {mtd.get('gap_to_target_pct')}%")
        lines.append(f"  Max lev used : {mtd.get('max_leverage_used')}:1  (ceiling 100:1)")
        lines.append(f"  Max DD MTD   : {mtd.get('max_drawdown_mtd')}%  (hard limit -7%)")
        if mtd.get("halted"):
            lines.append("  STATUS       : BOOK HALTED (drawdown limit hit)")
    lines.append("─" * 42)
    lines.append("DISCLAIMER: Simulated desk opinion + paper book, not financial advice. Dry-run by default.")
    return "\n".join(lines)


def scorecard_report(card):
    """Boss-facing monthly mandate scorecard."""
    verdict = "✅ OBJECTIVE HIT" if card["hit"] else "❌ MISSED"
    lines = []
    lines.append("📊 MONTHLY MANDATE SCORECARD")
    lines.append(f"Month reported : {card['month_reported']}")
    lines.append("─" * 42)
    lines.append(f"  Return       : {card['return_pct']}%   (objective +{card['objective_pct']}%)  {verdict}")
    lines.append(f"  Trades       : {card['trades']}   (W {card['wins']} / L {card['losses']}  win-rate {card['win_rate_pct']}%)")
    lines.append(f"  Gross P&L    : ${card['gross_pnl']:,.0f}")
    lines.append(f"  Max leverage : {card['max_leverage_used']}:1   (ceiling 100:1)")
    lines.append(f"  Max drawdown : {card['max_drawdown_mtd_pct']}%   (hard limit -7%)")
    lines.append(f"  Halt events  : {card['drawdown_halts']}")
    lines.append(f"  End equity   : ${card['equity']:,.0f}")
    lines.append("─" * 42)
    lines.append("New month trackers reset. Book cleared for next mandate cycle.")
    return "\n".join(lines)


def midday_internal(minutes):
    c = minutes.get("cio_call", {})
    return (
        f"[INTERNAL MIDDAY — not sent to boss]\n"
        f"Recheck: {c.get('DECISION')} {c.get('INSTRUMENT')} · conv {c.get('CONVICTION')}/5\n"
        f"Thesis: {c.get('THESIS')}\n"
        f"Desk dissent: {c.get('DESK DISSENT')}"
    )


if __name__ == "__main__":
    print("report renderer ready")
