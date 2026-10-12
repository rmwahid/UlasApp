"""The locked beat library: the pieces a review script can be made of, and the shapes built from them.

A beat is one named moment of a review script. It carries the prompt fragment the model is asked to
write, the word budget for its line, and whether it may appear more than once. The user picks beats
and puts them in order; the prompts stay ours, so a shape the user builds can never ask for a beat the
pipeline cannot render. Two preset shapes are simply saved beat lists, which is why the editor and the
presets are the same machinery.

Labels are UI copy (English, like the rest of the interface); the prompt fragments are product content
and stay in Indonesian, because that is the language of the script they produce.
"""

BEATS: dict[str, dict] = {
    "hook": {
        "label": "Hook",
        "prompt": "Pembuka yang berdiri sendiri dan bikin penonton berhenti scroll.",
        "max_words": 12,
        "once_only": True,
    },
    "bait": {
        "label": "Bait",
        "prompt": "Pancingan rasa ingin tahu: sesumbar atau pertanyaan yang jawabannya ada nanti.",
        "max_words": 14,
        "once_only": True,
    },
    "problem": {
        "label": "Problem",
        "prompt": "Masalah yang dirasakan penonton sebelum tahu produk ini.",
        "max_words": 18,
        "once_only": False,
    },
    "reveal": {
        "label": "Reveal",
        "prompt": "Perkenalkan produknya: apa ini dan untuk siapa.",
        "max_words": 16,
        "once_only": True,
    },
    "demo": {
        "label": "Demo",
        "prompt": "Produknya dipakai atau dibuka langsung di depan kamera.",
        "max_words": 16,
        "once_only": False,
    },
    "solution": {
        "label": "Solution",
        "prompt": "Bagaimana produk ini menyelesaikan masalah tadi.",
        "max_words": 18,
        "once_only": False,
    },
    "proof": {
        "label": "Proof",
        "prompt": "Bukti nyata: satu uji atau pengalaman yang bisa dilihat sendiri.",
        "max_words": 18,
        "once_only": False,
    },
    "comparison": {
        "label": "Comparison",
        "prompt": "Bandingkan dengan yang biasa dipakai penonton: apa yang beda.",
        "max_words": 18,
        "once_only": False,
    },
    "objection": {
        "label": "Objection",
        "prompt": "Jawab keraguan yang paling mungkin muncul, sebagai fakta, bukan bantahan.",
        "max_words": 18,
        "once_only": False,
    },
    "social": {
        "label": "Social proof",
        "prompt": "Tanda orang lain memakainya, hanya dari fakta yang ada di Poin penting.",
        "max_words": 16,
        "once_only": False,
    },
    "cta": {
        "label": "CTA",
        "prompt": "Ajakan penutup yang kecil dan jelas.",
        "max_words": 16,
        "once_only": True,
    },
}

SHAPES: dict[str, dict] = {
    "ulasan": {
        "label": "Ulasan",
        "character": "Alur review klasik: masalah dulu, lalu produk menjawabnya.",
        "beats": ["hook", "problem", "solution", "proof", "cta"],
    },
    "reveal": {
        "label": "Reveal",
        "character": "Produk lebih cepat muncul, lalu dipakai dan dibuktikan.",
        "beats": ["hook", "reveal", "demo", "proof", "cta"],
    },
}

CUSTOM_SHAPE = "custom"
DEFAULT_SHAPE = "ulasan"
MIN_BEATS = 4
MAX_BEATS = 9


class BeatError(ValueError):
    """Raised when a shape asks for beats that cannot be rendered."""


def resolve_beats(shape: str, custom_beats: list[str] | None = None) -> list[str]:
    """The beat order a style block stands for, presets and custom shapes alike."""
    if shape == CUSTOM_SHAPE:
        beats = list(custom_beats or [])
    elif shape in SHAPES:
        beats = list(SHAPES[shape]["beats"])
    else:
        raise BeatError(f"unknown shape '{shape}'")
    validate_beats(beats)
    return beats


def validate_beats(beats: list[str]) -> None:
    """Refuse a shape the pipeline could not turn into a watchable video.

    The invariants exist so a custom shape cannot produce something with no opening, no closing, or a
    beat that repeats a moment (a second reveal is a different video, not a longer one).
    """
    if not MIN_BEATS <= len(beats) <= MAX_BEATS:
        raise BeatError(f"a shape needs {MIN_BEATS} to {MAX_BEATS} beats, got {len(beats)}")
    unknown = [beat for beat in beats if beat not in BEATS]
    if unknown:
        raise BeatError(f"unknown beats: {', '.join(sorted(set(unknown)))}")
    if beats[0] != "hook":
        raise BeatError("a shape has to open with the hook beat")
    if beats[-1] != "cta":
        raise BeatError("a shape has to close with the cta beat")
    repeated = [beat for beat in beats if BEATS[beat]["once_only"] and beats.count(beat) > 1]
    if repeated:
        raise BeatError(f"these beats can only appear once: {', '.join(sorted(set(repeated)))}")


def shape_rules(beats: list[str]) -> str:
    """The order rules the script prompt is built from, one line per beat."""
    lines = []
    for index, beat in enumerate(beats, start=1):
        spec = BEATS[beat]
        repeats = "" if spec["once_only"] else " (boleh diulang dengan isi berbeda)"
        detail = spec["prompt"]
        lines.append(f"{index}. {beat}{repeats}: {detail} Maksimal {spec['max_words']} kata.")
    return "\n".join(lines)


def labels(beats: list[str]) -> list[str]:
    """Beat labels for the UI, in order."""
    return [BEATS[beat]["label"] for beat in beats]
