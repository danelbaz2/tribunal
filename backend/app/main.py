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

from .api import cases, comparisons, runs
from .config import get_settings
from .database import create_tables

log = logging.getLogger("tribunal")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    await create_tables()

    if settings.validate_pool_on_startup and settings.openrouter_api_key:
        from .ai.openrouter import OpenRouterClient, OpenRouterError

        try:
            async with OpenRouterClient(settings) as client:
                await client.validate_pool(settings.model_pool)
        except OpenRouterError as error:
            # Loud, and at startup. Not a warning to be scrolled past.
            raise RuntimeError(str(error)) from error
    elif not settings.openrouter_api_key:
        log.warning("No OPENROUTER_API_KEY set: the pool was not validated and no run can start.")

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
    settings = get_settings()
    return {
        "status": "ok",
        "pool_size": len(settings.model_pool),
        "has_api_key": bool(settings.openrouter_api_key),
    }
