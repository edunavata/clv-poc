<!-- Fuente: https://the-odds-api.com/ | Fetched: 2026-07-06 -->

# The Odds API — Pricing Tiers

## Subscription Plans

The Odds API offers several subscription tiers, each with different monthly usage quotas.

| Plan | Monthly Credits | Price | Use Case |
|------|-----------------|-------|----------|
| **Starter** | Starter tier | FREE | Personal projects, testing |
| **20K** | 20,000 | $30/month | Small-scale applications |
| **100K** | 100,000 | $59/month | Medium-scale applications |
| **5M** | 5,000,000 | $119/month | Production applications |
| **15M** | 15,000,000 | $249/month | Large-scale production |

## Key Details

- **Billing:** Paid plans charge immediately upon subscription, then automatically each month on the same day.
- **Cancellation:** Can be cancelled at any time. Subscription cancels before the next billing cycle.
- **Monthly Reset:** Usage credits reset automatically on the **1st of every month** (UTC).
- **No Overage Charges:** Once you hit your monthly quota, further API calls return HTTP 429 until the next month.

## Free Tier Features

The Starter (free) tier includes:

- Access to all 10 endpoints
- Full sport and market coverage
- **No** historical odds data (paid plans only)
- Community support

## Paid Tier Features

All paid tiers include:

- All free tier features
- Historical odds data (snapshots from June 2020 onwards, 5–10 minute intervals)
- Priority support
- Higher usage quotas

## Quota Cost Examples

For reference, here are typical API call costs to plan your usage:

- Single `GET /v4/sports/americanfootball_nfl/odds?regions=us&markets=h2h` → **1 credit** (1 market × 1 region)
- Same but `markets=h2h,spreads,totals&regions=us,uk,au` → **9 credits** (3 markets × 3 regions)
- Historical equivalent `GET /v4/historical/sports/...?date=...` → **90 credits** (same as above × 10)

## Upgrade / Downgrade

You can upgrade or downgrade your plan at any time in your account dashboard.

For more info on managing your subscription, see:  
https://the-odds-api.com/manage/upgrade-downgrade-cancel-a-subscription.html

## Bookmaker Coverage

The API covers **50+ bookmakers** across multiple regions (US, UK, Europe, Australia, etc.).

See the full list at:  
https://the-odds-api.com/sports-odds-data/bookmaker-apis.html

## Contact

For billing questions or support: **team@the-odds-api.com**
