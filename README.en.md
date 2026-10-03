# Annual Report Analysis

[中文](README.md)

An evidence-based annual-report skill that produces an editable **Word report, Excel workpaper and PowerPoint deck** from one sourced workpaper. Built primarily for Chinese A-share filings, with Hong Kong and US accounting references and separate treatment of banks, insurers and securities firms.

The host AI reads disclosures and authors supported analysis. Small scripts extract document text, perform deterministic calculations and export files. No financial-terminal subscription or additional model API key is required. This is a skill, not a standalone autonomous financial-analysis application.

## Use it

> Analyze this company's annual report. Explain business changes, earnings and cash quality, material accounting notes and open questions. Produce Word, Excel and PowerPoint files with traceable figures.

The deliverables share one JSON workpaper. Every fact retains its original value, reporting period, currency, unit, consolidation scope, accounting basis and document locator. Missing data stays missing. Cash reconciliation includes FX effects; average-balance ratios do not silently fall back to closing balances.

**0.1.0 is a public preview.** The Claude Code local smoke test passed; native ChatGPT and DeepSeek Harness runtime tests remain pending. [Download plugin and skill ZIPs](https://github.com/qingkongwanli0l/annual-report-analysis/releases/tag/v0.1.0).

See the [Moutai 2024 example](examples/moutai-2024/README.md) for its source workpaper and editable Office files. Calculation JSON is generated locally.

## Install dependencies

Requires Python 3.10+ and Node.js 18+. From the repository root:

```sh
python -m pip install -r skills/annual-report-analysis/requirements.txt
npm install --prefix skills/annual-report-analysis
```

Install the same `skills/annual-report-analysis` directory in your host's skill location, or load the supplied plugin. ChatGPT, Claude Code and DeepSeek harness use different discovery and execution mechanisms. Format support alone does not establish end-to-end runtime compatibility; see the scope in the [installation guide](docs/installation.md).

## Reproduce the public example without an AI call

```sh
python skills/annual-report-analysis/scripts/calculate.py examples/moutai-2024/workpaper.json --output output/moutai-2024/calculated.json
python skills/annual-report-analysis/scripts/export.py output/moutai-2024/calculated.json --output-dir output/moutai-2024
```

This recalculates an already reviewed example workpaper. For a new company, the AI host must read the original disclosure and prepare the workpaper first. Set `company.language` to `en` and author the narrative and fact labels in English for an English report; the exporters do not translate evidence text.

PDF/HTML extraction:

```sh
python skills/annual-report-analysis/scripts/extract.py annual-report.pdf --pages 1-3 --output output/pages.json
python skills/annual-report-analysis/scripts/extract.py filing.html --output output/filing.json
```

Extraction preserves document locators but does not establish that a table was read correctly. Scans require the host's OCR/vision capability and source-page verification.

## Accounting and limitations

[Workpaper contract](skills/annual-report-analysis/references/data-contract.md) · [Accounting references](skills/annual-report-analysis/references/accounting.md) · [Sector guidance](skills/annual-report-analysis/references/industries.md)

Use the standards actually adopted for the reporting period, not a blanket market-to-GAAP assumption. Keep consolidated and parent-only statements, original and restated comparatives, and reported and analyst-adjusted figures distinct. Ratios are analytical definitions, not audit opinions or accounting compliance certifications.

The first release does not generate trading instructions, fraud probabilities or universal health scores. Financial companies use disclosed sector measures. Unread sections, unavailable data and unresolved reconciliation differences remain visible.

## Test and package

```sh
python -m unittest discover -s tests -v
python scripts/package.py
```

The ZIPs under `dist/` contain the self-contained skill or plugin, excluding source annual reports, caches, installed dependencies and user outputs. No telemetry or mandatory CI gates are included.

Report issues with the host/version, public source locator, observed result and expected result. Do not submit private financial documents or credentials. Financial fixes should include a minimal reproducible example.

Project code and original documentation use the [MIT License](LICENSE). Referenced filings, standards and upstream projects retain their own terms; they are not relicensed by this repository.
