"""Stage: turn product details and the user's brief into a UGC review script (text spine)."""

from app.services import llm
from app.services.llm_json import LLMOutputError, extract_json_object
from app.services.state import (
    SCRIPT_FILE,
    StageError,
    compute_spine,
    script_fingerprint,
    write_json,
)

SYSTEM_PROMPT = (
    "You write short-form UGC product review scripts in casual Bahasa Indonesia for TikTok/Reels "
    "style videos. You always answer with a single valid JSON object and nothing else: no markdown, "
    "no explanations."
)

USER_PROMPT_TEMPLATE = """Tulis script review produk UGC berdasarkan data berikut.

Nama produk: {name}
Poin penting: {points}
Arahan kreatif dari user: {direction}
Gaya teks overlay yang diminta: {overlay_style}

Aturan:
- 6 sampai 9 baris, urutan section: hook, problem, solution, proof, cta.
- Hook maksimal 12 kata dan langsung menarik perhatian di 3 detik pertama.
- Baris "say" adalah yang diucapkan: gaya santai, seperti orang bercerita, maksimal 18 kata per baris.
- Angka, harga, dan spesifikasi TIDAK diucapkan: taruh di "overlay" (teks pendek di layar).
- "hint" adalah deskripsi singkat visual yang cocok untuk baris itu.
- "overlay" berupa string pendek atau null.
- Ikuti arahan kreatif user kalau diisi: itu keinginan mereka soal gaya video, alur, dan teksnya.

Balas dengan JSON persis seperti ini:
{{"lines": [{{"section": "hook", "say": "...", "hint": "...", "overlay": null}}]}}"""

VALID_SECTIONS = {"hook", "problem", "solution", "proof", "cta"}
NOT_GIVEN = "(tidak diisi)"


def parse_script(raw: str) -> list[dict]:
    try:
        data = extract_json_object(raw)
    except LLMOutputError as exc:
        raise StageError(f"LLM script was unusable: {exc}") from exc
    raw_lines = data.get("lines")
    if not isinstance(raw_lines, list) or len(raw_lines) < 3:
        raise StageError("LLM script must contain at least 3 lines.")
    parsed: list[dict] = []
    for index, item in enumerate(raw_lines):
        section = str(item.get("section", "")).lower()
        say = str(item.get("say", "")).strip()
        if not say:
            continue
        if section not in VALID_SECTIONS:
            section = (
                "solution" if 0 < index < len(raw_lines) - 1 else ("hook" if index == 0 else "cta")
            )
        parsed.append(
            {
                "section": section,
                "say": say,
                "hint": str(item.get("hint", "")).strip(),
                "overlay": item.get("overlay") or None,
            }
        )
    if len(parsed) < 3:
        raise StageError("LLM script has too few usable lines.")
    return parsed


async def run(ctx: dict) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    state = ctx["state"]
    product = state["inputs"].get("product", {})
    brief = state.get("brief") or {}
    prompt = USER_PROMPT_TEMPLATE.format(
        name=product.get("name") or ctx.get("title", "the product"),
        points=product.get("points") or "not provided",
        direction=brief.get("direction") or NOT_GIVEN,
        overlay_style=brief.get("overlay_style") or NOT_GIVEN,
    )
    raw = await llm.complete(SYSTEM_PROMPT, prompt)
    lines = parse_script(raw)
    timeline = compute_spine(
        lines,
        settings.reading_words_per_second,
        settings.min_card_seconds,
        settings.line_pause_seconds,
    )
    write_json(ctx["dir"], SCRIPT_FILE, {"lines": lines})
    ctx["state"]["timeline"] = timeline
    ctx["state"]["script_fingerprint"] = script_fingerprint(ctx["state"])
