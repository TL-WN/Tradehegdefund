"""
run_live_subagents.py
Runs the fund using Hermes subagents as the four analysts + CIO (since this host
has no external LLM key configured). This exercises the FULL pipeline: real data ->
persona-driven debate -> CIO synthesis -> dry-run execution + saved position.
"""
import json
from agents import AGENTS, CIO
from data_provider import build_briefing, load_snapshot
from execution import place_order, save_position

# NOTE: delegate_task is provided by the Hermes tool runtime; this script is
# executed by the orchestrating assistant, which calls each persona via
# delegate_task and feeds results back here. Below is the pure-Python harness
# that the orchestrator fills in.

def harness(briefing, analyst_views):
    """Given the briefing and a dict {agent_id: view_text}, produce final position."""
    from llm_backend import call  # may raise if no key; we catch in orchestrator
    snap = load_snapshot()
    notes = {"briefing": briefing, "analysts": []}
    analyst_block = []
    for a in AGENTS:
        out = analyst_views.get(a["id"], "[no view]")
        notes["analysts"].append({"id": a["id"], "name": a["name"],
                                   "role": a["role"], "persona": a["persona"], "view": out})
        analyst_block.append(f"--- {a['name']} ({a['role']}) ---\n{out}\n")

    cio_user = (f"Morning, {CIO['name']}. Desk input:\n\n=== BRIEFING ===\n{briefing}\n\n"
                f"=== ANALYST VIEWS ===\n" + "\n".join(analyst_block) +
                f"\n=== YOUR CALL ===\nSynthesize and output in the required format.")
    # CIO also run as a subagent by the orchestrator; we accept the text here:
    cio_out = analyst_views.get("cio", "")
    position = _parse_cio(cio_out)
    position["_raw"] = cio_out
    position["_analysts"] = [a["id"] for a in AGENTS]
    with open("desk_notes.json", "w") as f:
        json.dump(notes, f, indent=2)
    receipt = place_order(position)
    position["_execution"] = receipt
    path = save_position(position)
    position["_saved_to"] = path
    return notes, position


def _parse_cio(text):
    out = {}
    keys = ["DECISION", "INSTRUMENT", "THESIS", "ENTRY", "STOP",
            "TARGET", "SIZE", "CONVICTION", "DESK DISSENT"]
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
    print("This module is driven by the orchestrator (run_fund.py).")
