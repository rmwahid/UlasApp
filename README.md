# UlasApp

Turn your product photos and self-recorded clips into a short product review video. UlasApp writes a
UGC-style script with AI, cuts your clips to the script lines, renders on-screen text cards, adds your
music, and exports a vertical video - all generated locally by a small pipeline engine, driven from a
web wizard.

> **Status:** early development. This repository is private while the core is being designed and
> will be published as open source once the first milestone is complete.

## Features

**Current**

- One project per product, set up in steps: pick the material, check the descriptions the vision model
  wrote, fill in the brief, generate. Every generate adds a version instead of overwriting, and the
  result section has a player plus "open folder"
- Material understanding: every photo and clip is described by the vision model (clips through sampled
  scene frames); you can correct any description, and the corrections are what matching uses
- Photos and clips to a 9:16 review video: AI script in casual Bahasa Indonesia with UGC structure
  (hook / problem / solution / proof / CTA) that follows your brief, automatic shot ordering,
  on-screen text cards, background music
- Material handling: up to 20 photos and clips in the order you want, a hero shot, scene detection
  per clip, clips trimmed to the line they cover (with a frozen last frame when a clip is shorter
  than its line)
- Storyboard review per script line: swap the material, edit the on-screen text, lock a line, rebuild
  the shots from your corrected descriptions
- Local engine: resumable stages (describe, script, visual, compose, QA) over a per-project state
  file, SQLite storage, live progress streamed to the UI; one render at a time
- Settings screen for any OpenAI-compatible LLM endpoint (vision included) and for render quality

**Planned**

- Voice cloning so videos are narrated in your own voice, with per-line delivery control
- Aspect presets (9:16, 16:9, 1:1, 4:5), a zoomable multi-track timeline, brand kits
- Desktop shell, MCP server and agent skill, batch runs

## How it works

```
frontend (Svelte)
      |  HTTP + SSE
      v
engine (FastAPI on 127.0.0.1)
      |  project store (SQLite), per-project state file
      v
stages: 0. describe (vision model reads the material)
        -> 1. script (LLM, uses your brief)
        -> 2. visual (shot plan from the descriptions)
        -> 3. compose (HyperFrames render)
        -> 4. QA
```

A project is one product you are making a video for. Nothing renders while you set it up: you pick the
material, the vision model describes it, you correct whatever it got wrong, you fill in the brief
(creative direction and on-screen text style), and only then you generate. Each generate writes a new
versioned file (`your-project_20261008-1056_1080x1920_v1.mp4`) instead of overwriting the last one,
and one project renders at a time.

Every stage writes a JSON artifact plus its status into the project folder. A run therefore resumes
where it stopped, and each step can be inspected on disk. Compositions are plain HTML/CSS rendered
to MP4 by [HyperFrames](https://hyperframes.heygen.com).

## Project layout

- `backend/` - FastAPI + SQLModel + SQLite service: job queue, pipeline stages, sidecar entrypoint
- `frontend/` - Svelte + Vite wizard UI
- `src-tauri/` - desktop shell (Rust + WebView2): runs the engine as a child process, reads its
  port handshake, and hosts the UI in a native window

## Requirements

- Python 3.12 or newer (engine)
- Bun 1.4+ (web tooling and the render runner) or Node.js 22+ (npx) - the HyperFrames CLI
  documents Node 22+, and bunx is verified to launch it
- FFmpeg and a local Chrome (used by the render step)
- Rust toolchain (MSVC) - only for building the desktop shell

## Quick start

```bat
:: terminal 1 - engine
cd backend
python -m venv .venv
.venv\Scripts\pip install "fastapi[standard]" sqlmodel pydantic-settings httpx python-multipart
.venv\Scripts\python -m app.sidecar --port 8765

:: terminal 2 - frontend
cd frontend
bun install
bun run dev
```

Open http://localhost:5173, create a job with your product photos and clips, product details and a
music track, then follow the stages until the video player appears. Reordering the files sets the
priority, the starred one opens the video, and the storyboard below the player lets you swap the
material per line and re-render compose and QA only.

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

1. Walking skeleton: one photo to a text + music 9:16 video (done)
2. Real material: multiple photos and clips, automatic shot ordering, storyboard review (done)
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
