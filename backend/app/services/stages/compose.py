"""Stage: build the HyperFrames composition from the shotlist and render it to MP4."""

import asyncio
import html
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from app.core import media
from app.core.config import get_settings
from app.services import tones
from app.services.shotlist import MODE_FREEZE, MODE_PHOTO
from app.services.state import (
    AssetRecord,
    Shot,
    StageContext,
    StageError,
    Timeline,
    version_path,
)

FRAME_MARGIN_SECONDS = 0.2
RENDER_WIDTH = 1080
RENDER_HEIGHT = 1920

TEMPLATE = """<!doctype html>
<html lang="id">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=@@WIDTH@@, height=@@HEIGHT@@" />
    <title>@@TITLE@@</title>
    <script src="./assets/gsap.min.js"></script>
    <style>
      body { margin: 0; background: @@TOK_BG@@; font-family: @@TOK_FONT@@; }
      #root { position: relative; width: 100%; height: 100%; overflow: hidden;
              background: @@TOK_BG@@; }
      .clip { position: absolute; inset: 0; display: grid; place-items: center; }
      .media { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
      .media-layer { z-index: 1; }
      .shade-layer { z-index: 10; }
      .card-clip { z-index: 20; display: flex; align-items: flex-end; justify-content: center;
                   padding-bottom: 5%; }
      .shade { position: absolute; left: 0; right: 0; bottom: 0; height: 46%;
               background: @@TOK_SHADE@@; }
      .card { width: 90%; padding: @@TOK_CARD_PADDING@@; border-radius: @@TOK_CARD_RADIUS@@;
              background: @@TOK_CARD_BG@@; backdrop-filter: blur(@@TOK_CARD_BLUR@@);
              border: @@TOK_CARD_BORDER@@; box-shadow: 0 18px 60px rgba(0,0,0,.5); }
      .line-text { font-size: @@TOK_LINE_SIZE@@; line-height: 1.28;
                   font-weight: @@TOK_LINE_WEIGHT@@; letter-spacing: @@TOK_LINE_SPACING@@;
                   text-transform: @@TOK_LINE_CASE@@; color: @@TOK_INK@@; margin: 0;
                   text-shadow: 0 2px 8px rgba(0,0,0,.45); }
      .overlay-chip { display: inline-block; margin: 22px 0 0; padding: @@TOK_BADGE_PAD@@;
                      border-radius: @@TOK_BADGE_RADIUS@@; background: @@TOK_BADGE_FILL@@;
                      color: @@TOK_BADGE_TEXT@@; border-bottom: @@TOK_BADGE_BORDER@@;
                      font-size: @@TOK_BADGE_SIZE@@; font-weight: @@TOK_BADGE_WEIGHT@@; }
      .card-clip.hero { align-items: center; padding-bottom: 20%; }
      .card.hero { width: 100%; padding: 56px 44px; background: @@TOK_HERO_BG@@; border: 0;
                   border-radius: 0; backdrop-filter: none; box-shadow: none; text-align: center; }
      .card.plate { background: @@TOK_ACCENT@@; border: 0; box-shadow: none; }
      .card.plate .line-text { color: @@TOK_ACCENT_INK@@; text-shadow: none; }
      .card.plate .overlay-chip { background: @@TOK_INK@@; color: @@TOK_ACCENT@@;
                                  border-bottom: 0; }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-width="@@WIDTH@@"
         data-height="@@HEIGHT@@" data-duration="@@TOTAL@@">
@@MEDIA@@
      <div id="shade-layer" class="clip shade-layer" data-start="0" data-duration="@@TOTAL@@"
           data-track-index="1">
        <div class="shade"></div>
      </div>
@@CARDS@@
@@MUSIC@@
    </div>
    <script>
      const tl = gsap.timeline({ paused: true });
@@TWEENS@@
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""


def _asset_src(asset: AssetRecord) -> str:
    return "assets/" + Path(asset["path"]).name


def _is_photo(shot: Shot, asset: AssetRecord) -> bool:
    return shot.get("mode") == MODE_PHOTO and asset.get("kind") == "photo"


def _media_layers(
    shots: list[Shot],
    assets: dict[str, AssetRecord],
    freeze_src: dict[str, str],
    tokens: dict[str, str],
) -> tuple[list[str], list[str]]:
    """One full-bleed element per shot, plus the slow-zoom tweens for photo shots.

    Photos keep the proven shape of an untimed `<img>` inside a timed section, because the
    zoom has to animate a non-media node. Consecutive photo shots of the same asset become a
    single section so the zoom never restarts mid-sequence. Clips are the timed media element
    itself, which is why they are never wrapped in anything else carrying `data-start`. How far the
    camera pushes in comes from the tone's motion tokens.
    """
    layers: list[str] = []
    tweens: list[str] = []
    index = 0
    while index < len(shots):
        shot = shots[index]
        asset = assets[shot["asset"]]
        start = round(float(shot["start"]), 3)
        if _is_photo(shot, asset):
            last = index
            end = round(float(shots[last]["end"]), 3)
            while last + 1 < len(shots):
                following = shots[last + 1]
                if not _is_photo(following, assets[following["asset"]]):
                    break
                if (
                    following["asset"] != asset["id"]
                    or abs(float(following["start"]) - end) > 0.001
                ):
                    break
                last += 1
                end = round(float(shots[last]["end"]), 3)
            span = round(end - start, 3)
            layers.append(
                f'      <section id="shot-{shot["id"]}" class="clip media-layer" data-start="{start}" '
                f'data-duration="{span}" data-track-index="0">\n'
                f'        <img class="media" src="{html.escape(_asset_src(asset))}" alt="" />\n'
                f"      </section>"
            )
            tweens.append(
                f'      tl.fromTo("#shot-{shot["id"]} .media", {{ scale: {tokens["zoom_from"]} }}, '
                f'{{ scale: {tokens["zoom_to"]}, duration: {span}, ease: "none" }}, {start});'
            )
            index = last + 1
            continue
        if asset.get("kind") == "photo":
            raise StageError(f"Shot {shot['id']} wants {shot['mode']} footage from a still image.")
        span = round(float(shot["end"]) - start, 3)
        if shot.get("mode") == MODE_FREEZE:
            source = freeze_src[shot["id"]]
            offset = 0.0
        else:
            source = _asset_src(asset)
            offset = round(float(shot.get("source_start") or 0.0), 3)
        layers.append(
            f'      <video id="shot-{shot["id"]}" class="clip media media-layer" '
            f'src="{html.escape(source)}" data-start="{start}" data-duration="{span}" '
            f'data-media-start="{offset}" data-track-index="0" muted playsinline></video>'
        )
        index += 1
    return layers, tweens


def _card_clips(
    timeline: Timeline, overlays: dict[str, str | None], tokens: dict[str, str]
) -> tuple[list[str], list[str]]:
    """One card per script line, treated by its position: the opening and closing beat differ.

    Every line is one thought: the text, and the on-screen label the script wrote for it. How the
    card is dressed comes from the tone's treatment for that position, so the same tokens that style
    the whole video also decide that the hook is type over the picture rather than another box.
    """
    cards: list[str] = []
    tweens: list[str] = []
    lines = timeline["lines"]
    for index, line in enumerate(lines):
        lid = line["id"]
        duration = max(0.1, round(line["end"] - line["start"], 3))
        position = "first" if index == 0 else ("last" if index == len(lines) - 1 else "middle")
        treatment = tones.treat(tokens, position)
        overlay = ""
        chip = overlays.get(lid, line.get("overlay"))
        if chip:
            overlay = f'        <p class="overlay-chip">{html.escape(str(chip))}</p>\n'
        cards.append(
            f'      <section id="card-{lid}" class="clip card-clip {treatment}" '
            f'data-start="{line["start"]}" data-duration="{duration}">\n'
            f'        <div class="card {treatment}">\n'
            f'          <p class="line-text">{html.escape(str(line["text"]))}</p>\n'
            f"{overlay}"
            f"        </div>\n"
            f"      </section>"
        )
        tweens.append(
            f'      tl.fromTo("#card-{lid} .card", '
            f"{{ y: {tokens['entry_travel']}, opacity: 0 }}, "
            f"{{ y: 0, opacity: 1, duration: {tokens['entry_duration']}, "
            f'ease: "{tokens["entry_ease"]}" }}, {line["start"]});'
        )
    return cards, tweens


def _freeze_clips(
    directory: Path, media_dir: Path, shots: list[Shot], assets: dict[str, AssetRecord]
) -> tuple[dict[str, str], list[tuple[Path, Path, float, float]]]:
    """Padded clips for shots that are shorter than their slot: play, then hold the last frame.

    The file name carries the source offset and the padded length, so a re-render reuses the
    file it already made and a changed slot length simply produces a new one.
    """
    sources: dict[str, str] = {}
    pending: list[tuple[Path, Path, float, float]] = []
    for shot in shots:
        if shot.get("mode") != MODE_FREEZE:
            continue
        asset = assets[shot["asset"]]
        offset = round(float(shot.get("source_start") or 0.0), 3)
        span = round(float(shot["end"]) - float(shot["start"]), 3) + FRAME_MARGIN_SECONDS
        name = f"{asset['id']}__{offset:.3f}__{span:.3f}.mp4"
        target = media_dir / name
        if not target.exists() or target.stat().st_size == 0:
            pending.append((directory / asset["path"], target, offset, span))
        sources[shot["id"]] = "media/" + name
    return sources, pending


def _music_element(music_src: str, total: float) -> str:
    if not music_src:
        return ""
    return (
        f'      <audio id="bgm" src="{html.escape(music_src)}" data-start="0" '
        f'data-duration="{total}"></audio>'
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


def render_video(compose_dir: Path, out_path: Path, quality: str, runner: str) -> None:
    runner = runner if runner in ("npx", "bunx") else "npx"
    executable = shutil.which(runner)
    if executable is None:
        raise StageError(
            f"'{runner}' not found on PATH; install Node.js 22+ (npx) or Bun 1.4+ (bunx)"
        )
    cmd = [
        runner,
        "--yes",
        "hyperframes",
        "render",
        "--quality",
        quality,
        "--output",
        str(out_path),
    ]
    if runner == "bunx":
        cmd = ["bunx", "hyperframes", "render", "--quality", quality, "--output", str(out_path)]
    if os.name == "nt":
        cmd = ["cmd", "/c"] + cmd
    try:
        proc = subprocess.run(
            cmd, cwd=str(compose_dir), capture_output=True, check=False, text=True, timeout=3600
        )
    except subprocess.TimeoutExpired as exc:
        raise StageError("Composition render timed out") from exc
    if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        tail = ((proc.stderr or "") + (proc.stdout or ""))[-1200:]
        raise StageError(f"Render failed. CLI output: {tail}")


async def run(ctx: StageContext) -> None:
    settings = get_settings()
    directory = Path(ctx["dir"])
    state = ctx["state"]
    timeline = state.get("timeline")
    shotlist = state.get("shotlist")
    shots = shotlist.get("shots") if shotlist else None
    if timeline is None or not timeline.get("lines"):
        raise StageError("Timeline has no lines; run the script stage first.")
    if not shots:
        raise StageError("No shots were planned; run the visual stage first.")
    inputs = state["inputs"]
    assets: dict[str, AssetRecord] = {asset["id"]: asset for asset in (inputs.get("assets") or [])}
    tokens = tones.resolve(state.get("style"))

    compose_dir = directory / "compose"
    assets_dir = compose_dir / "assets"
    media_dir = compose_dir / "media"
    assets_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)
    for asset_id in {shot["asset"] for shot in shots}:
        asset = assets.get(asset_id)
        if asset is None:
            raise StageError(f"The shotlist refers to unknown material '{asset_id}'.")
        source = directory / asset["path"]
        if not source.exists():
            raise StageError(f"Material file is missing: {asset['name']}")
        shutil.copyfile(source, assets_dir / Path(asset["path"]).name)

    music_rel = inputs.get("music")
    music_src = ""
    if music_rel:
        music_src = "assets/" + Path(music_rel).name
        shutil.copyfile(directory / music_rel, assets_dir / Path(music_rel).name)
    _ensure_gsap(settings.data_dir / "cache", assets_dir)

    freeze_src, pending = _freeze_clips(directory, media_dir, shots, assets)
    for source, target, offset, span in pending:
        await asyncio.to_thread(media.freeze_segment, source, target, offset, span)
    keep = {Path(name).name for name in freeze_src.values()}
    for stale in media_dir.glob("*.mp4"):
        if stale.name not in keep:
            stale.unlink(missing_ok=True)

    layers, media_tweens = _media_layers(shots, assets, freeze_src, tokens)
    overlays = {shot["line"]: shot["overlay"] for shot in shots if shot.get("overlay") is not None}
    cards, card_tweens = _card_clips(timeline, overlays, tokens)

    page = (
        TEMPLATE.replace("@@WIDTH@@", str(RENDER_WIDTH))
        .replace("@@HEIGHT@@", str(RENDER_HEIGHT))
        .replace("@@TOTAL@@", str(timeline["total"]))
        .replace("@@TITLE@@", html.escape(str(ctx.get("title", "Review"))))
        .replace("@@MEDIA@@", "\n".join(layers))
        .replace("@@CARDS@@", "\n".join(cards))
        .replace("@@TWEENS@@", "\n".join(media_tweens + card_tweens))
        .replace("@@MUSIC@@", _music_element(music_src, timeline["total"]))
        .replace("@@TOK_FONT@@", tokens["font"])
        .replace("@@TOK_LINE_SPACING@@", tokens["line_spacing"])
        .replace("@@TOK_LINE_WEIGHT@@", tokens["line_weight"])
        .replace("@@TOK_LINE_SIZE@@", tokens["line_size"])
        .replace("@@TOK_LINE_CASE@@", tokens["line_case"])
        .replace("@@TOK_CARD_PADDING@@", tokens["card_padding"])
        .replace("@@TOK_CARD_RADIUS@@", tokens["card_radius"])
        .replace("@@TOK_CARD_BLUR@@", tokens["card_blur"])
        .replace("@@TOK_CARD_BORDER@@", tokens["card_border"])
        .replace("@@TOK_CARD_BG@@", tokens["card_bg"])
        .replace("@@TOK_BADGE_WEIGHT@@", tokens["badge_weight"])
        .replace("@@TOK_BADGE_SIZE@@", tokens["badge_size"])
        .replace("@@TOK_BADGE_RADIUS@@", tokens["badge_radius"])
        .replace("@@TOK_BADGE_BORDER@@", tokens["badge_border"])
        .replace("@@TOK_BADGE_FILL@@", tokens["badge_fill"])
        .replace("@@TOK_BADGE_TEXT@@", tokens["badge_text"])
        .replace("@@TOK_BADGE_PAD@@", tokens["badge_pad"])
        .replace("@@TOK_HERO_BG@@", tokens["hero_bg"])
        .replace("@@TOK_SHADE@@", tokens["shade"])
        .replace("@@TOK_ACCENT_INK@@", tokens["accent_ink"])
        .replace("@@TOK_ACCENT@@", tokens["accent"])
        .replace("@@TOK_INK@@", tokens["ink"])
        .replace("@@TOK_BG@@", tokens["bg"])
    )
    (compose_dir / "index.html").write_text(page, encoding="utf-8")

    versions = state.setdefault("versions", [])
    number = len(versions) + 1
    relative = version_path(
        str(state.get("title") or ctx.get("title") or "project"),
        RENDER_WIDTH,
        RENDER_HEIGHT,
        number,
        datetime.now(UTC),
    )
    out_path = directory / relative
    out_path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(
        render_video, compose_dir, out_path, settings.compose_quality, settings.render_runner
    )
    versions.append(
        {
            "number": number,
            "file": relative,
            "resolution": f"{RENDER_WIDTH}x{RENDER_HEIGHT}",
            "created_at": datetime.now(UTC).isoformat(),
            "summary": _version_summary(shots),
        }
    )
    state["outputs"]["video"] = relative


def _version_summary(shots: list[Shot]) -> str:
    """What this render looks like at a glance, for the result list."""
    assets = sorted({shot["asset"] for shot in shots})
    modes = {shot["mode"] for shot in shots}
    return f"{len(shots)} shots, {len(assets)} material, {'/'.join(sorted(modes))}"
