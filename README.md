Absolutely. The current README still describes the **old Minute-36 / Martingale strategy**, which is no longer aligned with the implemented Under 0.5 HT engine. The project should replace that README with the following.

The implementation file is the current generated project you provided. 

## 1. Recommended `README.md`

# ⚽ LSB v3.4.0 — Live Under 0.5 HT Value Betting Engine

Automated live football signal engine for **Under 0.5 First-Half Goals**.

LSB v3.4.0 is designed around a simple principle:

> **Do not bet simply because a match is 0-0. Bet only when the live match state indicates a sufficiently high probability that the match remains 0-0 until Half Time AND the available market odds provide positive value.**

The system combines:

* Live football match discovery
* FotMob live data
* xG / expected goals
* shots
* shots on target
* corners
* big chances
* dangerous attacks when available
* red-card detection
* first-half time-window filtering
* Poisson-based remaining-goal probability
* market implied probability
* value-edge calculation
* bankroll/staking controls
* Firebase persistence
* Telegram notifications
* Prometheus metrics
* automatic match-state tracking

---

# 1. Strategy Overview

## Target Market

**Under 0.5 Goals — First Half**

The bet wins when:

```text
Half-Time Score = 0-0
```

The bet loses when:

```text
Half-Time Score = 1-0
0-1
1-1
2-0
0-2
...
```

Any first-half goal causes the Under 0.5 HT bet to lose.

---

# 2. Old Strategy vs v3.4.0

## Old Strategy

The original logic was essentially:

```text
At 25'
    ↓
Score = 0-0
    ↓
BET
```

This is too weak.

A match can be 0-0 at 25' while having:

* 1.5+ xG
* many shots
* several shots on target
* multiple big chances
* high corner pressure
* strong attacking pressure
* a large team-strength mismatch

Such a match can easily produce a goal before HT.

---

# 3. New v3.4.0 Strategy

The new decision process is:

```text
LIVE MATCH
    │
    ▼
MATCH FILTER
    │
    ├── Excluded league?
    ├── Excluded country?
    ├── Cup?
    ├── Youth?
    ├── U19/U21/U23?
    ├── Amateur?
    └── Other excluded competition?
          │
          ▼
      QUALIFIED
          │
          ▼
    FIRST-HALF CHECK
          │
          ▼
      23' → 35'
          │
          ▼
       SCORE 0-0?
          │
      ┌───┴───┐
      │       │
     NO      YES
      │       │
    NO BET    ▼
         LIVE FEATURES
              │
              ▼
       xG / SHOTS / SOT
       CORNERS / CHANCES
       DANGEROUS ATTACKS
       RED CARDS
              │
              ▼
        DANGER FILTER
              │
              ▼
      REMAINING GOAL λ
              │
              ▼
       P(0 GOALS → HT)
              │
              ▼
       MODEL PROBABILITY
              │
              ▼
        MARKET ODDS
              │
              ▼
       IMPLIED PROBABILITY
              │
              ▼
       VALUE EDGE CHECK
              │
              ▼
       STAKING ENGINE
              │
              ▼
           BET
```

---

# 4. Live Data Provider Architecture

The system is designed for environments where SofaScore or LiveScore may block the server IP.

## Provider Priority

```text
                    ┌───────────────┐
                    │ Match Scanner │
                    └───────┬───────┘
                            │
                            ▼
                     ┌─────────────┐
                     │   FotMob    │
                     │  PRIMARY    │
                     └──────┬──────┘
                            │
                     failed/blocked
                            │
                            ▼
                     ┌─────────────┐
                     │ SofaScore   │
                     │ FALLBACK    │
                     └──────┬──────┘
                            │
                     failed/blocked
                            │
                            ▼
                     ┌─────────────┐
                     │  LiveScore  │
                     │ FALLBACK    │
                     └─────────────┘
```

FotMob is the preferred provider because the current deployment environment may receive IP blocks from SofaScore and LiveScore.

The FotMob implementation is located at:

```text
worker/esd/fotmob.py
```

---

# 5. FotMob Data

The provider attempts to retrieve:

```text
Match discovery
Match status
Current minute
Home score
Away score
Competition
Country
xG
Shots
Shots on target
Corners
Big chances
Dangerous attacks
Red cards
Incidents
Market odds where available
```

The implementation also supports multiple endpoint variants and a page-data fallback.

