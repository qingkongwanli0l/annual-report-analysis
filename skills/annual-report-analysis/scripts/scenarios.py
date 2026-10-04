"""Offline operating-cash scenarios and a one-driver reverse stress calculation."""
import argparse
from copy import deepcopy
from datetime import date, timedelta
import json
from math import isclose, ulp
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


METHOD = "operating_cash_scenario_v2"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Sourced(Input):
    source: str = Field(min_length=1)
    available_at: date


class Opening(Sourced):
    date: date
    cash: float = Field(ge=0)
    receivables: float = Field(ge=0)
    inventory: float = Field(ge=0)
    payables: float = Field(ge=0)
    debt: float = Field(ge=0)


class CashFloor(Sourced):
    value: float = Field(ge=0)


class Period(Sourced):
    start: date
    end: date
    volume: float = Field(ge=0)
    unit_price: float = Field(ge=0)
    unit_cost_of_sales: float = Field(ge=0)
    fixed_cash_cost: float = Field(ge=0)
    depreciation: float = Field(ge=0)
    depreciation_in_cost_of_sales: float = Field(ge=0)
    inventory_cash_conversion: float = Field(ge=0)
    inventory_depreciation_change: float
    capex: float = Field(ge=0)
    tax_rate: float = Field(ge=0, le=1)
    dso: float = Field(ge=0)
    dio: float = Field(ge=0)
    dpo: float = Field(ge=0)
    interest_rate: float
    drawdown: float = Field(ge=0)
    principal: float = Field(ge=0)
    dividends: float = Field(ge=0)


class Contract(Sourced):
    label: str
    definition: str = Field(min_length=1)
    test_date: date
    metric: Literal["cash_end", "debt_end", "ebitda", "interest_coverage", "debt_to_ebitda"]
    relation: Literal["at_least", "at_most"]
    threshold: float


class Reverse(Sourced):
    period_index: int = Field(ge=0)
    driver: Literal["volume", "unit_price", "unit_cost_of_sales", "fixed_cash_cost", "dso", "dio", "dpo"]
    bounds: tuple[float, float]
    test_date: date
    target_cash: float = Field(ge=0)
    definition: str = Field(min_length=1)


class Realized(Input):
    period_index: int = Field(ge=0)
    through_date: date
    metric: Literal["revenue", "cost_of_sales", "capex", "drawdown", "principal", "dividends"]
    value: float | None = Field(default=None, ge=0)
    source: str | None = Field(default=None, min_length=1)
    available_at: date | None = None
    same_scope: bool = False


class Scenario(Input):
    entity: str
    as_of: date
    currency: str
    amount_scale: float = Field(gt=0)
    interest_basis_days: float = Field(gt=0)
    payables_denominator: Literal["cost_of_sales", "purchases"]
    opening: Opening
    minimum_cash: CashFloor
    periods: list[Period] = Field(min_length=1)
    contracts: list[Contract] = Field(default_factory=list)
    reverse: Reverse | None = None
    path_basis: Literal["forward", "counterfactual"] = "forward"
    realized: list[Realized] = Field(default_factory=list)

    @model_validator(mode="after")
    def periods_and_sources(self):
        previous = self.opening.date
        for p in self.periods:
            if p.start != previous + timedelta(days=1) or p.end < p.start:
                raise ValueError("forecast periods must be contiguous after the opening date")
            previous = p.end
        sourced = [self.opening, self.minimum_cash, *self.periods, *self.contracts,
                   *[r for r in self.realized if r.available_at is not None]]
        seen, through_dates = set(), {}
        for r in self.realized:
            if r.period_index >= len(self.periods):
                raise ValueError("realized period_index is outside the forecast")
            p = self.periods[r.period_index]
            if not p.start <= r.through_date <= p.end:
                raise ValueError("realized cumulative through_date must be within its period")
            if r.through_date > self.as_of:
                raise ValueError("realized cumulative through_date cannot be after as_of")
            if r.available_at is not None and r.available_at < r.through_date:
                raise ValueError("realized source cannot be public before its measurement date")
            key = (r.period_index, r.metric)
            if key in seen:
                raise ValueError("duplicate realized metric for a period; select one cumulative snapshot")
            seen.add(key)
            if r.period_index in through_dates and through_dates[r.period_index] != r.through_date:
                raise ValueError("realized rows for one period must share one cumulative through_date")
            through_dates[r.period_index] = r.through_date
        if self.reverse:
            sourced.append(self.reverse)
            if self.reverse.period_index >= len(self.periods):
                raise ValueError("reverse period_index is outside the forecast")
            low, high = self.reverse.bounds
            if low < 0 or low >= high:
                raise ValueError("reverse bounds must be increasing non-negative driver values")
            if self.reverse.test_date not in [p.end for p in self.periods]:
                raise ValueError("reverse test_date must be a forecast period end")
            if self.periods[self.reverse.period_index].end > self.reverse.test_date:
                raise ValueError("reverse driver period cannot follow the cash test date")
        if self.opening.available_at < self.opening.date:
            raise ValueError("opening actual balances cannot be public before their measurement date")
        if self.opening.date > self.as_of or any(x.available_at > self.as_of for x in sourced):
            raise ValueError("opening data, realized data and assumption sources must be available by as_of")
        return self


