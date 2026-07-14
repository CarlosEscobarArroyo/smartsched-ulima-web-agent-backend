from fastapi import APIRouter

from app.domains.admin.router import router as admin_router
from app.domains.auth.router import router as auth_router
from app.domains.chat.router import router as chat_router
from app.domains.fichas.router import router as fichas_router
from app.domains.professors.router import router as professors_router
from app.domains.schedules.router import router as schedules_router
from app.domains.silabos.router import router as silabos_router
from app.domains.support.router import router as support_router
from app.health.router import router as health_router
from app.integrations.bucket.router import router as upload_router
from app.integrations.ocr.router import router as ocr_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(professors_router)
api_router.include_router(chat_router)
api_router.include_router(fichas_router)
api_router.include_router(upload_router)
api_router.include_router(schedules_router)
api_router.include_router(ocr_router)
api_router.include_router(support_router)
api_router.include_router(silabos_router)
