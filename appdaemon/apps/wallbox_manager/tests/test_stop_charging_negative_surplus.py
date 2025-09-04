import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import time

# Import the classes
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wallbox import Wallbox

# Create a mock for the hassapi module
class MockHass:
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
            return self.entity_states.get(entity_id, "0")
        
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
        
        def run_in(self, callback, seconds, **kwargs):
            timer_id = f"timer_{len(self.timer_callbacks)}"
            self.timer_callbacks[timer_id] = (callback, seconds, kwargs)
            return timer_id
        
        def run_every(self, callback, when, interval):
            timer_id = f"timer_every_{len(self.timer_callbacks)}"
            self.timer_callbacks[timer_id] = (callback, when, interval)
            return timer_id
        
        def cancel_timer(self, timer_id):
            if timer_id in self.timer_callbacks:
                del self.timer_callbacks[timer_id]

# Mock the hassapi module
sys.modules['hassapi'] = MockHass()

# Now import the WallboxManager
from wallbox_manager import WallboxManager

class TestStopChargingNegativeSurplus(unittest.TestCase):
    """Test to ensure wallboxes stop charging when surplus becomes negative (no solar power)."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock app
        self.app = WallboxManager()
        self.app.args = getattr(self, "args", {})
        self.app.initialize()
        
        # Initialize with test configuration 
        self.app.args = {
            "ratio_dani_to_elli": 2.0,
            "voltage": 233.33,
            "sqrt_3": 1.0,
            "min_current_a": 6,
            "max_current_a": 32,
            "buffer_watts": 100,
            "max_power_change_per_cycle": 500,
            "timer_interval": 10,
            "max_charging_attempts": 3,
            "charging_retry_interval": 300,
            "charging_power_threshold": 100
        }
        
        # Mock entity states and service calls
        self.app.entity_states = {}
        self.app.service_calls = []
        self.app.log_messages = []
        self.app.callbacks = {}
        self.app.timer_callbacks = {}
        
        # Mock methods
        self.app.log = MagicMock(side_effect=lambda msg: self.app.log_messages.append(msg))
        self.app.get_state = MagicMock(side_effect=self._get_state)
        self.app.set_state = MagicMock()
        self.app.call_service = MagicMock(side_effect=self._call_service)
        self.app.listen_state = MagicMock()
        self.app.run_in = MagicMock()
        self.app.run_every = MagicMock()
        
        # Initialize the app
        self.app.initialize()
    
    def _get_state(self, entity_id):
        """Mock get_state method."""
        return self.app.entity_states.get(entity_id, "0")
    
    def _call_service(self, service, **kwargs):
        """Mock call_service method."""
        self.app.service_calls.append((service, kwargs))
    
    def setup_already_charging_no_solar_scenario(self):
        """Set up scenario: Elli is already charging but there's no solar power (negative surplus)."""
        # Negative surplus: Grid power shows import (positive value means importing from grid)
        self.app.entity_states["sensor.netz_gesamt_w"] = "902.91"  # Importing from grid
        
        # Dani wallbox: disabled, connected, not charging
        self.app.entity_states["input_boolean.wallbox_dani_ueberschuss"] = "off"   # disabled
        self.app.entity_states["binary_sensor.warp2_22vo_daniel_cable"] = "on"     # connected
        self.app.entity_states["binary_sensor.warp2_22vo_daniel_charging"] = "off" # not charging
        self.app.entity_states["sensor.warp2_22vo_daniel_powernow"] = "3.0"        # 3W power
        self.app.entity_states["number.warp2_22vo_daniel_globalcurrent"] = "0.0"   # 0A limit
        
        # Elli wallbox: enabled, connected, ALREADY CHARGING (this is the key issue)
        self.app.entity_states["input_boolean.wallbox_elli_ueberschuss"] = "on"    # enabled
        self.app.entity_states["binary_sensor.warp2_22vo_elli_cable"] = "on"       # connected  
        self.app.entity_states["binary_sensor.warp2_22vo_elli_charging"] = "on"    # ALREADY CHARGING
        self.app.entity_states["sensor.warp2_22vo_elli_powernow"] = "1355.0"       # 1355W power consumption
        self.app.entity_states["number.warp2_22vo_elli_globalcurrent"] = "6.0"     # 6A current limit
    
    def test_already_charging_wallbox_should_stop_when_no_solar(self):
        """Test that an already-charging wallbox should stop when there's negative surplus (no solar)."""
        # Set up the scenario
        self.setup_already_charging_no_solar_scenario()
        
        # Clear service calls to track only what happens during manage_wallboxes
        self.app.service_calls.clear()
        self.app.log_messages.clear()
        
        # Run the wallbox manager
        self.app.manage_wallboxes(None, None, None, None, None)
        
        # Debug output
        print("\n=== LOG MESSAGES ===")
        for msg in self.app.log_messages:
            print(f"LOG: {msg}")
        
        print("\n=== SERVICE CALLS ===")
        for service, kwargs in self.app.service_calls:
            print(f"SERVICE: {service} -> {kwargs}")
        
        # Verify that surplus is calculated as negative
        surplus_msgs = [msg for msg in self.app.log_messages if "Surplus:" in msg]
        self.assertTrue(any("-902.91W" in msg for msg in surplus_msgs), 
                       "Should show negative surplus (-902.91W)")
        
        # Verify adjusted surplus after buffer is even more negative  
        adjusted_msgs = [msg for msg in self.app.log_messages if "Adjusted surplus after" in msg]
        self.assertTrue(any("-1002.91W" in msg for msg in adjusted_msgs),
                       "Should show -1002.91W adjusted surplus after 100W buffer")
        
        # **KEY TEST**: Even though the system calculates "available power" by adding back
        # Elli's consumption (1355W), when there's NO SOLAR POWER, the wallbox should stop
        # 
        # Expected behavior: Wallbox should be stopped because there's no solar generation
        # Current buggy behavior: Wallbox continues because -1002.91W + 1355W = 352W "available"
        
        # Check for stop charging service calls
        stop_service_calls = [call for call in self.app.service_calls 
                            if call[0] == "button/press" and 
                            "stopcharge" in call[1].get("entity_id", "")]
        
        # The wallbox should be stopped when there's no solar power
        # This test will currently FAIL, demonstrating the bug
        self.assertGreater(len(stop_service_calls), 0,
                          "Wallbox should be stopped when there's no solar power (negative surplus)")
        
        # Verify that Elli specifically was stopped
        elli_stop_calls = [call for call in stop_service_calls
                          if "warp2_22vo_elli_stopcharge" in call[1].get("entity_id", "")]
        
        self.assertGreater(len(elli_stop_calls), 0,
                          "Elli wallbox should be stopped when there's no solar power")
        
        # Alternative check: current should be set to 0A when no solar
        current_service_calls = [call for call in self.app.service_calls 
                               if call[0] == "number/set_value" and 
                               "warp2_22vo_elli_globalcurrent" in call[1].get("entity_id", "")]
        
        if current_service_calls:
            last_current_call = current_service_calls[-1]
            current_value = last_current_call[1].get("value", None)
            # Should be set to 0A when there's no solar power
            self.assertEqual(current_value, 0,
                           f"Elli current should be set to 0A when no solar, got {current_value}A")

if __name__ == '__main__':
    unittest.main()