def _actual_bridge(s):
    actuals = {(r.period_index, r.metric): r for r in s.realized}
    rows = []
    for index, p in enumerate(s.periods):
        totals = {"revenue": p.volume * p.unit_price, "cost_of_sales": p.volume * p.unit_cost_of_sales,
                  "capex": p.capex, "drawdown": p.drawdown, "principal": p.principal, "dividends": p.dividends}
        for metric, total in totals.items():
            r = actuals.get((index, metric))
            known = r is not None and r.value is not None and r.source is not None and r.available_at is not None and r.same_scope
            actual = r.value if r else None
            remaining = total - actual if known else None
            conflict = known and actual > total and not isclose(actual, total, rel_tol=0,
                                                               abs_tol=8 * max(ulp(actual), ulp(total)))
            rows.append({"period_index": index, "period_start": p.start.isoformat(), "period_end": p.end.isoformat(),
                         "metric": metric, "period_total": total, "actual": actual, "remaining": remaining,
                         "through_date": r.through_date.isoformat() if r else None,
                         "source": r.source if r else None, "available_at": r.available_at.isoformat() if r and r.available_at else None,
                         "same_scope": r.same_scope if r else False,
                         "status": "known" if known else "not_identified" if r else "not_supplied", "conflict": bool(conflict)})
    return rows


def _checked_actual_bridge(s):
    actual_bridge = _actual_bridge(s)
    conflicts = [f"period {r['period_index']} {r['metric']}: period_total={r['period_total']}, actual={r['actual']}, remaining={r['remaining']}"
                 for r in actual_bridge if r["conflict"]]
    if conflicts and s.path_basis == "forward":
        raise ValueError("sourced cumulative gross amounts declared same-scope exceed forward totals: " + "; ".join(conflicts)
                         + "; revise period totals/scope or explicitly select counterfactual")
    return actual_bridge, conflicts


