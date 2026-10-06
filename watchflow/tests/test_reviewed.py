import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from watchflow.reviewed import prepare
from watchflow.policy import ReviewRequired
from watchflow.assets import download

class ReviewedTests(unittest.TestCase):
    def record(self):
        return json.loads((Path(__file__).resolve().parents[2] / 'watch-review/approved-2026-10-06.json').read_text(encoding='utf-8'))[0]

    def test_missing_physical_binding_or_different_ean_blocks(self):
        for change in ('binding', 'ean', 'variant'):
            r=copy.deepcopy(self.record())
            if change == 'binding': r['label_and_product_in_same_photo']=False
            elif change == 'ean': r['identity_sources'][0]['ean']='4549526112065'
            else: r['images'][0]['matches']['bracelet']=False
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(ReviewRequired): prepare(r,[Path(d)/'missing.png'],Path(d))
                self.assertFalse((Path(d)/'watch-ready').exists())

    def test_real_package_uses_native_hd_and_preserves_identifier(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); original=root/'native.png'
            Image.new('RGB',(2000,2000),'white').save(original)
            manifest=prepare(self.record(),[original],root)
            self.assertEqual(manifest['identity']['reference'],'GBA-900UU-5ADR')
            self.assertEqual(manifest['identity']['ean'],'4549526322709')
            self.assertEqual(manifest['images'][0]['width'],1600)
            self.assertEqual(manifest['allowed_changes'],['photo','gallery'])
            self.assertFalse(manifest['ecommerce_uploaded'])

    @patch('watchflow.assets.public_url')
    @patch('watchflow.assets.requests.Session')
    def test_casio_server_upscale_is_not_used(self,session,public):
        session.return_value.get.return_value.ok=True
        session.return_value.get.return_value.is_redirect=False
        session.return_value.get.return_value.iter_content.return_value=[b'original']
        with tempfile.TemporaryDirectory() as d:
            url=download('https://www.casio.com/content/image.png.transform/main-visual-sp/image.png',Path(d)/'image')
            self.assertEqual(url,'https://www.casio.com/content/image.png')
            self.assertEqual(session.return_value.get.call_args.args[0],url)
