"""The shared, source-linked workpaper used by calculation and export scripts."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Mandate(Record):
    title: str
    entity: str
    industry: str
    purpose: str
    period_start: date
    period_end: date
    cutoff: date
    accounting_basis: str
    scope: str
    language: str = "zh-CN"
    version: str
    methods: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class Source(Record):
    id: str
    title: str
    url: str
    published: date | None
    availability_note: str = ""
    sha256: str | None = None


class Evidence(Record):
    id: str
    source: str
    locator: str
    observation: str
    reliability: str


class Context(Record):
    entity: str
    scope: str
    start: date | None = None
    end: date
    aggregation: Literal["instant", "flow", "average", "ratio", "assumption"]
    basis: str
    measure: Literal["money", "count", "ratio", "days"]
    currency: str | None = None
    scale: Decimal = Decimal(1)
    physical_unit: str | None = None

    @model_validator(mode="after")
    def coherent(self):
        if self.scale <= 0 or not self.scale.is_finite():
            raise ValueError("scale must be positive and finite")
        if (self.measure == "money") != bool(self.currency):
            raise ValueError("money requires currency; other measures have no currency")
        if self.measure == "count" and not self.physical_unit:
            raise ValueError("count requires a physical_unit, for example GWh, shares or units")
        if self.start and self.start > self.end:
            raise ValueError("period start must not exceed end")
        if self.aggregation in ("flow", "average") and self.start is None:
            raise ValueError("flow/average requires a start date")
        return self


class Fact(Record):
    id: str
    label: str
    concept: str
    value: Decimal | None
    context: Context
    evidence: list[str]
    state: Literal["reported", "restated", "assumption", "missing"] = "reported"
    note: str = ""

    @model_validator(mode="after")
    def supported(self):
        if self.value is not None and not self.value.is_finite():
            raise ValueError("fact value must be finite")
        if (self.state == "missing") != (self.value is None):
            raise ValueError("unknown values use null and state=missing")
        if self.state in ("assumption", "missing") and not self.note:
            raise ValueError("assumptions/missing facts require an explanation")
        if self.state in ("reported", "restated") and not self.evidence:
            raise ValueError("reported facts require evidence")
        return self


class Term(Record):
    ref: str
    weight: Decimal = Decimal(1)


class Calculation(Record):
    id: str
    label: str
    concept: str | None = None
    op: Literal["sum", "difference", "ratio", "growth", "average_balance", "product"]
    terms: list[Term] = Field(min_length=1)
    context: Context
    definition: str
    interpretation: str
    period_rule: Literal["same", "comparison", "rollforward", "balance_flow", "forecast"] = "same"
    denominator: Literal["positive", "nonzero"] = "positive"
    multiplier: Decimal = Decimal(1)


class Reconciliation(Record):
    id: str
    label: str
    actual: str
    expected: str
    tolerance: Decimal = Field(ge=0)
    basis: str


class Finding(Record):
    id: str
    title: str
    question: str
    conclusion: str
    mechanism: str
    status: Literal["supported", "conditional", "unresolved"]
    evidence: list[str]
    counterevidence: list[str] = Field(default_factory=list)
    alternatives: list[str]
    changes_if: str


class Procedure(Record):
    id: str
    finding: str
    purpose: str
    assertions: list[str]
    population: str
    selection: str
    steps: list[str]
    status: Literal["planned", "awaiting_data", "performed", "limited"]
    result: str
    evidence: list[str] = Field(default_factory=list)
    performed_by: str | None = None
    performed_on: date | None = None

    @model_validator(mode="after")
    def execution(self):
        if self.status == "performed" and not (self.evidence and self.performed_by and self.performed_on):
            raise ValueError("performed procedures require evidence, executor and date")
        return self


class Request(Record):
    id: str
    finding: str
    request: str
    reason: str
    owner_role: str
    close_when: str


class Section(Record):
    title: str
    findings: list[str] = Field(default_factory=list)
    figures: list[str] = Field(default_factory=list)


class PresentationSlide(Section):
    body: str


class QuantitativeFigure(Record):
    id: str
    label: str
    row: int = Field(ge=0)
    field: str
    context: Context


class QuantitativeResult(Record):
    id: str
    label: str
    method: str
    as_of: date | datetime
    input_refs: list[str]
    evidence: list[str]
    assumptions: list[str]
    limitations: list[str]
    artifact: dict
    figures: list[QuantitativeFigure] = Field(default_factory=list)

    @model_validator(mode="after")
    def figure_values(self):
        if self.figures and not self.artifact.get("input_snapshot"):
            raise ValueError("quantitative figures require an input_snapshot")
        rows = self.artifact.get("rows", [])
        for figure in self.figures:
            if figure.row >= len(rows) or figure.field not in rows[figure.row]:
                raise ValueError(f"{figure.id}: unknown artifact row or field")
            value = rows[figure.row][figure.field]
            if value is not None and not TypeAdapter(Decimal).validate_python(value).is_finite():
                raise ValueError(f"{figure.id}: result must be finite or null")
        return self


class Workpaper(Record):
    mandate: Mandate
    sources: list[Source]
    evidence: list[Evidence]
    facts: list[Fact]
    calculations: list[Calculation] = Field(default_factory=list)
    reconciliations: list[Reconciliation] = Field(default_factory=list)
    findings: list[Finding]
    procedures: list[Procedure] = Field(default_factory=list)
    requests: list[Request] = Field(default_factory=list)
    sections: list[Section]
    presentation: list[PresentationSlide] = Field(default_factory=list)
    quantitative: list[QuantitativeResult] = Field(default_factory=list)

    @model_validator(mode="after")
    def references(self):
        groups = [self.sources, self.evidence, self.facts, self.calculations,
                  self.reconciliations, self.findings, self.procedures, self.requests, self.quantitative]
        ids = [item.id for group in groups for item in group]
        ids.extend(f.id for q in self.quantitative for f in q.figures)
        if len(ids) != len(set(ids)):
            raise ValueError("record identifiers must be globally unique")
        sources = {s.id: s for s in self.sources}
        evidence = {e.id: e for e in self.evidence}
        numbers = {f.id for f in self.facts} | {c.id for c in self.calculations}
        figures = {f.id for q in self.quantitative for f in q.figures}
        support = set(evidence) | numbers | figures
        findings = {f.id for f in self.findings}

        def require(refs, allowed, label):
            missing = set(refs) - set(allowed)
            if missing:
                raise ValueError(f"{label}: unknown references {sorted(missing)}")

        for e in self.evidence:
            require([e.source], sources, e.id)
            if sources[e.source].published and sources[e.source].published > self.mandate.cutoff:
                raise ValueError(f"{e.id}: source published after analysis cutoff")
        for f in self.facts:
            require(f.evidence, evidence, f.id)
        available = {f.id for f in self.facts}
        for c in self.calculations:
            require([t.ref for t in c.terms], available, c.id)
            available.add(c.id)
        for r in self.reconciliations:
            require([r.actual, r.expected], numbers, r.id)
        for f in self.findings:
            require(f.evidence + f.counterevidence, support, f.id)
            if f.status == "supported" and not f.evidence:
                raise ValueError(f"{f.id}: supported finding requires evidence")
        for p in self.procedures:
            require([p.finding], findings, p.id)
            require(p.evidence, support, p.id)
        for r in self.requests:
            require([r.finding], findings, r.id)
        for s in [*self.sections, *self.presentation]:
            require(s.findings, findings, s.title)
            require(s.figures, numbers | figures, s.title)
        model_cutoffs = {}
        for q in self.quantitative:
            require(q.input_refs, available, q.id)
            require(q.evidence, evidence, q.id)
            cutoff = q.as_of.date() if isinstance(q.as_of, datetime) else q.as_of
            if cutoff > self.mandate.cutoff:
                raise ValueError(f"{q.id}: result cutoff exceeds mandate cutoff")
            for ref in set(q.input_refs) & model_cutoffs.keys():
                previous = model_cutoffs[ref]
                if isinstance(previous, datetime) and isinstance(q.as_of, datetime):
                    if (previous.utcoffset() is None) != (q.as_of.utcoffset() is None):
                        raise ValueError(f"{q.id}: input model cutoff has incompatible timezone precision: {ref}")
                    later = previous > q.as_of
                else:
                    later = (previous.date() if isinstance(previous, datetime) else previous) > cutoff
                if later:
                    raise ValueError(f"{q.id}: input model cutoff exceeds result cutoff: {ref}")
            available.update(f.id for f in q.figures)
            model_cutoffs.update((f.id, q.as_of) for f in q.figures)
        return self
