import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import time

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
        
        def set_state(self, entity_id, state, attributes=None):
            self.entity_states[entity_id] = state
        
        def call_service(self, service, **kwargs):
            self.service_calls.append((service, kwargs))
        
        def run_in(self, callback, seconds, **kwargs):
            timer_id = f"timer_{len(self.timer_callbacks)}"
            self.timer_callbacks[timer_id] = (callback, seconds, kwargs)
            return timer_id
        
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

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Wallbox class
from wallbox import Wallbox

class TestWallbox(unittest.TestCase):
    """Test the Wallbox class functionality."""
    
    def setUp(self):
        """Set up the test environment."""
        self.hass = MockHass.Hass()
        
        # Create a mock app with the necessary attributes
        self.app = MagicMock()
        self.app.log = self.hass.log
        self.app.get_state = self.hass.get_state
        self.app.set_state = self.hass.set_state
        self.app.call_service = self.hass.call_service
        self.app.run_in = self.hass.run_in
        self.app.get_now_ts = self.hass.get_now_ts
        
        # Set up the app attributes
        self.app.max_attempts = 3
        self.app.retry_interval = 300
        self.app.power_threshold = 100
        self.app.min_current_a = 6
        self.app.max_current_a = 32
        
        # Create the wallbox instance
        self.wallbox = Wallbox("dani", self.app)
    def test_entity_id_generation(self):
        """Test that entity IDs are generated correctly."""
        self.assertEqual(self.wallbox.get_entity_id("enabled"), "input_boolean.wallbox_dani_ueberschuss")
        self.assertEqual(self.wallbox.get_entity_id("charging"), "binary_sensor.warp2_22vo_daniel_charging")
        self.assertEqual(self.wallbox.get_entity_id("cable"), "binary_sensor.warp2_22vo_daniel_cable")
        self.assertEqual(self.wallbox.get_entity_id("power"), "sensor.warp2_22vo_daniel_powernow")
        self.assertEqual(self.wallbox.get_entity_id("current"), "number.warp2_22vo_daniel_globalcurrent")
        self.assertEqual(self.wallbox.get_entity_id("start"), "button.warp2_22vo_daniel_startcharge")
        self.assertEqual(self.wallbox.get_entity_id("stop"), "button.warp2_22vo_daniel_stopcharge")
        self.assertEqual(self.wallbox.get_entity_id("stop"), "button.warp2_22vo_daniel_stopcharge")
    
    def test_is_enabled(self):
        """Test the is_enabled method."""
        # Test when enabled
        self.hass.entity_states["input_boolean.wallbox_dani_ueberschuss"] = "on"
        self.assertTrue(self.wallbox.is_enabled())
        
        # Test when disabled
        self.hass.entity_states["input_boolean.wallbox_dani_ueberschuss"] = "off"
        self.assertFalse(self.wallbox.is_enabled())
    
    def test_is_connected(self):
        """Test the is_connected method."""
        # Test when connected
        self.hass.entity_states["binary_sensor.warp2_22vo_daniel_cable"] = "on"
        self.assertTrue(self.wallbox.is_connected())
        
        # Test when not connected
        self.hass.entity_states["binary_sensor.warp2_22vo_daniel_cable"] = "off"
        self.assertFalse(self.wallbox.is_connected())
    
    def test_is_charging(self):
        """Test the is_charging method."""
        # Test when charging
        self.hass.entity_states["binary_sensor.warp2_22vo_daniel_charging"] = "on"
        self.assertTrue(self.wallbox.is_charging())
        
        # Test when not charging
        self.hass.entity_states["binary_sensor.warp2_22vo_daniel_charging"] = "off"
        self.assertFalse(self.wallbox.is_charging())
    def test_get_current_power(self):
        """Test the get_current_power method."""
        self.hass.entity_states["sensor.warp2_22vo_daniel_powernow"] = "2000.0"
        self.assertEqual(self.wallbox.get_current_power(), 2000.0)
    
    def test_get_current_limit(self):
        """Test the get_current_limit method."""
        self.hass.entity_states["number.warp2_22vo_daniel_globalcurrent"] = "10.0"
        self.assertEqual(self.wallbox.get_current_limit(), 10.0)
        self.assertEqual(self.wallbox.get_current_limit(), 10.0)
    
    def test_start_charging(self):
        """Test the start_charging method."""
        self.wallbox.start_charging()
        
        # Check that the current was set to 6A
        service_calls = [call for call in self.hass.service_calls if call[0] == "number/set_value"]
        self.assertEqual(len(service_calls), 1)
        self.assertEqual(service_calls[0][1]["entity_id"], "number.warp2_22vo_daniel_globalcurrent")
        self.assertEqual(service_calls[0][1]["value"], 6)
        
        # Check that the start button was pressed
        service_calls = [call for call in self.hass.service_calls if call[0] == "button/press"]
        self.assertEqual(len(service_calls), 1)
        self.assertEqual(service_calls[0][1]["entity_id"], "button.warp2_22vo_daniel_startcharge")
        
        # Check that the attempt count was incremented
        self.assertEqual(self.wallbox.attempt_count, 1)
        
        # Check that a check was scheduled
        self.assertEqual(len(self.hass.timer_callbacks), 1)
    
    def test_stop_charging(self):
        """Test the stop_charging method."""
        self.wallbox.stop_charging()
        # Check that the stop button was pressed
        service_calls = [call for call in self.hass.service_calls if call[0] == "button/press"]
        self.assertEqual(len(service_calls), 1)
        self.assertEqual(service_calls[0][1]["entity_id"], "button.warp2_22vo_daniel_stopcharge")
        self.assertEqual(service_calls[0][1]["entity_id"], "button.warp2_22vo_daniel_stopcharge")
        
        # Check that the current was set to 0A
        service_calls = [call for call in self.hass.service_calls if call[0] == "number/set_value"]
        self.assertEqual(len(service_calls), 1)
        self.assertEqual(service_calls[0][1]["entity_id"], "number.warp2_22vo_daniel_globalcurrent")
        self.assertEqual(service_calls[0][1]["value"], 0)
    
    def test_set_current(self):
        """Test the set_current method."""
        # Set up initial state
        self.hass.entity_states["number.warp2_22vo_daniel_globalcurrent"] = "8.0"
        
        # Test setting current above minimum
        self.wallbox.set_current(10)
        
        # Check that the current was set to 10A
        service_calls = [call for call in self.hass.service_calls if call[0] == "number/set_value"]
        self.assertEqual(len(service_calls), 1)
        self.assertEqual(service_calls[0][1]["entity_id"], "number.warp2_22vo_daniel_globalcurrent")
        self.assertEqual(service_calls[0][1]["value"], 10)
        
        # Reset service calls
        self.hass.service_calls = []
        
        # Test setting current below minimum
        self.hass.entity_states["binary_sensor.warp2_22vo_daniel_charging"] = "on"
        self.wallbox.set_current(3)
        
        # Check that stop_charging was called
        service_calls = [call for call in self.hass.service_calls if call[0] == "button/press"]
        self.assertEqual(len(service_calls), 1)
        self.assertEqual(service_calls[0][1]["entity_id"], "button.warp2_22vo_daniel_stopcharge")
    
    def test_check_charging_success(self):
        """Test the check_charging method when charging starts successfully."""
        # Set up the initial state
        self.wallbox.attempt_count = 1
        self.hass.entity_states["binary_sensor.warp2_22vo_daniel_charging"] = "on"
        self.hass.entity_states["sensor.warp2_22vo_daniel_powernow"] = "2000.0"
        
        # Call the method
        self.wallbox.check_charging(None)
        
        # Check that the attempt count was reset
        self.assertEqual(self.wallbox.attempt_count, 0)
    
    def test_check_charging_failure(self):
        """Test the check_charging method when charging fails to start."""
        # Set up the initial state
        self.wallbox.attempt_count = 1
        self.hass.entity_states["binary_sensor.warp2_22vo_daniel_charging"] = "off"
        self.hass.entity_states["sensor.warp2_22vo_daniel_powernow"] = "2.0"
        
        # Call the method
        self.wallbox.check_charging(None)
        
        # Check that the attempt count was not reset
        self.assertEqual(self.wallbox.attempt_count, 1)
    def test_check_charging_max_attempts(self):
        """Test the check_charging method when max attempts are reached."""
        # Set up the initial state
        self.wallbox.attempt_count = 3  # Max attempts
        self.hass.entity_states["binary_sensor.warp2_22vo_daniel_charging"] = "off"
        self.hass.entity_states["sensor.warp2_22vo_daniel_powernow"] = "2.0"
        
        # Clear any existing timer callbacks
        self.hass.timer_callbacks = {}
        
        # Call the method
        self.wallbox.check_charging(None)
        
        # Check that the wallbox is marked as failed
        self.assertTrue(self.wallbox.is_charging_failed())
        
        # Check that a retry timer is set
        self.assertIsNotNone(self.wallbox.retry_timer)
        
        # Check that at least one timer callback exists
        self.assertGreater(len(self.hass.timer_callbacks), 0)
    
    def test_is_charging_failed(self):
        """Test the is_charging_failed method."""
        # Test when not failed (charging and consuming power)
        self.hass.entity_states["binary_sensor.warp2_22vo_daniel_charging"] = "on"
        self.hass.entity_states["sensor.warp2_22vo_daniel_powernow"] = "2000.0"
        self.wallbox.attempt_count = 0
        self.assertFalse(self.wallbox.is_charging_failed())
        
        # Test when failed (not charging and max attempts reached)
        self.hass.entity_states["binary_sensor.warp2_22vo_daniel_charging"] = "off"
        self.hass.entity_states["sensor.warp2_22vo_daniel_powernow"] = "2.0"
        self.wallbox.attempt_count = 3
        self.assertTrue(self.wallbox.is_charging_failed())
    
    def test_schedule_retry(self):
        """Test the schedule_retry method."""
        # Call the method
        self.wallbox.schedule_retry()
        
        # Check that a retry was scheduled
        self.assertEqual(len(self.hass.timer_callbacks), 1)
        
        # Call again to test that it doesn't schedule another retry
        self.wallbox.schedule_retry()
        
        # Check that still only one retry is scheduled
        self.assertEqual(len(self.hass.timer_callbacks), 1)
    
    def test_retry(self):
        """Test the retry method."""
        # Set up the initial state
        self.wallbox.attempt_count = 3
        self.wallbox.retry_timer = "some_timer"
        self.hass.entity_states["input_boolean.wallbox_dani_ueberschuss"] = "on"
        self.hass.entity_states["binary_sensor.warp2_22vo_daniel_cable"] = "on"
        
        # Clear service calls
        self.hass.service_calls = []
        
        # Call the method
        self.wallbox.retry(None)
        
        # Check that the attempt count was reset
        self.assertEqual(self.wallbox.attempt_count, 1)  # Will be 1 after start_charging
        
        # Check that the retry timer was cleared
        self.assertIsNone(self.wallbox.retry_timer)
        
        # Check that start_charging was called
        service_calls = [call for call in self.hass.service_calls if call[0] == "number/set_value"]
        self.assertEqual(len(service_calls), 1)
        self.assertEqual(service_calls[0][1]["entity_id"], "number.warp2_22vo_daniel_globalcurrent")
        self.assertEqual(service_calls[0][1]["value"], 6)
    
    def test_requires_power(self):
        """Test the requires_power method."""
        # Test when enabled, connected, and charging
        self.hass.entity_states["input_boolean.wallbox_dani_ueberschuss"] = "on"
        self.hass.entity_states["binary_sensor.warp2_22vo_daniel_cable"] = "on"
        self.hass.entity_states["binary_sensor.warp2_22vo_daniel_charging"] = "on"
        self.hass.entity_states["sensor.warp2_22vo_daniel_powernow"] = "2000.0"
        self.wallbox.attempt_count = 0
        self.assertTrue(self.wallbox.requires_power())
        
        # Test when enabled, connected, not charging, but not failed
        self.hass.entity_states["binary_sensor.warp2_22vo_daniel_charging"] = "off"
        self.wallbox.attempt_count = 0
        self.assertTrue(self.wallbox.requires_power())
        
        # Test when enabled, connected, not charging, and failed
        self.wallbox.attempt_count = 3
        self.assertFalse(self.wallbox.requires_power())
        
        # Test when enabled but not connected
        self.hass.entity_states["binary_sensor.warp2_22vo_daniel_cable"] = "off"
        self.assertFalse(self.wallbox.requires_power())
        
        # Test when not enabled
        self.hass.entity_states["input_boolean.wallbox_dani_ueberschuss"] = "off"
        self.assertFalse(self.wallbox.requires_power())

if __name__ == "__main__":
    unittest.main()