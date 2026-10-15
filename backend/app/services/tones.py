"""Tone presets: how a video presents itself, as tokens the composition reads.

A tone carries typography, palette, badge treatment and motion energy, plus how the first, middle and
last beats are treated. Colours and fonts the seller owns belong to the phase 5 brand kit; a tone is a
designed default that stands on its own, and the three overrides (accent, energy, badge) are deliberate
exceptions a user can set per project.

Token names are the contract between this module and the composition template. Every tone defines every
token, so the template never has to fall back; `tests/services/test_tones.py` holds that promise.
"""

from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from app.services.state import Style

DEFAULT_TONE = "bersih"
DEFAULT_ENERGY = "normal"
DEFAULT_BADGE = "pill"

ENERGIES = ("tenang", "normal", "energik")
BADGES = ("pill", "underline", "plain")

# Motion scaling per energy: how far the camera pushes in, how far text travels, and how fast it lands.
ENERGY_SCALE: dict[str, dict[str, float]] = {
    "tenang": {"zoom": 0.6, "travel": 0.6, "speed": 1.35},
    "normal": {"zoom": 1.0, "travel": 1.0, "speed": 1.0},
    "energik": {"zoom": 1.6, "travel": 1.5, "speed": 0.72},
}

# How a beat position is treated. `hero` is type over the picture with no card, `card` is the standard
# bottom card, `plate` is a solid accent block.
TREATMENTS = ("hero", "card", "plate")


class Tone(TypedDict):
    """One tone preset: its UI copy plus the token map the composition template reads."""

    label: str
    character: str
    tokens: dict[str, str]


TONES: dict[str, Tone] = {
    "bersih": {
        "label": "Bersih",
        "character": "Netral dan rapi: teks tebal sedang, gerak tenang.",
        "tokens": {
            "bg": "#0b0f14",
            "ink": "#f4f7fb",
            "ink_soft": "#c8d2de",
            "accent": "#f5b52e",
            "accent_ink": "#14181f",
            "card_bg": "rgba(10, 13, 18, .72)",
            "card_border": "1px solid rgba(255, 255, 255, .08)",
            "card_blur": "10px",
            "card_radius": "24px",
            "card_padding": "34px 42px",
            "font": "system-ui, -apple-system, 'Segoe UI', sans-serif",
            "line_size": "60px",
            "line_weight": "700",
            "line_case": "none",
            "line_spacing": "0",
            "badge_size": "44px",
            "badge_weight": "800",
            "badge_radius": "999px",
            "badge_pad": "12px 30px",
            "zoom_from": "1",
            "zoom_to": "1.06",
            "entry_travel": "60",
            "entry_duration": "0.5",
            "entry_ease": "power3.out",
            "treat_first": "hero",
            "treat_middle": "card",
            "treat_last": "plate",
        },
    },
    "tegas": {
        "label": "Tegas",
        "character": "Kontras tinggi dan cepat: huruf berat, potongan tegas.",
        "tokens": {
            "bg": "#07080b",
            "ink": "#ffffff",
            "ink_soft": "#c3c9d4",
            "accent": "#ff4d2e",
            "accent_ink": "#12060a",
            "card_bg": "rgba(7, 8, 11, .82)",
            "card_border": "2px solid rgba(255, 255, 255, .14)",
            "card_blur": "6px",
            "card_radius": "10px",
            "card_padding": "30px 36px",
            "font": "'Arial Narrow', 'Helvetica Neue', system-ui, sans-serif",
            "line_size": "66px",
            "line_weight": "800",
            "line_case": "uppercase",
            "line_spacing": "-0.01em",
            "badge_size": "46px",
            "badge_weight": "800",
            "badge_radius": "8px",
            "badge_pad": "12px 26px",
            "zoom_from": "1",
            "zoom_to": "1.14",
            "entry_travel": "90",
            "entry_duration": "0.34",
            "entry_ease": "expo.out",
            "treat_first": "hero",
            "treat_middle": "card",
            "treat_last": "plate",
        },
    },
    "hangat": {
        "label": "Hangat",
        "character": "Lembut dan santai: warna hangat, gerak lambat.",
        "tokens": {
            "bg": "#1a1512",
            "ink": "#f7efe4",
            "ink_soft": "#d8c8b6",
            "accent": "#ffb07c",
            "accent_ink": "#2a1a10",
            "card_bg": "rgba(26, 21, 18, .74)",
            "card_border": "1px solid rgba(255, 232, 214, .12)",
            "card_blur": "14px",
            "card_radius": "28px",
            "card_padding": "36px 44px",
            "font": "'Segoe UI', 'Trebuchet MS', system-ui, sans-serif",
            "line_size": "58px",
            "line_weight": "600",
            "line_case": "none",
            "line_spacing": "0.005em",
            "badge_size": "42px",
            "badge_weight": "700",
            "badge_radius": "999px",
            "badge_pad": "14px 32px",
            "zoom_from": "1",
            "zoom_to": "1.04",
            "entry_travel": "40",
            "entry_duration": "0.7",
            "entry_ease": "power2.out",
            "treat_first": "hero",
            "treat_middle": "card",
            "treat_last": "plate",
        },
    },
    "toko": {
        "label": "Toko",
        "character": "Ramai dan menonjol: aksen terang, badge besar, ritme cepat.",
        "tokens": {
            "bg": "#101820",
            "ink": "#ffffff",
            "ink_soft": "#cfd8e3",
            "accent": "#ffd400",
            "accent_ink": "#1a1400",
            "card_bg": "rgba(16, 24, 32, .80)",
            "card_border": "2px solid rgba(255, 212, 0, .35)",
            "card_blur": "8px",
            "card_radius": "16px",
            "card_padding": "32px 40px",
            "font": "'Segoe UI', system-ui, sans-serif",
            "line_size": "62px",
            "line_weight": "800",
            "line_case": "none",
            "line_spacing": "0",
            "badge_size": "50px",
            "badge_weight": "900",
            "badge_radius": "12px",
            "badge_pad": "14px 32px",
            "zoom_from": "1",
            "zoom_to": "1.10",
            "entry_travel": "70",
            "entry_duration": "0.4",
            "entry_ease": "back.out(1.4)",
            "treat_first": "plate",
            "treat_middle": "card",
            "treat_last": "plate",
        },
    },
}


