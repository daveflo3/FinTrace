# Analysis Lab — v0.5.0 preview

FinTrace is an **analyst companion**, not a substitute for financial analysis.
This release brings six controlled prototypes together in a local interactive Streamlit dashboard.
All bundled companies, claims and forecasts are fictional.

## Launch on Windows (PowerShell)

From the repo folder (`C:\Users\19\Documents\FinTrace` on the original developer PC):

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,excel,dashboard]"
.\.venv\Scripts\python.exe -m streamlit run src/fintrace/dashboard.py
```

The dashboard will print a local link, commonly `http://localhost:8501`. Use Ctrl+C to stop it.

## UI quality improvements in the v0.5 preview

- Overview: a readable evidence-to-judgement chain rather than a truncated KPI value.
- DCF attribution and one-at-a-time stress charts: horizontal driver labels and two-decimal financial tables.
- Monte Carlo: a continuous **£m** axis with 32 aggregated bins and P5 / median / P95 reference markers. These represent results **conditional on your inputs**, not calibrated market probabilities.
- Backtesting: formatted signed errors plus an explanation of MAE, RMSE and WAPE.
- Analyst memory: the form warns instead of appending an immediate exact duplicate; historical records remain immutable.
- Narrative review: margins entered as **20** for 20%, not 0.20; T-2 appears only for revenue-acceleration claims.

### Manual browser smoke test

After launching the dashboard, check the Overview chain, run Excel comparison using the bundled workbooks,
change a DCF driver, run Monte Carlo and verify the value axis/markers, and switch Narrative review between
margin expansion and revenue acceleration. The Python tests do **not** replace real-browser testing.

## What works now

| Feature | Real implementation | Major limit |
| --- | --- | --- |
| Excel comparison | Diff saved values, formulas and workbook structure, trace formula references and candidate outputs | Excel formulas are **not recalculated**; named/dynamic/external formulas can be unresolved |
| Numerical valuation-change attribution | Built-in transparent five-year DCF, exact four-input Shapley allocation across growth, EBIT margin, WACC and terminal growth | **Not** arbitrary-workbook attribution; fixed underlying DCF parameters must match |
| Thesis fragility | One-at-a-time adverse-input stress testing and top-two downside concentration | Not calibrated risk or joint-downside probability; isolated losses interact |
| Monte Carlo | Independent triangular distributions, reproducible seed and 5th/50th/95th percentiles | User-imposed assumptions are not empirical forecast probabilities; no correlations |
| Backtesting and bias | Input forecast issue dates and actual publication dates, compute MAE, RMSE, mean signed error, WAPE and groups | Cannot verify underlying historical source truth; inputs are analyst supplied |
| Analyst memory | Append-only local JSON Lines notes with changes, rationale and evidence reference | No multi-user database, user authentication or file locking |
| Narrative vs numbers | Manually entered citations and claims checked against comparable metrics | No automatic text extraction; 'tension' is a question, **not** an accusation |

## How the DCF works

With a user-selected unit (sample: **£m**), FinTrace forecasts annual revenue and FCF for five years:

- `Revenue(t) = Revenue(t-1) × (1 + g)`
- `EBIT(t) = Revenue(t) × EBIT margin`
- `FCF(t) = EBIT(t) × (1 − tax) + revenue × D&A ratio − revenue × capex ratio − Δrevenue × NWC ratio`
- `Terminal Value = FCF(year 5) × (1 + terminal growth) / (WACC − terminal growth)`
- `Enterprise Value = present value of forecast FCF + present value of terminal value`
- `Equity Value = Enterprise Value − net debt`

For two scenarios that **differ only in** growth, margin, WACC or terminal growth,
FinTrace recomputes valuation along all `4! = 24` driver orderings, averaging each
marginal contribution. The result **exactly reconciles** to the difference between
the two DCF equity values (floating-point precision aside).

These formula choices are deliberately simplified and are not a production-grade DCF.
In particular, all forecast-year growth/margins remain constant and terminal cash flow
is grown from year five by a single perpetuity rate.

## Example scenario — not Excel attribution

- Previous DCF equity value: ~£1,688.8m
- Revised DCF equity value: ~£1,113.2m
- Difference: ~−£575.5m
- Inputs revised: revenue growth 8% → 6%, EBIT margin 20% → 19%, WACC 10% → 11.5%, terminal growth 2.5% → 2.0%
- Shapley contributions reconcile exactly to ~−£575.5m

This is an **illustrative DCF calculation**, *not* a claim that FinTrace numerically attributed the workbook demo's enterprise-value movement.

## Dated historical data and integrity

Try the bundled `examples/sample_forecasts.csv`, or upload your own CSV with these columns:

```text
analyst,metric,as_of,target_date,actual_released_on,forecast,actual
```

FinTrace rejects forecasts issued after their target date and excludes actual observations
not yet released by the selected evaluation date. **It does not download historical data**.
Combining unrelated metrics or units in one bias statistic is avoided by grouping.

Analyst notes are written to `outputs/analyst_journal.jsonl` (excluded by `.gitignore`).
Do not upload confidential documents or personally identifiable customer data to GitHub.

## Remaining work before claiming production readiness

- User-driven mapping from workbook cells into DCF drivers and formula-aware numerical attribution
- Source/filing ingestion with citations and evidence freshness controls
- Calibrated forecast distributions, correlations and rigorous backtest cohort construction
- Model/scenario persistence in a proper transactional store, concurrency and access control
- Error boundaries, accessibility checks, packaging and deployment tests for the UI
- Ongoing UX and visual design polish

**Project stance:** FinTrace surfaces relationships and review questions; the analyst owns the economic interpretation and decision.
