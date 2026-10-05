# HKEX2025：增长、公司资金与清算资源的独立研究示例

共同底稿含94项事实、28项计算、13项勾稽及9项实质判断；这是一项专业会计研究辅助案例，不是对完整交易所风险或财务报表的鉴证。

实际成果：[Word](deliverables/report.docx)、[Excel](deliverables/workbook.xlsx)、[PPT](deliverables/presentation.pptx)。[输入](workpaper.json)保留事实、计算定义与证据，[独立预期](expected.json)供复算核对。运行下方导出命令后，完整JSON结果及版本和文件哈希生成在`output/hkex/`。

## 来源与复现

- [HKEX2025年报](https://www.hkexnews.hk/listedco/listconews/sehk/2026/0316/2026031600319.pdf)，240页，SHA256 `01f90f3b213f368e1ed66887ec6ec862f5129c74d5c89d3c11cf5b0fda8887ee`。
- [FCA最终通知](https://www.fca.org.uk/publication/final-notices/london-metal-exchange-2025.pdf)，41页，SHA256 `8fee698e2f844433e57039749c3765b404b1309edc9229d21ea8b599a491b915`。
- [HKEX2025可持续报告](https://www.hkexgroup.com/-/media/HKEX-Group-Site/ssd/Investor-Relations/Regulatory-Reports/documents/2026/260316sr_e.pdf)，76页，SHA256 `ea0deef0b3f3a0d31c01d7936d60a652e4a3b9a6dd41b7d5351a80fba6b4af5f`。

不转载完整原件。具体来源页码、公开补证和剩余请求见底稿。底稿按HKFRS、HKD及集团/母公司/会员资金的实际口径保留，不能把人民币案例的数据字典直接套入。

在仓库根安装README依赖后：

```bash
python skills/annual-report-analysis/scripts/export.py examples/hkex-2025/workpaper.json --output output/hkex
```

命令复算既有研究，不会自动完成另一家公司的取证。Office文件是这次导出快照；直接改Excel只更新公式，不同步文字、JSON、Word或PPT。正式修订应更新共同JSON，再统一导出。

## 关键复核答案

以下金额均为HKD百万元，页码为年报PDF页码；完整输入和计算链见底稿。

| 核验点 | 结果 | 来源及边界 |
|---|---:|---|
| 收入同比 | 36.8903% | p153—158；不与投资收益合并后换名为收费收入 |
| 税前利润经非现金及营运项目调整 | 19,005 | p205完整逐行桥，会员/结算项成对读取 |
| 主要经营现金 → 总经营现金 | 19,855 → 25,627 | p205、147；差额5,772为投资组合净赎回，不是新增收费利润 |
| 期末现金及现金等价物 | 19,353 | p147、167—168；货币资金总池182,724含会员/清算资金，不等于公司可付现金 |
| 会员保证金资源 / 清算基金净额 | 269,243 / 35,796 | p190、193；总额不证明逐服务压力覆盖 |
| 总权益完整滚动 | 58,729 | p145—146；保留非控股权益及看跌期权相关各列 |
| 看跌期权负债滚动 | 398 | p195；非控股分配不重复扣总权益 |
| 商誉 / 软件净额滚动 | 13,274 / 4,341 | p185—187；软件成本与累计摊销两条线分开 |
| 主要经营现金减两项资产付款及归母股息 | 1,252 | p147、205；是明确的局部资金观察，不冒称完整自由现金流 |

全部28项计算与独立预期一致，13项勾稽零残差。公式结果并不替代会计政策、经济机制和原文复核。

尚未完成：CCP完整日内流动性与压力情景、CGU估值全模型、总部合同和逐笔支付、控制运行样本及气候模型原始数据。报告已把取得的公开补充材料写回底稿，未继续索取已经公开取得的整份报告。
