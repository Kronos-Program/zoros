"""Zoros core module providing plugin loading."""

from __future__ import annotations

import importlib.metadata
from typing import Callable, Dict, List
import os

from .plugins import ZorosPlugin


class CoreAPI:
    """Minimal core API used for plugin registration."""

    def __init__(self) -> None:
        self._plugins: Dict[str, ZorosPlugin] = {}
        self._transcribers: Dict[str, Callable[[bytes], str]] = {}

    def register_plugin(self, plugin: ZorosPlugin) -> None:
        self._plugins[plugin.name] = plugin

    def register_transcriber(self, name: str, func: Callable[[bytes], str]) -> None:
        self._transcribers[name] = func

    def list_plugins(self) -> List[str]:
        if not self._plugins:
            load_plugins()
        return list(self._plugins.keys())

    def transcribe_with(self, name: str, audio: bytes) -> str:
        if name not in self._transcribers:
            raise KeyError(name)
        return self._transcribers[name](audio)


core_api = CoreAPI()


def load_plugins() -> None:
    """Load plugins via entry points."""
    for ep in importlib.metadata.entry_points(group="zoros.plugins"):
        plugin_cls = ep.load()
        if not issubclass(plugin_cls, ZorosPlugin):
            continue
        plugin = plugin_cls()
        core_api.register_plugin(plugin)
        plugin.register_with_core(core_api)


def reload_plugins() -> None:
    """Reload all plugins at runtime."""
    core_api._plugins.clear()
    core_api._transcribers.clear()
    load_plugins()


# Load plugins on import unless disabled for tests
if not os.getenv("ZOROS_DISABLE_AUTO_PLUGINS"):
    load_plugins()
