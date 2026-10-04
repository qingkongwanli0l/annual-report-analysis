# 年报量化分析：可复算情景与真实时点面板

本参考用于研究、风险和信用工作中的量化部分。先选生产问题，再判断资料是否足够。单企业年报能够支持报表桥、经营驱动、资本回报、现金质量和条件压力分析；它本身不能验证因子收益、操纵概率、校准PD或因果效果。脚本只实现下面两项明确功能，其余方法按证据执行，不以标题代替能力。

## 1. 工作产品与能力边界

| 任务 | 可交付产品 | 必要外部输入/边界 |
|---|---|---|
| 成长来源 | 同口径收入桥：有机、并购、处置、汇率、重分类及残差 | 无可比范围/销量时，不推造有机增长或量价贡献 |
| 资本配置 | 正常化经营利润与投入资本桥、含/不含商誉回报、投资兑现滞后 | 增量利润/投资只是诊断；未隔离项目现金流不称项目IRR；无市场数据不造WACC |
| 利润现金质量 | 净利润→非现金调整→营运资本→CFO，及账龄/存货/保理解释 | 资产负债表变化需剔除并购、汇率与重分类；异常不证明舞弊 |
| 经营现金压力 | `scenarios.py`逐期现金/债务表，输入门槛、融资缺口、逆向现金边界 | 工业企业简化模型；没有月度数据不能覆盖月中缺口；不输出PD |
| 同业/样本外验证 | `panel.py`按公开版本选取的毛利特征，以及一项冻结参数的毛利率预测 | 要有真实多公司多期记录；仅输出可观察的留出误差，不输出训练准确率/评级 |
| 银行/保险 | 公开NII量价桥、信用减值/核销、资本/RWA、保险服务/CSM及准备金桥 | 工业现金模型和毛利面板不适用；ECL、IRRBB、精算模型需要贷款/期限/赔付数据 |

