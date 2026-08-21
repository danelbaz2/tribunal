"""Settings and the model pool.

The two secrets live in `.env` (see `.env.example`). Everything else here is a
decision that belongs in one place because both situations must draw on it
identically -- a per-model tweak makes Situation A and Situation B
non-comparable.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# The pool is not a constant any more.
#
# It was: seven free model identifiers written down by hand. Every one of them
# had left OpenRouter's free tier by August 2026, and the startup check --
# working exactly as intended -- refused to start the server. A written list
# decays; the tier does not hold still (pitfall 7).
#
# So the pool is **discovered at startup** from what OpenRouter is offering
# today, by the mechanical rules in `ai/openrouter.py:select_free_models`. No
# model is named anywhere in this project, because a hand-picked bench is a
# hand-picked result.
#
# `MODEL_POOL` pins it instead, as a deliberate act -- to reproduce an old run,
# or to hold the bench still across a comparison. A pinned pool is validated
# against OpenRouter at startup and fails loudly if a member has gone.


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        # `model_pool` is a pool of models, not a pydantic model attribute.
        protected_namespaces=(),
    )

    openrouter_api_key: str = ""
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tribunal"

    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    #: Fixed for every call in both situations. Free models may ignore it
    #: (pitfall 6) -- what was requested and what the response reported are
    #: both recorded, and no determinism is claimed that was not observed.
    temperature: float = 0.0

    #: One retry, then the call fails and the run with it. Raising this trades
    #: the measurement for a nicer demo; it is not a knob to turn quietly.
    max_attempts: int = 2

    request_timeout_seconds: float = 180.0

    #: The target length named in the statement prompt. Never enforced, never
    #: truncated -- the actual word count is recorded instead.
    statement_target_words: int = 300

    #: Empty means "discover from the live free tier". Set MODEL_POOL to pin it.
    model_pool: tuple[str, ...] = ()

    #: A judge is sent the charge file and all four statements. A model that
    #: cannot hold that much fails stage 2 every time, so it is not seated.
    min_context_length: int = 16384

    #: Resolve the pool at startup, so a tier that has moved fails with a clear
    #: message rather than mid-trial (pitfall 7). Off when there is no key, and
    #: in tests.
    resolve_pool_on_startup: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
