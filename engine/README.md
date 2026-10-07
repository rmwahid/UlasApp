# Engine

Local FastAPI service that runs the review-video pipeline (script, visual, compose, QA) as
resumable stages over a per-project state file.

## Run (development)

```bat
cd engine
python -m venv .venv
.venv\Scripts\pip install "fastapi[standard]" sqlmodel pydantic-settings httpx python-multipart pytest
.venv\Scripts\python -m app.sidecar --port 8765
```

- API base: http://127.0.0.1:8765/api (health: `/api/health`)
- The web app (see `../web`) proxies `/api` to port 8765 in development.
- Without `--port` the engine binds a free port and prints `ENGINE_READY port=<n>` on stdout.

## Configuration

Environment variables (prefix `ULASAPP_`) or JSON overrides written by the Settings screen:

- `ULASAPP_DATA_DIR`: data directory (default `%USERPROFILE%\.ulasapp`)
- `ULASAPP_LLM_BASE_URL`, `ULASAPP_LLM_API_KEY`, `ULASAPP_LLM_MODEL`
- `ULASAPP_COMPOSE_QUALITY`: HyperFrames render quality (`draft`, `looks`, `delivery`)

## Tests

```bat
.venv\Scripts\python -m pytest -q
```
