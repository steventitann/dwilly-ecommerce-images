# Relojes D’WILLY: tienda → Drive → Codex → GitHub → Antigravity

La tienda toma una foto nítida del reloj junto a su etiqueta y la sube a `Imágenes dwilly reloj`, ID `1anN1xrwP1Lr39Uxs0Ti1m3kB8fawYwKj`. El worker prepara recursos para Antigravity. Su permiso de salida termina en GitHub: no tiene cliente del ecommerce ni métodos para escribir precio, stock o inventario.

## Qué hace el código

1. Lista con paginación las fotos de NUEVAS y, para facilitar el uso de la carpeta actual, también las fotos directamente en la raíz. No recorre PROCESADAS, ERROR ni PENDIENTE_REVISION.
2. Usa ID+checksum de Drive como clave estable. Descarga el original, valida su checksum y conserva la fotografía localmente.
3. Invoca Codex CLI con la imagen y salida JSON validada por esquema. Codex lee etiquetas, referencia y EAN y busca el producto exacto en internet.
4. Contrasta los identificadores con el texto real de las páginas de evidencia. Prioriza dominios oficiales conocidos; sin ellos exige dos dominios independientes. Una página inaccesible o con identificador no verificable se envía a revisión.
5. Descarga hasta tres fotos HD válidas entre un máximo de seis candidatos, rechaza duplicados y convierte a WebP, calidad 88 y máximo 1600 px. Exige al menos 1000 px en el lado mayor del original de catálogo.
6. Invoca de nuevo Codex con la fotografía original y los archivos descargados para comparar marca, modelo, referencia, color, esfera y brazalete.
7. Publica solo si el identificador es exacto y visible, todas las coincidencias son true y el menor score es >=0.95. El score es una valoración del modelo, **no una probabilidad calibrada ni una garantía estadística**. Los controles exactos son obligatorios además del score.
8. Genera `_01.webp` principal, `_02.webp` y `_03.webp` secundarias cuando existan, `barcode.svg` (EAN13 o Code128 de la referencia exacta), `manifest.json` y `operations.json`.
9. Hace commit y push sin force y descarga los archivos RAW para comprobar sus hashes. Solo después mueve la entrada a PROCESADAS y verifica sus padres en Drive.
10. Ambigüedad → PENDIENTE_REVISION. Error de descarga original/análisis técnico → ERROR. Fallos temporales de GitHub o del movimiento final quedan como operaciones pendientes de reintento, sin afirmar éxito ni perder el paquete.

En este flujo **PROCESADAS significa recursos preparados y publicados en GitHub**. No significa que Antigravity ya haya cargado el ecommerce. El manifiesto conserva `ecommerce_uploaded: false`; la carga posterior tiene su propio recibo.

## Módulos

- `drive.py`: autenticación, paginación, descarga, creación de estados y movimientos verificados.
- `analyst.py`, `prompts/`, `schemas/`: visión y búsqueda con Codex CLI, y segunda validación visual.
- `evidence.py`, `policy.py`: fuentes exactas, EAN con checksum y puerta de publicación.
- `assets.py`: descargas limitadas, WebP y códigos de barras.
- `publisher.py`: Git, publicación sin sobrescritura y readback por hash.
- `state.py`: SQLite local y log JSONL por operación, más bloqueo de concurrencia.
- `pipeline.py`: orquestación, reanudación y comandos de operación.

## Preparación del equipo que ejecutará el worker

Usar una **copia dedicada limpia** de este repositorio en main. Python 3.10+, Git y Codex CLI con sesión iniciada en ChatGPT y búsqueda web disponible. El worker no usa ni lee `OPENAI_API_KEY`; delega visión y búsqueda a la sesión de Codex CLI. Esa sesión necesita mantenerse válida y disponer de cuota.

```sh
python -m venv .venv
# Linux/macOS
. .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r watchflow/requirements.txt
codex login
python -m watchflow.pipeline doctor
```

Configurar `DWILLY_GOOGLE_CREDENTIALS` con la ruta de un JSON OAuth de usuario autorizado que incluya refresh_token, o de una cuenta de servicio con acceso de editor a la carpeta. Habilitar Drive API y otorgar el scope `https://www.googleapis.com/auth/drive`. Mantener el archivo fuera de Git, preferentemente fuera del checkout. No pegar tokens en commits, logs o prompts. Un enlace público no sustituye las credenciales de lectura y movimiento.

La conexión Google Drive del chat permite inspeccionar la carpeta, pero sus credenciales no se exportan al programa. **El worker programado necesita su propia autenticación de Drive**. Configurar también autenticación Git para push al repositorio; usar el gestor de credenciales o SSH del equipo. El runner utiliza el remote ya configurado y no almacena tokens en URLs.

Variables adicionales:

