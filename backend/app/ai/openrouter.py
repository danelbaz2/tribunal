"""The single door to every model.

Credentials, transport retries, timing and cost live here and nowhere else. No
other module may open an HTTP client -- if a second one appears, the recorded
cost and duration stop meaning one thing.

Two different retries exist in this project, and confusing them weakens a rule:

* the **transport retry**, here: a timeout, a 5xx or an empty body is retried
  once, because nothing was said and asking again is the same question;
* the **format retry**, in `tribunal/judges.py`: a judge that answered but not
  in the required form is asked once more with the form restated. That is a
  second call with a different prompt, not a repeat of this one.

Either one exhausting itself fails the call, and a failed call fails the run.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import Settings, get_settings


class OpenRouterError(RuntimeError):
    """A call that did not produce a usable body. Always a failed call."""


@dataclass(frozen=True)
class ModelResponse:
    """One completed call, with everything the row needs recorded on it."""

    model: str
    text: str
    duration_ms: int
    cost: float
    temperature_requested: float
    #: What the response says it used, when it says anything. Free models
    #: frequently ignore temperature; a null here is the honest answer, not a
    #: reason to claim the requested value was honoured.
    temperature_reported: float | None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def words(self) -> int:
        return len(self.text.split())


#: Called with the text so far, each time more of it arrives. Used by stage 1
#: so the courtroom fills in front of the reader.
ChunkHandler = Callable[[str], Awaitable[None]]


class OpenRouterClient:
    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self._settings = settings or get_settings()
        self._client = client

    async def __aenter__(self) -> "OpenRouterClient":
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.openrouter_base_url,
                timeout=httpx.Timeout(self._settings.request_timeout_seconds),
                headers=self._headers(),
            )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict[str, str]:
        if not self._settings.openrouter_api_key:
            raise OpenRouterError(
                "No OPENROUTER_API_KEY. Copy .env.example to .env and set it."
            )
        return {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "X-Title": "LLM Tribunal",
        }

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise OpenRouterError("Use the client inside `async with OpenRouterClient()`.")
        return self._client

    # ── the one call ──────────────────────────────────────────────────────

    async def complete(
        self,
        model: str,
        prompt: str,
        *,
        on_chunk: ChunkHandler | None = None,
    ) -> ModelResponse:
        """Send one prompt to one model and measure what came back.

        Retried once on a transport failure. A second failure raises, and the
        caller fails the call rather than inventing a body for it.
        """
        last_error: Exception | None = None

        for attempt in range(1, self._settings.max_attempts + 1):
            started = time.perf_counter()
            try:
                if on_chunk is not None:
                    return await self._stream(model, prompt, started, on_chunk)
                return await self._request(model, prompt, started)
            except (httpx.HTTPError, OpenRouterError, json.JSONDecodeError) as error:
                last_error = error
                if attempt < self._settings.max_attempts:
                    await asyncio.sleep(1.0)

        raise OpenRouterError(f"{model}: {last_error}") from last_error

    def _body(self, model: str, prompt: str, *, stream: bool) -> dict[str, Any]:
        return {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self._settings.temperature,
            "stream": stream,
            # Ask for the cost back with the response, so cost is measured
            # rather than assumed to be zero because the tier says so.
            "usage": {"include": True},
        }

    async def _request(self, model: str, prompt: str, started: float) -> ModelResponse:
        response = await self._http.post(
            "/chat/completions", json=self._body(model, prompt, stream=False)
        )
        response.raise_for_status()
        payload = response.json()
        text = _content_of(payload)
        if not text.strip():
            # An empty body is a failed call, never an empty statement and
            # never an empty verdict.
            raise OpenRouterError(f"{model} returned an empty body")
        return self._response(model, text, started, payload)

    async def _stream(
        self, model: str, prompt: str, started: float, on_chunk: ChunkHandler
    ) -> ModelResponse:
        text = ""
        payload: dict[str, Any] = {}

        async with self._http.stream(
            "POST", "/chat/completions", json=self._body(model, prompt, stream=True)
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[len("data: ") :].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                payload = chunk
                delta = _delta_of(chunk)
                if delta:
                    text += delta
                    await on_chunk(text)

        if not text.strip():
            raise OpenRouterError(f"{model} streamed an empty body")
        return self._response(model, text, started, payload)

    def _response(
        self, model: str, text: str, started: float, payload: dict[str, Any]
    ) -> ModelResponse:
        usage = payload.get("usage") or {}
        return ModelResponse(
            model=model,
            text=text,
            duration_ms=int((time.perf_counter() - started) * 1000),
            cost=float(usage.get("cost") or 0.0),
            temperature_requested=self._settings.temperature,
            temperature_reported=_reported_temperature(payload),
            raw=payload,
        )

    # ── the pool ──────────────────────────────────────────────────────────

    async def available_models(self) -> set[str]:
        response = await self._http.get("/models")
        response.raise_for_status()
        return {entry["id"] for entry in response.json().get("data", [])}

    async def validate_pool(self, pool: tuple[str, ...] | list[str]) -> None:
        """Fail at startup, not mid-trial.

        OpenRouter's free tier changes without notice. A model that has
        vanished should stop the server with a clear message rather than
        surface as a failed run three minutes into a deliberation.
        """
        available = await self.available_models()
        missing = sorted(set(pool) - available)
        if missing:
            raise OpenRouterError(
                "These pool models are not available on OpenRouter any more: "
                + ", ".join(missing)
                + ". Correct the pool in app/config.py before running a trial."
            )


def _content_of(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return message.get("content") or ""


def _delta_of(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("delta") or {}).get("content") or ""


def _reported_temperature(payload: dict[str, Any]) -> float | None:
    value = payload.get("temperature")
    return float(value) if isinstance(value, (int, float)) else None