def _project(s):
    cash, debt = s.opening.cash, s.opening.debt
    receivables, payables = s.opening.receivables, s.opening.payables
    inventory = s.opening.inventory
    inventory_depreciation_low, inventory_depreciation_high = 0, inventory
    nwc = s.opening.receivables + inventory - s.opening.payables
    rows = []
    for p in s.periods:
        days = (p.end - p.start).days + 1
        revenue = p.volume * p.unit_price
        cost = p.volume * p.unit_cost_of_sales
        if p.depreciation_in_cost_of_sales > min(p.depreciation, cost):
            raise ValueError("cost-of-sales depreciation exceeds total P&L depreciation or cost of sales")
        production_depreciation = p.depreciation_in_cost_of_sales + p.inventory_depreciation_change
        if production_depreciation < 0:
            raise ValueError("negative production depreciation: supplied inventory depreciation path is not feasible")
        ebitda = revenue - cost + p.depreciation_in_cost_of_sales - p.fixed_cash_cost
        ebit = ebitda - p.depreciation
        interest = debt * p.interest_rate * days / s.interest_basis_days
        taxes = max(ebit - interest, 0) * p.tax_rate
        profit = ebit - interest - taxes
        ar_end = revenue * p.dso / days
        inv_end = cost * p.dio / days
        inventory_depreciation_low = max(0, inventory_depreciation_low + p.inventory_depreciation_change)
        inventory_depreciation_high = min(inv_end, inventory_depreciation_high + p.inventory_depreciation_change)
        if inventory_depreciation_low > inventory_depreciation_high:
            raise ValueError("inventory depreciation balance cannot fit within total inventory across forecast periods")
        purchases = cost + inv_end - inventory - p.inventory_cash_conversion - production_depreciation
        if purchases < 0:
            raise ValueError("negative implied purchases: supplied inventory path is not feasible")
        ap_base = cost if s.payables_denominator == "cost_of_sales" else purchases
        ap_end = ap_base * p.dpo / days
        collectible = receivables + revenue
        payable = payables + purchases
        if ar_end > collectible and not isclose(ar_end, collectible, rel_tol=1e-14):
            raise ValueError("negative implied customer collections: receivable-days path exceeds opening receivables plus sales")
        if ap_end > payable and not isclose(ap_end, payable, rel_tol=1e-14):
            raise ValueError("negative implied supplier payments: payable-days path exceeds opening payables plus purchases")
        nwc_end = ar_end + inv_end - ap_end
        delta_nwc = nwc_end - nwc
        cfo = profit + p.depreciation + p.inventory_depreciation_change - delta_nwc
        debt_end = debt + p.drawdown - p.principal
        if debt_end < 0:
            raise ValueError("principal exceeds opening debt plus explicit drawdown")
        cash_end = cash + cfo - p.capex + p.drawdown - p.principal - p.dividends
        rows.append({
            "period_start": p.start.isoformat(), "period_end": p.end.isoformat(), "days": days,
            "revenue": revenue, "cost_of_sales": cost, "ebitda": ebitda, "ebit": ebit,
            "depreciation": p.depreciation, "production_depreciation": production_depreciation,
            "cash_interest": interest, "cash_taxes": taxes, "net_income": profit,
            "receivables_end": ar_end, "inventory_end": inv_end, "implied_purchases": purchases,
            "inventory_depreciation_lower": inventory_depreciation_low,
            "inventory_depreciation_upper": inventory_depreciation_high,
            "payables_end": ap_end, "nwc_end": nwc_end, "delta_nwc": delta_nwc,
            "customer_collections": max(0, collectible - ar_end),
            "supplier_payments": max(0, payable - ap_end),
            "cfo": cfo, "capex": p.capex, "drawdown": p.drawdown,
            "principal": p.principal, "dividends": p.dividends,
            "cash_begin": cash, "cash_end": cash_end, "debt_begin": debt, "debt_end": debt_end,
            "cash_headroom": cash_end - s.minimum_cash.value,
            "funding_needed_to_floor": max(s.minimum_cash.value - cash_end, 0),
            "interest_coverage": ebit / interest if interest > 0 else None,
            "debt_to_ebitda": debt_end / ebitda if ebitda > 0 else None,
            "status": "unfunded_cash_shortfall" if cash_end < 0 else "below_cash_floor" if cash_end < s.minimum_cash.value else "conditional",
            "assumption_source": p.source,
        })
        cash, debt, inventory, nwc = cash_end, debt_end, inv_end, nwc_end
        receivables, payables = ar_end, ap_end
        if cash < 0:
            break
    contract_results = []
    for contract in s.contracts:
        row = next((r for r in rows if r["period_end"] == contract.test_date.isoformat()), None)
        value = row[contract.metric] if row else None
        if value is None:
            status = "not_tested"
        else:
            complies = value >= contract.threshold if contract.relation == "at_least" else value <= contract.threshold
            complies = complies or abs(value - contract.threshold) <= 8 * 2**-52 * max(
                abs(value), abs(contract.threshold))
            status = "within_input_threshold" if complies else "outside_input_threshold"
        contract_results.append({**contract.model_dump(mode="json"), "value": value, "status": status,
                                 "reason": "no projection at test date or ratio denominator is not meaningful" if value is None else ""})
    return rows, contract_results


