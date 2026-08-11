"""
fund.py
Runs the desk: each analyst reads the briefing via the LLM backend, then the CIO
synthesizes a single position. Saves notes + final position.
"""
import json
import os
from agents import AGENTS, CIO
from data_provider import build_briefing, load_snapshot
from llm_backend import call
from execution import place_order, save_position

NOTES_FILE = os.path.join(os.path.dirname(__file__), "desk_notes.json")


def run_desk(snap=None, briefing=None, analyst_fn=None):
    """
    analyst_fn(system, user, agent) -> str   # injectable; defaults to real LLM
    Returns (notes_dict, position_dict)
    """
    snap = snap or load_snapshot()
    briefing = briefing or build_briefing(snap)

    if analyst_fn is None:
        def analyst_fn(system, user, agent):
            return call(system, user, temperature=0.8)

    notes = {"briefing": briefing, "analysts": []}
    analyst_block = []
    for a in AGENTS:
        user = (
            f"Good morning, {a['name']} ({a['role']}).\n\n"
            f"Here is today's briefing:\n\n{briefing}\n\n"
            f"Give the desk your read now."
        )
        try:
            out = analyst_fn(a["system"], user, a)
        except Exception as e:
            out = f"[analysis unavailable: {e}]"
        notes["analysts"].append({
            "id": a["id"], "name": a["name"], "role": a["role"],
            "persona": a["persona"], "view": out,
        })
        analyst_block.append(f"--- {a['name']} ({a['role']}) ---\n{out}\n")

    cio_user = (
        f"Morning, {CIO['name']}. Here is the desk's input.\n\n"
        f"=== BRIEFING ===\n{briefing}\n\n"
        f"=== ANALYST VIEWS ===\n" + "\n".join(analyst_block) +
        f"\n=== YOUR CALL ===\nSynthesize and output in the required format."
    )
    try:
        cio_out = analyst_fn(CIO["system"], cio_user, CIO)
    except Exception as e:
        cio_out = f"[CIO synthesis unavailable: {e}]"

    position = _parse_cio(cio_out)
    position["_raw"] = cio_out
    position["_analysts"] = [a["id"] for a in AGENTS]

    with open(NOTES_FILE, "w") as f:
        json.dump(notes, f, indent=2)

    receipt = place_order(position)
    position["_execution"] = receipt
    path = save_position(position)
    position["_saved_to"] = path
    return notes, position


def _parse_cio(text):
    """Best-effort parse of the CIO's fixed-format block into a dict."""
    out = {}
    keys = ["DECISION", "INSTRUMENT", "THESIS", "ENTRY", "STOP",
            "TARGET", "SIZE", "CONVICTION", "DESK DISSENT"]
    for line in text.splitlines():
        for k in keys:
            if line.strip().upper().startswith(k):
                val = line.split(":", 1)[1].strip()
                out[k] = val
    # normalize decision
    d = out.get("DECISION", "").upper()
    for tok in ("LONG", "SHORT", "FLAT"):
        if tok in d:
            out["DECISION"] = tok
            break
    return out


if __name__ == "__main__":
    notes, position = run_desk()
    print("=== DESK NOTES SAVED:", NOTES_FILE)
    for a in notes["analysts"]:
        print(f"\n## {a['name']} — {a['role']}")
        print(a["view"])
    print("\n================ POSITION OF THE DAY ================")
    print(position.get("_raw", ""))
    print("\nEXECUTION:", position.get("_execution", {}).get("mode"))
