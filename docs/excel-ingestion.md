# Excel ingestion — Milestone 2

FinTrace treats Excel as an **analyst-owned model**, not something to replace.

## What the first ingestion layer records

For each non-empty workbook cell, FinTrace can preserve:

- workbook sheet and exact coordinate;
- literal value or formula;
- cached value when Excel has stored one;
- number format;
- nearby row label;
- workbook-defined names.

Formula references become directed dependencies. For example:

```text
'Inputs'!B2 (RevenueGrowth)
          ↓
'Model'!B1 (= historical revenue × (1 + growth))
          ↓
'Model'!B2 (EBIT)
          ↓
'Model'!B3 (FCF)
```

## Candidate roles are deliberately heuristic

The ingestion layer can surface **candidate assumptions** and **candidate outputs**, but it does not silently classify them as financial truth.

Examples of signals used for an assumption candidate:

- a literal numeric cell is referenced by formulas;
- it is percentage formatted;
- it has a defined name;
- its label contains modelling language such as growth, WACC, margin or tax;
- it influences more than one downstream formula.

Examples of signals used for an output candidate:

- the formula is not consumed by another mapped formula;
- the row label resembles a material output such as FCF or equity value;
- it combines several inputs;
- it has a defined name.

The analyst must review these hints before promoting them into the FinTrace assumption/evidence register.

## Limits of the first parser

The first version intentionally does not guess at:

- dynamic references such as `OFFSET` or `INDIRECT`;
- external workbook links;
- structured table references;
- very large ranges beyond the configured expansion limit;
- semantic meaning of arbitrary formulas.

Those cases are reported as warnings rather than being silently misread.

## CLI target

```bash
fintrace inspect-excel model.xlsx --json-out outputs/model_map.json
```

The output JSON is designed to become the input to future model comparison, attribution and thesis-fragility features.
