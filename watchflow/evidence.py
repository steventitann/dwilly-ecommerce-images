"""Contrasta identificadores contra texto de páginas HTTPS reales."""
import re
from html import unescape
from .assets import public_url
from .policy import canonical, ReviewRequired
import requests

OFFICIAL_DOMAINS = {
    'CASIO': ('casio.com',), 'CITIZEN': ('citizenwatch.com', 'citizenwatch-global.com'),
    'SEIKO': ('seikowatches.com',), 'TIMEX': ('timex.com',), 'FOSSIL': ('fossil.com',),
    'ORIENT': ('orient-watch.com',), 'TISSOT': ('tissotwatches.com',),
}

def verify_sources(analysis):
    from urllib.parse import urljoin, urlparse
    for source in analysis['sources']:
        url = source['url']
        text = None
        for _ in range(6):
            public_url(url)
            r = requests.get(url, timeout=45, allow_redirects=False, stream=True)
            if r.is_redirect:
                url = urljoin(url, r.headers['Location'])
                r.close()
                continue
            if not r.ok:
                r.close()
                break
            content = bytearray()
            for chunk in r.iter_content(65536):
                content.extend(chunk)
                if len(content) > 4 * 1024 * 1024:
                    r.close()
                    raise ReviewRequired('Página de evidencia demasiado grande')
            r.close()
            text = canonical(unescape(re.sub('<[^>]+>', ' ', content.decode('utf-8', errors='replace'))))
            break
        if not text or canonical(source['identifier']) not in text:
            raise ReviewRequired('No se confirmó el identificador en la página de evidencia')
        host = urlparse(url).hostname
        allowed = OFFICIAL_DOMAINS.get(canonical(source['brand']), ())
        source['official'] = bool(source['official'] and any(host == d or host.endswith('.' + d) for d in allowed))
        source['http_identifier_verified'] = True
    # Dominios de marcas adicionales se añaden explícitamente, nunca por decisión del modelo.
