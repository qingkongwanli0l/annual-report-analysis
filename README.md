# 企业年报专业分析

由官方年报及必要的补充披露建立信用研究底稿，形成有证据链的评级建议、Word 报告、Excel 底稿和 PowerPoint 讨论稿。A 股为主，按企业实际采用的 CAS、IFRS、HKFRS 或 US GAAP 分析港美及其他披露，无需金融数据订阅。

**当前为开发版，尚未合并主分支、正式发布重建版或上架宿主公共目录。** 已有的 [v0.1.0 Release](https://github.com/qingkongwanli0l/annual-report-analysis/releases/tag/v0.1.0) 属于旧版。

[English](README.en.md) · [安装与宿主能力](docs/installation.md) · [核心 Skill](skills/annual-report-analysis/SKILL.md)

## 得到什么

对企业完整年报及相关披露进行深入研究，并逐项对照国内外评级机构适用于该企业的分析方法。分析范围由原始资料和方法要求建立，不能用预先挑选的几个领域、指标或模板代替。具体要求见[全面分析程序](skills/annual-report-analysis/references/analysis-program.md)。

每项适用内容形成有来源的专业判断，说明证据、计算或推理、相互影响、反证和后续行动，并汇入同一底稿及三份成果。评级建议保留对象、尺度、方法版本、形成过程与变动条件。缺少足以决定等级的材料或规则时，明确尚不能形成的结论及所需证据。

## 使用

按[安装说明](docs/installation.md)将完整技能目录安装到宿主，提供原始年报、企业及期间、分析目的。宿主负责取证、建立底稿和解释；脚本负责计算及导出。在线查找报告需要宿主具备浏览能力。

可先从真实案例了解成果形式：

- [科顺股份及科顺转债研究](examples/keshun-2025/README.md)：从原件事实、适用方法和因素判断形成条件性主体及债项建议，可先看 [10 页简报](examples/keshun-2025/deliverables/research-brief.pptx)。
- [宁德时代 2025 年案例](examples/catl-2025/README.md)：包含[共同底稿](examples/catl-2025/workpaper.json)及同源 [Word](examples/catl-2025/deliverables/report.docx)、[Excel](examples/catl-2025/deliverables/workbook.xlsx)、[PPT](examples/catl-2025/deliverables/presentation.pptx)，展示限定范围的财务研究。
- [HKEX 2025 年案例](examples/hkex-2025/README.md)：展示港股与金融基础设施研究中的资金范围及会计口径。
- [Crown Castle 2025 年报与 Fiber 出售案例](examples/crown-castle-2025/README.md)：连接减值、终止经营、实际交割、公开备考与信贷契约，保留原件差异和未取得的证据。
- [四家 A 股电池企业案例](examples/a-share-battery-panel/README.md)：展示真实披露的跨公司、跨期研究及模型适用限制。

在可写仓库副本中安装依赖并导出宁德时代案例：

```bash
python -m pip install -r skills/annual-report-analysis/requirements.txt
npm install --prefix skills/annual-report-analysis
python skills/annual-report-analysis/scripts/export.py examples/catl-2025/workpaper.json --output output/catl
```

需要 Python 3.11+、Node 18+。产物写入任务目录，不写插件缓存。导出已有底稿不会自动分析另一家公司。

## 实际能力与限制

Claude Code 和官方 DeepSeek harness 已实际执行技能并生成三种文件，但全面分析初稿仍存在取数、口径和因果判断错误，需要专业核验。Claude Code 实测使用其已配置的 DeepSeek 模型，不代表 Anthropic 模型测试。ChatGPT 原生完整工作流尚未完成实测。

Excel 数值编辑可触发公式重算，但不会回写共同底稿或同步更新 Word、PPT 及叙述。正式更新应修订共同底稿并重新导出三份成果。文件生成与算术正确不代表专业判断正确。

技能提供分析程序和必要的官方来源引用。现有参考不代表已覆盖所有评级机构的全部内容。研究建议不等同于正式评级行动、法定审计意见或真人执业签字。

MIT 许可；外部依赖分别适用各自许可，区间库 [portion](https://github.com/AlexandreDecan/portion) 为 LGPL-3.0，源码不随本项目复制。准则和第三方报告保持原链接，不整体转载。反馈请提供公开来源、问题位置、实际结果和修正依据。项目不内置用户追踪。
