import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from watchflow.policy import gate, ReviewRequired, valid_ean, match_inventory, ATTRIBUTES
from watchflow.pipeline import Pipeline
from watchflow.state import State
from watchflow.assets import optimize, barcode_file

def evidence():
    identity = {'ean': '4549526112065', 'reference': 'AE-1000W-3AVDF', 'code': None,
                'brand': 'CASIO', 'model': 'AE-1000W-3AVDF', 'color': 'green', 'dial': 'digital', 'bracelet': 'green resin'}
    source = {'url': 'https://www.casio.com/test', 'identifier': identity['ean'], 'official': True,
              'brand': 'CASIO', 'model': identity['model'], 'evidence_text': identity['ean']}
    analysis = {'identity': identity, 'ambiguous': False, 'confidence': .99, 'sources': [source],
                'label_text': 'visible barcode', 'reason': 'exact',
                'exact_evidence': {'kind': 'ean', 'observed_value': identity['ean'], 'visible_in_photo': True, 'page_verified': True},
                'candidates': [{'url': 'https://www.casio.com/test.webp', 'source_page': source['url']}]}
    visual = {'original_readable': True, 'identity_confidence': .99, 'images': [
        {'order': 1, 'matches': {k: True for k in ATTRIBUTES}, 'image_usable': True, 'confidence': .97, 'reason': 'matches'}]}
    return analysis, visual, [{'source_page': source['url']}]

class PolicyTests(unittest.TestCase):
    def test_exact_accepted(self):
        self.assertEqual(gate(*evidence()), .97)

    def test_low_score_and_wrong_variants_rejected(self):
        for attr in ATTRIBUTES:
            a, v, i = evidence()
            v['images'][0]['matches'][attr] = False
            with self.assertRaises(ReviewRequired): gate(a, v, i)
        a, v, i = evidence(); v['images'][0]['confidence'] = .949
        with self.assertRaises(ReviewRequired): gate(a, v, i)

    def test_no_inferred_barcode(self):
        a, v, i = evidence(); a['exact_evidence']['visible_in_photo'] = False
        with self.assertRaises(ReviewRequired): gate(a, v, i)
        self.assertTrue(valid_ean('4549526112065'))
        self.assertFalse(valid_ean('4549526112066'))

    def test_sources_and_ambiguity(self):
        a, v, i = evidence(); a['sources'][0]['official'] = False
        with self.assertRaises(ReviewRequired): gate(a, v, i)
        a, v, i = evidence(); a['ambiguous'] = True
        with self.assertRaises(ReviewRequired): gate(a, v, i)

    def test_matching_never_mutates_inventory(self):
        a, _, _ = evidence()
        rows = [{'code': a['identity']['ean'], 'brand': 'CASIO', 'description': 'CASIO AE-1000W-3AVDF', 'stock': 2, 'price': 69}]
        before = copy.deepcopy(rows)
        self.assertEqual(match_inventory(rows, a['identity'])['matched_by'], 'EAN')
        self.assertEqual(rows, before)
        rows[0]['brand'] = 'SEIKO'
        with self.assertRaises(ReviewRequired): match_inventory(rows, a['identity'])

    def test_optimization_and_barcode(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); original = root / 'image.png'; out = root / 'out.webp'
            Image.new('RGBA', (2400, 1200), (0, 0, 0, 0)).save(original)
            info = optimize(original, out)
            self.assertEqual((info['width'], info['height']), (1600, 800))
            with Image.open(out) as image:
                self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
            self.assertEqual(barcode_file(evidence()[0]['identity'], root)['value'], '4549526112065')
            self.assertTrue((root / 'barcode.svg').is_file())

class FakeDrive:
    def __init__(self): self.moves = []
    def download(self, file_id, target):
        Image.new('RGB', (1200, 1200), 'green').save(target, format='PNG')
        return {'id': file_id, 'modifiedTime': 'version-1'}
    def move(self, file_id, source, target): self.moves.append((file_id, source, target))

class FakeAnalyst:
    def __init__(self, ambiguous=False): self.ambiguous = ambiguous
    def identify(self, original, work):
        a, _, _ = evidence(); a['ambiguous'] = self.ambiguous; return a
    def verify(self, original, paths, analysis, work): return evidence()[1]

class FakePublisher:
    def __init__(self, repo, fail=False): self.repo, self.fail, self.calls = repo, fail, []
    def publish(self, path, key):
        self.calls.append('publish')
        if self.fail: raise RuntimeError('Git unavailable')
        return 'commit-test'
    def verify(self, path, raw): self.calls.append('verify')

class PipelineTests(unittest.TestCase):
    def make(self, root, ambiguous=False, fail=False):
        state = State(root / 'runtime'); drive = FakeDrive(); publisher = FakePublisher(root, fail)
        self.addCleanup(state.close)
        pipeline = Pipeline({'drive_root': 'root'}, drive, FakeAnalyst(ambiguous), publisher, state)
        return pipeline, drive, publisher, state

    @patch('watchflow.pipeline.verify_sources')
    @patch('watchflow.pipeline.download')
    def test_success_then_duplicate_is_noop(self, dl, sources):
        def fake_download(url, target): Image.new('RGB', (1800, 1800), 'green').save(target, format='PNG'); return url
        dl.side_effect = fake_download
        with tempfile.TemporaryDirectory() as d:
            p, drive, publisher, state = self.make(Path(d))
            meta = {'id': 'photo', 'modifiedTime': 'version-1'}
            folders = {'PROCESADAS': 'done', 'ERROR': 'err', 'PENDIENTE_REVISION': 'review'}
            p.process(meta, 'new', folders); p.process(meta, 'new', folders)
            self.assertEqual(publisher.calls, ['publish', 'verify'])
            self.assertEqual(drive.moves, [('photo', 'new', 'done')])
            manifest = json.loads(next((Path(d) / 'watch-ready').rglob('manifest.json')).read_text(encoding='utf-8'))
            self.assertEqual(manifest['allowed_changes'], ['photo', 'gallery'])
            self.assertFalse(manifest['ecommerce_uploaded'])
            state.close()

    def test_ambiguity_never_publishes(self):
        with tempfile.TemporaryDirectory() as d:
            p, drive, publisher, state = self.make(Path(d), ambiguous=True)
            p.process({'id': 'photo', 'modifiedTime': 'version-1'}, 'new', {'PENDIENTE_REVISION': 'review'})
            self.assertEqual(publisher.calls, [])
            self.assertEqual(drive.moves[0][-1], 'review')
            state.close()

    @patch('watchflow.pipeline.verify_sources')
    @patch('watchflow.pipeline.download')
    def test_publish_failure_resumes_before_drive_move(self, dl, sources):
        dl.side_effect = lambda url, target: (Image.new('RGB', (1200, 1200), 'green').save(target, format='PNG') or url)
        with tempfile.TemporaryDirectory() as d:
            p, drive, publisher, state = self.make(Path(d), fail=True)
            with self.assertRaises(RuntimeError):
                p.process({'id': 'photo', 'modifiedTime': 'version-1'}, 'new', {'PROCESADAS': 'done'})
            self.assertEqual(drive.moves, [])
            self.assertEqual(state.resumable()[0]['status'], 'PUBLISHING')
            publisher.fail = False
            p.resume(state.resumable()[0], {'PROCESADAS': 'done'})
            self.assertEqual(drive.moves[0][-1], 'done')
            state.close()

if __name__ == '__main__': unittest.main()
