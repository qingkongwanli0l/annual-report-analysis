"""Calculate a sourced annual-report workpaper; never author financial conclusions."""

import argparse
import copy
import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path


INSTANT = {
    "assets", "liabilities", "equity", "parent_equity", "current_assets",
    "current_liabilities", "inventory", "receivables", "cash_equivalents",
}
INDUSTRIAL = {"gross_margin", "cash_profit_ratio", "current_ratio", "inventory_days", "receivable_days", "free_cash_flow"}


def decimal(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Financial values must be finite decimal numbers")
    return result


def number(value):
    return None if value is None else format(value, "f")


def validate(data):
    company = data["company"]
    for key in ("name", "identifier", "market", "accounting_standard", "currency", "scope", "display_unit"):
        if not company.get(key):
            raise ValueError(f"company.{key} is required")
    if company.get("industry") not in {"non-financial", "bank", "insurance", "securities"}:
        raise ValueError("company.industry must identify the industry")
    if company.get("language", "zh") not in {"zh", "en"}:
        raise ValueError("company.language must be zh or en")
    for prefix in ("", "prior_"):
        start, end = (date.fromisoformat(company[prefix + key]) for key in ("period_start", "period_end"))
        if start > end:
            raise ValueError(f"{prefix}period_start is after period_end")
    if decimal(company["display_multiplier"]) <= 0:
        raise ValueError("display_multiplier must be positive")
    source_ids = [s["id"] for s in data["sources"]]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Duplicate source IDs")
    fact_ids = set()
    for fact in data["facts"]:
        fact_id = fact["id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", fact_id) or fact_id in fact_ids:
            raise ValueError(f"Invalid or duplicate fact ID: {fact_id}")
        fact_ids.add(fact_id)
        if fact["source_id"] not in source_ids or not fact.get("locator"):
            raise ValueError(f"{fact_id}: a source and document locator are required")
        for key in ("metric", "label", "currency", "scope", "standard", "raw_value", "restated", "basis", "period_start"):
            if key not in fact:
                raise ValueError(f"{fact_id}: missing {key}")
        if fact["basis"] not in {"reported", "analyst_adjusted"}:
            raise ValueError(f"{fact_id}: invalid basis")
        end = date.fromisoformat(fact["period_end"])
        if fact["period_start"] and date.fromisoformat(fact["period_start"]) > end:
            raise ValueError(f"{fact_id}: period starts after its end")
        multiplier = decimal(fact["unit_multiplier"])
        if multiplier <= 0:
            raise ValueError(f"{fact_id}: unit_multiplier must be positive")
        fact["normalized_value"] = number(decimal(fact["value"]) * multiplier) if fact["value"] is not None else None
        if fact["value"] is not None:
            if "source_decimals" not in fact:
                tokens = re.findall(r"\d[\d,]*(?:\.\d+)?", fact["raw_value"])
                if len(tokens) != 1 or abs(decimal(tokens[0].replace(",", ""))) != abs(decimal(fact["value"])):
                    raise ValueError(f"{fact_id}: provide source_decimals when raw_value has no unambiguous numeric precision")
                fact["source_decimals"] = max(0, -decimal(tokens[0].replace(",", "")).as_tuple().exponent)
            if type(fact["source_decimals"]) is not int or fact["source_decimals"] < 0:
                raise ValueError(f"{fact_id}: source_decimals must be a non-negative integer")
    for row in data.get("coverage", []):
        if row["status"] not in {"reviewed", "partial", "unavailable"}:
            raise ValueError("Invalid coverage status")
        if row.get("source_id") and row["source_id"] not in source_ids:
            raise ValueError("Coverage references an unknown source")


def calculate(workpaper):
    data = copy.deepcopy(workpaper)
    validate(data)
    c = data["company"]
    english = c.get("language") == "en"
    tr = lambda zh, en: en if english else zh
    opening = (date.fromisoformat(c["period_start"]) - timedelta(days=1)).isoformat()
    days = (date.fromisoformat(c["period_end"]) - date.fromisoformat(c["period_start"])).days + 1
    prior_days = (date.fromisoformat(c["prior_period_end"]) - date.fromisoformat(c["prior_period_start"])).days + 1
    data["calculations"], data["checks"] = [], []
    data["calculation_notes"] = [tr(
        "金额先换算为同一币种基本单位；不自动换汇。指标为分析定义，非会计准则结论。平均余额使用期初期末均值。",
        "Amounts are normalized to base currency units without FX conversion. Ratios are analytical definitions, not accounting-standard conclusions. Averages use opening and closing balances.",
    )]

    def select(metric, period="current"):
        instant = metric in INSTANT
        end = opening if period == "opening" else c["prior_period_end"] if period == "prior" else c["period_end"]
        start = None if instant else c["prior_period_start"] if period == "prior" else c["period_start"]
        candidates = [f for f in data["facts"] if f["metric"] == metric and f["period_end"] == end
                      and f["period_start"] == start and f["scope"] == c["scope"]
                      and f["currency"] == c["currency"] and f["standard"] == c["accounting_standard"]
                      and f["basis"] == "reported" and f.get("use_for_analysis", True)]
        if len(candidates) != 1:
            reason = tr("缺少同口径输入", "Missing comparable input") if not candidates else tr("存在多个可用值，请明确选用的重述/版本", "Multiple eligible facts; select the correct restatement/version")
            return None, f"{reason}: {metric} ({end})"
        fact = candidates[0]
        if fact["normalized_value"] is None:
            return None, tr("未披露或未读取", "Not disclosed or not extracted") + f": {fact['id']}"
        return fact, None

    def record(identifier, label, specs, expression, operation, unit="ratio", guard=None, check=False):
        row = {"id": identifier, "label": label, "value": None, "unit": unit,
               "expression": None, "inputs": [], "reason": None}
        if check:
            row.update(status="unavailable", tolerance=None)
        else:
            row["period_end"] = c["period_end"]
        target = data["checks"] if check else data["calculations"]
        target.append(row)
        if identifier in INDUSTRIAL and c["industry"] != "non-financial":
            row["reason"] = tr("金融企业不套用此工业企业指标；请查阅披露的行业指标。", "Not applied to financial companies; use disclosed sector measures.")
            return
        selected = [select(*spec) for spec in specs]
        errors = [error for _, error in selected if error]
        if errors:
            row["reason"] = "; ".join(errors)
            return
        facts = [fact for fact, _ in selected]
        values = [decimal(f["normalized_value"]) for f in facts]
        reason = guard(values) if guard else None
        if reason:
            row["reason"] = reason
            return
        value = operation(values)
        row.update(value=number(value), expression=expression.format(*["{" + f["id"] + "}" for f in facts]), inputs=[f["id"] for f in facts])
        if check:
            tolerance = sum((Decimal("0.5") * Decimal(10) ** -f["source_decimals"] * decimal(f["unit_multiplier"]) for f in facts), Decimal(0))
            row.update(tolerance=number(tolerance), status="matched" if abs(value) <= tolerance else "difference")
            if row["status"] == "difference":
                row["reason"] = tr("差额超过原文显示精度的舍入范围；请回查口径、遗漏或提取错误。", "Residual exceeds source rounding precision; review definitions, omissions or extraction.")

    def positive_denominator(values):
        return tr("分母为零或负数，指标不作常规解释。", "Zero or negative denominator; ordinary interpretation is not meaningful.") if values[-1] <= 0 else None

    def growth_guard(values):
        if c["prior_period_end"] != opening:
            return tr("比较期不是相邻上一年度，不标为同比；仅展示绝对变化。", "The comparative period is not the immediately preceding year; no year-over-year rate is calculated.")
        if not (330 <= days <= 380 and 330 <= prior_days <= 380 and abs(days - prior_days) <= 7):
            return tr("报告期间不构成可比完整年度；仅展示绝对变化。", "Periods are not comparable full years; show absolute change only.")
        return positive_denominator(values)

    with localcontext() as context:
        context.prec = 34
        for metric, zh, en in (("revenue", "营业收入", "Revenue"), ("net_income", "净利润", "Net income")):
            specs = [(metric,), (metric, "prior")]
            record(metric + "_change", tr(zh + "变动额", en + " change"), specs, "{0}-{1}", lambda v: v[0] - v[1], "currency")
            record(metric + "_growth", tr(zh + "同比", en + " growth"), specs, "({0}-{1})/{1}", lambda v: (v[0] - v[1]) / v[1], "percent", growth_guard)
        record("gross_margin", tr("毛利率", "Gross margin"), [("cost_of_sales",), ("revenue",)], "({1}-{0})/{1}", lambda v: (v[1] - v[0]) / v[1], "percent",
               lambda v: tr("营业成本应为正数支出。", "Cost of sales must use the positive expense convention.") if v[0] < 0 else positive_denominator(v))
        record("net_margin", tr("净利率", "Net margin"), [("net_income",), ("revenue",)], "{0}/{1}", lambda v: v[0] / v[1], "percent", positive_denominator)
        record("cash_profit_ratio", tr("经营现金流与净利润比", "Operating cash flow / net income"), [("cfo",), ("net_income",)], "{0}/{1}", lambda v: v[0] / v[1], guard=positive_denominator)
        record("current_ratio", tr("流动比率", "Current ratio"), [("current_assets",), ("current_liabilities",)], "{0}/{1}", lambda v: v[0] / v[1], guard=positive_denominator)
        record("liabilities_assets", tr("资产负债率", "Liabilities / assets"), [("liabilities",), ("assets",)], "{0}/{1}", lambda v: v[0] / v[1], "percent", positive_denominator)

        def average_guard(values):
            return tr("期初或期末余额非正数，平均余额指标不作常规解释。", "Opening or closing balance is non-positive; ordinary average-balance interpretation is not meaningful.") if min(values[1:]) <= 0 else None

        record("roe", tr("简化归母ROE", "Simplified parent-attributable ROE"), [("parent_net_income",), ("parent_equity", "opening"), ("parent_equity",)], "{0}/(({1}+{2})/2)", lambda v: v[0] / ((v[1] + v[2]) / 2), "percent", average_guard)
        record("roa", tr("ROA 净利润口径", "ROA based on net income"), [("net_income",), ("assets", "opening"), ("assets",)], "{0}/(({1}+{2})/2)", lambda v: v[0] / ((v[1] + v[2]) / 2), "percent", average_guard)
        for metric, denominator, identifier, zh, en in (("inventory", "cost_of_sales", "inventory_days", "存货周转天数", "Inventory days"), ("receivables", "revenue", "receivable_days", "应收账款周转天数", "Trade receivable days")):
            record(identifier, tr(zh, en), [(metric, "opening"), (metric,), (denominator,)], "({0}+{1})/2/{2}*" + str(days), lambda v: (v[0] + v[1]) / 2 / v[2] * days, "days",
                   lambda v: tr("余额为负，需核查口径。", "Negative balance; review its definition.") if min(v[:2]) < 0 else positive_denominator(v))
        record("free_cash_flow", tr("自由现金流 CFO减资本开支", "Free cash flow CFO less capex"), [("cfo",), ("capex",)], "{0}-{1}", lambda v: v[0] - v[1], "currency",
               lambda v: tr("资本开支须按正数现金支付录入。", "Capex must be entered as a positive cash payment.") if v[1] < 0 else None)
        record("balance_sheet", tr("资产减负债减权益", "Assets less liabilities less equity"), [("assets",), ("liabilities",), ("equity",)], "{0}-{1}-{2}", lambda v: v[0] - v[1] - v[2], "currency", check=True)
        record("profit_attribution", tr("净利润归属勾稽", "Net income attribution"), [("net_income",), ("parent_net_income",), ("minority_net_income",)], "{0}-{1}-{2}", lambda v: v[0] - v[1] - v[2], "currency", check=True)
        record("cash_rollforward", tr("现金及等价物变动勾稽 含汇率影响", "Cash equivalents roll-forward including FX"), [("cash_equivalents",), ("cash_equivalents", "opening"), ("cfo",), ("cfi",), ("cff",), ("fx_effect",)], "{0}-{1}-{2}-{3}-{4}-{5}", lambda v: v[0] - sum(v[1:]), "currency", check=True)
        record("equity_rollforward", tr("权益变动勾稽", "Equity roll-forward"), [("equity",), ("equity", "opening"), ("comprehensive_income",), ("owner_transactions",)], "{0}-{1}-{2}-{3}", lambda v: v[0] - sum(v[1:]), "currency", check=True)

    known = {f"{kind}:{row['id']}" for kind, rows in (("fact", data["facts"]), ("source", data["sources"]), ("calculation", data["calculations"]), ("check", data["checks"])) for row in rows}
    analysis = data.get("analysis", {})
    items = analysis.get("summary", []) + analysis.get("questions", []) + [item for section in analysis.get("sections", []) for item in section["items"]]
    for item in items:
        if not item.get("evidence"):
            raise ValueError("Narrative conclusions and questions require evidence; put unsourced limitations in analysis.limitations")
        for ref in item["evidence"]:
            if ref not in known:
                raise ValueError(f"Unknown narrative evidence: {ref}")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = calculate(json.loads(args.input.read_text(encoding="utf-8-sig")))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (ValueError, KeyError, InvalidOperation, OSError) as error:
        parser.exit(2, f"Calculation failed: {error}\n")
    print(args.output)


if __name__ == "__main__":
    main()
