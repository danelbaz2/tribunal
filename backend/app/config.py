"""Settings and the model pool.

The two secrets live in `.env` (see `.env.example`). Everything else here is a
decision that belongs in one place because every slot must draw on it
identically -- a per-model tweak makes one slot a different experiment from
the rest.

`MODEL_POOL` is a hand-picked, static list of at least seven free model
identifiers. It is not checked against OpenRouter at startup; a model that has
left the free tier simply fails the run that draws it, same as any other
failure. Update the list by hand when that happens.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    #: Fixed for every call. Free models may ignore it (pitfall 6) -- what was
    #: requested and what the response reported are both recorded, and no
    #: determinism is claimed that was not observed.
    temperature: float = 0.0

    #: One retry, then the call fails and the run with it. Raising this trades
    #: the measurement for a nicer demo; it is not a knob to turn quietly.
    #: Rate limits are not counted here -- see `ai/openrouter.py:complete`.
    max_attempts: int = 2

    #: How hard the model may think before it answers, through OpenRouter's
    #: unified `reasoning` parameter.
    #:
    #: Measured on real runs: **65% of every output token was hidden reasoning**
    #: -- one judgment generated 1712 tokens of which 1485 were thinking, for
    #: 168 visible words in 126 seconds. It was also the cause of the empty
    #: bodies: a model that spends its whole budget reasoning has none left for
    #: an answer.
    #:
    #: **Not "none".** Measured against the live API: gpt-oss-20b answers
    #: `400 Reasoning is mandatory for this endpoint and cannot be disabled` to
    #: "none", to `enabled: false` and to `max_tokens: 0` alike. "low" and
    #: "minimal" are accepted. Note also that `exclude` would only *hide* the
    #: reasoning and buy nothing.
    #:
    #: One value for all seven slots -- the same class of parameter as
    #: temperature and max_tokens. What is not untouched is the quality of the
    #: reasoning, which is a real trade and is why this is one setting rather
    #: than a hidden constant.
    #:
    #: "low" still measured 80-92% of a call's completion budget spent on
    #: hidden reasoning on some models -- the free tier's low-throughput
    #: models spend real wall-clock time on tokens nobody reads. "minimal" is
    #: the floor confirmed to work; below it is "none", which some endpoints
    #: reject outright.
    reasoning_effort: str = "minimal"

    #: Calls in flight at once, inside a stage. Four lets every advocate (and
    #: every judge) hold the floor together -- but the free tier is documented
    #: to answer 429 to a burst of exactly four, so this is the one setting
    #: most likely to need turning back down after a real run is watched.
    #:
    #: This is pacing, not method. It does not change what any call is sent.
    #: Isolation is untouched: no advocate reads another whether they write at
    #: once or in turn.
    max_concurrent_calls: int = 4

    #: What to wait when a 429 arrives without a `Retry-After` header.
    rate_limit_pause_seconds: float = 20.0

    #: Total time one call may spend waiting out rate limits before it fails.
    rate_limit_max_wait_seconds: float = 180.0

    #: How long one call may take to answer before it is treated as a failure
    #: and retried once. A run is only as fast as its slowest seat, so this
    #: bounds that -- a model that cannot answer inside it fails its call
    #: rather than holding up the whole trial. 30s measured too tight: the
    #: free tier's own latency swings run-to-run for the *same* model (shared
    #: capacity, provider routing, non-deterministic reasoning depth even at
    #: temperature 0), so 30s failed calls that a retry alone would have
    #: cleared.
    request_timeout_seconds: float = 60.0

    #: The target length named in the statement prompt. Never enforced, never
    #: truncated -- the actual word count is recorded instead.
    statement_target_words: int = 300

    #: Room to finish, asked for explicitly on every call. A provider default
    #: is silent and differs between providers, which would make statement
    #: length a measure of the gateway rather than of the model. One value for
    #: all seven slots: a per-model figure would be a second variable, and
    #: word count is a reported finding (criterion 18). A model cut off at
    #: this limit fails its call rather than storing half an argument -- 2048
    #: measured too tight for a model that reasons heavily even at "low"
    #: effort: a real run showed 80-92% of the completion budget spent on
    #: hidden reasoning before any visible answer, with two of four calls
    #: exhausting the budget entirely (one cut off, one empty).
    max_response_tokens: int = 4096

    #: Below this, what came back is not a statement -- it is a refusal, a
    #: classification, or a preamble. Not a length rule: the prompt still
    #: enforces nothing and truncates nothing. This is the floor under which
    #: no argument exists to be judged.
    min_statement_words: int = 60

    #: The hand-picked bench: at least seven free model identifiers, best
    #: first. Set in `.env`.
    model_pool: tuple[str, ...] = ()


@lru_cache
def get_settings() -> Settings:
    return Settings()
