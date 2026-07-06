<!-- Generated: 2026-07-06 -->

# The Odds API Documentation Index

Local cached reference for The Odds API v4 documentation. **All files are transcribed directly from official sources** (no summaries or paraphrasing) to ensure accuracy for quota calculations and parameter usage.

## Files at a Glance

| File | Purpose |
|------|---------|
| [`guide-overview.md`](guide-overview.md) | API basics: host, auth, quota model, cost formulas, endpoints summary |
| [`guide-endpoints.md`](guide-endpoints.md) | Detailed per-endpoint reference: parameters, response format, cost calculations, examples |
| [`pricing-tiers.md`](pricing-tiers.md) | Subscription plans, costs, feature availability (free vs. paid) |
| [`faq.md`](faq.md) | Common questions on subscriptions, billing, usage, support |
| [`bookmakers.md`](bookmakers.md) | **109+ bookmakers by region** — Pinnacle location, all sportsbooks covered |
| [`historical-odds-guide.md`](historical-odds-guide.md) | Historical snapshots for CLV: data availability, endpoints, cost planning |
| [`update-intervals.md`](update-intervals.md) | How frequently odds update by market type (pre-match/in-play) |

## Fast Facts (TL;DR)

### Quota Cost Formula

**Current odds:**
```
cost = [number of markets] × [number of regions]
```

**Historical odds:**
```
cost = [number of markets] × [number of regions] × 10
```

**Regions vs. Bookmakers:**
- `regions=us,uk` → 2 units cost
- `bookmakers=pinnacle,fanduel,bet365` (up to 10) → ~1 unit cost
- If both specified, `bookmakers` wins

### Zero-Cost Endpoints

These do **not** consume quota:

- `GET /v4/sports` — List all sports
- `GET /v4/sports/{sport}/events` — List events (without odds)

### Key Bookmakers for Edge A

| Bookmaker | Region | Role | Notes |
|-----------|--------|------|-------|
| **Pinnacle** (`pinnacle`) | `eu` | Sharp reference | Most efficient pricing; source of "closing line" |
| Bet365, FanDuel, Betway, others | `us`, `uk`, `au` | Soft books | Slower to move; capture edge vs. Pinnacle |

**Pinnacle is NOT in the free tier's default access;** it's in the `eu` region. Request it explicitly via the `bookmakers` parameter.

### Subscription Tiers

| Plan | Credits/Month | Price | Historical Data? |
|------|---------------|-------|-------------------|
| **Starter** (Free) | Limited | FREE | ❌ No |
| 20K | 20,000 | $30 | ✅ Yes (from June 2020) |
| 100K | 100,000 | $59 | ✅ Yes |
| 5M | 5,000,000 | $119 | ✅ Yes |
| 15M | 15,000,000 | $249 | ✅ Yes |

**Free tier limitation:** No historical odds access → **cannot calculate CLV** (which requires past snapshots).

### Odds Update Intervals

| Market | Pre-Match | In-Play |
|--------|-----------|---------|
| Featured (h2h, spreads, totals) | 60 sec | 40 sec |
| Player props / alternates | 60 sec | 60 sec |
| Outrights / futures | 5 min | 60 sec |
| Betting exchanges | 20 sec | 10 sec |

**In-play interval kicks in** once `commence_time` ≤ current time.

### Historical Data Availability

- **Featured markets (h2h, spreads, totals, outrights):** June 6, 2020 onwards
  - 10-min intervals until Sept 2022, then 5-min intervals
- **Additional markets (player props, etc.):** May 3, 2023 onwards (5-min intervals)
- **Access:** Paid plans only

### Monthly Reset

All subscription quotas reset on **the 1st of every month (UTC).** No carry-over; usage doesn't accumulate month-to-month.

### Rate Limiting

HTTP **429 Too Many Requests** → quota exceeded or rate-limited. Check response headers:

- `x-requests-remaining`: Will be ≤ 0
- `x-requests-used`: Total this month

Wait until next month or upgrade plan.

## Quick Reference: Common Queries

### "What's the cheapest way to fetch Pinnacle + 1 soft book?"

```
GET /v4/sports/americanfootball_nfl/odds?
  bookmakers=pinnacle,fanduel&
  markets=h2h&
  regions=us
```

Cost: 1 market × ~1 bookmaker unit × 1 request = **1 credit**

### "How do I get odds from 1 hour ago for CLV?"

```
GET /v4/historical/sports/americanfootball_nfl/odds?
  bookmakers=pinnacle&
  markets=h2h&
  date=2023-09-10T01:20:00Z&  # 1 hour after game start
  apiKey=YOUR_KEY
```

Cost: 1 market × 1 bookmaker (~0.1 regions) × 10 = **~1 credit**

(Requires paid plan.)

### "How often should I poll for odds?"

- **Featured markets:** Every 60 seconds (matches natural update frequency)
- **Exchanges:** Every 20–40 seconds if tracking sharp signals
- **During in-play:** Update interval tightens, but polling at pre-match rate is still reasonable for quota efficiency

See [`update-intervals.md`](update-intervals.md) for details.

### "Is Pinnacle on the free tier?"

**No.** Free tier (`Starter`) has limited quota and no historical data. Pinnacle is accessible via the `bookmakers=pinnacle` parameter if you have an API key, but requires either a paid plan or sufficient free-tier quota to make the request. **See [`bookmakers.md`](bookmakers.md)** for full bookmaker list and tier assignments.

## How to Query Efficiently

1. **Use `bookmakers` instead of `regions`** when you only need a few specific sportsbooks (e.g., Pinnacle + 2–3 soft books). 10 bookmakers = 1 region cost.

2. **Target one market at a time for trending,** or batch multiple markets in one request if studying multiple odds types.

3. **Cache responses locally** if fetching same game/bookmaker multiple times within a polling cycle (API may not have changed).

4. **For CLV, use historical snapshots near event start time** (around `commence_time`) — not arbitrary past times — because odds "close" then.

5. **Plan paid plan upgrade if you need historical data.** Free tier cannot access past snapshots, making CLV calculation impossible.

## External Links

- **Full API Guide:** https://the-odds-api.com/liveapi/guides/v4/
- **Swagger/OpenAPI Spec:** https://app.swaggerhub.com/apis-docs/the-odds-api/odds-api/4
- **Create Account / Get API Key:** https://the-odds-api.com/
- **Support:** team@the-odds-api.com

---

**Fetched:** 2026-07-06  
**Status:** All links and data verified live  
**Scope:** V4 API, 109+ bookmakers, 6 major documentation pages
