#!/usr/bin/env python3
from pathlib import Path
import json, sys

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "catalog" / "catalogo.json"
data = json.loads(p.read_text(encoding="utf-8"))

errors = []
for i, product in enumerate(data.get("productos", []), start=1):
    if not product.get("producto"):
        errors.append(f"{i}: falta producto")
    if not product.get("codigo") and not product.get("ean"):
        errors.append(f"{i}: sin codigo ni EAN")
    imgs = product.get("imagenes") or []
    orders = sorted(x.get("orden") for x in imgs)
    if orders != [1,2,3]:
        errors.append(f"{i}: órdenes de imágenes no son [1,2,3]: {orders}")
    if any(not x.get("url") for x in imgs):
        errors.append(f"{i}: imagen sin URL")

if errors:
    print("\n".join(errors))
    raise SystemExit(2)

print(f"OK: {len(data['productos'])} productos y {sum(len(x['imagenes']) for x in data['productos'])} imágenes.")
