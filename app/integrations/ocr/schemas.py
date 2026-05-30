"""Schema de la respuesta del OCR (US-01/US-02).

Replica el shape que el frontend espera de `POST /api/v1/ocr/process-image`
(ver `CONTRACTS.md` §2 y `ocr_clean_output_example.json`). También se usa como
`response_schema` del modelo Gemini para forzar salida JSON estructurada.
"""

from pydantic import BaseModel, Field


class OCRHorario(BaseModel):
    dia: str = Field(description="Día en mayúsculas: LUN, MAR, MIE, JUE, VIE, SAB, DOM")
    inicio: str = Field(description="Hora de inicio en formato HH:MM (24h)")
    fin: str = Field(description="Hora de fin en formato HH:MM (24h)")
    aula: str | None = None


class OCRSeccion(BaseModel):
    seccion: str
    profesor: str = ""
    vacantes: int = 0
    horario: list[OCRHorario] = Field(default_factory=list)


class OCRCurso(BaseModel):
    codigo: str = ""
    nombre: str
    creditos: float = 0.0
    nivel: int = 0
    secciones: list[OCRSeccion] = Field(default_factory=list)


class OCRExtractionResponse(BaseModel):
    cursos: list[OCRCurso] = Field(default_factory=list)
