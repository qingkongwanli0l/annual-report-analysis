"""Export a calculated annual-report workpaper to Word, Excel and PowerPoint."""

import argparse
import json
import re
import subprocess
from decimal import Decimal
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
import xlsxwriter
from calculate import calculate


ROOT = Path(__file__).resolve().parent.parent
STYLE = json.loads((ROOT / "assets/report-style.json").read_text(encoding="utf-8"))


def local(data, zh, en):
    return zh if data["company"]["language"] == "zh" else en


def number(data, value, unit="currency"):
    if value is None:
        return local(data, "未获取或不适用", "Unavailable or inapplicable")
    value = Decimal(value)
    if unit == "currency":
        value /= Decimal(data["company"]["display_multiplier"])
        return f"{value:,.2f}"
    if unit == "percent":
        return f"{value * 100:,.2f}%"
    suffix = local(data, " 天", " days") if unit == "days" else "×" if unit == "ratio" else ""
    return f"{value:,.2f}{suffix}"


def short_locator(locator):
    return re.split(r"[,，;；]", locator, maxsplit=1)[0] if locator.startswith("PDF p.") else locator


def evidence_text(data, references, compact=False):
    facts = {item["id"]: item for item in data["facts"]}
    sources = {item["id"]: item for item in data["sources"]}
    calculations = {item["id"]: item for item in data["calculations"] + data["checks"]}
    result = []
    for reference in references:
        kind, key = reference.split(":", 1)
        if kind == "fact":
            fact = facts[key]
            result.append(f"[{fact['source_id']}] {short_locator(fact['locator'])}" if compact else
                          f"{key} [{fact['source_id']}] {fact['locator']}")
        elif kind == "source":
            source = sources[key]
            result.append(f"[{key}] {short_locator(source.get('locator', ''))}" if compact else
                          f"[{key}] {source['title']} {source.get('locator', '')}".strip())
        else:
            result.append(("" if compact else f"{key}: ") + evidence_text(data, [f"fact:{i}" for i in calculations[key]["inputs"]], compact))
    return "; ".join(dict.fromkeys(result))


def metadata(data):
    c = data["company"]
    return " | ".join(str(c[key]) for key in (
        "identifier", "market", "accounting_standard", "scope", "period_end", "currency", "display_unit"
    ))


def kind_label(data, kind):
    return {"fact": local(data, "披露事实", "Disclosed fact"),
            "management": local(data, "管理层表述", "Management statement"),
            "inference": local(data, "分析判断", "Analyst inference")}.get(kind, "")


