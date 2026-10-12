"""Stage: turn product details and the user's brief into a UGC review script (text spine)."""

from app.services import llm
from app.services.beats import DEFAULT_SHAPE, resolve_beats, shape_rules
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
Teks dan fakta yang wajib tampil di layar: {overlay_style}

Susunan video (persis {count} baris, satu baris untuk satu beat, urutannya tidak boleh diubah):
{beats}

Aturan:
- Isi "section" dengan nama beat baris itu, persis seperti tertulis di susunan di atas.
- Hook ditulis paling dulu dan harus berdiri sendiri: jelas sebelum 3 detik, dan baris-baris awal
  harus gamblang dalam 5 detik pertama. Bagian tengah adalah hal paling menarik dari produk ini,
  bukan daftar fitur.
- Baris "say" adalah yang diucapkan: gaya santai, seperti orang bercerita, maksimal sesuai batas kata
  beat-nya.
- Setiap fakta di "Poin penting" harus diturunkan dulu sampai ke gunanya buat pembeli: yang diucapkan
  adalah gunanya ("jam tetap jalan walau kena air"), bukan spesifikasinya; angka dan istilah teknisnya
  masuk "overlay". Fakta yang tidak bisa sampai ke guna pembeli jangan dipakai.
- Satu baris = satu poin baru. Dua baris tidak boleh membahas ide yang sama dengan kalimat berbeda;
  kalau beat yang sama muncul dua kali (misalnya dua proof), buktinya harus hal yang berbeda.
- Variasikan bentuk dan panjang kalimat: jangan memakai pola pembuka yang sama di semua baris, dan
  jangan membuat semua baris sama panjang.
- Minimal satu baris harus dibuktikan langsung di kamera: "hint"-nya adalah aksi atau close-up yang
  membuktikan klaim baris itu (disiram air lalu tetap menyala, dijatuhkan lalu tetap utuh), bukan
  sekadar suasana.
- Jangan mengarang apa pun: jumlah pembeli, testimoni, rating, sertifikasi, atau batas waktu promo.
  Social proof dan urgensi hanya boleh muncul kalau ada di "Poin penting"; kalau tidak ada, tutup
  dengan ajakan kecil yang jelas.
- Jangan pakai superlatif yang tidak bisa dicek ("paling bagus", "terbaik di kelasnya"): pakai angka
  atau perbandingan yang benar.
- Hook harus dibayar tuntas di dalam video: apa pun yang dijanjikan baris pertama harus dijelaskan di
  baris berikutnya, jangan menggantung.
- Kalau "Poin penting" menyebut satu keterbatasan yang benar, boleh ditulis sekali setelah baris
  proof (jangan di hook, jangan dikarang). Kalau tidak ada, jangan menciptakan.
- Angka, harga, dan spesifikasi TIDAK diucapkan: taruh di "overlay" (teks pendek di layar).
- "overlay" maksimal 4 kata, huruf kapital, tanpa emoji: itu label yang dibaca sekilas, bukan kalimat.
- Setiap "overlay" harus label yang berbeda: jangan mengulang kata atau angka yang sama di overlay
  lain. Kalau brief meminta harga selalu tampil, taruh harganya di paling banyak dua overlay.
- "hint" adalah satu momen nyata yang bisa direkam: tulis apa yang terlihat di frame. Sebut nama
  produknya di sebagian hint saja, dan minimal satu hint harus menampilkan produknya secara langsung.
- Hindari klise marketing ("solusi terbaik", "revolusioner", "wajib punya", "tingkatkan
  produktivitasmu"): pakai hal konkret yang bisa dilihat atau dirasakan pemakai.
- Semua harus terasa dibuat khusus untuk produk ini, bukan bisa dipakai produk apa pun.
- Ikuti arahan kreatif user kalau diisi: itu keinginan mereka soal gaya video, alur, dan teksnya.

Balas dengan JSON persis seperti ini:
{{"lines": [{{"section": "{example_section}", "say": "...", "hint": "...", "overlay": null}}]}}"""

NOT_GIVEN = "(tidak diisi)"


def build_prompt(
    name: str, points: str, direction: str, overlay_style: str, beats: list[str]
) -> str:
    """The user prompt for one script, with the chosen shape's beats and rules filled in."""
    return USER_PROMPT_TEMPLATE.format(
        name=name or "produk ini",
        points=points or NOT_GIVEN,
        direction=direction or NOT_GIVEN,
        overlay_style=overlay_style or NOT_GIVEN,
        beats=shape_rules(beats),
        count=len(beats),
        example_section=beats[1] if len(beats) > 1 else beats[0],
    )


def parse_script(raw: str, beats: list[str] | None = None) -> list[dict]:
    order = list(beats) if beats else resolve_beats(DEFAULT_SHAPE)
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
        if section not in order:
            if index == 0:
                section = order[0]
            elif index == len(raw_lines) - 1:
                section = order[-1]
            else:
                section = order[len(order) // 2]
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


def apply_shape(lines: list[dict], beats: list[str]) -> list[dict]:
    """Give the lines the shape's order, because the prompt asks for one line per beat.

    The model's own labels are advisory: a line that arrives with the wrong beat name, or an extra
    line, still ends up renderable, and the video keeps its opening hook and its closing call to
    action, which the spine and QA both rely on.
    """
    shaped = list(lines[: len(beats)])
    for index, line in enumerate(shaped):
        line["section"] = beats[index]
    if shaped:
        shaped[-1]["section"] = beats[-1]
    return shaped


async def run(ctx: dict) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    state = ctx["state"]
    product = state["inputs"].get("product", {})
    brief = state.get("brief") or {}
    style = state.get("style") or {}
    beats = resolve_beats(style.get("shape") or DEFAULT_SHAPE, style.get("beats"))
    prompt = build_prompt(
        name=product.get("name") or ctx.get("title", "the product"),
        points=product.get("points") or "",
        direction=brief.get("direction") or "",
        overlay_style=brief.get("overlay_style") or "",
        beats=beats,
    )
    raw = await llm.complete(SYSTEM_PROMPT, prompt)
    lines = apply_shape(parse_script(raw, beats), beats)
    timeline = compute_spine(
        lines,
        settings.reading_words_per_second,
        settings.min_card_seconds,
        settings.line_pause_seconds,
        settings.hook_min_card_seconds,
    )
    write_json(ctx["dir"], SCRIPT_FILE, {"lines": lines})
    ctx["state"]["timeline"] = timeline
    ctx["state"]["script_fingerprint"] = script_fingerprint(ctx["state"])
