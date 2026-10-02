# Analysis workpaper format

UTF-8 JSON is the single workpaper used by the calculator and all three exporters. Monetary facts retain the source's decimal strings. Missing is `null`, never zero. This file is the canonical interface.

```json
{
  "company": {
    "name": "Example company",
    "identifier": "EXAMPLE",
    "market": "A-share",
    "industry": "non-financial",
    "accounting_standard": "CAS",
    "scope": "consolidated",
    "currency": "CNY",
    "period_start": "2024-01-01",
    "period_end": "2024-12-31",
    "prior_period_start": "2023-01-01",
    "prior_period_end": "2023-12-31",
    "display_unit": "百万元",
    "display_multiplier": "1000000",
    "language": "zh"
  },
  "sources": [{
    "id": "ar2024",
    "title": "2024 annual report",
    "url": "https://example.com/annual-report.pdf",
    "published": "2025-03-31"
  }],
  "facts": [{
    "id": "revenue_2024",
    "metric": "revenue",
    "label": "营业收入",
    "value": "123.45",
    "raw_value": "123.45",
    "currency": "CNY",
    "unit_multiplier": "1000000",
    "period_start": "2024-01-01",
    "period_end": "2024-12-31",
    "scope": "consolidated",
    "standard": "CAS",
    "source_id": "ar2024",
    "locator": "PDF p. 100 / printed p. 98, consolidated income statement",
    "restated": false,
    "basis": "reported"
  }],
  "coverage": [{
    "section": "现金流量表",
    "status": "reviewed",
    "source_id": "ar2024",
    "locator": "PDF p. 104",
    "note": ""
  }],
  "analysis": {
    "summary": [{"text": "Evidence-based conclusion", "kind": "inference", "evidence": ["fact:revenue_2024"]}],
    "sections": [{"title": "经营变化", "items": [{"text": "Source-based observation", "kind": "fact", "evidence": ["source:ar2024"]}]}],
    "questions": [{"text": "An unresolved question", "evidence": ["source:ar2024"]}],
    "limitations": ["Only disclosed comparative periods are available."]
  }
}
```

## Inputs

- `company.industry`: `non-financial`, `bank`, `insurance`, or `securities`. Language is `zh` or `en`. Company metadata specifies the analysis scope, not every source's scope.
- Every source has `id`, `title`, `url` (empty for a private upload), and `published` (null if unknown). Optional `sha256` records a fetched file's hash. Sources may additionally include `locator` for a specific note or narrative passage. Create separate source entries for distinct narrative passages when needed.
- Every fact has all fields shown above. Instant balance-sheet facts use `period_start: null`; duration facts carry both dates. `value: null` means missing. Parent-only facts use `scope: "parent"` and remain separate.
- `basis` is `reported` or `analyst_adjusted`. Only reported facts are selected automatically. Optional `use_for_analysis: false` retains a superseded/original comparative without selecting it. Never silently choose between duplicate eligible facts. Retain the restatement explanation in analysis.
- `value` is a signed decimal string without commas, parentheses, units or percentage signs; `raw_value` preserves the original text. `unit_multiplier` converts the source figure to the base currency unit. Optional `note` documents metric-specific definitions. This v1 calculator takes monetary facts, not percentages or per-share facts; disclosed sector KPIs belong in cited narrative sections.
- Rounding precision is derived from the numeric text in `raw_value`, including trailing zeros. When the original uses a dash, scientific notation or other ambiguous representation, supply `source_decimals` as the number of decimal places actually displayed and explain the convention in `note`. Do not derive source precision from a normalized value with trailing zeros removed.
- `coverage.status`: `reviewed`, `partial`, or `unavailable`. Coverage is a record of work actually performed, not a requirement to claim all pages read.
- Narrative items have `text`, `kind` (`fact`, `management`, `inference`), and `evidence`. Questions need only `text` and `evidence`. Evidence references use `fact:<id>`, `source:<id>`, `calculation:<id>` or `check:<id>`; use a source locator for narrative claims.

## Monetary metric keys

Duration: `revenue`, `cost_of_sales`, `net_income`, `parent_net_income`, `minority_net_income`, `cfo`, `cfi`, `cff`, `fx_effect`, `capex`, `comprehensive_income`, `owner_transactions`.

Instant: `assets`, `liabilities`, `equity`, `parent_equity`, `current_assets`, `current_liabilities`, `inventory`, `receivables`, `cash_equivalents`.

`cost_of_sales` and `capex` are positive expense/payment amounts. `capex` is cash paid for property, plant, equipment and intangible assets, excluding acquisitions and financial investments; describe any limitation. `receivables` is net trade accounts receivable on a consistent basis. `owner_transactions` is the signed total of disclosed owner changes for the equity roll-forward, including contributions, dividends and relevant transfers; do not invent a balancing plug. `fx_effect` is the disclosed exchange-rate effect on cash and cash equivalents; absence is not zero.

## Calculator output

The calculator retains input fields and replaces `calculations`, `checks`, and `calculation_notes`. Each fact gains `normalized_value` (base-currency decimal string or null). It does not author narrative conclusions.

Each calculation has `id`, `label`, `value` (decimal string or null), `unit` (`currency`, `percent`, `ratio`, `days`), `expression`, `inputs` (fact IDs), `reason` (null or explanation), and `period_end`. Percent values are fractions (0.12 = 12%). Expressions contain basic arithmetic and fact placeholders, e.g. `({revenue_2024}-{revenue_2023})/{revenue_2023}`. No arbitrary code is evaluated. Missing or inapplicable calculations have null expression/value and an explicit reason.

Each check has `id`, `label`, `value` (residual in base currency, or null), `unit: "currency"`, `expression`, `inputs`, `status` (`matched`, `difference`, `unavailable`), `tolerance` (decimal string or null), and `reason`. Tolerances derive from the source precision, not an arbitrary percentage of assets.

Exporters consume the calculated JSON. They display currency values using `company.display_multiplier` and `display_unit`; Excel also retains raw and base-currency values. Exporters never invent calculations or recompute narrative judgments. Excel formulas reference normalized input cells and cache the computed result. Null results remain unavailable with a reason.
