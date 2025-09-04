"""
Base test class for wallbox manager tests.

This module provides a common base class that eliminates duplicate setup code
across all wallbox manager tests.
"""

import sys
import os
import time
import unittest
from unittest.mock import Mock, MagicMock, patch

# Add the parent directory to the path to import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockHass:
    """Mock Home Assistant AppDaemon interface."""
    
    class Hass:
        def __init__(self):
            self.args = {}
            self.entity_states = {}
            self.service_calls = []
            self.log_messages = []
            self.callbacks = {}
            self.timer_callbacks = {}
            self.current_time = time.time()
        
        def log(self, message):
            self.log_messages.append(message)
        
        def get_state(self, entity_id):
            value = self.entity_states.get(entity_id, "0")
            # Handle unavailable/unknown values like the real system would
            if value in ["unavailable", "unknown", "None"]:
                return None
            return value
        
        def set_state(self, entity_id, state=None, attributes=None):
            if attributes:
                self.entity_states[entity_id] = state
                return True
            else:
                self.entity_states[entity_id] = state
                return True
        
        def call_service(self, service, **kwargs):
            self.service_calls.append((service, kwargs))
        
        def listen_state(self, callback, entity_id):
            if entity_id not in self.callbacks:
                self.callbacks[entity_id] = []
            self.callbacks[entity_id].append(callback)
        
        def run_every(self, callback, start_time, interval):
            # Mock implementation - just store the callback
            pass
        
        def run_in(self, callback, seconds, **kwargs):
            timer_id = f"timer_{len(self.timer_callbacks)}"
            self.timer_callbacks[timer_id] = (callback, seconds, kwargs)
            return timer_id
        
        def cancel_timer(self, timer_id):
            if timer_id in self.timer_callbacks:
                del self.timer_callbacks[timer_id]
        
        def get_now_ts(self):
            return self.current_time
        
        def advance_time(self, seconds):
            """Advance the mock time by the specified number of seconds."""
            self.current_time += seconds
            
            # Check for timers that should fire
            timers_to_fire = []
            for timer_id, (callback, timer_seconds, kwargs) in self.timer_callbacks.items():
                if timer_seconds <= seconds:
                    timers_to_fire.append((timer_id, callback, kwargs))
            
            # Fire the timers and remove them
            for timer_id, callback, kwargs in timers_to_fire:
                callback(kwargs)
                del self.timer_callbacks[timer_id]


# Mock the hassapi module
sys.modules['hassapi'] = MockHass

from wallbox_manager import WallboxManager, WallboxCollection, WALLBOX_CONFIGS, PowerConverter


