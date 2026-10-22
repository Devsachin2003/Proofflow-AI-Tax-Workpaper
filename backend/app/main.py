import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_core, routes_evidence, routes_workspace
from app.core.config import get_settings
from app.core.errors import install_handlers

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ProofFlow AI", version="0.1.0",
                  description="Evidence-backed tax workpaper API (demo identity via X-Demo-User header).")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Demo-User"],
    )
    install_handlers(app)
    for r in (routes_core.router, routes_evidence.router, routes_workspace.router):
        app.include_router(r)
    return app


app = create_app()
