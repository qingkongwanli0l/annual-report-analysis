"""Source-linked interval arithmetic and joint-feasibility counterexamples."""
from decimal import Decimal
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import portion as P
from pydantic import ValidationError

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/annual-report-analysis/scripts"
sys.path.insert(0, str(SCRIPTS))
from calculate import evaluate
from export import prepare
import score_bounds
from workpaper import Calculation, QuantitativeResult, Workpaper


def workpaper():
    context = {"entity": "Constructed company", "scope": "consolidated", "end": "2025-12-31",
               "aggregation": "ratio", "basis": "constructed", "measure": "ratio", "scale": "0.01"}
    facts = [{"id": f"w{weight}", "label": f"Global weight {weight}", "concept": "method_weight",
              "value": str(weight), "context": context, "evidence": ["E"], "note": "Constructed method weight"}
             for weight in (47, 3, 5, 17, 11, 13, 4, 55, 45, 0, 1)]
    return Workpaper.model_validate({
        "mandate": {"title": "Constructed intervals", "entity": "Constructed company", "industry": "constructed",
                    "purpose": "Arithmetic counterexamples", "period_start": "2025-01-01", "period_end": "2025-12-31",
                    "cutoff": "2026-06-30", "accounting_basis": "constructed", "scope": "consolidated",
                    "version": "1", "methods": ["Constructed supplied linear score bands"]},
        "sources": [{"id": "M", "title": "Constructed method", "url": "constructed:method", "published": "2024-08-20"}],
        "evidence": [{"id": "E", "source": "M", "locator": "Constructed method table",
                      "observation": "Supplied bands and weights, not an official model", "reliability": "constructed"}],
        "facts": facts, "findings": [], "sections": []})


def leaf(id, low, high, *, left=True, right=True, state="method_band", refs=None):
    return {"id": id, "bounds": None if low is None else {"lower": str(low), "upper": str(high),
            "left_closed": left, "right_closed": right}, "state": state, "input_refs": refs or [],
            "evidence": ["E"], "note": "Constructed supplied interval; no point interpolation"}


def weighted(id, terms, *, joint="independent"):
    return {"id": id, "mode": "weighted_mean", "terms": [{"node_ref": node, "weight_ref": weight} for node, weight in terms],
            "basis_state": "reported", "joint_basis": joint, "evidence": ["E"], "note": "Supplied global weights"}


def convex(id, children):
    return {"id": id, "mode": "unknown_convex_weights", "children": children, "basis_state": "assumption",
            "joint_basis": "independent", "evidence": ["E"], "note": "Independent intervals; nonnegative child weights sum to one"}


def spec(nodes, output):
    return {"method_evidence": ["E"], "nodes": nodes, "outputs": [output]}


def run(nodes, output, w=None):
    return score_bounds.run(w or workpaper(), spec(nodes, output), id="bounds", label="Conditional intervals", as_of="2026-06-30")


def row(result, id):
    return next(r for r in result.artifact["rows"] if r["id"] == id)


def interval(result, id):
    r = row(result, id)
    return P.from_data([(r["lower_closed"], Fraction(r["lower_exact"]), Fraction(r["upper_exact"]), r["upper_closed"])])


def wealth_nodes():
    return [leaf("market", 7, 7), leaf("operation", 5, 6, right=False), leaf("rd", 6, 7, right=False),
            weighted("wealth", [("market", "w47"), ("operation", "w3"), ("rd", "w5")])]


def numeric():
    return {"id": "credit", "mode": "numeric_band", "input_ref": "w47", "threshold_scale": "0.01",
            "bands": [{"id": "middle", "lower": "35", "upper": "50", "left_closed": True,
                       "right_closed": False, "score": {"lower": "3", "upper": "4", "left_closed": True, "right_closed": False}},
                      {"id": "higher", "lower": "50", "upper": None, "left_closed": True,
                       "right_closed": False, "score": {"lower": "4", "upper": "5", "left_closed": True, "right_closed": False}}],
            "evidence": ["E"], "note": "Constructed original numeric table; no interpolation"}


