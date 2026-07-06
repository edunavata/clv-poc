<!-- Fuente: https://the-odds-api.com/sports-odds-data/bookmaker-apis.html | Fetched: 2026-07-06 -->

# Bookmaker APIs — Regional Coverage

Bookmakers are segmented by region, which can be specified in an API request. The Odds API currently covers **109+ bookmakers** across 9 regions.

## How Regions Work

You can request odds from a specific region using the `regions` parameter:

```
GET /v4/sports/{sport}/odds?regions=us,uk,au&markets=h2h&...
```

Or target specific bookmakers using the `bookmakers` parameter (more granular):

```
GET /v4/sports/{sport}/odds?bookmakers=pinnacle,fanduel,bet365_uk&markets=h2h&...
```

**If both `regions` and `bookmakers` are specified, `bookmakers` takes priority.**

## US Bookmakers

Primary US sportsbooks and betting sites.

| Key | Bookmaker |
|-----|-----------|
| `betmgm` | BetMGM |
| `betonlineag` | BetOnline.ag |
| `betrivers` | BetRivers |
| `betus` | BetUS |
| `bovada` | Bovada |
| `draftkings` | DraftKings |
| `fanatics` | Fanatics Sportsbook |
| `fanduel` | FanDuel |
| `lowvig` | LowVig |
| `mybookieag` | MyBookie.ag |
| `williamhill_us` | William Hill (US) |

## US2 Bookmakers

Additional US sportsbooks (newer or secondary markets).

| Key | Bookmaker |
|-----|-----------|
| `ballybet` | Bally Bet |
| `betanysports` | BetAnySports |
| `betparx` | BetParx |
| `espnbet` | ESPNBet |
| `fliff` | Fliff |
| `hardrockbet` | Hard Rock Bet |
| `hardrockbet_az` | Hard Rock Bet (AZ) |
| `hardrockbet_fl` | Hard Rock Bet (FL) |
| `hardrockbet_oh` | Hard Rock Bet (OH) |
| `rebet` | ReBet |

## US DFS

US Daily Fantasy Sports sites.

| Key | Bookmaker |
|-----|-----------|
| `betr_us_dfs` | BetR (DFS) |
| `pick6` | Pick6 |
| `prizepicks` | PrizePicks |
| `underdog` | Underdog |

## US Exchanges

US-based betting exchanges and prediction markets.

| Key | Bookmaker |
|-----|-----------|
| `betopenly` | BetOpenly |
| `kalshi` | Kalshi |
| `novig` | NoVig |
| `polymarket` | Polymarket |
| `prophetx` | ProphetX |

## UK Bookmakers

British and UK-available sportsbooks.

| Key | Bookmaker |
|-----|-----------|
| `betfair_ex_uk` | Betfair Exchange (UK) |
| `betfair_sb_uk` | Betfair Sportsbook (UK) |
| `betfred_uk` | Betfred |
| `betvictor` | BetVictor |
| `betway` | Betway |
| `boylesports` | BoyleSports |
| `casumo` | Casumo |
| `coral` | Coral |
| `grosvenor` | Grosvenor |
| `ladbrokes_uk` | Ladbrokes (UK) |
| `leovegas` | LeoVegas |
| `livescorebet` | LiveScore Bet |
| `matchbook` | Matchbook |
| `paddypower` | Paddy Power |
| `skybet` | Sky Bet |
| `smarkets` | Smarkets |
| `sport888` | 888 Sport |
| `unibet_uk` | Unibet (UK) |
| `virginbet` | Virgin Bet |
| `williamhill` | William Hill |

## EU Bookmakers

European bookmakers and exchanges (multi-country).

| Key | Bookmaker |
|-----|-----------|
| `betanysports` | BetAnySports |
| `betclic_fr` | Betclic (FR) |
| `betfair_ex_eu` | Betfair Exchange (EU) |
| `betonlineag` | BetOnline.ag |
| `betsson` | Betsson |
| `betvictor` | BetVictor |
| `codere_it` | Codere (IT) |
| `coolbet` | CoolBet |
| `everygame` | Everygame |
| `gtbets` | GTBets |
| `leovegas_se` | LeoVegas (SE) |
| `marathonbet` | Marathonbet |
| `matchbook` | Matchbook |
| `mybookieag` | MyBookie.ag |
| `nordicbet` | NordicBet |
| `onexbet` | OneXBet |
| **`pinnacle`** | **Pinnacle** ⭐ |
| `pmu_fr` | PMU (FR) |
| `sport888` | 888 Sport |
| `suprabets` | Suprabets |
| `tipico_de` | Tipico (DE) |
| `unibet_fr` | Unibet (FR) |
| `unibet_it` | Unibet (IT) |
| `unibet_nl` | Unibet (NL) |
| `unibet_se` | Unibet (SE) |
| `williamhill` | William Hill |
| `winamax_de` | Winamax (DE) |
| `winamax_fr` | Winamax (FR) |

**Note:** Pinnacle is listed under `eu` region. Odds from Pinnacle may incur a delay as they are sourced from the public website.

## FR Bookmakers

French-specific bookmakers.

| Key | Bookmaker |
|-----|-----------|
| `betclic_fr` | Betclic |
| `netbet_fr` | Netbet |
| `pmu_fr` | PMU |
| `unibet_fr` | Unibet |
| `winamax_fr` | Winamax |

## SE Bookmakers

Swedish-specific bookmakers.

| Key | Bookmaker |
|-----|-----------|
| `atg_se` | ATG |
| `betinia_se` | Betinia |
| `betmgm_se` | BetMGM (SE) |
| `betsson` | Betsson |
| `campobet_se` | CampoBet |
| `expekt_se` | Expekt |
| `hajper_se` | Hajper |
| `leovegas_se` | LeoVegas |
| `mrgreen_se` | MrGreen |
| `nordicbet` | NordicBet |
| `sport888_se` | 888 Sport |
| `svenskaspel_se` | Svenskaspel |
| `unibet_se` | Unibet |

## AU Bookmakers

Australian sportsbooks and betting sites.

| Key | Bookmaker |
|-----|-----------|
| `bet365_au` | Bet365 (AU) |
| `betfair_ex_au` | Betfair Exchange (AU) |
| `betr_au` | BetR |
| `betright` | BetRight |
| `dabble_au` | Dabble |
| `ladbrokes_au` | Ladbrokes (AU) |
| `neds` | NEDS |
| `playup` | PlayUp |
| `pointsbetau` | PointsBet (AU) |
| `sportsbet` | Sportsbet |
| `tab` | TAB |
| `tabtouch` | TABtouch |
| `unibet` | Unibet |

## Notes

- **New bookmakers are added periodically.** Check back regularly for updates.
- **Suggest new bookmakers** if you'd like to see a particular sportsbook covered.
- **Moneyline odds:** All listed bookmakers are covered for moneyline/h2h (head-to-head) betting markets.
- **Regional overlap:** Some bookmakers appear in multiple regions (e.g., Betfair has UK, EU, and AU exchanges).
- **Accuracy:** Regional classifications may not always be precise; always reference the `regions` parameter in API responses.

## Quota Cost Reminder

Using the `bookmakers` parameter is more efficient than regions if you only need specific bookmakers:

- `regions=eu` → Costs 1 region (or more depending on markets)
- `bookmakers=pinnacle,bet365_au,fanduel` → Costs ~1 region (up to 10 bookmakers = 1 region cost)

## Get Started

To access the full API and start requesting odds, sign up for a free account at:  
https://the-odds-api.com

---

**Total Coverage:** 109+ bookmakers across 9 regions as of 2026-07-06.