class BaseWallboxTest(unittest.TestCase):
    """
    Base test class for wallbox manager tests.
    
    This class provides common setup and utility methods that eliminate
    duplicate code across all wallbox manager tests.
    """
    
    def setUp(self):
        """Set up test fixtures with clean architecture."""
        self.hass = MockHass.Hass()
        self.hass.args = self.get_default_config()
        
        # Create the app instance
        self.manager = WallboxManager()
        self.manager.hass = self.hass
        self.manager.args = getattr(self, "args", {})
        self.manager.initialize()
        
        # Set up the app attributes manually since we're not calling initialize()
        self._setup_manager_attributes()
        
        # Create wallbox collection with clean architecture
        self._setup_wallbox_collection()
        
        # Initialize the clean utilities that the new architecture uses
        self._setup_clean_utilities()
        
        # Patch the app's methods to use our mocked hass
        self._patch_manager_methods()
    
    def get_default_config(self):
        """
        Get default configuration for tests.
        
        Override this method in subclasses to customize configuration.
        
        Returns:
            dict: Default configuration dictionary
        """
        return {
            'ratio_dani_to_elli': 2.0,
            'voltage': 230,
            'sqrt_3': 1.0,  # Single-phase
            'min_current_a': 6,
            'max_current_a': 16,
            'buffer_watts': 100,
            'max_power_change_per_cycle': 500,  # Realistic rate limiting
            'timer_interval': 10,
            'max_charging_attempts': 3,
            'charging_retry_interval': 300,
            'charging_power_threshold': 100
        }
    
    def _setup_manager_attributes(self):
        """Set up manager attributes from configuration."""
        self.manager.ratio_dani_to_elli = float(self.hass.args.get("ratio_dani_to_elli", 2.0))
        self.manager.voltage = float(self.hass.args.get("voltage", 230))
        self.manager.sqrt_3 = float(self.hass.args.get("sqrt_3", 1.732))
        self.manager.min_current_a = float(self.hass.args.get("min_current_a", 6))
        self.manager.max_current_a = float(self.hass.args.get("max_current_a", 16))
        self.manager.buffer_watts = float(self.hass.args.get("buffer_watts", 100))
        
        # Configuration for gradual adjustment
        self.manager.max_power_change_per_cycle = float(self.hass.args.get("max_power_change_per_cycle", 500))
        self.manager.timer_interval = int(self.hass.args.get("timer_interval", 10))
        
        # Set up the new attributes for failed charging detection
        self.manager.max_attempts = int(self.hass.args.get("max_charging_attempts", 3))
        self.manager.retry_interval = int(self.hass.args.get("charging_retry_interval", 300))
        self.manager.power_threshold = float(self.hass.args.get("charging_power_threshold", 100))
        
        # Set the args attribute that WallboxCollection expects
        self.manager.args = self.hass.args
    
    def _setup_wallbox_collection(self):
        """Set up wallbox collection with proper configuration."""
        ratio_dani_to_elli = float(self.hass.args.get("ratio_dani_to_elli", 2.0))
        
        # Update wallbox configs with custom ratio if provided
        configs = WALLBOX_CONFIGS.copy()
        for config in configs:
            if config['name'] == 'dani':
                config['priority'] = ratio_dani_to_elli
            elif config['name'] == 'elli':
                config['priority'] = 1.0
        
        # Create wallbox collection like the initialize method does
        self.manager.wallbox_collection = WallboxCollection(configs, self.manager)
        
        # Keep backward compatibility reference for existing code
        self.manager.wallboxes = self.manager.wallbox_collection.wallboxes
    
    def _setup_clean_utilities(self):
        """Initialize the clean utilities that the new architecture uses."""
        self.manager.power_converter = PowerConverter(
            voltage=self.manager.voltage,
            sqrt_3=self.manager.sqrt_3
        )
    
    def _patch_manager_methods(self):
        """Patch the app's methods to use our mocked hass."""
        self.manager.log = self.hass.log
        self.manager.get_state = self.hass.get_state
        self.manager.set_state = self.hass.set_state
        self.manager.call_service = self.hass.call_service
        self.manager.run_in = self.hass.run_in
        self.manager.cancel_timer = self.hass.cancel_timer
        self.manager.get_now_ts = self.hass.get_now_ts
    
    def clear_service_calls(self):
        """Clear the service calls list for clean test assertions."""
        self.hass.service_calls = []
    
    def clear_log_messages(self):
        """Clear the log messages list for clean test assertions."""
        self.hass.log_messages = []
    
    def fire_all_timers(self):
        """Fire all timer callbacks for testing timer-based functionality."""
        for timer_id, (callback, seconds, kwargs) in list(self.hass.timer_callbacks.items()):
            callback(kwargs)
            del self.hass.timer_callbacks[timer_id]
    
    def set_wallbox_state(self, wallbox_name, enabled=True, connected=True, charging=False, 
                         power=0.0, current=0.0):
        """
        Convenience method to set wallbox state.
        
        Args:
            wallbox_name (str): Name of wallbox ('dani' or 'elli')
            enabled (bool): Whether wallbox is enabled
            connected (bool): Whether cable is connected
            charging (bool): Whether wallbox is charging
            power (float): Current power consumption in watts
            current (float): Current limit in amps
        """
        entity_name = "daniel" if wallbox_name == "dani" else wallbox_name
        
        self.hass.entity_states.update({
            f"input_boolean.wallbox_{wallbox_name}_ueberschuss": "on" if enabled else "off",
            f"binary_sensor.warp2_22vo_{entity_name}_cable": "on" if connected else "off",
            f"binary_sensor.warp2_22vo_{entity_name}_charging": "on" if charging else "off",
            f"sensor.warp2_22vo_{entity_name}_powernow": str(power),
            f"number.warp2_22vo_{entity_name}_globalcurrent": str(current),
        })
    
    def set_grid_power(self, watts):
        """
        Convenience method to set grid power.
        
        Args:
            watts (float): Grid power in watts (negative = export, positive = import)
        """
        self.hass.entity_states["sensor.netz_gesamt_w"] = str(watts)
    
    def get_service_calls_for_wallbox(self, wallbox_name, service_type=None):
        """
        Get service calls for a specific wallbox.
        
        Args:
            wallbox_name (str): Name of wallbox ('dani' or 'elli')
            service_type (str, optional): Filter by service type ('current', 'start', 'stop')
            
        Returns:
            list: List of matching service calls
        """
        entity_name = "daniel" if wallbox_name == "dani" else wallbox_name
        
        if service_type == 'current':
            return [call for call in self.hass.service_calls
                   if call[0] == "number/set_value" and
                   f"{entity_name}_globalcurrent" in str(call[1].get("entity_id", ""))]
        elif service_type == 'start':
            return [call for call in self.hass.service_calls
                   if call[0] == "button/press" and
                   f"{entity_name}_startcharge" in str(call[1].get("entity_id", ""))]
        elif service_type == 'stop':
            return [call for call in self.hass.service_calls
                   if call[0] == "button/press" and
                   f"{entity_name}_stopcharge" in str(call[1].get("entity_id", ""))]
        else:
            return [call for call in self.hass.service_calls
                   if entity_name in str(call[1].get("entity_id", ""))]
    
    def get_logs_containing(self, text):
        """
        Get log messages containing specific text.
        
        Args:
            text (str): Text to search for in log messages
            
        Returns:
            list: List of matching log messages
        """
        return [str(msg) for msg in self.hass.log_messages if text in str(msg)]
    
    def assert_wallbox_current_set(self, wallbox_name, expected_current, delta=0.1):
        """
        Assert that a wallbox current was set to expected value.
        
        Args:
            wallbox_name (str): Name of wallbox
            expected_current (float): Expected current value
            delta (float): Tolerance for comparison
        """
        current_calls = self.get_service_calls_for_wallbox(wallbox_name, 'current')
        self.assertTrue(len(current_calls) > 0, f"No current calls found for {wallbox_name}")
        
        actual_current = current_calls[-1][1]["value"]  # Get the last call
        self.assertAlmostEqual(actual_current, expected_current, delta=delta,
                              msg=f"{wallbox_name} current should be {expected_current}A, got {actual_current}A")
    
    def assert_wallbox_stopped(self, wallbox_name):
        """
        Assert that a wallbox was stopped.
        
        Args:
            wallbox_name (str): Name of wallbox
        """
        stop_calls = self.get_service_calls_for_wallbox(wallbox_name, 'stop')
        current_zero_calls = [call for call in self.get_service_calls_for_wallbox(wallbox_name, 'current')
                             if call[1].get("value", 1) == 0]
        
        self.assertTrue(len(stop_calls) > 0 or len(current_zero_calls) > 0,
                       f"{wallbox_name} should have been stopped")