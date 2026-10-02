from pathlib import Path
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/annual-report-analysis/scripts'))
from calculate import evaluate
from export import prepare, word, workbook
from recovery import RecoveryInput, calculate_recovery
from test_recovery import example
from workpaper import Workpaper


class ExportTests(unittest.TestCase):
    def test_recovery_results_reach_report_and_editable_workbook(self):
        result = calculate_recovery(RecoveryInput.model_validate(example()))
        w = Workpaper.model_validate({
            'mandate': dict(title='Constructed recovery', entity='Borrower A', industry='synthetic',
                            purpose='Verify recoveries survive export', period_start='2026-01-01',
                            period_end='2026-10-02', cutoff='2026-10-02', accounting_basis='Scenario',
                            scope='single entity', version='test'),
            'sources': [dict(id='s', title='Synthetic fixture', url='test_recovery.py', published='2026-10-02')],
            'evidence': [dict(id=k, source='s', locator='example()', observation='Constructed inputs',
                              reliability='Mathematical example only') for k in result.evidence],
            'facts': [], 'findings': [], 'sections': [], 'quantitative': [result],
        })
        data = prepare(w, evaluate(w))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            word(data, root/'report.docx')
            workbook(w, data, root/'workbook.xlsx')
            with ZipFile(root/'report.docx') as z:
                text = ' '.join(ET.fromstring(z.read('word/document.xml')).itertext())
            self.assertIn('Secured loan', text)
            self.assertIn('85.00', text)
            self.assertIn('85.00%', text)
            self.assertNotIn('已执行程序与待核工作', text)
            with ZipFile(root/'workbook.xlsx') as z:
                ns = {'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                sheets = ET.fromstring(z.read('xl/workbook.xml')).find('x:sheets', ns)
                recovery_index = next(i for i, s in enumerate(sheets, 1) if s.get('name') == 'Q1Recovery')
                xml = ET.fromstring(z.read(f'xl/worksheets/sheet{recovery_index}.xml'))
                cell = xml.find(".//x:c[@r='E2']", ns)
                self.assertEqual(cell.find('x:f', ns).text, 'C2+D2')
                self.assertEqual(float(cell.find('x:v', ns).text), 85)


if __name__ == '__main__':
    unittest.main()
