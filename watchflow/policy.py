import re
from urllib.parse import urlparse

ATTRIBUTES = ('brand', 'model', 'reference', 'color', 'dial', 'bracelet')

class ReviewRequired(Exception):
    pass

def canonical(value):
    return re.sub(r'\s+', ' ', str(value or '').strip()).upper()

def valid_ean(value):
    value = str(value or '')
    if not re.fullmatch(r'\d{13}', value):
        return False
    check = (10 - sum(int(n) * (1 if i % 2 == 0 else 3) for i, n in enumerate(value[:12])) % 10) % 10
    return check == int(value[-1])

def valid_upc(value):
    value = str(value or '')
    if not re.fullmatch(r'\d{12}', value):
        return False
    return (sum(int(n) for n in value[::2]) * 3 + sum(int(n) for n in value[1::2])) % 10 == 0

def https_url(value):
    p = urlparse(value)
    return p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password

def gate(analysis, visual, images):
    """El score es el mínimo de evidencias; no se permite compensar un fallo."""
    identity = analysis['identity']
    ean = identity.get('ean')
    reference = identity.get('reference')
    if ean and not valid_ean(ean):
        raise ReviewRequired('EAN inválido: no corregir ni inventar dígitos')
    if not identity.get('brand') or not identity.get('model'):
        raise ReviewRequired('Falta marca/modelo')
    if not (ean or reference) or analysis['ambiguous']:
        raise ReviewRequired('Identificación ausente o ambigua')
    evidence = analysis['exact_evidence']
    kind = evidence['kind']
    observed = ean if kind == 'ean' else reference if kind == 'reference' else None
    if not observed or canonical(observed) != canonical(evidence['observed_value']):
        raise ReviewRequired('Identificador exacto no observado en la foto')
    if not evidence['visible_in_photo']:
        raise ReviewRequired('Código deducido por apariencia')
    sources = analysis['sources']
    matches = [s for s in sources if https_url(s['url']) and canonical(s['identifier']) == canonical(observed)
               and canonical(s['brand']) == canonical(identity['brand'])
               and canonical(s['model']) == canonical(identity['model'])]
    official = any(s['official'] for s in matches)
    domains = {urlparse(s['url']).hostname for s in matches}
    if not official and len(domains) < 2:
        raise ReviewRequired('Sin fabricante oficial ni dos fuentes independientes exactas')
    if not evidence['page_verified'] or not visual['original_readable']:
        raise ReviewRequired('Evidencia sin verificar o foto ilegible')
    if len(images) < 1 or len(images) > 3 or len(visual['images']) != len(images):
        raise ReviewRequired('Número de imágenes/verificaciones inconsistente')
    scores = [analysis['confidence'], visual['identity_confidence']]
    for index, (item, verdict) in enumerate(zip(images, visual['images']), 1):
        if verdict['order'] != index or not all(verdict['matches'].get(k) is True for k in ATTRIBUTES):
            raise ReviewRequired('Marca/modelo/referencia/color/esfera/brazalete no coinciden')
        if item['source_page'] not in {s['url'] for s in matches}:
            raise ReviewRequired('Imagen sin página de producto exacta respaldada')
        if not verdict['image_usable']:
            raise ReviewRequired('Imagen no apta para catálogo')
        scores.append(verdict['confidence'])
    if any(not isinstance(s, (int, float)) or isinstance(s, bool) or not 0 <= s <= 1 for s in scores):
        raise ReviewRequired('Score inválido')
    score = min(scores)
    if score < .95:
        raise ReviewRequired(f'Confidence {score:.3f} < 0.95')
    return score

def match_inventory(items, identity):
    """Solo lectura. En D’WILLY el EAN suele almacenarse en code."""
    ean = identity.get('ean')
    rows = [x for x in items if ean and str(x.get('ean') or x.get('barcode') or x.get('code') or '') == ean]
    used = 'EAN'
    if not rows:
        code = identity.get('code') or identity.get('reference')
        rows = [x for x in items if code and canonical(x.get('code')) == canonical(code)]
        used = 'code'
    if not rows:
        return {'status': 'NOT_FOUND', 'matched_by': None, 'codes': []}
    if any(canonical(x.get('brand')) != canonical(identity['brand']) for x in rows):
        raise ReviewRequired('EAN/código del inventario corresponde a otra marca')
    # Un mismo code puede aparecer en sucursales; nunca mezclar descripciones distintas.
    if len({canonical(x.get('description')) for x in rows}) != 1:
        raise ReviewRequired('Múltiples productos distintos con el mismo identificador')
    return {'status': 'EXACT_IDENTIFIER_RECHECK_REQUIRED', 'matched_by': used,
            'codes': sorted({str(x['code']) for x in rows}),
            'descriptions': sorted({x.get('description', '') for x in rows})}