def _reverse(s):
    from scipy.optimize import root_scalar

    target = s.reverse
    snapshot = s.model_dump(mode="json")
    snapshot["reverse"] = None
    candidate_conflicts = {}

    def objective(driver_value):
        changed = deepcopy(snapshot)
        changed["periods"][target.period_index][target.driver] = float(driver_value)
        candidate = Scenario.model_validate(changed)
        actual_bridge, conflicts = _checked_actual_bridge(candidate)
        if conflicts:
            candidate_conflicts[float(driver_value)] = {"driver_value": float(driver_value),
                "actual_bridge": actual_bridge, "conflicts": conflicts}
        rows, _ = _project(candidate)
        row = next((r for r in rows if r["period_end"] == target.test_date.isoformat()), None)
        if row is None:
            raise ValueError("an earlier unfunded period prevents projection at reverse test_date")
        # Use monetary-operation precision, including cancellation at a zero cash target.
        roundoff = sum(ulp(x) for x in (target.target_cash, s.opening.cash,
                       s.opening.receivables, s.opening.inventory, s.opening.payables))
        roundoff += sum(ulp(r[key]) for r in rows if r["period_end"] <= row["period_end"]
                        for key in ("revenue", "cost_of_sales", "ebitda", "depreciation",
                                    "cash_interest", "cash_taxes", "nwc_end", "delta_nwc", "cfo",
                                    "cash_begin", "capex", "drawdown", "principal", "dividends"))
        return row["cash_end"] - target.target_cash, 8 * roundoff

    low, high = target.bounds
    (a, a_roundoff), (b, b_roundoff) = objective(low), objective(high)
    a_zero, b_zero = abs(a) <= a_roundoff, abs(b) <= b_roundoff
    if a_zero and b_zero:
        return {"status": "not_identified", "definition": target.definition,
                "bounds": [low, high], "endpoint_cash_residuals": [a, b],
                "candidate_conflicts": list(candidate_conflicts.values()),
                "reason": "both bounds meet the cash target within floating-point precision; no unique driver boundary established"}
    if not (a_zero or b_zero) and (a > 0) == (b > 0):
        return {"status": "not_bracketed", "definition": target.definition,
                "bounds": [low, high], "endpoint_cash_residuals": [a, b],
                "candidate_conflicts": list(candidate_conflicts.values()),
                "reason": "no sign change within supplied bounds; no failure boundary established"}
    if a_zero or b_zero:
        root, converged = (low if a_zero else high), True
    else:
        solution = root_scalar(lambda value: objective(value)[0], bracket=(low, high), method="brentq", xtol=ulp(0.0))
        root, converged = float(solution.root), solution.converged
    changed = deepcopy(snapshot)
    changed["periods"][target.period_index][target.driver] = root
    candidate = Scenario.model_validate(changed)
    actual_bridge, conflicts = _checked_actual_bridge(candidate)
    rows, contracts = _project(candidate)
    cash_residual = objective(root)[0]
    return {"status": "converged" if converged else "not_converged",
            "driver": target.driver, "period_index": target.period_index,
            "driver_value": root, "test_date": target.test_date.isoformat(),
            "target_cash": target.target_cash, "cash_residual": cash_residual,
            "bounds": [low, high], "endpoint_cash_residuals": [a, b],
            "definition": target.definition, "source": target.source,
            "rows": rows, "contracts": contracts,
            "actual_bridge": actual_bridge, "actual_conflicts": conflicts,
            "candidate_conflicts": list(candidate_conflicts.values()),
            "limitation": "A conditional cash boundary, not a default probability or a most-likely scenario."}


