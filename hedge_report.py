"""
ai_hedge_fund/hedge_report.py  —  Send the hedge-fund desk recap to Telegram.

Pulls the live desk state from the Render dashboard (/api/state) and sends a
morning / night recap to the SAME Telegram bot used by pm_arb (token via env
TG_BOT_TOKEN / TG_CHAT_ID, or pm_arb/.tg_config.json). Read-only reporter — never trades.

Report contents:
  - paper equity + P&L vs the +1%/mo mandate
  - current open position (demo desk) + live uPnL
  - the automated CIO call (decision / conviction / thesis)
  - F&G regime

USAGE:
  python hedge_report.py morning
  python hedge_report.py night
  python hedge_report.py status
"""
import os
import sys
import json
import datetime
import urllib.request
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER_URL = os.environ.get("RENDER_URL", "https://hermes-capital-desk.onrender.com")
# reuse pm_arb telegram config if present, else env
PM_TG = os.path.join(HERE, "..", "pm_arb", ".tg_config.json")


def _tg():
    tok = os.environ.get("TG_BOT_TOKEN")
    cid = os.environ.get("TG_CHAT_ID")
    if tok and cid:
        return tok, cid
    try:
        d = json.load(open(PM_TG))
        return d.get("bot_token"), d.get("chat_id")
    except Exception:
        return None, None


def _get_state():
    try:
        with urllib.request.urlopen(RENDER_URL + "/api/state", timeout=25) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"_error": str(e)[:120]}


def build(kind, st):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    book = st.get("book", {}) or {}
    eq = book.get("equity")
    pnl = book.get("realized_mtd")
    if pnl is None:
        pnl = book.get("realized_pnl") or 0
    pos = st.get("open_positions") or []
    if not pos and book.get("open_position"):
        pos = [book["open_position"]]
    meet = {}
    mraw = st.get("meetings")
    if isinstance(mraw, dict):
        meet = next(iter(mraw.values()), {}) or {}
    elif isinstance(mraw, list):
        meet = mraw[0] if mraw else {}
    if not meet:
        meet = st.get("meeting") or {}
    fng = st.get("fng")
    if isinstance(fng, dict):
        fng = fng.get("value")
    # fallback: read today's automated meeting log if not in live state
    if not meet.get("decision"):
        import glob
        today = datetime.date.today().isoformat()
        for fn in glob.glob(os.path.join(HERE, "meeting_logs", f"opening_{today}.json")):
            try:
                meet = json.load(open(fn)); break
            except Exception:
                pass
    lines = [f"🏦 <b>HERMES CAPITAL — {kind.upper()} REPORT</b> ({now})"]
    if eq is not None:
        lines.append(f"Paper equity: ${eq:,.0f}  |  Realized P&L (MTD): ${pnl:,.0f}")
    else:
        lines.append(f"Equity: n/a ({st.get('_error','')})")
    if pos:
        p = pos[0]
        lines.append(f"Open: {p.get('side')} {p.get('symbol') or p.get('instrument')} x{p.get('leverage')} "
                     f"@ {p.get('entry')} | uPnL ${p.get('unrealized_pnl',0):,.0f}")
        if p.get("dist_to_stop") is not None:
            lines.append(f"  stop {p.get('stop')} ({p.get('dist_to_stop'):.1f}%) / "
                         f"target {p.get('target')} ({p.get('dist_to_target'):.1f}%)")
    else:
        lines.append("Open positions: none")
    if meet:
        lines.append(f"CIO call: {meet.get('decision')} (conv {meet.get('conviction')}) — "
                     f"{(meet.get('thesis') or '')[:90]}")
    if fng is not None:
        lines.append(f"Fear&Greed: {fng}")
    lines.append("Mandate: +1%/mo, -7% DD halt. Paper only.")
    return "\n".join(lines)


def send(kind):
    tok, cid = _tg()
    if not tok or not cid:
        print("ERROR: TG_BOT_TOKEN / TG_CHAT_ID not set (or pm_arb/.tg_config.json missing).")
        sys.exit(1)
    st = _get_state()
    msg = build(kind, st)
    data = urllib.parse.urlencode({"chat_id": cid, "text": msg,
                                   "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=data)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read())
        print("sent:", resp.get("ok"))
    except Exception as e:
        print("send error:", e)


if __name__ == "__main__":
    k = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
    send(k)
