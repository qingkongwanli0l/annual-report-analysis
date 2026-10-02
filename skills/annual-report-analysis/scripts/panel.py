"""Point-in-time industrial peers and one frozen out-of-time margin forecast."""
import argparse
from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path

import numpy as np
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


METHOD = "pit_margin_persistence_v1"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Record(Input):
    id: str
    entity: str
    period_start: date
    period_end: date
    available_at: AwareDatetime
    version: str
    industry: str
    accounting_basis: str
    currency: str
    revenue: float | None
    cost_of_sales: float | None
    total_assets: float | None
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def annual_period(self):
        if not 364 <= (self.period_end - self.period_start).days <= 365:
            raise ValueError("this concrete study requires 365/366-day annual periods")
        if self.available_at.date() < self.period_end:
            raise ValueError("annual actual figures cannot be available before their period end")
        return self


class Study(Input):
    as_of: AwareDatetime
    training_cutoff: AwareDatetime
    peer_period_end: date
    industry: str
    accounting_basis: str
    currency: str
    universe_definition: str = Field(min_length=1)
    records: list[Record]

    @model_validator(mode="after")
    def chronology(self):
        if self.training_cutoff >= self.as_of:
            raise ValueError("training_cutoff must precede as_of")
        if len({r.id for r in self.records}) != len(self.records):
            raise ValueError("record ids must be unique")
        keys = [(r.entity, r.period_end, r.available_at) for r in self.records]
        if len(set(keys)) != len(keys):
            raise ValueError("ambiguous versions at the same public availability time")
        return self


def features(record):
    gross = record.revenue - record.cost_of_sales if record.revenue is not None and record.cost_of_sales is not None else None
    margin = gross / record.revenue if gross is not None and record.revenue > 0 else None
    profitability = gross / record.total_assets if gross is not None and record.total_assets is not None and record.total_assets > 0 else None
    return {"gross_margin": margin, "gross_profit_to_assets": profitability}


def _scope(record, study):
    return (record.industry, record.accounting_basis, record.currency) == (study.industry, study.accounting_basis, study.currency)


def select_as_of(records, cutoff):
    selected = {}
    for record in sorted(records, key=lambda r: r.available_at):
        if record.available_at <= cutoff:
            selected[record.entity, record.period_end] = record
    return list(selected.values())


def run(input_dict):
    s = Study.model_validate(input_dict)
    # Select a vintage before applying its industry/basis classification.
    current = select_as_of(s.records, s.as_of)
    peers = [r for r in current if r.period_end == s.peer_period_end and _scope(r, s)]
    rows = [{"kind": "peer", "entity": r.entity, "record_id": r.id, "version": r.version,
             "available_at": r.available_at.isoformat(), "period_end": r.period_end.isoformat(),
             "source": r.source, **features(r)} for r in peers]
    values = [r["gross_profit_to_assets"] for r in rows if r["gross_profit_to_assets"] is not None]
    for row in rows:
        value = row["gross_profit_to_assets"]
        row["peer_n"] = len(values)
        row["gross_profitability_percentile"] = ((sum(x < value for x in values) + (sum(x == value for x in values) + 1) / 2) / len(values)) if value is not None else None

    # Historical predictors and outcomes are first-publication observations.
    first = {}
    for r in sorted(s.records, key=lambda r: r.available_at):
        first.setdefault((r.entity, r.period_end), r)
    by_start = {(r.entity, r.period_start): r for r in first.values()}
    if len(by_start) != len(first):
        raise ValueError("overlapping annual records have the same entity and period start")
    train, test, pending, excluded = [], [], [], []
    for origin in first.values():
        if origin.available_at > s.as_of or not _scope(origin, s):
            continue
        target = by_start.get((origin.entity, origin.period_end + timedelta(days=1)))
        x = features(origin)["gross_margin"]
        if x is None:
            excluded.append({"record_id": origin.id, "reason": "missing inputs or non-positive revenue"})
            continue
        if target is None or target.available_at > s.as_of:
            pending.append({"record_id": origin.id, "reason": "next-year outcome is not yet observed by as_of"})
            continue
        y = features(target)["gross_margin"]
        if target.available_at <= origin.available_at:
            excluded.append({"record_id": origin.id, "reason": "outcome already public at predictor origin"})
            continue
        if y is None or not _scope(target, s):
            excluded.append({"record_id": origin.id, "reason": "next-year outcome is missing or its scope is not comparable"})
            continue
        pair = {"entity": origin.entity, "origin_id": origin.id, "target_id": target.id,
                "origin_available_at": origin.available_at.isoformat(),
                "target_available_at": target.available_at.isoformat(),
                "x": x, "actual": y, "source": origin.source, "target_source": target.source}
        if origin.available_at <= s.training_cutoff and target.available_at <= s.training_cutoff:
            train.append(pair)
        elif origin.available_at > s.training_cutoff:
            test.append(pair)
        else:
            excluded.append({"record_id": origin.id, "reason": "label immature at training cutoff; origin is not out of time"})

    model = {"status": "not_estimated", "training_n": len(train), "test_n": len(test),
             "reason": "need at least three matured pairs and two distinct predictor values"}
    if len(train) >= 3:
        design = np.column_stack((np.ones(len(train)), [p["x"] for p in train]))
        coefficient, _, rank, _ = np.linalg.lstsq(design, [p["actual"] for p in train], rcond=None)
        if rank == 2:
            predictions = [{**p, "kind": "out_of_time_prediction",
                            "predicted": float(coefficient[0] + coefficient[1] * p["x"]),
                            "last_value_baseline": p["x"]} for p in test]
            rows.extend(predictions)
            model = {"status": "estimated", "training_n": len(train), "test_n": len(test),
                     "intercept": float(coefficient[0]), "slope": float(coefficient[1]),
                     "test_mae": float(np.mean([abs(p["predicted"]-p["actual"]) for p in predictions])) if predictions else None,
                     "baseline_mae": float(np.mean([abs(p["x"]-p["actual"]) for p in predictions])) if predictions else None,
                     "validation_status": "observed_holdout" if predictions else "no_matured_holdout"}

    return {
        "method": METHOD, "as_of": s.as_of.isoformat(),
        "input_snapshot": deepcopy(s.model_dump(mode="json")),
        "assumptions": [
            f"Supplied universe: {s.universe_definition}",
            "Current peers use the latest version available at as_of, with period-end assets as denominator.",
            "Historical x and y use first-publication gross margins; future restatements never replace them.",
            "One frozen pooled OLS: next-year gross margin = intercept + slope × current gross margin.",
            f"Training pairs must have both releases available by {s.training_cutoff.isoformat()}.",
        ],
        "limitations": [
            "Industrial annual statements only; gross profitability is not comparable for banks and insurers.",
            "Ranks describe the supplied universe, not the whole market; no missing or delisted companies are invented.",
            "Missing or non-positive revenue is not zero margin; negative gross profits remain valid observations.",
            "Three observations only establish algebraic identifiability, not empirical reliability or cycle coverage.",
            "Holdout MAE is descriptive; no independence assumption, significance, causality, PD or investment return is claimed.",
            "Model is frozen at one cutoff, not tuned on holdout; observed firms may recur in the holdout.",
            "Unconstrained OLS predictions are not clipped to an economically plausible interval; inspect extrapolation.",
        ],
        "rows": rows, "model": model, "training_pairs": train,
        "pending_outcomes": pending, "excluded_pairs": excluded,
        "selected_peer_versions": [r.id for r in peers],
    }


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
