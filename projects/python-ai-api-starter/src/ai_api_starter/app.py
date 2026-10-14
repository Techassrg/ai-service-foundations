"""Small inference gateway with explicit bounds and provider failure mapping."""

import json
import os
import re
import urllib.error
import urllib.request
import uuid
from typing import Protocol

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

MAX_OUTPUT_CHARS = 20_000
MODEL_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")


class CompletionRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    model: str = Field(default="llama3.2:3b", min_length=1, max_length=80)


class CompletionResponse(BaseModel):
    text: str
    model: str
    request_id: str


class ProviderError(Exception):
    """A safe error that does not expose provider details to clients."""


class CompletionBackend(Protocol):
    def complete(self, prompt: str, model: str) -> str: ...


class OllamaBackend:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(self, prompt: str, model: str) -> str:
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        request = urllib.request.Request(
            self.base_url + "/api/generate", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read(1_000_000 + 1)
            if len(body) > 1_000_000:
                raise ProviderError("Provider response too large")
            data = json.loads(body)
            result = data["response"]
            if not isinstance(result, str):
                raise ValueError("Provider response must be text")
            return result
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise ProviderError("Local model unavailable or returned an invalid response") from exc


def create_app(backend: CompletionBackend | None = None) -> FastAPI:
    app = FastAPI(title="Python AI API Starter", version="0.1.0")
    provider = backend or OllamaBackend(
        os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "20")),
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", supplied) else uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    @app.exception_handler(ProviderError)
    async def provider_error_handler(request: Request, exc: ProviderError):
        return JSONResponse(
            status_code=503,
            content={"error": "provider_unavailable", "request_id": request.state.request_id},
        )

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.post("/v1/completions", response_model=CompletionResponse)
    def complete(payload: CompletionRequest, request: Request):
        if not payload.prompt.strip():
            return JSONResponse(status_code=422, content={"error": "empty_prompt"})
        if not MODEL_PATTERN.fullmatch(payload.model):
            return JSONResponse(status_code=422, content={"error": "invalid_model"})
        result = provider.complete(payload.prompt, payload.model)
        if len(result) > MAX_OUTPUT_CHARS:
            raise ProviderError("Provider response too large")
        return CompletionResponse(text=result, model=payload.model, request_id=request.state.request_id)

    return app


app = create_app()