class ScoreBoundsTests(unittest.TestCase):
    def test_numeric_lookup_keeps_original_band_and_percent_scale(self):
        node = numeric()
        result = run([node], "credit")
        self.assertEqual(interval(result, "credit"), P.closedopen(Fraction(3), Fraction(4)))
        self.assertEqual(row(result, "credit")["matched_band_ids"], ["middle"])
        self.assertEqual(row(result, "credit")["input_normalized_exact"], "47/100")
        self.assertNotEqual(interval(result, "credit"), P.singleton(Fraction(4)))
        node["input_ref"] = "w55"
        self.assertEqual(interval(run([node], "credit"), "credit"), P.closedopen(Fraction(4), Fraction(5)))

    def test_numeric_boundary_overlap_gap_and_unbounded_threshold(self):
        w, node = workpaper(), numeric()
        w.facts[0].value = Decimal("50")
        self.assertEqual(row(run([node], "credit", w), "credit")["matched_band_ids"], ["higher"])
        node["bands"][0]["right_closed"] = True
        result = row(run([node], "credit", w), "credit")
        self.assertIsNone(result["range_text"])
        self.assertEqual(result["matched_band_ids"], ["middle", "higher"])
        self.assertIn("overlapping", result["reason"])
        node["bands"][0]["right_closed"], node["bands"][1]["left_closed"] = False, False
        result = row(run([node], "credit", w), "credit")
        self.assertIsNone(result["range_text"])
        self.assertIn("no matching", result["reason"])
        node["bands"].append({"id": "lowest", "lower": None, "upper": "35", "left_closed": False,
                              "right_closed": False, "score": {"lower": "1", "upper": "3", "left_closed": True, "right_closed": False}})
        w.facts[0].value = Decimal("-1")
        self.assertEqual(interval(run([node], "credit", w), "credit"), P.closedopen(Fraction(1), Fraction(3)))

    def test_numeric_missing_or_invalid_calculation_is_not_zero(self):
        w, node = workpaper(), numeric()
        w.facts[0].value, w.facts[0].state, w.facts[0].note = None, "missing", "Constructed company input not available"
        self.assertIsNone(row(run([node], "credit", w), "credit")["range_text"])
        w = workpaper()
        w.calculations.append(Calculation.model_validate({
            "id": "invalid_ratio", "label": "Zero denominator", "op": "ratio", "terms": [{"ref": "w47"}, {"ref": "w0"}],
            "context": w.facts[0].context.model_dump(mode="json"), "definition": "Constructed zero denominator", "interpretation": "Undefined"}))
        node["input_ref"] = "invalid_ratio"
        result = run([node], "credit", w)
        self.assertIsNone(row(result, "credit")["range_text"])
        self.assertIn("non-positive denominator", result.artifact["input_snapshot"]["resolved_inputs"]["invalid_ratio"]["calculation_reason"])

    def test_numeric_aggregation_and_existing_export_interface(self):
        w = workpaper()
        result = run([numeric(), leaf("other", 7, 7), weighted("group", [("credit", "w47"), ("other", "w3")])], "group", w)
        self.assertEqual(interval(result, "group"), P.closedopen(Fraction("3.24"), Fraction("4.18")))
        w.quantitative.append(result)
        prepared = prepare(Workpaper.model_validate(w.model_dump(mode="json")), evaluate(w))
        saved = prepared["quantitative"][0]["artifact"]
        self.assertEqual(saved["rows"][0]["matched_band_ids"], ["middle"])
        self.assertEqual(saved["input_snapshot"]["spec"]["nodes"][0]["bands"][0]["score"]["upper"], "4")

    def test_exact_open_wealth_bound_is_not_point_score(self):
        result = run(wealth_nodes(), "wealth")
        actual = interval(result, "wealth")
        self.assertEqual(actual, P.closedopen(Fraction(374, 55), Fraction(382, 55)))
        self.assertNotEqual(actual, P.singleton(Fraction("6.8")))
        self.assertNotIn(Fraction(382, 55), actual)
        self.assertEqual(row(result, "wealth")["normalizer_exact"], "11/20")
        self.assertEqual(result.artifact["input_snapshot"]["resolved_inputs"]["w47"]["normalized_exact"], "47/100")
        self.assertFalse(result.figures)

    def test_known_group_weights_exclude_S_one(self):
        nodes = wealth_nodes() + [leaf("source", 1, 7, state="missing"), leaf("capital", 4, 5, right=False),
            leaf("coverage", 6, 7), leaf("cashflow", 7, 7),
            weighted("debt", [("source", "w17"), ("capital", "w11"), ("coverage", "w13"), ("cashflow", "w4")]),
            weighted("total", [("wealth", "w55"), ("debt", "w45")])]
        result = run(nodes, "total")
        self.assertEqual(interval(result, "debt"), P.closedopen(Fraction(167, 45), Fraction(293, 45)))
        self.assertNotIn(1, interval(result, "debt"))
        self.assertEqual(interval(result, "total"), P.closedopen(Fraction("5.41"), Fraction("6.75")))
        self.assertEqual(row(result, "source")["state"], "missing")

    def test_unknown_convex_weights_are_not_equal_weights(self):
        result = run([leaf("a", 2, 2), leaf("b", 8, 8), convex("group", ["a", "b"])], "group")
        self.assertEqual(interval(result, "group"), P.closed(Fraction(2), Fraction(8)))
        self.assertNotEqual(interval(result, "group"), P.singleton(Fraction(5)))
        constant = run([leaf("a", 7, 7), leaf("b", 7, 7), convex("group", ["a", "b"])], "group")
        self.assertEqual(row(constant, "group")["status"], "point_given_inputs")
        reused = run([leaf("a", 7, 7), leaf("b", 7, 7), convex("group", ["a", "b"]),
                      weighted("twice", [("group", "w1"), ("group", "w1")])], "twice")
        self.assertEqual(interval(reused, "twice"), P.singleton(Fraction(7)))
        self.assertTrue(any("nonnegative" in a for a in result.assumptions))
        invalid = convex("group", ["a", "b"])
        invalid["basis_state"] = "reported"
        with self.assertRaises(ValidationError):
            run([leaf("a", 2, 2), leaf("b", 8, 8), invalid], "group")

    def test_convex_hull_endpoint_can_come_from_closed_child(self):
        result = run([leaf("open", 1, 2, left=False, right=False), leaf("closed", 2, 2),
                      convex("group", ["open", "closed"])], "group")
        self.assertEqual(interval(result, "group"), P.openclosed(Fraction(1), Fraction(2)))

    def test_positive_unresolved_component_and_missing_weight_are_not_dropped(self):
        nodes = [leaf("unknown", None, None, state="missing"), leaf("known", 7, 7),
                 weighted("group", [("unknown", "w47"), ("known", "w3")])]
        result = run(nodes, "group")
        self.assertIsNone(row(result, "group")["range_text"])
        self.assertIn("cannot be omitted", row(result, "group")["reason"])
        w = workpaper()
        w.facts[0].value, w.facts[0].state = None, "missing"
        result = run([leaf("a", 7, 7), weighted("group", [("a", "w47"), ("a", "w3")])], "group", w)
        self.assertIsNone(row(result, "group")["normalizer_exact"])
        self.assertIn("missing weight", row(result, "group")["reason"])

    def test_zero_weight_does_not_propagate_unresolved_or_open_endpoint(self):
        for low, high, state in [(None, None, "missing"), (1, 2, "method_band")]:
            nodes = [leaf("ignored", low, high, left=False, right=False, state=state), leaf("known", 7, 7),
                     weighted("group", [("ignored", "w0"), ("known", "w1")])]
            self.assertEqual(interval(run(nodes, "group"), "group"), P.singleton(Fraction(7)))

    def test_unknown_form_and_shared_constraint_stay_unresolved(self):
        nodes = [leaf("x", 0, 1), leaf("y", 0, 1), weighted("sum", [("x", "w1"), ("y", "w1")], joint="unknown_or_shared")]
        nodes[-1]["note"] = "Shared constraint x+y=1: independent rectangle would be incorrect"
        self.assertIsNone(row(run(nodes, "sum"), "sum")["range_text"])
        nodes[-1] = {"id": "sum", "mode": "unresolved", "children": ["x", "y"],
                     "evidence": ["E"], "note": "Aggregation form not published"}
        self.assertIn("no weights or linear form", row(run(nodes, "sum"), "sum")["reason"])

    def test_reused_uncertain_input_does_not_assert_independent_sets(self):
        nodes = [leaf("x", 1, 2), leaf("y", 3, 4), convex("a", ["x", "y"]),
                 weighted("group", [("a", "w1"), ("x", "w1")])]
        self.assertIn("shared uncertain", row(run(nodes, "group"), "group")["reason"])

    def test_method_band_does_not_hide_missing_company_input(self):
        w = workpaper()
        w.facts[0].value, w.facts[0].state = None, "missing"
        node = leaf("score", 6, 7, right=False, refs=["w47"])
        self.assertIsNone(row(run([node], "score", w), "score")["range_text"])
        node["state"], node["bounds"]["lower"], node["bounds"]["upper"] = "missing", "1", "7"
        self.assertEqual(interval(run([node], "score", w), "score"), P.closedopen(Fraction(1), Fraction(7)))

    def test_current_workpaper_and_prepare_keep_exact_snapshot_on_rerun(self):
        w = workpaper()
        first = run(wealth_nodes(), "wealth", w)
        w.quantitative.append(first)
        checked = Workpaper.model_validate(w.model_dump(mode="json"))
        prepared = prepare(checked, evaluate(checked))
        self.assertEqual(prepared["quantitative"][0]["artifact"]["rows"][-1]["range_text"], "[34/5,382/55)")
        changed = wealth_nodes()
        changed[1]["bounds"]["upper"] = "7"
        second = run(changed, "wealth", workpaper())
        self.assertNotEqual(row(second, "wealth")["upper_exact"], row(first, "wealth")["upper_exact"])
        self.assertEqual(row(first, "wealth")["upper_exact"], "382/55")

    def test_weights_from_existing_calculation_and_source_cutoff(self):
        w = workpaper()
        w.facts[0].state, w.facts[0].note = "assumption", "Constructed weight branch, not disclosed"
        w.calculations.append(Calculation.model_validate({
            "id": "derived_weight", "label": "Derived documented weight", "op": "sum", "terms": [{"ref": "w47"}, {"ref": "w3"}],
            "context": w.facts[0].context.model_dump(mode="json"), "definition": "47+3 global percent", "interpretation": "Constructed sum"}))
        result = run([leaf("a", 5, 6, right=False), weighted("group", [("a", "derived_weight")])], "group", w)
        self.assertEqual(row(result, "group")["normalizer_exact"], "1/2")
        self.assertIn("derived_weight", result.input_refs)
        self.assertTrue(any("Constructed weight branch" in a for a in result.assumptions))
        self.assertIn("not disclosed", result.artifact["input_snapshot"]["resolved_inputs"]["derived_weight"]["assumptions"][0])
        with self.assertRaisesRegex(ValueError, "published after"):
            score_bounds.run(w, spec(wealth_nodes(), "wealth"), id="bounds", label="Intervals", as_of="2024-01-01")

    def test_cli_returns_existing_quantitative_record(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / "workpaper.json").write_text(workpaper().model_dump_json(), encoding="utf-8")
            (folder / "spec.json").write_text(json.dumps({"method_evidence": ["E"], "nodes": wealth_nodes() + [numeric()],
                "outputs": ["wealth", "credit"]}), encoding="utf-8")
            output = subprocess.run([sys.executable, "-B", "-X", "utf8", str(SCRIPTS / "score_bounds.py"),
                str(folder / "workpaper.json"), str(folder / "spec.json"), "--id", "bounds", "--label", "Conditional intervals",
                "--as-of", "2026-06-30"], check=True, capture_output=True, text=True)
            result = QuantitativeResult.model_validate_json(output.stdout)
            self.assertEqual(row(result, "wealth")["range_text"], "[34/5,382/55)")
            self.assertEqual(row(result, "credit")["range_text"], "[3,4)")


if __name__ == "__main__":
    unittest.main()
