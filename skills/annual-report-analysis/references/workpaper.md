# 同一底稿生成三份成果

需要可复算数字和文件导出时读取。底稿是已完成研究的记录，不是把年报丢给脚本就能自动判读的工具。模型须先按任务方法取证、形成解释，再用脚本计算。

## 运行

Python 3.11+，Node 18+。用宿主提供的解释器或任务虚拟环境安装本 skill 的 `requirements.txt`；在可写的 skill 副本目录运行 `npm install` 安装 `package.json` 中的 PptxGenJS。不要往托管插件缓存安装。宿主已有依赖可以直接使用。

```bash
python /path/to/skill/scripts/extract_pdf.py annual-report.pdf --output /task/pages.json
python /path/to/skill/scripts/extract_pdf.py annual-report.pdf --pages 111 112 113 --output /task/selected-pages.json
python /path/to/skill/scripts/export.py /task/workpaper.json --output /task/deliverables
```

Node 不在 PATH 时给 `--node /absolute/path/to/node`。运行结果列未计算记录；查看 `results.json` 中具体原因，判断应补输入、改口径还是保留不适用。不要为了通过校验而改写事实。

产物：`report.docx`、`workbook.xlsx`、`presentation.pptx`；另保存 `workpaper.json`、`results.json`、用于 PPT 的同源数据及 `manifest.json` 文件校验值。量化模型原始输入快照及结果保存在 `quantitative-记录ID.json`。本地文件生成不会发布或外传资料。

## 数据契约

完整字段以 `scripts/workpaper.py` 的 Pydantic 定义为准；可用 `Workpaper.model_json_schema()` 查看机器模式。ID 在整份底稿中唯一，数值用十进制字符串，未知值用 `null`。不使用 `NaN`、空字符串或零代替缺失。

| 记录 | 实际用途 |
|---|---|
| mandate | 标题、实体、行业、目的、期间、资料截止日、准则、范围、语言、版本、方法版本和任务限制 |
| sources | 文件/网页 ID、标题、正式 URL 或上传文件路径、公布日期（未核验填 null）、availability_note 时间依据与限制，PDF 的 SHA256 |
| evidence | 来源 ID、PDF 页码及印刷页/附注/表/行、实际观察与可靠性限制；文字事实也在此保存 |
| facts | 原始科目、统一概念名、原值、context、证据 IDs；reported/restated/assumption/missing 状态和调整或缺失说明 |
| calculations | 引用事实或前序计算的确定性运算、结果口径、定义、经济解释边界；禁止直接提供计算结果 |
| reconciliations | 实际与目标的引用、基础单位容差及其来源；残差始终公开 |
| findings | 决策问题、结论、机制、支持证据和反证、竞争解释、结论改变条件；supported/conditional/unresolved |
| procedures | 目的、事项、认定、总体、选取、可重做步骤、状态、实际结果及证据、执行人和日期 |
| requests | 具体所需资料、结论影响、责任角色、关闭条件 |
| sections | Word/PPT 主题和引用的 findings/figures；此处不再填第二套数值 |
| quantitative | 场景/面板/回收脚本结果，输入事实和证据、假设、限制、方法、截至日及含输入快照的 artifact |

`performed` 程序必须有本次真实执行者、日期和结果证据；不能填写原审计师名称来表示本次执行。缺资料时用 `awaiting_data`，已做但证据不足用 `limited`，纯计划用 `planned`。程序的字段完整不能证明证据充分，结论仍按专业方法评估。

上传文件没有精确公告日期时，`sources.published=null`，在 `availability_note` 记录已知信息；批准报出日、审计签署日和封面月份不能代替公告日。导出器会保留时间未核验限制，不阻止当前内容分析，也不能因此声称历史时点可用性已验证。时点研究仍需取得真实公告证据；`panel.py` 的可用时间不允许用占位日期填充。

每个事实/计算的 `context` 包含：

```json
{
  "entity": "示例企业集团",
  "scope": "consolidated",
  "start": "2025-01-01",
  "end": "2025-12-31",
  "aggregation": "flow",
  "basis": "CAS",
  "measure": "money",
  "currency": "CNY",
  "scale": "1000"
}
```

余额 `aggregation=instant` 且 `start=null`。实际期间均值 `average`、比率 `ratio`、情景驱动 `assumption` 单独标识。`measure` 为 money/count/ratio/days；金额必须有币种，其他量纲币种为空，count必须填 `physical_unit`（如GWh、shares）。原披露“17.5%”可以写 `value="17.5", scale="0.01", measure="ratio"`；计算出的比率使用 scale=1。原币种不要猜测，跨币种转换需要单独的已取证汇率/换算底稿。

合并总权益和归母权益、总净利润和归母利润即使同属合并表也具有不同经济概念，须按指标定义选取。程序只检查结构和部分口径一致性，不会代替这种会计判断。母公司使用不同 `scope`，银行监管口径与会计合并口径亦分开。

## 运算和解释

```json
{
  "id": "gross_profit",
  "label": "毛利",
  "op": "difference",
  "terms": [{"ref":"revenue"},{"ref":"cost"}],
  "context": {"entity":"示例企业集团","scope":"consolidated","start":"2025-01-01","end":"2025-12-31","aggregation":"flow","basis":"CAS","measure":"money","currency":"CNY","scale":"1000"},
  "definition": "同范围营业收入减营业成本",
  "interpretation": "毛利变化需要量价结构及成本解释，不等于营业利润",
  "period_rule": "same"
}
```

