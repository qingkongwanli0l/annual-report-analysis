# 原始资料与适用规则

维护核查日：2026-10-02。这是一份适用性索引，不是法规引擎或准则全文。每项任务记录实际报告政策及所用规则版本；检索最新文本不等于该报告期已适用。

## 查找和读取报告

先核对发行人全称、代码、年度、完整报告/摘要、修订版本、公布日期及审计报告签署日期。A股：[巨潮](https://www.cninfo.com.cn/)、[上交所](https://www.sse.com.cn/)、[深交所](https://www.szse.cn/)及公司官网；港股：[披露易](https://www.hkexnews.hk/)及公司官网；美股：[SEC EDGAR](https://www.sec.gov/edgar/search/)及公司官网。外国发行人可能提交20-F，不能只查10-K。官方接口失败就用另一官方渠道或用户原件，不伪造下载成功。

PDF页码从1开始，同时记录报告印刷页、附注编号、表和行。电子文本提取后，特别回看跨页续表、合并/母公司切换、括号负号、外币列和小数/千分符。扫描页用OCR/视觉，不能把OCR空白当“未披露”。公开URL可能变化，保留文件SHA256与取得日期供复核，不转载整库年报。

财务事实优先经审计财务报表及附注；业务/KPI和管理层解释来自相应章节，标明是否属于审计覆盖。问询回复、债券条款、监管资本报告和期后公告补足年报范围。第三方聚合值和XBRL用来定位/交叉核对，标签单位、维度、期间和合并范围仍须核验。

## 会计适用表

| 专题 | 已核查的关键边界与原始入口 |
|---|---|
| 年报披露 | 证监会2025年第3号年报内容与格式准则自2025-07-01施行，是披露规则，不替代确认计量。[公告](https://www.csrc.gov.cn/csrc/c101954/c7547588/content.shtml) |
| CAS30新版 | 财会〔2026〕11号按指定境内外上市企业2027、其他境内上市企业2029、非上市企业2030分步实施，允许提前采用。不得全部套在2025年报。[准则](https://kjs.mof.gov.cn/zt/kjzzss/kuaijizhunzeshishi/202608/t20260806_3995008.htm)、[实施说明](https://ln.mof.gov.cn/lianzhengjianshe/202608/t20260811_3995236.htm) |
| IFRS18/HKFRS18 | 2027-01-01起开始的年度期间适用，允许提前采用；核查公司采用状态。利润表新分类不直接等于现金流分类。[IFRS](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-18-presentation-and-disclosure-in-financial-statements/)、[HKICPA](https://www.hkicpa.org.hk/en/Standards-setting/Standards/New-and-major-standards/New-and-Major-Standards/HKFRS18) |
| 现金 | [CAS31](https://kjs.mof.gov.cn/zt/kjzzss/kuaijizhunzeshishi/200806/t20080618_46250.htm)、[IAS7](https://www.ifrs.org/issued-standards/list-of-standards/ias-7-statement-of-cash-flows.html/)；IFRS18对IAS7有相应修改。US GAAP现金流勾稽可能包含受限现金，按原报表定义读取。 |
| 收入 | [CAS14](https://kjs.mof.gov.cn/zt/kjzzss/kuaijizhunzeshishi/201709/t20170907_2694006.htm)；金融工具、保险、租赁的收入不是一律客户合同收入。主责人/代理人、返利、验收、履约进度分别核验。 |
| 金融工具 | [CAS22](https://www.mof.gov.cn/zcsjtsgb/gfxwj/201703/t20170331_3583504.htm)；[解释19](https://kjs.mof.gov.cn/zhengcefabu/202512/t20251218_3979556.htm)自2026-01-01施行；[解释20](https://kjs.mof.gov.cn/zhengcefabu/202606/t20260615_3991686.htm)按其公布及过渡规定使用。CAS/IFRS ECL与US GAAP CECL不可强制三阶段对应。 |
| 减值 | [CAS8](https://kjs.mof.gov.cn/zt/kjzzss/kuaijizhunzeshishi/200806/t20080618_46240.htm)范围的已确认减值不能转回；[IAS36](https://www.ifrs.org/issued-standards/list-of-standards/ias-36-impairment-of-assets/)对非商誉另有转回条件。存货与信用减值属于各自规则。 |
| 研发与租赁 | [CAS6](https://kjs.mof.gov.cn/zt/kjzzss/kuaijizhunzeshishi/200806/t20080618_46242.htm)、[IAS38](https://www.ifrs.org/issued-standards/list-of-standards/ias-38-intangible-assets/)、[CAS21](https://kjs.mof.gov.cn/zt/kjzzss/kuaijizhunzeshishi/201910/t20191028_3411190.htm)。美国研发/软件专门规定及ASC842经营/融资租赁须分别检查；不能制造通用跨准则调整。 |
| 合并与分部 | [CAS33](https://www.mof.gov.cn/gp/xxgkml/hjs/201402/t20140220_2512607.htm)、[CAS28](https://kjs.mof.gov.cn/zt/kjzzss/kuaijizhunzeshishi/200806/t20080618_46220.htm)；CAS35须结合[解释3第八项](https://www.mofcom.gov.cn/zcfb/zgdwjjmywg/art/2009/art_82703a66a45743c7a976374f21014052.html)。同一控制判断、经营分部、收入分拆和资产组不是同一边界。 |
| 保险 | CAS25分步实施及2025年暂缓安排不能一律简化为所有企业2026实施。[财政部通知文告](https://www.mof.gov.cn/gkml/caizhengwengao/wg2025/wg202506/202509/P020250901386386943150.pdf)、[IFRS17](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-17-insurance-contracts/)。先核对公司政策与过渡。 |
| 非经常损益 | [证监会2023年规则](https://www.csrc.gov.cn/csrc/c101954/c7451398/content.shtml)。优先正式调节表，分析者调整与正式扣非分列，反复出现的所谓一次性项目应重新评价。 |

具体业务还应查[财政部2025年报通知](https://kjs.mof.gov.cn/gongzuotongzhi/202512/t20251224_3980024.htm)等实施要求。征求意见稿、监管发现和机构分析方法都不能冒充适用准则原文。

## 审计和信用方法的版本

中国审计、ISA、PCAOB按审计报告所述基础及期间进入官方现行目录。ISA240修订、ISA570（2024）已发布但相关生效日期为2026-12-15起开始的期间，不能直接视为2025中国年报法定要求。PCAOB技术辅助分析修订适用于2025-12-15起开始的财年，原审计意见、CAM/KAM、强调事项和持续经营段落须独立分类。[IAASB准则](https://www.iaasb.org/standards-pronouncements)、[PCAOB按期准则目录](https://pcaobus.org/oversight/standards/auditing-standards)、[中注协](https://www.cicpa.org.cn/)。详细执行读会计审计参考。

评级方法登记机构、名称、版本、原始/修订日期、适用行业/对象/尺度、正文可得范围。方法来源可从中诚信、联合、鹏元、东方、大公、新世纪及S&P、Moody’s、Fitch、DBRS、KBRA的官方目录查找；公开目录不等于全部参数可得。方法仅有目录/摘要时，可用已证实主题开展自己的分析，但不能宣称复现其整套模型。

国内方法的对象选择、指标口径及适用范围见[国内信用方法](domestic-credit-methods.md)；官方目录不证明具体方法仍在用，也不证明全文或参数已取得。行业、特殊结构和金融方法仍按相应参考执行；公开目录中的历史版、提案、不同尺度和特殊交易不直接合并计数。

重要已识别差异：联合2026工商方法含自身历史加权与360天公式，和项目平均权益ROE不能混名；鹏元国内/全球财务调整不同；S&P回收方法2026-03-31更新；Fitch工商2026-01-09、银行2026-05-08及保险后续版本分别核验；Moody’s带OUTDATED的旧PDF不作现行方法。金融机构另见金融参考中的当前方法及缺口。没有校准证据不得将等级直接转换PD。

版本使用示例：大公PFM-TY-2025-V.3.0，正文2025-12-10发布生效、目录12-18，当前58%/42%不能沿用历史51%/49%。中诚信2026发布的企业集团文件代码仍为C210200_2024_02，一般投资控股为C210101_2026_03；其20%/30%/50%包含下一年预测，与联合三年历史加权不同。中诚信支持目录上传2026-03-11但正文为2025版，远东总论封面2024年11月而2025-02-28生效。原文页码、输入及未实施评分边界均见国内参考，不把上传日期、代码年份或模型指标当会计准则事实。
