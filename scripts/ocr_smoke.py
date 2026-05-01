"""Smoke test manual contra Cloud Vision API.

Uso:
    uv run python scripts/ocr_smoke.py <ruta-imagen> [--out <ruta-json>]

Hace una llamada real a Vision (consume cuota). Imprime un resumen del texto
detectado y opcionalmente guarda el JSON crudo a disco.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.integrations.ocr.client import detect_document_text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if not args.image.exists():
        print(f"No existe: {args.image}", file=sys.stderr)
        return 1

    image_bytes = args.image.read_bytes()
    print(f"→ Enviando {args.image.name} ({len(image_bytes)} bytes) a Cloud Vision...")

    raw = detect_document_text(image_bytes)

    full_text = raw.get("fullTextAnnotation", {}).get("text", "")
    pages = raw.get("fullTextAnnotation", {}).get("pages", [])
    text_annotations = raw.get("textAnnotations", [])

    print(f"✓ Páginas: {len(pages)}")
    print(f"✓ Bloques (textAnnotations): {len(text_annotations)}")
    print(f"✓ Caracteres detectados: {len(full_text)}")
    print("--- primeras 500 chars ---")
    print(full_text[:500])
    print("--------------------------")

    if args.out:
        args.out.write_text(json.dumps(raw, ensure_ascii=False, indent=2))
        print(f"✓ JSON crudo guardado en {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
