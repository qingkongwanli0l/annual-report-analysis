"""Reproduce a bounded historical disclosure example from the public source ledger."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "skills" / "annual-report-analysis" / "scripts"))
import panel
from workpaper import Workpaper


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def main():
    ledger = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    records = ledger["records"]
    limitations = [
        "仅四家事先选定企业，产品结构和合并范围不同；不是全市场样本或完全同质同业。",
        "公告日期来自官方列表，次日零点仅为日级证据的保守边界；没有证明历史精确字节从未替换。",
        "亿纬2022当前官方PDF的生成时间晚于原公告，历史可用时间为空，不纳入时点模型。",
        "2024年保证类质量保证成本重分类造成列报断点；原报告毛利率不等于跨年同口径经营质量。",
        "研究在2026年事后完成，研究者已知部分后期披露；这是固定方法流程演示，不是前瞻注册实验。",
        "留出误差只描述本次样本，不证明预测优势、统计显著性、因果、收益、违约概率或评级。",
    ]
    model_input = dict(as_of="2026-10-02T00:00:00+08:00", training_cutoff="2024-10-02T00:00:00+08:00",
        peer_period_end="2025-12-31", industry="battery-industrial", accounting_basis="CAS", currency="CNY",
        universe_definition="事先选定宁德时代、亿纬锂能、国轩高科、欣旺达2022至2025官方合并披露；只取available_at已核对的记录。不是市场总体。",
        records=[dict(id=r["id"], entity=r["entity"], period_start=r["period_start"], period_end=r["period_end"],
            available_at=r["available_at"], version="own-year-report-current-column",
            industry="battery-industrial", accounting_basis=r["basis"], currency=r["currency"],
            **{k: float(r["facts"][k]["base"]) for k in ("revenue", "cost_of_sales", "total_assets")},
            source=r["pdf"]["url"]) for r in records if r["available_at"]])
    save("panel-input.json", model_input)
    result = panel.run(model_input)
    save("panel-result.json", result)
    workpaper = dict(mandate=dict(title="A股电池企业：原始披露与历史时点验证", entity="四家预选A股电池企业",
        industry="industrial", purpose="演示原文取证、原始版本保留、列报变化识别、固定小样本毛利率模型及可复算交接；不作投资或评级结论。",
        period_start="2022-01-01", period_end="2025-12-31", cutoff="2026-10-02", accounting_basis="CAS",
        scope="各报告当期合并范围", version="real-disclosure-example-v1", methods=[panel.METHOD], limitations=limitations),
        sources=[], evidence=[], facts=[], calculations=[], reconciliations=[], findings=[], procedures=[], requests=[], sections=[], quantitative=[])
    for r in records:
        key = r["id"]
        source, evidence = "s_" + key, "e_" + key
        version_note = "；".join(r["version_limit"]["notes"])
        workpaper["sources"].append(dict(id=source, title=f'{r["entity"]} {r["year"]} 年度报告',
            url=r["pdf"]["url"], published=r["published"] if r["available_at"] else None,
            sha256=r["pdf"]["sha256"], availability_note=f'官方列表日期{r["published"]}；保守可用时点{r["available_at"]}。{version_note}'))
        locators = [f'{f["label"]}：PDF物理页{f["page"]}，{f["column"]}，原单位{f["unit"]}' for f in r["facts"].values()]
        workpaper["evidence"].append(dict(id=evidence, source=source, locator="；".join(locators),
            observation="当年合并表本期数及期末余额；收入、营业成本、资产总计分别取证。官方日期证据与已见重列差异见sources.json。",
            reliability=version_note + "历史可用性与跨期经济可比性仍需分别判断。"))
        if r["year"] == 2024:
            notes = [n for n in r["comparability_notes"] if n["source_report_year"] == 2024]
            pages = sorted({p for n in notes for p in n["pages"]})
            workpaper["evidence"].append(dict(id="p_"+key, source=source, locator=f'PDF物理页{pages}，会计政策变更及比较数',
                observation="；".join(n["note"] for n in notes), reliability="记录已观察重列；未穷尽其他历史修订或证明业务范围恒定。"))
        common = dict(entity=r["entity"], scope="consolidated", end=r["period_end"], basis="CAS")
        for concept, fact in r["facts"].items():
            context = dict(**common, start=None if concept == "total_assets" else r["period_start"],
                aggregation="instant" if concept == "total_assets" else "flow", measure="money", currency="CNY", scale=fact["scale"])
            workpaper["facts"].append(dict(id=f'{key}_{concept}', label=f'{r["entity"]}{r["year"]}{fact["label"]}',
                concept=concept, value=fact["raw"], context=context, evidence=[evidence], state="reported",
                note="原报告当期值。" + ("历史时点版本未核实，仅保留当前内容核查。" if not r["available_at"] else "不以后年比较数回填。")))
        flow = dict(**common, start=r["period_start"], aggregation="flow", measure="money", currency="CNY", scale="1")
        ratio = dict(**common, start=r["period_start"], aggregation="ratio", measure="ratio", currency=None, scale="1")
        workpaper["calculations"].extend([
            dict(id=key+"_gross", label=f'{r["entity"]}{r["year"]}毛利', op="difference",
                terms=[dict(ref=key+"_revenue"), dict(ref=key+"_cost_of_sales")], context=flow,
                definition="当期合并营业收入减营业成本", interpretation="原报告列报口径；成本重分类会改变毛利。"),
            dict(id=key+"_margin", label=f'{r["entity"]}{r["year"]}毛利率', op="ratio",
                terms=[dict(ref=key+"_gross"), dict(ref=key+"_revenue")], context=ratio,
                definition="当期毛利/营业收入", interpretation="不代表同口径经济利润变化或下一年保证。")])
        if r["year"] == 2025:
            workpaper["calculations"].append(dict(id=key+"_gpa", label=f'{r["entity"]}2025毛利/期末资产', op="ratio",
                terms=[dict(ref=key+"_gross"), dict(ref=key+"_total_assets")], context=ratio, period_rule="balance_flow",
                definition="当期毛利/当期期末总资产", interpretation="明确采用期末资产；不是使用平均资产的ROA。"))
    issues = [
        ("vintage", "先核实版本，再划分时间", "历史文件与公告日能否对应？",
         "可用记录按固定截止分割；亿纬2022保留内容但不参与历史模型。日期级官方记录不能证明精确字节的历史可得。",
         "后生成文件若沿用早期公告日，会引入未来信息。", ["e_300014_2022"],
         "取得原始字节版及可验证历史时间后，另立版本重新运行并报告变化。"),
        ("classification", "成本重分类改变跨期含义", "毛利变化是否全部来自经营？",
         "2024报告中的保证类质量保证列报变化使旧期比较成本重列；模型保留原报告值，估计对象是原始披露毛利率。",
         "销售费用转入营业成本可以改变毛利率，而不因此改变利润总额；不能将全部毛利变化解释为经营改善或恶化。",
         ["p_300750_2024", "p_300207_2024", "p_002074_2024", "p_300014_2024"],
         "若研究目的改为经济可比趋势，需要另建截至当时可得的调整桥，不能覆盖原版本。"),
        ("holdout", "固定方法与基准一同报告", "固定OLS是否优于沿用上期值？",
         "训练、留出及未成熟记录均按预先约定划分，逐公司误差及两项MAE见模型表。本案例不据结果选择模型。",
         "三个训练配对只支持代数拟合；产品结构、政策断点及共同周期限制外推。",
         ["e_300750_2022", "e_300207_2022", "e_002074_2022"],
         "需要更多历史可用版本、不同周期和预先独立设定的验证任务，才可评价推广表现。"),
        ("peers", "样本内位置需要业务解释", "同业位置能否直接转成质量评级？",
         "毛利/期末资产及百分位仅描述四家公司当前所给样本，不映射健康分数、违约概率或投资评级。",
         "电池品类、资产投入阶段、外协比例和合并范围都会影响该指标。",
         [r["id"]+"_gpa" for r in records if r["year"] == 2025],
         "取得可比产品和分部信息后才可形成更细的经营解释。")]
    for key, title, question, conclusion, mechanism, evidence, changes in issues:
        workpaper["findings"].append(dict(id=key, title=title, question=question, conclusion=conclusion,
            mechanism=mechanism, status="conditional", evidence=evidence, alternatives=["列报政策、样本选择及业务结构差异不能由一个比率模型消除。"], changes_if=changes))
        workpaper["sections"].append(dict(title=title, findings=[key]))
    q = panel.to_workpaper_result(result, "panel", "四家预选企业的固定历史毛利率模型",
        [f["id"] for f in workpaper["facts"] if not f["id"].startswith("300014_2022_")], [e["id"] for e in workpaper["evidence"]])
    q["limitations"].extend(limitations)
    workpaper["quantitative"].append(q)
    checked = Workpaper.model_validate(workpaper)
    save("workpaper.json", checked.model_dump(mode="json"))
    print(json.dumps(result["model"], ensure_ascii=False))


if __name__ == "__main__":
    main()
