from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.domains.auth.router import router as auth_router
from app.domains.projects.router import router as projects_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
