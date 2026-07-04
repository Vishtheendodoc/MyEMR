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


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_phase2_columns()
    if settings.seed_on_startup:
        db = SessionLocal()
        try:
            seed_if_empty(db)
            seed_extensions_if_missing(db)
            seed_clinic_medications(db)
        finally:
            db.close()
    yield


app = FastAPI(
    title="Endocrinology EMR API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