class ToneError(ValueError):
    """Raised when a style block asks for a tone, energy or badge that does not exist."""


def treat(tokens: dict[str, str], position: str) -> str:
    """The treatment for the first, middle or last beat of a video."""
    if position == "first":
        return tokens["treat_first"]
    if position == "last":
        return tokens["treat_last"]
    return tokens["treat_middle"]


def resolve(style: "Style | None") -> dict[str, str]:
    """Final tokens for a project: the chosen tone, with the user's overrides applied.

    A missing or empty style block falls back to the default tone, so projects created before the
    style system existed still render.
    """
    name = (style.get("tone") if style else None) or DEFAULT_TONE
    if name not in TONES:
        raise ToneError(f"unknown tone '{name}'")
    energy = (style.get("energy") if style else None) or DEFAULT_ENERGY
    if energy not in ENERGIES:
        raise ToneError(f"unknown energy '{energy}'")
    badge = (style.get("badge") if style else None) or DEFAULT_BADGE
    if badge not in BADGES:
        raise ToneError(f"unknown badge style '{badge}'")

    tokens: dict[str, str] = dict(TONES[name]["tokens"])
    accent = style.get("accent") if style else None
    if accent:
        tokens["accent"] = accent

    scale = ENERGY_SCALE[energy]
    zoom_to = float(tokens["zoom_to"])
    tokens["zoom_to"] = f"{1 + (zoom_to - 1) * scale['zoom']:.3f}"
    tokens["entry_travel"] = f"{float(tokens['entry_travel']) * scale['travel']:.0f}"
    tokens["entry_duration"] = f"{float(tokens['entry_duration']) * scale['speed']:.2f}"
    tokens["badge_style"] = badge
    tokens["energy"] = energy

    # Derived values, so every tone gets them for free and the template never has to guess: the
    # bottom scrim, the wash behind the opening card, and the badge's colours per style.
    bg = tokens["bg"]
    tokens["shade"] = (
        f"linear-gradient(180deg, {bg}00 0%, {bg}e6 80%)"
        if _is_hex(bg)
        else "linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,.86) 80%)"
    )
    tokens["hero_bg"] = (
        f"linear-gradient(180deg, {bg}00 16%, {bg}cc 44%, {bg}00 74%)"
        if _is_hex(bg)
        else "linear-gradient(180deg, rgba(0,0,0,0) 16%, rgba(0,0,0,.8) 44%, rgba(0,0,0,0) 74%)"
    )
    if badge == "underline":
        tokens["badge_fill"] = "transparent"
        tokens["badge_text"] = tokens["accent"]
        tokens["badge_border"] = f"6px solid {tokens['accent']}"
        tokens["badge_radius"] = "0"
    elif badge == "plain":
        tokens["badge_fill"] = "transparent"
        tokens["badge_text"] = tokens["accent"]
        tokens["badge_border"] = "0"
        tokens["badge_radius"] = "0"
    else:
        tokens["badge_fill"] = tokens["accent"]
        tokens["badge_text"] = tokens["accent_ink"]
        tokens["badge_border"] = "0"
    return tokens


def _is_hex(color: str) -> bool:
    """Whether a colour can be given an alpha channel, which the scrims are built from."""
    value = str(color).lstrip("#")
    return len(value) == 6 and all(char in "0123456789abcdefABCDEF" for char in value)


def catalog() -> list[dict[str, Any]]:
    """What the Style panel shows: names, characters and the colours for a small preview."""
    return [
        {
            "id": name,
            "label": tone["label"],
            "character": tone["character"],
            "preview": {
                key: tone["tokens"][key] for key in ("bg", "ink", "accent", "accent_ink", "card_bg")
            },
        }
        for name, tone in TONES.items()
    ]
