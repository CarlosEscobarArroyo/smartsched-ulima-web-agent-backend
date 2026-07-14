"""Estructurador multimodal: imagen(es) del horario → JSON `{cursos: [...]}` (US-01).

Es el corazón del flujo OCR. En vez de aplanar la imagen a texto con Cloud Vision
(que destruye la estructura fila/columna de la tabla y hace que el modelo adivine a
qué día/sección pertenece cada horario), le pasamos la **imagen directa** a Gemini
—que es multimodal— con `response_schema` para forzar la salida al shape de
`OCRExtractionResponse`. Gemini lee la grilla visualmente y respeta columnas (días)
y filas (secciones).

El import de `google.genai` y la creación del cliente son perezosos para que importar
este módulo no requiera credenciales GCP (los tests del endpoint mockean el estructurador).
"""

import json
import logging
import os

from app.integrations.ocr.schemas import OCRExtractionResponse

logger = logging.getLogger(__name__)

MODEL = "gemini-flash-latest"
GCP_PROJECT = "ulima-agent"
GCP_LOCATION = "global"

# Par (bytes, mime_type) de una imagen ya validada por el router.
ImageInput = tuple[bytes, str]

STRUCTURE_INSTRUCTION = """
Eres un extractor de datos. Recibes una o varias imágenes (screenshots) de la oferta
de cursos de la Universidad de Lima (ULIMA) y debes estructurar su contenido en JSON.

La imagen es una TABLA. Léela respetando filas y columnas:
- Cada bloque empieza con una cabecera de curso con COD. (código), CRD. (créditos),
  Nv. (nivel) y NOMBRE ASIGNATURA (nombre del curso).
- Debajo, cada fila es una SECCIÓN: su número (columna SEC.), el profesor (columna
  PROFESOR TITULAR) y sus horarios repartidos en las columnas de días.
- Las columnas de días son LUN, MAR, MIE, JUE, VIE, SAB (y DOM si aparece). La celda
  que cruza una sección con un día contiene el horario de esa sección ESE día.

Horarios:
- El contenido de una celda de día suele ser un RANGO DE HORAS "inicio-fin" en formato
  de 24 horas, p. ej. "7-10" = 07:00 a 10:00, "17-19" = 17:00 a 19:00, "14-16" = 14:00 a 16:00.
- Por cada celda con horario crea un objeto {dia, inicio, fin, aula}:
  - `dia` = el encabezado de esa columna (LUN/MAR/MIE/JUE/VIE/SAB/DOM).
  - `inicio` y `fin` en formato HH:MM de 24 horas ("07:00", "10:00").
- Una misma sección suele tener clase en varios días: añade un objeto por CADA celda
  con horario, asignando el día por su columna. No mezcles horarios entre secciones:
  cada rango pertenece a la fila (sección) en la que está.
- Si la celda incluye además un AULA (un código de salón, p. ej. "850014" o "A-201"),
  ponlo en `aula`; si la celda solo tiene el rango de horas, usa null en `aula`.

Reglas:
- Extrae TODOS los cursos y TODAS las secciones visibles. Recorre la tabla fila por
  fila de arriba abajo y no omitas ninguna sección, aunque haya muchas o se repita el
  profesor. La respuesta debe incluir cada fila de sección de cada bloque de curso.
- Extrae ÚNICAMENTE lo que aparece en la imagen. NO inventes datos. Si un campo no
  aparece, usa "" para textos, 0 para números y null para `aula`.
- `dia` SIEMPRE en mayúsculas y abreviado a tres letras: LUN, MAR, MIE, JUE, VIE, SAB, DOM.
- Cada curso aparece una sola vez, con todas sus secciones agrupadas bajo él.
- Ignora las columnas auxiliares (casillas de selección, GR., INF., "Vac", iconos).
""".strip()


class CourseStructurer:
    """Facade (estructural) sobre el SDK de `google.genai`/Vertex.

    Expone `structure(images)` y esconde el subsistema del SDK (`genai.Client`,
    `types.Part`, `GenerateContentConfig`, `response_schema`, parseo de la respuesta).
    La única instancia por proceso (Singleton) se crea abajo como `_structurer`.
    """

    def __init__(self) -> None:
        self._client: object | None = None

    def _get_client(self) -> object:
        if self._client is None:
            from google import genai

            os.environ.setdefault("GOOGLE_CLOUD_PROJECT", GCP_PROJECT)
            self._client = genai.Client(
                vertexai=True,
                project=os.environ.get("GOOGLE_CLOUD_PROJECT", GCP_PROJECT),
                location=GCP_LOCATION,
            )
        return self._client

    def structure(self, images: list[ImageInput]) -> dict:
        """Imágenes (bytes, mime) → dict con la clave `cursos`. Lanza si el modelo falla."""
        from google.genai import types

        client = self._get_client()
        parts = [
            types.Part.from_bytes(data=data, mime_type=mime_type)
            for data, mime_type in images
        ]
        parts.append(
            types.Part.from_text(
                text="Extrae los cursos, secciones y horarios de esta(s) imagen(es)."
            )
        )
        response = client.models.generate_content(  # type: ignore[attr-defined]
            model=MODEL,
            contents=parts,
            config=types.GenerateContentConfig(
                system_instruction=STRUCTURE_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=OCRExtractionResponse,
                temperature=0.0,
                # Tablas densas (muchas secciones) generan JSON largo; subimos el tope
                # para que el modelo no se corte y devuelva todas las filas.
                max_output_tokens=16384,
            ),
        )
        return json.loads(response.text)


# Singleton (creacional): una única instancia por proceso, expuesta vía
# get_course_structurer(). El cliente genai/Vertex de adentro se crea perezosamente.
_structurer = CourseStructurer()


# Factory / provider (creacional): función de acceso usada como dependencia
# (FastAPI Depends). Devuelve el singleton y permite sobrescribirlo en tests.
def get_course_structurer() -> CourseStructurer:
    return _structurer
