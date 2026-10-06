"""Genera el catálogo de recursos preparados; no modifica el ecommerce."""
import copy
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://raw.githubusercontent.com/steventitann/dwilly-ecommerce-images/main/'
catalog = json.loads((ROOT / 'catalog/catalogo.json').read_text(encoding='utf-8'))
manifest = json.loads((ROOT / 'artifacts/assets_manifest.json').read_text(encoding='utf-8'))
assert manifest['ok'] == 18 and manifest['errors'] == 0
prepared = copy.deepcopy(catalog)
for product in prepared['productos']:
    for image in product['imagenes']:
        item = next(x for x in manifest['items'] if x['codigo_catalogo'] == product['codigo'] and x['ean'] == product['ean'] and x['orden'] == image['orden'])
        path = item['optimized_path'].replace('\\', '/')
        image['source_url'] = image['url']
        image['url'] = BASE + path
        image['local_path'] = path
        image['sha256'] = item['optimized_sha256']
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == image['sha256']
        with Image.open(ROOT / path) as im:
            im.verify()
        item['optimized_path'] = path
        item['public_url'] = image['url']
(ROOT / 'catalog/catalogo_preparado.json').write_text(json.dumps(prepared, ensure_ascii=False, indent=2), encoding='utf-8')
(ROOT / 'artifacts/assets_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print('OK: 18 WebP verificados; catálogo preparado y URLs generadas.')
