<!-- Fuente: https://the-odds-api.com/manage/faqs.html | Fetched: 2026-07-06 -->

# The Odds API — Frequently Asked Questions

## Subscriptions & Billing

### Q: What happens when I subscribe?

You will receive an email containing your API key and links to help you get started.

### Q: When am I billed?

For paid plans, billing happens immediately upon subscription. After that, payment is charged automatically each month on the same calendar day your subscription started.

**Example:** If your first payment is on the 1st, you will be charged on the 1st of every subsequent month.

### Q: How can I cancel?

You can cancel your subscription at any time using the accounts portal or the cancellation form at:  
https://the-odds-api.com/manage/cancel.html

Your subscription will automatically cancel before the next billing cycle. You will not be charged again.

### Q: How can I upgrade or downgrade a subscription?

More info on upgrading or downgrading your subscription can be found at:  
https://the-odds-api.com/manage/upgrade-downgrade-cancel-a-subscription.html

### Q: How can I update my credit card details?

Billing details can be managed in your account dashboard. When creating an account for the first time, use the same email address as any existing subscriptions to merge them.

## API Usage & Quota

### Q: What is a request?

A single request returns live and upcoming games for a given sport, betting market, and bookmaker region. Each game includes a start time, participants, and bookmaker odds for the specified region.

**Example:** If you request odds for NBA basketball from US-region bookmakers in the moneyline market, the API returns live and upcoming NBA games showing moneyline odds from US bookmakers. This counts as **1 request** against your plan's usage quota.

**Cost calculation:** The actual cost depends on the endpoint and parameters:

```
cost = [number of markets specified] × [number of regions specified]
```

For details, see the API guide at:  
https://the-odds-api.com/liveapi/guides/v4/

### Q: When are usage credits reset?

Usage credits are automatically reset on the **1st of every month** (UTC). All subscription tiers reset on this schedule, regardless of when you subscribed.

### Q: How frequently are odds updated?

Odds update at intervals depending on the market type and proximity to event start time.

| Market Type | Pre-Match Interval | In-Play Interval |
|-------------|-------------------|------------------|
| Featured Markets (h2h, spreads, totals) | 60 seconds | 40 seconds |
| Additional Markets (player props, period markets) | 60 seconds | 60 seconds |
| Outrights / Futures | 5 minutes | 60 seconds |
| Betting Exchanges | 20 seconds | 10 seconds |

**Six hours before an event starts,** the update interval gradually decreases from the pre-match interval to the in-play interval.

For more details, see:  
https://the-odds-api.com/sports-odds-data/update-intervals.html

## Support & Issues

### Q: How can I get in touch?

Contact support at: **team@the-odds-api.com**

You can also reply to the email that contains your API key when you sign up.

### Q: What if I find an error?

We cover hundreds of games and thousands of odds from 50+ bookmakers, and data changes constantly. While we have systems to detect anomalies, errors can occasionally occur.

**Before reporting:**  
Compare the API response with the bookmaker's website directly. These sometimes differ due to live updates.

**When reporting:**  
Include:
- The full API URL that was called
- Screenshots of the API response and the bookmaker's website (if relevant)
- Any additional context

Email your report to: **team@the-odds-api.com**

## Non-Developers

### Q: What if I'm not a programmer?

You can access all live sports odds data with your API key in:

- **Google Sheets** — Odds in Google Sheets add-on
- **Excel** — Odds in Excel add-on

No coding required. Just click a button to pull odds into your spreadsheet.

See more at:  
https://the-odds-api.com/features/spreadsheets.html

### Q: Can I embed odds on my website?

Yes, use the **Odds Widget**. Embed a simple HTML tag on your website to display live odds, and optionally monetize with bookmaker affiliate links.

See more at:  
https://the-odds-api.com/widget/

## Additional Resources

- **Full API Documentation:** https://the-odds-api.com/liveapi/guides/v4/
- **Bookmakers by Region:** https://the-odds-api.com/sports-odds-data/bookmaker-apis.html
- **Betting Markets Explained:** https://the-odds-api.com/sports-odds-data/betting-markets.html
- **Odds Update Intervals:** https://the-odds-api.com/sports-odds-data/update-intervals.html
- **Historical Odds Data:** https://the-odds-api.com/historical-odds-data/

---

*Last updated: 2026-07-06*
