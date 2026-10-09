# Architecture

## 1. Core concept

FinTrace models financial reasoning as a directed graph.

Each node is one of:

- **Evidence** — source material such as an annual report, management guidance, market data or a historical financial statement.
- **Assumption** — a forward-looking input chosen by the analyst.
- **Calculation** — a deterministic transformation.
- **Output** — a material model result such as free cash flow, enterprise value or implied share price.
- **Judgement** — the analyst's written interpretation or rationale.

Edges represent dependency or support relationships.

Example:

```text
Annual report guidance
        ↓ supports
Revenue growth assumption
        ↓ feeds
Revenue forecast
        ↓ feeds
Free cash flow
        ↓ feeds
DCF valuation
        ↓ informs
Investment thesis
```

The graph is deliberately independent from Excel. Excel will become one input adapter, not the core of the system.

## 2. Why a graph

A graph lets FinTrace answer questions ordinary spreadsheets struggle with:

- "Why is this valuation £37?"
- "Which pieces of evidence support this assumption?"
- "Which outputs depend on this assumption?"
- "Which high-impact assumptions have weak evidence?"
- "What breaks if this node is removed?"

This becomes the foundation for attribution, fragility, backtesting and analyst memory.

## 3. Layers

### Domain layer
Pure Python objects representing evidence, assumptions, calculations, outputs and judgements.

### Lineage layer
A directed graph for dependency and support relationships.

### Adapter layer — implemented / expanding
Importers / adapters for:
- Excel workbooks — implemented;
- workbook-version comparison — implemented;
- CSV / structured financial data — planned;
- source documents and extracted snippets — planned.

### Analysis layer — later
- assumption-quality checks
- valuation attribution
- thesis fragility
- Monte Carlo
- backtesting
- analyst-bias metrics
- narrative-vs-numbers checks

### Interface layer — later
Start with CLI. Add FastAPI only after the core is stable. A web UI comes later.

## 4. Non-goals

FinTrace is not intended to:

- automatically decide the "correct" forecast;
- replace an analyst's financial model;
- generate investment recommendations;
- hide financial calculations behind an LLM;
- silently alter user assumptions.

## 5. Data integrity rules

The initial engine should enforce:

1. Node IDs are unique.
2. A node cannot depend on itself.
3. The reasoning graph must be acyclic.
4. Missing dependency nodes are rejected.
5. Every material assumption can carry a rationale and confidence level.
6. Every evidence node can carry provenance metadata.
7. Financial outputs can be traced upstream to their dependencies.

## 6. Future Excel integration

Excel support should preserve the workbook as the analyst's working model.

FinTrace should read:

- relevant cells and formulas;
- named ranges;
- selected assumptions;
- outputs;
- workbook version metadata.

It should then map those values into the lineage graph rather than converting the entire spreadsheet into a proprietary model.

This keeps FinTrace useful even when the analyst's spreadsheet is complex or bespoke.

## Implemented assumption register

The `AssumptionRegister` validates evidence references and preserves every `AssumptionRevision`.
Revisions contain value, unit, author, rationale, confidence, evidence links and timestamp.
The persisted JSON document can be loaded back into the typed models; writes use a temporary
file followed by an atomic replacement. The review routine raises flags for missing support
and potentially stale sources, but does not assess truthfulness or recommend a forecast.

### Limitations

- JSON files are local snapshots, not a multi-user event database.
- `source_uri` is provenance metadata; the application does not verify that URL or excerpt.
- All example data is fictional.
- No Excel ingestion, valuation calculations or production-ready security controls yet.
