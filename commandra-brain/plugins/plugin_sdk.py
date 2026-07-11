"""
Plugin SDK -- a small, dependency-free plugin system. Plugins register named
actions; the server can list them (`/plugins`) and invoke them by name
(`/plugins/{name}/invoke`). This is intentionally minimal: real external
plugin loading (e.g. from disk or a marketplace) can be layered on top of
`PluginRegistry.register` later without changing the public API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class PluginResult:
    plugin: str
    action: str
    ok: bool
    data: Any = None
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "plugin": self.plugin,
            "action": self.action,
            "ok": self.ok,
            "data": self.data,
            "error": self.error,
        }


@dataclass
class Plugin:
    name: str
    description: str
    actions: dict[str, Callable[..., Any]] = field(default_factory=dict)

    def action_names(self) -> list[str]:
        return sorted(self.actions.keys())

    def as_dict(self) -> dict:
        return {"name": self.name, "description": self.description, "actions": self.action_names()}


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        self._plugins[plugin.name] = plugin

    def list_plugins(self) -> list[dict]:
        return [p.as_dict() for p in self._plugins.values()]

    def invoke(self, plugin_name: str, action: str, **kwargs) -> PluginResult:
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            raise KeyError(f"Unknown plugin: {plugin_name}")
        handler = plugin.actions.get(action)
        if handler is None:
            raise KeyError(f"Unknown action '{action}' for plugin '{plugin_name}'")
        try:
            data = handler(**kwargs)
            return PluginResult(plugin=plugin_name, action=action, ok=True, data=data)
        except Exception as exc:  # noqa: BLE001 -- plugin failures must not crash the server
            return PluginResult(plugin=plugin_name, action=action, ok=False, error=str(exc))


def _echo(**kwargs) -> dict:
    return {"received": kwargs}


def _word_count(text: str = "") -> dict:
    return {"words": len(text.split()), "characters": len(text)}


def _build_default_registry() -> PluginRegistry:
    registry = PluginRegistry()
    registry.register(
        Plugin(
            name="utils",
            description="Small built-in utility actions (echo, word_count) useful for smoke-testing the plugin pipeline.",
            actions={"echo": _echo, "word_count": _word_count},
        )
    )
    return registry


_REGISTRY: PluginRegistry | None = None


def get_registry() -> PluginRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_default_registry()
    return _REGISTRY
