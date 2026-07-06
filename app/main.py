"""Flowea CMMS API — application entrypoint."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.routers import auth, checklists, dashboard, equipment, media, records, users

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    if settings.seed_demo:
        from app.seed import seed
        async with SessionLocal() as db:
            await seed(db)
    yield


app = FastAPI(title="Flowea Maintenance API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth.router, equipment.router, checklists.router, records.router, dashboard.router, media.router, users.router):
    app.include_router(r)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


# Serve the web UI at the root path (same origin as the API → no CORS needed)
_WEB_INDEX = os.path.join(os.path.dirname(__file__), "web", "index.html")


@app.get("/", include_in_schema=False)
async def web_ui():
    return FileResponse(_WEB_INDEX)
