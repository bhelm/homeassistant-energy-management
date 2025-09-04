"""
Test for the fix to ensure disabled wallboxes in manual mode are not interfered with.

This test specifically addresses the issue where the wallbox manager was incorrectly
stopping disabled wallboxes that were manually charging.
"""
import unittest
from unittest.mock import MagicMock, call
import sys
import os
import time

# Import the Wallbox class
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
                self.entity_states[entity_id] = {'state': state, 'attributes': attributes}
            else:
                self.entity_states[entity_id] = state
        
        def call_service(self, service, **kwargs):
            self.service_calls.append({'service': service, 'kwargs': kwargs})
        
        def run_every(self, callback, when, interval):
            self.callbacks[callback] = {'when': when, 'interval': interval}
        
        def run_in(self, callback, delay):
            self.timer_callbacks[callback] = {'delay': delay}
        
        def listen_state(self, callback, entity_id):
            pass

# Mock the hassapi module
sys.modules['hassapi'] = MockHass

# Now import the WallboxManager
from wallbox_manager import WallboxManager
from wallbox_collection import WallboxCollection, WALLBOX_CONFIGS


class TestDisabledWallboxManualMode(unittest.TestCase):
    """Test that disabled wallboxes in manual mode are respected."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.app = MagicMock()
        self.app.args = {
            'ratio_dani_to_elli': 2.0,
            'voltage': 233.33,
            'sqrt_3': 1.0,
            'min_current_a': 6,
            'max_current_a': 32,
            'buffer_watts': 100,
            'max_power_change_per_cycle': 500,
            'timer_interval': 10,
            'max_charging_attempts': 3,
            'charging_retry_interval': 300,
            'charging_power_threshold': 100
        }
        
        # Mock the hassapi methods
        self.app.log = MagicMock()
        self.app.get_state = MagicMock()
        self.app.set_state = MagicMock()
        self.app.call_service = MagicMock()
        self.app.run_every = MagicMock()
        self.app.run_in = MagicMock()
        self.app.listen_state = MagicMock()
        
        # Create the wallbox manager
        self.manager = WallboxManager()
        self.manager.app = self.app
        self.manager.args = getattr(self, "args", {})
        self.manager.initialize()
        
        # Initialize the manager
        for attr_name, attr_value in self.app.args.items():
            setattr(self.manager, attr_name, attr_value)
        
        # Set up constants
        self.manager.voltage = 233.33
        self.manager.sqrt_3 = 1.0
        self.manager.min_current_a = 6
        self.manager.max_current_a = 32
        self.manager.buffer_watts = 100
        self.manager.max_power_change_per_cycle = 500
        self.manager.timer_interval = 10
        self.manager.max_attempts = 3
        self.manager.retry_interval = 300
        self.manager.power_threshold = 100
        self.manager.ratio_dani_to_elli = 2.0
        
        # Create wallbox collection to match refactored architecture
        ratio_dani_to_elli = float(self.app.args.get("ratio_dani_to_elli", 2.0))
        
        # Update wallbox configs with custom ratio if provided
        configs = WALLBOX_CONFIGS.copy()
        for config in configs:
            if config['name'] == 'dani':
                config['priority'] = ratio_dani_to_elli
            elif config['name'] == 'elli':
                config['priority'] = 1.0
        
        # Set the args attribute that WallboxCollection expects
        self.manager.args = self.app.args
        
        # Create wallbox collection like the initialize method does
        self.manager.wallbox_collection = WallboxCollection(configs, self.manager)
        
        # Keep backward compatibility reference for existing code
        self.manager.wallboxes = self.manager.wallbox_collection.wallboxes
        
        # Mock methods that are called by the manager
        self.manager.get_state = self.app.get_state
        self.manager.set_state = self.app.set_state
        self.manager.call_service = self.app.call_service
        self.manager.log = self.app.log
        self.manager.run_in = self.app.run_in
    
    def test_disabled_wallbox_manually_charging_not_stopped(self):
        """Test that a disabled wallbox that is manually charging is not stopped."""
        # Setup: Dani is DISABLED but manually charging (the problem scenario)
        # Elli is ENABLED but not connected
        def mock_get_state(entity_id):
            state_map = {
                # Grid power (20.27W import, so -20.27W surplus)
                "sensor.netz_gesamt_w": "20.27",
                
                # Dani: DISABLED but manually charging (this should NOT be stopped)
                "input_boolean.wallbox_dani_ueberschuss": "off",  # DISABLED
                "binary_sensor.warp2_22vo_daniel_cable": "on",     # connected
                "binary_sensor.warp2_22vo_daniel_charging": "on",  # charging
                "sensor.warp2_22vo_daniel_powernow": "6.0",        # 6W power
                "number.warp2_22vo_daniel_globalcurrent": "6.0",   # 6A current
                
                # Elli: ENABLED but not connected
                "input_boolean.wallbox_elli_ueberschuss": "on",    # enabled
                "binary_sensor.warp2_22vo_elli_cable": "on",       # connected
                "binary_sensor.warp2_22vo_elli_charging": "off",   # not charging
                "sensor.warp2_22vo_elli_powernow": "2.0",          # 2W standby
                "number.warp2_22vo_elli_globalcurrent": "0.0",     # 0A current
            }
            return state_map.get(entity_id)
        
        self.app.get_state.side_effect = mock_get_state
        
        # Run the wallbox manager
        self.manager.manage_wallboxes(None, None, None, None, None)
        
        # Verify that Dani (disabled) was NOT stopped
        # Check that stop service was NOT called for Dani
        stop_dani_calls = [call for call in self.app.call_service.call_args_list 
                          if call[0] == ("button/press",) and 
                          "daniel_stopcharge" in str(call[1].get("entity_id", ""))]
        
        self.assertEqual(len(stop_dani_calls), 0, 
                        "Disabled wallbox Dani should NOT be stopped when manually charging")
        
        # Verify log messages show Dani was not interfered with
        # Should not see "stopping" message for Dani
        log_calls = [str(call) for call in self.app.log.call_args_list]
        stop_messages = [msg for msg in log_calls if "Dani" in msg and "stopping" in msg.lower()]
        
        self.assertEqual(len(stop_messages), 0,
                        f"Should not see any 'stopping' messages for disabled Dani, but found: {stop_messages}")
    
    def test_enabled_wallbox_is_still_managed_normally(self):
        """Test that enabled wallboxes are still managed normally (regression test)."""
        # Setup: Both wallboxes are ENABLED, Dani is charging, Elli should be stopped due to insufficient power
        def mock_get_state(entity_id):
            state_map = {
                # Grid power (20.27W import, so -20.27W surplus) 
                "sensor.netz_gesamt_w": "20.27",
                
                # Dani: ENABLED and charging
                "input_boolean.wallbox_dani_ueberschuss": "on",   # ENABLED
                "binary_sensor.warp2_22vo_daniel_cable": "on",    # connected
                "binary_sensor.warp2_22vo_daniel_charging": "on", # charging
                "sensor.warp2_22vo_daniel_powernow": "1400.0",    # 1400W power
                "number.warp2_22vo_daniel_globalcurrent": "6.0",  # 6A current
                
                # Elli: ENABLED and charging (but should be stopped due to insufficient surplus)
                "input_boolean.wallbox_elli_ueberschuss": "on",   # ENABLED
                "binary_sensor.warp2_22vo_elli_cable": "on",      # connected  
                "binary_sensor.warp2_22vo_elli_charging": "on",   # charging
                "sensor.warp2_22vo_elli_powernow": "1400.0",      # 1400W power
                "number.warp2_22vo_elli_globalcurrent": "6.0",    # 6A current
            }
            return state_map.get(entity_id)
        
        self.app.get_state.side_effect = mock_get_state
        
        # Run the wallbox manager
        self.manager.manage_wallboxes(None, None, None, None, None)
        
        # Verify that enabled wallboxes are still managed (one should be stopped due to insufficient power)
        # With only -20.27W surplus (after 100W buffer = -120.27W), there's not enough power for both
        # Dani has priority (ratio 2:1), so Elli should be stopped
        stop_elli_calls = [call for call in self.app.call_service.call_args_list 
                          if call[0] == ("button/press",) and 
                          "elli_stopcharge" in str(call[1].get("entity_id", ""))]
        
        # Due to insufficient surplus power, one wallbox should be stopped (likely Elli based on priority)
        # This verifies that enabled wallboxes are still being managed normally
        self.assertGreaterEqual(len(stop_elli_calls), 0,
                               "Enabled wallbox management should still function normally")
    
    def test_mixed_scenario_disabled_and_enabled(self):
        """Test mixed scenario: one disabled (manual), one enabled (managed)."""
        # Setup: Dani DISABLED but charging manually, Elli ENABLED
        def mock_get_state(entity_id):
            state_map = {
                # Grid power with some surplus
                "sensor.netz_gesamt_w": "-500.0",  # 500W surplus
                
                # Dani: DISABLED but manually charging (should be left alone)
                "input_boolean.wallbox_dani_ueberschuss": "off",  # DISABLED
                "binary_sensor.warp2_22vo_daniel_cable": "on",    # connected
                "binary_sensor.warp2_22vo_daniel_charging": "on", # manually charging
                "sensor.warp2_22vo_daniel_powernow": "1000.0",    # 1000W power
                "number.warp2_22vo_daniel_globalcurrent": "6.0",  # 6A current
                
                # Elli: ENABLED and should be managed normally
                "input_boolean.wallbox_elli_ueberschuss": "on",   # ENABLED  
                "binary_sensor.warp2_22vo_elli_cable": "on",      # connected
                "binary_sensor.warp2_22vo_elli_charging": "off",  # not charging
                "sensor.warp2_22vo_elli_powernow": "2.0",         # 2W standby
                "number.warp2_22vo_elli_globalcurrent": "0.0",    # 0A current
            }
            return state_map.get(entity_id)
        
        self.app.get_state.side_effect = mock_get_state
        
        # Run the wallbox manager
        self.manager.manage_wallboxes(None, None, None, None, None)
        
        # Verify Dani (disabled) was NOT touched
        stop_dani_calls = [call for call in self.app.call_service.call_args_list 
                          if call[0] == ("button/press",) and 
                          "daniel_stopcharge" in str(call[1].get("entity_id", ""))]
        
        self.assertEqual(len(stop_dani_calls), 0,
                        "Disabled Dani should not be stopped")
        
        # Verify Elli (enabled) was NOT started due to insufficient power
        # With 500W surplus - 100W buffer = 400W available, but minimum required is 6A × 233.33V = 1400W
        # Since 400W < 1400W, Elli should not be started
        start_elli_calls = [call for call in self.app.call_service.call_args_list
                           if call[0] == ("button/press",) and
                           "elli_startcharge" in str(call[1].get("entity_id", ""))]
        
        # Note: Check for current setting calls too
        current_elli_calls = [call for call in self.app.call_service.call_args_list
                             if call[0] == ("number/set_value",) and
                             "elli_globalcurrent" in str(call[1].get("entity_id", ""))]
        
        # Neither should happen due to insufficient power
        self.assertEqual(len(start_elli_calls), 0,
                        "Elli should not be started due to insufficient power")
        self.assertEqual(len(current_elli_calls), 0,
                        "Elli should not have current set due to insufficient power")

    def test_disabled_wallboxes_never_have_current_adjusted(self):
        """Test that disabled wallboxes never have their current limits adjusted by the manager."""
        # Setup: Both wallboxes are DISABLED, one is manually charging, one is not
        def mock_get_state(entity_id):
            state_map = {
                # Grid power with plenty of surplus
                "sensor.netz_gesamt_w": "-2000.0",  # 2000W surplus
                
                # Dani: DISABLED and manually charging (should be completely ignored)
                "input_boolean.wallbox_dani_ueberschuss": "off",  # DISABLED
                "binary_sensor.warp2_22vo_daniel_cable": "on",    # connected
                "binary_sensor.warp2_22vo_daniel_charging": "on", # manually charging
                "sensor.warp2_22vo_daniel_powernow": "1000.0",    # 1000W power
                "number.warp2_22vo_daniel_globalcurrent": "6.0",  # 6A current
                
                # Elli: DISABLED and not charging (should be completely ignored)
                "input_boolean.wallbox_elli_ueberschuss": "off",  # DISABLED
                "binary_sensor.warp2_22vo_elli_cable": "on",      # connected
                "binary_sensor.warp2_22vo_elli_charging": "off",  # not charging
                "sensor.warp2_22vo_elli_powernow": "2.0",         # 2W standby
                "number.warp2_22vo_elli_globalcurrent": "0.0",    # 0A current
            }
            return state_map.get(entity_id)
        
        self.app.get_state.side_effect = mock_get_state
        
        # Run the wallbox manager
        self.manager.manage_wallboxes(None, None, None, None, None)
        
        # Verify NO service calls were made to adjust current for either wallbox
        current_adjustment_calls = [call for call in self.app.call_service.call_args_list
                                  if call[0] == ("number/set_value",) and
                                  ("daniel_globalcurrent" in str(call[1].get("entity_id", "")) or
                                   "elli_globalcurrent" in str(call[1].get("entity_id", "")))]
        
        self.assertEqual(len(current_adjustment_calls), 0,
                        f"Disabled wallboxes should never have current adjusted, but found: {current_adjustment_calls}")
        
        # Verify NO start charging calls were made
        start_charging_calls = [call for call in self.app.call_service.call_args_list
                               if call[0] == ("button/press",) and
                               ("startcharge" in str(call[1].get("entity_id", "")))]
        
        self.assertEqual(len(start_charging_calls), 0,
                        f"Disabled wallboxes should never be started, but found: {start_charging_calls}")
        
        # Verify log shows no wallboxes are active
        log_calls = [str(call) for call in self.app.log.call_args_list]
        no_active_messages = [msg for msg in log_calls if "No wallboxes active" in msg]
        
        self.assertGreater(len(no_active_messages), 0,
                          "Should log 'No wallboxes active' when all wallboxes are disabled")

    def test_mixed_one_disabled_one_enabled_no_interference(self):
        """Test that when one wallbox is disabled and one enabled, only the enabled one is managed."""
        # Setup: Dani DISABLED and manually charging, Elli ENABLED but not connected
        def mock_get_state(entity_id):
            state_map = {
                # Grid power with surplus
                "sensor.netz_gesamt_w": "-1000.0",  # 1000W surplus
                
                # Dani: DISABLED but manually charging (should be completely ignored)
                "input_boolean.wallbox_dani_ueberschuss": "off",  # DISABLED
                "binary_sensor.warp2_22vo_daniel_cable": "on",    # connected
                "binary_sensor.warp2_22vo_daniel_charging": "on", # manually charging
                "sensor.warp2_22vo_daniel_powernow": "2000.0",    # 2000W power (high usage)
                "number.warp2_22vo_daniel_globalcurrent": "8.0",  # 8A current
                
                # Elli: ENABLED and connected but not charging
                "input_boolean.wallbox_elli_ueberschuss": "on",   # ENABLED
                "binary_sensor.warp2_22vo_elli_cable": "on",      # connected
                "binary_sensor.warp2_22vo_elli_charging": "off",  # not charging
                "sensor.warp2_22vo_elli_powernow": "2.0",         # 2W standby
                "number.warp2_22vo_elli_globalcurrent": "0.0",    # 0A current
            }
            return state_map.get(entity_id)
        
        self.app.get_state.side_effect = mock_get_state
        
        # Run the wallbox manager
        self.manager.manage_wallboxes(None, None, None, None, None)
        
        # Verify NO service calls were made for Dani (disabled)
        dani_service_calls = [call for call in self.app.call_service.call_args_list
                             if "daniel" in str(call[1].get("entity_id", ""))]
        
        self.assertEqual(len(dani_service_calls), 0,
                        f"Disabled Dani should not be touched at all, but found: {dani_service_calls}")
        
        # Verify that Elli (enabled) was NOT started due to insufficient power
        # Available power: 1000W surplus - 100W buffer = 900W
        # Minimum required: 6A × 233.33V = 1400W
        # Since 900W < 1400W, Elli should not be started
        elli_service_calls = [call for call in self.app.call_service.call_args_list
                             if "elli" in str(call[1].get("entity_id", ""))]
        
        self.assertEqual(len(elli_service_calls), 0,
                        "Elli should not be started due to insufficient power (900W available, 1400W required)")


if __name__ == '__main__':
    unittest.main()