"""Draft a brief from what the project already knows, so the user can edit instead of staring at a box.

The brief is the user's intent, so this only ever proposes a starting point: it reads the product facts
and what the material shows, then writes a short creative direction and the on-screen facts worth
keeping. Nothing is saved here; the user edits the fields and saves them like any other brief.
"""

from app.services import llm
from app.services.llm_json import LLMOutputError, extract_json_object
from app.services.state import StageError

SYSTEM_PROMPT = (
    "You write short creative briefs for short-form product review videos in casual Bahasa Indonesia. "
    "You always answer with a single valid JSON object and nothing else."
)

USER_PROMPT_TEMPLATE = """Susun draf brief untuk video review produk ini.

Nama produk: {name}
Poin penting: {points}
Material yang akan dipakai:
{material}

Aturan:
- "direction" berisi keinginan untuk video INI: angle, adegan pembuka, hal yang harus kelihatan di
  layar. Satu sampai dua kalimat, konkret, tanpa klise marketing.
- "overlay_style" berisi KONTEN teks di layar: fakta apa yang wajib selalu muncul (harga, garansi,
  ketahanan air), bukan bentuknya (huruf kapital, ukuran, posisi).
- Jangan mengarang fakta yang tidak ada di data di atas.

Balas dengan JSON persis seperti ini:
{{"direction": "...", "overlay_style": "..."}}"""

NOT_DESCRIBED = "(material belum dideskripsikan)"
MAX_FIELD_CHARS = 400


def material_lines(assets: list[dict]) -> str:
    """The described material, one line each, because the vision text is what the shots show."""
    described = [asset for asset in assets if asset.get("description")]
    if not described:
        return NOT_DESCRIBED
    return "\n".join(
        f"- {asset['id']} ({asset.get('kind', 'material')}): {asset['description']}"
        for asset in described
    )


def clean_field(value: object) -> str:
    """One short line of user-facing text, refusing anything that is not a usable string."""
    text = " ".join(str(value or "").split()).strip("\"'` ")
    return text[:MAX_FIELD_CHARS]


async def draft(state: dict) -> dict:
    """A proposed brief: the direction and the on-screen facts, for the user to edit."""
    product = (state.get("inputs") or {}).get("product") or {}
    prompt = USER_PROMPT_TEMPLATE.format(
        name=product.get("name") or "produk ini",
        points=product.get("points") or "(tidak diisi)",
        material=material_lines((state.get("inputs") or {}).get("assets") or []),
    )
    answer = await llm.complete(SYSTEM_PROMPT, prompt)
    try:
        parsed = extract_json_object(answer)
    except LLMOutputError as exc:
        raise StageError(f"The brief draft was unusable: {exc}") from exc
    proposed = {
        "direction": clean_field(parsed.get("direction")),
        "overlay_style": clean_field(parsed.get("overlay_style")),
    }
    if not proposed["direction"]:
        raise StageError("The model returned an empty brief draft. Try again.")
    return proposed
