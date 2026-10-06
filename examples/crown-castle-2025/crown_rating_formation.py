"""Crown-specific numeric formation interface; qualitative choices remain evidence leaves."""
import argparse
from decimal import Decimal, getcontext
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/annual-report-analysis/scripts"))

from calculate import evaluate
from score_bounds import NumericBand, _numeric_band
from workpaper import QuantitativeResult, Workpaper

getcontext().prec = 28
D = Decimal


def run(workpaper):
    w = Workpaper.model_validate(workpaper)
    data = w.model_dump(mode="json")
    forward = next(q for q in data["quantitative"] if q["id"] == "Q_crown_forward")
    facts = {f["id"]: f for f in data["facts"]}
    calculations = {c["id"]: c for c in evaluate(w)["calculations"]}
    source_figures = {f["id"]: f for f in forward["figures"]}
    snapshot, refs, rows, figures = {}, [], [], []
    entity = "Crown Castle Inc. and subsidiaries"

    def value(ref):
        if ref not in refs:
            refs.append(ref)
        if ref in facts:
            record = facts[ref]
            result = record["value"]
            snapshot[ref] = {"record": record}
        elif ref in source_figures:
            record = source_figures[ref]
            result = forward["artifact"]["rows"][record["row"]][record["field"]]
            snapshot[ref] = {"quantitative": "Q_crown_forward", "row": record["row"],
                             "field": record["field"], "context": record["context"], "value": result}
        else:
            record = calculations[ref]
            result = record["normalized"]
            snapshot[ref] = {"record": record}
            calculation = next(c for c in data["calculations"] if c["id"] == ref)
            return None if result is None else D(result) / (D(1000000) if calculation["context"]["measure"] == "money" else D(1))
        if result is None:
            return None
        scale = D(record["context"]["scale"])
        normalized = D(result) * scale
        return normalized / D(1000000) if record["context"]["measure"] == "money" else normalized

    def metric(scenario, year, name):
        path = forward["artifact"]["scenarios"][scenario]["path"][str(year)]
        result = path[name]
        locator = f"artifact.scenarios.{scenario}.path.{year}.{name}"
        row = next((i for i, r in enumerate(forward["artifact"]["rows"])
                    if r.get("scenario") == scenario and r.get("year") == str(year) and r.get("metric") == name), None)
        context = dict(source_figures[f"fwd_{scenario}_FFO_{year}"]["context"])
        ratio = name.endswith("_debt") or name.endswith("_coverage")
        context.update(aggregation="ratio" if ratio else "flow", measure="ratio" if ratio else "money",
                       currency=None if ratio else "USD", scale="1" if ratio else "1000000",
                       physical_unit="times" if name.endswith("_coverage") else None)
        snapshot[locator] = {"quantitative": "Q_crown_forward", "path": locator,
                             "row": row, "field": "result" if row is not None else name,
                             "context": context,
                             "value": result}
        return None if result is None else D(result)

    def add(id, label, result, formula, measure="ratio", unit=None, **extra):
        index = len(rows)
        rows.append({"id": id, "label": label, "result": None if result is None else str(result),
                     "formula": formula, **extra})
        figures.append({"id": id, "label": label, "row": index, "field": "result",
                        "context": {"entity": entity, "scope": "issuer_and_CCI_4pct_March2027_formation",
                                    "start": None, "end": "2026-06-30", "aggregation": "assumption",
                                    "basis": "Supplied original S&P tables and explicit issuer-specific assumptions",
                                    "measure": measure, "currency": "USD" if measure == "money" else None,
                                    "scale": "1000000" if measure == "money" else "1", "physical_unit": unit}})
        return result

    tables = {
        "standard_FFO_debt": [("60", None, 1), ("45", "60", 2), ("30", "45", 3),
                               ("20", "30", 4), ("12", "20", 5), (None, "12", 6)],
        "standard_debt_EBITDA": [(None, "1.5", 1), ("1.5", "2", 2), ("2", "3", 3),
                                  ("3", "4", 4), ("4", "5", 5), ("5", None, 6)],
        "standard_FFO_cash_interest": [("13", None, 1), ("9", "13", 2), ("6", "9", 3),
                                       ("4", "6", 4), ("2", "4", 5), (None, "2", 6)],
        "standard_EBITDA_interest": [("15", None, 1), ("10", "15", 2), ("6", "10", 3),
                                     ("3", "6", 4), ("2", "3", 5), (None, "2", 6)],
        "standard_CFO_debt": [("50", None, 1), ("35", "50", 2), ("25", "35", 3),
                              ("15", "25", 4), ("10", "15", 5), (None, "10", 6)],
        "standard_FOCF_debt": [("40", None, 1), ("25", "40", 2), ("15", "25", 3),
                               ("10", "15", 4), ("5", "10", 5), (None, "5", 6)],
        "standard_DCF_debt": [("25", None, 1), ("15", "25", 2), ("10", "15", 3),
                              ("5", "10", 4), ("2", "5", 5), (None, "2", 6)],
        "medial_FFO_debt": [("50", None, 1), ("35", "50", 2), ("23", "35", 3),
                             ("13", "23", 4), ("9", "13", 5), (None, "9", 6)],
        "medial_debt_EBITDA": [(None, "1.75", 1), ("1.75", "2.5", 2), ("2.5", "3.5", 3),
                                ("3.5", "4.5", 4), ("4.5", "5.5", 5), ("5.5", None, 6)],
        "low_FFO_debt": [("35", None, 1), ("23", "35", 2), ("13", "23", 3),
                          ("9", "13", 4), ("6", "9", 5), (None, "6", 6)],
        "low_debt_EBITDA": [(None, "2", 1), ("2", "3", 2), ("3", "4", 3),
                             ("4", "5", 4), ("5", "6", 5), ("6", None, 6)]}

    def band(id, table, result):
        bands = []
        for lower, upper, score in tables[table]:
            # Hyphenated ranges share closed endpoints; actual boundary overlap stays unresolved.
            closed_lower = lower is not None and not (score == 6 or (score == 1 and "interest" in table))
            closed_upper = upper is not None and not (score == 6 or (score == 1 and "debt_EBITDA" in table))
            bands.append({"id": f"{table}_{score}", "lower": lower, "upper": upper,
                          "left_closed": closed_lower, "right_closed": closed_upper,
                          "score": {"lower": str(score), "upper": str(score),
                                    "left_closed": True, "right_closed": True}})
        node = NumericBand.model_validate({"id": id, "mode": "numeric_band", "input_ref": id + "_ratio",
                                           "threshold_scale": ".01" if table.endswith("_debt") else "1",
                                           "bands": bands, "evidence": ["E_R109_FRP_TABLE"],
                                           "note": "Exact transcription of original table ranges; no endpoint tie-break invented."})
        selected, reason, matches = _numeric_band(node, Fraction(result) if result is not None else None)
        add(id, table + " numerical category", None if selected is None else D(selected.lower.numerator) / D(selected.lower.denominator),
            "Existing NumericBand/_numeric_band applied to the executed indicative ratio", "count", "method category 1..6",
            table=node.model_dump(mode="json"), normalized_input=str(result), matched_bands=matches,
            exact_interval=str(selected), reason=reason)

    weights = [value("F_R109_W120_CURRENT"), value("F_R109_W120_NEXT")]
    weights117 = [value("F_R109_W117_CURRENT"), value("F_R109_W117_NEXT"), value("F_R109_W117_SECOND")]
    for scenario in ["base", "joint_stress"]:
        for name in ["FFO_debt", "debt_EBITDA"]:
            annual = [value(f"fwd_{scenario}_{name}_{y}") for y in [2026, 2027, 2028]]
            indicative = sum(v * weight for v, weight in zip(annual, weights))
            add(f"r109_{scenario}_{name}_120", f"{scenario} paragraph120 indicative {name}", indicative,
                "Mean of current/pro-forma current and next-year ratios; not ratio of averaged balances", unit="times" if name == "debt_EBITDA" else None)
            for table in ["standard", "medial", "low"]:
                band(f"r109_{scenario}_{table}_{name}_category", table + "_" + name, indicative)
            add(f"r109_{scenario}_{name}_117", f"{scenario} conditional paragraph117 indicative {name}",
                sum(v * weight for v, weight in zip(annual, weights117)),
                "Current/next/second-next ratios weighted30/40/30; only applicable if negative debt-repayment cash deteriorates metrics", unit="times" if name == "debt_EBITDA" else None)
        for name in ["FFO_cash_interest_coverage", "EBITDA_interest_coverage", "CFO_debt", "FOCF_debt", "DCF_debt"]:
            indicative = sum(metric(scenario, year, name) * weight for year, weight in zip([2026, 2027], weights))
            add(f"r109_{scenario}_{name}_120", f"{scenario} indicative {name}", indicative,
                "Mean of original Q_crown_forward scenario yearly ratios", unit="times" if "coverage" in name else None)
            table = "standard_" + name.replace("_coverage", "")
            band(f"r109_{scenario}_{name}_category", table, indicative)
        for year in [2026, 2027, 2028]:
            add(f"r109_{scenario}_DCF_{year}", f"{scenario} {year} DCF", metric(scenario, year, "DCF"),
                "Direct observation of original Q_crown_forward existing row.result; no new Fact", "money")

    cap = value("fwd_base_window_capex_rolling12m")
    div = value("fwd_base_window_dividends_rolling12m")
    debt = value("fwd_base_fixed_maturities_if_not_prepaid_rolling12m")
    routine = value("fwd_base_routine_principal_proxy_rolling12m")
    cfo = value("fwd_base_window_CFO_rolling12m")
    stress = value("fwd_base_cash_loss_if_weighted_method_EBITDA_declines_15pct_rolling12m")
    b = add("r109_window_B0", "Jul2026-Jun2027 displayed uses subtotal", cap + div + debt + routine,
            "CAP+dividends+unprepaid fixed maturities+routine principal; additional/offset uses are U", "money")
    add("r109_window_JV_for_adequate", "Necessary June cash plus qualified facilities for A/B test", value("F_R109_LIQ_AB") * b - cfo,
        "J+V >=1.2*B0-CFO +1.2*U+0.2*W; W is negativeWC already deducted in CFO and restored to sourceFFO/uses; V excludes uncommitted market refinancing", "money")
    add("r109_window_WC_AB_coefficient", "A/B condition additional coefficient for negativeWC already in CFO", value("F_R109_LIQ_AB") - D(1),
        "A=(J+CFO+W+V), B=(B0+U+W); hence additional coefficient (1.2-1)*W")
    add("r109_window_JV_for_positive_stress", "Necessary June cash plus qualified facilities for positive stressed A-B", b - cfo + stress,
        "J+V >B0-CFO+15% EBITDA loss +U+additional stress financing interest", "money")
    add("r109_window_nominal_pool_reference", "May1 nominal undrawn facility reference", value("newcommit") - value("newlc"),
        "Commitments-LC; subtract actual June draws/LC changes and qualification restrictions before use as V", "money")
    add("r109_window_actual_AB", "Actual June-based A/B", None,
        "(J+CFO+W+qualifiedV)/(B0+U+W) under displayed CFO proxy; actual full FFO/WC and peak uses replace proxy when known", unit="times")
    # Rate shock is a numerical condition; Tier2 alone is not a Table21 negative capital-structure assessment.
    current_e = metric("base", 2026, "EBITDA")
    next_e = metric("base", 2027, "EBITDA")
    current_i = metric("base", 2026, "adjusted_accrual_interest")
    next_i = metric("base", 2027, "adjusted_accrual_interest")
    threshold = value("F_R109_COVERAGE_BOUNDARY")
    a = D(2) * threshold
    b_rate = a * (current_i + next_i) - current_e - next_e
    c_rate = a * current_i * next_i - current_e * next_i - next_e * current_i
    extra_interest = (-b_rate + (b_rate*b_rate - D(4)*a*c_rate).sqrt()) / (D(2)*a)
    add("r109_float_at100bp_coverage_boundary", "Equal annual floating principal at indicative coverage boundary under100bp shock", extra_interest / value("F_R109_RATE_100BP"),
        "Solve0.5*E26/(I26+0.01*V)+0.5*E27/(I27+0.01*V)=3; same V bothyears explicit; annual-ratio mean retained", "money")

    note_face = value("F_DEV_NOTE_FACE")
    note_claim = add("r109_note_same_coupon_claim", "Specific note same-coupon six-month claim scenario", note_face * (D(1) + value("F_R109_NOTE_COUPON") * value("F_R109_PREINTEREST_YEARS")),
                     "Face*(1+coupon*0.5); bullet prior to hypothetical default assumed refinanced; same coupon is explicit replacement scenario", "money")
    add("r109_note_30pct_distribution", "Specific note distribution needed for30% recovery", note_claim * value("F_R109_RECOVERY_30"),
        "0.30*specific note principal plus prepetition interest claim", "money")
    add("r109_note_10pct_distribution", "Specific note distribution needed for10% recovery", note_claim * value("F_R109_RECOVERY_10"),
        "0.10*specific note principal plus prepetition interest claim", "money")
    net_per_tower = value("F_R109_DAV_TOWER") * (D(1) - value("F_R109_ADMIN_COST"))
    add("r109_towers_per_1000m_U_for30", "Qualified non-SPE tower equivalents per1000m unsecured claim for30%", D(1000) * value("F_R109_RECOVERY_30") / net_per_tower,
        "0.30*1000/(0.36*0.95), before priority claims and other eligible value", "count", "qualified tower equivalents")
    add("r109_towers_per_1000m_U_for10", "Qualified non-SPE tower equivalents per1000m unsecured claim for10%", D(1000) * value("F_R109_RECOVERY_10") / net_per_tower,
        "0.10*1000/(0.36*0.95), before priority claims and other eligible value", "count", "qualified tower equivalents")
    add("r109_towers_per_1m_priority", "Extra qualified tower equivalents per1m priority claim", D(1) / net_per_tower,
        "1/(0.36*0.95)", "count", "qualified tower equivalents")
    add("r109_actual_note_recovery", "Actual qualified-asset recovery", None,
        "clip((0.95*(0.36*N+EVother)-P)/U,0,1); N/U/P/EVother and U.S. jurisdiction ranking unverified")
    for ref in ["F_R109_ELIGIBLE_NON_SPE_TOWERS", "F_R109_PRIORITY_EAD", "F_R109_UNSECURED_EAD", "F_R109_OTHER_ELIGIBLE_EV", "F_R109_RECOVERY_70", "F_R109_WC_OUTFLOW_ALREADY_IN_CFO", "F_DEV_BRP", "C_DEV_CPGP"]:
        value(ref)
    return QuantitativeResult.model_validate({
        "id": "Q_r109_crown_rating", "label": "Crown issuer and specific senior-unsecured note rating formation",
        "method": "S&P Corporate original Tables1/2/3/5/14-19/21-25; existing NumericBand/portion2.6.3; liquidity and recovery original clauses",
        "as_of": "2026-06-30", "input_refs": refs, "evidence": ["E_DEV_DI", "E_DEV_CORP", "E_R109_FRP_TABLE", "E_R109_MODIFIERS", "E_R109_LIQ", "E_R109_RECOVERY", "E_DEV_NOTE", "E_DEV_CREDIT"],
        "assumptions": ["BRP2 is an evidence-based research leaf, including average profitability and volatility3; not an issuer-reported score.",
                        "Standard primary table. FRP6 primary; FRP5 is at most one-category supplementary improvement conditional on sustainable distribution/funding evidence.",
                        "June liquidity uses the displayed Jul-Jun timing proxy plus unknown J/V/U. No unique liquidity descriptor is manufactured.",
                        "Neutral management/governance is only an explicit scenario; specialist method not verified. All letter outputs require the stated modifier/support/country conditions.",
                        "Tower DAV only for qualified non-SPE facility or transferable-right equivalents. A same-coupon replacement note claim is illustrative; no actual recovery estimate."],
        "limitations": ["NumericBand tests supplied tables and actual numbers; it does not decide qualitative applicability or generate issuer ratings.",
                        "Unverified management/governance methodology, current U.S. sovereign/T&C and jurisdiction ranking remain scoped conditions.",
                        "Cash/CP/executed2100 allocation/June draws/covenant denominators and non-SPE asset/claim eligibility remain specific missing inputs."],
        "artifact": {"input_snapshot": snapshot, "rows": rows, "forward_snapshot_sha256": hashlib.sha256(json.dumps(forward, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                     "execution": "Actual case arithmetic and existing NumericBand selection; upstream observations retain original row/path/field and context.",
                     "primary_sequence": [{"step": "CP/BRP", "result": "CP2/BRP2", "condition": "factor2/2/2 plus profitability<=3"},
                                          {"step": "coreFRP", "result": "6", "condition": "standard two core ratios both6"},
                                          {"step": "supplementary/volatility", "result": "6", "condition": "DCF/funding more representative; joint stress does not justify further category beyond6"},
                                          {"step": "anchor", "result": "bb", "condition": "Table3 BRP2/FRP6"},
                                          {"step": "diversification", "input": "bb", "result": "bb", "condition": "neutral0; retained Towers/relatedservices"},
                                          {"step": "capital structure", "input": "bb", "result": "bb", "condition": "neutral0 scenario; Tier1 maturity not negative; Tier2 alone neutral perTable21"},
                                          {"step": "financial policy", "input": "bb", "result": "bb", "condition": "neutral0; forecast already includes disclosed distribution/debt plans"},
                                          {"step": "liquidity", "input": "bb", "result": "bb ifadequate; bb- iflessadequate; atmostb- ifweak", "condition": "Each branch uses current range; no six-month exception forBB; cap-createdBB+ footnote not applicable"},
                                          {"step": "management/governance", "input": "postliquidity branch", "result": "same only underneutral scenario", "condition": "specialistclassification unverified; moderatelynegative0/-1 ornegative>=-1 inBB/B column"},
                                          {"step": "CRA", "input": "postgovernance branch", "result": "same underneutral0 scenario; +/-1 if sustained peer-category position or notfullycapturedfactor supports", "condition": "same-category overall strong/weak-edge evidence may qualify; cannot override liquidity cap or mechanically repeatDISH/2028"},
                                          {"step": "support/sovereign", "input": "postCRA branch", "result": "ICR same only if no extra support/constraint", "condition": "no demonstrated support mechanism; country-risk1 is not current sovereign/T&C"}],
                     "adjacent_sequence": "FRP5 condition: BRP2→bb+; neutral capital/policy→bb+; adequate→bb+ orlessadequate→bb; subsequent M&G/CRA/support conditions separately applied.",
                     "recovery_scope": "N=qualified owned facilities outsideSPE + retained transferable carrier-right equivalents outsideSPE; excludes rooftop/single-purpose unless separately valued. DAV excludes matched securitization assets AND claims. Do not infer N from land ownership or residual45%.",
                     "recovery_waterfall": "NetEV=0.95*(0.36*N+EVother); subtract P for valid priority/non-guarantor claims; unsecured sharing by U principal+prepetitioninterest. RCF typically85%, CPbackup counted once; scheduled amortization/rollovers/lease rejection/ARO/legal costs by actual conditions. N30=(0.30*U+P-0.95*EVother)/0.342; N10 analogous. Case adjustments require issuer-specific evidence; no positive adjustment presumed.",
                     "issue_branches": "If recovery applies in verified A/B and ICR is BBcategory: general unsecuredcap3 gives>=30% sameICR,10..<30% ICR-1,<10% ICR-2; no positive notch even if>=70%. If ICR becomesB+orlower: generalGroupA cap2 permits>=70% ICR+1,30..<70%sameICR,lowerbands asabove; generalGroupB remainscap3 and>=30%sameICR. REITlabel does not prove exceptioncaps. C/unranked or outofscope uses actual six-step subordination instead."},
        "figures": figures})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workpaper", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.workpaper).read_text(encoding="utf-8-sig"))
    result = run(data).model_dump(mode="json")
    data["quantitative"] = [q for q in data["quantitative"] if q["id"] != result["id"]] + [result]
    Workpaper.model_validate(data)
    Path(args.output).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"result": result["id"], "rows": len(result["artifact"]["rows"]), "figures": len(result["figures"])}, ensure_ascii=False))
