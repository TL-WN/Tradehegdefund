"""
execution.py
The broker stub. DRY-RUN by default. It never places a real order unless
EXEC_LIVE=1 is set AND EXEC_CONFIRMED=YES (two independent gates) are present,
and even then it only calls a pluggable place_order() you must implement for your
broker. This is deliberate: no responsible bot trades live on autopilot.
"""
import os
import json
import datetime


def _live_enabled():
    return os.getenv("EXEC_LIVE") == "1" and os.getenv("EXEC_CONFIRMED") == "YES"


def place_order(position: dict) -> dict:
    """Execute (or simulate) the day's position. Returns an execution receipt."""
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    decision = position.get("DECISION", "FLAT")

    if decision == "FLAT" or not position.get("INSTRUMENT"):
        receipt = {
            "executed": False,
            "mode": "dry-run",
            "note": "No action taken (FLAT / no instrument).",
            "timestamp": ts,
            "position": position,
        }
        return receipt

    if not _live_enabled():
        receipt = {
            "executed": False,
            "mode": "DRY-RUN (safe default)",
            "note": "Set EXEC_LIVE=1 and EXEC_CONFIRMED=YES in .env to arm live orders. "
                    "No broker connection was attempted.",
            "timestamp": ts,
            "position": position,
        }
        return receipt

    # --- LIVE PATH (only reached if both gates are set) ---
    # Implement your broker's order call here, e.g.:
    #   from my_broker import submit
    #   return submit(position)
    raise NotImplementedError(
        "Live order routing is intentionally unimplemented. Wire your broker's SDK "
        "in execution.place_order() behind the EXEC_LIVE/EXEC_CONFIRMED gates, then "
        "this raises only as a reminder. Do NOT enable live trading without testing "
        "in paper mode first."
    )


def save_position(position: dict, path: str = "position_of_the_day.json"):
    with open(path, "w") as f:
        json.dump(position, f, indent=2)
    return path


if __name__ == "__main__":
    p = {"DECISION": "FLAT", "INSTRUMENT": None, "THESIS": "test", "CONVICTION": 1}
    print(json.dumps(place_order(p), indent=2))
