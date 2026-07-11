"""Typography Engine -- produces a coherent type scale and pairing rules."""

from __future__ import annotations

from dataclasses import dataclass, field

# Major third (1.25) scale from a 16px base -- a safe, widely used ratio
# that gives clear hierarchy without huge jumps.
_SCALE_RATIO = 1.25
_BASE_PX = 16

_ROLE_STEPS = {
    "display": 4, "h1": 3, "h2": 2, "h3": 1, "body": 0, "small": -1, "caption": -2,
}

_FONT_PAIRINGS = {
    "modern_saas": {"heading": "Inter", "body": "Inter", "mono": "JetBrains Mono"},
    "editorial": {"heading": "Fraunces", "body": "Inter", "mono": "IBM Plex Mono"},
    "playful": {"heading": "Poppins", "body": "Inter", "mono": "Fira Code"},
    "technical": {"heading": "IBM Plex Sans", "body": "IBM Plex Sans", "mono": "IBM Plex Mono"},
    "luxury": {"heading": "Playfair Display", "body": "Lato", "mono": "Space Mono"},
}


@dataclass
class TypeScale:
    pairing: str
    fonts: dict = field(default_factory=dict)
    sizes_px: dict = field(default_factory=dict)
    line_heights: dict = field(default_factory=dict)
    weights: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"pairing": self.pairing, "fonts": self.fonts, "sizesPx": self.sizes_px, "lineHeights": self.line_heights, "weights": self.weights}

    def as_css_variables(self) -> str:
        lines = [f"  --font-{k}: '{v}', sans-serif;" for k, v in self.fonts.items()]
        lines += [f"  --text-{role}: {px}px;" for role, px in self.sizes_px.items()]
        return ":root {\n" + "\n".join(lines) + "\n}"


def generate_type_scale(pairing: str = "modern_saas") -> TypeScale:
    fonts = _FONT_PAIRINGS.get(pairing, _FONT_PAIRINGS["modern_saas"])
    sizes = {role: round(_BASE_PX * (_SCALE_RATIO ** step)) for role, step in _ROLE_STEPS.items()}
    line_heights = {
        "display": 1.1, "h1": 1.15, "h2": 1.2, "h3": 1.3, "body": 1.6, "small": 1.5, "caption": 1.4,
    }
    weights = {"display": 700, "h1": 700, "h2": 600, "h3": 600, "body": 400, "small": 400, "caption": 500}
    return TypeScale(pairing=pairing, fonts=fonts, sizes_px=sizes, line_heights=line_heights, weights=weights)


def available_pairings() -> list[str]:
    return sorted(_FONT_PAIRINGS.keys())