def export_word(data, destination):
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.top_margin = section.bottom_margin = Inches(0.7)
    section.left_margin = section.right_margin = Inches(0.75)
    font = STYLE["font_zh" if data["company"]["language"] == "zh" else "font_en"]
    for name, size in [("Normal", 11), ("Title", 23), ("Heading 1", 15), ("Heading 2", 12)]:
        style = doc.styles[name]
        style.font.name = font
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), font)
        for border in style.element.xpath("./w:pPr/w:pBdr"):
            border.getparent().remove(border)
    doc.styles["Normal"].paragraph_format.space_after = Pt(6)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.15
    title = data["company"]["name"] + local(data, " 年报分析", " Annual Report Analysis")
    doc.core_properties.title = title
    doc.core_properties.author = ""
    doc.add_paragraph(title, "Title")
    doc.add_paragraph(metadata(data))
    doc.add_paragraph(local(data, "分析范围以披露资料及下列阅读记录为准。缺失信息和未解决问题单独列示。",
                            "The analysis scope follows the disclosures and review record below. Missing information and unresolved questions are identified separately."))

    def heading(zh, en):
        doc.add_heading(local(data, zh, en), 1)

    def items(entries):
        for item in entries:
            p = doc.add_paragraph()
            label = kind_label(data, item.get("kind"))
            if label:
                p.add_run(label + "  ").bold = True
            p.add_run(item["text"])
            if item.get("evidence"):
                p.paragraph_format.keep_with_next = True
                p = doc.add_paragraph(evidence_text(data, item["evidence"], compact=True))
                p.paragraph_format.keep_together = True
                for run in p.runs:
                    run.font.size = Pt(9)
                    run.font.color.rgb = RGBColor.from_string(STYLE["muted"])

    def table(headers, rows, widths):
        tbl = doc.add_table(rows=1, cols=len(headers))
        tbl.style = "Light Shading"
        tbl.autofit = False
        for col, width in zip(tbl.columns, widths):
            col.width = Inches(width)
        for cell, text, width in zip(tbl.rows[0].cells, headers, widths):
            cell.width = Inches(width)
            cell.text = text
            for run in cell.paragraphs[0].runs:
                run.bold = True
                run.font.size = Pt(9.5)
                run.font.color.rgb = RGBColor(0, 0, 0)
        repeat = OxmlElement("w:tblHeader")
        tbl.rows[0]._tr.get_or_add_trPr().append(repeat)
        for row in rows:
            new_row = tbl.add_row()
            new_row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
            for cell, value, width in zip(new_row.cells, row, widths):
                cell.width = Inches(width)
                cell.text = str(value)
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.space_after = Pt(3)
                    for run in paragraph.runs:
                        run.font.size = Pt(9.5)
        doc.add_paragraph()

    analysis = data.get("analysis", {})
    heading("主要发现", "Key findings")
    items(analysis.get("summary", []))
    if not analysis.get("summary"):
        doc.add_paragraph(local(data, "未提供经证据支持的分析结论。", "No evidence-backed narrative conclusions supplied."))
    for part in analysis.get("sections", []):
        doc.add_heading(part["title"], 1)
        items(part["items"])
    heading("财务事实", "Financial facts")
    table([local(data, "项目及口径", "Metric and basis"), local(data, "期间", "Period"),
           local(data, "金额", "Amount") + " (" + data["company"]["display_unit"] + ")", local(data, "出处", "Evidence")], [
        [f"{f['label']}\n{f['scope']} / {f['basis']}" + (local(data, " / 已重述", " / restated") if f["restated"] else "") +
         (local(data, " / 排除选用", " / excluded from selection") if f.get("use_for_analysis") is False else
          local(data, " / 原披露候选", " / reported candidate") if f['basis'] == 'reported' else
          local(data, " / 分析调整值", " / analyst adjustment")),
         f"{f['period_start'] or '—'} → {f['period_end']}", number(data, f["normalized_value"]) + " " + f["currency"],
         f"[{f['source_id']}] {short_locator(f['locator'])}"] for f in data["facts"]
    ], [2.4, 1.45, 1.05, 2.1])
    for fact in data["facts"]:
        if fact.get("note"):
            p = doc.add_paragraph(f"{fact['label']} ({fact['period_end']})  {fact['note']}")
            p.paragraph_format.keep_together = True
            for run in p.runs:
                run.font.size = Pt(9)
    heading("计算结果", "Calculated metrics")
    table([local(data, "指标", "Metric"), local(data, "结果", "Value"), local(data, "依据或缺失原因", "Basis or missing-data reason")], [
        [f"{c['label']}\n{c['period_end']}", number(data, c["value"], c["unit"]),
         c["reason"] or f"{c['expression']}\n" + evidence_text(data, [f"fact:{i}" for i in c["inputs"]], compact=True)]
        for c in data["calculations"]
    ], [2.1, 1.0, 3.9])
    heading("报表勾稽", "Statement reconciliation")
    table([local(data, "检查", "Check"), local(data, "差额及状态", "Residual and status"), local(data, "说明", "Explanation")], [
        [c["label"], f"{number(data, c['value'])} / {c['status']}", c["reason"] or
         f"{c['expression']}\n" + evidence_text(data, [f"fact:{i}" for i in c["inputs"]], compact=True)]
        for c in data["checks"]
    ], [2.1, 1.25, 3.65])
    heading("待核问题", "Questions for further review")
    items(analysis.get("questions", []))
    heading("阅读覆盖及局限", "Review coverage and limitations")
    table([local(data, "章节", "Section"), local(data, "状态", "Status"), local(data, "记录", "Record")], [
        [c["section"], c["status"], f"[{c.get('source_id', '')}] {c.get('locator', '')}\n{c.get('note', '')}"]
        for c in data.get("coverage", [])
    ], [2.0, 0.85, 4.15])
    for note in analysis.get("limitations", []):
        doc.add_paragraph(str(note))
    for note in data.get("calculation_notes", []):
        doc.add_paragraph(str(note))
    heading("来源索引", "Source index")
    urls = {}
    for source in data["sources"]:
        url = source["url"]
        location = (local(data, "同来源 ", "Same document as ") + f"[{urls[url]}]") if url and url in urls else (url or local(data, "用户上传资料", "User-supplied document"))
        urls.setdefault(url, source["id"])
        p = doc.add_paragraph(f"[{source['id']}] {source['title']} | {source['published'] or '—'}\n"
                             f"{source.get('locator', '')}\n{location}")
        p.paragraph_format.keep_together = True
        for run in p.runs:
            run.font.size = Pt(9)
    doc.save(destination)


