# AI Hedge Fund — persona-driven trading desk

A simulated hedge fund that **doesn't use machine learning to trade**. Instead, it
sends each day's real market data to a desk of **AI agents with distinct
personalities** (a macro strategist, a quant, a sentiment analyst, a head of risk),
they hold **scheduled meetings** during the work day, and the **CIO (PM)
synthesizes one decisive position**. You — the boss — receive a **morning opening
report** and an **evening close report**. The midday sync is internal only.

> ⚠️ This is a simulation / decision-support tool, **not financial advice**, and
> **not an autonomous money machine**. Execution is **dry-run by default** — it
> never places a real order unless you explicitly arm live trading.

## What each persona "does" (their job)
| Persona | Role | Bias |
|---|---|---|
| Dr. Helena Voss | Macro Strategist | Regimes, liquidity, cautious |
| Kenji Arai | Quant / Systematic | Price/volatility only, cold |
| Mara Quinn | Sentiment & Flow | Contrarian, crowd positioning |
| Dmitri Sokolov | Head of Risk | Tail risk, invalidate the trade |
| Eleanor Cross | CIO / PM | Synthesizes the desk into one call |

## Paper equity, leverage, drawdown & the +1%/month mandate
The firm runs a **paper book** (`book.py`) — a simulated notional account (default
$1,000,000), no real money. The CIO's daily decision deploys a paper position; at
**CLOSE** it's marked to market against the real price and the day's P&L is booked.

**Hard firm constraints (mechanically enforced by the book, not just talk):**
- **Leverage:** up to **1:100**. `SIZE` is margin % of book; notional = margin% × leverage.
  Default for a normal day is LOW (e.g. 2% margin × 1–3).
- **Max drawdown:** **−7%** from peak equity is a **HARD STOP-OUT**. If account value
  would fall >7% below peak, all positions are force-closed and the book is **halted**
  — but it **auto-resumes after a 48h cooldown** (not locked until month-end). The
  monthly scorecard still resets everything on the 1st.
- **Objective:** **+1.0% net/month**. Wired into the CIO prompt; desk told not to force
  trades to hit the number.

Every boss report shows: paper equity, day P&L, **MTD return vs +1% target + progress**,
max leverage used (ceiling 100:1), and **max drawdown MTD (hard limit −7%)**.

**Monthly Scorecard** (cron on the 1st, 09:00, to boss): the just-ended month's return
vs +1%, win-rate, gross P&L, max leverage, max drawdown, and halt events — then resets
the trackers for the new cycle.

> Still a simulation. Paper equity is a ledger for you to read; no broker is touched.

## Research desk (find → backtest → bring to the meeting)
A research agent (`research.py` + `backtest.py`) hunts for strategies and brings them
to the desk as agenda items to debate:
- `research.py` picks/requests a strategy, runs it through `backtest.py` on the firm's
  **real daily price history** (`history.json`, fetched from CoinGecko), and emits a
  one-page brief.
- `backtest.py` is a small, honest vectorized backtester (momentum / mean-reversion /
  breakout) reporting return, win-rate, max drawdown, and a buy&hold baseline. No ML,
  no lookahead.
- The brief is injected into the **OPENING meeting** prompt. Macro/Quant/Sentiment/Risk
  debate ADOPT / REJECT / PILOT, and the CIO votes with a max size that respects the
  −7% DD limit and 1:100 leverage.

