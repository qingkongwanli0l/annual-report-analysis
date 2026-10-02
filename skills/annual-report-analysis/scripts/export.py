"""Calculate a workpaper once and export its editable research deliverables."""
import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import xlsxwriter
from xlsxwriter.utility import xl_col_to_name
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from calculate import evaluate, excel_expression
from workpaper import Workpaper


def unit(ctx):
    measure = ctx.currency if ctx.measure == "money" else ctx.physical_unit if ctx.measure == "count" else ctx.measure
    return f"{measure} × {ctx.scale}" if ctx.scale != 1 else measure


def display(value, ctx):
    if value is None:
        return "未计算 / unavailable"
    value = Decimal(str(value))
    if ctx.measure == "money" and ctx.currency == "CNY" and abs(value * ctx.scale) >= Decimal("1e8"):
        return f"{value * ctx.scale / Decimal('1e8'):,.2f} 亿元人民币"
    return f"{value*ctx.scale:.2%}" if ctx.measure == "ratio" else f"{value:,.2f} {unit(ctx)}"


def prepare(w, result):
    figures = {}
    for f in w.facts:
        figures[f.id] = {"id": f.id, "label": f.label, "value": str(f.value) if f.value is not None else None,
                         "display": display(f.value, f.context), "context": f.context.model_dump(mode="json"),
                         "evidence": f.evidence, "note": f.note}
    computed = {r["id"]: r for r in result["calculations"]}
    for c in w.calculations:
        r = computed[c.id]
        evidence = sorted({e for t in c.terms for e in figures[t.ref]["evidence"]})
        figures[c.id] = {"id": c.id, "label": c.label, "value": r["value"],
                         "display": display(r["value"], c.context), "context": c.context.model_dump(mode="json"),
                         "evidence": evidence, "note": r["reason"] or c.interpretation}

    def resolve(text):
        def replace(match):
            key = match.group(1)
            if key not in figures:
                raise ValueError(f"unknown numeric token {{{{{key}}}}}")
            return figures[key]["display"]
        return re.sub(r"\{\{([^{}]+)\}\}", replace, text)

    data = w.model_dump(mode="json")
    for finding in data["findings"]:
        for key in ("title", "question", "conclusion", "mechanism", "changes_if"):
            finding[key] = resolve(finding[key])
        finding["alternatives"] = [resolve(x) for x in finding["alternatives"]]
    data["figures"] = figures
    data["results"] = result
    return data


