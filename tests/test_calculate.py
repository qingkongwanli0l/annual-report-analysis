"""Small regression examples target accounting mistakes, not report wording."""

import copy
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/annual-report-analysis/scripts"))
from calculate import calculate


def workpaper():
    return {"company": {"name": "Synthetic regression case", "identifier": "TEST", "market": "A-share",
            "industry": "non-financial", "accounting_standard": "CAS", "scope": "consolidated",
            "currency": "CNY", "period_start": "2024-01-01", "period_end": "2024-12-31",
            "prior_period_start": "2023-01-01", "prior_period_end": "2023-12-31",
            "display_unit": "元", "display_multiplier": "1", "language": "en"},
            "sources": [{"id": "test", "title": "Synthetic unit test", "url": "", "published": None}], "facts": []}


def add(data, metric, value, year=2024, instant=False, **changes):
    fact = {"id": f"{metric}_{year}", "metric": metric, "label": metric, "value": str(value) if value is not None else None,
            "raw_value": str(value), "currency": "CNY", "unit_multiplier": "1", "period_start": None if instant else f"{year}-01-01",
            "period_end": f"{year}-12-31", "scope": "consolidated", "standard": "CAS", "source_id": "test",
            "locator": "Synthetic fixture", "restated": False, "basis": "reported"}
    fact.update(changes)
    data["facts"].append(fact)
    return fact


def result(data, identifier, group="calculations"):
    return next(row for row in calculate(data)[group] if row["id"] == identifier)


class AccountingRegressions(unittest.TestCase):
    def test_cash_rollforward_includes_fx_and_missing_is_not_zero(self):
        data = workpaper()
        add(data, "cash_equivalents", "100.00", 2023, instant=True)
        add(data, "cash_equivalents", "132.00", instant=True)
        for key, value in (("cfo", "50.00"), ("cfi", "-20.00"), ("cff", "0.00"), ("fx_effect", "2.00")):
            add(data, key, value)
        self.assertEqual(result(data, "cash_rollforward", "checks")["status"], "matched")
        data["facts"].pop()
        self.assertEqual(result(data, "cash_rollforward", "checks")["status"], "unavailable")

    def test_roa_uses_average_assets_and_requires_opening(self):
        data = workpaper()
        add(data, "net_income", 30)
        add(data, "assets", 100, 2023, instant=True)
        add(data, "assets", 200, instant=True)
        self.assertEqual(Decimal(result(data, "roa")["value"]), Decimal("0.2"))
        data["facts"].pop(1)
        self.assertIsNone(result(data, "roa")["value"])

    def test_units_convert_before_growth(self):
        data = workpaper()
        add(data, "revenue", "1.20", unit_multiplier="100000000")
        add(data, "revenue", "10000", 2023, unit_multiplier="10000")
        self.assertEqual(Decimal(result(data, "revenue_growth")["value"]), Decimal("0.2"))

    def test_parent_scope_currency_and_ytd_cannot_leak(self):
        for change in ({"scope": "parent"}, {"currency": "USD"}, {"period_start": "2024-04-01"}, {"standard": "IFRS"}):
            with self.subTest(change=change):
                data = workpaper()
                add(data, "revenue", 100, **change)
                add(data, "revenue", 90, 2023)
                self.assertIsNone(result(data, "revenue_growth")["value"])

    def test_duplicate_restatement_needs_explicit_selection(self):
        data = workpaper()
        add(data, "revenue", 120)
        old = add(data, "revenue", 100, 2023)
        add(data, "revenue", 110, 2023, id="revenue_restated", restated=True)
        self.assertIsNone(result(data, "revenue_growth")["value"])
        old["use_for_analysis"] = False
        self.assertAlmostEqual(float(result(data, "revenue_growth")["value"]), 120 / 110 - 1)

    def test_negative_baseline_and_zero_denominator_remain_unavailable(self):
        data = workpaper()
        add(data, "net_income", 10)
        add(data, "net_income", -10, 2023)
        add(data, "revenue", 0)
        self.assertIsNone(result(data, "net_income_growth")["value"])
        self.assertEqual(result(data, "net_income_change")["value"], "20")
        self.assertIsNone(result(data, "net_margin")["value"])

    def test_negative_equity_not_presented_as_healthy_roe(self):
        data = workpaper()
        add(data, "parent_net_income", -10)
        add(data, "parent_equity", -100, 2023, instant=True)
        add(data, "parent_equity", -90, instant=True)
        self.assertIsNone(result(data, "roe")["value"])

    def test_financial_industries_skip_industrial_metrics(self):
        for industry in ("bank", "insurance", "securities"):
            data = workpaper()
            data["company"]["industry"] = industry
            add(data, "current_assets", 10, instant=True)
            add(data, "current_liabilities", 2, instant=True)
            self.assertIsNone(result(data, "current_ratio")["value"])

    def test_balance_difference_is_not_silently_passed(self):
        data = workpaper()
        for key, value in (("assets", "100.00"), ("liabilities", "60.00"), ("equity", "30.00")):
            add(data, key, value, instant=True)
        row = result(data, "balance_sheet", "checks")
        self.assertEqual(row["status"], "difference")
        self.assertEqual(Decimal(row["value"]), 10)

    def test_precision_uses_raw_display_not_stripped_decimal_value(self):
        data = workpaper()
        for key, value in (("assets", 100), ("liabilities", 60), ("equity", 39)):
            add(data, key, value, instant=True, raw_value=f"{value}.00")
        row = result(data, "balance_sheet", "checks")
        self.assertEqual(row["status"], "difference")
        self.assertEqual(Decimal(row["tolerance"]), Decimal("0.015"))

    def test_nonadjacent_years_do_not_become_yoy(self):
        data = workpaper()
        data["company"].update(prior_period_start="2021-01-01", prior_period_end="2021-12-31")
        add(data, "revenue", 120)
        add(data, "revenue", 100, 2021)
        self.assertIsNone(result(data, "revenue_growth")["value"])

    def test_evidence_and_finite_values_are_required(self):
        data = workpaper()
        fact = add(data, "revenue", 100)
        data["analysis"] = {"summary": [{"text": "Claim", "evidence": ["fact:invented"]}]}
        with self.assertRaisesRegex(ValueError, "Unknown narrative"):
            calculate(data)
        data.pop("analysis")
        fact["value"] = "NaN"
        with self.assertRaisesRegex(ValueError, "finite"):
            calculate(data)

    def test_calculation_does_not_mutate_input(self):
        data = workpaper()
        add(data, "revenue", 100)
        original = copy.deepcopy(data)
        calculate(data)
        self.assertEqual(data, original)


if __name__ == "__main__":
    unittest.main()
