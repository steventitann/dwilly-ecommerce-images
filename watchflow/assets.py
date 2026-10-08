import hashlib
import ipaddress
import socket
from urllib.parse import urlparse, urljoin
from PIL import Image, ImageOps
import requests
from .policy import https_url, ReviewRequired

def public_url(url):
    if not https_url(url):
        raise ReviewRequired('Solo se permiten URLs públicas HTTPS sin credenciales')
    host = urlparse(url).hostname
    for address in socket.getaddrinfo(host, 443):
        if not ipaddress.ip_address(address[4][0]).is_global:
            raise ReviewRequired('Dirección privada o local rechazada')

def download(url, path):
    # Casio transforma incluso originales de 500px a 1200px: validar el
    # archivo nativo, no aceptar esa ampliación como evidencia de HD.
    if urlparse(url).hostname and urlparse(url).hostname.endswith('casio.com') and '.transform/' in url:
        url = url.split('.transform/', 1)[0]
    session = requests.Session()
    for _ in range(6):
        public_url(url)
        r = session.get(url, stream=True, timeout=45, allow_redirects=False)
        if r.is_redirect:
            url = urljoin(url, r.headers['Location'])
            r.close()
            continue
        if not r.ok:
            raise RuntimeError(f'Imagen HTTP {r.status_code}')
        size = 0
        try:
            with path.open('wb') as out:
                for chunk in r.iter_content(65536):
                    size += len(chunk)
                    if size > 25 * 1024 * 1024:
                        raise RuntimeError('Imagen supera 25 MB')
                    out.write(chunk)
        finally:
            r.close()
        return url
    raise RuntimeError('Demasiadas redirecciones de imagen')

def optimize(original, target):
    with Image.open(original) as im:
        im.verify()
    with Image.open(original) as im:
        im.load()
        if max(im.size) < 1000:
            raise ReviewRequired('Fotografía de catálogo no HD: lado mayor < 1000 px')
        source_size = im.size
        im = ImageOps.exif_transpose(im)
        if im.mode in ('RGBA', 'LA') or 'transparency' in im.info:
            rgba = im.convert('RGBA')
            background = Image.new('RGB', rgba.size, 'white')
            background.paste(rgba, mask=rgba.getchannel('A'))
            im = background
        else:
            im = im.convert('RGB')
        im.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        im.save(target, 'WEBP', quality=88, method=6)
        size = im.size
    return {'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'source_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
            'source_width': source_size[0], 'source_height': source_size[1],
            'width': size[0], 'height': size[1], 'bytes': target.stat().st_size}

def barcode_file(identity, directory):
    import barcode
    from .policy import valid_upc, ReviewRequired
    ean = identity.get('ean')
    upc = identity.get('upc')
    if upc and (ean or not valid_upc(upc) or identity.get('code') != upc):
        raise ReviewRequired('UPC inválido o código inconsistente')
    value = ean or upc or identity.get('code') or identity['reference']
    cls = barcode.get_barcode_class('ean13' if ean else 'upc' if upc else 'code128')
    path = cls(value).save(str(directory / 'barcode'))
    return {'value': value, 'format': 'EAN13' if ean else 'UPC-A' if upc else 'CODE128', 'file': 'barcode.svg'}
