"""Settings and the model pool.

The two secrets live in `.env` (see `.env.example`). Everything else here is a
decision that belongs in one place because both situations must draw on it
identically -- a per-model tweak makes Situation A and Situation B
non-comparable.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# The pool of free OpenRouter model identifiers. It must hold at least 7
# entries (SPECIFICATION.md Part 3).
#
# Both situations draw from this one pool: Situation A takes 1 model and seats
# it seven times, Situation B takes 7 distinct models. Adding to the pool, or
# admitting a paid model, changes what the comparison measures -- that is a
# decision for a human, not a convenience for a failing run.
DEFAULT_MODEL_POOL: tuple[str, ...] = (
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "google/gemma-2-27b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "deepseek/deepseek-r1:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "microsoft/phi-4-reasoning:free",
)


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

    model_pool: tuple[str, ...] = DEFAULT_MODEL_POOL

    #: Validate the pool against OpenRouter at startup, so a model that has
    #: disappeared from the free tier fails with a clear message rather than
    #: mid-trial (pitfall 7). Off when there is no key, and in tests.
    validate_pool_on_startup: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
