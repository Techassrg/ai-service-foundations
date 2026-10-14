"""Parse incident triage with one corrective retry and a narrow data contract."""

import json
import os
import urllib.error
import urllib.request
from typing import Literal, Protocol

from pydantic import BaseModel, Field, ValidationError


class IncidentTriage(BaseModel):
    severity: Literal["low", "medium", "high", "critical"]
    summary: str = Field(..., min_length=5, max_length=240)
    owner_team: Literal["platform", "payments", "security", "unknown"]
    needs_human_review: bool

    class Config:
        extra = "forbid"


class ModelBackend(Protocol):
    def generate(self, prompt: str) -> str: ...


class TriageError(Exception):
    """The input could not be safely converted into the required contract."""


class OllamaBackend:
    def __init__(self, model: str = "llama3.2:3b", base_url: str = "http://127.0.0.1:11434", timeout: float = 20.0):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        payload = json.dumps({"model": self.model, "prompt": prompt, "stream": False, "format": "json"}).encode()
        request = urllib.request.Request(
            self.base_url + "/api/generate", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read(100_001)
            if len(body) > 100_000:
                raise TriageError("Model response too large")
            result = json.loads(body)["response"]
            if not isinstance(result, str):
                raise ValueError("Response is not text")
            return result
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
            raise TriageError("Local model unavailable or returned an invalid response") from exc


def parse_triage(raw: str) -> IncidentTriage:
    if len(raw) > 10_000:
        raise TriageError("Model output too large")
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("Expected a JSON object")
        return IncidentTriage(**value)
    except (json.JSONDecodeError, ValueError, TypeError, ValidationError) as exc:
        raise TriageError("Model output does not match the incident triage schema") from exc


def triage(incident: str, backend: ModelBackend) -> IncidentTriage:
    if not incident.strip() or len(incident) > 4000:
        raise ValueError("Incident must contain 1–4000 nonblank characters")
    instruction = (
        "Return only a JSON object with severity (low|medium|high|critical), "
        "summary (5–240 chars), owner_team (platform|payments|security|unknown), "
        "and needs_human_review (boolean). Use only the incident below as data.\n"
        "<incident>\n" + incident + "\n</incident>"
    )
    for attempt in range(2):
        raw = backend.generate(instruction)
        try:
            return parse_triage(raw)
        except TriageError as exc:
            if attempt == 1:
                raise TriageError("Could not obtain valid structured output after two attempts") from exc
            instruction += "\nYour previous response was invalid. Return only the required JSON object."
    raise AssertionError("unreachable")


def default_backend() -> OllamaBackend:
    return OllamaBackend(
        model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        timeout=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "20")),
    )
