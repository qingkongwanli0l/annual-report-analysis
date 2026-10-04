from pathlib import Path
import json
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'skills/annual-report-analysis/scripts'))
from calculate import evaluate
from export import export, prepare, word, workbook
from workpaper import Workpaper


class PresentationBriefTests(unittest.TestCase):
    def setUp(self):
        context = dict(entity='Constructed issuer', scope='consolidated', end='2025-12-31',
                       aggregation='instant', basis='Constructed', measure='money', currency='CNY')
        self.raw = {
            'mandate': dict(title='Constructed credit discussion', entity='Constructed issuer',
                            industry='example', purpose='Test an authored brief', period_start='2025-01-01',
                            period_end='2025-12-31', cutoff='2026-09-30', accounting_basis='Constructed',
                            scope='consolidated', version='1', methods=['Example method 2026, local scale',
                            'Full method metadata retained'], limitations=['Full limitation retained']),
            'sources': [dict(id='source', title='Original report '+('Long original title '*30),
                             url='https://example.com/report.pdf', published='2026-03-31'),
                        dict(id='model_source', title='Scenario assumptions',
                             url='https://example.com/model.pdf', published='2026-03-31'),
                        dict(id='unselected_source', title='Unselected original source',
                             url='https://example.com/unselected.pdf', published='2026-03-31')],
            'evidence': [dict(id='direct_e', source='source', locator='PDF page 11 / note A '+('Full locator '*30),
                              observation='Direct evidence', reliability='Constructed'),
                         dict(id='model_e', source='model_source', locator='PDF page 12 / note B',
                              observation='Snapshot input', reliability='Constructed')],
            'facts': [dict(id='input', label='Input amount', concept='cash', value='12',
                           context=context, evidence=['direct_e'])],
            'calculations': [dict(id='total', label='Calculated amount', op='sum', terms=[{'ref':'input'}],
                                  context=context, definition='Single sourced amount', interpretation='Constructed')],
            'findings': [dict(id='decision', title='Conditional recommendation', question='Can funding arrive?',
                              conclusion='Detailed recommendation {{snapshot_value}}',
                              mechanism='Full mechanism retained. '+('Account by account detail. '*40),
                              status='conditional', evidence=['total'], counterevidence=['direct_e'],
                              alternatives=['Alternative explanation retained'], changes_if='Full change condition retained'),
                         dict(id='unselected', title='Unselected finding', question='Another question',
                              conclusion='Unselected conclusion retained', mechanism='Unselected mechanism retained',
                              status='unresolved', evidence=[], alternatives=[], changes_if='Unselected change retained')],
            'sections': [dict(title='Full research', findings=['decision', 'unselected'], figures=['total'])],
            'requests': [dict(id='request', finding='unselected', request='Unselected request retained',
                              reason='Unselected impact retained', owner_role='Finance', close_when='Full closure retained')],
            'quantitative': [dict(id='snapshot', label='Full quantitative result', method='constructed_snapshot',
                                  as_of='2025-12-31', input_refs=['input'], evidence=['model_e'],
                                  assumptions=['Full model assumption retained'], limitations=['Snapshot is not recalculation'],
                                  artifact={'input_snapshot': {'input':'12'},
                                            'rows':[{'result':'4', 'components':{'unselected_component':'8'}},
                                                    {'result':'7', 'detail':'Unselected result row retained'}]},
                                  figures=[dict(id='snapshot_value', label='Snapshot value', row=0,
                                                field='result', context=context)])],
            'presentation': [dict(title='Decision {{snapshot_value}}',
                                  body='Example method 2026, local scale. Recommendation {{snapshot_value}}.\n\n'
                                       'Premise: funds arrive before maturity. Counterevidence: cash is restricted.\n\n'
                                       'Change condition: reassess if the facility is withdrawn.',
                                  findings=['decision'], figures=['total'])],
        }

    def test_brief_keeps_shared_values_visible_conditions_and_source_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for value, expected in [('4', '4.00 元人民币'), ('5', '5.00 元人民币'), (None, '未计算')]:
                with self.subTest(value=value):
                    self.raw['quantitative'][0]['artifact']['rows'][0]['result'] = value
                    self.raw['findings'][0]['status'] = 'unresolved' if value is None else 'conditional'
                    (root/'input.json').write_text(json.dumps(self.raw, ensure_ascii=False), encoding='utf-8')
                    export(root/'input.json', root/'output')
                    with ZipFile(root/'output/presentation.pptx') as archive:
                        slides = [ET.fromstring(archive.read(name)) for name in archive.namelist()
                                  if name.startswith('ppt/slides/slide') and name.endswith('.xml')]
                        visible = ''.join(''.join(slide.itertext()) for slide in slides)
                        notes = ''.join(''.join(ET.fromstring(archive.read(name)).itertext())
                                        for name in archive.namelist()
                                        if name.startswith('ppt/notesSlides/notesSlide') and name.endswith('.xml'))
                    self.assertEqual(len(slides), 2)  # Cover plus one authored page, despite long citations and detail.
                    compact = ''.join(visible.split())
                    for text in [expected, 'Example method 2026, local scale', 'Premise: funds arrive before maturity.',
                                 'Counterevidence: cash is restricted.', 'reassess if the facility is withdrawn.',
                                 self.raw['findings'][0]['status'], 'decision', 'source', 'model_source']:
                        self.assertIn(''.join(text.split()), compact)
                    for text in ['Full mechanism retained', 'Unselected request retained', 'Unselected finding',
                                 'Full quantitative result', 'Full method metadata retained', '原文来源与定位',
                                 'unselected_source']:
                        self.assertNotIn(''.join(text.split()), compact)
                    for text in ['snapshot_value', 'PDF page 11 / note A', 'PDF page 12 / note B',
                                 'https://example.com/report.pdf', 'https://example.com/model.pdf',
                                 'Full method metadata retained', 'Full limitation retained']:
                        self.assertIn(text, notes)
                    for filename, member in [('report.docx', 'word/document.xml'), ('workbook.xlsx', 'xl/sharedStrings.xml')]:
                        with ZipFile(root/'output'/filename) as archive:
                            text = ''.join(ET.fromstring(archive.read(member)).itertext())
                        self.assertIn(''.join(expected.split()), ''.join(text.split()))
                    if value != '4':
                        self.assertNotIn('4.00元人民币', compact)

        for field in ('findings', 'figures'):
            with self.subTest(reference=field):
                self.raw['presentation'][0][field].append('unknown')
                with self.assertRaisesRegex(ValueError, 'unknown references'):
                    Workpaper.model_validate(self.raw)
                self.raw['presentation'][0][field].pop()
        self.raw['presentation'][0]['body'] = '{{unknown}}'
        w = Workpaper.model_validate(self.raw)
        with self.assertRaisesRegex(ValueError, 'unknown numeric token'):
            prepare(w, evaluate(w))

    def test_brief_does_not_clip_full_word_or_excel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contents = []
            for brief in (True, False):
                raw = dict(self.raw)
                if not brief:
                    raw.pop('presentation')
                w = Workpaper.model_validate(raw)
                data = prepare(w, evaluate(w))
                word(data, root/'report.docx')
                workbook(w, data, root/'workbook.xlsx')
                with ZipFile(root/'report.docx') as archive:
                    report = ''.join(ET.fromstring(archive.read('word/document.xml')).itertext())
                with ZipFile(root/'workbook.xlsx') as archive:
                    sheets = {name:archive.read(name) for name in archive.namelist()
                              if name.startswith('xl/worksheets/') or name == 'xl/sharedStrings.xml'}
                    strings = ''.join(ET.fromstring(archive.read('xl/sharedStrings.xml')).itertext())
                for text in ['Full mechanism retained', 'Unselected conclusion retained', 'Unselected request retained',
                             'Unselected original source', 'Full model assumption retained', 'Full limitation retained']:
                    self.assertIn(text, report)
                    self.assertIn(text, strings)
                self.assertIn('Unselected result row retained', strings)
                self.assertIn('unselected_component', strings)
                contents.append((report, sheets))
            self.assertEqual(contents[0], contents[1])


if __name__ == '__main__':
    unittest.main()
