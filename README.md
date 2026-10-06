# D’WILLY — Proyecto autónomo para Codex

## Integración con Antigravity

**Flujo de relojes Google Drive → GitHub:** [watchflow/README.md](watchflow/README.md). El worker identifica fotos de `Imágenes dwilly reloj`, valida referencias y variantes y publica paquetes con WebP y códigos de barras. Antigravity carga después el ecommerce siguiendo [ANTIGRAVITY_WATCHES.md](ANTIGRAVITY_WATCHES.md).

Empieza por [ANTIGRAVITY_START_HERE.md](ANTIGRAVITY_START_HERE.md). Este repositorio publica recursos e instrucciones para seis productos (18 imágenes); Antigravity realiza la integración desde el proyecto real del ecommerce. Consulta `artifacts/PREPARATION_REPORT.md` para conocer el estado de preparación.

Este paquete convierte la tarea de cargar imágenes de productos en un trabajo autónomo para Codex.

## Cómo usarlo

### Opción recomendada
Copia esta carpeta dentro del repositorio del ecommerce, por ejemplo:

```text
tu-ecommerce/
├── ... código actual ...
└── dwilly-codex-job/
    ├── AGENTS.md
    ├── CODEX_START_HERE.md
    ├── catalog/
    ├── scripts/
    └── config/
```

Después dile a Codex únicamente:

```text
Abre dwilly-codex-job/CODEX_START_HERE.md y ejecuta el proyecto completo.
```

### Qué hará Codex

- descubrirá cómo está construido el ecommerce;
- hará backup de los campos de imágenes;
- descargará y validará las fotos;
- encontrará los productos por EAN/código;
- cargará las imágenes usando la arquitectura existente;
- hará dry run;
- aplicará cambios;
- correrá tests/build;
- verificará `dwillygalapagos.com`;
- dejará un reporte final.

## Seguridad

El trabajo está limitado a imágenes. No autoriza modificaciones de precio, stock, tallas, descuentos, pedidos ni clientes.
