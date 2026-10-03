from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'skills/annual-report-analysis/scripts'))
from calculate import evaluate
from export import prepare
from workpaper import Workpaper


class PresentationEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        context = dict(entity='Example issuer', scope='consolidated', end='2025-12-31',
                       aggregation='instant', basis='Constructed', measure='money', currency='CNY')
        raw = {
            'mandate': dict(title='Evidence review', entity='Example issuer', industry='example',
                            purpose='Constructed traceability example', period_start='2025-01-01',
                            period_end='2025-12-31', cutoff='2026-09-30', accounting_basis='Constructed',
                            scope='consolidated', version='1'),
            'sources': [dict(id='report', title='Example original report',
                             url='https://example.com/annual-report.pdf', published='2026-03-31'),
                        dict(id='unused', title='Unused source', url='https://example.com/unused.pdf',
                             published='2026-03-31')],
            'evidence': [dict(id=key, source='report', locator=locator, observation=observation,
                              reliability='Constructed example') for key, locator, observation in [
                ('direct_e', 'PDF page 11 / note A', 'Direct support'),
                ('calculation_e', 'PDF page 12 / note B', 'Calculation input'),
                ('quant_input_e', 'PDF page 13 / note C', 'Quantitative input'),
                ('quant_e', 'PDF page 14 / note D', 'Quantitative assumption'),
                ('counter_e', 'PDF page 15 / note E', 'An offsetting exposure remains'),
                ('counter_number_e', 'PDF page 16 / note F', 'Remaining exposure amount')]],
            'facts': [dict(id=key, label=label, concept='example', value='10', context=context,
                           evidence=[evidence]) for key, label, evidence in [
                ('input', 'Input amount', 'calculation_e'),
                ('quant_input', 'Quantitative input amount', 'quant_input_e'),
                ('counter_number', 'Residual exposure', 'counter_number_e')]],
            'calculations': [dict(id='total', label='Calculated total', op='sum', terms=[{'ref':'input'}],
                                  context=context, definition='Single input', interpretation='Constructed result')],
            'findings': [dict(id='finding', title='Comparable capital', question='What changed?',
                              conclusion='The observed movement is conditional.',
                              mechanism='Reclassification changes the comparison basis. ' +
                                        'The transaction must be traced through each relevant account. '*15 +
                                        'The remaining economic change is distinct.',
                              evidence=['direct_e', 'total'], counterevidence=['counter_e', 'counter_number'],
                              alternatives=['Business mix may explain the remaining movement.'],
                              status='conditional', changes_if='Reassess after comparable figures are available.')],
            'sections': [dict(title='Capital interpretation', findings=['finding'], figures=['total'])],
            'quantitative': [dict(id='quant', label='Quantitative snapshot', method='custom_bridge_v1',
                                  as_of='2025-12-31', input_refs=['quant_input'], evidence=['quant_e'],
                                  assumptions=['Constructed case'], limitations=['No independent model validation'],
                                  artifact={'input_snapshot': {'amount':'10'}, 'rows':[{'result':'10'}]},
                                  figures=[dict(id='quant_result', label='Quantitative result', row=0,
                                                field='result', context=context)])],
        }
        workpaper = Workpaper.model_validate(raw)
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        path = Path(cls.directory.name)
        (path/'presentation-data.json').write_text(json.dumps(prepare(workpaper, evaluate(workpaper)),
                                                             ensure_ascii=False), encoding='utf-8')
        subprocess.run(['node', str(ROOT/'skills/annual-report-analysis/scripts/export_pptx.cjs'),
                        str(path/'presentation-data.json'), str(path/'presentation.pptx')], check=True)
        with ZipFile(path/'presentation.pptx') as archive:
            cls.slides = [ET.fromstring(archive.read(name)) for name in archive.namelist()
                          if name.startswith('ppt/slides/slide') and name.endswith('.xml')]
            cls.visible = ''.join(''.join(slide.itertext()) for slide in cls.slides)
            cls.notes = '\n'.join(''.join(ET.fromstring(archive.read(name)).itertext())
                                  for name in archive.namelist()
                                  if name.startswith('ppt/notesSlides/notesSlide') and name.endswith('.xml'))

    def test_reasoning_and_counterevidence_are_visible_without_notes(self):
        visible = ''.join(self.visible.split())
        for text in ['Reclassification changes the comparison basis.',
                     'The remaining economic change is distinct.',
                     'Business mix may explain the remaining movement.',
                     'An offsetting', 'exposure remains', 'Residual exposure', '10.00 元人民币']:
            self.assertIn(''.join(text.split()), visible)
        capital_slides = [slide for slide in self.slides if 'Capital interpretation' in ''.join(slide.itertext())]
        self.assertGreater(len(capital_slides), 1)
        ns = {'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
              'p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
        for slide in capital_slides:
            for shape in slide.findall('.//p:sp', ns):
                if 'Reclassification' in ''.join(shape.itertext()) or 'relevant account' in ''.join(shape.itertext()):
                    self.assertTrue(all(int(run.get('sz')) >= 1600
                                        for run in shape.findall('.//a:rPr', ns) if run.get('sz')))

    def test_original_sources_resolve_direct_calculated_quantitative_and_counterevidence(self):
        visible = ''.join(self.visible.split())
        for text in ['https://example.com/annual-report.pdf', 'Example original report',
                     'PDF page 11 / note A', 'PDF page 12 / note B', 'PDF page 13 / note C',
                     'PDF page 14 / note D', 'PDF page 15 / note E', 'PDF page 16 / note F']:
            self.assertIn(''.join(text.split()), visible)
        self.assertIn('https://example.com/annual-report.pdf', self.notes)
        self.assertNotIn('https://example.com/unused.pdf', self.visible)
        source_slides = [slide for slide in self.slides if '原文来源与定位' in ''.join(slide.itertext())]
        self.assertLessEqual(len(source_slides), 2)


if __name__ == '__main__':
    unittest.main()
