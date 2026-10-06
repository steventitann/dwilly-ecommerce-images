import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from .analyst import Analyst
from .assets import download, optimize, barcode_file
from .drive import Drive
from .evidence import verify_sources
from .policy import gate, match_inventory, ReviewRequired
from .publisher import Publisher
from .state import State, lock, now

REPO = Path(__file__).resolve().parents[1]
RAW = 'https://raw.githubusercontent.com/steventitann/dwilly-ecommerce-images/main/'

def write_json(path, data):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)

class Pipeline:
    def __init__(self, config, drive, analyst, publisher, state, inventory=None):
        self.config, self.drive, self.analyst = config, drive, analyst
        self.publisher, self.state, self.inventory = publisher, state, inventory
        self.root = config['drive_root']
        self.repo = publisher.repo

    def resume(self, job, folders):
        key, status = job['key'], job['status']
        if status == 'PUBLISHING':
            target = self.repo / job['package']
            staging = self.state.directory / 'jobs' / key / 'package'
            if staging.exists():
                shutil.copytree(staging, target, dirs_exist_ok=True)
            commit = self.publisher.publish(self.repo / job['package'], key)
            self.state.log(key, 'github_push_completed', commit=commit)
            job = self.state.set(key, status='PUBLISHED', commit=commit)
            status = 'PUBLISHED'
        if status == 'PUBLISHED':
            self.publisher.verify(self.repo / job['package'], RAW)
            self.state.log(key, 'github_raw_hashes_verified')
            destination = 'PROCESADAS'
            terminal = 'PREPARED_IN_GITHUB'
        elif status == 'MOVE_REVIEW':
            destination, terminal = 'PENDIENTE_REVISION', 'REVIEW'
        elif status == 'MOVE_ERROR':
            destination, terminal = 'ERROR', 'ERROR'
        else:
            return
        for file_id in job.get('file_ids', [job['file_id']]):
            self.drive.move(file_id, job['source_parent'], folders[destination])
        self.state.log(key, 'drive_move_verified', destination=destination)
        self.state.set(key, status=terminal)

    def process(self, meta, source_parent, folders, companions=None):
        inputs = sorted([meta, *(companions or [])], key=lambda x: x['id'])
        if not 1 <= len(inputs) <= 5 or len({x['id'] for x in inputs}) != len(inputs):
            raise RuntimeError('Grupo de fotos inválido')
        fingerprint = meta.get('md5Checksum') or meta.get('modifiedTime')
        if not fingerprint:
            raise RuntimeError('Drive no proporcionó versión de la foto')
        key = hashlib.sha256((meta['id'] + ':' + fingerprint).encode()).hexdigest()[:24]
        if companions:
            versions = [x['id'] + ':' + (x.get('md5Checksum') or x.get('modifiedTime') or '') for x in inputs]
            if any(not (x.get('md5Checksum') or x.get('modifiedTime')) for x in inputs):
                raise RuntimeError('Falta versión de una foto del grupo')
            key = hashlib.sha256('|'.join(versions).encode()).hexdigest()[:24]
        previous = self.state.get(key)
        if previous and previous.get('status') != 'DISCOVERED':
            return
        job = self.state.set(key, key=key, status='DISCOVERED', file_id=meta['id'],
                             source_parent=source_parent, version=fingerprint, file_ids=[x['id'] for x in inputs])
        work = self.state.directory / 'jobs' / key
        work.mkdir(parents=True, exist_ok=True)
        try:
            original = work / 'original.photo'
            current = self.drive.download(meta['id'], original)
            if (current.get('md5Checksum') or current.get('modifiedTime')) != fingerprint:
                raise RuntimeError('La foto cambió mientras se descargaba')
            if current.get('md5Checksum') and hashlib.md5(original.read_bytes()).hexdigest() != current['md5Checksum']:
                raise RuntimeError('Checksum de fotografía Drive no coincide')
            from PIL import Image
            with Image.open(original) as im:
                im.verify()
            # Sufijo estándar para el lector multimodal; no alterar el original.
            with Image.open(original) as im:
                im.load()
                vision_input = work / 'input.png'
                im.save(vision_input)
            vision_inputs = [vision_input]
            for index, other in enumerate(inputs):
                if other['id'] == meta['id']:
                    continue
                target = work / f'companion-{index}.photo'
                downloaded = self.drive.download(other['id'], target)
                version = other.get('md5Checksum') or other.get('modifiedTime')
                if (downloaded.get('md5Checksum') or downloaded.get('modifiedTime')) != version:
                    raise RuntimeError('Una foto del grupo cambió durante la descarga')
                if other.get('md5Checksum') and hashlib.md5(target.read_bytes()).hexdigest() != other['md5Checksum']:
                    raise RuntimeError('Checksum del grupo no coincide')
                with Image.open(target) as im:
                    im.verify()
                path = work / f'companion-{index}.png'
                with Image.open(target) as im:
                    im.load()
                    im.save(path)
                vision_inputs.append(path)
            if companions:
                vision_input = vision_inputs
            self.state.log(key, 'drive_download_verified', original_count=len(vision_inputs))
            analysis = self.analyst.identify(vision_input, work)
            write_json(work / 'analysis.json', analysis)
            self.state.log(key, 'identification_complete', confidence=analysis['confidence'])
            if analysis['ambiguous'] or analysis['confidence'] < .95:
                raise ReviewRequired('Identificación inicial ambigua o confidence < 0.95')
            verify_sources(analysis)
            self.state.log(key, 'web_identifiers_verified')
            assets = []
            paths = []
            hashes = set()
            for candidate in analysis['candidates'][:6]:
                if len(assets) == 3:
                    break
                n = len(assets) + 1
                raw = work / f'candidate-{n}.bin'
                webp = work / f'candidate-{n}.webp'
                try:
                    final_url = download(candidate['url'], raw)
                    info = optimize(raw, webp)
                    if info['source_sha256'] in hashes:
                        continue
                    hashes.add(info['source_sha256'])
                    assets.append({**info, 'order': n, 'role': 'principal' if n == 1 else 'secundaria',
                                   'source_url': candidate['url'], 'resolved_url': final_url,
                                   'source_page': candidate['source_page']})
                    paths.append(webp)
                    self.state.log(key, 'hd_image_prepared', order=n, sha256=info['sha256'])
                except (ReviewRequired, RuntimeError, OSError):
                    self.state.log(key, 'candidate_rejected', index=n)
            if not assets:
                raise ReviewRequired('No se encontraron imágenes HD válidas')
            visual = self.analyst.verify(vision_input, paths, analysis, work)
            write_json(work / 'visual.json', visual)
            score = gate(analysis, visual, assets)
            identity = analysis['identity']
            inventory_match = match_inventory(self.inventory, identity) if self.inventory is not None else {
                'status': 'ANTIGRAVITY_MUST_MATCH', 'matched_by': None, 'codes': []}
            # Carpeta versionada por ID+checksum: ninguna foto anterior se sobrescribe.
            package = work / 'package'
            package.mkdir(parents=True, exist_ok=True)
            code = identity.get('ean') or identity.get('code') or identity['reference']
            safe_code = ''.join(c if c.isascii() and (c.isalnum() or c in '-_') else '_' for c in code)[:100]
            for image, asset in zip(paths, assets):
                target = package / f"{safe_code}_{asset['order']:02d}.webp"
                shutil.copyfile(image, target)
                asset['path'] = f'watch-ready/jobs/{key}/{target.name}'
                asset['url'] = RAW + asset['path']
            barcode = barcode_file(identity, package)
            # Solo datos de identidad e imágenes, nunca filas de inventario ni OCR completo.
            manifest = {'schema_version': 1, 'job_id': key, 'prepared_at': now(), 'status': 'READY_FOR_ANTIGRAVITY',
                        'identity': identity, 'confidence': score, 'confidence_method': 'minimum_evidence_score',
                        'barcode': barcode, 'inventory_match': inventory_match,
                        'sources': analysis['sources'], 'exact_evidence': analysis['exact_evidence'],
                        'visual_validation': visual, 'images': assets,
                        'allowed_changes': ['photo', 'gallery'], 'ecommerce_uploaded': False}
            write_json(package / 'manifest.json', manifest)
            write_json(package / 'operations.json', {'job_id': key, 'events': [
                {'event': 'identity_verified', 'confidence': score},
                {'event': 'images_optimized', 'count': len(assets)},
                {'event': 'ready_for_antigravity', 'ecommerce_uploaded': False}]})
            job = self.state.set(key, status='PUBLISHING', package=f'watch-ready/jobs/{key}')
        except ReviewRequired as exc:
            job = self.state.set(key, status='MOVE_REVIEW', reason=str(exc))
        except Exception as exc:
            # Registrar clase de error; mensajes externos pueden contener credenciales.
            job = self.state.set(key, status='MOVE_ERROR', error_type=type(exc).__name__)
        # Un fallo al publicar/mover queda pendiente para reintento, sin perder el paquete.
        self.resume(job, folders)

    def run(self, initialize=False):
        folders = self.drive.folders(self.root, create=initialize)
        missing = set(('NUEVAS', 'PROCESADAS', 'PENDIENTE_REVISION', 'ERROR')) - folders.keys()
        if missing:
            raise RuntimeError('Faltan subcarpetas Drive: ejecutar init-drive')
        for job in self.state.resumable():
            self.resume(job, folders)
        self.publisher.preflight()
        parents = [folders['NUEVAS']]
        if self.config.get('accept_root_uploads', True):
            parents.append(self.root)
        processed = 0
        groups = []
        if os.getenv('DWILLY_INPUT_GROUPS'):
            groups = json.loads(Path(os.environ['DWILLY_INPUT_GROUPS']).read_text(encoding='utf-8'))
        grouped_ids = [file_id for group in groups for file_id in group['file_ids']]
        if len(grouped_ids) != len(set(grouped_ids)) or any(not 2 <= len(g['file_ids']) <= 5 for g in groups):
            raise RuntimeError('Grupos solapados o fuera de límites')
        visited = set()
        for parent in parents:
            children = list(self.drive.children(parent))
            by_id = {x['id']: x for x in children}
            for meta in children:
                if not meta['mimeType'].startswith('image/'):
                    continue
                if meta['id'] in visited:
                    continue
                group = next((g for g in groups if meta['id'] in g['file_ids']), None)
                companions = []
                if group:
                    if any(file_id not in by_id or not by_id[file_id]['mimeType'].startswith('image/') for file_id in group['file_ids']):
                        raise RuntimeError('Grupo incompleto: todas las fotos deben existir en la misma carpeta de entrada')
                    companions = [by_id[file_id] for file_id in group['file_ids'] if file_id != meta['id']]
                    visited.update(group['file_ids'])
                self.process(meta, parent, folders, companions)
                processed += 1
                if processed >= self.config.get('max_files_per_run', 5):
                    return

