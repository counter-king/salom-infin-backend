from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path


def autodiscover_scopes():
    """
    Import all modules inside apps.accessctrl.scopes to trigger @register decorators.
    """
    pkg_name = __name__
    pkg = importlib.import_module(pkg_name)
    pkg_path = Path(pkg.__file__).parent
    for m in pkgutil.iter_modules([str(pkg_path)]):
        if m.name in {"__init__", "base", "registry"}:
            continue
        importlib.import_module(f"{pkg_name}.{m.name}")
