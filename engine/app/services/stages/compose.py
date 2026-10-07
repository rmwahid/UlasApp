"""Stage 3: build the HyperFrames composition (text cards + music) and render it to MP4."""

import asyncio
import html
import os
import shutil
import subprocess
from pathlib import Path

from app.core.config import get_settings
from app.services.state import StageError

TEMPLATE = """<!doctype html>
<html lang="id">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=@@WIDTH@@, height=@@HEIGHT@@" />
    <title>@@TITLE@@</title>
    <script src="./assets/gsap.min.js"></script>
    <style>
      body { margin: 0; background: #0b0f14; font-family: system-ui, sans-serif; }
      #root { position: relative; width: 100%; height: 100%; overflow: hidden; background: #0b0f14; }
      .clip { position: absolute; inset: 0; display: grid; place-items: center; }
      .photo { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
      .scrim { position: absolute; inset: 0;
               background: linear-gradient(180deg, rgba(8,10,14,.3) 0%, rgba(8,10,14,.8) 100%); }
      .card { position: relative; width: 82%; padding: 44px 52px; border-radius: 28px;
              background: rgba(12,16,22,.74); box-shadow: 0 24px 80px rgba(0,0,0,.45); }
      .section-tag { font-size: 32px; letter-spacing: .18em; text-transform: uppercase;
                     color: #7fd4c1; margin: 0 0 16px; }
      .line-text { font-size: 72px; line-height: 1.25; font-weight: 700; color: #f4f7fb; margin: 0; }
      .overlay-chip { display: inline-block; margin: 26px 0 0; padding: 14px 32px; border-radius: 999px;
                      background: #f5b52e; color: #14181f; font-size: 52px; font-weight: 800; }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-width="@@WIDTH@@"
         data-height="@@HEIGHT@@" data-duration="@@TOTAL@@">
      <section id="photo-bg" class="clip" data-start="0" data-duration="@@TOTAL@@">
        <img class="photo" src="@@PHOTO@@" alt="" />
        <div class="scrim"></div>
      </section>
@@CARDS@@
@@MUSIC@@
    </div>
    <script>
      const tl = gsap.timeline({ paused: true });
      tl.fromTo("#photo-bg .photo", { scale: 1 }, { scale: 1.08, duration: @@TOTAL@@, ease: "none" }, 0);
@@TWEENS@@
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""


def _build_html(timeline: dict, photo_src: str, music_src: str | None, title: str) -> str:
    lines = timeline["lines"]
    total = timeline["total"]
    cards: list[str] = []
    tweens: list[str] = []
    for line in lines:
        lid = line["id"]
        duration = max(0.1, round(line["end"] - line["start"], 3))
        overlay = ""
        if line.get("overlay"):
            overlay = (
                f'        <p class="overlay-chip">{html.escape(str(line["overlay"]))}</p>\n'
            )
        cards.append(
            f'      <section id="card-{lid}" class="clip" data-start="{line["start"]}" '
            f'data-duration="{duration}">\n'
            f'        <div class="card">\n'
            f'          <p class="section-tag">{html.escape(str(line["section"]))}</p>\n'
            f'          <p class="line-text">{html.escape(str(line["text"]))}</p>\n'
            f"{overlay}"
            f"        </div>\n"
            f"      </section>"
        )
        tweens.append(
            f'      tl.fromTo("#card-{lid} .card", {{ y: 60, opacity: 0 }}, '
            f'{{ y: 0, opacity: 1, duration: 0.5, ease: "power3.out" }}, {line["start"]});'
        )
    music = ""
    if music_src:
        music = (
            f'      <audio id="bgm" src="{html.escape(music_src)}" data-start="0" '
            f'data-duration="{total}"></audio>'
        )
    return (
        TEMPLATE.replace("@@WIDTH@@", "1080")
        .replace("@@HEIGHT@@", "1920")
        .replace("@@TOTAL@@", str(total))
        .replace("@@TITLE@@", html.escape(title))
        .replace("@@PHOTO@@", html.escape(photo_src))
        .replace("@@CARDS@@", "\n".join(cards))
        .replace("@@TWEENS@@", "\n".join(tweens))
        .replace("@@MUSIC@@", music)
    )


def _ensure_gsap(cache_dir: Path, assets_dir: Path) -> None:
    assets_dir.mkdir(parents=True, exist_ok=True)
    target = assets_dir / "gsap.min.js"
    if target.exists() and target.stat().st_size > 0:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / "gsap.min.js"
    if not cached.exists() or cached.stat().st_size == 0:
        import httpx

        # Hardcoded, literal vendor URL - never built from user input.
        response = httpx.get(
            "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js", timeout=60
        )
        response.raise_for_status()
        cached.write_bytes(response.content)
    shutil.copyfile(cached, target)


def render_video(compose_dir: Path, out_path: Path, quality: str) -> None:
    npx = shutil.which("npx")
    if npx is None:
        raise StageError("npx not found; install Node.js 22+ to render compositions")
    cmd = ["npx", "--yes", "hyperframes", "render", "--quality", quality, "--output", str(out_path)]
    if os.name == "nt":
        cmd = ["cmd", "/c"] + cmd
    try:
        proc = subprocess.run(
            cmd, cwd=str(compose_dir), capture_output=True, text=True, timeout=3600
        )
    except subprocess.TimeoutExpired as exc:
        raise StageError("Composition render timed out") from exc
    if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        tail = ((proc.stderr or "") + (proc.stdout or ""))[-1200:]
        raise StageError(f"Render failed. CLI output: {tail}")


async def run(ctx: dict) -> None:
    settings = get_settings()
    directory = Path(ctx["dir"])
    state = ctx["state"]
    timeline = state.get("timeline", {})
    if not timeline.get("lines"):
        raise StageError("Timeline has no lines; run the script stage first.")
    compose_dir = directory / "compose"
    (compose_dir / "assets").mkdir(parents=True, exist_ok=True)

    photo_rel = state["inputs"]["photo"]
    photo_name = Path(photo_rel).name
    shutil.copyfile(directory / photo_rel, compose_dir / "assets" / photo_name)
    music_rel = state["inputs"].get("music")
    music_name = ""
    if music_rel:
        music_name = "assets/" + Path(music_rel).name
        shutil.copyfile(directory / music_rel, compose_dir / "assets" / Path(music_rel).name)

    _ensure_gsap(settings.data_dir / "cache", compose_dir / "assets")

    page = _build_html(timeline, "assets/" + photo_name, music_name, str(ctx.get("title", "Review")))
    (compose_dir / "index.html").write_text(page, encoding="utf-8")

    out_path = directory / "output" / "video.mp4"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(render_video, compose_dir, out_path, settings.compose_quality)
