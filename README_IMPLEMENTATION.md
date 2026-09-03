# LSB v3.4.0 Implementation Guide

LSB v3.4.0 is a conservative live football signal engine for **Under 0.5 First-Half Goals**.

The engine only considers a bet when all required conditions pass:

- The match is in the first-half entry window.
- The score is still 0-0.
- Live match features are available.
- No configured danger threshold is exceeded.
- The model probability is high enough.
- Market odds are available.
- The calculated value edge meets the configured minimum.
- The staking engine is not paused.

Missing data results in **no bet**.

## Runtime Architecture

```text
FotMob live matches
        |
        v
Competition filters
        |
        v
Under 0.5 HT evaluation
        |
        +--> Live features: xG, shots, SOT, corners, big chances
        |
        +--> Red-card and danger filters
        |
        +--> Poisson no-goal probability
        |
        +--> Market odds and value edge
        |
        v
Staking and bankroll controls
        |
        v
Firebase persistence and Telegram notification
```

FotMob is the primary live-data provider. SofaScore and LiveScore remain compatibility fallbacks for live event discovery.

## Entry Rules

Default entry window:

```text
23' through 35'
```

The match must be 0-0. A match with any first-half goal is rejected.

Default danger limits:

```text
Maximum shots on target: 3
Maximum big chances: 1
Maximum corners: 6
Maximum red cards: 0
Maximum remaining xG: 0.58
```

The model estimates remaining first-half goal intensity using:

```text
remaining_minutes = 45 - current_minute
xG_rate = current_xG / max(5, current_minute)
base_remaining_xG = xG_rate * remaining_minutes
```

Live pressure increases the estimated intensity. The no-goal probability is calculated as:

```text
P(0 goals before HT) = exp(-remaining_xG)
```

## Value Calculation

For decimal odds:

```text
implied_probability = 1 / odds
value_edge = model_probability - implied_probability
```

A bet requires a minimum model probability and value edge. If odds are missing, the engine rejects the opportunity rather than assuming a price.

## Configuration

Set these variables in `.env` or the deployment environment:

```dotenv
SLEEP_TIME=30
UNDER05_MARKET_ODDS=
UNDER05_MIN_EDGE=0.05
UNDER05_MIN_MODEL_PROB=0.55
UNDER05_MINUTE_MIN=23
UNDER05_MINUTE_MAX=35
UNDER05_MAX_XG_REMAINING=0.58
UNDER05_MAX_SOT=3
UNDER05_MAX_BIG_CHANCES=1
UNDER05_MAX_CORNERS=6
UNDER05_MAX_RED_CARDS=0
UNDER05_REQUIRE_LIVE_FEATURES=true
```

Required service configuration for live operation:

```dotenv
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
FIREBASE_CREDENTIALS_JSON={...}
INITIAL_BANKROLL=1000
PORT=8000
```

Never commit real Telegram or Firebase credentials.

## Important Modules

| Module | Responsibility |
| --- | --- |
| `worker/main.py` | Supervisor loop, shutdown handling, metrics server, polling interval |
| `worker/bot.py` | Filters, live evaluation, value checks, staking integration, settlement |
| `worker/esd/fotmob.py` | FotMob requests, endpoint fallbacks, normalization, feature extraction |
| `worker/esd/sofascore/service.py` | FotMob-first provider orchestration and legacy fallbacks |
| `worker/esd/sofascore/client.py` | Public client facade for events, details, and live features |
| `worker/staking_engine.py` | Stake state, bankroll, results, pause protection |
| `worker/metrics.py` | Prometheus counters and gauges |

## Windows Console Logging

The supervisor configures console streams and `bot_activity.log` as UTF-8. This prevents Windows `cp1252` encoding errors when diagnostic messages contain Unicode symbols.

The log file is written as:

```text
bot_activity.log
```

## Running Locally

From the project root:

```powershell
C:/Python314/python.exe -m pip install -r requirements.txt
C:/Python314/python.exe worker/main.py
```

The process exposes Prometheus metrics at:

```text
http://localhost:8000/metrics
```

Use valid Firebase and Telegram configuration before starting production operation.

## Validation

Run a syntax check across the worker:

```powershell
C:/Python314/python.exe -m compileall -q worker
```

The project currently has no committed unit-test suite. Live provider responses are external and may change, so FotMob parsing should be checked periodically against current payloads.

## Operational Limitations

- FotMob is an unofficial public web-data source, not a guaranteed commercial API.
- Endpoint structures and availability can change.
- Odds are not guaranteed to be present in FotMob responses.
- The probability model is rule-based and requires historical calibration before being treated as a proven betting edge.
- Firebase credentials are required for state locks, bet persistence, and settlement.
- The engine intentionally fails closed when live features, odds, or risk controls are unavailable.
