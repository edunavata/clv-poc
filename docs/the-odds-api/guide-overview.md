<!-- Fuente: https://the-odds-api.com/liveapi/guides/v4/ | Fetched: 2026-07-06 -->

# The Odds API V4 Guide — Overview

## Getting Started (3 Steps)

1. **Get an API key** from https://the-odds-api.com  
2. **Call an endpoint** such as `/v4/sports?apiKey={apiKey}`  
3. **Use the response** to access event IDs, odds, markets, and more

## Host / Base URL

All requests use the host: `https://api.the-odds-api.com`

For IPv6-compatible clients, use: `https://ipv6-api.the-odds-api.com`

## Authentication

Include your API key with every request using the `apiKey` query parameter:

```
GET https://api.the-odds-api.com/v4/sports/?apiKey={apiKey}
```

## Usage Quota & Cost Model

### Cost Formula

The usage quota cost depends on the number of **markets** and **regions** (or **bookmakers**) specified:

```
cost = [number of markets specified] × [number of regions specified]
```

**Example:**  
Requesting `/v4/sports/basketball_nba/odds?markets=h2h,spreads,totals&regions=us,uk,au`  
→ 3 markets × 3 regions = **9 credits**

### Regions vs. Bookmakers

- **`regions` parameter**: Each region counts as 1 unit (e.g., `us`, `uk`, `au`, `eu`)
- **`bookmakers` parameter**: More granular selection. Every 10 bookmakers count as 1 region unit.
  - Up to 10 bookmakers = 1 region cost
  - 11–20 bookmakers = 2 region cost
  - etc.
  
**If both `regions` and `bookmakers` are specified, `bookmakers` takes priority.**

This allows efficient queries: instead of requesting a whole region, you can request exactly the bookmakers you need (e.g., just Pinnacle + 5 soft books = ~1 region cost).

### Response Headers (Quota Tracking)

Every API response includes:

- **`x-requests-remaining`**: Credits left until monthly reset  
- **`x-requests-used`**: Credits consumed this month  
- **`x-requests-last`**: Cost of the last API call

### Monthly Reset

Usage credits reset automatically on the **1st of every month** (UTC).

## Rate Limiting (HTTP 429)

If you exceed your quota or rate limits, the API returns HTTP **429 Too Many Requests**.

**Response headers on 429:**
- `x-requests-remaining`: Will be 0 or negative
- `x-requests-used`: Total used
- Retry after the monthly reset or upgrade your plan

## Free Tier Limitations

The free tier (`Starter`) includes a basic allowance of requests. The exact quota is shown in your account dashboard. Paid tiers (20K, 100K, 5M, 15M credits/month) are available.

## Endpoints at a Glance

| Endpoint | Cost | Purpose |
|----------|------|---------|
| `/v4/sports` | 0 | List all sports in season (or `all=true` for out-of-season) |
| `/v4/sports/{sport}/odds` | [markets] × [regions] | Current odds for upcoming/live games |
| `/v4/sports/{sport}/scores` | 1 (no `daysFrom`) or 2 (with `daysFrom`) | Live/recent game scores |
| `/v4/sports/{sport}/events` | 0 | Event listings without odds |
| `/v4/sports/{sport}/events/{eventId}/odds` | [unique markets returned] × [regions] | Odds for a single event |
| `/v4/sports/{sport}/events/{eventId}/markets` | 1 | Available markets for a single event |
| `/v4/sports/{sport}/participants` | 1 | List of teams/players for a sport |
| `/v4/historical/sports/{sport}/odds` | [markets] × [regions] × 10 | Historical odds snapshots |
| `/v4/historical/sports/{sport}/events` | 1 | Historical event listings |
| `/v4/historical/sports/{sport}/events/{eventId}/odds` | [unique markets returned] × [regions] × 10 | Historical odds for a single event |

### Zero-Cost Endpoints

These do **not** consume quota:

- `GET /v4/sports` — list all sports
- `GET /v4/sports/{sport}/events` — list events without odds

### Historical Odds Cost

Historical endpoints cost **10 times** more than their "current" equivalents because they return snapshot data:

```
cost = [number of markets] × [number of regions] × 10
```

## Pagination

The API does not return paginated results. Each endpoint returns all matching records in a single response.

## Response Timestamps

By default, timestamps are returned in **ISO 8601 format** (e.g., `2023-09-10T15:30:00Z`).

Use `dateFormat=unix` to get UNIX timestamps (seconds since epoch).

## Odds Format

By default, odds are returned in **decimal format** (e.g., 2.50).

Use `oddsFormat=american` to get American/moneyline format (e.g., -110, +150).

Note: Small rounding errors may occur for some bookmakers when converting to American odds.

## Error Responses

Common HTTP status codes:

- **200 OK**: Request succeeded
- **400 Bad Request**: Invalid parameters
- **401 Unauthorized**: Missing or invalid API key
- **404 Not Found**: Sport/event not found
- **429 Too Many Requests**: Quota exceeded or rate limited
- **500 Internal Server Error**: API server error

## Swagger Documentation

For detailed request/response schemas, see the full Swagger API docs:  
https://app.swaggerhub.com/apis-docs/the-odds-api/odds-api/4

---

**Next:** See `guide-endpoints.md` for detailed parameters and examples for each endpoint.
