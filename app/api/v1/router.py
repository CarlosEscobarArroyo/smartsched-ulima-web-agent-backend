from fastapi import APIRouter

from app.domains.chat.router import router as chat_router
from app.health.router import router as health_router
from app.integrations.bucket.router import router as upload_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(chat_router)
api_router.include_router(upload_router)
