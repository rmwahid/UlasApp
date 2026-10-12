import pytest

from app.services import beats


def test_the_preset_shapes_are_renderable():
    assert beats.resolve_beats("ulasan") == ["hook", "problem", "solution", "proof", "cta"]
    assert beats.resolve_beats("reveal") == ["hook", "reveal", "demo", "proof", "cta"]
    for shape in beats.SHAPES.values():
        beats.validate_beats(shape["beats"])


def test_an_unknown_shape_is_refused():
    with pytest.raises(beats.BeatError):
        beats.resolve_beats("nope")


def test_a_custom_shape_has_to_open_and_close_correctly():
    with pytest.raises(beats.BeatError, match="open with the hook"):
        beats.validate_beats(["problem", "solution", "proof", "cta"])
    with pytest.raises(beats.BeatError, match="close with the cta"):
        beats.validate_beats(["hook", "problem", "solution", "proof"])
    assert beats.validate_beats(["hook", "bait", "demo", "proof", "cta"]) is None


def test_a_custom_shape_stays_inside_the_beats_that_exist():
    with pytest.raises(beats.BeatError, match="unknown beats"):
        beats.validate_beats(["hook", "unboxing-teleport", "proof", "cta"])
    with pytest.raises(beats.BeatError, match="4 to 9 beats"):
        beats.validate_beats(["hook", "proof", "cta"])
    long_shape = [
        "hook",
        "problem",
        "demo",
        "solution",
        "proof",
        "comparison",
        "objection",
        "demo",
        "cta",
    ]
    assert len(long_shape) == beats.MAX_BEATS
    beats.validate_beats(long_shape)
    with pytest.raises(beats.BeatError, match="4 to 9 beats"):
        beats.validate_beats([*long_shape, "social"])


def test_once_only_beats_cannot_repeat():
    with pytest.raises(beats.BeatError, match="only appear once"):
        beats.validate_beats(["hook", "reveal", "reveal", "proof", "cta"])
    with pytest.raises(beats.BeatError, match="only appear once"):
        beats.validate_beats(["hook", "bait", "proof", "bait", "cta"])
    with pytest.raises(beats.BeatError, match="only appear once"):
        beats.validate_beats(["hook", "demo", "proof", "cta", "cta"])


def test_repeatable_beats_may_appear_twice():
    beats.validate_beats(["hook", "proof", "proof", "demo", "cta"])


def test_shape_rules_describe_every_beat_with_its_budget():
    rules = beats.shape_rules(beats.resolve_beats("reveal"))
    assert "1. hook" in rules
    assert "2. reveal: Perkenalkan produknya" in rules
    assert f"Maksimal {beats.BEATS['hook']['max_words']} kata." in rules
    assert rules.count("Maksimal") == 5


def test_labels_follow_the_order():
    assert beats.labels(["hook", "proof", "cta"]) == ["Hook", "Proof", "CTA"]
