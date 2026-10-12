import json

import pytest

from app.services.beats import resolve_beats
from app.services.stages import script as script_stage

GOOD_SCRIPT = json.dumps(
    {
        "lines": [
            {
                "section": "hook",
                "say": "Jam ini bikin aku lupa pakai yang lain.",
                "hint": "jam di pergelangan",
            },
            {
                "section": "problem",
                "say": "Jam lama aku cepat kotor dan lecet.",
                "hint": "jam lama yang lecet",
            },
            {
                "section": "cta",
                "say": "Cek link di bio sebelum kehabisan.",
                "hint": "tangan menunjuk ke bawah",
            },
        ]
    }
)


def test_parse_script_reads_lines_with_hint_and_overlay():
    lines = script_stage.parse_script(GOOD_SCRIPT)
    assert [line["section"] for line in lines] == ["hook", "problem", "cta"]
    assert lines[0]["hint"] == "jam di pergelangan"
    assert lines[0]["overlay"] is None


def test_parse_script_falls_back_for_an_unknown_section():
    raw = json.dumps(
        {
            "lines": [
                {"section": "intro", "say": "Awal.", "hint": "x"},
                {"section": "nope", "say": "Tengah.", "hint": "x"},
                {"section": "closing", "say": "Akhir.", "hint": "x"},
            ]
        }
    )
    lines = script_stage.parse_script(raw)
    assert [line["section"] for line in lines] == ["hook", "solution", "cta"]


def test_parse_script_refuses_too_few_usable_lines():
    raw = json.dumps({"lines": [{"section": "hook", "say": "Satu.", "hint": "x"}]})
    with pytest.raises(script_stage.StageError):
        script_stage.parse_script(raw)


def test_prompt_teaches_the_rules_that_keep_the_video_watchable():
    prompt = script_stage.build_prompt(
        name="Jam X",
        points="ringan",
        direction="santai",
        overlay_style="kapital",
        beats=resolve_beats("ulasan"),
    )
    assert "Hook ditulis paling dulu" in prompt
    assert "5 detik pertama" in prompt
    assert "maksimal 4 kata" in prompt
    assert "minimal satu hint harus menampilkan produknya secara langsung" in prompt
    assert "klise marketing" in prompt
    assert "khusus untuk produk ini" in prompt
    assert '"hint"' in prompt and '"overlay"' in prompt


def test_prompt_forbids_repeating_itself():
    """Six lines of one short video cannot afford two lines on one idea or one label used six times."""
    prompt = script_stage.build_prompt(
        name="Jam X",
        points="ringan",
        direction="",
        overlay_style="harga selalu tampil",
        beats=resolve_beats("ulasan"),
    )
    assert "Satu baris = satu poin baru" in prompt
    assert "buktinya harus hal yang berbeda" in prompt
    assert "Variasikan bentuk dan panjang kalimat" in prompt
    assert "jangan mengulang kata atau angka yang sama di overlay" in prompt
    assert "paling banyak dua overlay" in prompt


def test_prompt_teaches_how_the_script_sells():
    """The two craft gaps (benefit ladder, proof typing) and the moves that must never happen."""
    prompt = script_stage.build_prompt(
        name="Jam X",
        points="tahan air 50m, harga 99rb",
        direction="",
        overlay_style="",
        beats=resolve_beats("ulasan"),
    )
    assert "diturunkan dulu sampai ke gunanya buat pembeli" in prompt
    assert "angka dan istilah teknisnya" in prompt
    assert "dibuktikan langsung di kamera" in prompt
    assert "Jangan mengarang apa pun" in prompt
    assert "superlatif yang tidak bisa dicek" in prompt
    assert "Hook harus dibayar tuntas" in prompt
    assert "keterbatasan yang benar" in prompt


def test_prompt_is_built_from_the_chosen_shape():
    beats = resolve_beats("reveal")
    prompt = script_stage.build_prompt(
        name="Jam X", points="ringan", direction="", overlay_style="", beats=beats
    )
    assert "persis 5 baris" in prompt
    assert "1. hook" in prompt and "5. cta" in prompt
    assert "reveal" in prompt and "demo" in prompt


def test_apply_shape_gives_the_lines_the_shape_order():
    """The model's own labels are advisory: the shape decides what each line is."""
    lines = [
        {"section": "hook", "say": "a", "hint": "", "overlay": None},
        {"section": "cta", "say": "b", "hint": "", "overlay": None},
        {"section": "proof", "say": "c", "hint": "", "overlay": None},
        {"section": "whatever", "say": "d", "hint": "", "overlay": None},
        {"section": "extra", "say": "e", "hint": "", "overlay": None},
    ]
    shaped = script_stage.apply_shape(lines, resolve_beats("ulasan"))
    assert [line["section"] for line in shaped] == ["hook", "problem", "solution", "proof", "cta"]


def test_apply_shape_keeps_a_short_answer_renderable():
    """Fewer lines than beats still opens with the hook and closes with the call to action."""
    lines = [
        {"section": "hook", "say": "a", "hint": "", "overlay": None},
        {"section": "problem", "say": "b", "hint": "", "overlay": None},
        {"section": "solution", "say": "c", "hint": "", "overlay": None},
    ]
    shaped = script_stage.apply_shape(lines, resolve_beats("ulasan"))
    assert [line["section"] for line in shaped] == ["hook", "problem", "cta"]
