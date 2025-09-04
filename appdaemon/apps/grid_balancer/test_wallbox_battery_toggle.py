#!/usr/bin/env python3
"""
Test script for wallbox battery use toggle functionality
Tests both toggle OFF (prevent discharge) and toggle ON (allow discharge) scenarios
"""

import sys
import os

# Add the grid_balancer directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from wallbox_priority_controller import WallboxPriorityController

class MockApp:
    """Mock AppDaemon app for testing"""
    def __init__(self, wallbox_power=0):
        self.wallbox_power = wallbox_power
        self.logs = []
    
    def get_state(self, entity):
        """Mock get_state method"""
        if 'wallbox' in entity.lower():
            return str(self.wallbox_power)
        return "0"
    
    def log(self, message, level="INFO"):
        """Mock log method"""
        self.logs.append(f"[{level}] {message}")
        print(f"[{level}] {message}")

def test_wallbox_battery_toggle():
    """Test wallbox battery use toggle functionality"""
    print("=" * 80)
    print("TESTING WALLBOX BATTERY USE TOGGLE FUNCTIONALITY")
    print("=" * 80)
    
    # Test configuration
    config = {
        'enabled': True,
        'wallbox_power_threshold_w': 100,
        'wallbox_reserve_power_w': 1000,
        'wallbox_power_sensor': 'sensor.gesamt_wallboxen_w'
    }
    
    # Test scenarios
    scenarios = [
        {
            'name': 'No wallbox activity',
            'wallbox_power': 0,
            'battery_target': -2000,  # Want to discharge 2000W
            'toggle_off_expected': -2000,  # Should allow discharge
            'toggle_on_expected': -2000,   # Should allow discharge
        },
        {
            'name': 'Wallbox charging (1500W)',
            'wallbox_power': 1500,
            'battery_target': -2000,  # Want to discharge 2000W
            'toggle_off_expected': 0,      # Should prevent discharge
            'toggle_on_expected': -2000,   # Should allow discharge
        },
        {
            'name': 'Wallbox charging, battery charging target',
            'wallbox_power': 1500,
            'battery_target': 3000,   # Want to charge 3000W
            'toggle_off_expected': 2000,   # Should reduce by 1000W (reserve)
            'toggle_on_expected': 2000,    # Should reduce by 1000W (reserve)
        },
        {
            'name': 'Low wallbox power (below threshold)',
            'wallbox_power': 50,      # Below 100W threshold
            'battery_target': -2000,  # Want to discharge 2000W
            'toggle_off_expected': -2000,  # Should allow discharge (wallbox not "active")
            'toggle_on_expected': -2000,   # Should allow discharge
        }
    ]
    
    for scenario in scenarios:
        print(f"\n--- SCENARIO: {scenario['name']} ---")
        print(f"Wallbox Power: {scenario['wallbox_power']}W")
        print(f"Desired Battery Target: {scenario['battery_target']}W")
        
        # Create mock app with wallbox power
        mock_app = MockApp(wallbox_power=scenario['wallbox_power'])
        controller = WallboxPriorityController(config, mock_app)
        
        # Test with toggle OFF (default behavior)
        print(f"\n🔴 TOGGLE OFF (Prevent discharge when wallbox charging):")
        result_off, reason_off = controller.calculate_allowed_battery_power(
            grid_power=1000,  # Not used in simplified logic
            normal_battery_target=scenario['battery_target'],
            allow_wallbox_battery_use=False
        )
        print(f"  Result: {result_off}W (Expected: {scenario['toggle_off_expected']}W)")
        print(f"  Reason: {reason_off}")
        
        # Test with toggle ON (allow discharge)
        print(f"\n🟢 TOGGLE ON (Allow discharge even when wallbox charging):")
        result_on, reason_on = controller.calculate_allowed_battery_power(
            grid_power=1000,  # Not used in simplified logic
            normal_battery_target=scenario['battery_target'],
            allow_wallbox_battery_use=True
        )
        print(f"  Result: {result_on}W (Expected: {scenario['toggle_on_expected']}W)")
        print(f"  Reason: {reason_on}")
        
        # Validate results
        toggle_off_correct = result_off == scenario['toggle_off_expected']
        toggle_on_correct = result_on == scenario['toggle_on_expected']
        
        print(f"\n✅ VALIDATION:")
        print(f"  Toggle OFF: {'✓ PASS' if toggle_off_correct else '✗ FAIL'}")
        print(f"  Toggle ON:  {'✓ PASS' if toggle_on_correct else '✗ FAIL'}")
        
        if not (toggle_off_correct and toggle_on_correct):
            print(f"  ❌ SCENARIO FAILED!")
            return False
        else:
            print(f"  ✅ SCENARIO PASSED!")
    
    print("\n" + "=" * 80)
    print("🎉 ALL TESTS PASSED! Wallbox battery use toggle is working correctly.")
    print("=" * 80)
    return True

if __name__ == "__main__":
    success = test_wallbox_battery_toggle()
    sys.exit(0 if success else 1)