| Variable | Uso |
| --- | --- |
| DWILLY_CODEX_BIN | Ruta a Codex si no está en PATH |
| DWILLY_RUNTIME_DIR | Estado, originales y logs persistentes; por defecto .watch-runtime |
| DWILLY_INVENTORY_SNAPSHOT | Opcional: inventory.json de solo lectura para pre-matching |
| DWILLY_INPUT_GROUPS | Opcional: ruta privada de un JSON de grupos explícitos de fotos de un mismo producto |

Para fotos separadas, el JSON privado tiene la forma `[{"file_ids":["ID_RELOJ","ID_ETIQUETA"]}]`. Cada grupo contiene 2–5 imágenes que existen en la misma carpeta de entrada, sin compartir IDs con otro grupo. Se descargan todas, se comprueba cada versión/checksum y se pasan juntas a ambas revisiones visuales. El agrupamiento no confirma identidad: una asociación ambigua sigue enviándose a revisión. Todos los originales del grupo se mueven juntos, con reanudación idempotente. Nunca subir ese JSON privado al repositorio.

Las imágenes Casio con `.transform/` se descargan desde el archivo nativo anterior a esa transformación: un original de 500 px ampliado en el servidor no cuenta como HD.

El lote revisado en la conversación usa `watchflow/reviewed.py` y el expediente público `watch-review/approved-2026-10-06.json`. Es una revisión interactiva con páginas abiertas y comparación visual, no una ejecución autónoma de Drive ni una prueba de credenciales del worker. Sus manifiestos conservan ese modo de revisión explícitamente.

```sh
python -m watchflow.pipeline init-drive
python -m watchflow.pipeline scan
python -m watchflow.pipeline run
```

`init-drive` crea NUEVAS, PROCESADAS, PENDIENTE_REVISION y ERROR dentro de la carpeta configurada, sin mover automáticamente el lote existente. `run` acepta las fotos actuales en la raíz. `scan` no descarga ni cambia archivos.

## Ejecución programada

Cron, cada 15 minutos, en el equipo autenticado:

```cron
*/15 * * * * cd /ruta/dwilly-ecommerce-images && /ruta/dwilly-ecommerce-images/.venv/bin/python -m watchflow.pipeline run >> /ruta/logs/dwilly-watch.log 2>&1
```

En Windows, Programador de tareas: ejecutar `scripts/run_watchflow.ps1`, con el usuario que tiene la sesión de Codex y las variables/credenciales configuradas, cada 15 minutos. La opción de tareas simultáneas debe ser “No iniciar una instancia nueva”. El bloqueo del worker también evita dos ejecuciones. No crear el cron hasta completar doctor, init-drive, scan y una prueba real.

Una ejecución procesa hasta cinco entradas. La siguiente continúa el resto. No se ha activado ningún cron al publicar el código. En servidores sin sesión ChatGPT válida o sin búsqueda web el analista falla de forma cerrada.

## Logs y recuperación

`.watch-runtime/operations.jsonl` conserva detección/estado, descarga, identificación, validación de fuentes, preparación, publicación y movimientos. El estado y los originales deben respaldarse en el equipo del worker; no son datos públicos. Los paquetes publicados conservan un resumen JSON de operaciones, evidencias y hashes.

Si GitHub o Drive fallan después de preparar un paquete, la siguiente ejecución reanuda publicación/verificación/movimiento antes de buscar fotos nuevas. Nunca se mueve una foto a PROCESADAS sin readback correcto. Si el proceso fue terminado abruptamente, comprobar que no queda un worker activo antes de retirar `.watch-runtime/runner.lock`; se mantiene el bloqueo para evitar dos escritores. Una entrada enviada a ERROR o revisión se reintenta subiendo una foto corregida o limpiando su registro local bajo supervisión; no se reintenta una ambigüedad indefinidamente.

## Contrato para Antigravity

El preparador de expedientes revisados también admite Cubitt con UPC-A válido de 12 dígitos: conserva `ean=null`, `upc` y `code` exactos. Requiere reloj/etiqueta visibles juntos, dos dominios independientes y variante oficial con SKU, barcode, color e imágenes exactas. No convierte UPC en EAN. Esta validación se aplica a expedientes revisados; no se ha ampliado el esquema del analista autónomo para deducir UPC.

Lee [ANTIGRAVITY_WATCHES.md](../ANTIGRAVITY_WATCHES.md). Consumir `watch-ready/jobs/*/manifest.json`; no importar imágenes candidatas ni fotos originales. Cada job representa una foto/version y puede apuntar al mismo producto que otro job: deduplicar por identificador exacto y SHA-256 antes de cargar.

## Comprobaciones

```sh
python -m unittest discover -s watchflow/tests -v
```

Las pruebas ejercitan la puerta de confianza, variantes erróneas, EAN inválidos, matching sin escrituras, WebP, barcode, publicación simulada, ambigüedad y recuperación tras fallo Git. Las llamadas a Codex, Google Drive y GitHub se simulan en esas pruebas; no constituyen una prueba de integración en producción.

Referencias técnicas: [Codex no interactivo](https://learn.chatgpt.com/docs/non-interactive-mode), [Drive files.list](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list), [Drive files.update](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/update).
