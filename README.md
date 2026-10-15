# UlasApp

Turn your product photos and self-recorded clips into a short product review video. UlasApp writes a
UGC-style script with AI, cuts your clips to the script lines, renders on-screen text cards, adds your
music, and exports a vertical video - all generated locally by a small pipeline engine, driven from a
web workspace.

> **Status:** early development. This repository is private while the core is being designed and
> will be published as open source once the first milestone is complete.

## Features

**Current**

- One project per product, set up in steps: pick the material, check the descriptions the vision model
  wrote, fill in the brief, generate. Every generate adds a version instead of overwriting, and the
  versions list offers the player plus "open folder"
- Material understanding: every photo and clip is described by the vision model (clips through sampled
  scene frames); you can correct any description, and the corrections are what matching uses. One
  button generates the missing descriptions in bulk, and each tile shows whether its description is
  filled in yet
- Photos and clips to a 9:16 review video: AI script in casual Bahasa Indonesia that follows your brief,
  automatic shot ordering, on-screen text cards, background music
- Shape and Tone, chosen per project. Shape is the order of the beats: two presets (Ulasan, Reveal) or
  your own order built from a locked library of 11 beats (hook, bait, problem, reveal, demo, solution,
  proof, comparison, objection, social proof, CTA), with a live duration estimate. Tone carries the
  look: typography, palette, badge treatment, motion and how the first, middle and last beat are
  treated (four presets: Bersih, Tegas, Hangat, Toko), plus three overrides for accent colour, motion
  and badge style. Changing the beat order writes a new script; changing the tone only renders again,
  and the panel says which will happen before you commit
- The script aims to sell, not to list: every fact has to reach what it means for the buyer, at least
  one line is proven on camera, and invented claims, fake urgency and unverifiable superlatives are
  banned by the prompt
- Material handling: up to 20 photos and clips in the order you want, a hero shot, scene detection
  per clip, clips trimmed to the line they cover (with a frozen last frame when a clip is shorter
  than its line)
- A workspace built around the work: the steps on the left (Media, Brief, Style, Music, and the Voice
  Clone step that arrives with the voice phase), the media or the step's content next to it, the
  preview on the right, and the storyboard along the bottom with a timeline ruler, the shot clips, the
  on-screen text per line and the music track. Clicking a clip jumps the preview there
- The brief can be written by hand, started from one of four example briefs, or drafted from the
  product details and the material descriptions with one button
- Editing a shot line from the interface (swapping its material, typing its on-screen text, locking it)
  is not exposed yet; the engine supports it through the API and the end-to-end checks, and the
  controls return together with the multi-track timeline
- Readability is checked, not assumed: every text card has to stay up long enough to be read (a
  settled beat plus a per-word reading time), the opening card holds longer than the rest, the shots
  have to cover every script line, and the rendered length has to match the timeline
- Local engine: resumable stages (describe, script, visual, compose, QA) over a per-project state
  file, SQLite storage, live progress streamed to the UI; one render at a time
- Desktop app: a Tauri window that starts the engine, shows the same UI, and restarts the engine if it
  dies
- Settings screen for any OpenAI-compatible LLM endpoint (vision included) and for render quality

**Planned**

- Voice cloning so videos are narrated in your own voice, with per-line delivery control
- Aspect presets (9:16, 16:9, 1:1, 4:5), a zoomable multi-track timeline that also edits shots, brand
  kits
- MCP server and agent skill, CLI, publishing integrations, batch runs, installer

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
and one project renders at a time. Generating again keeps what you already approved: the script is only
written again when the product details or the brief changed, and an existing shot plan is kept unless
the script changed.

Every stage writes a JSON artifact plus its status into the project folder. A run therefore resumes
where it stopped, and each step can be inspected on disk. Compositions are plain HTML/CSS rendered
to MP4 by [HyperFrames](https://hyperframes.heygen.com).

## Project layout

- `backend/` - FastAPI + SQLModel + SQLite service: project store, pipeline stages, sidecar entrypoint
- `frontend/` - Svelte + Vite workspace UI
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
uv sync --frozen            :: exact locked versions; creates .venv on a fresh clone

:: without uv installed
python -m venv .venv
.venv\Scripts\pip install "fastapi>=0.115" "uvicorn[standard]>=0.30" sqlmodel pydantic-settings httpx python-multipart

.venv\Scripts\python -m app.sidecar --port 8765

:: terminal 2 - frontend
cd frontend
bun install
bun run dev
```

Open http://localhost:5173 and create a project with your product photos and clips, the product
details, the brief and an optional music track. The project opens as a workspace: check the
descriptions the vision model wrote and fix what it got wrong, fill in the brief, then press Generate
and watch the stages. Finished renders are listed under Versions with a player and "open folder", and
generating again adds the next version. Reordering the files at creation sets the priority and the
starred one opens the video.

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

MIT. See [LICENSE](LICENSE). Third-party material, if any is ever bundled, is recorded in
[THIRD-PARTY-NOTICES](THIRD-PARTY-NOTICES).
