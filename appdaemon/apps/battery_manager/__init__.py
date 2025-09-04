"""
Battery Manager - Modular battery management system.

This package provides a clean, modular architecture for managing battery systems
based on available power and battery states, following SOLID principles and DRY practices.
"""

import sys
import os

# Add the battery_manager directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from battery import Battery, BatteryState
from battery_collection import BatteryCollection
from marstek_battery import MarstekBattery

# Import BatteryManager using importlib to avoid circular import
import importlib.util
import os as _os
_spec = importlib.util.spec_from_file_location("battery_manager_module", _os.path.join(_os.path.dirname(__file__), "battery_manager.py"))
_battery_manager_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_battery_manager_module)
BatteryManager = _battery_manager_module.BatteryManager

__version__ = "1.0.0"
__all__ = [
    "Battery",
    "BatteryState",
    "BatteryCollection",
    "MarstekBattery",
    "BatteryManager"
]