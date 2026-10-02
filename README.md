# 企业年报专业分析

输入官方年报，形成有原文依据、可复算、可以继续编辑的 Word 报告、Excel 底稿和 PowerPoint 讨论稿。A 股为主，按企业实际采用的 CAS、IFRS、HKFRS 或 US GAAP 分析港美及其他披露。无需金融数据订阅。

## 得到什么

- 经营与成长：解释量价结构、分部、并购、资本投入和兑现，保留其他解释。
- 会计与盈利质量：四表及附注勾稽、政策交易判断、净利润至现金和资产负债滚动桥。
- 审计支持：风险、认定、总体、具体程序、实际结果与追加资料，区分公开分析和未执行细节检查。
- 企业信用：债务盈利现金调整、可调度资金、期限及契约、支持约束、债项顺位、条件回收和跟踪。
- 量化分析：业务驱动的现金/债务情景、逆向压力、按真实可用时点的面板与样本外基准比较。
- 金融机构：银行准备/资本/流动性，保险合同/CSM/偿付能力，证券客户资金与净资本，清算风险分别处理。

所有重要数字来自同一底稿。原值、重述、假设、缺失和调整分开；未披露不填零，负分母不包装成正常比率，不用未经校准分数映射评级或违约概率。

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
