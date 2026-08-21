"""Starts the server.

Two things happen before the first request: the tables are created if they are
missing, and the model pool is checked against OpenRouter. The second is
deliberate -- OpenRouter's free tier changes without notice, and a model that
has vanished should stop the server with a clear message rather than surface
three minutes into a deliberation as a failed run.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import pool
from .api import cases, comparisons, runs
from .config import get_settings
from .database import create_tables

log = logging.getLogger("tribunal")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    await create_tables()

    if settings.resolve_pool_on_startup and settings.openrouter_api_key:
        from .ai.openrouter import OpenRouterClient, OpenRouterError

        try:
            async with OpenRouterClient(settings) as client:
                if settings.model_pool:
                    # Pinned by hand: check it is still real, and use it as given.
                    await client.validate_pool(settings.model_pool)
                    models = tuple(settings.model_pool)
                    source = "pinned by MODEL_POOL"
                else:
                    models = await client.discover_free_pool(settings.min_context_length)
                    source = "discovered from the live free tier"
        except OpenRouterError as error:
            # Loud, and at startup. Not a warning to be scrolled past.
            raise RuntimeError(str(error)) from error

        pool.set_pool(models)
        log.warning(
            "Model pool, %s: %d models\n    %s",
            source,
            len(models),
            "\n    ".join(models),
        )
    elif not settings.openrouter_api_key:
        log.warning("No OPENROUTER_API_KEY set: no pool was resolved and no run can start.")

    yield


app = FastAPI(title="LLM Tribunal", lifespan=lifespan)

# The frontend proxies /api in development, so this matters only when the two
# are served from different origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases.router)
app.include_router(runs.router)
app.include_router(comparisons.router)


@app.get("/api/health")
async def health() -> dict[str, object]:
    """Says what bench the next run would draw from, and where it came from."""
    settings = get_settings()
    try:
        models = pool.get_pool()
    except pool.PoolTooSmall:
        models = ()

    return {
        "status": "ok",
        "has_api_key": bool(settings.openrouter_api_key),
        "pool_source": "pinned" if settings.model_pool else "discovered",
        "pool_size": len(models),
        "pool": list(models),
    }