def run(input_dict):
    s = Scenario.model_validate(input_dict)
    actual_bridge, conflicts = _checked_actual_bridge(s)
    rows, contracts = _project(s)
    result = {
        "method": METHOD, "as_of": s.as_of.isoformat(),
        "input_snapshot": s.model_dump(mode="json"),
        "currency": s.currency, "amount_scale": s.amount_scale,
        "path_basis": s.path_basis, "actual_bridge": actual_bridge,
        "assumptions": [
            f"Path basis: {s.path_basis}; the supplied complete periods are retained.",
            f"Opening balances: {s.opening.source} (available {s.opening.available_at}).",
            f"Minimum operating cash {s.minimum_cash.value}: {s.minimum_cash.source} (available {s.minimum_cash.available_at}).",
            "All sales use the supplied receivable-days proxy; inventory uses cost-of-sales days.",
            "Cost of sales includes its allocated depreciation and amortization; fixed_cash_cost excludes all costs already in cost of sales.",
            "Depreciation is total P&L depreciation and amortization; its cost-of-sales portion is added back once for EBITDA.",
            "Supplier purchases exclude internal production cash conversion and current production depreciation; inventory depreciation change is ending less opening embedded depreciation and amortization.",
            f"Payables use the explicitly selected {s.payables_denominator} denominator; cost_of_sales is a cost proxy, not supplier purchases.",
            "Interest uses opening debt for actual period days; explicit borrowing and principal payments occur at period end.",
            "Cash tax equals max(EBIT minus cash interest, 0) times the supplied rate; no immediate loss refund.",
            "CFO adds back P&L depreciation and the net change of depreciation in inventory; it includes interest and cash tax.",
            *[f"{p.start}/{p.end}: {p.source} (available {p.available_at})" for p in s.periods],
        ],
        "limitations": [
            "Industrial operating-cash model; not a bank or insurer model and not a complete balance-sheet forecast.",
            "End-period turnover proxies do not measure intra-period liquidity or seasonality.",
            "No automatic refinancing, unused-facility draw, asset sale, tax loss carryforward, FX or acquisition effects.",
            "Internal production cash conversion is paid in-period; no payroll payable changes or noncash inventory movements other than depreciation and amortization.",
            "Supplier purchases and payables cover inventory inputs only, with no VAT, prepayments, capital payables or noncash supplier settlements.",
            "Negative cash denotes an unfunded gap; subsequent periods are not projected until a funding plan is supplied.",
            "A threshold result uses the supplied definition and test date; it is not a legal default conclusion.",
        ],
        "rows": rows, "contracts": contracts,
        "unprojected_periods": len(s.periods) - len(rows),
    }
    if not s.realized:
        result["limitations"].append("Cumulative actual inputs not_supplied; this mathematical path has not been reconciled to realized amounts.")
    else:
        result["limitations"].append("Realized amounts use the scenario entity, currency and amount_scale; same_scope is the caller's evidence declaration, not script verification.")
        result["limitations"].append("actual_bridge compares cumulative amounts with supplied period totals only; it does not construct remaining Periods, infer volume or rebase the cash path.")
        gaps = [f"period {r['period_index']} {r['metric']} {r['status']}" for r in actual_bridge
                if r["status"] != "known" and s.periods[r["period_index"]].start <= s.as_of]
        if gaps:
            result["limitations"].append("Actual bridge incomplete: " + "; ".join(gaps) + "; unknown or incomparable inputs are not replaced with zero.")
    if conflicts:
        result["assumptions"].append("Counterfactual replay retains the original period assumptions despite sourced cumulative conflicts.")
        result["limitations"].extend("Counterfactual conflict: " + c + "; this is not a reconciled forward forecast." for c in conflicts)
    if s.reverse:
        result["reverse"] = _reverse(s)
        reverse = result["reverse"]
        if reverse["candidate_conflicts"]:
            result["assumptions"].append("Counterfactual reverse retains evaluated candidates despite sourced cumulative conflicts; their actual bridges are separate from the baseline bridge.")
            for candidate in reverse["candidate_conflicts"]:
                result["limitations"].extend(f"Counterfactual reverse candidate {s.reverse.driver}={candidate['driver_value']}: " + c
                    + "; this is not a reconciled forward forecast." for c in candidate["conflicts"])
        result["limitations"].extend(f"Counterfactual reverse root {s.reverse.driver}={reverse['driver_value']}: " + c
            + "; this is not a reconciled forward forecast." for c in reverse.get("actual_conflicts", []))
    return result


def to_workpaper_result(result, id, label, input_refs, evidence):
    return {"id": id, "label": label, "method": result["method"], "as_of": result["as_of"],
            "input_refs": input_refs, "evidence": evidence, "assumptions": result["assumptions"],
            "limitations": result["limitations"], "artifact": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(json.loads(args.input.read_text(encoding="utf-8-sig")))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
