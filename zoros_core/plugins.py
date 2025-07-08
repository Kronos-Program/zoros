class ZorosPlugin:
    """Base class for Zoros plugins."""

    name: str
    version: str

    def register_with_core(self, core_api):
        """Register plugin with the core system."""
        raise NotImplementedError

    def cli_commands(self):
        """Return CLI command metadata."""
        return []

    def ui_panels(self):
        """Return UI panels metadata."""
        return []
