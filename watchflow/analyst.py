"""Adaptador Codex CLI con sesión iniciada. No lee OPENAI_API_KEY."""
import json
import os
import subprocess
from pathlib import Path
from jsonschema import validate

HERE = Path(__file__).resolve().parent

class Analyst:
    def __init__(self, timeout=600):
        self.executable = os.getenv('DWILLY_CODEX_BIN', 'codex')
        self.timeout = timeout

    def call(self, schema_name, prompt, images, workspace):
        schema = HERE / 'schemas' / (schema_name + '.json')
        output = workspace / (schema_name + '.json')
        output.unlink(missing_ok=True)
        cmd = [self.executable, 'exec', '--skip-git-repo-check', '--ephemeral', '-s', 'read-only',
               '-c', 'web_search="live"', '--output-schema', str(schema), '-o', str(output)]
        for image in images:
            cmd.extend(['--image', str(image)])
        cmd.append('-')
        # No entregar al analista credenciales de Drive/GitHub/ecommerce heredadas.
        env = {k: v for k, v in os.environ.items() if not any(x in k.upper() for x in
               ('API_KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'DWILLY_GOOGLE_CREDENTIALS', 'GOOGLE_APPLICATION_CREDENTIALS'))}
        result = subprocess.run(cmd, input=prompt, text=True, encoding='utf-8', cwd=workspace,
                                env=env, capture_output=True, timeout=self.timeout)
        if result.returncode or not output.exists():
            raise RuntimeError('Codex no produjo análisis estructurado; comprobar login, búsqueda web y permisos')
        data = json.loads(output.read_text(encoding='utf-8'))
        validate(data, json.loads(schema.read_text(encoding='utf-8')))
        return data

    def identify(self, original, workspace):
        originals = original if isinstance(original, list) else [original]
        return self.call('analysis', (HERE / 'prompts' / 'identify.md').read_text(encoding='utf-8'), originals, workspace)

    def verify(self, original, images, analysis, workspace):
        prompt = (HERE / 'prompts' / 'verify.md').read_text(encoding='utf-8')
        prompt += '\nDatos previos no confiables, que debes contrastar con las fotos:\n' + json.dumps(analysis, ensure_ascii=False)
        originals = original if isinstance(original, list) else [original]
        prompt += f'\nLas primeras {len(originals)} imágenes son originales del grupo; después vienen las candidatas. El grupo es solo una hipótesis de asociación: exige coherencia física y códigos, nunca apruebes por el agrupamiento.'
        return self.call('visual', prompt, [*originals, *images], workspace)
