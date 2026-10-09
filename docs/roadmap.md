# Roadmap

## Phase 0 — Foundations
**Goal:** prove the reasoning model.

- [x] Define project thesis
- [x] Define node taxonomy
- [x] Build lineage graph
- [x] Add upstream/downstream tracing
- [x] Detect missing dependencies and cycles
- [x] Add JSON persistence
- [x] Add richer provenance metadata

## Phase 1 — Assumption register
**Goal:** make analyst assumptions first-class objects.

- [x] analyst rationale
- [x] evidence links
- [x] confidence level
- [x] versioned timestamps / change history
- [ ] historical range
- [ ] sensitivity metadata
- [x] stale-evidence review flag

Deliverable: an assumption register that can answer "what are we assuming, why, and what depends on it?"

## Phase 2 — Excel companion
**Goal:** assist an existing Excel model.

- read workbook with openpyxl
- inspect named ranges / selected cells
- map cells to FinTrace nodes
- capture formulas and values
- preserve workbook location
- flag broken references / obvious reconciliation issues
- export a review report

Deliverable: point FinTrace at a workbook and create a structured model map without replacing Excel.

## Phase 3 — Model version intelligence
**Goal:** "Git for financial models."

- compare model snapshots
- identify changed assumptions
- distinguish updated actuals from analyst changes
- attribute output / valuation movement to changed drivers
- generate a concise change report

Example output:

```text
Implied equity value: £38.60 → £34.20 (-11.4%)

Main contributors:
- Revenue growth 8.0% → 6.0%
- WACC 8.4% → 8.8%
- Terminal margin 19.0% → 18.0%
```

## Phase 4 — Thesis fragility
**Goal:** show where the conclusion is most vulnerable.

- local sensitivity analysis
- concentration of valuation dependence
- dependency centrality
- evidence-quality weighting
- scenario stress testing

Deliverable: "61% of upside depends on three assumptions."

## Phase 5 — Monte Carlo
**Goal:** replace false precision with outcome distributions.

- parameter distributions
- correlation support
- deterministic seed
- 10k+ simulations
- percentile outputs
- probability of exceeding a benchmark

## Phase 6 — Historical backtesting
**Goal:** test whether the reasoning worked.

- freeze information set at historical date
- rerun prior assumptions
- compare forecasts with actual results
- calculate bias / error metrics
- preserve analyst rationale from that date

Deliverable: track recurring forecasting biases.

## Phase 7 — Analyst memory
**Goal:** make judgement cumulative.

- historical assumptions
- reason for changes
- model-version timeline
- previous forecasts
- recurring bias report

## Phase 8 — Narrative vs numbers
**Goal:** surface tensions between qualitative statements and reported behaviour.

- source annual reports / transcripts
- extract claims with citations
- compare claims with financial trends
- surface questions, never accusations

## Phase 9 — Evidence graph UI
**Goal:** visually explore the chain from source to conclusion.

Click a valuation and trace:
source evidence → interpretation → assumption → calculation → output → thesis.
