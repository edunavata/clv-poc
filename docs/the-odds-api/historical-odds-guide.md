<!-- Fuente: https://the-odds-api.com/historical-odds-data/ | Fetched: 2026-07-06 -->

# Historical Odds Data API

Historical odds data allows you to access snapshots of odds and events from past timestamps. This is essential for calculating **Closing Line Value (CLV)** and analyzing betting edge over time.

**Availability:** Historical data is **only available on paid usage plans** (not free tier).

## Data Availability

Historical snapshots are available for **all sports and bookmakers** covered by The Odds API.

### Featured Markets

Featured markets (moneyline, spreads, totals, outrights) have the longest history:

- **Available since:** June 6, 2020
- **Snapshot interval (June 2020 – Sept 2022):** 10-minute intervals
- **Snapshot interval (Sept 2022 – present):** 5-minute intervals

### Additional Markets

Additional betting markets (player props, period markets, alternates, etc.) have shorter history:

- **Available since:** May 3, 2023
- **Snapshot interval:** 5-minute intervals

## Endpoints

Three historical endpoints mirror their current equivalents:

### 1. GET /v4/historical/sports/{sport}/odds

Returns odds for all events at a snapshot timestamp.

```
GET /v4/historical/sports/{sport}/odds?
  apiKey={apiKey}&
  regions={regions}&
  markets={markets}&
  date={date}
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `sport` | string | Yes | Sport key (e.g., `americanfootball_nfl`) |
| `apiKey` | string | Yes | API key |
| `regions` | string | Conditional | Comma-separated region codes |
| `bookmakers` | string | Conditional | Comma-separated bookmaker keys (overrides regions) |
| `markets` | string | Yes | Comma-separated market keys (h2h, spreads, totals, etc.) |
| `date` | string | Yes | ISO 8601 timestamp (e.g., `2023-09-09T12:00:00Z`) |
| `oddsFormat` | string | No | `decimal` (default) or `american` |
| `dateFormat` | string | No | `iso` (default) or `unix` |
| `eventIds` | string | No | Filter by event IDs |

**Cost:** `[markets] × [regions] × 10`

**Response:**

```json
{
  "timestamp": "2023-09-09T12:00:00Z",
  "games": [
    {
      "id": "event_id_123",
      "sport_key": "americanfootball_nfl",
      "commence_time": "2023-09-10T00:20:00Z",
      "home_team": "Tampa Bay Buccaneers",
      "away_team": "Dallas Cowboys",
      "bookmakers": [
        {
          "key": "fanduel",
          "title": "FanDuel",
          "last_update": "2023-09-09T12:00:00Z",
          "markets": [
            {
              "key": "h2h",
              "outcomes": [
                { "name": "Tampa Bay Buccaneers", "price": 2.50 },
                { "name": "Dallas Cowboys", "price": 1.52 }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

- **`timestamp`**: Actual timestamp of the snapshot returned (may be earlier than requested `date` if exact match unavailable)
- **`games`**: Array of event and odds data at that point in time

**Closest Match Behavior:**  
The API returns the closest snapshot **equal to or earlier than** the provided `date` parameter. If no snapshot exists for your exact time, you get the most recent one before it.

**Example:**  
- Request: `date=2023-09-09T12:30:00Z`
- If no snapshot at exactly 12:30, API returns snapshot from 12:25 or 12:20 (whichever is closest and earlier)

### 2. GET /v4/historical/sports/{sport}/events

Returns event listings at a snapshot timestamp (without odds).

```
GET /v4/historical/sports/{sport}/events?apiKey={apiKey}&date={date}
```

**Cost:** 1 credit

**Response:**

```json
{
  "timestamp": "2023-09-09T12:00:00Z",
  "games": [
    {
      "id": "event_id_456",
      "sport_key": "americanfootball_nfl",
      "sport_title": "NFL",
      "commence_time": "2023-09-10T00:20:00Z",
      "home_team": "Tampa Bay Buccaneers",
      "away_team": "Dallas Cowboys"
    }
  ]
}
```

### 3. GET /v4/historical/sports/{sport}/events/{eventId}/odds

Returns odds for a single event at a snapshot timestamp.

```
GET /v4/historical/sports/{sport}/events/{eventId}/odds?
  apiKey={apiKey}&
  regions={regions}&
  markets={markets}&
  date={date}
```

**Cost:** `[unique markets returned] × [regions] × 10`

**Response:** Same as `/v4/historical/sports/{sport}/odds`, but for a single event.

## Usage for CLV Calculation

To calculate **Closing Line Value (CLV)**, compare your initial odds capture against the final closing odds:

1. **Capture initial odds** at event opening using `GET /v4/sports/{sport}/odds`
   - Record: `sport`, `event_id`, `bookmaker`, `market`, `initial_price`, `timestamp`
   - Cost: `[markets] × [regions]` credits

2. **Get closing odds** from Pinnacle (reference close) using:
   ```
   GET /v4/historical/sports/{sport}/odds?
     bookmakers=pinnacle&
     markets=h2h&
     date={event_commence_time}
   ```
   - Cost: `1 market × 1 bookmaker (~0.1 region) × 10` = **~1 credit per sport/date**

3. **Calculate CLV:**
   ```
   CLV = (closing_price - opening_price) / opening_price × 100
   ```
   - If opening price (your bet) was 2.00 and closing (Pinnacle ref) was 1.90: CLV = -5%
   - If opening was 1.90 and closing was 2.00: CLV = +5.26%

4. **Track over time:** Accumulate CLV across all bets to measure edge (positive CLV = edge captured)

## Cost Planning for CLV

For a POC tracking Edge A (soft books vs. Pinnacle reference):

**Per event analysis:**
- Initial capture: 3 markets × 1 region (e.g., h2h, spreads, totals on `us` bookmakers) = **3 credits**
- Closing snapshot: 1 market × 1 bookmaker × 10 (Pinnacle h2h close) = **~1 credit**
- **Total per event:** ~4 credits

**Monthly budget example (free tier: Starter):**
- If Starter tier quota is ~100–500 credits (typically low), you can track ~25–125 events/month
- Paid 20K tier: ~5,000 events/month
- Paid 100K tier: ~25,000 events/month

**Optimization tip:**  
Use the `bookmakers` parameter to fetch only Pinnacle + your target soft books, not all regions. This saves quota while still capturing the needed data.

## Important Notes

1. **Paid Plans Only:** Free tier (Starter) does not have access to historical data.

2. **Snapshot Precision:** 5–10 minute intervals means you won't get odds at the exact second an event closed. Use the closest snapshot.

3. **Data Freshness:** All historical data is fresh and updated in real-time as bookmakers update odds. The historical endpoints simply return past snapshots.

4. **Event Start Time:** For CLV, the most relevant historical snapshot is usually at or very close to the event's `commence_time` (when odds "close" for that market).

5. **Public Website Delay:** For Pinnacle specifically, the API notes state "Odds are from public website which may incur a delay." This is important for high-precision CLV calculations — there may be a 1–2 minute gap between the actual sharp close and what the API reflects.

## Example: Fetch Historical Odds for CLV

**Request:** Get odds as they were 2 hours before an NFL game start

```
GET https://api.the-odds-api.com/v4/historical/sports/americanfootball_nfl/odds?
  apiKey=YOUR_API_KEY&
  bookmakers=pinnacle,fanduel,bet365_uk&
  markets=h2h&
  date=2023-09-10T00:20:00Z  (game starts at 00:20, so this is 22:20 previous day - 2 hours before start)
  &oddsFormat=decimal
```

**Response will contain:**
- Pinnacle's h2h odds for all games ~2 hrs before start
- FanDuel's h2h odds at same time
- Bet365 (UK) h2h odds at same time

**Cost:** 1 market × 3 bookmakers (~1 region) × 10 = **~10 credits**

---

## Learn More

- **API Guide:** https://the-odds-api.com/liveapi/guides/v4/
- **Pricing:** https://the-odds-api.com/
- **Support:** team@the-odds-api.com
