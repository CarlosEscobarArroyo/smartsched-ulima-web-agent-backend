"""Endpoints públicos de profesores y reseñas (US-21)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.admin import service as admin_service
from app.domains.auth.deps import get_current_user
from app.domains.professors import service
from app.domains.professors.schemas import CreateReviewRequest, MyReviewOut, ProfessorOut, ReviewOut
from app.domains.users.models import User

router = APIRouter(prefix="/professors", tags=["professors"])


@router.get("/my-reviews", response_model=list[MyReviewOut])
async def get_my_reviews(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[MyReviewOut]:
    return await service.list_my_reviews(db, current_user)


@router.get("", response_model=list[ProfessorOut])
async def list_professors(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProfessorOut]:
    return await service.list_professors(db)


@router.get("/{professor_id}", response_model=ProfessorOut)
async def get_professor(
    professor_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfessorOut:
    return await service.get_professor(db, professor_id)


@router.get("/{professor_id}/photo")
async def get_professor_photo(
    professor_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Sirve la foto del profesor desde GCS. Pública por id opaco: la embebe la
    ficha (iframe) y el directorio del panel admin. 404 si no tiene foto."""
    data, content_type = await admin_service.get_professor_photo(db, professor_id)
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.delete("/my-reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_review(
    review_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_my_review(db, review_id, current_user)


@router.post(
    "/{professor_id}/reviews",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_review(
    professor_id: str,
    payload: CreateReviewRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReviewOut:
    return await service.add_review(db, professor_id, payload, current_user)
