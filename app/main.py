from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import settings
from app.services.context import context_registry
from app.api.v1.router import router
from app.api.v1.middleware.exception_handler import cv_optimizer_exception_handler
from app.core.exceptions import CVOptimizerError
import structlog

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create shared Redis pool — injected into routes via app.state.redis
    app.state.redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    log.info("startup.redis.ready")

    # Startup: load persisted FAISS index from disk (skips rebuild on every restart)
    if context_registry.faiss:
        loaded = await context_registry.faiss.load_persisted()
        if loaded:
            log.info("startup.faiss.loaded_from_disk")
        else:
            log.warning(
                "startup.faiss.no_index_found",
                hint="Call POST /api/v1/admin/faiss/build to build",
            )

    yield

    # Shutdown: close Redis pool cleanly
    await app.state.redis.close()
    log.info("shutdown.redis.closed")


app = FastAPI(title="CV Optimizer", lifespan=lifespan)

# CORS — restrict credentials in production by setting allowed_origins explicitly
_allow_origins = ["*"]
if settings.allowed_origins:
    _allow_origins = settings.allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=bool(settings.allowed_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler
app.add_exception_handler(CVOptimizerError, cv_optimizer_exception_handler)

# Router
app.include_router(router, prefix="/api/v1")
