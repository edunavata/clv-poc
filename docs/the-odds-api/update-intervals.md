<!-- Fuente: https://the-odds-api.com/sports-odds-data/update-intervals.html | Fetched: 2026-07-06 -->

# Odds API — Update Intervals

Odds update at intervals which depend on the market type and the proximity to an event's start time.

## Update Interval Table

| Market Type | Pre-Match Interval | In-Play Interval |
|---|---|---|
| **Featured Markets** (h2h/moneyline, spreads/handicaps, totals/over-under) | 60 seconds | 40 seconds |
| **Additional Markets** (player props, alternates, period markets) | 60 seconds | 60 seconds |
| **Outrights / Futures** | 5 minutes | 60 seconds |
| **Betting Exchanges** (all markets) | 20 seconds | 10 seconds |

## Schedule Details

**Six hours before an event's start time,** the update interval begins decreasing gradually from the pre-match interval, eventually reaching the in-play interval once the event goes live.

### Examples

- **NFL Game (60-second pre-match interval):**  
  6 hours before kick-off → update every ~60 seconds  
  → Gradually decrease to →  
  Live event → update every ~40 seconds

- **Betting Exchange (20-second pre-match):**  
  6 hours before → update every ~20 seconds  
  → Gradually decrease →  
  Live → update every ~10 seconds

- **Golf Outright Market (5-minute pre-match):**  
  Tournament week → update every ~5 minutes  
  → Tournament starts → update every ~60 seconds

## Implications for Your Application

- **Live Odds Fetching:** If you're polling for live odds, use at least the in-play interval as your request cadence (don't poll faster than 40 seconds for featured markets, 10 seconds for exchanges).
- **Cost Planning:** More frequent pre-match updates for exchanges means more API calls and higher quota consumption if you're tracking those bookmakers closely.
- **Event Detection:** The 6-hour transition period means odds updates accelerate as an event approaches, so prices move more frequently near game time.

## Scheduler Recommendations

For the CLV-POC project:

- **For featured markets (h2h, spreads, totals):**  
  Start polling at 60-second intervals pre-match. Don't need to adjust dynamically; 60 seconds is sufficient and matches the natural update frequency.

- **For betting exchanges:**  
  If tracking exchanges for sharp price signals, consider polling at 30–40 second intervals to capture changes between their natural 20-second updates (some buffering for network latency).

- **After event start:**  
  Update interval tightens (40 sec for featured, 10 sec for exchanges), but polling at the pre-match interval (60/20 sec) is still reasonable to keep quota consumption manageable.

---

**Learn more:** https://the-odds-api.com/sports-odds-data/update-intervals.html
