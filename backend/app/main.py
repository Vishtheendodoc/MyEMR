import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.models import Base
from app.services.db_migrate import ensure_phase2_columns
from app.services.seed_data import seed_if_empty
from app.services.seed_extensions import seed_extensions_if_missing
from app.services.seed_medications import seed_clinic_medications
from app.services.seed_staff import seed_staff_users
from app.services.platform_seed import seed_platform

logger = logging.getLogger("endo_emr")


async def _reminder_scheduler():
    """Hourly job: appointment reminders 1 day prior (Friday for Monday visits)."""
    await asyncio.sleep(15)
    while True:
        try:
            from app.services.reminder_service import process_due_auto_reminders
            db = SessionLocal()
            try:
                result = process_due_auto_reminders(db)
                if result.get("sent") or result.get("queued"):
                    logger.info(
                        "Auto reminders: sent=%s queued=%s failed=%s skipped=%s",
                        result.get("sent"), result.get("queued"), result.get("failed"), result.get("skipped"),
                    )
            finally:
                db.close()
        except Exception:  # noqa: BLE001
            logger.exception("Auto reminder job failed")
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.uses_default_jwt_secret:
        if settings.is_production:
            raise RuntimeError("JWT_SECRET is still the placeholder value. Set a long random secret before starting in production.")
        logger.warning("JWT_SECRET is the placeholder value. Fine on one local PC, never on a shared or online server.")
    Base.metadata.create_all(bind=engine)
    ensure_phase2_columns()
    db = SessionLocal()
    try:
        from app.services.specialty_templates import reflect_stored_visit_labs
        reflect_stored_visit_labs(db)
    except Exception:
        logger.exception("Could not copy visit results onto the lab list")
        db.rollback()
    finally:
        db.close()
    if settings.is_production:
        # No demo doctor and no shared-password desk accounts on a live server.
        db = SessionLocal()
        try:
            seed_platform(db)
        finally:
            db.close()
    elif settings.seed_on_startup:
        db = SessionLocal()
        try:
            seed_if_empty(db)
            seed_extensions_if_missing(db)
            seed_clinic_medications(db)
            seed_staff_users(db)
            seed_platform(db)
        finally:
            db.close()
    else:
        db = SessionLocal()
        try:
            seed_staff_users(db)
            seed_platform(db)
        finally:
            db.close()
    task = asyncio.create_task(_reminder_scheduler())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Endocrinology EMR API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_failed_requests(request, call_next):
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled API error on %s", request.url.path)
        raise
    if response.status_code >= 500:
        logger.error("API %s %s returned %s", request.method, request.url.path, response.status_code)
    return response

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
