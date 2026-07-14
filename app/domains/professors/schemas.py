"""Schemas públicos de profesores y reseñas (US-21)."""


from pydantic import BaseModel, Field


class ReviewOut(BaseModel):
    id: str
    student: str
    rating: int
    comment: str
    date: str

    model_config = {"from_attributes": True}


class CourseOut(BaseModel):
    id: str
    code: str
    name: str

    model_config = {"from_attributes": True}


class ProfessorOut(BaseModel):
    id: str
    name: str
    course: str
    initials: str
    department: str | None
    degree: str | None
    bio: str | None
    email: str | None
    availability: list[str]
    rating: float
    reviews: list[ReviewOut]
    courses: list[CourseOut]

    model_config = {"from_attributes": True}


class CreateReviewRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=500)


class MyReviewOut(BaseModel):
    id: str
    professor: str
    course: str
    rating: int
    comment: str
