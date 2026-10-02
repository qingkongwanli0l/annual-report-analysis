"""Small official-report samples; source locations and scope are documented separately."""

import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/annual-report-analysis/scripts"))
from calculate import calculate

WORKPAPERS = json.loads((Path(__file__).parent / "fixtures/international.json").read_text(encoding="utf-8"))


class InternationalSamples(unittest.TestCase):
    def test_tencent_ifrs_reported_profit_and_cny_millions(self):
        data = calculate(next(item for item in WORKPAPERS if item["company"]["identifier"] == "00700.HK"))
        rows = {row["id"]: row for row in data["calculations"]}
        facts = {row["id"]: row for row in data["facts"]}
        self.assertEqual(facts["net_income_2024"]["normalized_value"], "196467000000")
        self.assertEqual(facts["parent_net_income_2024"]["normalized_value"], "194073000000")
        self.assertAlmostEqual(Decimal(rows["revenue_growth"]["value"]), Decimal("0.084139142714055"), places=12)
        self.assertAlmostEqual(Decimal(rows["net_margin"]["value"]), Decimal("0.297561404119911"), places=12)
        self.assertEqual(set(rows["net_margin"]["inputs"]), {"net_income_2024", "revenue_2024"})
        self.assertTrue(all(row["status"] == "unavailable" for row in data["checks"]))

    def test_apple_us_gaap_52_and_53_week_fiscal_years(self):
        data = calculate(next(item for item in WORKPAPERS if item["company"]["identifier"] == "AAPL"))
        rows = {row["id"]: row for row in data["calculations"]}
        facts = {row["id"]: row for row in data["facts"]}
        self.assertEqual(facts["revenue_2024"]["normalized_value"], "391035000000")
        self.assertEqual(rows["revenue_growth"]["period_end"], "2024-09-28")
        self.assertAlmostEqual(Decimal(rows["revenue_growth"]["value"]), Decimal("0.020219940775141"), places=12)
        self.assertAlmostEqual(Decimal(rows["net_margin"]["value"]), Decimal("0.239712557699439"), places=12)
        self.assertTrue(all(row["status"] == "unavailable" for row in data["checks"]))


if __name__ == "__main__":
    unittest.main()
