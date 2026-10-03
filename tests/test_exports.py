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
import scenarios
from test_quantitative import manufacturing_case
from test_recovery import example
from workpaper import Workpaper


class ExportTests(unittest.TestCase):
    def test_historical_cash_artifact_cannot_be_relabelled_as_v2(self):
        raw = json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/legacy-scenario-workpaper.json').read_text(encoding='utf-8'))
        raw['quantitative'] = raw['quantitative'][:1]
        w = Workpaper.model_validate(raw)
        with self.assertRaisesRegex(ValueError, 'historical model'):
            prepare(w, evaluate(w))
        raw['quantitative'][0]['method'] = 'operating_cash_scenario_v2'
        raw['quantitative'][0]['artifact']['method'] = 'operating_cash_scenario_v2'
        w = Workpaper.model_validate(raw)
        with self.assertRaisesRegex(ValueError, 'unit_cost_of_sales'):
            prepare(w, evaluate(w))

    def test_manufacturing_cost_decomposition_reaches_cash_formulas(self):
        for inventory_change, ending_inventory, cash in [(0, 60, 100), (10, 90, 110), (-10, 70, 110)]:
            with self.subTest(inventory_depreciation_change=inventory_change):
                source = manufacturing_case()
                if inventory_change:
                    source['periods'][0].update(depreciation=30, depreciation_in_cost_of_sales=30,
                        inventory_cash_conversion=20, inventory_depreciation_change=inventory_change,
                        dio=ending_inventory*365/120, source='Constructed manufacturing D&A and payroll cash bridge')
                artifact = scenarios.run(source)
                w = Workpaper.model_validate({
                    'mandate': dict(title='Manufacturing cash', entity='Constructed', industry='manufacturing',
                                    purpose='Independent direct cash bridge', period_start='2025-01-01',
                                    period_end='2025-12-31', cutoff='2024-12-31', accounting_basis='Constructed',
                                    scope='single entity', version='v2'),
                    'sources': [], 'evidence': [], 'facts': [], 'findings': [], 'sections': [],
                    'quantitative': [scenarios.to_workpaper_result(artifact, 'manufacturing', 'Manufacturing', [], [])],
                })
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    data = prepare(w, evaluate(w))
                    workbook(w, data, root/'workbook.xlsx')
                    word(data, root/'report.docx')
                    with ZipFile(root/'workbook.xlsx') as z:
                        ns = {'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                        sheets = ET.fromstring(z.read('xl/workbook.xml')).find('x:sheets', ns)
                        index = next(i for i, s in enumerate(sheets, 1) if s.get('name') == 'Q1Cash')
                        xml = ET.fromstring(z.read(f'xl/worksheets/sheet{index}.xml'))
                    for ref, expected in [('L2', 100), ('M2', 40), ('V2', cash)]:
                        self.assertAlmostEqual(float(xml.find(f".//x:c[@r='{ref}']/x:v", ns).text), expected)
                    for ref, formula in [('D2', "B2-C2+'Q1Drivers'!R2-'Q1Drivers'!G2"),
                                         ('L2', "C2+K2-'Q1Inputs'!B8-'Q1Drivers'!S2-'Q1Drivers'!R2-'Q1Drivers'!T2"),
                                         ('P2', "I2+E2+'Q1Drivers'!T2-O2")]:
                        self.assertIn(formula, xml.find(f".//x:c[@r='{ref}']/x:f", ns).text)
                    self.assertIn("COUNT('Q1Drivers'!A2:T2)=20", xml.find(".//x:c[@r='V2']/x:f", ns).text)
                    with ZipFile(root/'report.docx') as z:
                        text = ' '.join(ET.fromstring(z.read('word/document.xml')).itertext())
                    self.assertIn(f'{cash:,.4f}', text)
                    self.assertIn('Supplier purchases exclude internal production cash conversion', text)

    def test_incomplete_ratio_or_growth_remains_unavailable_in_workbook(self):
        for operation in ('ratio', 'growth'):
            with self.subTest(operation=operation):
                raw = json.loads((Path(__file__).resolve().parents[1]/'examples/catl-2025/workpaper.json').read_text(encoding='utf-8'))
                calculation = next(c for c in raw['calculations'] if c['op'] == operation)
                calculation['terms'] = calculation['terms'][:1]
                w = Workpaper.model_validate(raw)
                result = evaluate(w)
                row = next(i for i, c in enumerate(w.calculations, 2) if c.id == calculation['id'])
                computed = result['calculations'][row-2]
                self.assertEqual(computed['status'], 'not_calculated')
                self.assertEqual(computed['reason'], 'operation requires two inputs')
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory)/'workbook.xlsx'
                    workbook(w, prepare(w, result), path)
                    with ZipFile(path) as z:
                        ns = {'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                        xml = ET.fromstring(z.read('xl/worksheets/sheet3.xml'))
                    cell = xml.find(f".//x:c[@r='D{row}']", ns)
                    self.assertEqual(cell.find('x:f', ns).text, 'NA()')
                    self.assertEqual(cell.find('x:v', ns).text, '#N/A')

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
                self.assertEqual(cell.find('x:f', ns).text, 'IF(COUNT(C2:D2)=2,C2+D2,NA())')
                self.assertEqual(float(cell.find('x:v', ns).text), 85)


if __name__ == '__main__':
    unittest.main()
