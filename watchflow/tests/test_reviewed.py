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
from watchflow.policy import valid_upc

class ReviewedTests(unittest.TestCase):
    def cubitt(self):
        return json.loads((Path(__file__).resolve().parents[2] / 'watch-review/approved-2026-10-08.json').read_text(encoding='utf-8'))[0]

    def test_upc_preserved_without_inventing_ean(self):
        self.assertTrue(valid_upc('850071934281'))
        self.assertFalse(valid_upc('850071934282'))
        self.assertFalse(valid_upc('0850071934281'))
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); original=root/'native.png'
            Image.new('RGB',(1000,1000),'white').save(original)
            r=self.cubitt(); r['images']=r['images'][:1]
            m=prepare(r,[original],root)
            self.assertIsNone(m['identity']['ean'])
            self.assertEqual(m['identity']['code'],'850071934281')
            self.assertEqual(m['barcode']['format'],'UPC-A')
            self.assertEqual(m['barcode']['value'],'850071934281')
            self.assertEqual(m['exact_evidence']['kind'],'upc')

    def test_wrong_cubitt_variant_or_upc_blocks_before_writing(self):
        for change in ('upc','code','color','image','host','source'):
            r=copy.deepcopy(self.cubitt())
            if change=='upc': r['identity']['upc']='850071934282'
            elif change=='code': r['identity']['code']='0850071934281'
            elif change=='color': r['official_variant']['title']='Rose Gold'
            elif change=='image': r['images'][0]['source_url']='https://example.com/other-color.webp'
            elif change=='host': r['official_mapping']['url']='https://cubittofficial.com.evil.test/product'
            else: r['identity_sources'][1]['upc']='850071934274'
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(ReviewRequired): prepare(r,[Path(d)/'missing.png']*3,Path(d))
                self.assertFalse((Path(d)/'watch-ready').exists())

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
