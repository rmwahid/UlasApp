from fastapi import APIRouter

from app.api.routes import jobs, settings

api_router = APIRouter()


@api_router.get("/health")
def health() -> dict:
    return {"status": "ok"}


api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
