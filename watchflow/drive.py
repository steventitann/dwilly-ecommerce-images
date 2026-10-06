import json
import os
import time
from pathlib import Path
import requests

API = 'https://www.googleapis.com/drive/v3'
SCOPE = ['https://www.googleapis.com/auth/drive']
FOLDER = 'application/vnd.google-apps.folder'

class Drive:
    def __init__(self):
        credential_path = os.getenv('DWILLY_GOOGLE_CREDENTIALS')
        if not credential_path:
            raise RuntimeError('Falta DWILLY_GOOGLE_CREDENTIALS: OAuth autorizado o cuenta de servicio con acceso a la carpeta')
        from google.auth.transport.requests import AuthorizedSession
        data = json.loads(Path(credential_path).read_text(encoding='utf-8'))
        if data.get('type') == 'service_account':
            from google.oauth2.service_account import Credentials
            credentials = Credentials.from_service_account_info(data, scopes=SCOPE)
        else:
            from google.oauth2.credentials import Credentials
            credentials = Credentials.from_authorized_user_info(data, scopes=SCOPE)
        self.session = AuthorizedSession(credentials)

    def request(self, method, path, **kwargs):
        for attempt in range(4):
            r = self.session.request(method, API + path, timeout=60, **kwargs)
            if r.status_code not in (429, 500, 502, 503, 504):
                # No imprimir headers, tokens ni cuerpos que puedan contener secretos.
                if not r.ok:
                    raise RuntimeError(f'Drive HTTP {r.status_code} en {method} {path}')
                return r
            time.sleep(2 ** attempt)
        raise RuntimeError('Drive temporalmente indisponible tras cuatro intentos')

    def metadata(self, file_id):
        return self.request('GET', '/files/' + file_id, params={
            'fields': 'id,name,mimeType,parents,md5Checksum,modifiedTime,size', 'supportsAllDrives': 'true'}).json()

    def children(self, parent):
        token = None
        while True:
            p = {'q': f"'{parent}' in parents and trashed = false", 'pageSize': 100,
                 'fields': 'nextPageToken,incompleteSearch,files(id,name,mimeType,parents,md5Checksum,modifiedTime,size)',
                 'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true'}
            if token:
                p['pageToken'] = token
            result = self.request('GET', '/files', params=p).json()
            if result.get('incompleteSearch'):
                raise RuntimeError('Drive informó búsqueda incompleta')
            yield from result.get('files', [])
            token = result.get('nextPageToken')
            if not token:
                break

    def folders(self, root, create=False):
        children = list(self.children(root))
        result = {}
        for name in ('NUEVAS', 'PROCESADAS', 'PENDIENTE_REVISION', 'ERROR'):
            matches = [f for f in children if f['name'] == name and f['mimeType'] == FOLDER]
            if len(matches) > 1:
                raise RuntimeError('Subcarpeta duplicada: ' + name)
            if matches:
                result[name] = matches[0]['id']
            elif create:
                result[name] = self.request('POST', '/files', params={'fields': 'id', 'supportsAllDrives': 'true'},
                    json={'name': name, 'mimeType': FOLDER, 'parents': [root]}).json()['id']
        return result

    def download(self, file_id, path):
        meta = self.metadata(file_id)
        if not meta['mimeType'].startswith('image/'):
            raise RuntimeError('Entrada no es imagen')
        if int(meta.get('size', 0)) > 25 * 1024 * 1024:
            raise RuntimeError('Fotografía supera 25 MB')
        r = self.request('GET', '/files/' + file_id, params={'alt': 'media', 'supportsAllDrives': 'true'}, stream=True)
        size = 0
        try:
            with path.open('wb') as out:
                for chunk in r.iter_content(65536):
                    size += len(chunk)
                    if size > 25 * 1024 * 1024:
                        raise RuntimeError('Descarga Drive supera 25 MB')
                    out.write(chunk)
        finally:
            r.close()
        return meta

    def move(self, file_id, source, target):
        meta = self.metadata(file_id)
        if target in meta.get('parents', []) and source not in meta['parents']:
            return  # Reintento tras caída entre move y registro local.
        if source not in meta.get('parents', []):
            raise RuntimeError('Padre de la foto cambió; no mover')
        self.request('PATCH', '/files/' + file_id, params={'addParents': target, 'removeParents': source,
                     'supportsAllDrives': 'true', 'fields': 'id,parents'}, json={})
        parents = self.metadata(file_id).get('parents', [])
        if target not in parents or source in parents:
            raise RuntimeError('No se confirmó el movimiento Drive')
