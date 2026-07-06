"""Flowea CMMS API — application entrypoint."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.routers import auth, checklists, dashboard, equipment, media, records, users

settings = get_settings()

# On serverless platforms (e.g. Vercel) opening a DB connection during the frozen
# startup lifespan is unreliable, so we skip it there and initialise once via
# POST /admin/init-db instead. On normal servers/containers it runs at startup.
IS_SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


async def _setup_database():
    await init_db()
    if settings.seed_demo:
        from app.seed import seed
        async with SessionLocal() as db:
            await seed(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not IS_SERVERLESS:
        await _setup_database()
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


@app.post("/admin/init-db", tags=["meta"])
async def admin_init_db(token: str = ""):
    """One-time database setup for serverless hosts (create tables + optional demo seed).

    Protected by the SETUP_TOKEN env var. Call once after deploying to Vercel:
    open /docs, run this endpoint with your token, then you're ready to log in.
    """
    if not settings.setup_token or token != settings.setup_token:
        raise HTTPException(status_code=403, detail="Missing or invalid setup token")
    try:
        await _setup_database()
    except Exception as e:  # surface the real reason instead of a generic 500
        raise HTTPException(status_code=500, detail=f"DB init failed: {type(e).__name__}: {e}")
    return {"status": "initialized", "seeded": settings.seed_demo}


# Serve the web UI at the root path (same origin as the API → no CORS needed)
_WEB_INDEX = os.path.join(os.path.dirname(__file__), "web", "index.html")


@app.get("/", include_in_schema=False)
async def web_ui():
    return FileResponse(_WEB_INDEX)
