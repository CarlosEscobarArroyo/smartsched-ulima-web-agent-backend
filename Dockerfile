# Backend FastAPI + agente ADK embebido (ulima-agent) — imagen para Cloud Run.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# uv: gestor de dependencias (mismo que en local).
RUN pip install --no-cache-dir uv==0.8.13

WORKDIR /code

# Se copia todo el contexto: app/ y ulima-agent/ son necesarios porque
# ulima-agent es una dependencia editable del workspace de uv
# ([tool.uv.sources] ulima-agent = { path = "ulima-agent", editable = true }).
COPY . .

# Instala las dependencias exactas del lockfile, sin grupo dev.
RUN uv sync --frozen --no-dev

EXPOSE 8080

# Cloud Run inyecta la variable PORT (8080 por defecto); se expande con shell.
CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
