"""Does DATABASE_URL work? Answer in one command.

Connects, reports what answered, and says what is wrong when nothing does.
Written because the alternative is starting uvicorn and reading eighty lines of
driver traceback whose last line is the only one that matters.

    cd backend && .venv/Scripts/python scripts/check_database.py

Never prints the password.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.config import get_settings  # noqa: E402


def describe(url_string: str) -> str:
    return make_url(url_string).render_as_string(hide_password=True)


def advise(url) -> list[str]:
    """Warn about the two Supabase shapes that fail in ways hard to read."""
    notes: list[str] = []
    host = (url.host or "").lower()

    if url.drivername != "postgresql+asyncpg":
        notes.append(
            f"The driver is {url.drivername!r}. This project needs "
            "'postgresql+asyncpg://' -- SQLAlchemy is running async."
        )

    if "supabase" in host or "pooler" in host:
        if url.port == 6543:
            notes.append(
                "Port 6543 is Supabase's TRANSACTION pooler. It does not support the "
                "prepared statements asyncpg uses, and fails later with "
                "'prepared statement __asyncpg_stmt_N__ already exists'. Use the "
                "SESSION pooler on port 5432 instead."
            )
        if "sslmode" in (url.query or {}):
            notes.append(
                "Drop 'sslmode' from the URL: asyncpg does not accept it and raises "
                "\"connect() got an unexpected keyword argument 'sslmode'\". "
                "Supabase requires TLS and asyncpg negotiates it anyway."
            )
        if url.username and "." not in url.username and "pooler" in host:
            notes.append(
                f"The pooler username is usually 'postgres.<project-ref>', not "
                f"{url.username!r}. Copy it from the dashboard rather than typing it."
            )

    return notes


async def main() -> int:
    settings = get_settings()
    url = make_url(settings.database_url)

    print(f"DATABASE_URL -> {describe(settings.database_url)}")
    print(f"  driver {url.drivername}   host {url.host}   port {url.port}   db {url.database}")

    for note in advise(url):
        print(f"\n  ! {note}")

    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as connection:
            version = (await connection.execute(text("select version()"))).scalar_one()
            tables = (
                await connection.execute(
                    text(
                        "select table_name from information_schema.tables "
                        "where table_schema = 'public' order by table_name"
                    )
                )
            ).scalars().all()
    except Exception as error:
        last = str(error).strip().splitlines()[-1]
        print(f"\nFAILED: {last}")
        print(
            "\nIf that says 'connection refused' or 'connect call failed', nothing is "
            "listening at that address.\nIf it says authentication or password, the "
            "credentials are wrong -- a password with @ : / or ? in it must be "
            "percent-encoded in the URL."
        )
        return 1
    finally:
        await engine.dispose()

    print(f"\nOK  {version.split(',')[0]}")
    print("tables in public: " + (", ".join(tables) if tables else "none yet"))
    if not tables:
        print("  (the four tables are created when the server starts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
