"""Responsive Planner -- defines breakpoints and per-breakpoint layout
behavior so components are designed to reflow deliberately, not by accident."""

from __future__ import annotations

from dataclasses import dataclass, field

_BREAKPOINTS_PX = {"sm": 375, "md": 768, "lg": 1024, "xl": 1440}


@dataclass
class ResponsiveBehavior:
    breakpoint: str
    width_px: int
    layout_note: str


@dataclass
class ResponsivePlan:
    component: str
    behaviors: list[ResponsiveBehavior] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"component": self.component, "behaviors": [b.__dict__ for b in self.behaviors]}


_COMPONENT_RULES = {
    "nav": {"sm": "Collapse into a hamburger menu / drawer.", "md": "Show primary links inline, collapse secondary into a menu.", "lg": "Show full nav inline.", "xl": "Full nav with extra breathing room."},
    "data_table": {"sm": "Switch to a stacked card-per-row layout or enable horizontal scroll.", "md": "Horizontal scroll with sticky first column.", "lg": "Full table, all columns visible.", "xl": "Full table with additional columns visible."},
    "grid": {"sm": "1 column.", "md": "2 columns.", "lg": "3 columns.", "xl": "4 columns."},
    "sidebar_layout": {"sm": "Sidebar becomes an off-canvas drawer.", "md": "Sidebar collapses to icons-only.", "lg": "Full sidebar visible.", "xl": "Full sidebar visible with more padding."},
}


def plan_responsive(component: str) -> ResponsivePlan:
    key = component.lower().replace(" ", "_")
    rules = _COMPONENT_RULES.get(key, {"sm": "Stack vertically, full width.", "md": "Introduce a two-column layout if content allows.", "lg": "Full intended layout.", "xl": "Full layout with a max-width container."})
    behaviors = [ResponsiveBehavior(breakpoint=bp, width_px=_BREAKPOINTS_PX[bp], layout_note=note) for bp, note in rules.items()]
    return ResponsivePlan(component=key, behaviors=behaviors)


def breakpoints() -> dict:
    return dict(_BREAKPOINTS_PX)
