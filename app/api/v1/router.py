from fastapi import APIRouter

from app.domains.admin.router import router as admin_router
from app.domains.auth.router import router as auth_router
from app.domains.chat.router import router as chat_router
from app.domains.schedules.router import router as schedules_router
from app.health.router import router as health_router
from app.integrations.bucket.router import router as upload_router
from app.integrations.ocr.router import router as ocr_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(chat_router)
api_router.include_router(upload_router)
api_router.include_router(schedules_router)
api_router.include_router(ocr_router)
