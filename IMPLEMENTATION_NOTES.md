# LSB v3.4.0 live-data / Under 0.5 implementation

## What changed
- Added `worker/esd/fotmob.py` as the preferred live provider.
- FotMob match discovery uses `/api/matches` with `/api/data/matches` compatibility fallback.
- FotMob match details uses `/api/matchDetails` with `/api/data/matchDetails` compatibility fallback.
- Added shared Event normalization for FotMob.
- Existing SofaScore and LiveScore feeds remain as fallback providers.
- Under 0.5 HT no longer places a blind bet at exactly 25'.
- Entry window is 23'-35' and requires 0-0 plus live-feature validation.
- Live feature gate uses xG, shots, shots-on-target, corners, big chances, dangerous attacks and red cards when supplied by FotMob.
- Model estimates remaining first-half goal intensity and no-goal probability with a transparent Poisson gate.
- If actual market odds are available, a minimum +5 percentage-point value edge is required.
- If odds are unavailable, no bet is placed; this prevents the bot from treating missing market data as value.
- A paused staking engine now correctly suppresses betting instead of silently falling back to the base stake.
- Polling defaults to 30 seconds.

## Configuration
See `.env.example` for:
- `UNDER05_MARKET_ODDS`
- `UNDER05_MIN_EDGE`
- `UNDER05_MIN_MODEL_PROB`
- `UNDER05_MINUTE_MIN`
- `UNDER05_MINUTE_MAX`
- `UNDER05_MAX_XG_REMAINING`
- `UNDER05_REQUIRE_LIVE_FEATURES`

## Important limitation
FotMob is an unofficial/public web data source rather than a guaranteed commercial API. Endpoint availability and JSON structure can change. The implementation therefore uses multiple endpoint variants and conservative failure behavior.

The probability model is a starting rule-based model and must be calibrated against a much larger historical dataset before being treated as a proven betting edge.
