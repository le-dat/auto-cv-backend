from fastapi import APIRouter
from app.api.v1.routes import health, jobs, admin

router = APIRouter()

router.include_router(health.router)
router.include_router(jobs.router)
router.include_router(admin.admin_router)
