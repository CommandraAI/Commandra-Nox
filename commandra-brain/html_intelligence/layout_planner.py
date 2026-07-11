"""Layout Planner -- decides page/section structure before markup exists."""

from __future__ import annotations

from dataclasses import dataclass, field

_LAYOUT_TEMPLATES = {
    "landing_page": ["nav", "hero", "social_proof", "features", "testimonials", "pricing", "faq", "cta", "footer"],
    "dashboard": ["sidebar_nav", "topbar", "kpi_cards", "primary_chart", "secondary_widgets", "data_table"],
    "admin_panel": ["sidebar_nav", "topbar", "filters_toolbar", "data_table", "pagination", "bulk_actions"],
    "auth_page": ["logo", "form_card", "helper_links"],
    "settings_page": ["sidebar_tabs", "section_form", "save_bar"],
    "blog_post": ["header", "hero_image", "article_body", "author_bio", "related_posts"],
    "ecommerce_product": ["breadcrumbs", "gallery", "product_info", "add_to_cart", "reviews", "related_products"],
}

_GRID_GUIDANCE = {
    "landing_page": "12-column grid, centered max-width container (~1280px), generous section vertical rhythm (80-120px between sections).",
    "dashboard": "12-column grid with a fixed sidebar (~240-280px) and fluid content area; cards on a 4/8/12 responsive split.",
    "admin_panel": "Fixed sidebar + fluid table area; table should scroll horizontally on narrow viewports rather than reflow.",
    "auth_page": "Single centered column, max-width ~400px, vertically centered on the viewport.",
    "settings_page": "Two-column: fixed-width tab list + flexible form area, collapsing to stacked on mobile.",
    "blog_post": "Single reading column, max-width ~680-760px for optimal line length (60-75 characters).",
    "ecommerce_product": "Two-column above the fold (gallery + info), full-width sections below for reviews/related.",
}


@dataclass
class LayoutPlan:
    page_kind: str
    sections: list[str] = field(default_factory=list)
    grid_guidance: str = ""

    def as_dict(self) -> dict:
        return {"pageKind": self.page_kind, "sections": self.sections, "gridGuidance": self.grid_guidance}


def plan_layout(page_kind: str) -> LayoutPlan:
    key = page_kind.lower().replace(" ", "_").replace("-", "_")
    sections = _LAYOUT_TEMPLATES.get(key, ["header", "main_content", "footer"])
    grid = _GRID_GUIDANCE.get(key, "12-column responsive grid, mobile-first, max-width container to prevent overly long lines on large screens.")
    return LayoutPlan(page_kind=key, sections=sections, grid_guidance=grid)


def available_page_kinds() -> list[str]:
    return sorted(_LAYOUT_TEMPLATES.keys())
