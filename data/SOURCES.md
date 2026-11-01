# Data sources and checks

All market data are published statistics. No market data are simulated. The lender in the analysis is hypothetical (see README).

| File | Source | Notes |
|---|---|---|
| `rba_a02_policy_changes.xlsx/.csv` | RBA statistical table A2, monetary policy changes (historical) | Cash-rate decisions. The 30 September 2026 increase to 4.60% is taken from news coverage of the RBA decision (Forbes Advisor Australia, Commonwealth Bank mortgage-rate pages), because the downloaded file predates it. |
| `rba_e02_household_ratios.xlsx/.csv` (+ `_meta.csv`) | RBA table E2, household finances (historical) | Housing debt to household disposable income (BHFDDIH) and related ratios. Quarterly, to 2026Q2. |
| `rba_f05_lending_rates.xlsx/.csv` (+ `_meta.csv`) | RBA table F5, indicator lending rates (historical) | Discounted (FILRHLBVD) and standard variable owner-occupier rates, 3-year fixed. Monthly, to mid-2026. |
| `apra_property_exposures_jun2026.xlsx` | APRA, Quarterly authorised deposit-taking institution property exposures, June 2026 | Tabs 1 to 7: all ADIs, banks, mutuals, major banks, other domestic banks, foreign subsidiary banks, mutual ADIs. Residential arrears, LVR bands, new-lending standards. Masked cells (*) read as missing. |
| `raw_pastes/bis_house_prices_nominal_QAUN628BIS.txt` | BIS via FRED | Residential property prices, Australia. Robustness check only. |
| `raw_pastes/bis_household_credit_pct_gdp_QAUHAM770A.txt` | BIS via FRED | Household credit to GDP. Context only. |
| `oecd_au_unemployment_quarterly.csv` | OECD via FRED | Australian unemployment rate (4.4% in 2026Q2). Some news coverage of the ABS release reports a lower figure (4.1%); the OECD series is used consistently. |

Derived files (`cash_rate_monthly.csv`, `rates_monthly.csv`, `macro_quarterly.csv`, `apra_panel_quarterly.csv`) are produced by `src/01_prepare.py`.

## Definitions
- Interest burden = housing debt to income (%) x discounted variable owner-occupier rate (%) / 100, a whole-stock average that ignores fixed-rate mix and offset balances.
- Non-performing ratio = non-performing term loans (90+ days or impaired) / residential term loan credit outstanding; past-due ratio = loans 30 to 89 days past due / credit outstanding. Both from APRA, per lender group.

## Known limits
- APRA residential history in this file starts in 2019; the model sample is 2021Q4 to 2026Q2 (19 quarters).
- E2 data stop at 2026Q2. F5 monthly data run to September 2026, but the September lender rates were recorded before the 30 September hike took effect, so the burden after the hike is an estimate (measured pass-through 0.87).
- APRA lender groups overlap (Mutual ADIs are also inside the bank tabs), so group values do not sum to All ADIs.
- Hypothetical lender parameters (book size, average loan, loss given default, time in default, cases per officer) are assumptions, not data.
- RBA Financial Stability Review, October 2026, chapter 2 (cash-flow shortfall shares, buffers, adverse scenario) is quoted as an independent check; it is not used in any calculation. https://www.rba.gov.au/publications/fsr/2026/oct/resilience-of-australian-households-and-businesses.html
