from fastapi import APIRouter

from app.api.v1 import (
    auth, calculators, cds, clinic_admin, commerce, dashboard, diagnoses, labs, medications,
    observations, operations, patients, platform, prescriptions, specialty, suggestions, visits,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(patients.router)
api_router.include_router(visits.router)
api_router.include_router(prescriptions.router)
api_router.include_router(medications.router)
api_router.include_router(diagnoses.router)
api_router.include_router(labs.router)
api_router.include_router(observations.router)
api_router.include_router(specialty.router)
api_router.include_router(calculators.router)
api_router.include_router(cds.router)
api_router.include_router(operations.router)
api_router.include_router(commerce.router)
api_router.include_router(clinic_admin.router)
api_router.include_router(suggestions.router)
api_router.include_router(platform.router)
