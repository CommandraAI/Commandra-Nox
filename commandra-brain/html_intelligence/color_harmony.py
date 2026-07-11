"""Color Harmony Engine -- derives a small, disciplined palette from one
brand hue rather than letting a model pick arbitrary colors per component."""

from __future__ import annotations

import colorsys
from dataclasses import dataclass, field


def _hex_to_hsl(hex_color: str) -> tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h, s, l


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h % 1.0, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


@dataclass
class Palette:
    brand: str
    scheme: str
    primary: str
    accent: str
    neutrals: list[str] = field(default_factory=list)
    success: str = "#16a34a"
    warning: str = "#d97706"
    danger: str = "#dc2626"

    def as_dict(self) -> dict:
        return {
            "brand": self.brand, "scheme": self.scheme, "primary": self.primary, "accent": self.accent,
            "neutrals": self.neutrals, "success": self.success, "warning": self.warning, "danger": self.danger,
        }


def generate_palette(brand_hex: str, scheme: str = "complementary") -> Palette:
    h, s, l = _hex_to_hsl(brand_hex)

    accent_hue = {
        "complementary": h + 0.5,
        "analogous": h + (1 / 12),
        "triadic": h + (1 / 3),
        "split_complementary": h + 0.5 - (1 / 12),
    }.get(scheme, h + 0.5)

    accent = _hsl_to_hex(accent_hue, min(1.0, s), l)
    neutrals = [_hsl_to_hex(h, min(0.08, s * 0.15), lightness) for lightness in (0.98, 0.9, 0.7, 0.5, 0.3, 0.15)]

    return Palette(brand=brand_hex, scheme=scheme, primary=brand_hex, accent=accent, neutrals=neutrals)


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    """WCAG relative-luminance contrast ratio between two hex colors."""

    def _luminance(hex_color: str) -> float:
        hex_color = hex_color.lstrip("#")
        channels = []
        for i in (0, 2, 4):
            c = int(hex_color[i : i + 2], 16) / 255
            channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
        r, g, b = channels
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    l1, l2 = sorted([_luminance(hex_a), _luminance(hex_b)], reverse=True)
    return round((l1 + 0.05) / (l2 + 0.05), 2)


def meets_wcag_aa(foreground: str, background: str, large_text: bool = False) -> bool:
    ratio = contrast_ratio(foreground, background)
    return ratio >= (3.0 if large_text else 4.5)
