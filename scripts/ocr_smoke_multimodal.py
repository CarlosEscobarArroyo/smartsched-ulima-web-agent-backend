"""Smoke test manual del OCR multimodal (Gemini directo, sin Cloud Vision).

Uso:
    uv run python scripts/ocr_smoke_multimodal.py <ruta-imagen> [<ruta-imagen2> ...]

Hace una llamada real a Vertex AI / Gemini (consume cuota; requiere credenciales GCP,
p. ej. `gcloud auth application-default login`). Imprime el JSON `{cursos}` resultante.
"""

from __future__ import annotations

import json
import mimetypes
import sys
from pathlib import Path

from app.integrations.ocr.service import get_ocr_service
from app.integrations.ocr.structurer import ImageInput


def main() -> int:
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        print("Uso: ocr_smoke_multimodal.py <imagen> [<imagen2> ...]", file=sys.stderr)
        return 1

    images: list[ImageInput] = []
    for path in paths:
        if not path.exists():
            print(f"No existe: {path}", file=sys.stderr)
            return 1
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        data = path.read_bytes()
        images.append((data, mime))
        print(f"→ {path.name} ({len(data)} bytes, {mime})")

    print("→ Enviando a Gemini multimodal...")
    result = get_ocr_service().extract(images)
    n_sec = sum(len(c.secciones) for c in result.cursos)
    print(f"→ {len(result.cursos)} cursos, {n_sec} secciones en total")
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
