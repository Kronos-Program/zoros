from importlib import import_module
import sys

MODULES = [
    "audit_repo_files",
    "check_architecture",
    "metadata_enforcer",
    "patch_metadata",
]

for name in MODULES:
    module = import_module(f"scripts.maintenance.{name}")
    sys.modules[f"{__name__}.{name}"] = module

__all__ = MODULES
