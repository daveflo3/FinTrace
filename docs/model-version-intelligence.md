# Model version intelligence — Milestone 3

FinTrace compares two workbook snapshots to explain **what changed and what may be affected downstream**.

This is the first step toward "Git for financial models".

## What is compared

For the same `Sheet!Cell` reference across two workbook versions, FinTrace can detect:

- literal value changes;
- formula changes;
- added or removed cells;
- label, number-format and defined-name metadata changes.

Changed cells are classified using explicit review heuristics:

- **candidate assumption change** — a changed literal cell is an assumption candidate in at least one model version;
- **candidate reported actual change** — the cell's label or sheet contains historical/reported-actual language;
- **input data change** — a changed literal that does not meet either heuristic;
- **calculation change** — formula text changed;
- **structural change** — a cell was added or removed.

These classifications are prompts for analyst review, not claims about author intent.

## Impact tracing

For each changed cell, FinTrace walks the newer workbook's dependency graph and reports downstream cells that were identified as material output candidates.

Example:

```text
'Inputs'!B2  Revenue Growth  8.0% → 6.0%
      ↓
'Model'!B1   Forecast Revenue
      ↓
'Model'!B2   Free Cash Flow
```

The current milestone proves **lineage-aware model comparison**. It does not yet calculate the numerical contribution of each driver to a valuation change. That attribution layer comes next.

## CLI

```bash
fintrace compare-excel old_model.xlsx new_model.xlsx --json-out outputs/model_changes.json
```
