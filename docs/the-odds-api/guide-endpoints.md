<!-- Fuente: https://the-odds-api.com/liveapi/guides/v4/ | Fetched: 2026-07-06 -->

# The Odds API V4 Guide — Detailed Endpoints

## 1. GET /v4/sports

**Returns:** List of in-season sports.

**Cost:** 0 (FREE — does not count toward quota)

### Endpoint

```
GET /v4/sports/?apiKey={apiKey}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `apiKey` | string | Yes | Your API key |
| `all` | boolean | No | If `all=true`, returns both in-season and out-of-season sports |

### Example Request

```
GET https://api.the-odds-api.com/v4/sports/?apiKey=YOUR_API_KEY
```

### Response

Array of sport objects:

```json
[
  {
    "key": "americanfootball_nfl",
    "group": "American Football",
    "title": "NFL",
    "description": "National Football League",
    "active": true
  },
  ...
]
```

### Response Headers

- `x-requests-remaining`: Credits remaining (not decremented for this endpoint)
- `x-requests-used`: Total credits used this month
- `x-requests-last`: 0 (this endpoint has no cost)

---

## 2. GET /v4/sports/{sport}/odds

**Returns:** Upcoming and live game odds for a given sport, region, and market.

**Cost:** `[markets] × [regions]` or `[markets] × ceil([bookmakers] / 10)`

### Endpoint

```
GET /v4/sports/{sport}/odds/?apiKey={apiKey}&regions={regions}&markets={markets}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `sport` | string | Yes | Sport key from `/sports` endpoint (e.g., `americanfootball_nfl`, `basketball_nba`) |
| `apiKey` | string | Yes | Your API key |
| `regions` | string | Conditional | Comma-separated region codes (e.g., `us,uk,au`). Either `regions` or `bookmakers` required |
| `bookmakers` | string | Conditional | Comma-separated bookmaker keys. Overrides `regions` if both specified. Max ~10 bookmakers = 1 region cost |
| `markets` | string | Yes | Comma-separated market keys: `h2h` (moneyline), `spreads` (handicap), `totals` (over/under), `outrights` (futures) |
| `oddsFormat` | string | No | `decimal` (default) or `american` |
| `dateFormat` | string | No | `iso` (default) or `unix` |
| `eventIds` | string | No | Filter by comma-separated event IDs |
| `commenceTimeFrom` | string | No | ISO 8601 timestamp; filter events on/after this time |
| `commenceTimeTo` | string | No | ISO 8601 timestamp; filter events on/before this time |
| `includeLinks` | boolean | No | If `true`, include bookmaker links to events/betslips |
| `includeSids` | boolean | No | If `true`, include bookmaker source IDs |
| `includeBetLimits` | boolean | No | If `true`, include bet limits (mainly for exchanges) |
| `includeRotationNumbers` | boolean | No | If `true`, include rotation numbers (home/away) |

### Available Markets

- **`h2h`** (Head-to-Head / Moneyline) — Pick the winner
- **`spreads`** (Point Spreads / Handicap) — Mainly US sports and selected bookmakers
- **`totals`** (Over/Under) — Mainly US sports and selected bookmakers
- **`outrights`** (Futures) — Long-term bets (e.g., championship winner)

For sports with outright markets (e.g., Golf), `outrights` is the default if not specified.

Lay odds (`h2h_lay`, `outrights_lay`) are automatically included for relevant betting exchanges (Betfair, Matchbook, etc.).

### Example Request

```
GET https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/?apiKey=YOUR_API_KEY&regions=us&markets=h2h,spreads&oddsFormat=american
```

### Response Structure

```json
[
  {
    "id": "event_id_123",
    "sport_key": "americanfootball_nfl",
    "sport_title": "NFL",
    "commence_time": "2023-09-10T00:20:00Z",
    "home_team": "Tampa Bay Buccaneers",
    "away_team": "Dallas Cowboys",
    "bookmakers": [
      {
        "key": "fanduel",
        "title": "FanDuel",
        "last_update": "2023-09-09T10:46:09Z",
        "markets": [
          {
            "key": "h2h",
            "last_update": "2023-09-09T10:46:09Z",
            "outcomes": [
              {
                "name": "Tampa Bay Buccaneers",
                "price": 2.50
              },
              {
                "name": "Dallas Cowboys",
                "price": 1.52
              }
            ]
          }
        ]
      }
    ]
  }
]
```

### Notes

- Results mirror listings from major bookmakers; includes current round games
- Events may temporarily be unavailable after a round or if sport is out-of-season
- If no events are returned, the request does **not** count against quota
- To detect in-play events: if `commence_time` < current time, the event is live
- The `/odds` endpoint does **not** return completed events