def workbook(w, data, path):
    with xlsxwriter.Workbook(path, {"strings_to_formulas": False, "strings_to_urls": False}) as book:
        book.set_properties({"title": w.mandate.title, "comments": f"Workpaper {w.mandate.version}"})
        head = book.add_format({"bold": True, "bg_color": "#213B45", "font_color": "white", "text_wrap": True})
        wrap = book.add_format({"text_wrap": True, "valign": "top"})
        number = book.add_format({"num_format": "#,##0.00;[Red](#,##0.00)"})
        percent = book.add_format({"num_format": "0.00%;[Red](0.00%)"})

        def sheet(name, headers, rows, widths=None):
            ws = book.add_worksheet(name)
            ws.write_row(0, 0, headers, head)
            ws.freeze_panes(1, 2)
            ws.set_row(0, 32)
            for rowno, row in enumerate(rows, 1):
                for col, item in enumerate(row):
                    ws.write(rowno, col, item, wrap)
            ws.autofilter(0, 0, max(1, len(rows)), len(headers)-1)
            for col in range(len(headers)):
                ws.set_column(col, col, widths[col] if widths else 28)
            return ws

        sheet("Readme", ["字段 / field", "内容 / value"], [
            ["任务", w.mandate.title], ["版本", w.mandate.version], ["信息截止", str(w.mandate.cutoff)],
            ["范围", w.mandate.scope], ["准则", w.mandate.accounting_basis],
            ["单位", "Facts D=原始值，E=倍数，F=基础单位。Calculations D=基础单位，E=展示值。"],
            ["复算", "数值公式可编辑；修改主体、期间、币种、规则或资料后须重跑 export.py 复核口径。"],
            ["缺口", "空值不是零。未执行程序、假设与已披露数据分别标识。"],
            *[["限制", x] for x in w.mandate.limitations]], [22, 110])
        rows = []
        for f in w.facts:
            c = f.context
            rows.append([f.id, f.label, ", ".join(f.evidence), float(f.value) if f.value is not None else None,
                         float(c.scale), None, c.measure, c.currency, c.entity, c.scope,
                         str(c.start or ""), str(c.end), c.aggregation, f.state, c.basis, f.note, f.concept, c.physical_unit])
        ws = sheet("Facts", ["ID", "原始科目", "证据", "原始数值", "倍数", "基础单位数值", "量纲", "币种",
                             "实体", "范围", "开始", "结束", "统计类型", "状态", "准则", "说明", "概念", "实物单位"], rows)
        cells = {}
        for i, f in enumerate(w.facts, 2):
            cells[f.id] = f"'Facts'!F{i}"
            if f.value is not None:
                ws.write_formula(i-1, 5, f"=D{i}*E{i}", number, float(f.value*f.context.scale))
            else:
                ws.write_formula(i-1, 5, "=NA()", number, "#N/A")
        rs = {r["id"]: r for r in data["results"]["calculations"]}
        calcrows = [[c.id, c.label, "", None, None, rs[c.id]["status"], rs[c.id]["reason"],
                     c.definition, c.interpretation, unit(c.context), float(c.context.scale),
                     c.context.entity, c.context.scope, str(c.context.start or ""), str(c.context.end)] for c in w.calculations]
        ws = sheet("Calculations", ["ID", "指标或桥", "基础单位公式", "基础单位结果", "展示结果", "状态", "不计算原因",
                                    "定义", "解释边界", "展示单位", "倍数", "实体", "范围", "开始", "结束"], calcrows)
        for i, c in enumerate(w.calculations, 2):
            r = rs[c.id]
            expr = excel_expression(c, cells) if len(c.terms) == 2 or c.op == "sum" else "=NA()"
            if c.op in ("ratio", "growth"):
                den = cells[c.terms[1].ref]
                test = f"{den}<=0" if c.denominator == "positive" or c.op == "growth" else f"{den}=0"
                if c.op == "growth":
                    test = f"OR({test},{cells[c.terms[0].ref]}<0)"
                expr = f"=IF({test},NA(),{expr[1:]})"
            ws.write_string(i-1, 2, expr, wrap)
            if r["normalized"] is not None:
                ws.write_formula(i-1, 3, expr, number, float(r["normalized"]))
                ws.write_formula(i-1, 4, f"=D{i}/K{i}", percent if c.context.measure == "ratio" else number, float(r["value"]))
            else:
                ws.write_formula(i-1, 3, "=NA()", number, "#N/A")
                ws.write_formula(i-1, 4, "=NA()", number, "#N/A")
            cells[c.id] = f"'Calculations'!D{i}"
        checks = {r["id"]: r for r in data["results"]["reconciliations"]}
        rows = [[r.id, r.label, r.actual, r.expected, None, float(r.tolerance), checks[r.id]["status"], r.basis] for r in w.reconciliations]
        ws = sheet("Reconciliations", ["ID", "勾稽", "实际", "目标", "残差 基础单位", "容差 基础单位", "状态", "容差依据"], rows)
        for i, r in enumerate(w.reconciliations, 2):
            value = checks[r.id]["residual"]
            if value is not None:
                ws.write_formula(i-1, 4, f"={cells[r.actual]}-{cells[r.expected]}", number, float(value))
        sheet("Sources", ["ID", "文件", "链接", "公布日期", "SHA256"],
              [[s.id, s.title, s.url, str(s.published), s.sha256] for s in w.sources], [20, 60, 100, 20, 70])
        sheet("Evidence", ["ID", "来源", "定位", "观察", "可靠性与限制"],
              [[e.id, e.source, e.locator, e.observation, e.reliability] for e in w.evidence], [20, 20, 45, 90, 65])
        sheet("Findings", ["ID", "问题", "结论", "机制", "状态", "依据", "反证", "其他解释", "改变结论条件"],
              [[f["id"], f["question"], f["conclusion"], f["mechanism"], f["status"], ", ".join(f["evidence"]),
                ", ".join(f["counterevidence"]), "\n".join(f["alternatives"]), f["changes_if"]] for f in data["findings"]], [18,45,85,75,18,35,35,75,75])
        sheet("Procedures", ["ID", "事项", "目的与认定", "总体", "选取", "步骤", "状态", "实际结果", "证据", "执行者日期"],
              [[p.id, p.finding, p.purpose+" / "+", ".join(p.assertions), p.population, p.selection,
                "\n".join(p.steps), p.status, p.result, ", ".join(p.evidence), f"{p.performed_by or ''} {p.performed_on or ''}"] for p in w.procedures])
        sheet("Requests", ["ID", "事项", "所需资料", "影响", "责任角色", "关闭条件"],
              [[r.id, r.finding, r.request, r.reason, r.owner_role, r.close_when] for r in w.requests], [18,18,75,70,30,75])
        for index, q in enumerate(w.quantitative, 1):
            if q.method == "operating_cash_scenario_v1":
                scenario_sheets(book, sheet, q.artifact, f"Q{index}", number)
            elif q.method == "pit_margin_persistence_v1":
                panel_sheets(sheet, q.artifact, f"Q{index}", number, percent)
            else:
                rows = q.artifact.get("rows", [])
                keys = list(dict.fromkeys(k for row in rows for k in row))
                sheet(f"Quant{index}", keys or ["result"], [[row.get(k, "") for k in keys] for row in rows])
            sheet(f"Quant{index}Notes", ["field", "value"], [["method", q.method], ["as_of", str(q.as_of)],
                  ["input references", ", ".join(q.input_refs)], ["assumptions", "\n".join(q.assumptions)],
                  ["limitations", "\n".join(q.limitations)], ["reproduction", f"See quantitative-{q.id}.json input_snapshot and method version"]], [28,110])


