from pathlib import Path
import json
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
    def test_monetary_reconciliation_keeps_a_real_cent_difference(self):
        ctx = dict(entity='A', scope='consolidated', start='2025-01-01', end='2025-12-31',
                   aggregation='flow', basis='test', measure='money', currency='CNY')
        for right, residual, status in [('200000000000.22', '0.00', 'within_input_tolerance'),
                                        ('200000000000.23', '0.01', 'unexplained_difference')]:
            with self.subTest(right=right):
                w = Workpaper.model_validate({
                    'mandate': dict(title='Decimal precision', entity='A', industry='synthetic', purpose='Precision test',
                                    period_start='2025-01-01', period_end='2025-12-31', cutoff='2026-10-02',
                                    accounting_basis='test', scope='consolidated', version='test'),
                    'sources': [], 'evidence': [],
                    'facts': [dict(id=k, label=k, concept=k, value=v, context=ctx, evidence=[],
                                   state='assumption', note='Synthetic precision test')
                              for k, v in [('left', '100000000000.11'), ('right', right), ('total', '300000000000.33')]],
                    'calculations': [dict(id='sum', label='Sum', op='sum', terms=[{'ref':'left'}, {'ref':'right'}],
                                          context=ctx, definition='left+right', interpretation='Synthetic')],
                    'reconciliations': [dict(id='check', label='Exact', actual='sum', expected='total', tolerance='0',
                                             basis='Exact decimal inputs, two decimal places')],
                    'findings': [], 'sections': [],
                })
                result = evaluate(w)
                self.assertEqual(result['reconciliations'][0]['residual'], residual)
                self.assertEqual(result['reconciliations'][0]['status'], status)
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory)/'workbook.xlsx'
                    workbook(w, prepare(w, result), path)
                    with ZipFile(path) as z:
                        ns = {'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                        sheets = ET.fromstring(z.read('xl/workbook.xml')).find('x:sheets', ns)
                        index = next(i for i, s in enumerate(sheets, 1) if s.get('name') == 'Reconciliations')
                        xml = ET.fromstring(z.read(f'xl/worksheets/sheet{index}.xml'))
                    cell = xml.find(".//x:c[@r='E2']", ns)
                    self.assertIn('ROUND(', cell.find('x:f', ns).text)
                    self.assertEqual(float(cell.find('x:v', ns).text), float(residual))
                    self.assertEqual(xml.find(".//x:c[@r='J2']/x:v", ns).text, '2')

    def test_procedure_and_request_numbers_are_resolved_in_both_documents(self):
        raw = json.loads((Path(__file__).resolve().parents[1]/'examples/catl-2025/workpaper.json').read_text(encoding='utf-8'))
        raw['procedures'][0]['result'] = 'Cash bridge {{cfo_bridge}}'
        raw['requests'][0]['request'] = 'Explain {{cfo_bridge}}'
        w = Workpaper.model_validate(raw)
        data = prepare(w, evaluate(w))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            word(data, root/'report.docx')
            workbook(w, data, root/'workbook.xlsx')
            for file, part in [('report.docx', 'word/document.xml'), ('workbook.xlsx', 'xl/sharedStrings.xml')]:
                with ZipFile(root/file) as z:
                    text = ' '.join(ET.fromstring(z.read(part)).itertext())
                self.assertIn('Cash bridge 1,332.20', text)
                self.assertIn('Explain 1,332.20', text)
                self.assertNotIn('{{cfo_bridge}}', text)
        raw['procedures'][0]['result'] = 'Unknown {{typo_cfo_missing}}'
        w = Workpaper.model_validate(raw)
        with self.assertRaisesRegex(ValueError, 'unknown numeric token'):
            prepare(w, evaluate(w))

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
