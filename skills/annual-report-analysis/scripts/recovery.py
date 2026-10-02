"""Distribute one legal estate across documented, nonoverlapping collateral pools."""
import argparse
from datetime import date
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from workpaper import QuantitativeResult, Record


Amount = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Text = Annotated[str, Field(min_length=1)]
METHOD = "single_entity_recovery_waterfall"
VERSION = "1.0"


class CollateralPool(Record):
    id: Text
    label: Text
    value: Amount
    costs: Amount
    evidence: list[Text] = Field(min_length=1)


class Claim(Record):
    id: Text
    obligation_id: Text
    label: Text
    amount: Amount
    priority: int = Field(gt=0, strict=True)
    collateral_pool: Text | None = None
    deficiency_treatment: Literal["not_applicable", "nonrecourse", "general"]
    deficiency_priority: int | None = Field(default=None, gt=0, strict=True)
    evidence: list[Text] = Field(min_length=1)

    @model_validator(mode="after")
    def recourse_matches_claim(self):
        if self.collateral_pool is None:
            if self.deficiency_treatment != "not_applicable" or self.deficiency_priority is not None:
                raise ValueError("unsecured claims require not_applicable deficiency treatment")
        elif self.deficiency_treatment == "general":
            if self.deficiency_priority is None:
                raise ValueError("general recourse requires a supported deficiency_priority")
        elif self.deficiency_treatment != "nonrecourse" or self.deficiency_priority is not None:
            raise ValueError("secured claims require explicit general or nonrecourse treatment")
        return self


class RecoveryInput(Record):
    id: Text
    label: Text
    entity: Text
    as_of: date
    currency: Text
    unit: Text
    quantum: Decimal = Field(gt=0, allow_inf_nan=False)
    scope: Literal["single_entity_nonoverlapping_pools"]
    unencumbered_value: Amount
    estate_costs: Amount
    value_basis: Text
    priority_basis: Text
    input_refs: list[Text]
    evidence: list[Text] = Field(min_length=1)
    assumptions: list[Text] = Field(min_length=1)
    pools: list[CollateralPool]
    claims: list[Claim] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_estate(self):
        for label, values in (
            ("pool", [p.id for p in self.pools]),
            ("claim", [c.id for c in self.claims]),
            ("economic obligation", [c.obligation_id for c in self.claims]),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label}: double recovery is unsupported")
        pool_ids = {p.id for p in self.pools}
        if pool_ids & {"general", "all"}:
            raise ValueError("pool ids general and all are reserved for estate output")
        for claim in self.claims:
            if claim.collateral_pool is not None and claim.collateral_pool not in pool_ids:
                raise ValueError(f"unknown collateral pool: {claim.collateral_pool}")
        amounts = [self.unencumbered_value, self.estate_costs]
        amounts += [a for p in self.pools for a in (p.value, p.costs)]
        amounts += [c.amount for c in self.claims]
        if any((Fraction(a) / Fraction(self.quantum)).denominator != 1 for a in amounts):
            raise ValueError("all amounts must be exact multiples of quantum")
        return self


