from fastapi.testclient import TestClient

from ai_api_starter.app import ProviderError, create_app


class FakeBackend:
    def __init__(self, response="synthetic answer", error=False):
        self.response = response
        self.error = error
        self.calls = []

    def complete(self, prompt, model):
        self.calls.append((prompt, model))
        if self.error:
            raise ProviderError("secret provider detail")
        return self.response


def post(app, payload, headers=None):
    with TestClient(app) as client:
        return client.post("/v1/completions", json=payload, headers=headers)


def test_success_and_request_id():
    backend = FakeBackend()
    response = post(create_app(backend), {"prompt": "summarize synthetic event"}, {"x-request-id": "trace_1"})
    assert response.status_code == 200
    assert response.json() == {"text": "synthetic answer", "model": "llama3.2:3b", "request_id": "trace_1"}
    assert response.headers["x-request-id"] == "trace_1"
    assert backend.calls == [("summarize synthetic event", "llama3.2:3b")]


def test_invalid_input_never_calls_provider():
    backend = FakeBackend()
    app = create_app(backend)
    for payload in ({"prompt": " "}, {"prompt": "x" * 4001}, {"prompt": "ok", "model": "bad/name"}):
        assert post(app, payload).status_code == 422
    assert backend.calls == []


def test_provider_failure_is_redacted():
    response = post(create_app(FakeBackend(error=True)), {"prompt": "hello"})
    assert response.status_code == 503
    assert response.json()["error"] == "provider_unavailable"
    assert "secret provider detail" not in response.text


def test_excessive_provider_output_fails_safely():
    response = post(create_app(FakeBackend("x" * 20_001)), {"prompt": "hello"})
    assert response.status_code == 503
