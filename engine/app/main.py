from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.main import api_router
from app.core.config import get_settings
from app.core.db import init_db
from app.core.ffmpeg import ensure_ffmpeg_on_path
from app.services.pipeline import start_worker, stop_worker


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_ffmpeg_on_path()
    init_db()
    start_worker()
    yield
    stop_worker()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin, settings.frontend_origin_alt],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix="/api")
    web_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if (web_dist / "index.html").exists():
        application.mount("/", StaticFiles(directory=str(web_dist), html=True), name="web")
    return application


app = create_app()