Important:

> FotMob is treated as a public web-data source, not a guaranteed commercial API.

Its response structure can change.

Therefore the code uses defensive parsing and failure handling.

---

# 6. Live Polling

Default polling:

```text
SLEEP_TIME=30
```

Therefore the bot checks live matches approximately every:

```text
30 seconds
```

The purpose is to continuously monitor the 23'–35' decision window rather than relying on a single exact minute.

---

# 7. Entry Window

The system does NOT require exactly 25'.

Current configuration:

```text
Minimum minute = 23
Maximum minute = 35
```

Therefore:

```text
23'
24'
25'
26'
27'
28'
29'
30'
31'
32'
33'
34'
35'
```

are valid evaluation times.

The actual bet can occur at any qualifying point inside this window.

---

# 8. First Mandatory Condition

The match must still be:

```text
0-0
```

If:

```text
1-0
0-1
1-1
2-0
0-2
...
```

the system immediately rejects the Under 0.5 HT opportunity.

Reason:

```text
Under 0.5 HT already lost its required 0-0 state.
```

---

# 9. Live Feature Validation

A live feature feed is required.

Current configuration:

```text
UNDER05_REQUIRE_LIVE_FEATURES=true
```

The engine examines:

```text
xG
Shots
Shots on Target
Corners
Big Chances
Dangerous Attacks
Red Cards
```

The most important inputs are:

1. xG
2. shots on target
3. big chances
4. shots
5. corners
6. attacking pressure
7. red cards

---

# 10. Hard Danger Filters

The strategy rejects a match when certain live danger conditions are reached.

Current defaults:

```text
Maximum SOT       = 3
Maximum Big Chance = 1
Maximum Corners   = 6
Maximum Red Cards = 0
Maximum Remaining xG = 0.58
```

Examples:

```text
Red cards > 0
→ NO BET
```

```text
Big chances > 1
→ NO BET
```

```text
Shots on target > 3
→ NO BET
```

```text
Corners > 6
→ NO BET
```

These are deliberately conservative because the current model has not yet been statistically calibrated for every match regime.

---

# 11. Remaining Goal Intensity

The engine estimates expected goals remaining until HT.

Let:

```text
M = current minute
R = 45 - M
```

The current live xG rate is approximated by:

```text
xG_rate = current_xG / max(5, M)
```

Initial remaining xG:

```text
base_remaining = xG_rate × remaining_minutes
```

Then the engine increases the estimated goal hazard when live pressure is high.

Pressure adjustments are applied for:

```text
Shots on target
Big chances
Corners
High shot volume
Dangerous attacks
```

Therefore:

```text
More attacking pressure
        ↓
Higher λ_remaining
        ↓
Lower probability of 0-0 HT
        ↓
Less likely to bet
```

---

# 12. Poisson Probability

The model uses a Poisson approximation.

If:

```text
λ = expected goals remaining until HT
```

then:

```text
P(0 goals) = e^(-λ)
```

Example:

```text
λ = 0.20

P(0 goals)
= e^-0.20
≈ 81.9%
```

Example:

```text
λ = 0.50

P(0 goals)
= e^-0.50
≈ 60.7%
```

Example:

```text
λ = 0.80

P(0 goals)
= e^-0.80
≈ 44.9%
```

Therefore:

```text
Lower λ
    =
Higher Under 0.5 HT probability
```

---

# 13. Model Probability Requirement

Current minimum:

```text
UNDER05_MIN_MODEL_PROB=0.55
```

Therefore:

```text
Model probability >= 55%
```

is required before the market-value calculation can pass.

However:

> 55% by itself does NOT mean a bet should be placed.

The market price must also provide sufficient value.

---

# 14. Value Betting

The strategy separates:

```text
Prediction
```

from:

```text
Value
```

These are different concepts.

## Market Probability

For decimal odds:

```text
Market Probability = 1 / Odds
```

Example:

```text
Odds = 2.00

Market Probability
= 1 / 2.00
= 50%
```

If the model says:

```text
P(Under 0.5 HT) = 56%
```

then:

```text
Model = 56%
Market = 50%

Edge = 56% - 50%
     = +6%
```

This is a positive-value candidate.

---

# 15. Minimum Value Edge

Current configuration:

```text
UNDER05_MIN_EDGE=0.05
```

