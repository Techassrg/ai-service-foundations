# AI Service Foundations

Two independent Python projects show how to expose and validate local LLM capabilities behind explicit contracts.

```mermaid
flowchart LR
  Client --> API[FastAPI gateway]
  API --> Ollama[Local Ollama]
  Client --> Triage[Structured triage CLI]
  Triage --> Ollama
  Triage --> Contract[Typed schema and retry policy]
```

| Project | Engineering problem | Run |
| --- | --- | --- |
| [Python AI API Starter](projects/python-ai-api-starter/README.md) | Safely expose local inference through a bounded HTTP contract | `cd projects/python-ai-api-starter && python -m uvicorn ai_api_starter.app:app` |
| [LLM Structured Output](projects/llm-structured-output/README.md) | Convert unreliable model text to validated incident records | `cd projects/llm-structured-output && python -m llm_structured_output.cli` |

Use each project's `pyproject.toml` to install locally. Tests use deterministic fake providers and cost nothing. The Ollama commands require a locally running model and have not been live validated in this environment.

No GitHub remote or public repository has been created. Review the local work before publishing.