def scenario_sheets(book, sheet, artifact, prefix, number):
    snapshot = artifact["input_snapshot"]
    opening, floor = snapshot["opening"], snapshot["minimum_cash"]
    sheet(prefix+"Inputs", ["输入", "值", "依据"], [
        ["amount_scale", snapshot["amount_scale"], snapshot["currency"]],
        ["interest_basis_days", snapshot["interest_basis_days"], "实际期间天数 / 此日数"],
        ["payables_denominator", snapshot["payables_denominator"], "purchases或cost_of_sales"],
        ["minimum_cash", floor["value"], floor["source"]],
        *[[key, opening[key], opening["source"]] for key in ("cash", "receivables", "inventory", "payables", "debt")],
        ["复算边界", "编辑数字驱动可重算公式；日期/来源/口径/期间或逆向目标改变须重跑脚本", "负现金后续期间为#N/A；不自动融资"]], [32,55,85])
    inputs = f"'{prefix}Inputs'!"
    driver_keys = ["start", "end", "days", "volume", "unit_price", "unit_variable_cost", "fixed_cash_cost",
                   "depreciation", "capex", "tax_rate", "dso", "dio", "dpo", "interest_rate", "drawdown", "principal", "dividends", "source", "available_at"]
    drivers = sheet(prefix+"Drivers", driver_keys, [[p.get(k, "") for k in driver_keys] for p in snapshot["periods"]])
    datefmt = book.add_format({"num_format": "yyyy-mm-dd"})
    for i, period in enumerate(snapshot["periods"], 2):
        start, end = datetime.fromisoformat(period["start"]), datetime.fromisoformat(period["end"])
        drivers.write_datetime(i-1, 0, start, datefmt)
        drivers.write_datetime(i-1, 1, end, datefmt)
        drivers.write_formula(i-1, 2, f"=B{i}-A{i}+1", number, (end-start).days+1)
    keys = ["period_end", "revenue", "cost_of_sales", "ebitda", "depreciation", "ebit", "cash_interest", "cash_taxes", "net_income",
            "receivables_end", "inventory_end", "implied_purchases", "payables_end", "nwc_end", "delta_nwc", "cfo",
            "capex", "drawdown", "principal", "dividends", "cash_begin", "cash_end", "debt_begin", "debt_end",
            "cash_headroom", "funding_needed_to_floor", "interest_coverage", "debt_to_ebitda", "status"]
    cash = sheet(prefix+"Cash", keys, [])
    output = {r["period_end"]: r for r in artifact["rows"]}
    for i, period in enumerate(snapshot["periods"], 2):
        d = lambda col: f"'{prefix}Drivers'!{col}{i}"
        prev = i-1
        previous_cash = f"V{prev}" if i > 2 else inputs+"B6"
        previous_debt = f"X{prev}" if i > 2 else inputs+"B10"
        previous_inventory = f"K{prev}" if i > 2 else inputs+"B8"
        previous_nwc = f"N{prev}" if i > 2 else f"({inputs}B7+{inputs}B8-{inputs}B9)"
        formulas = [f"{d('D')}*{d('E')}", f"{d('D')}*{d('F')}", f"B{i}-C{i}-{d('G')}", d('H'),
                    f"D{i}-E{i}", f"W{i}*{d('N')}*{d('C')}/{inputs}B3", f"MAX(F{i}-G{i},0)*{d('J')}",
                    f"F{i}-G{i}-H{i}", f"B{i}*{d('K')}/{d('C')}", f"C{i}*{d('L')}/{d('C')}",
                    f"C{i}+K{i}-{previous_inventory}",
                    f'IF({inputs}B4="purchases",IF(L{i}<0,NA(),L{i}),C{i})*{d("M")}/{d("C")}',
                    f"J{i}+K{i}-M{i}", f"N{i}-{previous_nwc}", f"I{i}+E{i}-O{i}", d('I'), d('O'), d('P'), d('Q'),
                    previous_cash, f"U{i}+P{i}-Q{i}+R{i}-S{i}-T{i}", previous_debt,
                    f"IF(W{i}+R{i}-S{i}<0,NA(),W{i}+R{i}-S{i})", f"V{i}-{inputs}B5", f"MAX({inputs}B5-V{i},0)",
                    f"IF(G{i}>0,F{i}/G{i},NA())", f"IF(D{i}>0,X{i}/D{i},NA())"]
        row = output.get(period["end"], {})
        cash.write(i-1, 0, period["end"])
        for col, formula in enumerate(formulas, 1):
            if i > 2:
                formula = f"IF({previous_cash}<0,NA(),{formula})"
            value = period["depreciation"] if keys[col] == "depreciation" and row else row.get(keys[col])
            cash.write_formula(i-1, col, "="+formula, number, value if value is not None else "#N/A")
        cash.write_formula(i-1, 28, f'=IFERROR(IF(V{i}<0,"unfunded_cash_shortfall",IF(V{i}<{inputs}B5,"below_cash_floor","conditional")),"not_projected")',
                           None, row.get("status", "not_projected"))
    contracts = artifact.get("contracts", [])
    ws = sheet(prefix+"Contracts", ["条件", "日期", "指标", "关系", "阈值", "计算值", "结果", "定义", "依据"],
               [[c["label"], c["test_date"], c["metric"], c["relation"], c["threshold"], c["value"], c["status"], c["definition"], c["source"]] for c in contracts])
    dates = [p["end"] for p in snapshot["periods"]]
    for i, c in enumerate(contracts, 2):
        if c["test_date"] in dates:
            ref = f"'{prefix}Cash'!{xl_col_to_name(keys.index(c['metric']))}{dates.index(c['test_date'])+2}"
            ws.write_formula(i-1, 5, "="+ref, number, c["value"] if c["value"] is not None else "#N/A")
            comparison = ">=" if c["relation"] == "at_least" else "<="
            ws.write_formula(i-1, 6, f'=IFERROR(IF(F{i}{comparison}E{i},"within_input_threshold","outside_input_threshold"),"not_tested")', None, c["status"])
    reverse = artifact.get("reverse")
    if reverse:
        rows = [["status", reverse["status"]], ["definition", reverse["definition"]],
                ["recalculation", "逆向根由SciPy计算；改边界/目标后重跑，不自动再次求根"]]
        for key in ("driver", "period_index", "driver_value", "test_date", "target_cash", "cash_residual", "source", "reason"):
            if key in reverse:
                rows.append([key, reverse[key]])
        for label, value in zip(("lower_bound", "upper_bound"), reverse["bounds"]):
            rows.append([label, value])
        for label, value in zip(("lower_cash_residual", "upper_cash_residual"), reverse["endpoint_cash_residuals"]):
            rows.append([label, value])
        sheet(prefix+"Reverse", ["字段", "结果"], rows, [35,100])
        if reverse.get("rows"):
            summary = ["period_end", "revenue", "net_income", "cfo", "cash_end", "debt_end", "cash_headroom"]
            sheet(prefix+"AtBoundary", summary, [[r[k] for k in summary] for r in reverse["rows"]])


