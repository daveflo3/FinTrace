# FinTrace

**FinTrace is a financial decision-intelligence layer that assists analysts rather than replacing them.**

The core idea is simple: a financial model should not just produce an answer. It should make the chain from **evidence → assumptions → calculations → outputs → judgement** inspectable.

FinTrace is being built to sit beside an analyst's existing workflow (especially Excel), not to automate away the analyst.

## What FinTrace is trying to solve

Traditional models are good at calculations but weak at preserving reasoning:

- Where did an assumption come from?
- Which source supported it?
- What changed between model versions?
- Why did valuation move?
- Which assumptions make the thesis fragile?
- Did the analyst's previous forecasts actually prove accurate?
- Does management's narrative match the numbers?

FinTrace aims to make those questions answerable.

## Design principles

1. **Assist, don't replace.** FinTrace should surface evidence, contradictions, sensitivities and questions. The human owns the judgement.
2. **Traceability first.** Important outputs should be traceable back to assumptions and evidence.
3. **Deterministic finance.** Financial calculations should remain explicit, testable and auditable.
4. **Language models are optional helpers.** They may assist with text-heavy extraction or questioning later, but never become the source of truth for the model.
5. **No black-box recommendations.** FinTrace should not output "buy", "sell" or an unexplained forecast.
6. **Version everything that matters.** Assumptions, evidence, model versions and analyst rationale should have history.

## Planned capabilities

- Assumption lineage
- Evidence graph
- Excel model ingestion
- Model-version comparison
- Valuation-change attribution
- Fact / assumption / calculation / judgement classification
- Thesis fragility analysis
- Monte Carlo scenario analysis
- Historical forecast backtesting
- Analyst bias tracking
- Analyst memory
- Narrative-vs-numbers review

## Current milestone — Excel model ingestion (working)

The current build can:

- create dated, attributed evidence records;
- register and revise assumptions without deleting earlier reasoning;
- inspect `.xlsx`/`.xlsm` models while leaving Excel as the analyst-owned model;
- preserve exact sheet/cell references, formulas, formats, labels and named ranges;
- map formula dependencies across sheets and workbook-defined names;
- surface **review candidates** for assumptions and material outputs using transparent heuristics;
- export a deterministic workbook snapshot to JSON;
- warn rather than guess when a formula reference cannot be safely resolved.

### Quickstart

Python 3.11+ required. From the repository root:

```bash
python -m pip install -e ".[dev,excel]"
fintrace demo
fintrace inspect-excel path/to/model.xlsx --json-out outputs/model_map.json
python examples/register_demo.py
python -m pytest -q
```

The example creates `outputs/assumption_register_demo.json` (ignored by Git). Its numbers are illustrative, not real financial data.

### Example of the central idea

```text
Source: management's published guidance (evidence)
   | supports
   v
FY27 revenue growth = 6.5% (analyst assumption)
   | influences
   v
Revenue / FCF / DCF valuation (future workbook integration)
```

The code currently supports the first link and the core lineage primitives. It **does not yet** analyse real Excel models or calculate valuations.

## Milestone 0 — Lineage engine

The first milestone is intentionally small but foundational:

- represent evidence, assumptions, calculations, outputs and judgements as typed nodes;
- connect them in a directed graph;
- trace any output back to its source evidence;
- validate broken or circular reasoning chains;
- expose the result through a simple CLI/demo.

Once this works, Excel ingestion and model versioning can be layered on top without corrupting the core data model.

## Repository structure

```text
src/fintrace/
├── domain.py          # Core financial reasoning entities
├── graph.py           # Evidence / assumption lineage graph
├── register.py        # Provenance, revisions and JSON storage
├── excel.py           # Workbook structure + formula lineage ingestion
└── cli.py             # Small CLI for exercising the core

tests/
├── test_graph.py
├── test_register.py
└── test_excel.py

docs/
├── architecture.md
└── roadmap.md

examples/
└── lineage_demo.py
```

## Status

Early build. Core lineage, an auditable assumption register and the first Excel-ingestion layer are implemented. Model attribution, backtesting and the UI remain planned.

## Why this project exists

Most finance automation projects try to automate the analyst. FinTrace takes the opposite view: the more consequential the judgement, the more important it is to make the reasoning visible, challengeable and testable.
