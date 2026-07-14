"""Lógica del panel de administración (US-29/30/31/32)."""

import csv
import io
import re
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domains.admin import repository as admin_repo
from app.domains.admin.models import Course, Professor
from app.domains.admin.schemas import (
    AdminCourseOut,
    AdminProfessorOut,
    AdminStatsOut,
    AdminUserOut,
    BulkDeleteProfessorsResult,
    CreateAdminCourseRequest,
    CreateAdminProfessorRequest,
    CreateAdminUserRequest,
    ImportProfessorsResult,
    UpdateAdminCourseRequest,
    UpdateAdminProfessorRequest,
    UpdateAdminUserRequest,
)
from app.domains.users import repository
from app.domains.users.models import User, UserRole
from app.integrations.bucket import bucket


def _to_out(user: User) -> AdminUserOut:
    return AdminUserOut.model_validate(user)


async def list_users(db: AsyncSession) -> list[AdminUserOut]:
    users = await repository.list_all(db)
    return [_to_out(u) for u in users]


async def create_user(db: AsyncSession, payload: CreateAdminUserRequest) -> AdminUserOut:
    existing = await repository.get_by_email(db, payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese correo",
        )
    user = await repository.create(
        db,
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    return _to_out(user)


async def update_user(
    db: AsyncSession, user_id: str, payload: UpdateAdminUserRequest
) -> AdminUserOut:
    existing = await repository.get_by_email(db, payload.email)
    if existing is not None and existing.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese correo",
        )
    user = await repository.update_by_id(
        db, user_id, name=payload.name, email=payload.email, role=payload.role
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return _to_out(user)


async def delete_user(db: AsyncSession, admin_id: str, user_id: str) -> None:
    if admin_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puede eliminar su propia cuenta",
        )
    found = await repository.delete_by_id(db, user_id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")


async def get_stats(db: AsyncSession) -> AdminStatsOut:
    total = await repository.count_all(db)
    students = await repository.count_by_role(db, UserRole.STUDENT.value)
    admins = await repository.count_by_role(db, UserRole.ADMIN.value)
    professors = await admin_repo.count_professors(db)
    courses = await admin_repo.count_courses(db)
    return AdminStatsOut(
        total_users=total,
        student_count=students,
        admin_count=admins,
        professor_count=professors,
        course_count=courses,
    )


# ---------------------------------------------------------------------------
# Profesores
# ---------------------------------------------------------------------------


def _professor_initials(name: str) -> str:
    cleaned = re.sub(r"(?i)^(?:dr\.?|dra\.?|prof\.?|mg\.?)\s*", "", name)
    parts = cleaned.strip().split()
    first = parts[0][0] if parts else ""
    second = (
        parts[1][0]
        if len(parts) > 1
        else (parts[0][1] if parts and len(parts[0]) > 1 else "")
    )
    return (first + second).upper()


def _prof_to_out(p: Professor, review_count: int = 0) -> AdminProfessorOut:
    return AdminProfessorOut(
        id=p.id,
        name=p.name,
        initials=_professor_initials(p.name),
        department=p.department,
        degree=p.degree,
        bio=p.bio,
        email=p.email,
        has_photo=p.photo_gcs_path is not None,
        review_count=review_count,
        updated_at=p.updated_at,
    )


async def list_professors(db: AsyncSession) -> list[AdminProfessorOut]:
    profs = await admin_repo.list_professors(db)
    counts = await admin_repo.count_reviews_by_professor(db)
    return [_prof_to_out(p, counts.get(p.id, 0)) for p in profs]


async def create_professor(
    db: AsyncSession, payload: CreateAdminProfessorRequest
) -> AdminProfessorOut:
    p = await admin_repo.create_professor(
        db,
        name=payload.name,
        department=payload.department,
        degree=payload.degree,
        bio=payload.bio,
        email=payload.email,
    )
    return _prof_to_out(p)


async def update_professor(
    db: AsyncSession, professor_id: str, payload: UpdateAdminProfessorRequest
) -> AdminProfessorOut:
    p = await admin_repo.update_professor(
        db,
        professor_id,
        name=payload.name,
        department=payload.department,
        degree=payload.degree,
        bio=payload.bio,
        email=payload.email,
    )
    if p is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profesor no encontrado"
        )
    review_count = await admin_repo.count_reviews_for_professor(db, professor_id)
    return _prof_to_out(p, review_count)


async def delete_professor(db: AsyncSession, professor_id: str) -> None:
    found = await admin_repo.delete_professor(db, professor_id)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profesor no encontrado"
        )


async def bulk_delete_professors(
    db: AsyncSession, ids: list[str]
) -> BulkDeleteProfessorsResult:
    deleted, not_found = await admin_repo.bulk_delete_professors(db, ids)
    return BulkDeleteProfessorsResult(deleted=deleted, not_found=not_found)