def calculate_recovery(data: RecoveryInput) -> QuantitativeResult:
    """Use integer cash units; round pari passu shares by largest remainder."""
    def units(amount):
        return int(Fraction(amount) / Fraction(data.quantum))

    def money(value):
        with localcontext() as context:
            context.prec = max(28, len(str(abs(value))) + len(data.quantum.as_tuple().digits) + 2)
            return format(Decimal(value) * data.quantum, "f")

    rows = []
    claims = {c.id: c for c in data.claims}
    secured = {c.id: 0 for c in data.claims}
    unsecured = {c.id: 0 for c in data.claims}
    rounding = "按 quantum 分配；同顺位最大余数法；余数相同按 obligation_id 排序"
    common_assumptions = "；".join(data.assumptions + [data.priority_basis, data.value_basis])

    def row(kind, pool, claim_id, raw_input, formula, result, evidence, **details):
        rows.append({
            "kind": kind, "entity": data.entity, "pool": pool, "claim_id": claim_id,
            "currency": data.currency, "unit": data.unit,
            "raw_input": raw_input, "assumptions": common_assumptions,
            "formula": formula, "result": money(result),
            "evidence": "; ".join(evidence), **details,
        })

    def pay_costs(pool, available, costs, evidence):
        paid = min(available, costs)
        row("cost", pool, "", f"available={money(available)}; costs={money(costs)}",
            "min(available, costs)", paid, evidence, unpaid=money(costs - paid))
        return available - paid, paid

    def distribute(pool, available, entries, recovered):
        for rank in sorted({rank for _, _, rank in entries}):
            group = [(cid, amount) for cid, amount, priority in entries if priority == rank]
            total = sum(amount for _, amount in group)
            budget = min(available, total)
            paid = {cid: budget * amount // total if total else 0 for cid, amount in group}
            order = sorted(group, key=lambda item: (
                -(budget * item[1] % total) if total else 0,
                claims[item[0]].obligation_id,
            ))
            for cid, _ in order[:budget - sum(paid.values())]:
                paid[cid] += 1
            for cid, amount in group:
                recovered[cid] += paid[cid]
                row("allocation", pool, cid,
                    f"available={money(available)}; rank_claims={money(total)}; claim={money(amount)}",
                    "min(available, rank_claims) * claim / rank_claims (zero rank_claims: 0); " + rounding,
                    paid[cid], claims[cid].evidence, priority=rank,
                    outstanding_in_pool=money(amount - paid[cid]))
            available -= budget
        return available

    general_entries = [(c.id, units(c.amount), c.priority) for c in data.claims if c.collateral_pool is None]
    surplus = 0
    total_costs = 0
    for pool in data.pools:
        available, costs_paid = pay_costs(pool.id, units(pool.value), units(pool.costs), pool.evidence)
        total_costs += costs_paid
        pool_claims = [c for c in data.claims if c.collateral_pool == pool.id]
        remainder = distribute(pool.id, available,
                               [(c.id, units(c.amount), c.priority) for c in pool_claims], secured)
        surplus += remainder
        row("surplus_transfer", pool.id, "",
            f"net_pool_value={money(available)}; secured_paid={money(available - remainder)}",
            "net_pool_value - secured_paid; transfer to same entity general estate",
            remainder, pool.evidence)
        for claim in pool_claims:
            deficiency = units(claim.amount) - secured[claim.id]
            allowed = deficiency if claim.deficiency_treatment == "general" else 0
            if claim.deficiency_treatment == "general":
                general_entries.append((claim.id, deficiency, claim.deficiency_priority))
            row("deficiency", pool.id, claim.id,
                f"claim={money(units(claim.amount))}; secured_paid={money(secured[claim.id])}",
                "claim - secured_paid if supported general recourse; otherwise 0",
                allowed, claim.evidence, treatment=claim.deficiency_treatment,
                unrecoverable_here=money(deficiency - allowed))

    general_value = units(data.unencumbered_value) + surplus
    available, costs_paid = pay_costs("general", general_value, units(data.estate_costs), data.evidence)
    total_costs += costs_paid
    residual = distribute("general", available, general_entries, unsecured)
    for claim in data.claims:
        principal = units(claim.amount)
        recovery = secured[claim.id] + unsecured[claim.id]
        with localcontext() as context:
            context.prec = 28
            rate = format(Decimal(recovery) / Decimal(principal), ".10f") if principal else None
        row("claim_total", claim.collateral_pool or "general", claim.id,
            f"original_claim={money(principal)}; secured={money(secured[claim.id])}; general={money(unsecured[claim.id])}",
            "secured + general; recovery_rate = total / original_claim (zero claim: undefined)",
            recovery, claim.evidence, obligation_id=claim.obligation_id,
            original_claim=money(principal), secured=money(secured[claim.id]),
            general=money(unsecured[claim.id]), unpaid=money(principal - recovery), recovery_rate=rate)
    gross = units(data.unencumbered_value) + sum(units(p.value) for p in data.pools)
    debt_paid = sum(secured.values()) + sum(unsecured.values())
    row("estate_residual", "general", "", f"gross={money(gross)}; costs_paid={money(total_costs)}; debt_paid={money(debt_paid)}",
        "gross - costs_paid - debt_paid", residual, data.evidence)
    row("reconciliation", "all", "", f"gross={money(gross)}; costs_paid={money(total_costs)}; debt_paid={money(debt_paid)}; residual={money(residual)}",
        "gross - costs_paid - debt_paid - residual", gross - total_costs - debt_paid - residual, data.evidence)
    evidence = list(dict.fromkeys(data.evidence + [e for p in data.pools for e in p.evidence]
                                 + [e for c in data.claims for e in c.evidence]))
    return QuantitativeResult(
        id=data.id, label=data.label, method=METHOD, as_of=data.as_of,
        input_refs=data.input_refs, evidence=evidence, assumptions=data.assumptions + [rounding],
        limitations=[
            "仅单一法人及互不重叠抵押池；不计算跨担保、多个池共享同一债权、代位权或集团合并回收。",
            "顺位、担保有效性、追索、估值、成本由输入证据支持；程序不作法律认定、不估计违约概率。",
            "抵押池费用仅由该池支付；未付费用不自动转为一般债权；需要不同费用优先权时本模型不适用。",
            "抵押剩余须可转同一法人一般财产；结果是该情景的名义分配，不包含时间折现或机构回收等级。",
        ],
        artifact={"rows": rows, "input_snapshot": data.model_dump(mode="json"),
                  "method": METHOD, "version": VERSION, "as_of": data.as_of.isoformat()},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = RecoveryInput.model_validate_json(args.input.read_text(encoding="utf-8"))
    output = calculate_recovery(data).model_dump_json(indent=2)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
