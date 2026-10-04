"""Select supplied numeric method bands and propagate independent linear score intervals."""
import argparse
from datetime import date
from fractions import Fraction
import json
from pathlib import Path
from typing import Annotated, Literal

import portion as P
from pydantic import Field, TypeAdapter

from calculate import evaluate
from workpaper import QuantitativeResult, Record, Workpaper


Text = Annotated[str, Field(min_length=1)]
METHOD = "linear_score_bounds_v1"
VERSION = "1.1"


class Bounds(Record):
    lower: Text
    upper: Text
    left_closed: bool = Field(strict=True)
    right_closed: bool = Field(strict=True)


class Node(Record):
    id: Text
    evidence: list[Text] = Field(default_factory=list)
    note: Text


class Leaf(Node):
    mode: Literal["leaf"] = "leaf"
    bounds: Bounds | None
    state: Literal["method_band", "assumption", "missing"]
    input_refs: list[Text] = Field(default_factory=list)


class Band(Record):
    id: Text
    lower: Text | None
    upper: Text | None
    left_closed: bool = Field(strict=True)
    right_closed: bool = Field(strict=True)
    score: Bounds


class NumericBand(Node):
    mode: Literal["numeric_band"]
    input_ref: Text
    threshold_scale: Text
    bands: list[Band] = Field(min_length=1)


class Term(Record):
    node_ref: Text
    weight_ref: Text


class Weighted(Node):
    mode: Literal["weighted_mean"]
    terms: list[Term] = Field(min_length=1)
    basis_state: Literal["reported", "assumption"]
    joint_basis: Literal["independent", "unknown_or_shared"]


class Convex(Node):
    mode: Literal["unknown_convex_weights"]
    children: list[Text] = Field(min_length=1)
    basis_state: Literal["assumption"]
    joint_basis: Literal["independent", "unknown_or_shared"]


class Unresolved(Node):
    mode: Literal["unresolved"]
    children: list[Text] = Field(min_length=1)


class Spec(Record):
    method_evidence: list[Text] = Field(min_length=1)
    nodes: list[Leaf | NumericBand | Weighted | Convex | Unresolved] = Field(min_length=1)
    outputs: list[Text] = Field(min_length=1)


def _interval(b):
    result = P.from_data([(b.left_closed, Fraction(b.lower), Fraction(b.upper), b.right_closed)])
    if result.empty:
        raise ValueError("score bounds must form a nonempty finite interval")
    return result


def _weighted(terms):
    total = sum(w for w, _ in terms)
    return P.from_data([(all(i.left == P.CLOSED for _, i in terms),
                         sum(w * i.lower for w, i in terms) / total,
                         sum(w * i.upper for w, i in terms) / total,
                         all(i.right == P.CLOSED for _, i in terms))])


def _numeric_band(node, value):
    if not node.evidence:
        raise ValueError(f"{node.id}: numeric bands require original table evidence")
    scale = Fraction(node.threshold_scale)
    if scale <= 0:
        raise ValueError(f"{node.id}: threshold scale must be positive")
    if len({band.id for band in node.bands}) != len(node.bands):
        raise ValueError(f"{node.id}: duplicate band id")
    if value is None:
        return None, "company input unresolved; no band selected or zero inserted", []
    matches = []
    for band in node.bands:
        domain = P.from_data([(band.left_closed if band.lower is not None else False,
                              Fraction(band.lower) * scale if band.lower is not None else -P.inf,
                              Fraction(band.upper) * scale if band.upper is not None else P.inf,
                              band.right_closed if band.upper is not None else False)])
        if domain.empty:
            raise ValueError(f"{node.id}/{band.id}: empty numeric threshold interval")
        score = _interval(band.score)
        if value in domain:
            matches.append((band.id, score))
    ids = [id for id, _ in matches]
    if len(matches) != 1:
        return None, "no matching numeric band" if not matches else "overlapping numeric bands; no unique selection", ids
    return matches[0][1], "", ids