运算 `sum` 支持各 `terms` 的 `weight`（如 -1），其他运算固定两个输入，顺序分别为被减数/减数、分子/分母、本期/上期、两个真实余额、数量/驱动。`ratio` 分母默认必须为正，确需负数的有意义数学比率设 `denominator=nonzero` 并解释，不能据此给负权益 ROE 正常排名。`growth` 不对亏损基数或盈亏穿越给常规同比。`multiplier` 默认为1，明确周转定义后可使用期间天数，不硬编码全部360或365。

`period_rule`：same 为相同期间；comparison 为本期与上期、相同统计方式和等长期间；rollforward 为期初/本期变动/期末；balance_flow 为同终点的余额及期间流量；forecast 用于显式假设驱动。平均余额专用 `average_balance`，要求同概念、真实期初前一天和期末。规则表示计算所需的关系，不能用 forecast 绕过缺失历史。

原始余额事实仍用 `instant, start=null`。滚动计算需要单独记录运算窗口：例如 `cash_end_rebuilt` 使用 `sum` 引用期初现金及本期经营、投资、筹资、汇率等实际变动，`period_rule=rollforward`，计算 context 为 `aggregation=instant, start=2025-01-01, end=2025-12-31`；这里 start 表示桥的运算窗口，结果仍是期末余额。可将其与 `instant, start=null, end=2025-12-31` 的已披露期末现金勾稽。不要为配合计算去改原始余额事实。

由前序计算得到的余额，可填写 `calculations.concept`（例如 `adjusted_invested_capital`），期初和期末定义必须相同，再用 `average_balance` 引用两项计算。不能把已算出的金额重新标为 reported 事实；concept 只是明确口径，不会证明调整在经济上正确。

金额按 `原值 × scale` 统一到基础单位后计算，结果再除以输出 scale。币种、主体、范围或准则不一致时不计算。跨准则或主体调整先给完整对照及证据；不要为通过脚本擅自改 context。

`reconciliations.tolerance` 采用基础单位：人民币千元披露中容许2千元舍入差写 `2000`，并说明所依据的显示精度、加总行数及运算；审计重要性或净资产百分比不能充当舍入依据。结果 `within_input_tolerance` 仅表示残差未超过输入阈值，不证明该阈值合理、差额确由舍入造成或不存在遗漏。差额不是自动认定错报，超出容差需要逐项查原因，不能靠扩大容差关闭。

Excel 金额残差按两端 Decimal 基础单位结果保留的小数位计算 ROUND（取较细者，至少到基础单位个位），小数位在 Reconciliations J 列公开。该处理只消除二进制算术尾差，不增加容差；例如精确到分的零差额仍为零，真实一分差额仍保留。原始值和计算值不会按单元格显示格式截断。若编辑输入时提高了小数精度，须重跑导出；Excel 的有效数字限制仍存在，高精度结果以 Python Decimal 复算为依据。

结论、程序结果及步骤、资料请求等分析叙述中的动态数值写 `{{gross_profit}}`，导出时自动代入数值和单位；未知 ID 会报错。原文证据不做这种替换。记录 ID 保留在表格及证据链。重要数值不要在自由文本手工复制。各 `evidence`/`counterevidence` 可以引用 evidence、fact、calculation ID；沿计算输入追溯原文。

数字引用自带单位，不再手工追加单位。比率统一显示为百分比；比率之差不是相对增长率，正文须明确比较的是两个比率，不能把百分比差的显示误称为相对增长或在百分号后拼“百分点”。需要说明百分点变化时，可并列两期比率及其增减方向，底稿保留差值计算。

## 模型和复核

`scenarios.py`、`panel.py`、`recovery.py` 各有具体 JSON 输入和 CLI，按对应方法参考执行，再用其 `to_workpaper_result` 适配函数记录实际产物。模型输入快照、计算版本和结果均保留。没有运行不得编写一个看似成功的 artifact；关键结果应独立复算或改变单一假设重新运行。

Excel 中 Facts 的原值和倍数分别保留，基础单位值和指标为公式并含计算缓存。修改数值可供研判；修改主体/币种/期间或方法要重跑脚本，Excel 本身不重新执行语义检查。缺失或被判定不适用的结果用 `#N/A`，不能给正常数值外观。

情景表对数字输入执行与脚本一致的非负、税率区间及正数日数/单位检查（利率允许负数）；清空或填入无效驱动时显示 `invalid_numeric_inputs`，不把空白当零。缺失契约阈值不测试，缺失回收分项不计算合计，缺失或不适用的同业指标不参与自身排名。日期、来源、期间和样本选择仍须重跑相应脚本，不能仅靠Excel编辑重新证明其适用性。

本金偿付超过期初债务与当期提款之和时，期末债务及现金均不可计算，状态为 `not_projected`；当期没有有效现金路径时，各类条件均不测试。已选同业记录补齐有效金额后，相应指标及有效同业数随公式重算；这不会重新选择日期、版本或训练样本。

文件生成成功只说明导出运行。核对 Word 与 PPT 的数字标识、Excel 公式及实际来源；打开并渲染检查表格、字体、分页和幻灯片溢出。审阅者关注核心判断、关键桥和反例，而非只看 JSON 通过或文件数量。
