"""Design Token Generator -- packages Typography/Color/Spacing decisions
into a single portable token set (JSON + CSS variables + Tailwind config
fragment) so every generated component pulls from the same source of truth
instead of hardcoding values."""

from __future__ import annotations

import json
from dataclasses import dataclass

from html_intelligence.color_harmony import Palette
from html_intelligence.typography_engine import TypeScale

_SPACING_SCALE_PX = [0, 4, 8, 12, 16, 24, 32, 48, 64, 96]
_RADIUS_SCALE_PX = {"none": 0, "sm": 4, "md": 8, "lg": 12, "xl": 16, "full": 9999}


@dataclass
class DesignTokens:
    palette: Palette
    type_scale: TypeScale
    spacing_px: list[int]
    radius_px: dict

    def as_dict(self) -> dict:
        return {
            "palette": self.palette.as_dict(),
            "typography": self.type_scale.as_dict(),
            "spacingPx": self.spacing_px,
            "radiusPx": self.radius_px,
        }

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2)

    def as_css_variables(self) -> str:
        lines = [f"  --color-primary: {self.palette.primary};", f"  --color-accent: {self.palette.accent};"]
        for i, hex_val in enumerate(self.palette.neutrals):
            lines.append(f"  --color-neutral-{i}: {hex_val};")
        for step in self.spacing_px:
            lines.append(f"  --space-{step}: {step}px;")
        for name, px in self.radius_px.items():
            lines.append(f"  --radius-{name}: {px}px;")
        return ":root {\n" + "\n".join(lines) + "\n}"

    def as_tailwind_theme_fragment(self) -> str:
        colors = {"primary": self.palette.primary, "accent": self.palette.accent}
        colors.update({f"neutral-{i}": hex_val for i, hex_val in enumerate(self.palette.neutrals)})
        spacing = {str(step): f"{step}px" for step in self.spacing_px}
        theme = {"extend": {"colors": colors, "spacing": spacing, "borderRadius": {k: f"{v}px" for k, v in self.radius_px.items()}}}
        return "theme: " + json.dumps(theme, indent=2)


def generate_design_tokens(palette: Palette, type_scale: TypeScale) -> DesignTokens:
    return DesignTokens(palette=palette, type_scale=type_scale, spacing_px=_SPACING_SCALE_PX, radius_px=_RADIUS_SCALE_PX)
