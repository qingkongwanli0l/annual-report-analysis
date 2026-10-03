# 企业年报分析 Annual Report Analysis

[English](README.en.md)

把企业年报转成有原文依据、可以复算的 **Word 分析报告、Excel 财务底稿和 PowerPoint 演示文稿**。A 股优先，兼顾港股、美股；适用于投资研究和财会复核。

这是运行在 AI 宿主中的 skill：宿主负责阅读、取证和解释，附带脚本负责计算与文件生成。无需付费金融终端，不需要另配模型 API Key。它不会仅凭一条 Python 命令自动理解整份年报。

## 从年报到成果

输入完整年报，或提供公司和年度：

> 分析贵州茅台 2024 年年报，说明经营变化、利润与现金流差异、重要附注和待核问题。生成 Word、Excel 和 PPT，并保留每项关键数字的出处。

结果包括：

- `report.docx`：主要结论、经营与财务变化、会计及附注事项、审计与治理、未决问题及阅读范围。
- `financials.xlsx`：原始数据、口径标准化、可见公式、勾稽差额和来源索引。
- `presentation.pptx`：汇报摘要与关键图表，引用与前两份文件共用同一底稿。
- `calculated.json`：可复算的事实、计算、分析及证据记录。

[贵州茅台 2024 年公开案例](examples/moutai-2024/README.md)提供原始底稿及可编辑的 [Word](examples/moutai-2024/report.docx)、[Excel](examples/moutai-2024/financials.xlsx)、[PPT](examples/moutai-2024/presentation.pptx)。计算 JSON 在本地导出时生成。

## 为什么需要这个 skill

年报分析经常出错的地方是期间、单位、合并范围和附注，而不只是除法。这个项目保留四表与附注的关系，区分披露事实、管理层表述和分析推断；缺失不填零，重述不静默覆盖，异常不直接判定为舞弊。

现金勾稽包含汇率影响；ROE/ROA 使用期初期末平均余额；金融企业不套工业企业周转与现金利润指标。会计准则按报告实际采用的版本判断，不能把最新发布的准则应用于所有历史年报。

## 安装与平台支持

一份 `skills/annual-report-analysis` 同时用于 ChatGPT 插件、Claude Code 和 DeepSeek harness。[完整安装步骤与实测状态](docs/installation.md)。支持标准格式不等于所有聊天模式都能执行 Python/Node 或导出文件；请以安装说明中的能力范围为准。

首发为 **0.1.0 公开预览**：Claude Code 本地冒烟已通过；ChatGPT 原生插件与 DeepSeek Harness 的运行实测尚未完成。[下载插件或独立 skill 包](https://github.com/qingkongwanli0l/annual-report-analysis/releases/tag/v0.1.0)。

本地依赖：Python 3.10+、Node.js 18+。在仓库根目录执行：

```sh
python -m pip install -r skills/annual-report-analysis/requirements.txt
npm install --prefix skills/annual-report-analysis
```

随后将技能目录复制到宿主支持的技能目录，或加载插件。技能的参考文件、脚本、依赖清单和样式均自包含，不依赖仓库外的私有资源。

## 无需模型即可复算公开案例

在安装依赖后，从仓库根目录运行：

```sh
python skills/annual-report-analysis/scripts/calculate.py examples/moutai-2024/workpaper.json --output output/moutai-2024/calculated.json
python skills/annual-report-analysis/scripts/export.py output/moutai-2024/calculated.json --output-dir output/moutai-2024
```

这是对预先整理并核对原文的公开案例底稿进行复算和导出；新公司的年报仍需宿主阅读原文并构建底稿。

提取本地文件供宿主核对：

```sh
python skills/annual-report-analysis/scripts/extract.py annual-report.pdf --pages 1-3 --output output/pages.json
python skills/annual-report-analysis/scripts/extract.py filing.html --output output/filing.json
```

提取器保留 PDF 页序号或 HTML 定位，不保证表格识别正确，也不执行 OCR。扫描件由宿主已有视觉/OCR 工具处理，关键数字需回看页面。

## 工作底稿与计算边界

底稿格式见 [data-contract](skills/annual-report-analysis/references/data-contract.md)。金额保留原始十进制字符串、币种、单位倍率、期间、准则、合并范围及来源位置。计算器只计算有可比输入的指标；无法计算时保留原因。

事实值、公式或口径发生变化后，重新运行计算器再导出。财务比率是透明的分析定义，不是会计合规认证。阅读未覆盖部分必须披露；母公司报表、分析者调整以及公司自行披露的非准则指标单独呈现。

首发不提供自动审计、造假概率、买卖指令或统一财务健康分数。银行、保险、证券使用披露的行业指标及专门阅读要点。详见 [会计依据](docs/accounting-sources.md) 和 [行业说明](skills/annual-report-analysis/references/industries.md)。

## 验证与打包

```sh
python -m unittest discover -s tests -v
python scripts/package.py
```

打包结果写入忽略的 `dist/`，仅包含技能、插件清单和许可，不包含本地研究、过程材料或用户输出。

## 反馈和贡献

报告问题时提供宿主及版本、公开来源、具体期间/页码、实际值与预期值；请不要上传私有财务资料、账户凭据或完整受限文档。更正计算规则应附一个能复现问题的小样例。功能依据重复出现的真实任务增加，不提前扩建数据平台。

项目代码和自编文档采用 [MIT](LICENSE)。引用的年报、准则及第三方项目仍受其自身条款约束；本项目只保存必要事实、分析、官方链接与校验信息，不将外部文件重新声明为 MIT。
