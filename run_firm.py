"""
run_firm.py
Drives ONE full work day on demand: OPENING -> MIDDAY -> CLOSE.
The analyst_fn is injected (real LLM or, on this host, the orchestrator plays the
personas). Boss reports (OPENING + CLOSE) are returned for delivery; MIDDAY is logged.

Usage:
  python run_firm.py            # runs a full day with whatever analyst_fn is wired
  python run_firm.py OPENING    # run just one meeting
"""
import sys
import json
from schedule import run_meeting, MEETINGS
from report import boss_report, midday_internal
from execution import place_order, save_position
from data_provider import load_snapshot, build_briefing

# Import the wired analyst backend (LLM if key present, else a local fallback)
try:
    from llm_backend import call as _llm_call
    HAVE_LLM = True
except Exception:
    HAVE_LLM = False


def analyst_fn(system, user, agent):
    if HAVE_LLM:
        return _llm_call(system, user, temperature=0.85)
    raise RuntimeError("no LLM backend wired (orchestrator must supply personas)")


def run_one(kind, prev=None):
    m = run_meeting(kind, analyst_fn, prev_context=prev)
    if kind == "MIDDAY":
        report = midday_internal(m)
        deliver = False
    else:
        report = boss_report(m, kind)
        deliver = True
    # execution receipt for the CIO call
    receipt = place_order(m.get("cio_call", {}))
    m["_execution"] = receipt
    return m, report, deliver


def run_day():
    snap = load_snapshot()
    briefing = build_briefing(snap)
    results = {}
    prev = None
    order = ["OPENING", "MIDDAY", "CLOSE"]
    for kind in order:
        m, report, deliver = run_one(kind, prev)
        # carry forward a compact context for continuity
        c = m.get("cio_call", {})
        prev = {"kind": kind, "decision": c.get("DECISION"), "instrument": c.get("INSTRUMENT"),
                "conviction": c.get("CONVICTION"), "thesis": c.get("THESIS")}
        results[kind] = {"meeting": m, "report": report, "deliver_to_boss": deliver}
    return results


if __name__ == "__main__":
    arg = (sys.argv[1].upper() if len(sys.argv) > 1 else "DAY")
    if arg == "DAY":
        res = run_day()
        for kind in ("OPENING", "MIDDAY", "CLOSE"):
            r = res[kind]
            print("\n" + "=" * 60)
            print(f"MEETING: {kind}  (deliver_to_boss={r['deliver_to_boss']})")
            print("=" * 60)
            print(r["report"])
    else:
        m, report, deliver = run_one(arg)
        print(report)
