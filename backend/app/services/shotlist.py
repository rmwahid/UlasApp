"""Shot assignment: which material covers which script line, and from where in a clip.

Everything here is a pure function over plain dictionaries so the matcher can be reasoned
about and tested without ffprobe, the LLM, or the renderer. The only IO it needs is a probe
result already stored on the asset (`scenes`, `duration`).
"""

from itertools import pairwise
from typing import Any

from app.services.state import AssetRecord, Scene, Shot, Shotlist, TimelineLine

MIN_SCENE_SECONDS = 0.6
FREEZE_EPSILON = 0.05
MIN_SLOT_SECONDS = 0.1
WINDOWS_PER_SCENE = 3

MODE_PHOTO = "photo"
MODE_TRIM = "trim"
MODE_FREEZE = "freeze"

FREEZE_RANK = 2

Window = tuple[int, float]
Ranges = dict[str, list[tuple[float, float]]]


def scene_segments(times: list[float], duration: float) -> list[Scene]:
    """Turn scene-change times into consecutive segments covering the whole clip.

    Slivers shorter than MIN_SCENE_SECONDS are merged into their neighbour, so a shaky
    detector does not produce unplayable one-frame scenes.
    """
    if duration <= 0:
        return []
    cuts: list[float] = []
    for moment in sorted(set(times)):
        previous = cuts[-1] if cuts else 0.0
        if moment - previous < MIN_SCENE_SECONDS:
            continue
        if duration - moment < MIN_SCENE_SECONDS:
            continue
        cuts.append(round(moment, 3))
    bounds = [0.0, *cuts, round(duration, 3)]
    return [{"start": start, "end": end} for start, end in pairwise(bounds) if end - start > 0]


def shot_windows(asset: AssetRecord, slot: float) -> list[Window]:
    """Ranked (rank, source start) candidates for covering `slot` seconds of a clip.

    rank 0: the window sits inside a single scene, so the shot contains no cut
    rank 1: starts on a scene boundary and still has enough footage after it
    rank 2: the clip is shorter than the slot, so it has to be padded with a frozen frame

    A scene long enough for several slots offers several starts, which is what lets a clip
    used by more than one line show different footage each time.
    """
    duration = float(asset.get("duration") or 0.0)
    scenes = _scenes(asset)
    if duration <= 0 or not scenes or duration + FREEZE_EPSILON < slot:
        return [(FREEZE_RANK, 0.0)]
    candidates: dict[float, int] = {}
    for scene in scenes:
        start = round(float(scene["start"]), 3)
        end = round(float(scene["end"]), 3)
        inside = start
        for _ in range(WINDOWS_PER_SCENE):
            if inside + slot > end + FREEZE_EPSILON:
                break
            candidates[inside] = min(candidates.get(inside, FREEZE_RANK), 0)
            inside = round(inside + slot, 3)
        if duration - start + FREEZE_EPSILON >= slot:
            candidates[start] = min(candidates.get(start, FREEZE_RANK), 1)
    if not candidates:
        return [(FREEZE_RANK, 0.0)]
    return sorted((rank, start) for start, rank in candidates.items())


def pick_window(asset: AssetRecord, slot: float, used: Ranges) -> tuple[str, float]:
    """Best (mode, source start) for covering `slot` seconds of a clip.

    Rank decides first because it encodes whether the shot needs padding or crosses a cut;
    among equally ranked windows, the one whose footage has not been shown yet wins.
    """
    taken = used.get(asset["id"], [])
    rank, start = min(
        shot_windows(asset, slot),
        key=lambda item: (item[0], _overlaps(item[1], slot, taken), item[1]),
    )
    if rank == FREEZE_RANK:
        return MODE_FREEZE, start
    return MODE_TRIM, start


