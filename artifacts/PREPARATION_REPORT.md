# Preparación de recursos — 6 de octubre de 2026

Estado: PREPARED_FOR_INTEGRATION. Este reporte corresponde a la preparación y publicación del paquete; la asociación con productos del ecommerce queda para Antigravity.

- Catálogo validado: 6 productos, 18 imágenes.
- Descarga y validación: 18 OK, 0 errores. Cada archivo fue decodificado y se comprobó un lado mayor de al menos 1000 px.
- Optimización: WebP calidad 88, lado mayor máximo 1600 px.
- Los hashes originales y optimizados figuran en `assets_manifest.json`.
- Los WebP se incluyen en `artifacts/optimized/`. Los originales descargados se conservan localmente y se excluyen de Git.
- `catalog/catalogo.json` conserva las fuentes originales; `catalog/catalogo_preparado.json` proporciona rutas de los archivos WebP, hashes y URLs RAW del repositorio.
- Se incluyen seis JPG de referencia para comparación visual. La validación técnica no certifica por sí sola el modelo/color; Antigravity debe comprobar la correspondencia antes de cargar.

| Código | EAN | Recursos |
| --- | --- | --- |
| F35579 | 4060512030366 | 3 WebP OK |
| KK4284 | Sin EAN en el lote | 3 WebP OK |
| KI9173 | Sin EAN en el lote | 3 WebP OK |
| JQ1448 | 4068804453145 | 3 WebP OK |
| POR_CONFIRMAR / Barreda XLG | 4068818828816 | 3 WebP OK; identificar solo por EAN |
| JQ6920 | 4068812361968 | 3 WebP OK |

Comprobaciones ejecutadas: validación del catálogo, preparación de los 18 recursos, reapertura de WebP y comparación de SHA-256 mediante `scripts/publish_manifest.py`.

Pendiente en el proyecto ecommerce: matching de productos, respaldo de imágenes, dry run, carga con almacenamiento existente, pruebas/build pertinentes, verificación pública y reporte final de integración. No se ha modificado ni desplegado el ecommerce durante esta preparación.
