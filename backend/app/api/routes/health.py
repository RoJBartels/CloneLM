"""Health endpoint. Reports app + database liveness. Always returns 200 (even
when the DB is down) so the frontend status indicator can render a state."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.domain.models import HealthStatus
from app.infrastructure.persistence.db import get_engine
from app.shared.logging import get_logger

log = get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    db_status = "ok"
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        log.warning("DB health check failed: %s", exc)
        db_status = "down"
    return HealthStatus(status="ok", db=db_status, version=__version__)
