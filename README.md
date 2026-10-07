# UlasApp

AI product-review video generator: upload product photos and/or self-recorded product footage,
clone your own voice from a short sample, and get a UGC-style product review video with your voice.

Status: Phase 1 (walking skeleton) scaffold in progress. Local pipeline engine (FastAPI + SQLModel +
SQLite) and web wizard (Svelte + Vite); desktop shell is completed later in this phase.

Planned architecture (see the project AGENTS.md for the full decision record):

- Web-based UI wrapped in Tauri 2 (same UI also runs in a browser)
- Rust core for job orchestration (SQLite queue, settings, sidecar lifecycle)
- Python sidecar engine (local FastAPI) with a stage pipeline:
  script -> voice (swappable provider adapters) -> visual -> compose -> qa
- HyperFrames as the primary composition renderer
- Heavy AI inference dispatchable to cloud providers; local composition works on low-spec machines

## License

To be finalized before first release. Third-party license obligations are tracked in
THIRD-PARTY-NOTICES when applicable.