def run(workpaper, spec, *, id, label, as_of):
    w = workpaper if isinstance(workpaper, Workpaper) else Workpaper.model_validate(workpaper)
    s = Spec.model_validate(spec)
    cutoff = TypeAdapter(date).validate_python(as_of)
    if cutoff > w.mandate.cutoff:
        raise ValueError("result cutoff exceeds workpaper cutoff")
    records = {f.id: f for f in w.facts}
    values = {f.id: Fraction(f.value) * Fraction(f.context.scale) if f.value is not None else None for f in w.facts}
    support = {f.id: set(f.evidence) for f in w.facts}
    states = {f.id: f.state for f in w.facts}
    input_assumptions = {f.id: [f"{f.id}: {f.note}"] if f.state == "assumption" else [] for f in w.facts}
    computed = {r["id"]: r for r in evaluate(w)["calculations"]}
    for c in w.calculations:
        records[c.id] = c
        value = computed[c.id]["normalized"]
        values[c.id] = Fraction(value) if value is not None else None
        support[c.id] = set().union(*(support[t.ref] for t in c.terms))
        states[c.id] = computed[c.id]["status"]
        input_assumptions[c.id] = list(dict.fromkeys(a for t in c.terms for a in input_assumptions[t.ref]))
    evidence_ids = {e.id for e in w.evidence}
    evidence = set(s.method_evidence)
    used_refs, intervals, variables, rows, assumptions = set(), {}, {}, [], []
    for n in s.nodes:
        if n.id in intervals:
            raise ValueError(f"duplicate score node: {n.id}")
        children = [t.node_ref for t in n.terms] if isinstance(n, Weighted) else getattr(n, "children", [])
        if any(ref not in intervals for ref in children):
            raise ValueError(f"{n.id}: children must refer to earlier score nodes")
        refs = n.input_refs if isinstance(n, Leaf) else [n.input_ref] if isinstance(n, NumericBand) else [t.weight_ref for t in n.terms] if isinstance(n, Weighted) else []
        if any(ref not in values for ref in refs):
            raise ValueError(f"{n.id}: unknown workpaper input reference")
        used_refs.update(refs)
        evidence.update(n.evidence)
        for ref in refs:
            evidence.update(support[ref])
        result, reason, normalizer, active, matched = None, "", None, children, []
        if isinstance(n, (Leaf, NumericBand)):
            if isinstance(n, NumericBand):
                result, reason, matched = _numeric_band(n, values[n.input_ref])
            elif n.bounds is None:
                reason = "score interval unresolved; not replaced with zero"
            elif n.state == "method_band" and any(values[ref] is None for ref in refs):
                reason = "method band has missing company input; no automatic band selection"
            else:
                if not n.evidence:
                    raise ValueError(f"{n.id}: a supplied interval requires evidence or assumption evidence")
                result = _interval(n.bounds)
            variables[n.id] = ({n.id} | {f"input:{ref}" for ref in refs}) if result is None or result != P.singleton(result.lower) else set()
        elif isinstance(n, Unresolved):
            reason = "aggregation rule unresolved; no weights or linear form supplied"
        else:
            terms = []
            if isinstance(n, Weighted):
                if any(records[ref].context.measure != "ratio" for ref in refs):
                    raise ValueError(f"{n.id}: weights must be dimensionless ratio records")
                weights = [values[t.weight_ref] for t in n.terms]
                if any(weight is None for weight in weights):
                    reason = "missing weight; not dropped or replaced with zero"
                elif any(weight < 0 for weight in weights):
                    raise ValueError(f"{n.id}: only nonnegative weights are supported")
                else:
                    normalizer = sum(weights)
                    if normalizer == 0:
                        raise ValueError(f"{n.id}: total weight must be positive")
                    active = [t.node_ref for t, weight in zip(n.terms, weights) if weight > 0]
                    terms = [(weight, intervals[t.node_ref]) for t, weight in zip(n.terms, weights) if weight > 0]
            if not reason and any(intervals[ref] is None for ref in active):
                reason = "unresolved contributing score; positive or unknown weights cannot be omitted"
            if not reason and n.joint_basis != "independent":
                reason = "joint feasible set unknown or shared; no exact attainable interval claimed"
            seen = set()
            for ref in active:
                if not reason and seen & variables[ref]:
                    reason = "shared uncertain inputs; independent child feasible sets not established"
                seen.update(variables[ref])
            if not reason:
                if isinstance(n, Weighted):
                    result = _weighted(terms)
                else:
                    result = P.empty()
                    for ref in children:
                        result |= intervals[ref]
                    result = result.enclosure
        if not isinstance(n, (Leaf, NumericBand)):
            variables[n.id] = set().union(*(variables[ref] for ref in active))
            if isinstance(n, Convex):
                variables[n.id].add(f"weights:{n.id}")
            if result is not None and result == P.singleton(result.lower):
                variables[n.id] = set()
        intervals[n.id] = result
        if isinstance(n, Convex):
            assumptions.append(f"{n.id}: unknown child weights are nonnegative and sum to one; {n.note}")
        elif getattr(n, "basis_state", None) == "assumption" or getattr(n, "state", None) == "assumption":
            assumptions.append(f"{n.id}: {n.note}")
        rows.append({"id": n.id, "mode": n.mode, "children": children, "input_refs": refs,
                     "state": "method_band" if isinstance(n, NumericBand) else getattr(n, "state", getattr(n, "basis_state", "unresolved")),
                     "joint_basis": getattr(n, "joint_basis", None), "note": n.note,
                     "normalizer_exact": str(normalizer) if normalizer is not None else None,
                     "lower_exact": str(result.lower) if result is not None else None,
                     "upper_exact": str(result.upper) if result is not None else None,
                     "lower_closed": result.left == P.CLOSED if result is not None else None,
                     "upper_closed": result.right == P.CLOSED if result is not None else None,
                     "range_text": P.to_string(result, conv=str) if result is not None else None,
                     "status": "unresolved" if result is None else "point_given_inputs" if result == P.singleton(result.lower) else "range_given_inputs",
                     "matched_band_ids": matched,
                     "input_normalized_exact": str(values[n.input_ref]) if isinstance(n, NumericBand) and values[n.input_ref] is not None else None,
                     "reason": reason, "selected_output": n.id in s.outputs})
    if set(s.outputs) - intervals.keys():
        raise ValueError("outputs must refer to score nodes")
    if evidence - evidence_ids:
        raise ValueError("unknown method or node evidence reference")
    sources = {source.id: source for source in w.sources}
    for e in w.evidence:
        if e.id in evidence and sources[e.source].published and sources[e.source].published > cutoff:
            raise ValueError(f"{e.id}: source published after result cutoff")
    return QuantitativeResult(
        id=id, label=label, method=METHOD, as_of=cutoff, input_refs=sorted(used_refs), evidence=sorted(evidence),
        assumptions=["Composed intervals require the declared independent feasible sets; no shared constraints are solved.",
                     *dict.fromkeys(a for ref in sorted(used_refs) for a in input_assumptions[ref]), *assumptions],
        limitations=["Numeric lookup matches supplied thresholds and retains their full score intervals; original tables, input definitions and manually supplied leaves are not verified. No interpolation, official model or rating mapping is performed.",
                     "Exact rational endpoints describe the supplied inputs; referenced Decimal calculations retain their existing calculation precision.",
                     "Missing rules, contributing inputs or unestablished joint feasibility remain unresolved; no zero or equal weights are inserted."],
        artifact={"method": METHOD, "version": VERSION, "as_of": cutoff.isoformat(),
                  "dependency_versions": {"portion": P.__version__}, "rows": rows,
                  "input_snapshot": {"spec": s.model_dump(mode="json"), "methods": w.mandate.methods,
                      "resolved_inputs": {ref: {"normalized_exact": str(values[ref]) if values[ref] is not None else None,
                          "state": states[ref], "context": records[ref].context.model_dump(mode="json"),
                          "note": getattr(records[ref], "note", getattr(records[ref], "interpretation", "")),
                          "calculation_reason": computed[ref]["reason"] if ref in computed else "",
                          "assumptions": input_assumptions[ref],
                          "evidence": sorted(support[ref])} for ref in sorted(used_refs)},
                      "sources": [source.model_dump(mode="json") for source in w.sources if any(e.id in evidence and e.source == source.id for e in w.evidence)]}},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workpaper", type=Path)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--id", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    w = Workpaper.model_validate_json(args.workpaper.read_text(encoding="utf-8-sig"))
    result = run(w, json.loads(args.spec.read_text(encoding="utf-8-sig")), id=args.id, label=args.label, as_of=args.as_of)
    output = result.model_dump_json(indent=2)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
