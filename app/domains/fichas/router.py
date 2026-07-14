"""Sirve las fichas (one page) HTML que genera el agente IA.

El agente corre in-process dentro de este backend; sus tools
(`ulima_agent.tools.fichas`) guardan el HTML en una caché de módulo y devuelven
una URL a esta ruta. Aquí solo se lee esa caché y se entrega el HTML.

Es público por id opaco (uuid): los datos provienen de la malla académica y así un
iframe o una pestaña nueva pueden abrir la ficha sin mandar `Authorization`. El
import del agente es perezoso para no exigir sus dependencias al montar el router.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/fichas", tags=["fichas"])


@router.get("/{ficha_id}", response_class=HTMLResponse)
async def get_ficha(ficha_id: str) -> HTMLResponse:
    from ulima_agent.tools.fichas import read_ficha_html

    doc = read_ficha_html(ficha_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ficha no encontrada o expirada",
        )
    return HTMLResponse(content=doc)
