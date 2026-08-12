"""
ai_hedge_fund/hedge_report.py  —  Send the hedge-fund desk recap + equity chart to Telegram.

Pulls the live desk state from the Render dashboard (/api/state + /api/series) and sends a
morning / night recap with an EQUITY-CURVE CHART (PNG photo) to the SAME Telegram bot
used by pm_arb (token via env TG_BOT_TOKEN / TG_CHAT_ID, or pm_arb/.tg_config.json).
Read-only reporter — never trades.

USAGE:
  python hedge_report.py morning
  python hedge_report.py night
  python hedge_report.py status
"""
import os
import sys
import json
import io
import datetime
import urllib.request
import urllib.parse
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER_URL = os.environ.get("RENDER_URL", "https://hermes-capital-desk.onrender.com")
PM_TG = os.path.join(HERE, "..", "pm_arb", ".tg_config.json")
START = 1_000_000.0


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


def _get_curve():
    try:
        with urllib.request.urlopen(RENDER_URL + "/api/series", timeout=25) as r:
            d = json.loads(r.read())
        return d.get("equity_curve") or []
    except Exception:
        return []


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
    if not meet.get("decision"):
        import glob
        today = datetime.date.today().isoformat()
        for fn in glob.glob(os.path.join(HERE, "meeting_logs", f"opening_{today}.json")):
            try:
                meet = json.load(open(fn)); break
            except Exception:
                pass
    lines = [f"\U0001F3E6 <b>HERMES CAPITAL — {kind.upper()} REPORT</b> ({now})"]
    if eq is not None:
        lines.append(f"Paper equity: ${eq:,.0f}  |  Realized P&L (MTD): ${pnl:,.0f}")
    else:
        lines.append(f"Equity: n/a ({st.get('_error','')})")
    if pos:
        p = pos[0]
        sym = p.get("symbol") or p.get("instrument")
        lines.append(f"Open: {p.get('side')} {sym} x{p.get('leverage')} "
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


def render_equity_png(curve, path="hedge_report_chart.png"):
    """Render the desk equity curve to a PNG (PIL). Returns bytes."""
    W, H = 900, 300
    eqs = [max(p.get("v", START), 0.0) for p in curve] or [START]
    n = len(eqs)
    lo = min(eqs); hi = max(eqs)
    if hi - lo < 1:
        hi = lo + 10000
    ymin = max(0, lo - (hi - lo) * 0.2)
    ymax = hi + (hi - lo) * 0.2

    img = Image.new("RGB", (W, H), (11, 21, 28))
    d = ImageDraw.Draw(img)
    try:
        fnt = ImageFont.truetype("DejaVuSans.ttf", 13)
    except Exception:
        fnt = ImageFont.load_default()

    def Y(v):
        return 30 + (ymax - v) / (ymax - ymin) * (H - 60)

    def X(i):
        return 40 + i / max(n - 1, 1) * (W - 60)

    d.line([(40, Y(START)), (W - 20, Y(START))], fill=(127, 132, 156), width=1)
    d.text((44, Y(START) - 14), f"${START/1e6:.2f}M start", fill=(127, 132, 156), font=fnt)
    peak = max(eqs)
    d.line([(40, Y(peak)), (W - 20, Y(peak))], fill=(167, 139, 250), width=1)
    d.text((44, Y(peak) - 14), f"peak ${peak/1e6:.2f}M", fill=(167, 139, 250), font=fnt)
    d.line([(X(i), Y(eqs[i])) for i in range(n)], fill=(166, 227, 161), width=2)
    col = (166, 227, 161) if eqs[-1] >= START else (243, 139, 168)
    d.text((44, 16), f"Equity ${eqs[-1]/1e6:.3f}M ({n} pts)", fill=col, font=fnt)
    d.text((W - 230, H - 22), "Hermes Capital — paper desk", fill=(127, 132, 156), font=fnt)
    img.save(path)
    with open(path, "rb") as fh:
        return fh.read()


def _send_text(tok, cid, msg):
    data = urllib.parse.urlencode({"chat_id": cid, "text": msg,
                                   "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=data)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read()).get("ok")


def _send_photo(tok, cid, png_bytes, caption=""):
    boundary = "----hedgereportbound"
    CRLF = b"\r\n"
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode())
    body.write(b'Content-Disposition: form-data; name="chat_id"\r\n\r\n')
    body.write(f"{cid}\r\n".encode())
    if caption:
        body.write(f"--{boundary}\r\n".encode())
        body.write(b'Content-Disposition: form-data; name="caption"\r\n\r\n')
        body.write(f"{caption}\r\n".encode())
    body.write(f"--{boundary}\r\n".encode())
    body.write(b'Content-Disposition: form-data; name="photo"; filename="hedge.png"\r\n')
    body.write(b"Content-Type: image/png\r\n\r\n")
    body.write(png_bytes)
    body.write(f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendPhoto",
                                 data=body.getvalue(),
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read()).get("ok")


def send(kind):
    tok, cid = _tg()
    if not tok or not cid:
        print("ERROR: TG_BOT_TOKEN / TG_CHAT_ID not set (or pm_arb/.tg_config.json missing).")
        sys.exit(1)
    st = _get_state()
    msg = build(kind, st)
    try:
        print("text sent:", _send_text(tok, cid, msg))
    except Exception as e:
        print("send error:", e)
    try:
        curve = _get_curve()
        if curve:
            png = render_equity_png(curve)
            print("photo sent:", _send_photo(tok, cid, png, caption=f"Hermes Capital equity curve ({kind})"))
    except Exception as e:
        print("chart skipped:", e)


if __name__ == "__main__":
    k = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
    send(k)
