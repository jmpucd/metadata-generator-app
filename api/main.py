"""
api/main.py — FastAPI application entry point.

Run with:
    uvicorn api.main:app --port 8000 --reload

During development the SvelteKit dev server runs separately on port 5173
and proxies /api/* here.  In production, build the SvelteKit app and
uncomment the StaticFiles mount at the bottom to serve everything from
one process.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import collections, images, metadata, status, revise, export

app = FastAPI(title="Metadata Review API", version="1.0.0")

# Allow the SvelteKit dev server (port 5173) and any localhost origin to
# call the API without CORS errors during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(collections.router, prefix="/api", tags=["collections"])
app.include_router(images.router,      prefix="/api", tags=["images"])
app.include_router(metadata.router,    prefix="/api", tags=["metadata"])
app.include_router(status.router,      prefix="/api", tags=["status"])
app.include_router(revise.router,      prefix="/api", tags=["revise"])
app.include_router(export.router,      prefix="/api", tags=["export"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_ui = Path(__file__).parent.parent / "ui" / "build"

if _ui.exists():
    # Serve hashed immutable assets directly
    app.mount("/_app", StaticFiles(directory=_ui / "_app"), name="assets")

    # SPA catch-all: serve real files if they exist, otherwise index.html
    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        target = _ui / full_path
        if target.is_file():
            return FileResponse(target)
        return FileResponse(_ui / "index.html")
