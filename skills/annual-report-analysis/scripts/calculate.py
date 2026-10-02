"""Deterministic arithmetic with financial-context checks and Excel equivalents."""
from datetime import timedelta
from decimal import Decimal

from workpaper import Workpaper


def evaluate(w: Workpaper):
    records = {f.id: f for f in w.facts}
    values = {f.id: f.value * f.context.scale if f.value is not None else None for f in w.facts}
    results = []
    for c in w.calculations:
        inputs = [records[t.ref] for t in c.terms]
        error = context_error(c, inputs)
        v = [values[t.ref] for t in c.terms]
        reason = error or ("missing input; not replaced with zero" if None in v else "")
        result = None
        if not reason:
            if c.op in ("ratio", "growth") and (v[1] == 0 or (c.denominator == "positive" and v[1] < 0)):
                reason = "zero or non-positive denominator; ratio is not meaningful"
            elif c.op == "growth" and (v[1] <= 0 or v[0] < 0):
                reason = "loss/negative growth base; use absolute movement and explain the transition"
            elif c.op == "sum":
                result = sum(x * t.weight for x, t in zip(v, c.terms))
            elif c.op == "difference":
                result = v[0] - v[1]
            elif c.op == "average_balance":
                result = (v[0] + v[1]) / 2
            elif c.op == "product":
                result = v[0] * v[1]
            elif c.op == "ratio":
                result = v[0] / v[1]
            elif c.op == "growth":
                result = (v[0] - v[1]) / v[1]
            if result is not None:
                result *= c.multiplier
        values[c.id] = result
        records[c.id] = c
        results.append({"id": c.id, "value": str(result / c.context.scale) if result is not None else None,
                        "normalized": str(result) if result is not None else None,
                        "status": "calculated" if result is not None else "not_calculated", "reason": reason})
    checks = []
    for r in w.reconciliations:
        a, b = values[r.actual], values[r.expected]
        ra, rb = records[r.actual], records[r.expected]
        same = reconciliation_matches(ra, rb)
        residual = a - b if a is not None and b is not None and same else None
        status = "not_tested" if residual is None else "within_input_tolerance" if abs(residual) <= r.tolerance else "unexplained_difference"
        checks.append({"id": r.id, "residual": str(residual) if residual is not None else None,
                       "status": status, "basis": r.basis,
                       "reason": "incompatible financial contexts" if not same else "missing or unavailable input" if residual is None else ""})
    return {"calculations": results, "reconciliations": checks}


def reconciliation_matches(a, b):
    ca, cb = a.context, b.context
    same = (ca.entity, ca.scope, ca.basis, ca.currency, ca.measure, ca.physical_unit, ca.end) == (cb.entity, cb.scope, cb.basis, cb.currency, cb.measure, cb.physical_unit, cb.end)
    periods_match = (ca.aggregation, ca.start) == (cb.aggregation, cb.start)
    closing_bridge = any(getattr(bridge, "period_rule", None) == "rollforward"
                         and balance.context.aggregation == "instant" and balance.context.start is None
                         for bridge, balance in ((a, b), (b, a)))
    return same and (periods_match or closing_bridge)


def context_error(c, inputs):
    ctx = [r.context for r in inputs]
    out = c.context
    if c.op != "sum" and len(inputs) != 2:
        return "operation requires two inputs"
    if any(not t.weight.is_finite() for t in c.terms) or not c.multiplier.is_finite():
        return "non-finite coefficient"
    if c.op != "sum" and any(t.weight != 1 for t in c.terms):
        return "weights apply only to sum"
    if any((x.entity, x.scope, x.basis) != (out.entity, out.scope, out.basis) for x in ctx):
        return "entity, consolidation scope or accounting basis mismatch; build a documented adjustment bridge first"
    dimensions = {(x.measure, x.currency, x.physical_unit) for x in ctx}
    if c.op != "product" and len(dimensions) != 1:
        return "incompatible measures or currencies"
    if c.op in ("sum", "difference", "average_balance") and (out.measure, out.currency, out.physical_unit) != (ctx[0].measure, ctx[0].currency, ctx[0].physical_unit):
        return "output must retain input dimension"
    if c.op in ("ratio", "growth") and out.measure not in ("ratio", "days"):
        return "division output must be a ratio or explicitly defined turnover days"
    if c.op == "product":
        nonratio = [x for x in ctx if x.measure != "ratio"]
        if len(nonratio) > 1 or (nonratio and (out.measure, out.currency) != (nonratio[0].measure, nonratio[0].currency)):
            return "product supports a quantity multiplied by a dimensionless driver"
        if not nonratio and out.measure != "ratio":
            return "two ratios must produce a ratio"
    if c.op == "average_balance":
        if not out.start or any(x.aggregation != "instant" for x in ctx):
            return "average balance requires two actual instant balances and a defined period"
        if sorted(x.end for x in ctx) != [out.start - timedelta(days=1), out.end]:
            return "average balance requires beginning and ending balances; ending balance cannot substitute"
        if not getattr(inputs[0], "concept", None) or getattr(inputs[0], "concept", None) != getattr(inputs[1], "concept", None):
            return "average balance inputs must refer to the same balance concept"
        return ""
    if c.period_rule == "same" and any((x.start, x.end) != (out.start, out.end) for x in ctx):
        return "period mismatch"
    if c.period_rule == "comparison":
        if len(ctx) != 2 or ctx[0].end <= ctx[1].end or ctx[0].aggregation != ctx[1].aggregation:
            return "comparison requires current and earlier comparable periods"
        if bool(ctx[0].start) != bool(ctx[1].start):
            return "cannot compare a period with an instant"
        if ctx[0].start and abs((ctx[0].end-ctx[0].start).days - (ctx[1].end-ctx[1].start).days) > 1:
            return "period lengths differ; define a separate normalized comparison"
    if c.period_rule == "rollforward":
        if not out.start:
            return "rollforward requires a start date"
        for x in ctx:
            if x.aggregation == "instant":
                if x.end not in (out.start-timedelta(days=1), out.end):
                    return "balance outside rollforward boundaries"
            elif (x.start, x.end) != (out.start, out.end):
                return "movement outside rollforward period"
    if c.period_rule == "balance_flow":
        if any(x.end != out.end for x in ctx):
            return "balance and flow end dates differ"
        if any(x.start != out.start for x in ctx if x.aggregation != "instant"):
            return "balance/flow period mismatch"
    if c.period_rule == "forecast":
        if not any(getattr(r, "state", None) == "assumption" or r.context.aggregation == "assumption" for r in inputs):
            return "forecast requires an explicit assumption input"
    if c.op == "growth" and c.period_rule != "comparison":
        return "growth requires a comparative period"
    return ""


def excel_expression(c, cells):
    refs = [cells[t.ref] for t in c.terms]
    if c.op == "sum":
        body = "+".join(f"({ref}*{t.weight})" for ref, t in zip(refs, c.terms))
    elif c.op == "difference":
        body = f"({refs[0]}-{refs[1]})"
    elif c.op == "average_balance":
        body = f"AVERAGE({refs[0]},{refs[1]})"
    elif c.op == "product":
        body = f"({refs[0]}*{refs[1]})"
    elif c.op == "ratio":
        body = f"({refs[0]}/{refs[1]})"
    else:
        body = f"(({refs[0]}-{refs[1]})/{refs[1]})"
    return f"=({body})*{c.multiplier}"
