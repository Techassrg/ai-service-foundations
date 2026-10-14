import pytest

from llm_structured_output.triage import TriageError, parse_triage, triage


VALID = '{"severity":"high","summary":"Synthetic payment timeout affects test calls.","owner_team":"payments","needs_human_review":true}'


class FakeBackend:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return next(self.responses)


def test_valid_contract():
    record = parse_triage(VALID)
    assert record.severity == "high"
    assert record.owner_team == "payments"


@pytest.mark.parametrize("raw", [
    "not json",
    '{"severity":"urgent","summary":"Valid long summary","owner_team":"payments","needs_human_review":true}',
    '{"severity":"high","summary":"short","owner_team":"payments","needs_human_review":true,"secret":"oops"}',
])
def test_rejects_invalid_schema(raw):
    with pytest.raises(TriageError):
        parse_triage(raw)


def test_retries_once_then_returns_valid_record():
    backend = FakeBackend(["{}", VALID])
    record = triage("Synthetic payment timeout", backend)
    assert record.needs_human_review is True
    assert len(backend.prompts) == 2
    assert "previous response was invalid" in backend.prompts[1]


def test_fails_after_two_invalid_responses():
    backend = FakeBackend(["{}", "[]"])
    with pytest.raises(TriageError, match="two attempts"):
        triage("Synthetic payment timeout", backend)
    assert len(backend.prompts) == 2


def test_rejects_bad_input_before_model_call():
    backend = FakeBackend([])
    with pytest.raises(ValueError):
        triage("   ", backend)
    assert backend.prompts == []
