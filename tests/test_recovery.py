"""Hand-calculated recovery cases and unsupported-input checks."""
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "annual-report-analysis" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from pydantic import ValidationError
from recovery import RecoveryInput, calculate_recovery
from workpaper import QuantitativeResult


def example():
    return {
        "id": "recovery_base", "label": "Single estate hand calculation",
        "entity": "Borrower A", "as_of": "2026-10-02", "currency": "CNY",
        "unit": "million", "quantum": "0.01", "scope": "single_entity_nonoverlapping_pools",
        "unencumbered_value": "50", "estate_costs": "10",
        "value_basis": "Scenario cash realization; not book value",
        "priority_basis": "Documented ranks; collateral surplus belongs to the same estate",
        "input_refs": [], "evidence": ["e_estate"],
        "assumptions": ["Independent asset pool; no guarantees or subrogation claims"],
        "pools": [{"id": "plant", "label": "Plant collateral", "value": "90", "costs": "10", "evidence": ["e_plant"]}],
        "claims": [
            {"id": "A", "obligation_id": "loan_A", "label": "Secured loan", "amount": "100", "priority": 1,
             "collateral_pool": "plant", "deficiency_treatment": "general", "deficiency_priority": 2, "evidence": ["e_A"]},
            {"id": "B", "obligation_id": "claim_B", "label": "Senior unsecured", "amount": "20", "priority": 1,
             "deficiency_treatment": "not_applicable", "evidence": ["e_B"]},
            {"id": "C", "obligation_id": "loan_C", "label": "Ordinary unsecured", "amount": "60", "priority": 2,
             "deficiency_treatment": "not_applicable", "evidence": ["e_C"]},
        ],
    }


def results(data):
    result = calculate_recovery(RecoveryInput.model_validate(data))
    totals = {r["claim_id"]: r for r in result.artifact["rows"] if r["kind"] == "claim_total"}
    return result, totals


class RecoveryTests(unittest.TestCase):
    def test_independent_hand_calculation(self):
        # Plant: 90-10=80 to A; deficiency A=20.
        # General: 50-10=40; B=20; remaining20*(A20,C60)/80=(5,15).
        result, totals = results(example())
        self.assertEqual({k: Decimal(v["result"]) for k, v in totals.items()},
                         {"A": Decimal(85), "B": Decimal(20), "C": Decimal(15)})
        self.assertEqual(Decimal(totals["A"]["unpaid"]), 15)
        self.assertEqual(Decimal(totals["C"]["recovery_rate"]), Decimal("0.25"))
        reconciliation = next(r for r in result.artifact["rows"] if r["kind"] == "reconciliation")
        self.assertEqual(Decimal(reconciliation["result"]), 0)
        self.assertEqual(result.artifact["input_snapshot"]["unencumbered_value"], "50")
        self.assertEqual(result.artifact["method"], result.method)
        for row in result.artifact["rows"]:
            self.assertTrue(all(k in row for k in ("raw_input", "assumptions", "formula", "result", "evidence")))
        QuantitativeResult.model_validate_json(result.model_dump_json())

    def test_duplicate_claim_or_economic_obligation_rejected(self):
        for field in ("id", "obligation_id"):
            with self.subTest(field=field):
                data = example()
                data["claims"][2][field] = data["claims"][0][field]
                with self.assertRaisesRegex(ValidationError, "duplicate"):
                    RecoveryInput.model_validate(data)

    def test_value_insufficient_even_for_costs(self):
        data = example()
        data["pools"][0]["value"] = "5"
        data["unencumbered_value"] = "3"
        result, totals = results(data)
        self.assertTrue(all(Decimal(row["result"]) == 0 for row in totals.values()))
        cost_rows = [r for r in result.artifact["rows"] if r["kind"] == "cost"]
        self.assertEqual(sum(Decimal(r["result"]) for r in cost_rows), 8)
        self.assertEqual(sum(Decimal(r["unpaid"]) for r in cost_rows), 12)
        self.assertEqual(Decimal(result.artifact["rows"][-1]["result"]), 0)

    def test_nonrecourse_and_collateral_surplus_are_not_double_counted(self):
        data = example()
        data["claims"][0]["amount"] = "40"
        data["claims"][0]["deficiency_treatment"] = "nonrecourse"
        data["claims"][0].pop("deficiency_priority")
        result, totals = results(data)
        # Pool surplus40 plus general50 less costs10 =>80; B20 and C60.
        self.assertEqual({k: Decimal(v["result"]) for k, v in totals.items()},
                         {"A": Decimal(40), "B": Decimal(20), "C": Decimal(60)})
        self.assertEqual(Decimal(result.artifact["rows"][-1]["result"]), 0)
        data["pools"][0]["value"] = "20"
        _, totals = results(data)
        self.assertEqual(Decimal(totals["A"]["result"]), 10)
        self.assertEqual(Decimal(totals["A"]["general"]), 0)

    def test_pari_passu_rounding_conserves_smallest_unit(self):
        data = example()
        data["pools"] = []
        data["unencumbered_value"] = "0.01"
        data["estate_costs"] = "0"
        for claim in data["claims"]:
            claim["amount"] = "1"
            claim["priority"] = 1
            claim["deficiency_treatment"] = "not_applicable"
            claim.pop("collateral_pool", None)
            claim.pop("deficiency_priority", None)
        _, totals = results(data)
        data["claims"].reverse()
        _, reversed_totals = results(data)
        expected = {"A": Decimal(0), "B": Decimal("0.01"), "C": Decimal(0)}
        # claim_B sorts before loan_A and loan_C when remainders are identical.
        self.assertEqual({k: Decimal(v["result"]) for k, v in totals.items()}, expected)
        self.assertEqual({k: Decimal(v["result"]) for k, v in reversed_totals.items()}, expected)

    def test_unsupported_or_incomplete_inputs_fail(self):
        variants = []
        data = example()
        data["claims"][0].pop("deficiency_priority")
        variants.append(data)
        data = example()
        data["claims"][0]["collateral_pool"] = "missing"
        variants.append(data)
        data = example()
        data["cross_guarantees"] = [{"from": "A", "to": "B"}]
        variants.append(data)
        data = example()
        data["unencumbered_value"] = "0.001"
        variants.append(data)
        data = example()
        data["unencumbered_value"] = "NaN"
        variants.append(data)
        for data in variants:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                RecoveryInput.model_validate(data)

    def test_cli_writes_serializable_workpaper_result(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            output = Path(directory) / "result.json"
            source.write_text(json.dumps(example()), encoding="utf-8")
            subprocess.run([sys.executable, "-B", str(SCRIPTS / "recovery.py"), str(source), "--output", str(output)], check=True)
            result = QuantitativeResult.model_validate_json(output.read_text(encoding="utf-8"))
            self.assertEqual(result.artifact["version"], "1.0")


if __name__ == "__main__":
    unittest.main()
