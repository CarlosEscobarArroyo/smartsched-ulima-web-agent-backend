"""Router de horarios (US-07). Expone la generación de combinaciones sin cruces."""

from fastapi import APIRouter, HTTPException

from app.domains.schedules import service
from app.domains.schedules.schemas import GeneratedSchedule, GenerateRequest

router = APIRouter(prefix="/schedules", tags=["schedules"])


# Síncrono a propósito: el backtracking es CPU-bound, FastAPI lo corre en un threadpool
# y así no bloquea el event loop durante el timeout de generación.
@router.post("/generate", response_model=GeneratedSchedule)
def generate(payload: GenerateRequest) -> GeneratedSchedule:
    try:
        return service.generate(payload)
    except service.NoCoursesSelectedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