def build_shotlist(
    lines: list[TimelineLine],
    assets: list[AssetRecord],
    previous: Shotlist | None = None,
    assignment: dict[str, str] | None = None,
    matched_by: str = "rotation",
    notes: str = "",
) -> Shotlist:
    """Assign one shot per script line.

    When `assignment` is given it decides the picture for every unlocked line (it is what the model
    proposed from the material descriptions), except that a hero tag always opens the video because
    that is the user's own intent; lines the assignment does not cover fall back to the rotation.
    The rotation follows the order the user arranged, starting at the hero (or the first asset) so
    the hook leads with it, never uses an asset twice in a row while an unused alternative exists,
    and hands out a different window on every pass. Lines marked locked keep the asset and window
    they already had, and overlay text the user typed is never dropped: a rebuild re-decides the
    picture, not the words.
    """
    pool = _rotation(assets)
    if not lines or not pool:
        return {"shots": [], "matched_by": matched_by, "notes": notes}
    by_id: dict[str, AssetRecord] = {asset["id"]: asset for asset in pool}
    previous_shots: dict[str, Shot] = (
        {shot["line"]: shot for shot in previous.get("shots", [])} if previous else {}
    )
    locked = {
        line: shot
        for line, shot in previous_shots.items()
        if shot.get("locked") and shot.get("asset") in by_id
    }
    chosen = _usable_assignment(assignment or {}, {line["id"] for line in lines}, by_id)
    hero = next((asset for asset in pool if asset.get("hero")), None)
    if chosen and hero is not None and lines[0]["id"] not in locked:
        # The hero tag is the user saying "open with this one", so it outranks the model.
        chosen[lines[0]["id"]] = hero["id"]
    fallback_pool = [asset for asset in pool if asset["id"] not in set(chosen.values())] or pool
    used: Ranges = {}
    cursor = _Cursor(fallback_pool)
    shots: list[Shot] = []
    for index, line in enumerate(lines, start=1):
        slot = _slot(line)
        prior = locked.get(line["id"])
        if prior:
            asset = by_id[prior["asset"]]
            mode = prior.get("mode") or MODE_PHOTO
            source_start = prior.get("source_start")
            cursor.remember(asset["id"])
        else:
            picked = chosen.get(line["id"])
            next_asset = by_id.get(picked) if picked is not None else None
            asset = next_asset if next_asset is not None else cursor.take()
            if asset.get("kind") == "clip":
                mode, source_start = pick_window(asset, slot, used)
            else:
                mode, source_start = MODE_PHOTO, None
        if mode == MODE_TRIM and source_start is not None:
            _remember(used, asset["id"], float(source_start), slot)
        prior_shot = previous_shots.get(line["id"])
        overlay = prior_shot.get("overlay") if prior_shot else None
        shots.append(_shot(index, line, asset, mode, source_start, bool(prior), overlay))
    return {
        "shots": shots,
        "matched_by": matched_by if chosen else "rotation",
        "notes": notes,
    }


def _usable_assignment(
    assignment: dict[str, str], line_ids: set[str], by_id: dict[str, AssetRecord]
) -> dict[str, str]:
    """Keep only the assignments that name a real line and a real asset."""
    return {
        line: asset for line, asset in assignment.items() if line in line_ids and asset in by_id
    }


def apply_edits(
    shotlist: Shotlist,
    lines: list[TimelineLine],
    assets: list[AssetRecord],
    edits: list[dict[str, Any]],
) -> Shotlist:
    """Merge storyboard edits (asset, overlay, locked) into an existing shotlist.

    A shot whose asset did not change keeps the window it had, so editing overlay text or
    locking a line never moves the picture. Changing the asset picks a fresh window that
    avoids footage the other shots already use.
    """
    by_asset: dict[str, AssetRecord] = {asset["id"]: asset for asset in assets}
    lines_by_id = {line["id"]: line for line in lines}
    requested: dict[str, dict[str, Any]] = {}
    for edit in edits:
        line_id = edit.get("line")
        if not isinstance(line_id, str) or line_id not in lines_by_id:
            raise ValueError(f"unknown script line '{line_id}'")
        asset_id = edit.get("asset")
        if asset_id is not None and (not isinstance(asset_id, str) or asset_id not in by_asset):
            raise ValueError(f"unknown asset '{asset_id}'")
        requested[line_id] = edit
    previous = {shot["line"]: shot for shot in shotlist.get("shots", [])}
    used: Ranges = {}
    for line_id, shot in previous.items():
        if line_id in requested or shot.get("mode") != MODE_TRIM:
            continue
        start = shot.get("source_start")
        if start is not None and line_id in lines_by_id:
            _remember(used, shot["asset"], float(start), _slot(lines_by_id[line_id]))
    shots: list[Shot] = []
    for index, line in enumerate(lines, start=1):
        slot = _slot(line)
        prior = previous.get(line["id"])
        edit = requested.get(line["id"], {})
        prior_asset = prior.get("asset") if prior else None
        asset_id = edit.get("asset") or prior_asset
        asset = by_asset.get(asset_id) if isinstance(asset_id, str) else None
        if asset is None:
            continue
        overlay = (
            edit["overlay"] if "overlay" in edit else (prior.get("overlay") if prior else None)
        )
        locked = bool(
            edit["locked"] if "locked" in edit else (prior.get("locked") if prior else False)
        )
        if asset.get("kind") != "clip":
            mode, source_start = MODE_PHOTO, None
        elif prior is not None and _window_holds(prior, asset, slot):
            mode, source_start = prior["mode"], prior.get("source_start")
        else:
            mode, source_start = pick_window(asset, slot, used)
        if mode == MODE_TRIM and source_start is not None:
            _remember(used, asset["id"], float(source_start), slot)
        shots.append(_shot(index, line, asset, mode, source_start, locked, overlay))
    return {"shots": shots, "matched_by": "manual", "notes": ""}