def main():
    parser = argparse.ArgumentParser(description='Preparación Drive → GitHub; Antigravity integra al ecommerce')
    parser.add_argument('command', choices=['scan', 'run', 'init-drive', 'doctor'])
    parser.add_argument('--config', type=Path, default=REPO / 'config/watchflow.json')
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    if args.command == 'doctor':
        print(json.dumps({'drive_credentials_configured': bool(os.getenv('DWILLY_GOOGLE_CREDENTIALS')),
                          'codex_available': bool(shutil.which(os.getenv('DWILLY_CODEX_BIN', 'codex'))),
                          'git_available': bool(shutil.which('git')),
                          'drive_root': config['drive_root'], 'mode': 'github_handoff'}, indent=2))
        return
    drive = Drive()
    if args.command == 'scan':
        folders = drive.folders(config['drive_root'])
        parents = [folders['NUEVAS']] if 'NUEVAS' in folders else []
        if config.get('accept_root_uploads', True):
            parents.append(config['drive_root'])
        print(json.dumps({'count': sum(1 for p in parents for x in drive.children(p) if x['mimeType'].startswith('image/')),
                          'folders': folders}, indent=2))
        return
    if args.command == 'init-drive':
        print(json.dumps(drive.folders(config['drive_root'], create=True), indent=2))
        return
    runtime = Path(os.getenv('DWILLY_RUNTIME_DIR', str(REPO / '.watch-runtime'))).resolve()
    inventory = None
    if os.getenv('DWILLY_INVENTORY_SNAPSHOT'):
        inventory = json.loads(Path(os.environ['DWILLY_INVENTORY_SNAPSHOT']).read_text(encoding='utf-8'))['items']
    with lock(runtime):
        state = State(runtime)
        publisher = Publisher(REPO, config['git_remote'], config['git_branch'])
        # Comprobar destino antes de reintentos de publicación.
        if publisher.git('branch', '--show-current') != config['git_branch']:
            raise RuntimeError('Rama incorrecta')
        if publisher.git('remote', 'get-url', config['git_remote']) not in (
            'https://github.com/steventitann/dwilly-ecommerce-images.git',
            'git@github.com:steventitann/dwilly-ecommerce-images.git'):
            raise RuntimeError('Remote incorrecto')
        try:
            Pipeline(config, drive, Analyst(config['analyst_timeout_seconds']), publisher, state, inventory).run()
        finally:
            state.close()

if __name__ == '__main__':
    main()
