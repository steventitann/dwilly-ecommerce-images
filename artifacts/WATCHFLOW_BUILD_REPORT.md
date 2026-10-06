# Flujo de relojes publicado para Antigravity

Fecha: 6 de octubre de 2026. Alcance actualizado por el propietario: preparar y publicar en GitHub; Antigravity integra el ecommerce.

## Inspección real

- Google Drive: se confirmó acceso mediante el conector a `Imágenes dwilly reloj` (`1anN1xrwP1Lr39Uxs0Ti1m3kB8fawYwKj`). La consulta devolvió 62 fotos directamente en la raíz y no encontró subcarpetas de estados.
- Ecommerce: se leyó el proyecto local `whatsapp-ai-bot`, remote `steventitann/catalogo-dwilly`, incluidos servidor e importadores. Identificador habitual `code`, principal `photo`, secundarias `gallery`. Persistencia mediante state-store (MySQL o JSON), medios mediante media-storage (R2 o almacenamiento local).
- No se modificaron productos, medios del ecommerce ni archivos de las 62 entradas de Drive durante esta construcción.

## Implementación

Código modular en `watchflow/`: Drive autenticado con paginación; análisis visual y búsqueda con Codex CLI; segunda comprobación visual; validación de páginas e identificadores; gate >=0.95; WebP HD y códigos de barras; paquete por foto/version; commit/push y verificación RAW; movimientos de estados; SQLite, JSONL y reanudación. Documentación en `watchflow/README.md` y contrato ecommerce en `ANTIGRAVITY_WATCHES.md`.

Los originales, OCR completo, credenciales y snapshots comerciales permanecen privados. Solo se publican recursos validados y metadatos de identidad/evidencia.

## Validación realizada

9 pruebas locales pasaron: identidad exacta, variantes y scores insuficientes, EAN/observación obligatoria, fuentes/ambigüedad, matching de inventario sin mutación, optimización y barcode, publicación simulada con idempotencia, ambigüedad sin publicación y recuperación tras fallo de Git.

Drive, Codex y GitHub se simulan en las pruebas de orquestación. El acceso del conector a la carpeta se verificó realmente; no se ejecutó identificación ni procesamiento masivo del lote. El worker standalone todavía no tiene `DWILLY_GOOGLE_CREDENTIALS` configurada. No se activó cron ni Programador de tareas. El modo doctor confirmó Codex y Git disponibles y credenciales de Drive del worker ausentes.

## Activación posterior

En el equipo que ejecutará el worker: configurar credenciales Drive con lectura/escritura sobre la carpeta, Git con permiso de push y Codex CLI con sesión y búsqueda web; ejecutar init-drive, scan y una prueba real antes de programar run. La conexión del chat no se transfiere automáticamente al worker. Esto es una dependencia de ejecución, no una credencial incluida en GitHub.

PROCESADAS indica paquete validado en GitHub. La carga final y la verificación pública del ecommerce se registran después por Antigravity en los recibos.
