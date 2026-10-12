import pytest

from app.services import tones


def test_every_tone_defines_every_token_the_template_reads():
    """The composition replaces tokens without falling back, so a missing token would break a render."""
    reference = set(tones.TONES[tones.DEFAULT_TONE]["tokens"])
    for name, tone in tones.TONES.items():
        assert set(tone["tokens"]) == reference, f"{name} has a different token set"


def test_resolved_tokens_cover_the_derived_values():
    tokens = tones.resolve(None)
    for key in (
        "shade",
        "hero_bg",
        "badge_fill",
        "badge_text",
        "badge_border",
        "energy",
        "badge_style",
    ):
        assert tokens[key]
    assert tokens["badge_style"] == tones.DEFAULT_BADGE


def test_a_missing_style_block_falls_back_to_the_default_tone():
    tokens = tones.resolve({})
    assert tokens["accent"] == tones.TONES[tones.DEFAULT_TONE]["tokens"]["accent"]
    assert tokens["energy"] == tones.DEFAULT_ENERGY


def test_the_accent_override_wins():
    tokens = tones.resolve({"tone": "bersih", "accent": "#123456"})
    assert tokens["accent"] == "#123456"
    assert tokens["badge_fill"] == "#123456"


def test_energy_scales_the_motion_it_promises_to_scale():
    calm = tones.resolve({"energy": "tenang"})
    normal = tones.resolve({"energy": "normal"})
    punchy = tones.resolve({"energy": "energik"})
    assert float(calm["zoom_to"]) < float(normal["zoom_to"]) < float(punchy["zoom_to"])
    assert (
        float(calm["entry_travel"]) < float(normal["entry_travel"]) < float(punchy["entry_travel"])
    )
    assert (
        float(calm["entry_duration"])
        > float(normal["entry_duration"])
        > float(punchy["entry_duration"])
    )


def test_the_badge_styles_change_the_badge_tokens():
    pill = tones.resolve({"badge": "pill"})
    underline = tones.resolve({"badge": "underline"})
    plain = tones.resolve({"badge": "plain"})
    assert pill["badge_fill"] == pill["accent"]
    assert underline["badge_fill"] == "transparent" and underline["badge_border"].startswith("6px")
    assert plain["badge_fill"] == "transparent" and plain["badge_border"] == "0"


def test_an_unknown_choice_is_refused():
    with pytest.raises(tones.ToneError, match="unknown tone"):
        tones.resolve({"tone": "neon"})
    with pytest.raises(tones.ToneError, match="unknown energy"):
        tones.resolve({"energy": "hyper"})
    with pytest.raises(tones.ToneError, match="unknown badge style"):
        tones.resolve({"badge": "sticker"})


def test_the_catalog_carries_what_the_panel_draws():
    catalog = tones.catalog()
    assert [tone["id"] for tone in catalog] == list(tones.TONES)
    for entry in catalog:
        assert entry["label"] and entry["character"]
        assert set(entry["preview"]) == {"bg", "ink", "accent", "accent_ink", "card_bg"}


def test_treatments_read_from_the_tone():
    tokens = tones.resolve({"tone": "bersih"})
    assert tones.treat(tokens, "first") == "hero"
    assert tones.treat(tokens, "middle") == "card"
    assert tones.treat(tokens, "last") == "plate"