Meaning:

```text
Minimum edge = +5 percentage points
```

Example:

```text
Odds: 2.00
Market probability: 50%

Model probability: 56%

Edge: +6%

6% > 5%

→ VALUE BET
```

But:

```text
Model = 52%
Market = 50%

Edge = +2%

2% < 5%

→ NO BET
```

---

# 16. Odds Examples

| Odds | Market Probability | Minimum Model for +5% Edge |
| ---: | -----------------: | -------------------------: |
| 1.60 |             62.50% |                     67.50% |
| 1.70 |             58.82% |                     63.82% |
| 1.80 |             55.56% |                     60.56% |
| 1.90 |             52.63% |                     57.63% |
| 2.00 |             50.00% |                     55.00% |
| 2.10 |             47.62% |                     52.62% |
| 2.20 |             45.45% |                     50.45% |

This is why odds are extremely important.

The same match can be:

```text
GOOD BET at 2.10
```

but:

```text
BAD BET at 1.70
```

even though the underlying match probability has not changed.

---

# 17. Missing Odds

The system intentionally does NOT assume that missing odds are good odds.

If no actual market price is available:

```text
NO ODDS
    ↓
NO VALUE CALCULATION
    ↓
NO BET
```

This is safer than inventing a price.

Optional configuration:

```text
UNDER05_MARKET_ODDS=
```

This should only be populated when it represents the actual sportsbook price being used.

---

# 18. Safety Score

The engine also creates a transparent 0–100 safety score.

Starting value:

```text
100
```

Penalties are applied for:

```text
xG
SOT
shots
big chances
corners
```

Conceptually:

```text
100
 - xG penalty
 - SOT penalty
 - shots penalty
 - big chance penalty
 - corner penalty
 =
Safety Score
```

Higher:

```text
Safety Score = safer Under candidate
```

Lower:

```text
Safety Score = more dangerous match
```

The score is primarily diagnostic in the current implementation.

It should eventually be calibrated using historical results.

---

# 19. Staking

The strategy should NOT use Martingale to recover losses.

The recommended philosophy is:

```text
Good signal
+
Positive expected value
+
Controlled bankroll exposure
```

Current bankroll configuration:

```text
INITIAL_BANKROLL=1000
```

Recommended risk:

```text
0.5% – 1.0% bankroll per normal bet
```

For a $1,000 bankroll:

```text
0.5% = $5
1.0% = $10
```

Maximum recommended exposure:

```text
1.5% = $15
```

Do not chase previous losses.

---

# 20. Staking State Protection

If the staking engine is paused:

```text
STAKING PAUSED
       ↓
NO BET
```

The bot must NOT silently fall back to the base stake.

This prevents the strategy from bypassing bankroll protection.

---

# 21. Daily Risk Protection

Recommended configuration:

```text
Maximum daily exposure ≈ 5%
Daily stop-loss ≈ 3%
Hard stop-loss ≈ 5%
```

Example with $1,000:

```text
3% daily stop = -$30
5% hard stop = -$50
```

If the daily stop is reached:

```text
STOP NEW BETS
```

The system should continue monitoring and recording signals but should not continue risking capital.

---

# 22. League Filtering

The engine supports:

```text
EXCLUDED_COUNTRIES
EXCLUDED_LEAGUES
EXCLUDED_COMBINATIONS
EXCLUDED_KEYWORDS
```

Examples:

```text
Youth
U18
U19
U21
U23
reserves
amateur
college
```

can be excluded.

This is important because different competition types have different scoring distributions.

---

# 23. Recommended Competition Segmentation

Do not assume all football competitions behave identically.

Recommended groups:

```text
Tier A
Major professional leagues
Stable data
Large sample
Normal stake

Tier B
Smaller professional leagues
Moderate sample
Reduced stake

Tier C
Low-data competitions
Unstable information
Paper trading only

Tier D
Youth / amateur / unusual cups
Avoid until separately modeled
```

Women’s football should also be evaluated as a separate statistical model.

---

# 24. Cup Match Protection

Cup matches can contain:

* huge team-strength differences
* rotations
* reserve players
* unusual incentives
* knockout-game dynamics
* extra-time considerations
* semi-professional opposition

Therefore cup matches should initially be:

```text
Excluded
```

or:

```text
Separate model
```

until enough historical data exists.

---