### Cost Example

Requesting `/v4/sports/basketball_nba/odds?markets=h2h,spreads,totals&regions=us,uk,au`  
→ 3 markets × 3 regions = **9 credits**

---

## 3. GET /v4/sports/{sport}/scores

**Returns:** Upcoming, live, and recently completed game scores.

**Cost:** 1 credit (no `daysFrom` parameter) or 2 credits (with `daysFrom` parameter)

**Availability:** Selected sports only, expanding over time. Check `/sports-odds-data/sports-apis.html` for coverage.

### Endpoint

```
GET /v4/sports/{sport}/scores/?apiKey={apiKey}&daysFrom={daysFrom}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `sport` | string | Yes | Sport key (e.g., `basketball_nba`) |
| `apiKey` | string | Yes | Your API key |
| `daysFrom` | integer | No | Return games completed within this many days (1–3). If omitted, only live/upcoming games returned |
| `dateFormat` | string | No | `iso` (default) or `unix` |
| `eventIds` | string | No | Filter by comma-separated event IDs |

### Example Request

```
GET https://api.the-odds-api.com/v4/sports/basketball_nba/scores/?apiKey=YOUR_API_KEY&daysFrom=1
```

### Response

Similar to `/odds`, but games include score data:

```json
[
  {
    "id": "event_id_456",
    "sport_key": "basketball_nba",
    "commenced_time": "2023-09-09T10:46:09Z",
    "home_team": "Los Angeles Lakers",
    "away_team": "Golden State Warriors",
    "scores": [
      {
        "name": "Los Angeles Lakers",
        "score": 105
      },
      {
        "name": "Golden State Warriors",
        "score": 103
      }
    ]
  }
]
```

### Notes

- Live scores update approximately every 30 seconds
- Only live and completed games have score data
- Scores update with `daysFrom=0` (omitted): returns upcoming + live games, live games will have scores

---

## 4. GET /v4/sports/{sport}/events

**Returns:** Upcoming and in-play events (event IDs, teams, commence times). **No odds included.**

**Cost:** 0 (FREE — does not count toward quota)

### Endpoint

```
GET /v4/sports/{sport}/events/?apiKey={apiKey}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `sport` | string | Yes | Sport key |
| `apiKey` | string | Yes | Your API key |
| `dateFormat` | string | No | `iso` (default) or `unix` |
| `eventIds` | string | No | Filter by comma-separated event IDs |
| `commenceTimeFrom` | string | No | ISO 8601 timestamp (lower bound) |
| `commenceTimeTo` | string | No | ISO 8601 timestamp (upper bound) |
| `includeRotationNumbers` | boolean | No | If `true`, include rotation numbers |

### Example Request

```
GET https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events/?apiKey=YOUR_API_KEY
```

### Response

```json
[
  {
    "id": "event_id_789",
    "sport_key": "americanfootball_nfl",
    "sport_title": "NFL",
    "commence_time": "2023-09-10T00:20:00Z",
    "home_team": "Tampa Bay Buccaneers",
    "away_team": "Dallas Cowboys"
  }
]
```

---

## 5. GET /v4/sports/{sport}/events/{eventId}/odds

**Returns:** All available odds for a single event (supports any market, including player props).

**Cost:** `[unique markets returned] × [regions]`

### When to Use

Use when you need odds for **all** available markets for one event (not just h2h/spreads/totals). Useful for niche betting markets (player props, period markets, etc.).

For the main markets (h2h, spreads, totals), the main `/odds` endpoint is simpler and more cost-effective if querying multiple events.

### Endpoint

```
GET /v4/sports/{sport}/events/{eventId}/odds/?apiKey={apiKey}&regions={regions}&markets={markets}
```

### Parameters

Same as `/odds` endpoint, plus:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `eventId` | string | Yes | Event ID from `/events` endpoint |
| `includeMultipliers` | boolean | No | For US DFS sites; include multipliers if `true` |

### Response

```json
{
  "id": "event_id_xyz",
  "sport_key": "americanfootball_nfl",
  "commence_time": "2023-09-10T00:20:00Z",
  "home_team": "Tampa Bay Buccaneers",
  "away_team": "Dallas Cowboys",
  "bookmakers": [
    {
      "key": "fanduel",
      "title": "FanDuel",
      "last_update": "2023-09-09T10:46:09Z",
      "markets": [
        {
          "key": "h2h",
          "last_update": "2023-09-09T10:46:09Z",
          "outcomes": [...]
        }
      ]
    }
  ]
}
```

