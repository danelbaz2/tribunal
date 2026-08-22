"""Starts the server.

Two things happen before the first request: the tables are created if they
are missing, and the hand-picked `MODEL_POOL` is loaded into `pool`. There is
no live check against OpenRouter -- a model that has left the free tier fails
the run that draws it, and the failure names the slot and model, same as any
other call failure.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from . import pool
from .api import cases, runs
from .config import get_settings
from .database import SessionFactory, create_tables
from .models import LlmCall, Run

log = logging.getLogger("tribunal")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    await create_tables()
    await abandon_interrupted_runs()

    if settings.model_pool:
        pool.set_pool(settings.model_pool)
        log.warning(
            "Model pool, pinned by MODEL_POOL: %d models\n    %s",
            len(pool.get_pool()),
            "\n    ".join(pool.get_pool()),
        )
    else:
        log.warning("No MODEL_POOL configured: no pool was resolved and no run can start.")

    yield


async def abandon_interrupted_runs() -> None:
    """Close out runs whose process is gone.

    A run is driven by a background task in this process. Restart the server
    mid-trial and that task dies, leaving the run `running` and its calls
    `writing` for ever -- an interface waiting indefinitely for a stage nobody
    is working on.

    They cannot be resumed: the calls were in flight, and a statement half
    written is not a statement. So they are marked `failed`, which is what they
    are, and the row says why rather than leaving a mystery in the table.

    Two states, treated differently, because they mean different things:

    * `writing` is a claim that a model is answering right now. After a restart
      that is false, so it is corrected.
    * `waiting` is a claim that the slot never got the floor. That stays true,
      and on a failed run it is worth keeping -- which slots never ran is part
      of what happened.
    """
    async with SessionFactory() as session:
        interrupted = (
            await session.execute(select(Run).where(Run.status == "running"))
        ).scalars().all()

        for run in interrupted:
            run.status = "failed"
            run.finished_at = datetime.now(timezone.utc)

        # Every stale `writing` row, on those runs and on any earlier run left
        # mid-flight by a previous restart.
        stale = (
            await session.execute(
                select(LlmCall).where(
                    LlmCall.status == "writing",
                    LlmCall.run_id.in_(select(Run.id).where(Run.status != "running")),
                )
            )
        ).scalars().all()

        for call in stale:
            call.status = "failed"
            call.error = (
                "The server restarted while this call was in flight. "
                "A run cannot be resumed; convene again."
            )

        if interrupted or stale:
            await session.commit()
            log.warning(
                "Startup: %d interrupted run(s) marked failed, %d stale call(s) closed.",
                len(interrupted),
                len(stale),
            )


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


@app.get("/api/health")
async def health() -> dict[str, object]:
    """Says what bench the next run would draw from."""
    settings = get_settings()
    try:
        models = pool.get_pool()
    except pool.PoolTooSmall:
        models = ()

    return {
        "status": "ok",
        "has_api_key": bool(settings.openrouter_api_key),
        "pool_size": len(models),
        "pool": list(models),
    }
