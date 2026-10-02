import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/annual-report-analysis/scripts'))
from calculate import evaluate
from export import prepare
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

    def test_average_can_trace_derived_opening_and_closing_balances(self):
        for suffix, date_suffix in [('open', '_prior'), ('close', '')]:
            self.data['calculations'].append(dict(id='capital_'+suffix, label='Illustrative financing capital',
                concept='illustrative_financing_capital', op='sum',
                terms=[dict(ref='equity'+date_suffix), dict(ref='debt'+date_suffix), dict(ref='cash'+date_suffix, weight='-1')],
                context=self.fact('equity'+date_suffix)['context'], definition='Equity plus financing debt less cash',
                interpretation='Illustrative capital bridge, not an official ROIC definition'))
        avg = json.loads(json.dumps(next(c for c in self.data['calculations'] if c['id'] == 'average_parent_equity')))
        avg.update(id='capital_average', terms=[dict(ref='capital_open'), dict(ref='capital_close')])
        self.data['calculations'].append(avg)
        c, _ = self.evaluate()
        self.assertEqual(Decimal(c['capital_average']['value']), Decimal('165170386.5'))

    def test_sources_after_cutoff_rejected(self):
        self.data['mandate']['cutoff'] = '2026-03-09'
        with self.assertRaisesRegex(ValidationError, 'published after'):
            Workpaper.model_validate(self.data)

    def test_historical_comparison_cannot_be_relabelled_as_next_year(self):
        growth = next(c for c in self.data['calculations'] if c['op'] == 'growth')
        growth['context'].update(start='2026-01-01', end='2026-12-31')
        c, _ = self.evaluate()
        self.assertIsNone(c[growth['id']]['value'])
        self.assertIn('current input', c[growth['id']]['reason'])

    def test_balance_growth_can_describe_the_intervening_year(self):
        growth = next(c for c in self.data['calculations'] if c['op'] == 'growth')
        for term in growth['terms']:
            self.fact(term['ref'])['context'].update(start=None, aggregation='instant')
        c, _ = self.evaluate()
        self.assertEqual(c[growth['id']]['status'], 'calculated')
        growth['context']['start'] = '2025-06-01'
        c, _ = self.evaluate()
        self.assertEqual(c[growth['id']]['status'], 'not_calculated')

    def test_dimensionless_driver_cannot_change_physical_units(self):
        ctx = dict(self.data['facts'][0]['context'], measure='count', currency=None,
                   physical_unit='GWh', aggregation='flow', start='2025-01-01', end='2025-12-31', scale='1')
        self.data['facts'].extend([
            dict(id='volume_probe', label='Volume', concept='volume', value='100', context=ctx,
                 evidence=[], state='assumption', note='Constructed unit probe'),
            dict(id='driver_probe', label='Driver', concept='driver', value='1.2',
                 context=dict(ctx, measure='ratio', physical_unit=None, aggregation='assumption'),
                 evidence=[], state='assumption', note='Constructed dimensionless driver')])
        self.data['calculations'].append(dict(id='product_probe', label='Mismatched output', op='product',
            terms=[dict(ref='volume_probe'), dict(ref='driver_probe')], context=dict(ctx, physical_unit='shares'),
            definition='100 GWh times 1.2', interpretation='Cannot become shares', period_rule='forecast'))
        c, _ = self.evaluate()
        self.assertIsNone(c['product_probe']['value'])

    def test_unknown_publication_date_remains_unknown_and_visible(self):
        self.data['sources'][0]['published'] = None
        self.data['sources'][0]['availability_note'] = 'Uploaded PDF gives a month and approval date, not an announcement date'
        w = Workpaper.model_validate(self.data)
        data = prepare(w, evaluate(w))
        self.assertIsNone(data['sources'][0]['published'])
        self.assertIn('公布日期未核验', data['mandate']['limitations'][-1])
        self.assertIn('不得据此证明', data['mandate']['limitations'][-1])
        self.assertEqual(data['results']['reconciliations'][0]['residual'], '0')

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

    def test_equal_values_with_different_contexts_do_not_reconcile(self):
        for field, value in [('basis', 'US GAAP'), ('start', '2025-07-01'),
                             ('physical_unit', 'shares')]:
            with self.subTest(field=field):
                a = json.loads(json.dumps(self.fact('revenue')))
                b = json.loads(json.dumps(a))
                a['id'], b['id'] = 'probe_a', 'probe_b'
                if field == 'physical_unit':
                    for f in (a, b):
                        f['context'].update(measure='count', currency=None, physical_unit='GWh')
                b['context'][field] = value
                self.data.update(facts=[a, b], calculations=[], findings=[], procedures=[], requests=[], sections=[],
                                 reconciliations=[dict(id='probe', label='Context probe', actual=a['id'], expected=b['id'],
                                                       tolerance='0', basis='Equal numbers need comparable contexts')])
                _, r = self.evaluate()
                self.assertEqual(r['probe']['status'], 'not_tested')
                self.assertIsNone(r['probe']['residual'])
                self.setUp()


if __name__ == '__main__':
    unittest.main()