def excel_expression(expression, rows):
    """Translate calculator arithmetic, never source text, into Excel references."""
    stripped = re.sub(r"\{[^{}]+\}", "0", expression)
    if not re.fullmatch(r"[\d.\s()+*/-]+", stripped):
        raise ValueError("Unsupported calculator expression: " + expression)
    return "=" + re.sub(r"\{([^{}]+)\}", lambda match: f"'Normalized'!$C${rows[match[1]]}", expression)


def export_excel(data, destination):
    c = data["company"]
    divisor = Decimal(c["display_multiplier"])
    with xlsxwriter.Workbook(destination, {"strings_to_formulas": False, "strings_to_urls": False}) as book:
        header = book.add_format({"bold": True, "font_color": "white", "bg_color": STYLE["accent"], "text_wrap": True})
        text_format = book.add_format({"text_wrap": True, "valign": "top"})
        numeric = book.add_format({"num_format": "#,##0.00;[Red](#,##0.00)", "valign": "top"})
        percent = book.add_format({"num_format": "0.00%;[Red](0.00%)", "valign": "top"})

        def sheet(name, headers):
            ws = book.add_worksheet(name)
            ws.freeze_panes(1, 0)
            ws.set_column(0, len(headers) - 1, 22, text_format)
            ws.set_row(0, 32)
            for col, label in enumerate(headers):
                ws.write_string(0, col, label, header)
            return ws

        def strings(ws, row, values):
            for col, value in enumerate(values):
                ws.write_string(row, col, "" if value is None else str(value), text_format)

        overview = sheet("Overview", [local(data, "项目", "Item"), local(data, "内容", "Content"), local(data, "证据", "Evidence")])
        overview.set_column(1, 2, 70, text_format)
        strings(overview, 1, [c["name"], metadata(data)])
        strings(overview, 2, [local(data, "数值精度", "Numeric precision"),
                local(data, "Excel数值使用浮点数；原始十进制文本保存在Raw中。货币计算列保留基础单位，Display列使用展示单位。",
                      "Excel uses floating point; Raw preserves exact decimal text. Currency calculation values use base units; Display uses the stated display unit.")])
        row = 3
        analysis = data.get("analysis", {})
        groups = [(local(data, "主要发现", "Findings"), analysis.get("summary", []))]
        groups += [(part["title"], part["items"]) for part in analysis.get("sections", [])]
        groups.append((local(data, "待核问题", "Questions"), analysis.get("questions", [])))
        for name, entries in groups:
            for item in entries:
                strings(overview, row, [name, f"{kind_label(data, item.get('kind'))} {item['text']}", evidence_text(data, item.get("evidence", []))])
                row += 1
        for note in analysis.get("limitations", []) + data.get("calculation_notes", []):
            strings(overview, row, [local(data, "局限", "Limitation"), str(note)])
            row += 1

        raw = sheet("Raw", ["ID", "Label", "Raw text", "Value exact text", "Value numeric", "Multiplier", "Currency", "Start", "End", "Scope", "Standard", "Basis", "Restated", "Use for analysis", "Source", "Locator", "Note"])
        normalized = sheet("Normalized", ["ID", "Label", "Base currency value", "Currency", "Scope", "Basis", "Period end", "Status"])
        rows = {}
        for row, f in enumerate(data["facts"], 1):
            rows[f["id"]] = row + 1
            strings(raw, row, [f["id"], f["label"], f["raw_value"], f["value"], None, None, f["currency"], f["period_start"], f["period_end"], f["scope"], f["standard"], f["basis"], f["restated"], f.get("use_for_analysis", True), f["source_id"], f["locator"], f.get("note", "")])
            raw.write_number(row, 5, float(Decimal(f["unit_multiplier"])), numeric)
            strings(normalized, row, [f["id"], f["label"], None, f["currency"], f["scope"], f["basis"], f["period_end"], ""])
            if f["value"] is not None:
                raw.write_number(row, 4, float(Decimal(f["value"])), numeric)
                normalized.write_formula(row, 2, f"=Raw!E{row+1}*Raw!F{row+1}", numeric, float(Decimal(f["normalized_value"])))
            else:
                normalized.write_string(row, 7, f.get("note") or local(data, "原始资料未提供该值", "Value not available in source"))

        for key, name in [("calculations", "Calculations"), ("checks", "Checks")]:
            ws = sheet(name, ["ID", "Label", "Value (base units)", "Display", "Unit", "Expression", "Inputs", "Status / Reason", "Tolerance (base units)", "Evidence"])
            ws.set_column(5, 7, 55, text_format)
            for row, item in enumerate(data[key], 1):
                strings(ws, row, [item["id"], item["label"], None, None, c["display_unit"] if item["unit"] == "currency" else item["unit"], item["expression"], ", ".join(item["inputs"]), " / ".join(filter(None, [item.get("status"), item.get("reason")])), None,
                                 evidence_text(data, [f"fact:{i}" for i in item["inputs"]])])
                if item.get("tolerance") is not None:
                    ws.write_number(row, 8, float(Decimal(item["tolerance"])), numeric)
                if item["value"] is None:
                    ws.write_string(row, 2, local(data, "不可计算", "Unavailable"))
                    ws.write_string(row, 3, item["reason"] or local(data, "数据不足", "Insufficient data"))
                    continue
                cached = float(Decimal(item["value"]))
                fmt = percent if item["unit"] == "percent" else numeric
                ws.write_formula(row, 2, excel_expression(item["expression"], rows), fmt, cached)
                display_formula = f"=C{row+1}"
                display_value = cached
                if item["unit"] == "currency":
                    display_formula += f"/{divisor}"
                    display_value = float(Decimal(item["value"]) / divisor)
                ws.write_formula(row, 3, display_formula, fmt, display_value)

        sources = sheet("Sources", ["ID", "Title", "URL / upload", "Published", "Locator", "SHA256"])
        sources.set_column(1, 2, 65, text_format)
        for row, source in enumerate(data["sources"], 1):
            strings(sources, row, [source["id"], source["title"], source["url"] or local(data, "用户上传", "User upload"), source["published"], source.get("locator"), source.get("sha256")])
        coverage = sheet("Coverage", ["Section", "Status", "Source", "Locator", "Note"])
        coverage.set_column(3, 4, 65, text_format)
        for row, item in enumerate(data.get("coverage", []), 1):
            strings(coverage, row, [item["section"], item["status"], item.get("source_id"), item.get("locator"), item.get("note")])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("calculated_json", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--node", default="node", help="Node.js executable (default: PATH)")
    args = parser.parse_args()
    data = json.loads(args.calculated_json.read_text(encoding="utf-8-sig"))
    if "calculations" not in data or "checks" not in data or any("normalized_value" not in f for f in data["facts"]):
        parser.error("Input must be calculator output; run calculate.py first.")
    verified = calculate(data)
    if any(verified[key] != data[key] for key in ("calculations", "checks")) or any(
            old["normalized_value"] != new["normalized_value"] for old, new in zip(data["facts"], verified["facts"])):
        parser.error("Cached calculations do not match current facts. Run calculate.py again before exporting.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    export_word(data, args.output_dir / "report.docx")
    export_excel(data, args.output_dir / "financials.xlsx")
    subprocess.run([args.node, str(ROOT / "scripts/export_slides.cjs"), str(args.calculated_json.resolve()),
                    str((args.output_dir / "presentation.pptx").resolve())], check=True)
    print(json.dumps({"files": [str((args.output_dir / name).resolve()) for name in
                               ("report.docx", "financials.xlsx", "presentation.pptx")]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
