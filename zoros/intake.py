"""
Backward compatibility wrapper for intake functionality.
Maps old zoros.intake imports to new backend.interfaces.intake structure.
"""

# Import everything from the new location
from backend.interfaces.intake import main

# Re-export for backward compatibility
__all__ = ["main"]