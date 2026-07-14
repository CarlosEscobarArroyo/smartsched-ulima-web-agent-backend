# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools import FunctionTool
from google.genai import types

import os

from .prompts import prompts_dict
from .tools import (
    buscar_profesor,
    descargar_silabo,
    detalle_curso,
    generar_ficha_curso,
    generar_ficha_profesor,
    listar_cursos,
    prerrequisitos_de,
    resenas_de_profesor,
)

# Proyecto GCP OBLIGATORIO (ver CLAUDE.md): Project ID "ulima-agent"
# (nombre visible "smartsched-ulima", número 563034868757). Nunca usar otro.
# Se respeta GOOGLE_CLOUD_PROJECT si ya viene del entorno/deploy; si no, se fija aquí
# para no heredar el proyecto activo de gcloud/ADC (que puede ser uno corporativo).
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "ulima-agent")
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"


# --- Configuración del modelo ---
MODEL_TEMPERATURE = 0.7

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    description="Asistente académico para estudiantes de la Universidad de Lima (ULIMA).",
    instruction=prompts_dict["root_agent_prompt"],
    generate_content_config=types.GenerateContentConfig(
        temperature=MODEL_TEMPERATURE,
    ),
    # Tools tipadas de solo lectura sobre la BD (Neon): profesores, cursos,
    # dificultad, prerrequisitos y reseñas. Ver ulima_agent/tools/academic.py.
    # Las dos últimas generan una FICHA VISUAL (one page HTML) y devuelven una URL
    # servida por GET /api/v1/fichas/{id}. Ver ulima_agent/tools/fichas.py.
    tools=[
        FunctionTool(func=buscar_profesor),
        FunctionTool(func=resenas_de_profesor),
        FunctionTool(func=listar_cursos),
        FunctionTool(func=detalle_curso),
        FunctionTool(func=prerrequisitos_de),
        FunctionTool(func=generar_ficha_curso),
        FunctionTool(func=generar_ficha_profesor),
        FunctionTool(func=descargar_silabo),
    ],
)

app = App(
    root_agent=root_agent,
    name="ulima_agent",
)