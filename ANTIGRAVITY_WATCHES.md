# Antigravity: consumir los relojes preparados en GitHub

El flujo vigente es tienda → Drive → preparación con Codex → este repositorio → integración con Antigravity. La preparación **no carga ni modifica el ecommerce**.

## Proyecto real inspeccionado

Repositorio ecommerce: `steventitann/catalogo-dwilly`. Aplicación `whatsapp-ai-bot`, Node.js, servidor `server.mjs`.

- Productos: `inventory.items`; `code` contiene habitualmente el EAN. Hay registros del mismo producto en sucursales diferentes.
- Campos de imágenes: `photo` principal y `gallery` secundarias.
- Persistencia: `readInventoryData` / `saveInventoryData` reutilizan `lib/state-store.mjs`; con configuración de MySQL guardan el estado allí y sin ella usan archivos JSON. No sustituir la base de producción por el snapshot local.
- Medios: `lib/media-storage.mjs`, `createMediaStorage`, `saveProductImage`. Reutiliza Cloudflare R2 cuando está configurado o el directorio de medios local existente.
- Uploader existente: `handlePhotoUpload` utiliza `mediaStorage.saveProductImage` y actualiza `photo`/`gallery`. Antigravity debe reutilizar esa lógica y su autenticación; no introducir otro proveedor ni guardar base64 en la base de datos.

Estas convenciones fueron leídas en el proyecto local el 6 de octubre de 2026. Verificar el código actual antes de integrar, porque el servidor puede haber evolucionado.

## Entrada

Cada `watch-ready/jobs/<job_id>/manifest.json` incluye identidad, EAN/referencia/code, fuentes, score mínimo, validación visual, barcode y entre una y tres imágenes con ruta, rol y SHA-256. No cargar automáticamente si el manifiesto no existe, el estado no es READY_FOR_ANTIGRAVITY, score <0.95 o algún atributo visual no coincide. Los SVG de barcode son identificadores para clasificación; no son fotos del producto ni nuevos EAN.

## Integración

Los paquetes Cubitt revisados el 8 de octubre conservan UPC-A de 12 dígitos en `identity.upc` y `identity.code`, con `identity.ean=null`. Buscar ese código exacto sin anteponer cero ni convertirlo en EAN. El SVG de estos paquetes es UPC-A. Su referencia CT-AURA2/CT-VIVA2 y color están corroborados en la variante oficial del fabricante y una fuente independiente.

1. Obtener el estado **actual** de productos del ecommerce y buscar EAN exacto primero (también en `code`), luego `code` exacto. La referencia fabricante solo sirve como code si realmente está guardada como code exacto; no hacer matching aproximado por descripción. Si no existe producto exacto, omitirlo y registrar NOT_FOUND.
2. Verificar marca, modelo y variante/color contra descripción y metadatos actuales. Si varios registros comparten el identificador, verificar que son el mismo producto en distintas sucursales; conservar todos sus stocks y precios individuales.
3. Crear respaldo privado de `photo` y `gallery` y un dry run. Comprobar hashes de cada archivo antes de subir. Reutilizar almacenamiento actual. Usar nombres versionados por hash para evitar cachés y colisiones.
4. Aplicar `_01` a `photo` y `_02`/`_03` a `gallery`. No borrar recursos anteriores antes de verificar los nuevos. Evitar duplicados por hash y no procesar de nuevo un job ya importado.
5. Restringir el cambio a `photo` y `gallery`, con comparación completa antes/después de todos los demás campos. No modificar precios, descuentos, stock, tallas, inventario comercial, marca, categoría, descripción, pedidos o clientes. No publicar respaldos ni filas completas de producción en este repo público.
6. Ejecutar pruebas/check/build adecuados en el ecommerce. Verificar HTTP 200 y hashes/decodificación de todas las nuevas fotos y la página pública `https://www.dwillygalapagos.com/catalogo/producto/{code}`. Confirmar la principal y las vistas correctas.
7. Escribir un recibo sanitizado `watch-ready/receipts/<job_id>.json` con job_id, resultado, identificador exacto, imágenes/URLs finales, fecha y validación pública. Usar UPDATED solo tras comprobarlo. Si falla, restaurar campos de imágenes desde el respaldo y reportar ERROR. No escribir el inventario completo ni credenciales en el recibo.

Antigravity lleva la integración y su despliegue en el repositorio ecommerce; este repositorio conserva recursos y manifiestos.

## Prompt

Lee ANTIGRAVITY_WATCHES.md de https://github.com/steventitann/dwilly-ecommerce-images. Consume los manifiestos READY_FOR_ANTIGRAVITY en watch-ready/jobs, verifica sus hashes e integra únicamente imágenes en el proyecto actual D’WILLY. Reutiliza state-store y media-storage, identifica por EAN y luego code exacto, haz respaldo y dry run y conserva todos los demás datos. Omite ausentes o ambiguos. Verifica la tienda pública y publica un recibo sanitizado por job.
