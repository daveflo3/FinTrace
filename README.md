# FinTrace

[![tests](https://github.com/daveflo3/FinTrace/actions/workflows/tests.yml/badge.svg)](https://github.com/daveflo3/FinTrace/actions/workflows/tests.yml)

**FinTrace is a financial decision-intelligence layer that assists analysts rather than replacing them.**

### Launch the interactive Analysis Lab (preview)

```powershell
py -m pip install -e ".[dev,excel,dashboard]"
py -m streamlit run src/fintrace/dashboard.py
```

The browser dashboard brings workbook comparisons, transparent DCF change attribution, stress tests, Monte Carlo scenario distributions, dated forecast backtesting, an append-only analyst journal and source-attributed narrative review into one local workspace. The UI preview includes readable financial charts, consistent narrative-input units and duplicate-entry protection for analyst notes.

**[See the dashboard walkthrough and limitations](docs/analysis-lab.md).** Demo data is entirely fictional. This is a research prototype, not investment advice.

The core idea is simple: a financial model should not just produce an answer. It should make the chain from **evidence → assumptions → calculations → outputs → judgement** inspectable.

FinTrace is being built to sit beside an analyst's existing workflow (especially Excel), not to automate away the analyst.


## See FinTrace in action (2-minute demo)

A fictional company's historical revenue is updated from **£850m to £865m**, while an analyst reduces forecast growth **8% → 6%** and EBITDA margin **20% → 19%**. FinTrace identifies the three changed inputs, distinguishes the *reported actual* from *assumption candidates*, and traces each through the workbook's formula dependencies.

![Portfolio demo showing classified model changes](docs/assets/portfolio-demo.png)

```bash
python -m pip install -e ".[dev,excel]"
python examples/portfolio_demo.py
```

**[Open the walkthrough and both real Excel examples](docs/portfolio-demo.md).** The numbers are synthetic. Workbook lineage identifies possible downstream effects; it does not calculate an Excel valuation change or recommend trades. The separate DCF scenario lab provides numerical attribution for its own transparent model.

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

## Capability map

- [x] Assumption lineage
- [x] Evidence graph primitives
- [x] Excel model ingestion
- [x] Model-version comparison
- [x] Changed-cell → downstream-output impact tracing
- [x] Numerical attribution across four specified parameters of the built-in DCF (not arbitrary Excel models)
- [x] Scenario-based thesis fragility / stress concentration (not a probability score)
- [x] Independent triangular Monte Carlo simulation (user-defined distributions)
- [x] Historical forecast backtesting with explicit release dates (CSV input)
- [x] Descriptive forecast-bias grouping + append-only local analyst journal
- [x] Rule-based, source-attributed narrative-vs-numbers review (manual claims)
- [ ] General-purpose numerical attribution for arbitrary Excel models
- [ ] Calibrated probability models, automated source extraction, and multi-user deployment

## Milestones

| Version | Milestone | Status |
| --- | --- | --- |
| `v0.2.0` | Evidence + assumption lineage | ✅ Complete |
| `v0.3.0` | Excel model ingestion | ✅ Complete |
| `v0.4.0` | Model version intelligence MVP | ✅ Complete |
| `v0.5.0` | Analysis Lab + interactive dashboard preview | Preview implementation |

## Earlier milestone — Model version intelligence

The current build can:

- create dated, attributed evidence records;
- register and revise assumptions without deleting earlier reasoning;
- inspect `.xlsx`/`.xlsm` models while leaving Excel as the analyst-owned model;
- preserve exact sheet/cell references, formulas, formats, labels and named ranges;
- map formula dependencies across sheets and workbook-defined names;
- surface **review candidates** for assumptions and material outputs using transparent heuristics;
- export a deterministic workbook snapshot to JSON;
- warn rather than guess when a formula reference cannot be safely resolved;
- compare two workbook versions and classify value, formula and structural changes;
- trace changed cells to downstream material-output candidates.

### Quickstart

Python 3.11+ required. From the repository root:

```bash
python -m pip install -e ".[dev,excel]"
fintrace demo
fintrace inspect-excel path/to/model.xlsx --json-out outputs/model_map.json
fintrace compare-excel old_model.xlsx new_model.xlsx --json-out outputs/model_changes.json
python examples/register_demo.py
python -m pytest -q
```

The example creates `outputs/assumption_register_demo.json` (ignored by Git). Its numbers are illustrative, not real financial data.

### Version-comparison demo

```bash
python examples/model_version_demo.py
```

Example output:

```text
'Inputs'!B2: 0.08 -> 0.06 [candidate_assumption_change]
  impacts: 'Model'!B1, 'Model'!B2
```

This is deliberately not an investment recommendation. It shows that a changed analyst-input candidate can be traced through the model to downstream outputs.

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

The code supports evidence/assumption lineage, Excel inspection, and lineage-aware workbook comparison. The **separate built-in DCF** calculates illustrative valuations and exactly allocates changes across four explicitly modelled drivers; it still **does not** numerically re-evaluate arbitrary Excel formulas or allocate their valuation changes.

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
├── compare.py         # Workbook-version comparison + impact tracing
├── valuation.py       # Parametric 5-year DCF and exact Shapley attribution
├── risk.py            # One-at-a-time stress concentration and Monte Carlo
├── backtest.py        # Dated historical forecast scoring and bias
├── memory.py          # Append-only reasoning journal
├── narrative.py       # Manual narrative/numeric consistency review
├── dashboard.py       # Streamlit user interface
└── cli.py             # Small CLI for exercising the core

tests/
├── test_graph.py
├── test_register.py
├── test_excel.py
└── test_compare.py

docs/
├── architecture.md
├── excel-ingestion.md
├── model-version-intelligence.md
├── portfolio-demo.md
├── analysis-lab.md
└── roadmap.md

examples/
├── lineage_demo.py
├── register_demo.py
├── model_version_demo.py
├── portfolio_demo.py
├── sample_forecasts.csv
└── sample_models/
```

## Status

The model-lineage MVP is functional. The experimental Analysis Lab adds a transparent fixed-structure DCF with exact four-driver attribution, analyst-controlled stress scenarios, reproducible simulations, release-date-aware backtesting, an append-only local memory log, manual narrative review and a Streamlit UI. The backend is covered by **40 automated tests**. The dashboard source is syntax-checked but still needs its first interactive smoke test on a machine with Streamlit installed. Numerical attribution for *arbitrary Excel formulas*, empirical distribution calibration, automatic filing extraction and a deployed multi-user product remain unimplemented.

## Why this project exists

Most finance automation projects try to automate the analyst. FinTrace takes the opposite view: the more consequential the judgement, the more important it is to make the reasoning visible, challengeable and testable.
