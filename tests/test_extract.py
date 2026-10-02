import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/annual-report-analysis/scripts"))
from extract import extract, page_numbers


class ExtractionChecks(unittest.TestCase):
    def test_page_numbers_are_one_based_and_bounded(self):
        self.assertEqual(page_numbers("1-2,4", 4), [1, 2, 4])
        for spec in ("0", "5", "3-1"):
            with self.assertRaises(ValueError):
                page_numbers(spec, 4)

    def test_html_preserves_locator_and_table_without_running_scripts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.html"
            path.write_text('<html><body><script>invented revenue</script><h1 id="financials">Statements</h1><table><tr><th>Revenue</th><td>100</td></tr></table></body></html>', encoding="utf-8")
            data = extract(path)
            self.assertEqual(data["blocks"][0]["locator"], "#financials")
            self.assertEqual(data["blocks"][1]["rows"], [["Revenue", "100"]])
            self.assertNotIn("invented", str(data["blocks"]))


if __name__ == "__main__":
    unittest.main()
