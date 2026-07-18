from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.app.config import get_settings
from api.app.logging import configure_logging
from api.app.routers.admin import router as admin_router
from api.app.routers.candidates import router as candidates_router
from api.app.routers.dependencies import router as dependencies_router
from api.app.routers.health import router as health_router
from api.app.routers.me import router as me_router
from api.app.routers.recordings import router as recordings_router

settings = get_settings()
configure_logging(settings, "api")
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("api_started", environment=settings.environment)
    yield
    logger.info("api_stopped")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/api/docs" if settings.environment != "production" else None,
    openapi_url="/api/openapi.json" if settings.environment != "production" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
                "retryable": exc.status_code >= 500,
            }
        },
        headers=exc.headers,
    )


app.include_router(health_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(dependencies_router, prefix="/api")
app.include_router(me_router, prefix="/api")
app.include_router(candidates_router, prefix="/api")
app.include_router(recordings_router, prefix="/api")
