"""Offline operating-cash scenarios and a one-driver reverse stress calculation."""
import argparse
from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


METHOD = "operating_cash_scenario_v1"


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
    unit_variable_cost: float = Field(ge=0)
    fixed_cash_cost: float = Field(ge=0)
    depreciation: float = Field(ge=0)
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
    driver: Literal["volume", "unit_price", "unit_variable_cost", "fixed_cash_cost", "dso", "dio", "dpo"]
    bounds: tuple[float, float]
    test_date: date
    target_cash: float = Field(ge=0)
    definition: str = Field(min_length=1)


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

    @model_validator(mode="after")
    def periods_and_sources(self):
        previous = self.opening.date
        for p in self.periods:
            if p.start != previous + timedelta(days=1) or p.end < p.start:
                raise ValueError("forecast periods must be contiguous after the opening date")
            previous = p.end
        sourced = [self.opening, self.minimum_cash, *self.periods, *self.contracts]
        if self.reverse:
            sourced.append(self.reverse)
            if self.reverse.period_index >= len(self.periods):
                raise ValueError("reverse period_index is outside the forecast")
            low, high = self.reverse.bounds
            if low < 0 or low >= high:
                raise ValueError("reverse bounds must be increasing non-negative driver values")
            if self.reverse.test_date not in [p.end for p in self.periods]:
                raise ValueError("reverse test_date must be a forecast period end")
        if self.opening.available_at < self.opening.date:
            raise ValueError("opening actual balances cannot be public before their measurement date")
        if self.opening.date > self.as_of or any(x.available_at > self.as_of for x in sourced):
            raise ValueError("opening data and assumption sources must be available by as_of")
        return self


def _project(s):
    cash, debt = s.opening.cash, s.opening.debt
    inventory = s.opening.inventory
    nwc = s.opening.receivables + inventory - s.opening.payables
    rows = []
    for p in s.periods:
        days = (p.end - p.start).days + 1
        revenue = p.volume * p.unit_price
        cost = p.volume * p.unit_variable_cost
        ebitda = revenue - cost - p.fixed_cash_cost
        ebit = ebitda - p.depreciation
        interest = debt * p.interest_rate * days / s.interest_basis_days
        taxes = max(ebit - interest, 0) * p.tax_rate
        profit = ebit - interest - taxes
        ar_end = revenue * p.dso / days
        inv_end = cost * p.dio / days
        purchases = cost + inv_end - inventory
        if s.payables_denominator == "purchases" and purchases < 0:
            raise ValueError("negative implied purchases: supplied inventory path is not feasible")
        ap_base = cost if s.payables_denominator == "cost_of_sales" else purchases
        ap_end = ap_base * p.dpo / days
        nwc_end = ar_end + inv_end - ap_end
        delta_nwc = nwc_end - nwc
        cfo = profit + p.depreciation - delta_nwc
        debt_end = debt + p.drawdown - p.principal
        if debt_end < 0:
            raise ValueError("principal exceeds opening debt plus explicit drawdown")
        cash_end = cash + cfo - p.capex + p.drawdown - p.principal - p.dividends
        rows.append({
            "period_start": p.start.isoformat(), "period_end": p.end.isoformat(), "days": days,
            "revenue": revenue, "cost_of_sales": cost, "ebitda": ebitda, "ebit": ebit,
            "cash_interest": interest, "cash_taxes": taxes, "net_income": profit,
            "receivables_end": ar_end, "inventory_end": inv_end, "implied_purchases": purchases,
            "payables_end": ap_end, "nwc_end": nwc_end, "delta_nwc": delta_nwc,
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
            status = "within_input_threshold" if complies else "outside_input_threshold"
        contract_results.append({**contract.model_dump(mode="json"), "value": value, "status": status,
                                 "reason": "no projection at test date or ratio denominator is not meaningful" if value is None else ""})
    return rows, contract_results


def _reverse(s):
    from scipy.optimize import root_scalar

    target = s.reverse
    snapshot = s.model_dump(mode="json")
    snapshot["reverse"] = None

    def objective(driver_value):
        changed = deepcopy(snapshot)
        changed["periods"][target.period_index][target.driver] = float(driver_value)
        rows, _ = _project(Scenario.model_validate(changed))
        row = next((r for r in rows if r["period_end"] == target.test_date.isoformat()), None)
        if row is None:
            raise ValueError("an earlier unfunded period prevents projection at reverse test_date")
        return row["cash_end"] - target.target_cash

    low, high = target.bounds
    a, b = objective(low), objective(high)
    if a * b > 0:
        return {"status": "not_bracketed", "definition": target.definition,
                "bounds": [low, high], "endpoint_cash_residuals": [a, b],
                "reason": "no sign change within supplied bounds; no failure boundary established"}
    solution = root_scalar(objective, bracket=(low, high), method="brentq")
    changed = deepcopy(snapshot)
    changed["periods"][target.period_index][target.driver] = float(solution.root)
    rows, contracts = _project(Scenario.model_validate(changed))
    return {"status": "converged" if solution.converged else "not_converged",
            "driver": target.driver, "period_index": target.period_index,
            "driver_value": float(solution.root), "test_date": target.test_date.isoformat(),
            "target_cash": target.target_cash, "cash_residual": objective(solution.root),
            "bounds": [low, high], "endpoint_cash_residuals": [a, b],
            "definition": target.definition, "source": target.source,
            "rows": rows, "contracts": contracts,
            "limitation": "A conditional cash boundary, not a default probability or a most-likely scenario."}


def run(input_dict):
    s = Scenario.model_validate(input_dict)
    rows, contracts = _project(s)
    result = {
        "method": METHOD, "as_of": s.as_of.isoformat(),
        "input_snapshot": s.model_dump(mode="json"),
        "currency": s.currency, "amount_scale": s.amount_scale,
        "assumptions": [
            f"Opening balances: {s.opening.source} (available {s.opening.available_at}).",
            f"Minimum operating cash {s.minimum_cash.value}: {s.minimum_cash.source} (available {s.minimum_cash.available_at}).",
            "All sales use the supplied receivable-days proxy; inventory uses cost-of-sales days.",
            f"Payables use the explicitly selected {s.payables_denominator} denominator.",
            "Interest uses opening debt for actual period days; explicit borrowing and principal payments occur at period end.",
            "Cash tax equals max(EBIT minus cash interest, 0) times the supplied rate; no immediate loss refund.",
            "CFO includes interest and cash tax; cash distributions and borrowing are financing flows.",
            *[f"{p.start}/{p.end}: {p.source} (available {p.available_at})" for p in s.periods],
        ],
        "limitations": [
            "Industrial operating-cash model; not a bank or insurer model and not a complete balance-sheet forecast.",
            "End-period turnover proxies do not measure intra-period liquidity or seasonality.",
            "No automatic refinancing, unused-facility draw, asset sale, tax loss carryforward, FX or acquisition effects.",
            "Negative cash denotes an unfunded gap; subsequent periods are not projected until a funding plan is supplied.",
            "A threshold result uses the supplied definition and test date; it is not a legal default conclusion.",
        ],
        "rows": rows, "contracts": contracts,
        "unprojected_periods": len(s.periods) - len(rows),
    }
    if s.reverse:
        result["reverse"] = _reverse(s)
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