# 25. Match State Machine

Each match has an internal state.

Example:

```text
DISCOVERED
    ↓
MONITORING
    ↓
23–35 MINUTE WINDOW
    ↓
QUALIFICATION
    ↓
EVALUATION
    ↓
NO BET
```

or:

```text
DISCOVERED
    ↓
MONITORING
    ↓
QUALIFICATION
    ↓
VALUE CONFIRMED
    ↓
BET PLACED
    ↓
WAIT FOR HT
    ↓
WIN / LOSS
    ↓
RESOLVED
```

This prevents duplicate bets.

---

# 26. Duplicate-Bet Protection

Before placing a bet:

```text
Check Firebase unresolved_bets_under0.5
```

If an active state exists:

```text
NO SECOND BET
```

This prevents the same match from being bet multiple times during the 30-second polling cycle.

---

# 27. Half-Time Settlement

At HT:

```text
Score = 0-0
    ↓
WIN
```

Any goal:

```text
Score != 0-0
    ↓
LOSS
```

Example:

```text
0-0 → WIN
1-0 → LOSS
0-1 → LOSS
1-1 → LOSS
2-0 → LOSS
```

---

# 28. Firebase Data

Unresolved bets are stored separately from resolved bets.

Conceptually:

```text
unresolved_bets_under0.5
        ↓
     HT result
        ↓
resolved_bets_under0.5
```

Each bet should contain:

```text
match_name
league
country
bet_time
score_at_bet
stake
bet_type
provider
market_odds
implied_probability
model_probability
value_edge
safety_score
xg_remaining
live_features
```

This is critical for future model training.

---

# 29. Why Feature Logging Matters

The system should not only record:

```text
WIN
LOSS
```

It should record the complete state at the time of the bet.

For example:

```json
{
  "minute": 27,
  "score": "0-0",
  "xg": 0.18,
  "shots": 5,
  "shots_on_target": 1,
  "corners": 2,
  "big_chances": 0,
  "red_cards": 0,
  "model_probability": 0.78,
  "market_odds": 2.10,
  "implied_probability": 0.476,
  "edge": 0.304,
  "result": "win"
}
```

This allows the strategy to be optimized later.

---

# 30. Future Machine-Learning Dataset

The long-term objective is:

```text
LIVE FEATURES
      ↓
HISTORICAL DATASET
      ↓
MODEL TRAINING
      ↓
PROBABILITY CALIBRATION
      ↓
VALUE DETECTION
      ↓
BETTING
```

Useful features include:

```text
minute
score
home xG
away xG
combined xG
shots
shots on target
corners
big chances
dangerous attacks
possession
red cards
yellow cards
pre-match odds
live odds
opening odds
closing odds
league
country
home team
away team
team strength
first-half scoring rate
0-0 HT frequency
recent form
lineups
substitutions
result
```

---

# 31. CLV Tracking

The system should eventually track:

**Closing Line Value (CLV)**.

Example:

```text
Bet Under 0.5 HT @ 2.10
Later market price = 1.90
```

This indicates the market moved toward the selection.

Conversely:

```text
Bet @ 1.80
Later = 2.10
```

indicates adverse movement.

CLV is useful because a good betting process can experience short-term losses while still consistently obtaining favorable prices.

---

# 32. Recommended Validation Target

The current 40-bet sample is too small to prove an edge.

Recommended minimum:

```text
500 bets
```

Better:

```text
1,000+ bets
```

Before increasing stakes.

The test should compare:

```text
20' entry
23' entry
25' entry
27' entry
30' entry
32' entry
35' entry
```

and different thresholds for:

```text
xG
SOT
shots
corners
big chances
model probability
value edge
```

---

# 33. Backtesting Objective

The goal is NOT:

```text
Generate more bets
```

The goal is:

```text
Reject bad bets
```

A successful strategy may produce fewer signals.

For example:

```text
Old system:

100 matches
100 bets
42% win rate
Negative ROI
```

Better system:

```text
100 matches
25 qualified bets
58% win rate
Positive expected value
```

The second system is preferable even though it produces fewer bets.

---

# 34. Core Decision Rule

The final decision can be summarized as:

