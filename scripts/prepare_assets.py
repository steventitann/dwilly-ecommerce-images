#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "catalogo.json"
ARTIFACTS = ROOT / "artifacts"
ORIGINALS = ARTIFACTS / "downloaded_originals"
OPTIMIZED = ARTIFACTS / "optimized"
MANIFEST = ARTIFACTS / "assets_manifest.json"

RULES = json.loads((ROOT / 'config' / 'job.json').read_text(encoding='utf-8'))['rules']
MIN_LONG_SIDE = int(RULES['minimum_long_side_px'])
MAX_LONG_SIDE = int(RULES['preferred_long_side_px'])
WEBP_QUALITY = int(RULES['webp_quality'])

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; DWILLY-Ecommerce-Image-Importer/1.0)"
})

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def safe_code(product: dict) -> str:
    code = product.get("codigo") or "SIN_CODIGO"
    if code == "POR_CONFIRMAR":
        ean = product.get("ean") or "SIN_EAN"
        return f"BARREDA_XLG_EAN_{ean}"
    return code.replace("/", "_").replace("\\", "_").strip()

def optimize(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    w, h = img.size
    long_side = max(w, h)
    if long_side > MAX_LONG_SIDE:
        scale = MAX_LONG_SIDE / long_side
        img = img.resize((round(w * scale), round(h * scale)), Image.Resampling.LANCZOS)
    return img

def main() -> int:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    ORIGINALS.mkdir(parents=True, exist_ok=True)
    OPTIMIZED.mkdir(parents=True, exist_ok=True)

    results = []
    seen_hashes = {}

    for product in data["productos"]:
        code = safe_code(product)
        p_orig = ORIGINALS / code
        p_opt = OPTIMIZED / code
        p_orig.mkdir(parents=True, exist_ok=True)
        p_opt.mkdir(parents=True, exist_ok=True)

        for meta in product["imagenes"]:
            order = int(meta["orden"])
            url = meta["url"]
            item = {
                "codigo_catalogo": product.get("codigo"),
                "ean": product.get("ean"),
                "producto": product.get("producto"),
                "orden": order,
                "rol": meta.get("rol"),
                "source_url": url,
                "status": "ERROR",
            }

            try:
                r = session.get(url, timeout=45, allow_redirects=True)
                r.raise_for_status()
                content_type = (r.headers.get("content-type") or "").lower()
                raw = r.content
                if not raw:
                    raise ValueError("respuesta vacía")

                digest = sha256(raw)
                item["sha256"] = digest
                item["content_type"] = content_type
                item["bytes"] = len(raw)

                with Image.open(io.BytesIO(raw)) as im:
                    im.verify()
                with Image.open(io.BytesIO(raw)) as im:
                    im.load()
                    item["source_width"], item["source_height"] = im.size
                    if max(im.size) < MIN_LONG_SIDE:
                        raise ValueError(f"resolución insuficiente: {im.size}")

                    # Save original using detected format extension
                    fmt = (im.format or "JPEG").upper()
                    ext = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "AVIF": ".avif"}.get(fmt, "." + fmt.lower())
                    orig_path = p_orig / f"{code}_{order:02d}{ext}"
                    orig_path.write_bytes(raw)

                    out = optimize(im)
                    webp_path = p_opt / f"{code}_{order:02d}.webp"
                    out.save(webp_path, "WEBP", quality=WEBP_QUALITY, method=6)

                    item["original_path"] = str(orig_path.relative_to(ROOT))
                    item["optimized_path"] = str(webp_path.relative_to(ROOT))
                    item["optimized_sha256"] = sha256(webp_path.read_bytes())
                    item["optimized_bytes"] = webp_path.stat().st_size
                    item["optimized_width"], item["optimized_height"] = out.size

                if digest in seen_hashes:
                    item["duplicate_of"] = seen_hashes[digest]
                else:
                    seen_hashes[digest] = f"{code}_{order:02d}"

                item["status"] = "OK"

            except Exception as exc:
                item["error"] = str(exc)

            results.append(item)
            print(item["status"], code, order, url)

    summary = {
        "total": len(results),
        "ok": sum(x["status"] == "OK" for x in results),
        "errors": sum(x["status"] != "OK" for x in results),
        "items": results,
    }
    MANIFEST.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nManifest: {MANIFEST}")
    return 0 if summary["errors"] == 0 else 2

if __name__ == "__main__":
    raise SystemExit(main())
