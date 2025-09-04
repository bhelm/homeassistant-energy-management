"""
Wallbox Manager - Modular wallbox charging management system.

This package provides a clean, modular architecture for managing wallbox charging
based on available power from the grid, following SOLID principles and DRY practices.
"""

import sys
import os

# Add the wallbox_manager directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from power_converter import PowerConverter
from rate_limiter import RateLimiter
from wallbox import Wallbox
from wallbox_collection import WallboxCollection, WALLBOX_CONFIGS

# Import WallboxManager using importlib to avoid circular import
import importlib.util
import os as _os
_spec = importlib.util.spec_from_file_location("wallbox_manager_module", _os.path.join(_os.path.dirname(__file__), "wallbox_manager.py"))
_wallbox_manager_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_wallbox_manager_module)
WallboxManager = _wallbox_manager_module.WallboxManager

__version__ = "2.0.0"
__all__ = [
    "PowerConverter",
    "RateLimiter",
    "Wallbox",
    "WallboxCollection",
    "WALLBOX_CONFIGS",
    "WallboxManager"
]