### Cost Calculation

```
cost = [unique markets actually returned] × [regions specified]
```

**Example:** Requesting 5 markets but only 2 are available for an event:  
→ 2 unique markets × 1 region = **2 credits** (not 5)

---

## 6. GET /v4/sports/{sport}/events/{eventId}/markets

**Returns:** Available market keys for each bookmaker for a single event.

**Cost:** 1 credit

### Notes

- Returns only **recently seen** market keys (not comprehensive)
- As event's commence time approaches, more markets appear (bookmakers open more markets over time)

### Endpoint

```
GET /v4/sports/{sport}/events/{eventId}/markets/?apiKey={apiKey}&regions={regions}
```

### Response

```json
{
  "event_id": "event_id_abc",
  "bookmakers": [
    {
      "key": "fanduel",
      "markets": ["h2h", "spreads", "totals", "player_pass_tds"]
    },
    {
      "key": "draftkings",
      "markets": ["h2h", "spreads", "totals"]
    }
  ]
}
```

---

## 7. GET /v4/sports/{sport}/participants

**Returns:** List of teams (for team sports) or players (for individual sports).

**Cost:** 1 credit

### Notes

- For NBA: returns list of teams
- For Tennis: returns list of players
- Does **not** return players on a team (only team-level participants)
- Treat as a whitelist; may include inactive participants

### Endpoint

```
GET /v4/sports/{sport}/participants/?apiKey={apiKey}
```

### Response

```json
[
  {
    "id": "player_id_123",
    "sport_key": "tennis_atp",
    "name": "Novak Djokovic"
  }
]
```

---

## Historical Endpoints (3 endpoints)

Historical odds data is available for all sports and bookmakers. Snapshots are available at 5–10 minute intervals.

**Availability:** Paid plans only. Free tier does not include historical data.

**Cost Formula:** All historical endpoints cost **10 times** the current endpoint equivalent.

### 8. GET /v4/historical/sports/{sport}/odds

**Returns:** Historical odds snapshots for upcoming and live games at a given timestamp.

**Cost:** `[markets] × [regions] × 10`

### Endpoint

```
GET /v4/historical/sports/{sport}/odds/?apiKey={apiKey}&regions={regions}&markets={markets}&date={date}
```

### Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `date` | string | ISO 8601 timestamp (e.g., `2023-09-09T12:00:00Z`). API returns closest snapshot **equal to or earlier** than this timestamp |
| Other params | | Same as current `/odds` endpoint |

### Response

Same as current `/odds` endpoint, wrapped with snapshot metadata:

```json
{
  "timestamp": "2023-09-09T12:00:00Z",  // Actual timestamp of snapshot
  "games": [
    // ... game/odds data ...
  ]
}
```

### Historical Data Availability

- **Featured markets** (h2h, spreads, totals, outrights): Available from **June 6, 2020** onwards
  - June 2020 – Sept 2022: 10-minute intervals
  - Sept 2022 – present: 5-minute intervals
- **Additional markets** (player props, period markets, etc.): Available from **May 3, 2023** onwards (5-minute intervals)

---

### 9. GET /v4/historical/sports/{sport}/events

**Returns:** Historical event listings at a given timestamp.

**Cost:** 1 credit

### Endpoint

```
GET /v4/historical/sports/{sport}/events/?apiKey={apiKey}&date={date}
```

---

### 10. GET /v4/historical/sports/{sport}/events/{eventId}/odds

**Returns:** Historical odds for a single event.

**Cost:** `[unique markets] × [regions] × 10`

### Endpoint

```
GET /v4/historical/sports/{sport}/events/{eventId}/odds/?apiKey={apiKey}&regions={regions}&markets={markets}&date={date}
```

---

## General Notes

### Event Lifecycle

- Events appear in `/events` and `/odds` endpoints only when major bookmakers list them
- After a round completes, events may temporarily be unavailable
- For out-of-season sports, no events appear unless sport is listed in `/sports?all=true`

### Timezone

All timestamps are in **UTC (Z)** by default. Use `dateFormat=unix` for UNIX timestamps.

### Bookmaker List

A comprehensive list of bookmakers by region is available at:  
https://the-odds-api.com/sports-odds-data/bookmaker-apis.html

### Market Definitions

Detailed descriptions of all betting markets:  
https://the-odds-api.com/sports-odds-data/betting-markets.html

### Swagger Specification

Full OpenAPI/Swagger schema:  
https://app.swaggerhub.com/apis-docs/the-odds-api/odds-api/4
