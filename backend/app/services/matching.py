"""Placing material on script lines with the model, guided by the asset descriptions.

The model proposes an assignment; the deterministic matcher in `shotlist.py` still owns the
invariants and the source windows. Anything the model gets wrong (unknown ids, missing lines,
malformed JSON, an unreachable endpoint) simply falls back to the rotation, so a job never fails
because of this step.
"""

from app.services import llm
from app.services.llm import LLMError
from app.services.llm_json import LLMOutputError, extract_json_object

MAX_NOTES_CHARS = 300

SYSTEM_PROMPT = (
    "You place product material onto the lines of a short vertical review video. You answer with "
    "a single valid JSON object and nothing else: no markdown, no explanations outside the JSON."
)

USER_TEMPLATE = """Material (id, kind, orientation, seconds, description):
{assets}

Script lines to fill (id, section, what is said, visual hint):
{lines}

Rules:
- Give every line exactly one material id from the list above.
- Choose by meaning: the description of the material has to fit what the line says and its hint.
- The video is vertical 9:16, so portrait material fills the frame better than landscape material.
- Do not give the same material to two lines unless there are more lines than materials.
- Never use a material id that is not in the list.

Answer with JSON exactly like this:
{{"assignment": [{{"line": "L1", "asset": "a01"}}], "notes": "one short sentence about your choices"}}"""

ORIENTATION_PORTRAIT = "portrait"
ORIENTATION_LANDSCAPE = "landscape"
ORIENTATION_SQUARE = "square"


def orientation(asset: dict) -> str:
    width = int(asset.get("width") or 0)
    height = int(asset.get("height") or 0)
    if width <= 0 or height <= 0:
        return "unknown"
    if width > height:
        return ORIENTATION_LANDSCAPE
    if height > width:
        return ORIENTATION_PORTRAIT
    return ORIENTATION_SQUARE


def _asset_lines(assets: list[dict]) -> str:
    rows = []
    for asset in assets:
        seconds = asset.get("duration")
        length = f"{float(seconds):.1f}s" if seconds else "still"
        description = asset.get("description") or "no description"
        rows.append(
            f"- {asset['id']} | {asset['kind']} | {orientation(asset)} | {length} | {description}"
        )
    return "\n".join(rows)


def _line_rows(lines: list[dict]) -> str:
    rows = []
    for line in lines:
        hint = line.get("hint") or "none"
        rows.append(f"- {line['id']} | {line['section']} | {line['text']} | hint: {hint}")
    return "\n".join(rows)


def build_prompt(lines: list[dict], assets: list[dict]) -> str:
    return USER_TEMPLATE.format(assets=_asset_lines(assets), lines=_line_rows(lines))


def read_assignment(answer: str, lines: list[dict], assets: list[dict]) -> tuple[dict, str]:
    """Validate a model answer into {line id: asset id}, dropping anything unusable."""
    parsed = extract_json_object(answer)
    known_lines = {line["id"] for line in lines}
    known_assets = {asset["id"] for asset in assets}
    assignment: dict[str, str] = {}
    for entry in parsed.get("assignment") or []:
        if not isinstance(entry, dict):
            continue
        line_id = entry.get("line")
        asset_id = entry.get("asset")
        if line_id in known_lines and asset_id in known_assets:
            assignment[line_id] = asset_id
    notes = " ".join(str(parsed.get("notes") or "").split())[:MAX_NOTES_CHARS]
    return assignment, notes


async def assign(lines: list[dict], assets: list[dict]) -> tuple[dict, str, str]:
    """Ask the model for an assignment.

    Returns (assignment, notes, reason). An empty assignment with a reason means the pipeline
    should fall back to the deterministic rotation. Material that could not be described is still
    offered, marked as undescribed: a partial description set matches better than none, and the
    notes say how much was missing.
    """
    if not lines or not assets:
        return {}, "", "nothing to place"
    described = [asset["id"] for asset in assets if asset.get("description")]
    if not described:
        return {}, "", "no material has a description yet"
    assignment, notes, failure = await _request(lines, assets)
    if not assignment:
        return {}, notes, failure or "the model did not place any line"
    missing = [line["id"] for line in lines if line["id"] not in assignment]
    undescribed = len(assets) - len(described)
    reasons = []
    if missing:
        reasons.append(f"the model left {len(missing)} line(s) to the automatic rotation")
    if undescribed:
        reasons.append(f"{undescribed} material file(s) had no description")
    return assignment, notes, "; ".join(reasons)


MATCH_ATTEMPTS = 2
SNIPPET_CHARS = 160


async def _request(lines: list[dict], assets: list[dict]) -> tuple[dict, str, str]:
    """(assignment, notes, failure): a failure means no usable answer survived the attempts."""
    failure = ""
    for _ in range(MATCH_ATTEMPTS):
        try:
            answer = await llm.complete(SYSTEM_PROMPT, build_prompt(lines, assets))
        except LLMError as exc:
            failure = f"matching call failed: {str(exc)[:200]}"
            continue
        try:
            assignment, notes = read_assignment(answer, lines, assets)
        except LLMOutputError as exc:
            failure = f"matching answer was unusable ({exc}): {_snippet(answer)}"
            continue
        return assignment, notes, ""
    return {}, "", failure


def _snippet(answer: str) -> str:
    return " ".join(str(answer).split())[:SNIPPET_CHARS]
