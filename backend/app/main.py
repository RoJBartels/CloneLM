"""FastAPI application factory + router registration.

Each feature module exposes a ``router``; the factory aggregates them. This and
``api/deps.py`` are the only shared, additive touch points across tracks — keep
edits here small (one ``include_router`` line per module)."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import (
    audio,
    chat,
    health,
    notebooks,
    notes,
    settings as settings_routes,
    sources,
    studio,
)
from app.config import get_settings
from app.shared.errors import (
    InsufficientContextError,
    NotFoundError,
    UnsupportedSourceError,
    ValidationError,
)
from app.shared.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="CloneLM API",
        version=__version__,
        summary="Faithfulness-first NotebookLM clone — grounded, cited Q&A over your sources.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routers (one line per feature module) ---
    app.include_router(health.router)
    app.include_router(notebooks.router)
    app.include_router(sources.router)
    app.include_router(chat.router)
    app.include_router(studio.router)
    app.include_router(notes.router)
    app.include_router(audio.router)
    app.include_router(settings_routes.router)

    _register_error_handlers(app)
    return app


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def _validation(_: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(UnsupportedSourceError)
    async def _unsupported(_: Request, exc: UnsupportedSourceError) -> JSONResponse:
        return JSONResponse(status_code=415, content={"detail": str(exc)})

    @app.exception_handler(InsufficientContextError)
    async def _insufficient(_: Request, exc: InsufficientContextError) -> JSONResponse:
        # Surfaced (not an error to the user) — the faithfulness refusal path.
        return JSONResponse(status_code=200, content={"detail": str(exc), "refused": True})


app = create_app()
