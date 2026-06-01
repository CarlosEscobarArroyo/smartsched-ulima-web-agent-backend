"""Schemas Pydantic del panel de administración (US-29/30/31)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class AdminUserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateAdminUserRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: Literal["student", "admin"] = "student"


class UpdateAdminUserRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    role: Literal["student", "admin"]


class AdminStatsOut(BaseModel):
    total_users: int
    student_count: int
    admin_count: int
    professor_count: int
    course_count: int


class AdminProfessorOut(BaseModel):
    id: str
    name: str
    initials: str
    review_count: int
    updated_at: datetime
    model_config = {"from_attributes": True}


class CreateAdminProfessorRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class UpdateAdminProfessorRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class AdminCourseOut(BaseModel):
    id: str
    code: str
    name: str
    level: str
    prerequisites: list[str]
    professor_id: str | None
    professor_name: str | None
    updated_at: datetime
    model_config = {"from_attributes": True}


class CreateAdminCourseRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    level: str = Field(min_length=1, max_length=10)
    prerequisites: list[str] = []
    professor_id: str | None = None


class UpdateAdminCourseRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    level: str = Field(min_length=1, max_length=10)
    prerequisites: list[str] = []
    professor_id: str | None = None
