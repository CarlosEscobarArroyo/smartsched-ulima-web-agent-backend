"""Schemas Pydantic del dominio de autenticación (US-24/25)."""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Credenciales de login. Replica la validación Zod del FE."""

    email: EmailStr
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    """Usuario expuesto al cliente (sin datos sensibles)."""

    id: str
    email: str
    name: str
    role: str


class TokenResponse(BaseModel):
    """Respuesta del login: token Bearer + usuario."""

    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6, max_length=128)


class MessageResponse(BaseModel):
    message: str
