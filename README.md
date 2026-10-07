# UlasApp

Turn one product photo into a short product review video. UlasApp writes a UGC-style script with
AI, renders on-screen text cards over your product shot, adds your music, and exports a vertical
video - all generated locally by a small pipeline engine, driven from a web wizard.

> **Status:** early development. This repository is private while the core is being designed and
> will be published as open source once the first milestone is complete.

## Features

**Current**

- One photo to a 9:16 review video: AI script in casual Bahasa Indonesia with UGC structure
  (hook / problem / solution / proof / CTA), on-screen text cards, background music
- Local pipeline engine: resumable stages (script, visual, compose, QA) over a per-project state
  file, job queue on SQLite, live progress streamed to the UI over SSE
- Web wizard: create a job from one photo, product details and a music track, watch each stage
  finish, play the rendered result
- Settings screen for any OpenAI-compatible LLM endpoint and for render quality

**Planned**

- Voice cloning so videos are narrated in your own voice, with per-line delivery control
- Multiple photos and self-recorded clips with automatic shot ordering and a storyboard editor
- Aspect presets (9:16, 16:9, 1:1, 4:5), a zoomable multi-track timeline, brand kits
- Desktop shell, MCP server and agent skill, batch runs

## How it works

```
web wizard (Svelte)
      |  HTTP + SSE
      v
engine (FastAPI on 127.0.0.1)
      |  job queue (SQLite), per-project state file
      v
stages: 1. script (LLM)  ->  2. visual (asset plan)  ->  3. compose (HyperFrames render)  ->  4. QA
```

Every stage writes a JSON artifact plus its status into the project folder. A job therefore resumes
where it stopped, and each step can be inspected on disk. Compositions are plain HTML/CSS rendered
to MP4 by [HyperFrames](https://hyperframes.heygen.com).

## Project layout

- `engine/` - FastAPI + SQLModel + SQLite service: job queue, pipeline stages, sidecar entrypoint
- `web/` - Svelte + Vite wizard UI

## Requirements

- Python 3.12 or newer (engine)
- Bun 1.4+ (web tooling and the render runner) or Node.js 22+ (npx) - the HyperFrames CLI
  documents Node 22+, and bunx is verified to launch it
- FFmpeg and a local Chrome (used by the render step)

## Quick start

```bat
:: terminal 1 - engine
cd engine
python -m venv .venv
.venv\Scripts\pip install "fastapi[standard]" sqlmodel pydantic-settings httpx python-multipart
.venv\Scripts\python -m app.sidecar --port 8765

:: terminal 2 - web
cd web
bun install
bun run dev
```

Open http://localhost:5173, create a job with one product photo, product details and a music track,
then follow the stages until the video player appears.

## Configuration

Settings live as JSON overrides in the data directory and are edited on the Settings screen;
environment variables (prefix `ULASAPP_`) are an override layer for advanced setups:

- `ULASAPP_DATA_DIR` - data directory (default `%USERPROFILE%\.ulasapp`)
- `ULASAPP_LLM_BASE_URL`, `ULASAPP_LLM_API_KEY`, `ULASAPP_LLM_MODEL` - any OpenAI-compatible endpoint
- `ULASAPP_COMPOSE_QUALITY` - HyperFrames render quality (`draft`, `looks`, `delivery`)
- `ULASAPP_RENDER_RUNNER` - `npx` (default, Node 22+) or `bunx` (Bun 1.4+)

When the desktop shell lands, the API key is planned to move to OS-protected storage (Windows
Credential Manager) managed by the shell; the engine keeps reading it through the same settings.

## Roadmap

1. Walking skeleton: one photo to a text + music 9:16 video (this milestone)
2. Real material: multiple photos and clips, automatic shot ordering, storyboard review
3. Own voice: voice cloning through a cloud provider, per-line script editing and re-synthesis
4. Output variants: aspect presets, live composition preview
5. Polish and fix-it tools: delivery editor, brand kit, BGM ducking, zoomable timeline
6. Voice everywhere: local voice model; optional cloud avatar
7. Distribution and automation: MCP server, agent skill, CLI, publishing, batch runs
8. Productization: installer, i18n, template marketplace

## Contributing

The project is in early private development. Contribution guidelines will be published together
with the first public release.

## License

A license will be added before the first public release.
