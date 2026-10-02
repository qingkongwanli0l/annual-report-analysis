"""Check cached Excel results and stale workpaper rejection."""

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/annual-report-analysis/scripts"))
from calculate import calculate
from export import export_excel

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


class ExportRegressions(unittest.TestCase):
    def setUp(self):
        self.data = calculate(json.loads((ROOT / "examples/moutai-2024/workpaper.json").read_text(encoding="utf-8")))

    def test_excel_formula_has_real_cached_result(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "book.xlsx"
            export_excel(self.data, output)
            with zipfile.ZipFile(output) as book:
                sheet = ET.fromstring(book.read("xl/worksheets/sheet4.xml"))
                cell = sheet.find(".//s:c[@r='C3']", NS)
                self.assertIn("Normalized", cell.find("s:f", NS).text)
                self.assertAlmostEqual(float(cell.find("s:v", NS).text), 0.157119512947908)

    def test_missing_values_and_source_text_do_not_become_formulas(self):
        self.data["sources"][0]["title"] = '=WEBSERVICE("https://invalid.invalid")'
        self.data["facts"] = [f for f in self.data["facts"] if f["metric"] != "cfo"]
        self.data.pop("analysis")
        self.data = calculate(self.data)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "book.xlsx"
            export_excel(self.data, output)
            with zipfile.ZipFile(output) as book:
                sheet = ET.fromstring(book.read("xl/worksheets/sheet4.xml"))
                row = 2 + next(i for i, item in enumerate(self.data["calculations"]) if item["id"] == "cash_profit_ratio")
                cell = sheet.find(f".//s:c[@r='C{row}']", NS)
                self.assertEqual(cell.get("t"), "s")
                self.assertIsNone(cell.find("s:f", NS))
                source = ET.fromstring(book.read("xl/worksheets/sheet6.xml"))
                self.assertIsNone(source.find(".//s:f", NS))

    def test_export_rejects_stale_calculated_values(self):
        self.data["facts"][0]["value"] = "1"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "stale.json"
            destination = Path(directory) / "result"
            input_file.write_text(json.dumps(self.data), encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "skills/annual-report-analysis/scripts/export.py"),
                                     str(input_file), "--output-dir", str(destination)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Cached calculations do not match", result.stderr)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