def panel_sheets(sheet, artifact, prefix, number, percent):
    records = artifact["input_snapshot"]["records"]
    keys = ["id", "entity", "period_end", "available_at", "version", "revenue", "cost_of_sales", "total_assets", "industry", "accounting_basis", "currency", "source"]
    sheet(prefix+"Records", keys, [[r[k] for k in keys] for r in records])
    locations = {r["id"]: i for i, r in enumerate(records, 2)}
    margin = lambda identifier: f"IF(AND(COUNT('{prefix}Records'!F{locations[identifier]}:G{locations[identifier]})=2,'{prefix}Records'!F{locations[identifier]}>0),('{prefix}Records'!F{locations[identifier]}-'{prefix}Records'!G{locations[identifier]})/'{prefix}Records'!F{locations[identifier]},NA())"
    peers = [r for r in artifact["rows"] if r["kind"] == "peer"]
    ws = sheet(prefix+"Peers", ["企业", "选用记录", "可用时间", "版本", "毛利率", "毛利/期末资产", "样本内百分位", "有效同业数"],
               [[r["entity"], r["record_id"], r["available_at"], r["version"], r["gross_margin"], r["gross_profit_to_assets"], r["gross_profitability_percentile"], r["peer_n"]] for r in peers])
    for i, row in enumerate(peers, 2):
        location = locations[row["record_id"]]
        ws.write_formula(i-1, 4, "=IFERROR("+margin(row["record_id"])+",NA())" if row["gross_margin"] is not None else "=NA()", percent, row["gross_margin"] if row["gross_margin"] is not None else "#N/A")
        expr = f"('{prefix}Records'!F{location}-'{prefix}Records'!G{location})/'{prefix}Records'!H{location}"
        ws.write_formula(i-1, 5, f"=IF(AND(COUNT('{prefix}Records'!F{location}:H{location})=3,'{prefix}Records'!H{location}>0),{expr},NA())" if row["gross_profit_to_assets"] is not None else "=NA()", percent, row["gross_profit_to_assets"] if row["gross_profit_to_assets"] is not None else "#N/A")
        area = f"F$2:F${len(peers)+1}"
        ws.write_formula(i-1, 6, f'=IFERROR((COUNTIF({area},"<"&F{i})+(COUNTIF({area},F{i})+1)/2)/COUNT({area}),NA())', percent,
                         row["gross_profitability_percentile"] if row["gross_profitability_percentile"] is not None else "#N/A")
        ws.write_formula(i-1, 7, f"=COUNT({area})", number, row["peer_n"])
    train = artifact["training_pairs"]
    ws = sheet(prefix+"Train", ["企业", "首次起点记录", "首次目标记录", "当前毛利率", "下一年毛利率"],
               [[p["entity"], p["origin_id"], p["target_id"], p["x"], p["actual"]] for p in train])
    for i, pair in enumerate(train, 2):
        ws.write_formula(i-1, 3, "="+margin(pair["origin_id"]), percent, pair["x"])
        ws.write_formula(i-1, 4, "="+margin(pair["target_id"]), percent, pair["actual"])
    model = artifact["model"]
    ws = sheet(prefix+"Model", ["字段", "结果"], [["training_n", model["training_n"]], ["test_n", model["test_n"]],
               ["intercept", model.get("intercept")], ["slope", model.get("slope")], ["test_mae", model.get("test_mae")],
               ["baseline_mae", model.get("baseline_mae")], ["status", model["status"]],
               ["解释", "样本/时间/版本改变须重跑panel.py；固定样本数值变化可复算OLS及留出误差。不是PD或显著性证明。"]], [32,110])
    if model["status"] == "estimated":
        last = len(train)+1
        for excel_row, function, value in [(4, "INTERCEPT", model["intercept"]), (5, "SLOPE", model["slope"])]:
            ws.write_formula(excel_row-1, 1, f"=IFERROR({function}('{prefix}Train'!E2:E{last},'{prefix}Train'!D2:D{last}),NA())", number, value)
    predictions = [r for r in artifact["rows"] if r["kind"] == "out_of_time_prediction"]
    predsheet = sheet(prefix+"Test", ["企业", "起点记录", "目标记录", "当前值", "实际下一期", "预测", "预测绝对误差", "Last-value绝对误差", "起点可用时间", "目标可用时间"],
                      [[p["entity"], p["origin_id"], p["target_id"], p["x"], p["actual"], p["predicted"], abs(p["predicted"]-p["actual"]), abs(p["x"]-p["actual"]), p["origin_available_at"], p["target_available_at"]] for p in predictions])
    for i, p in enumerate(predictions, 2):
        for col, identifier, value in [(3, p["origin_id"], p["x"]), (4, p["target_id"], p["actual"])]:
            predsheet.write_formula(i-1, col, "="+margin(identifier), percent, value)
        predsheet.write_formula(i-1, 5, f"='{prefix}Model'!B4+'{prefix}Model'!B5*D{i}", percent, p["predicted"])
        predsheet.write_formula(i-1, 6, f"=ABS(F{i}-E{i})", percent, abs(p["predicted"]-p["actual"]))
        predsheet.write_formula(i-1, 7, f"=ABS(D{i}-E{i})", percent, abs(p["x"]-p["actual"]))
    if predictions:
        for excel_row, col, value in [(6, "G", model["test_mae"]), (7, "H", model["baseline_mae"])]:
            ws.write_formula(excel_row-1, 1, f"=AVERAGE('{prefix}Test'!{col}2:{col}{len(predictions)+1})", percent, value)
    sheet(prefix+"Selection", ["类别", "记录", "原因"],
          [[kind, p["record_id"], p["reason"]] for kind, pairs in [("pending", artifact["pending_outcomes"]), ("excluded", artifact["excluded_pairs"])] for p in pairs], [22,45,100])


