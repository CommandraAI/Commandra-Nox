"""Animation Planner -- purposeful, restrained motion specs, never
decoration for its own sake, always respecting prefers-reduced-motion."""

from __future__ import annotations

from dataclasses import dataclass, field

_MOTION_PRESETS = {
    "entrance_fade_up": {"property": "opacity, transform", "from": "opacity:0; translateY(12px)", "to": "opacity:1; translateY(0)", "duration_ms": 300, "easing": "ease-out"},
    "hover_lift": {"property": "transform, box-shadow", "from": "translateY(0)", "to": "translateY(-2px)", "duration_ms": 150, "easing": "ease-out"},
    "press_scale": {"property": "transform", "from": "scale(1)", "to": "scale(0.97)", "duration_ms": 100, "easing": "ease-in-out"},
    "modal_scale_in": {"property": "opacity, transform", "from": "opacity:0; scale(0.95)", "to": "opacity:1; scale(1)", "duration_ms": 200, "easing": "ease-out"},
    "stagger_list": {"property": "opacity, transform", "from": "opacity:0; translateY(8px)", "to": "opacity:1; translateY(0)", "duration_ms": 250, "easing": "ease-out", "stagger_ms": 40},
}


@dataclass
class MotionSpec:
    name: str
    css_transition: str
    stagger_ms: int | None = None
    reduced_motion_fallback: str = "opacity 150ms ease-out"

    def as_dict(self) -> dict:
        return {"name": self.name, "cssTransition": self.css_transition, "staggerMs": self.stagger_ms, "reducedMotionFallback": self.reduced_motion_fallback}


def plan_animation(preset: str) -> MotionSpec:
    spec = _MOTION_PRESETS.get(preset, _MOTION_PRESETS["entrance_fade_up"])
    transition = f"{spec['property']} {spec['duration_ms']}ms {spec['easing']}"
    return MotionSpec(name=preset, css_transition=transition, stagger_ms=spec.get("stagger_ms"))


def reduced_motion_guard() -> str:
    return (
        "@media (prefers-reduced-motion: reduce) {\n"
        "  *, *::before, *::after {\n"
        "    animation-duration: 0.01ms !important;\n"
        "    animation-iteration-count: 1 !important;\n"
        "    transition-duration: 0.01ms !important;\n"
        "  }\n"
        "}\n"
    )


def available_presets() -> list[str]:
    return sorted(_MOTION_PRESETS.keys())
