from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import health, redteam, research, ui
from app.core.config import settings
from app.core.logging import logger
from app.memory.postgres_ltm import db_manager
from app.memory.redis_stm import redis_stm

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & shutdown lifespan events."""
    logger.info("Initializing Autonomous AI Research Platform services...")

    # 1. Initialize PostgreSQL & pgvector schema
    try:
        db_initialized = await db_manager.init_db()
        if db_initialized:
            logger.info("PostgreSQL pgvector extension and tables ready.")
        else:
            logger.warning("Running with in-memory / mock database fallback.")
    except Exception as e:
        logger.warning(f"Database bootstrap notice: {e}")

    # 2. Check Redis STM & Streams
    try:
        r = await redis_stm.get_redis()
        if r:
            await r.ping()
            logger.info("Connected to Redis STM & Streams.")
        else:
            logger.info("Redis not configured; utilizing in-memory STM & Streams fallback.")
    except Exception as e:
        logger.warning(f"Redis connection notice: {e}. Utilizing in-memory queue fallback.")

    logger.info("Multi-Agent Research Platform startup sequence completed.")
    yield
    logger.info("Shutting down Multi-Agent Research Platform services...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Multi-Agent AI Research Platform with Bedrock Guardrails, pgvector Semantic Caching, and PyRIT Red Teaming.",
    lifespan=lifespan,
)

# CORS Middleware — strict origin control; never combine allow_origins=["*"] with allow_credentials=True
cors_origins = settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:3000"]
allow_creds = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Assets
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Register API & UI Routers
app.include_router(ui.router)
app.include_router(research.router, prefix=settings.API_V1_STR)
app.include_router(redteam.router, prefix=settings.API_V1_STR)
app.include_router(health.router)
app.include_router(health.router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
