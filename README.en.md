# Annual Report Analysis

Develop evidence-backed credit rating recommendations from official annual reports and necessary supporting disclosures, with reproducible workpapers and editable Word, Excel and PowerPoint deliverables. A-share first, with analysis based on the company's actual CAS, IFRS, HKFRS or US GAAP accounting basis. No financial data subscription is required.

**This is a development version. The rebuild has not been merged into the main branch, formally released or listed in a host's public directory.** The existing [v0.1.0 Release](https://github.com/qingkongwanli0l/annual-report-analysis/releases/tag/v0.1.0) belongs to the older version.

[中文](README.md) · [Installation and host capabilities](docs/installation.md) · [Skill](skills/annual-report-analysis/SKILL.md)

## What it does

The [comprehensive analysis program](skills/annual-report-analysis/references/analysis-program.md) examines the complete annual report and related disclosures against the domestic and international rating methodologies applicable to the company. Original sources and applicable methods determine the work; a predefined selection of topics, ratios or templates cannot substitute for that scope.

Each applicable requirement leads to a source-backed judgment with evidence, calculations or reasoning, connected effects, counterevidence and next actions in the common workpaper and deliverables. A rating recommendation records its object, scale, method version, derivation and change conditions. Missing information or rules that prevent a grade decision are identified with the evidence needed to resolve them.

## Use

Follow the [installation guide](docs/installation.md) to install the complete skill directory in your host. Supply the original annual report, company, reporting period and analytical purpose. The host gathers evidence, builds the workpaper and interprets the results; the scripts calculate and export. Finding reports online requires the host's browsing capability.

Explore the deliverables through real examples:

- [Keshun issuer and convertible-bond research](examples/keshun-2025/README.md) connects original disclosures, applicable methods and factor judgments to conditional issuer and debt recommendations. Start with the [10-slide briefing](examples/keshun-2025/deliverables/research-brief.pptx).
- [CATL 2025](examples/catl-2025/README.md) demonstrates financial research of a defined scope, with a [common workpaper](examples/catl-2025/workpaper.json) and its [Word](examples/catl-2025/deliverables/report.docx), [Excel](examples/catl-2025/deliverables/workbook.xlsx) and [PowerPoint](examples/catl-2025/deliverables/presentation.pptx) outputs.
- [HKEX 2025](examples/hkex-2025/README.md) demonstrates fund scopes and accounting definitions in research on a Hong Kong-listed financial infrastructure company.
- [Crown Castle 2025 and the Fiber sale](examples/crown-castle-2025/README.md) connects reported figures, the completed sale, forward cash and debt scenarios, and conditional issuer/debt formation in three shared-source deliverables, retaining source discrepancies and specific evidence gaps.
- [Four A-share battery companies](examples/a-share-battery-panel/README.md) demonstrates research across companies and periods using real disclosures, with explicit model limitations.

Install dependencies and export the CATL example in a writable checkout:

```bash
python -m pip install -r skills/annual-report-analysis/requirements.txt
npm install --prefix skills/annual-report-analysis
python skills/annual-report-analysis/scripts/export.py examples/catl-2025/workpaper.json --output output/catl
```

Requires Python 3.11+ and Node 18+. Output belongs in the task workspace, never the installed plugin cache. Exporting an existing workpaper does not automatically analyze a different company.

## Actual capabilities and limitations

Claude Code and the official DeepSeek harness have executed the skill and generated all three file types. Comprehensive drafts still contain source-input, definition and causal-judgment errors and require professional review. Claude Code used its configured DeepSeek model; this is not an Anthropic-model test. Native ChatGPT verification of the complete workflow remains incomplete.

Editing Excel numbers can recalculate formulas but does not update the common workpaper, Word, PowerPoint or narrative text. For a formal update, revise the common workpaper and regenerate all three deliverables. Successful file generation and correct arithmetic do not establish sound professional judgments.

The published skill keeps its analytical procedures and necessary official source references. Existing references do not represent complete coverage of every rating agency's content. Research recommendations are distinct from authorized ratings, statutory audit opinions and licensed professional sign-off.

MIT license; external dependencies retain their own licenses. The interval library [portion](https://github.com/AlexandreDecan/portion) uses LGPL-3.0 and its source is not copied into this project. Third-party standards and reports remain linked rather than republished in full. Contributions should identify a public source, problem location, observed result and evidence for the correction. The project includes no user tracking.
