"""Preparación local de un expediente revisado; sin Drive/Git/ecommerce.

No reemplaza el worker autónomo. El revisor aporta evidencia explícita
de referencia regional, EAN y variante; no se eliminan sufijos por regla.
"""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from .assets import optimize, barcode_file
from .policy import ATTRIBUTES, ReviewRequired, valid_ean, canonical
from .state import now

def prepare(record, originals, repo):
    identity = record['identity']
    if not valid_ean(identity['ean']):
        raise ReviewRequired('EAN inválido')
    if not record.get('label_and_product_in_same_photo'):
        raise ReviewRequired('Etiqueta y producto sin vínculo confirmado')
    sources = record['identity_sources']
    exact = [s for s in sources if s.get('page_read') and
             s.get('ean') == identity['ean'] and
             canonical(s.get('reference')) == canonical(identity['reference']) and
             canonical(s.get('brand')) == canonical(identity['brand']) and
             urlparse(s['url']).scheme == 'https']
    if len({urlparse(s['url']).hostname.removeprefix('www.') for s in exact}) < 2:
        raise ReviewRequired('Faltan dos fuentes independientes de EAN/referencia')
    mapping = record['official_mapping']
    if not mapping.get('reviewed') or mapping['reference'] != identity['reference']:
        raise ReviewRequired('Referencia regional sin correspondencia revisada')
    official_host = urlparse(mapping['url']).hostname or ''
    if official_host != 'www.casio.com' or mapping['brand'] != 'CASIO':
        raise ReviewRequired('Fuente oficial no permitida')
    candidates = record['images']
    if not 1 <= len(candidates) <= 3 or len(originals) != len(candidates):
        raise ReviewRequired('Cantidad de imágenes inválida')
    scores = [record['identity_confidence'], mapping['confidence']]
    for candidate in candidates:
        if not all(candidate['matches'].get(k) is True for k in ATTRIBUTES):
            raise ReviewRequired('Variante visual no coincidente')
        if candidate['source_page'] != mapping['url'] or not candidate['native_original']:
            raise ReviewRequired('Sin original nativo del producto oficial')
        scores.append(candidate['confidence'])
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not .95 <= x <= 1 for x in scores):
        raise ReviewRequired('Confianza insuficiente')
    key = hashlib.sha256((identity['ean'] + ':' + identity['reference'] + ':' +
                          '|'.join(hashlib.sha256(p.read_bytes()).hexdigest() for p in originals)).encode()).hexdigest()[:24]
    directory = repo / 'watch-ready' / 'jobs' / key
    directory.mkdir(parents=True, exist_ok=True)
    assets = []
    for i, (original, candidate) in enumerate(zip(originals, candidates), 1):
        name = f"{identity['ean']}_{i:02d}.webp"
        info = optimize(original, directory / name)
        path = f'watch-ready/jobs/{key}/{name}'
        assets.append({**info, 'order': i, 'role': 'principal' if i == 1 else 'secundaria',
                       'path': path, 'url': 'https://raw.githubusercontent.com/steventitann/dwilly-ecommerce-images/main/' + path,
                       'source_url': candidate['source_url'], 'source_page': candidate['source_page']})
    manifest = {'schema_version': 1, 'job_id': key, 'prepared_at': now(), 'status': 'READY_FOR_ANTIGRAVITY',
                'identity': identity, 'confidence': min(scores), 'confidence_method': 'minimum_reviewed_evidence_score',
                'review_mode': 'interactive_visual_and_web_review', 'barcode': barcode_file(identity, directory),
                'inventory_match': {'status': 'ANTIGRAVITY_MUST_MATCH', 'matched_by': None, 'codes': []},
                'sources': sources, 'official_reference_mapping': mapping,
                'exact_evidence': {'kind': 'ean', 'observed_value': identity['ean'], 'visible_in_photo': True, 'page_verified': True},
                'visual_validation': {'original_readable': True, 'identity_confidence': record['identity_confidence'],
                    'images': [{'order': i, 'matches': c['matches'], 'image_usable': True, 'confidence': c['confidence']}
                               for i, c in enumerate(candidates, 1)]},
                'images': assets, 'allowed_changes': ['photo', 'gallery'], 'ecommerce_uploaded': False}
    (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (directory / 'operations.json').write_text(json.dumps({'job_id': key, 'events': [
        {'event': 'reviewed_identity_confirmed'}, {'event': 'native_hd_visual_match_confirmed'},
        {'event': 'webp_prepared', 'count': len(assets)}, {'event': 'ready_for_antigravity'}]}, indent=2)+'\n', encoding='utf-8')
    return manifest
