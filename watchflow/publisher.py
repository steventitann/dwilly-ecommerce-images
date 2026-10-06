import hashlib
import subprocess
import time

class Publisher:
    def __init__(self, repo, remote, branch):
        self.repo, self.remote, self.branch = repo, remote, branch

    def git(self, *args):
        p = subprocess.run(['git', *args], cwd=self.repo, capture_output=True, text=True, timeout=120)
        if p.returncode:
            raise RuntimeError('Git falló: ' + ' '.join(args[:2]) + '; revisar autenticación y divergencias')
        return p.stdout.strip()

    def preflight(self):
        if self.git('branch', '--show-current') != self.branch:
            raise RuntimeError('La copia del pipeline debe estar en ' + self.branch)
        origin = self.git('remote', 'get-url', self.remote)
        if origin.removesuffix('.git').rstrip('/') not in (
            'https://github.com/steventitann/dwilly-ecommerce-images',
            'git@github.com:steventitann/dwilly-ecommerce-images'):
            raise RuntimeError('Remote de publicación incorrecto')
        if self.git('status', '--porcelain'):
            raise RuntimeError('Repositorio con cambios: usar copia dedicada limpia')
        self.git('fetch', self.remote, self.branch)
        # FF-only: no sobrescribir trabajo de Antigravity ni conflictos.
        self.git('merge', '--ff-only', f'{self.remote}/{self.branch}')
        if self.git('rev-parse', 'HEAD') != self.git('rev-parse', f'{self.remote}/{self.branch}'):
            raise RuntimeError('Existen commits locales sin publicar; resolver antes de comenzar')

    def publish(self, path, key):
        relative = path.relative_to(self.repo).as_posix()
        self.git('add', '--', relative)
        changed = self.git('diff', '--cached', '--name-only')
        if any(not name.startswith(relative + '/') for name in changed.splitlines()):
            raise RuntimeError('Hay archivos ajenos al paquete staged; no crear commit')
        if changed:
            self.git('commit', '-m', 'Prepare watch resources ' + key)
        self.git('push', self.remote, self.branch)
        return self.git('rev-parse', 'HEAD')

    def verify(self, directory, base_url):
        import requests
        for path in directory.rglob('*'):
            if not path.is_file():
                continue
            url = base_url + path.relative_to(self.repo).as_posix()
            # Git normaliza CRLF/LF en Windows. Comparar con el blob publicado,
            # no con los bytes del checkout para JSON/SVG; WebP es binario.
            relative = path.relative_to(self.repo).as_posix()
            committed = subprocess.run(['git', '-c', 'safe.directory=' + str(self.repo),
                                        'show', 'HEAD:' + relative], cwd=self.repo, capture_output=True)
            if committed.returncode:
                raise RuntimeError('Recurso no incluido en el commit publicado')
            expected = hashlib.sha256(committed.stdout).hexdigest()
            for attempt in range(4):
                r = requests.get(url, timeout=45)
                if r.ok and hashlib.sha256(r.content).hexdigest() == expected:
                    break
                if attempt == 3:
                    raise RuntimeError('GitHub RAW no coincide con recurso publicado')
                time.sleep(2 ** attempt)
