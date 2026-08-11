"""
schedule.py
The firm's working day. Each "meeting" runs the desk as a set of role-played
personas (via an injected analyst_fn) and emits minutes + a CIO call.

Timetable (configurable):
  08:00  OPENING   -> delivered to the boss
  13:00  MIDDAY    -> internal only (logged, not sent to boss)
  17:30  CLOSE     -> delivered to the boss

The bot can run 100% on-host (Hermes is the brain). An external OpenAI-compatible
model is optional via LLM_API_KEY; if absent, the orchestrator plays the personas.
"""
import json
import os
import datetime
from agents import AGENTS, CIO
from data_provider import build_briefing, load_snapshot

MEETINGS = {
    "OPENING": {
        "time": "08:00",
        "to_boss": True,
        "blurb": "Morning standup: desk sets the day's plan and opening bias.",
    },
    "MIDDAY": {
        "time": "13:00",
        "to_boss": False,
        "blurb": "Midday sync: check drift vs the opening call, no boss report.",
    },
    "CLOSE": {
        "time": "17:30",
        "to_boss": True,
        "blurb": "End-of-day close: P&L vs plan, what to carry into tomorrow.",
    },
}

LOG_DIR = os.path.join(os.path.dirname(__file__), "meeting_logs")
os.makedirs(LOG_DIR, exist_ok=True)


def run_meeting(kind, analyst_fn, prev_context=None, snap=None, briefing=None, research_brief=None, news_brief=None):
    """
    kind: 'OPENING' | 'MIDDAY' | 'CLOSE'
    analyst_fn(system, user, agent) -> str   (play a persona; returns their spoken view)
    prev_context: dict from the previous meeting (for continuity)
    research_brief: optional str from research.format_for_meeting() -> desk debates it
    news_brief: optional str from news.format_for_meeting() -> desk reads before deciding
    Returns a meeting dict (minutes + cio call + meta).
    """
    assert kind in MEETINGS, f"unknown meeting {kind}"
    meta = MEETINGS[kind]
    snap = snap or load_snapshot()
    briefing = briefing or build_briefing(snap)

    cont = ""
    if prev_context:
        cont = (
            f"\n=== CONTEXT FROM PREVIOUS MEETING ({prev_context.get('kind')}) ===\n"
            f"Prior decision: {prev_context.get('decision')} {prev_context.get('instrument')} "
            f"@ conviction {prev_context.get('conviction')}\n"
            f"Prior thesis: {prev_context.get('thesis')}\n"
            f"Update the desk on whether the day has moved toward or against that call.\n"
        )

    rb = ""
    if research_brief:
        rb = f"\n=== RESEARCH DESK AGENDA ITEM (discuss & vote) ===\n{research_brief}\n"

    nb = ""
    if news_brief:
        nb = f"\n=== DAILY NEWS (from News Reporter) ===\n{news_brief}\n"

    minutes = {"kind": kind, "time": meta["time"], "to_boss": meta["to_boss"],
               "ts": datetime.datetime.utcnow().isoformat() + "Z",
               "briefing": briefing, "speakers": []}
    if research_brief:
        minutes["research_brief"] = research_brief
    if news_brief:
        minutes["news_brief"] = news_brief

    block = []
    for a in AGENTS:
        user = (
            f"Good {'morning' if kind=='OPENING' else 'afternoon' if kind=='MIDDAY' else 'evening'}, "
            f"{a['name']} ({a['role']}).\n\n"
            f"Today's briefing:\n{briefing}\n{cont}{nb}{rb}\n"
            f"Give the desk YOUR read for the {kind} meeting."
            + (" Address the research brief: should we adopt, reject, or size it?" if research_brief else "")
        )
        try:
            out = analyst_fn(a["system"], user, a)
        except Exception as e:
            out = f"[unavailable: {e}]"
        minutes["speakers"].append({"id": a["id"], "name": a["name"],
                                    "role": a["role"], "view": out})
        block.append(f"--- {a['name']} ({a['role']}) ---\n{out}\n")

    cio_user = (
        f"Morning/close, {CIO['name']}. Synthesize the desk for the {kind} meeting.\n\n"
        f"=== BRIEFING ===\n{briefing}\n{cont}{nb}{rb}\n"
        f"=== ANALYST VIEWS ===\n" + "\n".join(block)
    )
    if research_brief:
        cio_user += (
            f"\n=== YOUR CALL ===\nFirst, state whether the desk ADOPTS / REJECTS / PILOTS the "
            f"research strategy (and a max size respecting -7% DD and 1:100 leverage). Then output "
            f"the day's decision in the required format."
        )
    else:
        cio_user += f"\n=== YOUR CALL ===\nOutput in the required format."
    try:
        cio_out = analyst_fn(CIO["system"], cio_user, CIO)
    except Exception as e:
        cio_out = f"[CIO unavailable: {e}]"

    call = _parse_cio(cio_out)
    minutes["cio_call"] = call
    minutes["cio_raw"] = cio_out

    # --- paper book integration ---
    from book import deploy, mark_to_market, mtd_progress, load as load_book
    from data_provider import load_snapshot as _ld
    snap = _ld()
    if kind == "OPENING":
        book, note = deploy(call, snap)
        minutes["paper_action"] = note
        minutes["paper_equity"] = book["equity"]
    elif kind == "CLOSE":
        book, _dd, halt_note = mark_to_market(snap, flatten=True)
        # day P&L = realized MTD this session (close flattens any open position)
        minutes["paper_day_pnl"] = book.get("realized_mtd", 0.0)
        minutes["paper_equity"] = book["equity"]
        if halt_note:
            minutes["drawdown_halt"] = halt_note
    else:  # MIDDAY
        book, dd, halt_note = mark_to_market(snap, flatten=False)
        minutes["paper_equity"] = book["equity"]
        if halt_note:
            minutes["drawdown_halt"] = halt_note
    minutes["mtd"] = mtd_progress(book)

    # persist
    fn = os.path.join(LOG_DIR, f"{kind.lower()}_{datetime.date.today().isoformat()}.json")
    with open(fn, "w") as f:
        json.dump(minutes, f, indent=2)
    minutes["_log"] = fn
    return minutes


def _parse_cio(text):
    out = {}
    keys = ["DECISION", "INSTRUMENT", "THESIS", "ENTRY", "STOP",
            "TARGET", "SIZE", "LEVERAGE", "CONVICTION", "DESK DISSENT"]
    for line in text.splitlines():
        for k in keys:
            if line.strip().upper().startswith(k):
                out[k] = line.split(":", 1)[1].strip()
    d = out.get("DECISION", "").upper()
    for tok in ("LONG", "SHORT", "FLAT"):
        if tok in d:
            out["DECISION"] = tok
            break
    return out


if __name__ == "__main__":
    print("schedule defines the firm's meeting timetable. Run via run_firm.py.")