async def import_professors_csv(db: AsyncSession, content: bytes) -> ImportProfessorsResult:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="No se pudo leer el archivo CSV") from exc

    reader = csv.DictReader(io.StringIO(text))
    created = 0
    errors: list[str] = []

    for row_num, row in enumerate(reader, start=1):
        name = (row.get("nombre") or row.get("name") or "").strip()
        if not name or len(name) < 2:
            errors.append(f"Fila {row_num}: nombre inválido o vacío")
            continue
        if len(name) > 120:
            errors.append(f"Fila {row_num}: nombre demasiado largo (máx. 120 caracteres)")
            continue

        department = (row.get("departamento") or row.get("department") or "").strip() or None
        degree = (row.get("grado") or row.get("degree") or "").strip() or None
        bio = (row.get("bio") or "").strip() or None
        email = (row.get("email") or "").strip() or None

        try:
            await admin_repo.create_professor(
                db, name=name, department=department, degree=degree, bio=bio, email=email
            )
            created += 1
        except Exception as exc:
            errors.append(f"Fila {row_num}: error al crear profesor ({exc})")

    return ImportProfessorsResult(created=created, errors=errors)


# ---------------------------------------------------------------------------
# Cursos
# ---------------------------------------------------------------------------


async def _get_professor_name(db: AsyncSession, professor_id: str | None) -> str | None:
    if professor_id is None:
        return None
    prof = await admin_repo.get_professor_by_id(db, professor_id)
    return prof.name if prof else None


async def _course_to_out(db: AsyncSession, c: Course) -> AdminCourseOut:
    return AdminCourseOut(
        id=c.id,
        code=c.code,
        name=c.name,
        level=c.level,
        prerequisites=c.prerequisites or [],
        professor_id=c.professor_id,
        professor_name=await _get_professor_name(db, c.professor_id),
        syllabus_status="updated" if c.syllabus_uploaded_at is not None else "outdated",
        syllabus_file_name=c.syllabus_file_name,
        syllabus_updated_at=c.syllabus_uploaded_at,
        updated_at=c.updated_at,
    )


async def list_courses(db: AsyncSession) -> list[AdminCourseOut]:
    courses = await admin_repo.list_courses(db)
    return [await _course_to_out(db, c) for c in courses]


async def create_course(db: AsyncSession, payload: CreateAdminCourseRequest) -> AdminCourseOut:
    existing = await admin_repo.get_course_by_code(db, payload.code.upper())
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un curso con ese código",
        )
    c = await admin_repo.create_course(
        db,
        code=payload.code.upper(),
        name=payload.name,
        level=payload.level,
        prerequisites=payload.prerequisites,
        professor_id=payload.professor_id,
    )
    return await _course_to_out(db, c)


async def update_course(
    db: AsyncSession, course_id: str, payload: UpdateAdminCourseRequest
) -> AdminCourseOut:
    existing = await admin_repo.get_course_by_code(db, payload.code.upper())
    if existing is not None and existing.id != course_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un curso con ese código",
        )
    c = await admin_repo.update_course(
        db,
        course_id,
        code=payload.code.upper(),
        name=payload.name,
        level=payload.level,
        prerequisites=payload.prerequisites,
        professor_id=payload.professor_id,
    )
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso no encontrado")
    return await _course_to_out(db, c)


