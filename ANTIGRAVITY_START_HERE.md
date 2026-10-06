# Integración de imágenes D’WILLY con Antigravity

Repositorio de recursos: https://github.com/steventitann/dwilly-ecommerce-images

Este repositorio contiene el lote de imágenes y su especificación. La integración debe realizarse desde el repositorio real del ecommerce, usando su almacenamiento y su modelo de productos.

## Procedimiento

1. Clona este repositorio junto al ecommerce. Lee `AGENTS.md`, `config/job.json` y `catalog/catalogo.json`.
2. Consulta `artifacts/PREPARATION_REPORT.md` y `artifacts/assets_manifest.json`. Si hay recursos preparados con estado OK, usa sus archivos WebP y valida su hash; descarga de nuevo únicamente los recursos faltantes. Los JPG de `referencias/` sirven para comparación visual, no para sustituir automáticamente las fotos del catálogo.
3. Descubre en el ecommerce los identificadores de productos, las variantes, el almacenamiento y el mecanismo de carga. No supongas que el repositorio de imágenes contiene el ecommerce.
4. Encuentra productos por EAN exacto y después código exacto, comprobando modelo y color. Barreda XLG solo admite EAN 4068818828816. Omite ausentes o ambiguos y registra el motivo.
5. Guarda un respaldo local de los campos de imágenes de todos los productos objetivo y un dry run antes de modificar el ecommerce. No publiques datos de clientes, pedidos, secretos ni respaldos de producción en este repositorio público.
6. Carga los archivos usando el almacenamiento existente; orden 1 es principal y órdenes 2 y 3 son secundarias. Evita duplicar imágenes al repetir la importación. Conserva imágenes anteriores hasta comprobar las nuevas y prepara restauración desde el respaldo.
7. Verifica que solo cambiaron campos de imágenes: precios, stock, tallas, descuentos, categorías, marcas y textos deben permanecer iguales. Ejecuta las comprobaciones pertinentes y verifica URLs y vistas públicas.
8. Deja `artifacts/FINAL_REPORT.md` con resultados por producto, pruebas y estado de despliegue. Nunca declares integración completada solo por descargar o publicar estos recursos.

## Prompt para usar en Antigravity

Lee https://github.com/steventitann/dwilly-ecommerce-images/blob/main/ANTIGRAVITY_START_HERE.md y clona ese repositorio de recursos junto al proyecto del ecommerce. Integra las fotos válidas de los seis productos siguiendo AGENTS.md, con respaldo, dry run, identificación exacta por EAN/código y verificación final. Usa los WebP preparados cuando estén disponibles. Cambia exclusivamente imágenes; conserva precios, stock, tallas, descuentos y demás datos. Omite productos ausentes o ambiguos. Entrega el reporte final de integración.
