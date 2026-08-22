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
from datetime import datetime
from email.utils import parsedate_to_datetime
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
    #: Why the model stopped. "length" means it was cut off mid-argument --
    #: which is not a shorter statement, it is an incomplete one.
    finish_reason: str | None = None
    #: What it generated, and how much of that was thinking nobody reads.
    #: Recorded because it is the largest single explanation of duration, and
    #: duration is a reported finding (criterion 17).
    tokens: int | None = None
    thinking_tokens: int | None = None
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

        **A 429 is not an attempt.** It is the gateway saying "not now" -- the
        model never saw the prompt and never answered it. Waiting and asking
        again is the same question asked once, so it does not consume the one
        retry a real failure gets. What bounds it instead is a total waiting
        budget: past that, the call fails like any other, and the run with it.
        Keeping the two apart matters, because counting rate limits as failures
        would make a run look worse than it is -- seven models, seven chances
        to be told to wait.
        """
        last_error: Exception | None = None
        waited = 0.0
        attempt = 1

        while attempt <= self._settings.max_attempts:
            started = time.perf_counter()
            try:
                coro = (
                    self._stream(model, prompt, started, on_chunk)
                    if on_chunk is not None
                    else self._request(model, prompt, started)
                )
                try:
                    return await asyncio.wait_for(
                        coro, timeout=self._settings.request_timeout_seconds
                    )
                except TimeoutError as error:
                    # `httpx.Timeout` bounds a single read, not the call: a
                    # model that dribbles bytes resets that clock forever and
                    # never trips it. This is the one deadline that covers the
                    # whole call, start to last byte.
                    raise OpenRouterError(
                        f"{model} did not answer within "
                        f"{self._settings.request_timeout_seconds:.0f}s."
                    ) from error

            except httpx.HTTPStatusError as error:
                if error.response.status_code == 429:
                    delay = _retry_after(error.response, self._settings.rate_limit_pause_seconds)
                    if waited + delay <= self._settings.rate_limit_max_wait_seconds:
                        waited += delay
                        await asyncio.sleep(delay)
                        continue  # deliberately not `attempt += 1`
                    raise OpenRouterError(
                        f"{model}: rate limited, and {waited:.0f}s of waiting was not "
                        "enough. Lower MAX_CONCURRENT_CALLS, or wait for the free "
                        "tier's window to reset."
                    ) from error

                # A 4xx is the gateway refusing the request, and it says why in
                # the body. `raise_for_status()` throws that away, which turned
                # "Reasoning is mandatory for this endpoint" into a bare 400 and
                # cost an afternoon. Asking again cannot help either.
                detail = _error_detail(error.response)
                if 400 <= error.response.status_code < 500:
                    raise OpenRouterError(f"{model}: {detail}") from error
                last_error = OpenRouterError(detail)

            except (httpx.HTTPError, OpenRouterError, json.JSONDecodeError) as error:
                last_error = error

            attempt += 1
            if attempt <= self._settings.max_attempts:
                await asyncio.sleep(1.0)

        raise OpenRouterError(f"{model}: {last_error}") from last_error

    def _body(self, model: str, prompt: str, *, stream: bool) -> dict[str, Any]:
        return {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self._settings.temperature,
            # Asked for explicitly, because a provider default is silent and
            # differs between providers -- which would make statement length a
            # measure of the gateway rather than of the model. One value for
            # all seven slots.
            "max_tokens": self._settings.max_response_tokens,
            # `effort: "none"` prevents the reasoning tokens being generated at
            # all. `exclude` would only hide them and save nothing.
            "reasoning": {"effort": self._settings.reasoning_effort},
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

    @staticmethod
    def _refuse_if_truncated(model: str, finish_reason: str | None) -> None:
        """A cut-off argument is not a short argument.

        Storing it would put half a case in front of three judges and count
        its words as if the model had chosen to stop there. It is a failed
        call, and a failed call fails the run.
        """
        if finish_reason == "length":
            raise OpenRouterError(
                f"{model} was cut off at the token limit mid-argument. Raise "
                "MAX_RESPONSE_TOKENS, or accept that this model cannot finish "
                "a statement."
            )

    async def _stream(
        self, model: str, prompt: str, started: float, on_chunk: ChunkHandler
    ) -> ModelResponse:
        text = ""
        payload: dict[str, Any] = {}

        async with self._http.stream(
            "POST", "/chat/completions", json=self._body(model, prompt, stream=True)
        ) as response:
            if response.is_error:
                # The body must be read before `raise_for_status` -- a
                # streaming response that errors before any chunk is read
                # cannot have its content (the gateway's error message)
                # accessed later, in the caller's handler, without this.
                await response.aread()
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[len("data: ") :].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                delta = _delta_of(chunk)
                # Keep the last chunk that says anything about how it ended:
                # the final one often carries the finish reason and the usage
                # and nothing else.
                if _finish_reason(chunk) or chunk.get("usage") or delta:
                    payload = _merge(payload, chunk)
                if delta:
                    text += delta
                    await on_chunk(text)

        if not text.strip():
            raise OpenRouterError(f"{model} streamed an empty body")
        return self._response(model, text, started, payload)

    def _response(
        self, model: str, text: str, started: float, payload: dict[str, Any]
    ) -> ModelResponse:
        finish_reason = _finish_reason(payload)
        self._refuse_if_truncated(model, finish_reason)
        usage = payload.get("usage") or {}
        return ModelResponse(
            model=model,
            text=text,
            duration_ms=int((time.perf_counter() - started) * 1000),
            cost=float(usage.get("cost") or 0.0),
            temperature_requested=self._settings.temperature,
            temperature_reported=_reported_temperature(payload),
            finish_reason=finish_reason,
            tokens=_int_or_none(usage.get("completion_tokens")),
            thinking_tokens=_int_or_none(
                (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
            ),
            raw=payload,
        )

def _content_of(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return message.get("content") or ""


def _merge(payload: dict[str, Any], chunk: dict[str, Any]) -> dict[str, Any]:
    """Carry forward what a streamed answer says about how it ended.

    Chunks arrive one at a time and the interesting fields are spread across
    them; the last chunk alone is not the whole story.
    """
    merged = dict(payload)
    merged.update({k: v for k, v in chunk.items() if k != "choices"})
    if _finish_reason(chunk):
        merged["choices"] = chunk["choices"]
    elif "choices" not in merged:
        merged["choices"] = chunk.get("choices", [])
    return merged


def _finish_reason(payload: dict[str, Any]) -> str | None:
    choices = payload.get("choices") or []
    if not choices:
        return None
    reason = choices[0].get("finish_reason") or choices[0].get("native_finish_reason")
    return reason if isinstance(reason, str) else None


def _delta_of(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("delta") or {}).get("content") or ""


def _error_detail(response: httpx.Response) -> str:
    """What the gateway actually said, when it said anything."""
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    error = payload.get("error") if isinstance(payload, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    return f"HTTP {response.status_code}: {message}" if message else f"HTTP {response.status_code}"


def _int_or_none(value: object) -> int | None:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _retry_after(response: httpx.Response, default: float) -> float:
    """How long the gateway asked us to wait.

    `Retry-After` is seconds, or an HTTP date. When it says neither, fall back
    to the configured pause rather than guessing something clever.
    """
    header = response.headers.get("retry-after")
    if header:
        try:
            return max(0.0, float(header))
        except ValueError:
            parsed = parsedate_to_datetime(header)
            if parsed is not None:
                return max(0.0, (parsed - datetime.now(parsed.tzinfo)).total_seconds())
    return default


def _reported_temperature(payload: dict[str, Any]) -> float | None:
    value = payload.get("temperature")
    return float(value) if isinstance(value, (int, float)) else None