有机增长必须能与并购、汇率等一起衔接总收入变化。[ESMA定义与调节要求](https://www.esma.europa.eu/publications-data/questions-answers/1881) 对利润—现金差异，优先用现金流量表及明细桥；并购会使单纯资产负债表差额产生应计测量偏误。[Hribar–Collins](https://onlinelibrary.wiley.com/doi/abs/10.1111/1475-679X.00041)

量价和单位经济性先在同一产品集合、数量单位和期间计算：`单位收入=收入/销量`、`单位毛利=(收入−成本)/销量`，同时保留毛利率。**构造例：** 销量100→120、单价10→9、单位成本8→7.2，则收入1000→1080；先量后价贡献为`20×10=200`和`120×(−1)=−120`。增长8%等于`(1+20%)×(1−10%)−1`，不是20%−10%。毛利率保持20%，单位毛利却从2降至1.8。收入/销量含产品组合时只称平均单位收入代理；集团内无对应数量的业务另列，不由该代理推断纯价格或效率原因。集团毛利变化另接各分部毛利及抵销，未解释残差保留。

## 2. 可复算的经营现金情景

调用 `scripts/scenarios.py`，或在Python中调用 `scenarios.run(input_dict)`。当前方法为`operating_cash_scenario_v2`。各情景分别传入完整输入；结果保存原始输入快照、方法版本、假设来源、限制和每期中间金额。改变业务驱动后必须重新运行同一个计算函数。

```text
python scripts/scenarios.py scenario-input.json --output scenario-result.json
```

命令在skill根目录执行。需要pydantic；逆向压力另需SciPy。脚本只读取本地JSON并写指定文件，不启动服务，不联网下载数据。

### 先把真实企业接入模型

在共同底稿用一张输入桥记录`原科目/附注位置及金额→期间、业务范围与现金性质调整算式→模型字段及金额（或模型外现金表）`，区分原披露、推导和假设。按[会计参考第3—4节](accounting-and-audit.md#3-四张报表附注及比较期重建)取齐相关附注组成项，再核下列连接；数值可计算不等于原科目符合字段定义。未接通部分在该桥说明具体影响，`source`引用对应项，不把整组未知参数统称为“年报披露及推导”。

| 连接 | 实际取数与处理 |
|---|---|
| 历史期末→预测期初 | 前瞻从最近可用的同范围实际期末接起，列会计现金→本次法人可动用现金及应收/存货/应付/债务调整。已有季度实际时，先取收入、成本、现金capex、借款流入、债券流入及还本，各已知行保存`剩余=全年设定−累计实际`的计算引用和剩余窗口；毛融资与净融资分开。范围可比的行先完成，其他字段缺口不阻止已知行分析。负的剩余毛融资不能作为未来新融资或补成零：修订全年设定、澄清融资类别，或明确保留为与实际不一致的反事实。完成这张桥后才生成企业修正版输入；历史拟合另列实际、模型和逐项差额，未解释差额不当未来现金下限，反事实路径不能替代已知实际期初。 |
| 业务量价、成本费用→模型字段 | 收入、完整销售成本与销量按第1节对齐产品集合，其他业务另接；集团总额除主业销量须明确为代理。按附注明细列`现金经营费用基数=营业成本以外的经营期间费用−其中折旧摊销−其他非现金项目`，已由利息字段或其他收付桥处理的项目先从该基数排除；财务费用明细按性质接入相应字段或现金桥，不把净额整体并入固定现金费用。在无付款时差简化下接入`fixed_cash_cost`，存在时差则另接应付/预付现金桥。同时列`损益总折旧摊销=销售成本内折旧摊销+期间费用折旧摊销`，调整这两个字段时联合复算，不能从分类错误直接推断现金差额。存货内折旧摊销按期末存量减期初存量，净变动可负；两端存量及本期生产折旧另受可行范围约束，总折旧/总成本率不识别存货折旧率。 |
| 累计披露→季度季节性 | 先按[同控、非同控与处置范围桥](accounting-and-audit.md#10-集团收购和合并抵销)逐项统一H1与Q1等累计输入，再作差分；同范围净CFO可核不等于毛收付款已可比。未完成范围桥的跨范围原报差分只能保留为混合范围观察；若用作预测代理，须明示范围调整假设，不能标成同范围实际。 |
| 经营付款→资本付款 | 按[成本、采购及资本投入桥](accounting-and-audit.md#43-成本到采购再到供应商付款)拆齐贸易、工程设备、供应商融资及其他应付，再选择DPO范围。若`capex`已是现金购建支出，核其中旧应付结算与当期付款，不把期初资本应付再加一次；若从资产新增推导，先剔除租赁、并表等不经该应付/预付结算的新增，再以同范围购建发生额减资本应付增加、加资本预付增加，并调节汇兑、重分类等变动。同一付款只入一条现金桥；账龄不替代合同付款日。重大模型外票据、预收及预计负债另列结算时点和现金影响。 |
| 其他收付→损益或周转 | 先用附注拆开利息、补助等损益型收付与保证金、备用金、往来回收。保留未来收款时，对应未来收益、递延项目或已有应收的结算；假设只是收回期初款项，应有可用余额和时点依据。剔除未来收益时不能继续保留同一新增收益收现。未分配周转残差不能自动吸收已可从公开附注识别的损益遗漏；资产负债表平衡不证明收款机制成立。 |
| 所得税费用→现金税 | 按纳税主体、税区和抵扣规则拆出当期税与递延税，并列`所得税支付=期初应交+当期计提+其他净增加−期末应交`，另衔接预缴、退税及非损益变动；“支付各项税费”须拆税种。用此桥选择现金税假设或有据分支；总费用率、当期费用率都不自动等于实付税率。合并亏损不表示各纳税主体现金税为零；`max(合并税前利润,0)×税率`只在相应简化成立时使用，无法接入的税款时点另列现金表，不以资产残差补平，也不重复扣已含所得税。 |
| 合同到期→本金和融资 | 按[债务口径桥](corporate-credit.md#3-报表到信用口径逐笔财务调整桥)先核同类义务在总债务及到期部分的一致处理，再将短期及一年内到期义务核到逐期还本；差额对应已偿、改期、续借或未解决。同时分列`评级债务范围→杠杆`与`付息本金×利率×实际计息期间→现金利息`；本模型单一`debt`驱动两者，扩大范围时逐期验证付息本金、利率及已偿/续借，给有据混合率或明确利息分支。仅首期等息的固定混合率不能称所有期间等息，也不能默认新增信用债务全按原利率计息。续借表现为原债偿还与新融资，分别标注已承诺/假设及现金时点；`drawdown>0`不能描述为“没有融资假设”。重要期中支付需细分期间或另做时点表。 |
| 现金余额→运营余量 | 按工资、采购、税费的付款日历与收款间隔确定覆盖天数和缓冲；需求构造剔除非现金费用，不另加已含在成本中的同笔人工。保证金或非现金等价物不是需求代理。阈值用于`现金余量=期末现金−阈值`，不是现金流出；没有需求依据时只给输入阈值的数学敏感性，不称公司安全边界。 |

**起点构造例。** 已知实际年末现金100，同年模型拟合75，差额25尚未解释；下一年正式预测从经范围核验的100接起，历史差额仍保留待解释。可以另展示从75接续的反事实路径，但较低起点不证明整个模型保守：若同时漏了40到期本金，所谓下限仍可能高估可用现金。收入/销量、成本内折旧、内部生产现金等每项假设都须独立说明，算术闭合不消除这些经济缺口。

**毛收付构造例。** 假设只有经营收款和付款：Q1原报100/90，同范围重述为120/110，两版CFO均为10；H1同范围为300/260。混合相减得到Q2收付200/170，正确同范围为180/150，净额虽都为30，季节性毛额却不同。以后期收款按历史0.9倍、付款不变外推，前者预测CFO为10，后者为12。净额碰巧闭合不能替代分项口径核验。

**将范围未知传到判断。** 将每个未确定的范围差ΔX与对应期间、抵销关系和证据约束列明；已知净CFO差只约束各分项带符号之和，不令每项为零，也不能用期初现金差替代。能据组成部分披露或台账界定上下界时，按可同时成立的组合重算季度毛流量、季节性、预测现金和评级同定义输入；零调整仅是明示参照假设。固定外推系数下，收款/付款范围调整ΔR、ΔP对该期预测CFO的影响为`α×ΔR−β×ΔP`；若系数或季节性份额也随口径改变，须重算完整模型，不能套此线性式。

将口径未知与经营恶化分别展示。若有依据的范围跨越最低现金、实际付款覆盖或所选评级方法的因素边界，明确会改变哪项预测、因素档或评级成立条件，并索取对应期间的组成部分现金流及抵销明细；没有可辩护边界时不报该代理的精确压力余量或唯一档位，仍可继续已核同范围净额、实际现金和合同期限分析。范围内结果一致时，只说明结论对已检验范围稳健，不能据此证明毛收付款真实可比。

**把已知累计接入运行。** 先在共同底稿用 `sum/difference` 保存累计组成与`期间总额−累计实际`，再从同一 `evaluate` 结果填入情景的 `realized`，不要另抄一组数字。每行含 `period_index`、`through_date`、`metric`、`value`、`source`、`available_at`、`same_scope`；金额沿该 scenario 的 entity/currency/amount_scale。累计日期位于对应 Period 内且不晚于 `as_of`；非空可得日满足 `through_date≤available_at≤as_of`。`metric` 仅支持模型已有的 revenue、cost_of_sales、capex、drawdown、principal、dividends，不能把净CFO或混合分红/利息行塞进毛额字段。`same_scope=true` 是调用者依据原件所作的范围声明，不是脚本已核验；未取证值或可用日期可为null，未确认范围保持false。每个 Period 选一个累计终点、同一指标一行；其他终点的单行差额仍可在基础底稿保存，但不能拼成同一个剩余现金期间。

对已取证、声明同范围且日期可用的累计量，`scenarios.run` 在投影或逆向前比较其与原期间总额。默认 `path_basis="forward"` 遇到模型非负项目的负剩余会报出具体项目、总额、实际和差额；修订设定/范围后再运行。原样数学复现明确设置 `path_basis="counterfactual"`，可以保留原路径，同时自动保存 `actual_bridge` 和具体冲突限制。逆向搜索的每个已评估候选及最终根按变更后的期间总额复核；forward遇到冲突候选即拒绝本次搜索，不自动裁剪区间。counterfactual另存冲突候选和最终根的桥及限制；`not_bracketed`（未括住根）或 `not_identified`（未建立唯一边界）时仍保留已评估冲突。未提供或未取证的累计项目保持缺口，不补零；各已知行的基础差额仍继续完成。

`actual_bridge` 只比较累计与所给期间总额，不重置现金起点、不把剩余金额倒造成销量/单价，也不自动构建剩余 Period。真实企业剩余预测须另取累计终点的同范围开局状态，同时更新 opening 的 date、cash、receivables、inventory、payables、debt，设置下一日起的 Period，并消费已核剩余 capex/drawdown/principal/dividends及经营驱动。已消费的累计数保留在原桥，不再放进新 Period 的 realized。累计终点早于信息截止日时，中间经过期间仍需实际或明确估计，不能把全年减Q1直接叫作下半年预测。原样复现、尚未衔接的全年条件路径和真实剩余预测分别命名；数值闭合不关闭这项期间缺口。

### 完整的构造输入示例

以下数据只用于解释和复算，不能充当真实企业证据。金额单位为百万元；单位售价和单位完整销售成本同样按百万元/数量单位填写。`source`须写可定位的实际资料/假设说明，`available_at`为该资料当时可得日期，不能填成今天的下载日来替代历史公开日。

```json
{
  "entity": "构造工业企业",
  "as_of": "2024-12-31",
  "currency": "CNY",
  "amount_scale": 1000000,
  "interest_basis_days": 365,
  "payables_denominator": "cost_of_sales",
  "opening": {
    "date": "2024-12-31", "cash": 80, "receivables": 100,
    "inventory": 60, "payables": 60, "debt": 200,
    "source": "构造起点；实际项目须链接期初余额证据",
    "available_at": "2024-12-31"
  },
  "minimum_cash": {
    "value": 20, "source": "构造最低运营现金假设，不是法律违约标准",
    "available_at": "2024-12-31"
  },
  "periods": [{
    "start": "2025-01-01", "end": "2025-12-31",
    "volume": 1000, "unit_price": 1, "unit_cost_of_sales": 0.6,
    "fixed_cash_cost": 250, "depreciation": 30, "capex": 40,
    "depreciation_in_cost_of_sales": 0,
    "inventory_cash_conversion": 0, "inventory_depreciation_change": 0,
    "tax_rate": 0.25, "dso": 36.5, "dio": 36.5, "dpo": 36.5,
    "interest_rate": 0.05, "drawdown": 0, "principal": 100, "dividends": 20,
    "source": "构造预算：存货全由供应商投入形成，无内部生产现金投入、存货内折旧摊销；30折旧摊销全为营业成本外期间费用。实际假设逐项在底稿解释",
    "available_at": "2024-12-31"
  }],
  "contracts": [{
    "label": "构造现金测试", "definition": "测试日期的模型现金不少于20",
    "test_date": "2025-12-31", "metric": "cash_end",
    "relation": "at_least", "threshold": 20,
    "source": "构造合同条款；实际项目引用条款及口径",
    "available_at": "2024-12-31"
  }],
  "reverse": {
    "period_index": 0, "driver": "dso", "bounds": [36.5, 60],
    "test_date": "2025-12-31", "target_cash": 20,
    "definition": "求本期期末现金等于20的DSO条件边界",
    "source": "构造逆向压力目标", "available_at": "2024-12-31"
  }
}
```

`contracts`及`reverse`可以省略。其他模型输入不得用缺失值静默补零。零融资、零分红和零资本开支都是明确输入假设。相邻预测期间必须连续，且紧接期初日；此模型接受自定义期间，但利率按实际天数计息。

`unit_cost_of_sales`是含分配折旧摊销的完整单位销售成本，不是单位变动成本；`fixed_cash_cost`只包括未进入营业成本的其他固定现金期间费用。`depreciation`为损益确认的总折旧摊销，`depreciation_in_cost_of_sales`为其中已经计入营业成本的部分，不能再次扣减利润。`inventory_cash_conversion`为本期加入存货的内部生产人工等现金投入；外购加工仍属供应商采购。`inventory_depreciation_change`为期末存货内含折旧摊销减期初内含金额，允许负值。后三项分解均必填，零必须有明确假设；不得以现金目标反推补平，也不能从资料缺失推定为零。

**由底稿结果填写输入。** 上例可在共同底稿按下表展开费用与折旧字段。六项事实都标 `state="assumption"`，采用相同构造主体、范围、2025年期间和人民币百万元 context；构造来源不能标成公司已披露事实。事实、计算及证据字段按 [workpaper.md](workpaper.md) 完整填写。其余驱动仍是上例已经逐项说明的构造假设，这里只展开费用、折旧与存货投入连接。

| 记录 ID | 构造假设或计算（百万元） |
|---|---|
| period_expenses | 营业成本外经营期间费用280，包含期间费用折旧；不含利息、所得税、资本化支出或其他现金表项目；无付款时差 |
| period_da | 其中折旧摊销30，本例全部损益折旧计入期间费用 |
| other_noncash | 其他非现金费用0，是本例明示假设 |
| total_da | 同范围损益总折旧摊销30 |
| internal_production_cash | 本期加入存货的内部生产现金投入0；本例存货全由供应商投入形成 |
| inventory_da_change | 存货内含折旧摊销净变化0；本例期初期末存货均不含折旧摊销 |
| cash_period_expenses | `sum`：period_expenses − period_da − other_noncash |
| da_in_cost | `difference`：total_da − period_da |

以下片段承接已经建立上述记录的 `Workpaper` 对象 `w`；`input_data` 是上面的完整构造 JSON 字典，`budget_terms` 是记录这些构造前提的已有 evidence ID。按工作底稿运行说明，从技能目录的 scripts 导入现有模块，输出目录设为用户任务目录。片段不是独立建稿程序，不会自动把财报内容变成假设。

```python
from copy import deepcopy
from decimal import Decimal
from calculate import evaluate
from workpaper import Workpaper
import scenarios

calculated = evaluate(w)
values = {f.id: f.value * f.context.scale if f.value is not None else None
          for f in w.facts}
values.update({r["id"]: Decimal(r["normalized"]) if r["normalized"] is not None else None
               for r in calculated["calculations"]})
field_refs = {
    "fixed_cash_cost": "cash_period_expenses",
    "depreciation_in_cost_of_sales": "da_in_cost",
    "depreciation": "total_da",
    "inventory_cash_conversion": "internal_production_cash",
    "inventory_depreciation_change": "inventory_da_change",
}
scenario = deepcopy(input_data)
for field, ref in field_refs.items():
    # evaluate返回基础货币金额，模型使用amount_scale指定的金额单位。
    scenario["periods"][0][field] = float(values[ref] / Decimal(str(scenario["amount_scale"])))
scenario["periods"][0]["source"] = (
    "其余驱动沿用上例构造假设；费用、折旧与存货投入见底稿budget_terms；字段桥："
    + repr(field_refs)
)
result = scenarios.run(scenario)
record = scenarios.to_workpaper_result(
    result, id="cash_scenario", label="构造经营现金情景",
    input_refs=list(field_refs.values()), evidence=["budget_terms"],
)
data = w.model_dump(mode="json")
data["quantitative"] = [q for q in data["quantitative"] if q["id"] != record["id"]] + [record]
w = Workpaper.model_validate(data)
```

现金费用得到250，成本内折旧得到0，原例期末现金仍为32.5。若把期间费用内折旧假设改为20、总折旧保持30，同步更新该分支的事实说明及 `budget_terms`，重新计算会同时得到现金费用260和成本内折旧10。本例费用总额、完整销售成本及其他驱动固定，现金经营期间费用增加10与模型供应商付款减少10相互抵销，现金仍为32.5；这不是实际会计重分类的证明。只改一个模型字段，会破坏这组底稿输入与模型的一致性。实际企业的期间费用变化还须核对其他非现金项目和付款时差，不因本构造结果相同就推定真实现金无影响。

**缺失对照。** 另建一份未完成底稿，将 `other_noncash` 改成 `value=null, state="missing"`，注明该组成尚未取得，并移除该分支 `quantitative` 中原有的 `cash_scenario` 结果。对它调用 `evaluate` 后，`cash_period_expenses` 为 `not_calculated/null`，`da_in_cost` 仍为0。继续交付已核费用、折旧与待补事项；这个分支不调用上面的字段赋值和情景运行，不沿用已完成分支的250或现金32.5。取得非现金项目和付款时差，或取得可辩护的假设范围后，再建立完整条件输入分别运行。

### 方程、时序和口径

对每一期，以实际包含的日历天数D计算：

```text
Revenue = volume × unit_price
Cost = volume × unit_cost_of_sales
EBITDA = Revenue - Cost + depreciation_in_cost_of_sales - fixed_cash_cost
EBIT = EBITDA - depreciation
Interest = opening_debt × interest_rate × D / interest_basis_days
Cash_tax = max(EBIT - Interest, 0) × tax_rate
Net_income = EBIT - Interest - Cash_tax
AR_end = Revenue × DSO / D
Inventory_end = Cost × DIO / D
Production_depreciation = depreciation_in_cost_of_sales + inventory_depreciation_change
Purchases = Cost + Inventory_end - Inventory_begin - inventory_cash_conversion - Production_depreciation
AP_end = selected_payables_denominator × DPO / D
Customer_collections = AR_begin + Revenue - AR_end
Supplier_payments = AP_begin + Purchases - AP_end
NWC_end = AR_end + Inventory_end - AP_end
CFO = Net_income + depreciation + inventory_depreciation_change - (NWC_end - NWC_begin)
Cash_end = Cash_begin + CFO - capex + drawdown - principal - dividends
Debt_end = Debt_begin + drawdown - principal
```

`payables_denominator`必须明确选`cost_of_sales`（完整营业成本代理，不等于采购）或`purchases`（库存滚动剔除内部现金投入及本期生产折旧摊销后的供应商采购）。存货余额由完整营业成本与DIO预测；应付余额则使用另行选定的分母与DPO，两者不能混作同一种周转假设。`dso/dio/dpo`是期末余额代理天数，不是平均余额周转天数。CFO加回库存内含折旧摊销的净变化，以免非现金资本化进入现金耗用；它已经扣了利息和现金税，现金瀑布不得再次扣息。

明确的简化是：全部模型收入使用应收天数代理；利息按期初债务在整期计息，提款和偿还本金在期末发生；无递延税、亏损结转、即时亏损退税、并购、汇兑、资产出售或季节性。需要这些因素时，先用单独有证据的工作底稿扩展经济模型，不能在输入中塞入一个无定义的补平额。该脚本不是完整资产负债表预测。

内部生产现金投入在本期支付，无应付薪酬变化；存货无折旧摊销以外的非现金变化。供应商采购和应付只涵盖存货投入，无增值税、预付款、资本性应付及供应商非现金结算。若实际企业不满足这些简化，先补相应明细桥，不能将混合应付余额直接塞入DPO。营业成本内折旧摊销不得超过营业成本或损益总折旧摊销；推导的本期生产折旧摊销和供应商采购不得为负。

在这些简化下，模型客户收款和供应商付款均不能为负：期末应收不得超过期初应收加本期收入，期末应付不得超过期初应付加供应商采购，即使用营业成本作为DPO代理分母也一样。逐期保留两项收付款以核对直接现金桥；逆向求解的区间也须满足这些条件。脚本仅容纳浮点运算的微小误差，不将不可能的应付增长解释成融资来源，也不默默压低周转天数。真实退款、退货、预收预付或非现金变动需要另建明细桥，不能用本模型的负收付款代替。

**构造反例。** 90天内收入100、供应商采购60，期初应收和应付均为零；DSO=0、DPO=120会推得应付80和付款−20，错误地使CFO变成120。该路径不成立，延迟全部60采购款也只能保留100销售收款。改为DSO=DPO=90时，两项收付款均为零；下一期还须承接应收100、应付60，不能每期重新使用零期初。

存货内含折旧摊销余额的可行区间从`[0,期初总存货]`开始，每期加上`inventory_depreciation_change`后与`[0,期末总存货]`取交集，并沿期间保留；空集即拒绝该路径。这只是必要可行性条件，不识别实际期初折旧摊销余额，也不证明全部存货成本构成真实。

Excel现金表同时列出客户收款、供应商付款和存货内含折旧摊销的可行区间。修改数字驱动后，负收付款或跨期区间为空会使现金路径返回`#N/A`及`infeasible_cash_path`，相关合同指标不再判为通过；恢复合法输入后可重新计算。金额只是浮点尾差时采用与脚本相同的数值处理，不把机器精度容差解释为财务重要性。

模型只使用输入的融资金额，绝不自动补现金。`cash_end<0`代表未融资缺口，该期保留计算，后续期停止并计入`unprojected_periods`；必须先解释资金方案才能继续。`funding_needed_to_floor`只表示补到输入最低现金需要的金额，不表示可取得的授信。已经低于最低运营现金但仍非负的期间会继续计算，并明确标记`below_cash_floor`。

### 合同与逆向边界

合同条件包含自己的定义、来源、日期、指标、关系和阈值；没有默认行业或评级阈值。可测试`cash_end/debt_end/ebitda/interest_coverage/debt_to_ebitda`，其中利息覆盖=`EBIT/Interest`，杠杆=`期末Debt/本期EBITDA`，分别要求利息或EBITDA为正。必须确认这恰好是合同定义；若合同使用不同允许加回或净债务定义，不得冒称完成合同测试。测试日没有预测值时为`not_tested`；结果`outside_input_threshold`本身不等于法律违约。

逆向压力只解决一个有经济含义的标量问题：在指定期间改变`volume/unit_price/unit_cost_of_sales/fixed_cash_cost/dso/dio/dpo`之一，使指定期末现金等于输入目标。调用SciPy的Brent求根，需提供经济可行的上下界；无异号时返回`not_bracketed`，不扩大边界到任意数值求出答案。若更早现金断裂导致目标期不可预测，不能继续假定正常经营求根。[SciPy求根要求](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.root_scalar.html)

逆向结果保存根、现金残差、区间端点残差和根处的整条现金/债务路径。它是条件边界，不是违约概率、置信区间或“最可能”情景。

**先失守的条件可能不是现金。** 构造一条价格下降路径，期末现金`C=100+2p`、EBITDA`E=10p−100`、债务90；分析者设现金至少120、债务/EBITDA至多3。这些是本例输入条件，不是合同或机构阈值。从p=20向下，杠杆在p=13先触线，此时E=30、C=126；现金根p=10处E=0，杠杆已不可计算。不能将现金根称为所有条件下的承受边界。求得根时，检查`reverse.contracts`中各已设测试日的条件和`reverse.rows`中的不可计算项，并沿同一驱动另行查明哪项已设条件先失守；`not_tested`不代表通过。每个结果保留测试日和条件性质，年度期末现金不表示年内最低现金。

两端现金都在货币运算的浮点精度内达到目标时，返回`not_identified`并保留原始残差，不能把尾差异号当作唯一压力边界。求解金额型驱动时，Brent的绝对终止容差取最小正浮点数，避免仅换金额单位就提前停在错误端点；相对精度仍按求根库处理。数值精度不替代最低运营现金、财务重要性或经济可行性判断。[SciPy终止条件](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.brentq.html)

### 独立复算基准

上述构造数据得EBITDA150、净利润82.5、CFO112.5、期末现金32.5和债务100。仅将`volume`改为900、`dso`改为46.5，采用成本代理DPO时，净利润仍为52.5，但现金为−12.157534，需要32.157534才能达到最低现金20。若改为采购口径DPO，应付为53.4而非54，现金进一步变为−12.757534；这是口径差异的实际现金影响。

保持其他驱动不变，DSO增加到41.0625天时现金恰好为20；略高应低于目标，略低应高于目标。两期例子还需检查第二期利息基于第一期期末债务，而不是每年重复使用初始债务。

制造人工反例：期初库存50+供应商采购100+内部生产工资30−营业成本120=期末60。全年销售收现200，期初应付30，采购口径DPO146天，则期末应付40、供应商付款90；直接CFO=200−90−30=80，期初现金20得到期末100。`Cost+ΔInventory=130`是生产总投入，不能叫采购。改用相同天数的完整成本代理会得到应付48、现金108，必须明确这是另一项代理假设。

含折旧摊销的制造反例：完整营业成本120含损益折旧摊销30，无其他损益折旧摊销；供应商采购100、内部生产现金投入20、期初库存50。若存货内含折旧摊销净增加10，则本期生产折旧摊销40、期末库存90；若净减少10，则本期生产折旧摊销20、期末库存70。两例销售收现200、期初/期末应付30/40，均应得到EBITDA110、净利润80、CFO90和期末现金110，等于直接法`200−90−20`；不能在完整营业成本之后再重复扣其中的30。

### 历史版本边界

`operating_cash_scenario_v1`的`Cost+ΔInventory`采购桥不能证明一般制造企业的供应商采购，算术或Excel重算一致也不能消除这个错误。当前脚本只实现v2，不提供自动兼容计算：旧`unit_variable_cost`输入与缺少三项分解的输入会被拒绝，当前导出器也拒绝v1现金artifact。应根据原始资料补齐成本分解后重新计算，不能只改方法版本标签。

迁移时另建v2输入及结果，先补齐有来源的完整单位销售成本、营业成本内折旧摊销、内部生产现金投入和存货内含折旧摊销净变化，再复算。不得仅改method标识或把缺失分解填零；旧版与新版的假设及结果分别保留。

## 3. 点时同业及一项样本外预测

调用 `scripts/panel.py`，或 `panel.run(input_dict)`：

```text
python scripts/panel.py panel-input.json --output panel-result.json
```

依赖pydantic和NumPy。此具体功能只处理365/366天完整年度，不接受季度、累计期间、52/53周制或stub period；不要通过改日期伪装可比。若数据不满足，保留确定性分析并明确此研究不适用。

### 输入

顶层字段为`as_of`、`training_cutoff`、`peer_period_end`、`industry`、`accounting_basis`、`currency`、`universe_definition`、`records`。两个截断时间须含时区，训练截止早于研究截止。同业定义和退市覆盖由资料提供者明确，脚本不能补出从未提供的公司。

每一条记录是**一个企业一个完整年度在一个公开版本下的原子快照**，字段如下。若不同科目来自不同发布时刻，应先在底稿构造满足可用时点的快照，不得将后公开的资产提前到更早收入公告日。

```json
{
  "id": "issuer-2023-original", "entity": "issuer",
  "period_start": "2023-01-01", "period_end": "2023-12-31",
  "available_at": "2024-03-01T10:00:00+08:00", "version": "original",
  "industry": "industrial", "accounting_basis": "specified-GAAP", "currency": "CNY",
  "revenue": 100, "cost_of_sales": 60, "total_assets": 200,
  "source": "公告文件及收入、成本、资产所在位置"
}
```

金额在同一条记录内须同币种同缩放；比率不依赖所选金额单位。数值缺失使用null，保留缺失。每次修订追加新记录和真实`available_at`，不能覆盖旧记录或只改版本名。相同企业/期末/公开时间存在两个版本会被拒绝，因为无法判定先后。

### 选取、特征与验证

1. 当前同业先对企业×期末选择`available_at<=as_of`的最后版本，再按指定期末/行业/准则/币种筛选。避免先用旧行业分类筛选而保留已经变更口径的旧版本。
2. 特征为`gross_margin=(revenue-cost)/revenue`和`gross_profit_to_assets=(revenue-cost)/期末资产`。收入或资产的必要分母非正时，相应值不可计算；负毛利保留。后者是毛利资产特征，不能与使用平均资产的其他版本混称。[Novy-Marx研究](https://www.nber.org/papers/w15940)
3. 同业百分位采用平均名次/N，显示有效样本数；它只是输入集合的描述，不证明统计可靠性。
4. 历史预测特征及下一完整年度目标，都使用各期**首次公开版本**。只有下一期现金/利润事实实际公开后，才算标签成熟；此实现目标为下一期毛利率。后续修订不会回填历史起点。
5. 训练样本必须在`training_cutoff`前同时公开特征与标签。测试起点必须晚于训练截止，目标须在`as_of`前公开。起点早于截止但标签未成熟的记录不参与训练，也不伪装为纯时间外留出；目标在起点前已经公开的迟报记录不用于预测验证。
6. 拟合唯一预先确定的模型：`next_margin=intercept+slope×current_margin`。使用NumPy现成最小二乘。至少三对成熟样本且设计矩阵秩为2，只表示可估计与存在剩余自由度，不表示样本可靠。
7. 冻结训练参数后，输出测试逐行预测、实际值、last-value基准，以及两者测试MAE。不调参、不截断预测、不报告训练“准确率”、PD、因果系数或因子收益。没有成熟测试结果时，MAE为null并标记`no_matured_holdout`。

每行特征和目标保留对应记录ID及公开时间。`training_pairs/pending_outcomes/excluded_pairs`解释样本流向。输入快照可保留尚未使用的未来版本以便重跑不同截断，但结果只使用对应时点允许的信息；来源与输出证据不能引用未使用的未来记录。

### 独立统计反例

用三对构造训练数据`0.10→0.15、0.20→0.20、0.30→0.25`，唯一线性关系为`y=0.1+0.5x`。第四个企业在训练截止后首次公告`x=0.4`，下一年首次公告`y=0.3`；应预测0.3，留出MAE为0，last-value基准MAE为0.1。这只是验证数学和时点处理的构造数据，不是真实经验效果。

若第四个企业以后将旧年度毛利率重述为0.9，当前同业可以显示0.9，但历史预测仍须使用0.4；若重述还晚于`as_of`，当前同业也不可使用。若下一年度尚未公开，不能把误差写零。只剩两对训练样本时，不估计模型。这些失败路径比对同一实现公式重新抄一遍的测试更有价值。

## 4. 进入共同底稿与导出

两个模块提供相同的适配函数：

```python
result = scenarios.run(input_data)  # 或 panel.run(input_data)
record = scenarios.to_workpaper_result(
    result, id="cash-stress", label="经营现金压力",
    input_refs=["opening-cash", "opening-debt"],
    evidence=["budget-assumptions", "debt-terms"]
)
```

将record加入共同Workpaper的`quantitative`列表。输入引用应覆盖实际采用的底稿数值/计算；evidence应覆盖假设、样本来源和合同，不可仅放一个泛泛报告链接。适配器不自行创造证据，也不把结果插成`reported`财务事实。

记录包括`method/as_of/input_refs/evidence/assumptions/limitations/artifact`。artifact保留完整输入快照、所有计算行、模型版本及逆向/验证明细；对`run(artifact["input_snapshot"])`的重新运行应复现结果。导出应展示金额、计算定义、假设和限制，同时保存完整artifact。若读者修改工作簿中的模型输入，应重新运行该模块并更新artifact；除非导出层实际实现了重新计算，不得声称静态单元格会自动更新这些高级计算。

## 5. 解释与不确定性的必要边界

- 行业、会计口径和样本周期先于模型。不能拿景气顶峰的资源企业、扩产期公用事业和轻资产软件做同一无条件排行；银行与保险必须按其风险结构分析。
- 采用相同国家/准则也不能消除并购、产品组合、存量会计估计和业务模式差异。异常残差有竞争解释；不把Beneish、F-score或字母评级直接映射成舞弊/违约概率。
- 当前脚本的OLS留出误差只是描述。要声称统计泛化，仍需多公司、多期和不同周期，按发行人/时间依赖选择推断方法，保留失败样本与退市样本，处理缺失和多重尝试。三对样本只是算术演示。
- Dechow–Dichev型应计模型含下一期CFO，完整残差不能在该CFO公开前作为当前可交易特征。真正投资回测另需股本、公司行动、退市收益、可交易性和成本。
- 概率模型需要实际事件定义、期限、删失/竞争风险、独立校准和样本外检查；排序好不等于PD校准好。[scikit-learn概率校准](https://scikit-learn.org/stable/modules/calibration.html)
- 情景假设范围不是置信区间；根求解收敛不是经济真实性；脚本测试通过不等于分析方法已获专业验证。

相关验证位于仓库`tests/test_quantitative.py`。只运行与本次变动有关的数值/PIT/CLI反例；不要为基础算术引入模型治理平台、审批流程或多层门禁。
