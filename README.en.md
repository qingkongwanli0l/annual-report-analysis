# Annual Report Analysis

Turn official annual reports into source-linked research, reproducible financial workpapers and editable Word, Excel and PowerPoint deliverables. A-share first, with accounting-basis-aware support for Hong Kong and US disclosures.

One skill covers business and growth drivers, accounting policies and estimates, earnings-to-cash bridges, audit-support procedures, corporate credit adjustments, liquidity, conditional recovery and quantitative scenarios. Banks, insurers, securities firms and clearing institutions use separate methods.

Facts retain their original value, unit, entity, scope, period, accounting basis and source location. Calculations reference those facts. Findings retain competing explanations and the evidence that could change them. Missing values remain missing; unperformed procedures never become completed audit evidence.

The Python scripts use maintained libraries for PDF extraction, validation, numerical root finding and Office documents. PptxGenJS exports editable presentations. There is no network service, mandatory financial-terminal subscription, telemetry or additional model API key required by this project.

## Reproduce a public example

The [CATL 2025 workpaper](examples/catl-2025/workpaper.json) has source references and actual financial calculations. [Word](examples/catl-2025/deliverables/report.docx), [Excel](examples/catl-2025/deliverables/workbook.xlsx) and [PowerPoint](examples/catl-2025/deliverables/presentation.pptx) are generated from that same workpaper.

The [example guide](examples/catl-2025/README.md) provides the source checksum, page references, expected figures and retained reconciliation differences.

The [four-company A-share battery example](examples/a-share-battery-panel/README.md) adds real 2022–2025 disclosures, version gaps, cost reclassification, a fixed historical split and an independent arithmetic check, with all three Office files. The last-value baseline beats the fixed OLS model on this small holdout; the result and limitations remain public.

```bash
python -m pip install -r skills/annual-report-analysis/requirements.txt
npm install --prefix skills/annual-report-analysis
python skills/annual-report-analysis/scripts/export.py examples/catl-2025/workpaper.json --output output/catl
```

Requires Python 3.11+ and Node 18+. Run in a writable checkout or use the host's existing dependencies. Output belongs in the task workspace, never the installed plugin cache. Exporting an existing workpaper does not automatically analyze a different company: the agent must first read the source material and form its own evidence-backed analysis.

ChatGPT/Codex and Claude manifests reference the same core skill; DeepSeek harness can discover the folder under `.agents/skills` or `.dsh/skills`. Native end-to-end host results are tracked separately from packaging compatibility.

Research records identify official sources, method versions and access limitations. Public methods do not supply all internal rating-agency data or parameters. Analysis and draft recommendations are distinct from statutory audit opinions, authorized ratings and calibrated default probabilities.

MIT license. Third-party standards and reports remain linked rather than republished in full. Contributions should include a reproducible task, source location, observed result and evidence for the correction.
