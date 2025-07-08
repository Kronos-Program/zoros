from __future__ import annotations

from zoros_core.plugins import ZorosPlugin
from scripts.zoros_cli import app
from source.language_service import LanguageService


class LangServicePlugin(ZorosPlugin):
    """Plugin exposing LanguageService helpers."""

    name = "lang-service"
    version = "0.1.0"

    def register_with_core(self, core_api) -> None:
        @app.command(name="lang-service-test")
        def lang_service_test() -> None:
            """Test connection to the local language service."""
            svc = LanguageService()
            svc.complete_chat([{"role": "user", "content": "ping"}])
            print("ok")

        core_api.register_plugin(self)

    def ui_panels(self):
        return [{"title": "Language Service", "component": "LangServicePanel"}]
