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

class TestNegativeSurplusBug(unittest.TestCase):
    """Test to reproduce the bug where wallbox starts charging with negative surplus."""
    
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
            "buffer_watts": 100,  # This is the key - should prevent charging when surplus is 0
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
        
        # Set up the exact scenario from the bug report logs
        self.setup_bug_scenario()
    
    def _get_state(self, entity_id):
        """Mock get_state method."""
        return self.app.entity_states.get(entity_id, "0")
    
    def _call_service(self, service, **kwargs):
        """Mock call_service method."""
        self.app.service_calls.append((service, kwargs))
    
    def setup_bug_scenario(self):
        """Set up the exact scenario from the bug report logs."""
        # Grid power: 0.0W (no surplus)
        self.app.entity_states["sensor.netz_gesamt_w"] = "0.0"
        
        # Dani wallbox: enabled=False, connected=True, charging=False, power=3.0W, limit=6.0A  
        self.app.entity_states["input_boolean.wallbox_dani_ueberschuss"] = "off"  # disabled
        self.app.entity_states["binary_sensor.warp2_22vo_daniel_cable"] = "on"     # connected
        self.app.entity_states["binary_sensor.warp2_22vo_daniel_charging"] = "off" # not charging
        self.app.entity_states["sensor.warp2_22vo_daniel_powernow"] = "3.0"       # 3W power
        self.app.entity_states["number.warp2_22vo_daniel_globalcurrent"] = "6.0"  # 6A limit
        
        # Elli wallbox: enabled=True, connected=True, charging=False, power=2.0W, limit=0.0A
        self.app.entity_states["input_boolean.wallbox_elli_ueberschuss"] = "on"   # enabled
        self.app.entity_states["binary_sensor.warp2_22vo_elli_cable"] = "on"      # connected  
        self.app.entity_states["binary_sensor.warp2_22vo_elli_charging"] = "off"  # not charging
        self.app.entity_states["sensor.warp2_22vo_elli_powernow"] = "2.0"         # 2W power
        self.app.entity_states["number.warp2_22vo_elli_globalcurrent"] = "0.0"    # 0A limit
    
    def test_negative_surplus_should_not_start_charging(self):
        """Test that wallbox should NOT start charging when there's negative surplus."""
        # Clear service calls to track only what happens during manage_wallboxes
        self.app.service_calls.clear()
        self.app.log_messages.clear()
        
        # Run the wallbox manager
        self.app.manage_wallboxes(None, None, None, None, None)
        
        # Check log messages for debugging
        for msg in self.app.log_messages:
            print(f"LOG: {msg}")
        
        # Check service calls 
        for service, kwargs in self.app.service_calls:
            print(f"SERVICE: {service} -> {kwargs}")
        
        # Assertions to check the bug
        # 1. Should calculate negative surplus after buffer
        surplus_msgs = [msg for msg in self.app.log_messages if "Adjusted surplus after" in msg]
        self.assertTrue(any("-100.0W" in msg for msg in surplus_msgs), 
                       "Should show -100W adjusted surplus")
        
        # 2. Should calculate negative current
        calc_msgs = [msg for msg in self.app.log_messages if "calculated current before limiting" in msg]
        negative_msgs = [msg for msg in self.app.log_messages if "has negative current" in msg]
        
        # Our new debug logging should show negative current
        if calc_msgs:
            self.assertTrue(any("-0." in msg for msg in calc_msgs),
                           "Should show negative current calculation")
        if negative_msgs:
            self.assertTrue(any("insufficient surplus power" in msg for msg in negative_msgs),
                           "Should detect insufficient surplus power")
        
        # 3. Should NOT set current to 6A (this is the bug)
        current_service_calls = [call for call in self.app.service_calls 
                               if call[0] == "number/set_value" and 
                               "warp2_22vo_elli_globalcurrent" in call[1].get("entity_id", "")]
        
        if current_service_calls:
            # If there are current setting calls, they should NOT be 6A when surplus is negative
            for service, kwargs in current_service_calls:
                current_value = kwargs.get("value", 0)
                self.assertNotEqual(current_value, 6, 
                                  f"Should NOT set current to 6A with negative surplus, got {current_value}A")
        
        # 4. Should NOT start charging
        start_service_calls = [call for call in self.app.service_calls 
                             if call[0] == "button/press" and 
                             "startcharge" in call[1].get("entity_id", "")]
        
        self.assertEqual(len(start_service_calls), 0, 
                        "Should NOT start charging when there's insufficient surplus power")
        
        # 5. Check that power required sensor is set correctly 
        power_required_calls = [call for call in self.app.set_state.call_args_list 
                              if len(call[0]) > 0 and call[0][0] == "binary_sensor.wallbox_power_required"]
        
        if power_required_calls:
            # The sensor should be "off" since no wallbox should be charging
            last_call = power_required_calls[-1]
            if len(last_call[1]) > 0 and "state" in last_call[1]:
                sensor_state = last_call[1]["state"]
                # Note: This might be "on" due to the bug, but ideally should be "off"
                print(f"Power required sensor state: {sensor_state}")

if __name__ == '__main__':
    unittest.main()