async def delete_course(db: AsyncSession, course_id: str) -> None:
    found = await admin_repo.delete_course(db, course_id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso no encontrado")


# ---------------------------------------------------------------------------
# Sílabo del curso (US-32) — el archivo se guarda en GCS
# ---------------------------------------------------------------------------

# Tipos permitidos para el sílabo: PDF, DOC y DOCX. Cada MIME mapea a su extensión.
SYLLABUS_CONTENT_TYPES: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
# Mapa inverso extensión → MIME (para el content-type de subida cuando el navegador
# no envía uno confiable).
EXTENSION_CONTENT_TYPES: dict[str, str] = {
    ext: mime for mime, ext in SYLLABUS_CONTENT_TYPES.items()
}
_SYLLABUS_EXTENSIONS = set(EXTENSION_CONTENT_TYPES)
MAX_SYLLABUS_BYTES = 10 * 1024 * 1024  # 10 MB


def _syllabus_extension(filename: str | None, content_type: str | None) -> str:
    """Extensión (.pdf/.doc/.docx) del nombre; cae al content-type. 422 si no es válida."""
    if filename and "." in filename:
        ext = "." + filename.rsplit(".", 1)[1].lower()
        if ext in _SYLLABUS_EXTENSIONS:
            return ext
    if content_type in SYLLABUS_CONTENT_TYPES:
        return SYLLABUS_CONTENT_TYPES[content_type]
    raise HTTPException(
        status_code=422,
        detail="Formato no permitido. Sube un archivo PDF, DOC o DOCX.",
    )


async def set_course_syllabus(
    db: AsyncSession,
    course_id: str,
    *,
    file_name: str,
    content_type: str | None,
    data: bytes,
    uploaded_at: datetime,
) -> AdminCourseOut:
    """Valida y sube el sílabo a GCS, y persiste sus metadatos en el curso."""
    course = await admin_repo.get_course_by_id(db, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso no encontrado")

    extension = _syllabus_extension(file_name, content_type)  # 422 si el tipo no es válido
    if not data:
        raise HTTPException(status_code=422, detail="El archivo está vacío.")
    if len(data) > MAX_SYLLABUS_BYTES:
        raise HTTPException(
            status_code=422, detail="El archivo supera el tamaño máximo de 10 MB."
        )

    default_type = EXTENSION_CONTENT_TYPES[extension]
    try:
        gcs_path = bucket.upload_syllabus(course_id, extension, data, content_type or default_type)
    except Exception as exc:  # pragma: no cover - error de infraestructura GCS
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo subir el sílabo al almacenamiento. Intenta de nuevo.",
        ) from exc

    updated = await admin_repo.set_course_syllabus(
        db, course_id, file_name=file_name, gcs_path=gcs_path, uploaded_at=uploaded_at
    )
    assert updated is not None  # el curso existía arriba
    return await _course_to_out(db, updated)


async def get_course_syllabus(db: AsyncSession, course_id: str) -> tuple[bytes, str, str]:
    """Descarga el sílabo del curso desde GCS → (bytes, content_type, file_name)."""
    course = await admin_repo.get_course_by_id(db, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso no encontrado")
    if not course.syllabus_gcs_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Este curso no tiene sílabo cargado."
        )
    try:
        data, content_type = bucket.download_from_gcs(course.syllabus_gcs_path)
    except Exception as exc:  # pragma: no cover - error de infraestructura GCS
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo descargar el sílabo del almacenamiento.",
        ) from exc
    fallback = f"silabo{_extension_from_path(course.syllabus_gcs_path)}"
    return data, content_type, course.syllabus_file_name or fallback


def _extension_from_path(gcs_path: str) -> str:
    tail = gcs_path.rsplit("/", 1)[-1]
    return "." + tail.rsplit(".", 1)[1] if "." in tail else ""


# ---------------------------------------------------------------------------
# Foto del profesor (US-15 / ficha visual) — el archivo se guarda en GCS
# ---------------------------------------------------------------------------

# Tipos de imagen permitidos para la foto. Cada MIME mapea a su extensión.
PHOTO_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
# Extensión → MIME (para el content-type de subida si el navegador no envía uno).
_PHOTO_EXTENSION_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB


def _photo_extension(filename: str | None, content_type: str | None) -> str:
    """Extensión (.jpg/.png/.webp) del nombre; cae al content-type. 422 si no es válida."""
    if filename and "." in filename:
        ext = "." + filename.rsplit(".", 1)[1].lower()
        if ext in _PHOTO_EXTENSIONS:
            return ".jpg" if ext == ".jpeg" else ext
    if content_type in PHOTO_CONTENT_TYPES:
        return PHOTO_CONTENT_TYPES[content_type]
    raise HTTPException(
        status_code=422,
        detail="Formato no permitido. Sube una imagen JPG, PNG o WEBP.",
    )


async def set_professor_photo(
    db: AsyncSession,
    professor_id: str,
    *,
    file_name: str,
    content_type: str | None,
    data: bytes,
) -> AdminProfessorOut:
    """Valida y sube la foto a GCS, y persiste su ruta en el profesor."""
    professor = await admin_repo.get_professor_by_id(db, professor_id)
    if professor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profesor no encontrado")

    extension = _photo_extension(file_name, content_type)  # 422 si el tipo no es válido
    if not data:
        raise HTTPException(status_code=422, detail="El archivo está vacío.")
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=422, detail="La imagen supera el tamaño máximo de 5 MB."
        )

    default_type = _PHOTO_EXTENSION_TYPES[extension]
    try:
        gcs_path = bucket.upload_professor_photo(
            professor_id, extension, data, content_type or default_type
        )
    except Exception as exc:  # pragma: no cover - error de infraestructura GCS
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo subir la foto al almacenamiento. Intenta de nuevo.",
        ) from exc

    updated = await admin_repo.set_professor_photo(db, professor_id, gcs_path=gcs_path)
    assert updated is not None  # el profesor existía arriba
    review_count = await admin_repo.count_reviews_for_professor(db, professor_id)
    return _prof_to_out(updated, review_count)


async def get_professor_photo(db: AsyncSession, professor_id: str) -> tuple[bytes, str]:
    """Descarga la foto del profesor desde GCS → (bytes, content_type)."""
    professor = await admin_repo.get_professor_by_id(db, professor_id)
    if professor is None or not professor.photo_gcs_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Este profesor no tiene foto cargada."
        )
    try:
        data, content_type = bucket.download_from_gcs(professor.photo_gcs_path)
    except Exception as exc:  # pragma: no cover - error de infraestructura GCS
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo descargar la foto del almacenamiento.",
        ) from exc
    return data, content_type