def word(data, path):
    doc = Document()
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = Cm(2)
    section.left_margin = section.right_margin = Cm(2.2)
    for name in ("Normal", "Title", "Heading 1", "Heading 2", "Heading 3"):
        style = doc.styles[name]
        style.font.name = "Arial"
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        for border in style.element.xpath("./w:pPr/w:pBdr"):
            border.getparent().remove(border)
    doc.styles["Normal"].font.size = Pt(10)
    doc.styles["Normal"].paragraph_format.space_after = Pt(6)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.2
    footer = section.footer.paragraphs[0]
    footer.text = f"{data['mandate']['entity']}  |  {data['mandate']['version']}  |  "
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)

    def table(headers, rows):
        t = doc.add_table(rows=1, cols=len(headers))
        t.style = "Table Grid"
        t.autofit = False
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            border = OxmlElement("w:"+edge)
            for key, value in (("val", "single"), ("sz", "4"), ("color", "D9D9D9")):
                border.set(qn("w:"+key), value)
            borders.append(border)
        t._tbl.tblPr.append(borders)
        for cell, text in zip(t.rows[0].cells, headers):
            cell.text = text
            shading = OxmlElement("w:shd")
            shading.set(qn("w:fill"), "E6EEF0")
            cell._tc.get_or_add_tcPr().append(shading)
        repeat = OxmlElement("w:tblHeader")
        t.rows[0]._tr.get_or_add_trPr().append(repeat)
        for row in rows:
            for cell, text in zip(t.add_row().cells, row):
                cell.text = str(text)
        weights = [.35, .45, .20] if len(headers) == 3 else [1/len(headers)]*len(headers)
        available_width = section.page_width - section.left_margin - section.right_margin
        for col, weight in zip(t.columns, weights):
            col.width = int(available_width*weight)
        for row in t.rows:
            row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
            for cell, weight in zip(row.cells, weights):
                cell.width = int(available_width*weight)
        doc.add_paragraph()

    m = data["mandate"]
    doc.add_paragraph(m["title"], "Title")
    doc.add_paragraph(f"{m['period_start']} — {m['period_end']}　资料截止 {m['cutoff']}　底稿 {m['version']}")
    doc.add_paragraph(m["purpose"])
    findings = {f["id"]: f for f in data["findings"]}
    doc.add_heading("核心判断", 1)
    for f in data["findings"][:3]:
        doc.add_paragraph(f"{f['conclusion']} [{f['id']}; {', '.join(f['evidence'])}]")
    doc.add_paragraph(f"范围：{m['scope']}。会计基础：{m['accounting_basis']}。")
    for text in m["limitations"]:
        doc.add_paragraph(text)
    for s in data["sections"]:
        doc.add_heading(s["title"], 1)
        if s["figures"]:
            table(["项目及记录", "期间及数值", "证据"],
                  [[data['figures'][ref]['label']+f" [{ref}]", data['figures'][ref]['context']['end']+"\n"+data['figures'][ref]['display'],
                    ", ".join(data['figures'][ref]['evidence'])] for ref in s["figures"]])
        for ref in s["findings"]:
            f = findings[ref]
            doc.add_heading(f["title"]+f" [{ref}]", 2)
            for text in (f["conclusion"], f["mechanism"], "证据："+", ".join(f["evidence"]),
                         "反证："+(", ".join(f["counterevidence"]) or "尚无足以排除其他解释的额外证据"),
                         "其他解释："+"；".join(f["alternatives"]), "判断改变条件："+f["changes_if"]):
                doc.add_paragraph(text)
    doc.add_heading("勾稽结果", 1)
    for r in data["reconciliations"]:
        result = next(x for x in data["results"]["reconciliations"] if x["id"] == r["id"])
        doc.add_paragraph(f"{r['label']} [{r['id']}]：{result['status']}；基础单位残差 {result['residual']}。{r['basis']}")
    for q in data["quantitative"]:
        doc.add_page_break()
        doc.add_heading(q["label"], 1)
        doc.add_paragraph(f"{q['method']}；截至 {q['as_of']}。")
        artifact = q["artifact"]
        rows = artifact.get("rows", [])
        fmt = lambda value: "未计算" if value is None else f"{value:,.4f}" if isinstance(value, (int, float)) else str(value)
        if q["method"] == "operating_cash_scenario_v1":
            minimum = min(rows, key=lambda row: row["cash_end"])
            doc.add_paragraph(f"金额单位 {artifact['currency']} × {artifact['amount_scale']:g}。最低期末现金 {minimum['cash_end']:,.4f}，发生在 {minimum['period_end']}；补至输入最低现金所需资金 {minimum['funding_needed_to_floor']:,.4f}。未自动补融资。")
            table(["期间", "收入", "净利润", "CFO", "期末现金", "期末债务"],
                  [[r["period_end"], *[fmt(r[k]) for k in ("revenue", "net_income", "cfo", "cash_end", "debt_end")]] for r in rows])
            table(["期间", "营运资本增加", "资本开支", "借入", "还本", "股利"],
                  [[r["period_end"], *[fmt(r[k]) for k in ("delta_nwc", "capex", "drawdown", "principal", "dividends")]] for r in rows])
            if artifact.get("contracts"):
                doc.add_heading("输入合同条件", 2)
                table(["条件和日期", "定义与阈值", "计算结果"],
                      [[c["label"]+"\n"+c["test_date"], f"{c['definition']}\n{c['metric']} {c['relation']} {fmt(c['threshold'])}\n来源 {c['source']}",
                        f"{fmt(c['value'])}\n{c['status']}"] for c in artifact["contracts"]])
            if artifact.get("reverse"):
                reverse = artifact["reverse"]
                doc.add_heading("逆向现金边界", 2)
                doc.add_paragraph(reverse["definition"]+"；"+reverse["status"])
                if reverse["status"] == "converged":
                    table(["变量与期间", "边界与目标", "求解残差"],
                          [[f"{reverse['driver']}\n{reverse['test_date']}", f"驱动值 {reverse['driver_value']:,.6f}\n目标现金 {reverse['target_cash']:,.4f}", f"{reverse['cash_residual']:.8g}"]])
                    doc.add_paragraph("这是输入假设下的现金边界，不是发生概率或法律违约判断。")
                else:
                    doc.add_paragraph(reverse.get("reason", "未取得收敛边界"))
            if artifact["unprojected_periods"]:
                doc.add_paragraph(f"因现金未融资缺口，后续 {artifact['unprojected_periods']} 期未继续预测。")
        elif q["method"] == "pit_margin_persistence_v1":
            model = artifact["model"]
            table(["检验", "结果", "解释"], [["训练与留出", f"{model['training_n']} / {model['test_n']}", model['status']],
                  ["留出MAE", fmt(model.get("test_mae")), "毛利率小数单位；不是训练准确率"],
                  ["Last-value基准MAE", fmt(model.get("baseline_mae")), "使用上一期毛利率预测下一期"]])
            peers = [r for r in rows if r["kind"] == "peer"]
            table(["企业", "选用版本", "毛利率", "毛利资产比", "样本内百分位"],
                  [[r["entity"], r["version"], fmt(r["gross_margin"]), fmt(r["gross_profit_to_assets"]), fmt(r["gross_profitability_percentile"])] for r in peers])
            predictions = [r for r in rows if r["kind"] == "out_of_time_prediction"]
            if predictions:
                table(["企业", "预测", "实际下一期", "Last-value基准"],
                      [[p["entity"], fmt(p["predicted"]), fmt(p["actual"]), fmt(p["last_value_baseline"])] for p in predictions])
            doc.add_paragraph(f"未成熟结果 {len(artifact['pending_outcomes'])} 条；其他排除 {len(artifact['excluded_pairs'])} 条。记录、版本和排除理由详见工作簿。")
        doc.add_paragraph("证据记录："+", ".join(q["evidence"]))
        doc.add_heading("假设与适用限制", 2)
        for text in q["assumptions"]+q["limitations"]:
            doc.add_paragraph(text)
        doc.add_paragraph(f"完整逐期结果、输入快照与复算信息见 Excel Quant 工作表及 quantitative-{q['id']}.json。")
    doc.add_heading("已执行程序与待核工作", 1)
    for p in data["procedures"]:
        doc.add_heading(f"{p['id']} {p['purpose']}", 2)
        doc.add_paragraph(f"状态 {p['status']}；认定 {'、'.join(p['assertions'])}；总体 {p['population']}；选取 {p['selection']}。")
        for step in p["steps"]:
            doc.add_paragraph(step)
        doc.add_paragraph(f"实际结果：{p['result']}；证据 {', '.join(p['evidence'])}。")
    for r in data["requests"]:
        doc.add_heading(f"{r['id']} 待补资料", 2)
        doc.add_paragraph(r["request"])
        doc.add_paragraph(f"影响：{r['reason']}。责任角色：{r['owner_role']}。关闭条件：{r['close_when']}")
    doc.add_heading("来源与定位", 1)
    for s in data["sources"]:
        doc.add_paragraph(f"[{s['id']}] {s['title']}；公布 {s['published']}\n{s['url']}")
    for e in data["evidence"]:
        doc.add_paragraph(f"[{e['id']}] {e['source']} {e['locator']}。{e['observation']} {e['reliability']}")
    for border in doc.element.xpath(".//w:pPr/w:pBdr"):
        border.getparent().remove(border)
    doc.save(path)


