from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.main import api_router
from app.core.config import get_settings
from app.core.db import init_db
from app.core.ffmpeg import ensure_ffmpeg_on_path
from app.services.pipeline import start_worker, stop_worker


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
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

    @application.middleware("http")
    async def never_cache_the_shell(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """The SPA entry point must not be cached, or a rebuilt frontend stays invisible.

        Hashed assets are safe to cache; index.html is not, and during development the same file
        name keeps being rewritten by every build.
        """
        response = await call_next(request)
        path = request.url.path
        if path in ("/", "") or path.endswith(".html"):
            response.headers["Cache-Control"] = "no-store"
        return response

    application.include_router(api_router, prefix="/api")
    web_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if (web_dist / "index.html").exists():
        application.mount("/", StaticFiles(directory=str(web_dist), html=True), name="frontend")
    return application


app = create_app()