```python
if minute < 23:
    NO_BET

elif minute > 35:
    NO_BET

elif score != "0-0":
    NO_BET

elif live_features_unavailable:
    NO_BET

elif red_cards > 0:
    NO_BET

elif shots_on_target > 3:
    NO_BET

elif big_chances > 1:
    NO_BET

elif corners > 6:
    NO_BET

else:
    calculate_remaining_goal_lambda()

    model_probability = exp(-lambda_remaining)

    if model_probability < 0.55:
        NO_BET

    elif lambda_remaining > 0.58:
        NO_BET

    else:
        obtain_market_odds()

        if odds_unavailable:
            NO_BET

        else:
            market_probability = 1 / odds

            edge = model_probability - market_probability

            if edge < 0.05:
                NO_BET

            elif staking_engine_paused:
                NO_BET

            else:
                PLACE_BET
```

---

# 35. Final Strategy Philosophy

LSB v3.4.0 should operate according to:

```text
DATA
 ↓
FILTER
 ↓
LIVE STATE
 ↓
PROBABILITY
 ↓
VALUE
 ↓
RISK
 ↓
STAKE
 ↓
BET
```

Never:

```text
0-0
 ↓
BET
```

Never:

```text
LOSS
 ↓
DOUBLE STAKE
```

Never:

```text
NO ODDS
 ↓
ASSUME VALUE
```

Never:

```text
API FAILED
 ↓
USE STALE DATA
```

The correct behavior is:

```text
INSUFFICIENT INFORMATION
        ↓
      NO BET
```

---

# 36. Recommended Production Configuration

```env
INITIAL_BANKROLL=1000

SLEEP_TIME=30

UNDER05_MINUTE_MIN=23
UNDER05_MINUTE_MAX=35

UNDER05_MIN_MODEL_PROB=0.55
UNDER05_MIN_EDGE=0.05

UNDER05_MAX_XG_REMAINING=0.58

UNDER05_MAX_SOT=3
UNDER05_MAX_BIG_CHANCES=1
UNDER05_MAX_CORNERS=6
UNDER05_MAX_RED_CARDS=0

UNDER05_REQUIRE_LIVE_FEATURES=true

PROMETHEUS_ENABLED=true
```

---

# 37. Important Disclaimer

This system is an automated decision-support and betting-engine project.

A positive model probability does not guarantee a winning bet.

The probability model currently uses a transparent rule-based/Poisson approximation and requires calibration using a substantially larger historical dataset.

Before using real money:

1. Run paper trading.
2. Collect at least 500–1,000 qualifying opportunities.
3. Store complete live features.
4. Compare predicted probability with actual outcomes.
5. Measure ROI.
6. Measure maximum drawdown.
7. Measure CLV.
8. Recalibrate thresholds.
9. Only then consider increasing stake size.

---

# 38. Project Structure