def _shot(
    index: int,
    line: TimelineLine,
    asset: AssetRecord,
    mode: str,
    source_start: float | None,
    locked: bool,
    overlay: str | None = None,
) -> Shot:
    return {
        "id": f"S{index}",
        "line": line["id"],
        "asset": asset["id"],
        "mode": mode,
        "source_start": round(float(source_start), 3) if source_start is not None else None,
        "start": round(float(line["start"]), 3),
        "end": round(float(line["end"]), 3),
        "overlay": overlay,
        "locked": locked,
    }


def _scenes(asset: AssetRecord) -> list[Scene]:
    scenes = [
        scene
        for scene in (asset.get("scenes") or [])
        if float(scene.get("end", 0.0)) > float(scene.get("start", 0.0))
    ]
    if scenes:
        return scenes
    duration = float(asset.get("duration") or 0.0)
    return [{"start": 0.0, "end": round(duration, 3)}] if duration > 0 else []


def _rotation(assets: list[AssetRecord]) -> list[AssetRecord]:
    """Asset order for the rotation: user order, rotated so the hero leads."""
    pool = [asset for asset in assets if asset.get("id")]
    if not pool:
        return []
    lead = next((index for index, asset in enumerate(pool) if asset.get("hero")), 0)
    return pool[lead:] + pool[:lead]


def _slot(line: TimelineLine) -> float:
    return max(MIN_SLOT_SECONDS, round(float(line["end"]) - float(line["start"]), 3))


def _window_holds(shot: Shot, asset: AssetRecord, slot: float) -> bool:
    """Whether a recorded window is still valid for the current slot length."""
    if shot.get("asset") != asset.get("id"):
        return False
    mode = shot.get("mode")
    if mode == MODE_FREEZE:
        return True
    if mode != MODE_TRIM:
        return False
    start = shot.get("source_start")
    if start is None:
        return False
    duration = float(asset.get("duration") or 0.0)
    if duration + FREEZE_EPSILON < slot:
        return False
    return float(start) + slot <= duration + FREEZE_EPSILON


def _remember(used: Ranges, asset_id: str, start: float, slot: float) -> None:
    used.setdefault(asset_id, []).append((start, round(start + slot, 3)))


def _overlaps(start: float, slot: float, taken: list[tuple[float, float]]) -> int:
    end = start + slot
    return sum(
        1
        for taken_start, taken_end in taken
        if start < taken_end - FREEZE_EPSILON and taken_start < end - FREEZE_EPSILON
    )


class _Cursor:
    """Round-robin over the rotation that refuses to repeat the previous asset."""

    def __init__(self, pool: list[AssetRecord]) -> None:
        self._pool = pool
        self._index = 0
        self._last: str | None = None

    def take(self) -> AssetRecord:
        choice = self._pool[self._index % len(self._pool)]
        if len(self._pool) > 1 and choice["id"] == self._last:
            self._index += 1
            choice = self._pool[self._index % len(self._pool)]
        self._index += 1
        self._last = choice["id"]
        return choice

    def remember(self, asset_id: str) -> None:
        self._last = asset_id
