"""Tools del agente SmartSched-ULIMA."""

from .academic import (
    buscar_profesor,
    detalle_curso,
    listar_cursos,
    prerrequisitos_de,
    resenas_de_profesor,
)
from .fichas import generar_ficha_curso, generar_ficha_profesor
from .silabos import descargar_silabo

__all__ = [
    "buscar_profesor",
    "descargar_silabo",
    "detalle_curso",
    "generar_ficha_curso",
    "generar_ficha_profesor",
    "listar_cursos",
    "prerrequisitos_de",
    "resenas_de_profesor",
]
