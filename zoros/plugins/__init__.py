"""Plugin loader package."""

from .loader import Plugin, list_plugins, execute_plugin, load_plugins

__all__ = ["Plugin", "list_plugins", "execute_plugin", "load_plugins"]
