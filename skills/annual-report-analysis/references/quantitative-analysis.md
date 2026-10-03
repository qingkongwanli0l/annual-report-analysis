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

## 2. 可复算的经营现金情景

调用 `scripts/scenarios.py`，或在Python中调用 `scenarios.run(input_dict)`。当前方法为`operating_cash_scenario_v2`。各情景分别传入完整输入；结果保存原始输入快照、方法版本、假设来源、限制和每期中间金额。改变业务驱动后必须重新运行同一个计算函数。

```text
python scripts/scenarios.py scenario-input.json --output scenario-result.json
```

命令在skill根目录执行。需要pydantic；逆向压力另需SciPy。脚本只读取本地JSON并写指定文件，不启动服务，不联网下载数据。

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
NWC_end = AR_end + Inventory_end - AP_end
CFO = Net_income + depreciation + inventory_depreciation_change - (NWC_end - NWC_begin)
Cash_end = Cash_begin + CFO - capex + drawdown - principal - dividends
Debt_end = Debt_begin + drawdown - principal
```

`payables_denominator`必须明确选`cost_of_sales`（完整营业成本代理，不等于采购）或`purchases`（库存滚动剔除内部现金投入及本期生产折旧摊销后的供应商采购）。存货余额由完整营业成本与DIO预测；应付余额则使用另行选定的分母与DPO，两者不能混作同一种周转假设。`dso/dio/dpo`是期末余额代理天数，不是平均余额周转天数。CFO加回库存内含折旧摊销的净变化，以免非现金资本化进入现金耗用；它已经扣了利息和现金税，现金瀑布不得再次扣息。

明确的简化是：全部模型收入使用应收天数代理；利息按期初债务在整期计息，提款和偿还本金在期末发生；无递延税、亏损结转、即时亏损退税、并购、汇兑、资产出售或季节性。需要这些因素时，先用单独有证据的工作底稿扩展经济模型，不能在输入中塞入一个无定义的补平额。该脚本不是完整资产负债表预测。

内部生产现金投入在本期支付，无应付薪酬变化；存货无折旧摊销以外的非现金变化。供应商采购和应付只涵盖存货投入，无增值税、预付款、资本性应付及供应商非现金结算。若实际企业不满足这些简化，先补相应明细桥，不能将混合应付余额直接塞入DPO。营业成本内折旧摊销不得超过营业成本或损益总折旧摊销；推导的本期生产折旧摊销和供应商采购不得为负。

模型只使用输入的融资金额，绝不自动补现金。`cash_end<0`代表未融资缺口，该期保留计算，后续期停止并计入`unprojected_periods`；必须先解释资金方案才能继续。`funding_needed_to_floor`只表示补到输入最低现金需要的金额，不表示可取得的授信。已经低于最低运营现金但仍非负的期间会继续计算，并明确标记`below_cash_floor`。

### 合同与逆向边界

合同条件包含自己的定义、来源、日期、指标、关系和阈值；没有默认行业或评级阈值。可测试`cash_end/debt_end/ebitda/interest_coverage/debt_to_ebitda`，其中利息覆盖=`EBIT/Interest`，杠杆=`期末Debt/本期EBITDA`，分别要求利息或EBITDA为正。必须确认这恰好是合同定义；若合同使用不同允许加回或净债务定义，不得冒称完成合同测试。测试日没有预测值时为`not_tested`；结果`outside_input_threshold`本身不等于法律违约。

逆向压力只解决一个有经济含义的标量问题：在指定期间改变`volume/unit_price/unit_cost_of_sales/fixed_cash_cost/dso/dio/dpo`之一，使指定期末现金等于输入目标。调用SciPy的Brent求根，需提供经济可行的上下界；无异号时返回`not_bracketed`，不扩大边界到任意数值求出答案。若更早现金断裂导致目标期不可预测，不能继续假定正常经营求根。[SciPy求根要求](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.root_scalar.html)

逆向结果保存根、现金残差、区间端点残差和根处的整条现金/债务路径。它是条件边界，不是违约概率、置信区间或“最可能”情景。

### 独立复算基准

上述构造数据得EBITDA150、净利润82.5、CFO112.5、期末现金32.5和债务100。仅将`volume`改为900、`dso`改为46.5，采用成本代理DPO时，净利润仍为52.5，但现金为−12.157534，需要32.157534才能达到最低现金20。若改为采购口径DPO，应付为53.4而非54，现金进一步变为−12.757534；这是口径差异的实际现金影响。

保持其他驱动不变，DSO增加到41.0625天时现金恰好为20；略高应低于目标，略低应高于目标。两期例子还需检查第二期利息基于第一期期末债务，而不是每年重复使用初始债务。

制造人工反例：期初库存50+供应商采购100+内部生产工资30−营业成本120=期末60。全年销售收现200，期初应付30，采购口径DPO146天，则期末应付40、供应商付款90；直接CFO=200−90−30=80，期初现金20得到期末100。`Cost+ΔInventory=130`是生产总投入，不能叫采购。改用相同天数的完整成本代理会得到应付48、现金108，必须明确这是另一项代理假设。

含折旧摊销的制造反例：完整营业成本120含损益折旧摊销30，无其他损益折旧摊销；供应商采购100、内部生产现金投入20、期初库存50。若存货内含折旧摊销净增加10，则本期生产折旧摊销40、期末库存90；若净减少10，则本期生产折旧摊销20、期末库存70。两例销售收现200、期初/期末应付30/40，均应得到EBITDA110、净利润80、CFO90和期末现金110，等于直接法`200−90−20`；不能在完整营业成本之后再重复扣其中的30。

### 历史版本边界

历史v1中的Cost+ΔInventory不能证明一般制造企业的供应商采购，数值复算一致也不能证明经济口径正确。当前脚本仅实现v2，拒绝旧unit_variable_cost及缺少三项分解输入的任务；当前导出器拒绝v1现金artifact。

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
