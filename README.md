# 企业年报专业分析

由官方年报及必要的补充披露建立信用研究底稿，形成有证据链的评级建议、Word 报告、Excel 底稿和 PowerPoint 讨论稿。A 股为主，按企业实际采用的 CAS、IFRS、HKFRS 或 US GAAP 分析港美及其他披露。无需金融数据订阅。

## 得到什么

对企业完整年报及相关披露进行深入研究，并逐项对照国内外评级机构适用于该企业的分析方法。分析范围由原始资料和方法要求建立，不能用预先挑选的几个领域、指标或模板代替。执行过程见[全面分析程序](skills/annual-report-analysis/references/analysis-program.md)。

每项适用内容形成有来源的专业判断，说明证据、计算或推理、相互影响、反证和后续行动，并汇入同一底稿及三份成果。评级建议保留对象、尺度、方法版本、形成过程与变动条件。缺少足以决定等级的材料或规则时，明确尚不能形成的结论及所需证据。

## 看一个真实案例

[宁德时代2025年底稿](examples/catl-2025/workpaper.json)以官方年报为输入，复算利润现金、融资负债、权益、供应商融资和现金口径。示例成果：[Word](examples/catl-2025/deliverables/report.docx)、[Excel](examples/catl-2025/deliverables/workbook.xlsx)、[PPT](examples/catl-2025/deliverables/presentation.pptx)。这是限定范围研究示范，不是完整审计或正式评级。

[复现说明与原文核对要点](examples/catl-2025/README.md)列出输入校验值、关键事实页码、预期计算及保留的差额。

[四家A股电池企业的真实披露案例](examples/a-share-battery-panel/README.md)进一步展示2022—2025原报告版本、成本重分类、历史时间分割和独立复算；附三种实际文件。此次留出样本中，简单上期值基准优于固定OLS，失败结果与适用限制一同公开。

```bash
python -m pip install -r skills/annual-report-analysis/requirements.txt
npm install --prefix skills/annual-report-analysis
python skills/annual-report-analysis/scripts/export.py examples/catl-2025/workpaper.json --output output/catl
```

Python 3.11+、Node 18+。在可写仓库副本运行，不向插件缓存写产物。只有导出命令不会自动读取并分析另一家公司；向安装了本技能的宿主提供原始年报与任务，由其取证、建立底稿和解释。

## 方法与验证


后续依据可复现错误和重复实际需求改进。反馈请提供任务、公开来源/定位、实际结果、期望及其依据，不提交未授权保密年报或账户信息。项目不内置用户追踪。

MIT 许可。准则和第三方报告保持原链接，不整体转载；AI专业研究角色不等同真人执业签字或评级机构授权。
