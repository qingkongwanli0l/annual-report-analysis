"""Independent cash examples, PIT counterexamples and offline CLI checks."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "annual-report-analysis" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import panel
import scenarios
from workpaper import QuantitativeResult


def cash_case():
    source = {"source": "Constructed analytical example, not an issuer disclosure", "available_at": "2024-12-31"}
    return {
        "entity": "Constructed industrial company", "as_of": "2024-12-31", "currency": "CNY",
        "amount_scale": 1000000, "interest_basis_days": 365, "payables_denominator": "cost_of_sales",
        "opening": {**source, "date": "2024-12-31", "cash": 80, "receivables": 100,
                    "inventory": 60, "payables": 60, "debt": 200},
        "minimum_cash": {**source, "value": 20},
        "periods": [{**source, "start": "2025-01-01", "end": "2025-12-31",
                     "volume": 1000, "unit_price": 1, "unit_variable_cost": .6,
                     "fixed_cash_cost": 250, "depreciation": 30, "capex": 40,
                     "tax_rate": .25, "dso": 36.5, "dio": 36.5, "dpo": 36.5,
                     "interest_rate": .05, "drawdown": 0, "principal": 100, "dividends": 20}],
    }


def annual_record(entity, year, margin, published, version="original"):
    return {"id": f"{entity}-{year}-{version}", "entity": entity,
            "period_start": f"{year}-01-01", "period_end": f"{year}-12-31",
            "available_at": published + "T10:00:00+08:00", "version": version,
            "industry": "industrial", "accounting_basis": "example-GAAP", "currency": "CNY",
            "revenue": 100, "cost_of_sales": 100 * (1-margin), "total_assets": 200,
            "source": f"Constructed source {entity}/{year}/{version}"}


def panel_case():
    records = []
    # Independent data-generating relationship y = .1 + .5x, three matured training pairs.
    for entity, before, after in [("A", .1, .15), ("B", .2, .2), ("C", .3, .25)]:
        records.extend([annual_record(entity, 2021, before, "2022-03-01"),
                        annual_record(entity, 2022, after, "2023-03-01")])
    records.extend([annual_record("D", 2023, .4, "2024-03-01"),
                    annual_record("D", 2023, .9, "2024-09-01", "revision"),
                    annual_record("D", 2023, .99, "2025-08-01", "future-revision"),
                    annual_record("D", 2024, .3, "2025-03-01"),
                    annual_record("E", 2023, -.2, "2024-03-01")])
    return {"as_of": "2025-06-30T23:59:59+08:00", "training_cutoff": "2023-06-30T23:59:59+08:00",
            "peer_period_end": "2023-12-31", "industry": "industrial", "accounting_basis": "example-GAAP",
            "currency": "CNY", "universe_definition": "A-E constructed examples; no empirical validity claim",
            "records": records}


class ScenarioTests(unittest.TestCase):
    def test_independent_base_and_downside_cash_bridge(self):
        data = cash_case()
        base = scenarios.run(data)["rows"][0]
        for key, expected in {"ebitda": 150, "net_income": 82.5, "cfo": 112.5,
                              "cash_end": 32.5, "debt_end": 100, "cash_headroom": 12.5}.items():
            self.assertAlmostEqual(base[key], expected)
        data["periods"][0].update(volume=900, dso=46.5)
        down = scenarios.run(data)["rows"][0]
        self.assertAlmostEqual(down["net_income"], 52.5)
        self.assertAlmostEqual(down["receivables_end"], 114.65753424657534)
        self.assertAlmostEqual(down["cfo"], 67.84246575342466)
        self.assertAlmostEqual(down["cash_end"], -12.15753424657534)
        self.assertAlmostEqual(down["funding_needed_to_floor"], 32.15753424657534)
        self.assertEqual(down["drawdown"], 0)
        self.assertEqual(down["status"], "unfunded_cash_shortfall")

    def test_second_period_uses_actual_cash_and_debt_rollforward(self):
        data = cash_case()
        second = {**data["periods"][0], "start": "2026-01-01", "end": "2026-12-31", "principal": 50}
        data["periods"].append(second)
        rows = scenarios.run(data)["rows"]
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[1]["cash_interest"], 5)
        self.assertAlmostEqual(rows[1]["net_income"], 86.25)
        self.assertAlmostEqual(rows[1]["cash_end"], 38.75)
        self.assertAlmostEqual(rows[1]["debt_end"], 50)
        data["periods"][0].update(volume=900, dso=46.5)
        failed = scenarios.run(data)
        self.assertEqual(len(failed["rows"]), 1)
        self.assertEqual(failed["unprojected_periods"], 1)

    def test_purchase_denominator_is_not_cost_proxy(self):
        data = cash_case()
        data["payables_denominator"] = "purchases"
        data["periods"][0].update(volume=900, dso=46.5)
        row = scenarios.run(data)["rows"][0]
        self.assertAlmostEqual(row["implied_purchases"], 534)
        self.assertAlmostEqual(row["payables_end"], 53.4)
        self.assertAlmostEqual(row["cash_end"], -12.75753424657534)

    def test_negative_inventory_implied_purchases_are_not_cash_release(self):
        for denominator in ('cost_of_sales', 'purchases'):
            data = cash_case()
            data['payables_denominator'] = denominator
            data['opening']['inventory'] = 100
            data['periods'][0].update(volume=100, unit_variable_cost=.2, dio=0)
            with self.assertRaisesRegex(ValueError, 'negative implied purchases'):
                scenarios.run(data)

    def test_reverse_cannot_change_the_past_or_claim_a_unique_flat_root(self):
        data = cash_case()
        data['periods'].append({**data['periods'][0], 'start':'2026-01-01', 'end':'2026-12-31', 'principal':50})
        data['reverse'] = dict(period_index=1, driver='dso', bounds=[0,60], test_date='2025-12-31',
                               target_cash=32.5, definition='Constructed cash boundary', source='Constructed input',
                               available_at='2024-12-31')
        with self.assertRaisesRegex(ValueError, 'cannot follow'):
            scenarios.run(data)
        data['periods'] = data['periods'][:1]
        data['opening'].update(receivables=0, inventory=0, payables=0, debt=0)
        data['periods'][0].update(volume=0, fixed_cash_cost=0, depreciation=0, capex=0, principal=0, dividends=0)
        data['reverse'].update(period_index=0, target_cash=80)
        self.assertEqual(scenarios.run(data)['reverse']['status'], 'not_identified')

    def test_reverse_boundary_has_independent_closed_form(self):
        data = cash_case()
        data["reverse"] = {"period_index": 0, "driver": "dso", "bounds": [36.5, 60],
                           "test_date": "2025-12-31", "target_cash": 20,
                           "definition": "Minimum operating cash, not a legal default definition",
                           "source": "Constructed budget", "available_at": "2024-12-31"}
        reverse = scenarios.run(data)["reverse"]
        # Starting headroom 12.5; each DSO day consumes 1000/365 cash.
        self.assertAlmostEqual(reverse["driver_value"], 41.0625)
        self.assertAlmostEqual(reverse["rows"][0]["cash_end"], 20)
        data.pop("reverse")
        data["periods"][0]["dso"] = 41.0
        self.assertGreater(scenarios.run(data)["rows"][0]["cash_end"], 20)
        data["periods"][0]["dso"] = 41.1
        self.assertLess(scenarios.run(data)["rows"][0]["cash_end"], 20)

    def test_input_dated_thresholds_and_future_assumption(self):
        data = cash_case()
        term = {"label": "Illustrative contractual cash condition", "definition": "Cash at stated date",
                "test_date": "2025-12-31", "metric": "cash_end", "relation": "at_least", "threshold": 40,
                "source": "Illustrative contract clause", "available_at": "2024-12-31"}
        data["contracts"] = [term, {**term, "test_date": "2025-06-30"}]
        result = scenarios.run(data)
        self.assertEqual(result["contracts"][0]["status"], "outside_input_threshold")
        self.assertEqual(result["contracts"][1]["status"], "not_tested")
        self.assertAlmostEqual(result["rows"][0]["cash_end"], 32.5)
        data["periods"][0]["available_at"] = "2025-01-01"
        with self.assertRaises(ValueError):
            scenarios.run(data)


class PanelTests(unittest.TestCase):
    def test_pit_revisions_differ_from_historical_prediction_origins(self):
        result = panel.run(panel_case())
        self.assertIn("D-2023-revision", result["selected_peer_versions"])
        self.assertNotIn("D-2023-future-revision", result["selected_peer_versions"])
        prediction = next(r for r in result["rows"] if r["kind"] == "out_of_time_prediction")
        self.assertEqual(prediction["origin_id"], "D-2023-original")
        self.assertAlmostEqual(prediction["predicted"], .3)
        self.assertAlmostEqual(result["model"]["intercept"], .1)
        self.assertAlmostEqual(result["model"]["slope"], .5)
        self.assertAlmostEqual(result["model"]["test_mae"], 0)
        self.assertAlmostEqual(result["model"]["baseline_mae"], .1)
        loss_peer = next(r for r in result["rows"] if r.get("record_id") == "E-2023-original")
        self.assertAlmostEqual(loss_peer["gross_margin"], -.2)
        self.assertAlmostEqual(loss_peer["gross_profit_to_assets"], -.1)

    def test_unmatured_labels_do_not_create_validation_results(self):
        data = panel_case()
        data["as_of"] = "2024-06-30T23:59:59+08:00"
        result = panel.run(data)
        self.assertIn("D-2023-original", result["selected_peer_versions"])
        self.assertEqual(result["model"]["test_n"], 0)
        self.assertIsNone(result["model"]["test_mae"])
        self.assertEqual(result["model"]["validation_status"], "no_matured_holdout")
        self.assertIn("D-2023-original", [p["record_id"] for p in result["pending_outcomes"]])

    def test_no_model_from_two_pairs_or_zero_revenue(self):
        data = panel_case()
        data["records"] = [r for r in data["records"] if r["entity"] != "C"]
        result = panel.run(data)
        self.assertEqual(result["model"]["status"], "not_estimated")
        self.assertNotIn("test_mae", result["model"])
        for r in data["records"]:
            if r["entity"] == "E":
                r["revenue"] = 0
        row = next(r for r in panel.run(data)["rows"] if r.get("entity") == "E")
        self.assertIsNone(row["gross_margin"])

    def test_late_predictor_cannot_use_already_public_outcome(self):
        data = panel_case()
        data["records"] = [r for r in data["records"] if r["entity"] != "D"] + [
            annual_record("D", 2023, .4, "2025-04-01"), annual_record("D", 2024, .3, "2025-03-01")]
        result = panel.run(data)
        self.assertEqual(result["model"]["test_n"], 0)
        self.assertTrue(any(p["reason"] == "outcome already public at predictor origin" for p in result["excluded_pairs"]))

    def test_snapshot_reproduces_both_modules_and_cli(self):
        for module, data in [(scenarios, cash_case()), (panel, panel_case())]:
            original = deepcopy(data)
            result = module.run(data)
            self.assertEqual(data, original)
            self.assertEqual(module.run(result["input_snapshot"]), result)
            adapted = QuantitativeResult.model_validate(module.to_workpaper_result(
                result, "quantitative-example", "Constructed example", [], []))
            self.assertEqual(adapted.artifact, result)
            with tempfile.TemporaryDirectory() as folder:
                source, output = Path(folder) / "input.json", Path(folder) / "result.json"
                source.write_text(json.dumps(data), encoding="utf-8")
                subprocess.run([sys.executable, str(SCRIPTS / (module.__name__ + ".py")), str(source),
                                "--output", str(output)], check=True, capture_output=True, text=True)
                self.assertEqual(json.loads(output.read_text(encoding="utf-8")), result)


if __name__ == "__main__":
    unittest.main()