def export(input_path, output_dir, node="node"):
    raw = Path(input_path).read_bytes()
    w = Workpaper.model_validate_json(raw)
    result = evaluate(w)
    data = prepare(w, result)
    out = Path(output_dir).resolve()
    skill_dir = Path(__file__).resolve().parents[1]
    if out == skill_dir or skill_dir in out.parents:
        raise ValueError("output must be in the task workspace, outside the installed skill")
    out.mkdir(parents=True, exist_ok=True)
    (out / "workpaper.json").write_text(w.model_dump_json(indent=2), encoding="utf-8")
    (out / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "presentation-data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for q in w.quantitative:
        (out / f"quantitative-{q.id}.json").write_text(json.dumps(q.artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    workbook(w, data, out / "workbook.xlsx")
    word(data, out / "report.docx")
    subprocess.run([node, str(Path(__file__).with_name("export_pptx.cjs")), str(out / "presentation-data.json"), str(out / "presentation.pptx")], check=True)
    manifest = {"version": w.mandate.version, "input_sha256": hashlib.sha256(raw).hexdigest(),
                "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.name in
                          ("report.docx", "workbook.xlsx", "presentation.pptx", "workpaper.json", "results.json")}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"output": str(out), "calculations": len(result["calculations"]),
            "not_calculated": [r["id"] for r in result["calculations"] if r["value"] is None]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    parser.add_argument("--node", default="node")
    args = parser.parse_args()
    print(json.dumps(export(args.input, args.output, args.node), ensure_ascii=False))