```text
new_32_lsb_corner-main/
│
├── worker/
│   ├── main.py
│   ├── bot.py
│   ├── metrics.py
│   ├── staking_engine.py
│   │
│   └── esd/
│       ├── fotmob.py
│       ├── utils.py
│       │
│       └── sofascore/
│           ├── client.py
│           ├── endpoints.py
│           ├── service.py
│           └── types/
│
├── backup/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

# 39. Operational Flow

Every 30 seconds:

```text
1. Discover live matches
2. Normalize match data
3. Apply competition filters
4. Check first-half status
5. Check 23–35 minute window
6. Check score
7. Retrieve live details
8. Extract live statistics
9. Calculate remaining goal intensity
10. Calculate P(0 goals until HT)
11. Check minimum probability
12. Retrieve market odds
13. Calculate implied probability
14. Calculate value edge
15. Check staking state
16. Calculate stake
17. Store bet
18. Send Telegram alert
19. Monitor until HT
20. Resolve WIN/LOSS
21. Update bankroll
22. Record metrics
```

This is the intended architecture for LSB v3.4.0.

## 2. Coding logic — simplified architecture

The important thing is that the code should be thought of as **six independent layers**, not one giant betting condition:

```text
┌──────────────────────────────────────────────┐
│                 LSB v3.4.0                  │
├──────────────────────────────────────────────┤
│ 1. DATA LAYER                               │
│    FotMob → SofaScore → LiveScore           │
├──────────────────────────────────────────────┤
│ 2. FILTER LAYER                             │
│    League / Country / Youth / Cup filters   │
├──────────────────────────────────────────────┤
│ 3. LIVE ANALYSIS                            │
│    xG / shots / SOT / corners / chances     │
├──────────────────────────────────────────────┤
│ 4. PROBABILITY MODEL                        │
│    λ remaining → P(0 goals)                 │
├──────────────────────────────────────────────┤
│ 5. VALUE ENGINE                             │
│    Odds → implied probability → edge        │
├──────────────────────────────────────────────┤
│ 6. RISK / EXECUTION                         │
│    bankroll → stake → Firebase → Telegram   │
└──────────────────────────────────────────────┘
```

### Core pseudocode

```python
def evaluate_match(match):

    # 1. Competition filter
    if is_match_excluded(match):
        return NO_BET("excluded competition")

    # 2. Match phase
    minute = get_current_minute(match)

    if not 23 <= minute <= 35:
        return NO_BET("outside entry window")

    # 3. Score
    if get_score(match) != (0, 0):
        return NO_BET("goal already scored")

    # 4. Live data
    features = provider.get_match_features(match.id)

    if not features:
        return NO_BET("live data unavailable")

    # 5. Hard danger filters
    if features.red_cards > 0:
        return NO_BET("red card")

    if features.shots_on_target > 3:
        return NO_BET("high SOT")

    if features.big_chances > 1:
        return NO_BET("big chances")

    if features.corners > 6:
        return NO_BET("high corner pressure")

    # 6. Probability
    lambda_remaining = calculate_remaining_xg(
        minute=minute,
        xg=features.xg,
        shots=features.shots,
        sot=features.shots_on_target,
        corners=features.corners,
        big_chances=features.big_chances,
        dangerous_attacks=features.dangerous_attacks
    )

    model_probability = math.exp(-lambda_remaining)

    # 7. Probability gate
    if model_probability < 0.55:
        return NO_BET("probability too low")

    if lambda_remaining > 0.58:
        return NO_BET("remaining xG too high")

    # 8. Market
    odds = get_actual_market_odds(match)

    if odds is None:
        return NO_BET("odds unavailable")

    implied_probability = 1 / odds

    # 9. Value
    edge = model_probability - implied_probability

    if edge < 0.05:
        return NO_BET("insufficient value")

    # 10. Risk
    if staking_engine.is_paused:
        return NO_BET("staking paused")

    stake = staking_engine.calculate_stake()

    if stake <= 0:
        return NO_BET("zero stake")

    # 11. Execute
    return PLACE_BET(
        stake=stake,
        odds=odds,
        model_probability=model_probability,
        implied_probability=implied_probability,
        edge=edge,
        lambda_remaining=lambda_remaining
    )
```

### The most important formula

For the current strategy:

```text
λ_remaining
      ↓
P(Under 0.5 HT)
      ↓
e^(-λ_remaining)
      ↓
Model Probability
      ↓
compare against sportsbook
      ↓
Value Edge
```

So the actual decision becomes:

```text
             MODEL
               │
               │ 56%
               ▼
        ┌───────────────┐
        │ Probability   │
        │     56%       │
        └───────┬───────┘
                │
                ▼
       SPORTSBOOK ODDS
            2.10
                │
                ▼
       IMPLIED PROBABILITY
             47.62%
                │
                ▼
       VALUE EDGE
       56 - 47.62
          = +8.38%
                │
                ▼
       +8.38% > +5%
                │
                ▼
             BET
```

Whereas:

```text
Model = 52%
Odds = 2.00
Market = 50%

Edge = +2%

+2% < +5%

→ NO BET
```

**This is the major conceptual upgrade I recommend for your bot:** the system should become a **selective value-betting engine**, not a 0-0 detection bot.

One implementation detail is worth correcting before production: the current `bot.py` contains the new `evaluate_under05_live()` logic, but the call path shown in the project still references `SOFASCORE_CLIENT` for the live-feature/detail retrieval.  That should be cleaned up so the provider abstraction truly follows **FotMob → fallback provider**, rather than having FotMob implemented but still being reached indirectly through the SofaScore client. This is particularly important given your IP-block problem.

If you want, I can next produce the **exact V3.4.0 coding specification for every function/class** (`FotMobProvider`, `LiveDataProvider`, `Under05Model`, `ValueEngine`, `RiskEngine`, `StakingEngine`, `BetRepository`, and `SignalEngine`) so the project has a clean production architecture rather than just adding more conditions into `bot.py`.
