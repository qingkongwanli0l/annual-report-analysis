import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/annual-report-analysis/scripts'))
from calculate import evaluate
from workpaper import Workpaper


class WorkpaperTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'examples/catl-2025/workpaper.json').read_text(encoding='utf-8'))

    def evaluate(self):
        r = evaluate(Workpaper.model_validate(self.data))
        return {x['id']: x for x in r['calculations']}, {x['id']: x for x in r['reconciliations']}

    def fact(self, id):
        return next(f for f in self.data['facts'] if f['id'] == id)

    def test_source_recalculation_and_rounding_are_not_zeroed(self):
        c, r = self.evaluate()
        self.assertEqual(Decimal(c['cfo_bridge']['value']), Decimal(133219980))
        self.assertEqual(Decimal(c['debt_rollforward']['value']), Decimal(119601197))
        self.assertEqual(Decimal(c['supply_components']['value']), Decimal(37222781))
        self.assertEqual(r['R_CFO']['residual'], '-2000')
        self.assertEqual(r['R_CASH']['residual'], '2000')
        self.assertEqual(r['R_BS']['residual'], '0')

    def test_zero_negative_and_missing_inputs_do_not_become_ratios(self):
        for value in ['0', '-10', None]:
            with self.subTest(value=value):
                f = self.fact('ni')
                f['value'] = value
                f['state'] = 'missing' if value is None else 'reported'
                f['note'] = 'not available' if value is None else ''
                c, _ = self.evaluate()
                self.assertIsNone(c['cfo_profit']['value'])
                if value == '0':
                    self.assertEqual(c['ni_growth']['value'], '-1')
                else:
                    self.assertIsNone(c['ni_growth']['value'])

    def test_normalized_units_and_currency_are_distinct(self):
        f = self.fact('cost')
        f['value'] = '312383.297'
        f['context']['scale'] = '1000000'
        c, _ = self.evaluate()
        self.assertEqual(Decimal(c['gross_profit']['value']), Decimal(111318537))
        f['context']['currency'] = 'USD'
        c, _ = self.evaluate()
        self.assertIsNone(c['gross_profit']['value'])
        self.assertIsNone(c['gross_margin']['value'])

    def test_parent_scope_is_not_group_scope(self):
        self.fact('ni')['context']['scope'] = 'parent_only'
        c, _ = self.evaluate()
        self.assertIsNone(c['cfo_profit']['value'])

    def test_missing_opening_equity_is_not_replaced_by_closing(self):
        self.fact('parent_equity_prior')['context']['end'] = '2025-12-31'
        c, _ = self.evaluate()
        self.assertIsNone(c['average_parent_equity']['value'])
        self.assertIsNone(c['roe_simple']['value'])

    def test_sources_after_cutoff_rejected(self):
        self.data['mandate']['cutoff'] = '2026-03-09'
        with self.assertRaisesRegex(ValidationError, 'published after'):
            Workpaper.model_validate(self.data)

    def test_unexecuted_procedure_cannot_claim_performed_without_evidence(self):
        self.data['procedures'][1]['status'] = 'performed'
        with self.assertRaisesRegex(ValidationError, 'executor and date'):
            Workpaper.model_validate(self.data)

    def test_cash_fx_omission_is_visible(self):
        calc = next(c for c in self.data['calculations'] if c['id'] == 'cash_flow_change')
        calc['terms'] = [t for t in calc['terms'] if t['ref'] != 'fx']
        _, r = self.evaluate()
        self.assertEqual(r['R_FX']['status'], 'unexplained_difference')
        self.assertEqual(Decimal(r['R_FX']['residual']), Decimal(2664641000))


if __name__ == '__main__':
    unittest.main()