Refresh history: `python fetch_history.py` (or it's pulled on demand).

## News Reporter (daily BTC news → desk context)
A News Reporter persona (**Nick Reed**) scans Bitcoin/crypto news every morning via the
browser (`news.py` + `browser_exec`), extracting fresh headlines, tagging sentiment
(bullish/bearish/neutral), and deduping them into a DAILY NEWS BRIEF. The brief is
injected into the OPENING (and MIDDAY) meeting so Macro/Quant/Sentiment/Risk/CIO decide
**with** the news flow, not blind. Sources: CryptoPanic, Cointelegraph, Bitcoin Magazine,
CoinGecko News (all server-rendered, no key). The reporter flags the 2-3 headlines most
likely to move BTC/ETH and separates FUD from real signal.

## Work-day timetable
- **08:00 OPENING** → boss report (plan + opening bias)
- **13:00 MIDDAY** → internal only (drift check, logged, not sent to boss)
- **17:30 CLOSE** → boss report (P&L vs plan, carry into tomorrow)
- **1st 09:00 SCORECARD** → boss report (month vs +1%)
- **Fri 17:00 WEEKLY NEWS DIGEST** → boss (narrative arc of the week's BTC news)

## Live dashboard (web app)
`dashboard_app.py` (Python **stdlib only** — no pip) serves a Bloomberg/hedge-fund styled
SPA (`index.html`, responsive — looks good on iPhone) at `http://localhost:8765`. It
exposes `GET /api/state` (live CoinGecko prices + Fear&Greed + paper book + meetings +
research + news) and polls every 5s. Shows live tickers, paper book + mandate progress,
positions history, desk analysis (CIO + personas), research briefs, daily news, weekly digest.

**Run it (persistent, self-healing):**
```
cd ai_hedge_fund
npm install localtunnel        # one-time, for the free public tunnel
python start_desk.py           # starts dashboard + localtunnel, auto-restarts both
```
`start_desk.py` writes the current public URL to `public_url.txt` and restarts either
process if it dies. A Windows Scheduled Task (`HermesDeskDashboard`, ONLOGON) relaunches
it after a reboot — so the desk comes back on its own. The public URL is a random
`*.loca.lt` subdomain that changes on each restart (read `public_url.txt` for the current one).

**For a FIXED permanent URL** (never changes) you need a free account on a host:
- **Render**: push the folder to GitHub, create a Web Service (start cmd `python dashboard_app.py 8765`,
  health check `/api/state`). Gets a permanent `*.onrender.com` URL.
- **PythonAnywhere**: upload + make `dashboard_app.py` a web app on a manual port.
- **localhost.run custom domain**: free SSH key → fixed subdomain.
Drop me a Render/GitHub token and I'll do the permanent deploy.

## Project layout
```
ai_hedge_fund/
  fetch_snapshot.py   pull real daily data -> market_snapshot.json
  data_provider.py    render briefing from snapshot
  agents.py           the personas (system prompts + personalities)
  schedule.py         meeting engine (OPENING/MIDDAY/CLOSE)
  report.py           boss-facing report rendering
  run_firm.py         run a full day (OPENING->MIDDAY->CLOSE)
  execution.py        dry-run broker stub (live gated by 2 env flags)
  llm_backend.py      OpenAI-compatible client (optional key)
  meeting_logs/       per-meeting minutes (JSON)
  position_of_the_day.json  latest CIO call
```

## How it "thinks" (no ML, just roles)
Each meeting, the runtime adopts every persona in turn and lets them argue from the
SAME real data, each through their own biased lens. The CIO reads all four views and
cuts ONE decision in a fixed format:
```
DECISION: LONG|SHORT|FLAT
INSTRUMENT: BTC / ETH / crypto basket
THESIS: ...
ENTRY / STOP / TARGET / SIZE / CONVICTION / DESK DISSENT
```

## Run it
```bash
pip install openai python-dotenv requests
python fetch_snapshot.py          # refresh real data
python run_firm.py OPENING        # one meeting
python run_firm.py                # full simulated day
```

### With a real model (optional)
Add `.env`:
```
LLM_API_KEY=sk-...        # your OpenAI-compatible key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```
With a key set, the desk consults that model. Without one, the orchestrator (e.g.
Hermes) plays the personas itself.

### Live trading (OFF by default — do not enable blindly)
```bash
EXEC_LIVE=1
EXEC_CONFIRMED=YES
```
Both must be set AND you must implement `place_order()` in `execution.py` for your
broker. Dry-run is the default and safest mode.

## Disclaimer
Simulated opinions of fictional AI personas. Not investment advice. Markets can go
to zero. You are responsible for any real capital you deploy.
