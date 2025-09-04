"""
Tests for Simplified WallboxPriorityController
Tests the new simple logic with only two rules:
1. If wallbox consuming power: reduce battery target by 1000W
2. If wallbox charging: prevent battery discharge
"""

import pytest
import sys
import os
from unittest.mock import Mock

# Add the grid_balancer directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wallbox_priority_controller import WallboxPriorityController


def test_simplified_wallbox_priority_scenarios():
    """Test simplified wallbox priority scenarios"""
    print("=== TESTING SIMPLIFIED WALLBOX PRIORITY SCENARIOS ===")
    
    # Create mock app instance
    mock_app = Mock()
    mock_app.log = Mock()
    
    # Create controller with simplified configuration
    controller = WallboxPriorityController({
        'enabled': True,
        'wallbox_power_sensor': 'sensor.wallbox_power',
        'wallbox_power_threshold_w': 100,  # Minimum power to consider "active"
        'wallbox_reserve_power_w': 1000    # Power to reserve when active
    }, mock_app)
    
    # Mock get_state function
    def mock_get_state(entity_id):
        return test_states.get(entity_id, 0.0)
    
    mock_app.get_state = mock_get_state
    
    # Test scenarios for simplified logic
    scenarios = [
        {
            'name': 'No wallbox activity',
            'states': {
                'sensor.wallbox_power': 0.0
            },
            'grid_power': -2000.0,  # Not used in simplified logic
            'normal_battery_target': 1950.0,
            'expected_allowed': 1950.0,
            'expected_reason': 'No wallbox activity'
        },
        {
            'name': 'Wallbox below threshold - no action',
            'states': {
                'sensor.wallbox_power': 50.0  # Below 100W threshold
            },
            'grid_power': -2000.0,
            'normal_battery_target': 1950.0,
            'expected_allowed': 1950.0,
            'expected_reason': 'No wallbox activity'
        },
        {
            'name': 'Wallbox active - reserve 1000W',
            'states': {
                'sensor.wallbox_power': 1500.0  # Above 100W threshold
            },
            'grid_power': -2000.0,
            'normal_battery_target': 1950.0,
            'expected_allowed': 950.0,  # 1950 - 1000 reserve
            'expected_reason': 'reserved 1000W'
        },
        {
            'name': 'Wallbox active - reserve more than available',
            'states': {
                'sensor.wallbox_power': 800.0
            },
            'grid_power': -1000.0,
            'normal_battery_target': 500.0,
            'expected_allowed': 0.0,  # max(0, 500-1000) = 0
            'expected_reason': 'reserved 1000W'
        },
        {
            'name': 'Wallbox active - prevent discharge',
            'states': {
                'sensor.wallbox_power': 1200.0
            },
            'grid_power': 500.0,  # Importing power
            'normal_battery_target': -450.0,  # Would discharge battery
            'expected_allowed': 0.0,
            'expected_reason': 'prevent battery discharge'
        },
        {
            'name': 'Wallbox just at threshold',
            'states': {
                'sensor.wallbox_power': 100.0  # Exactly at threshold
            },
            'grid_power': -1500.0,
            'normal_battery_target': 1400.0,
            'expected_allowed': 400.0,  # 1400 - 1000 reserve
            'expected_reason': 'reserved 1000W'
        },
        {
            'name': 'High wallbox power consumption',
            'states': {
                'sensor.wallbox_power': 3000.0  # High consumption
            },
            'grid_power': -4000.0,
            'normal_battery_target': 3950.0,
            'expected_allowed': 2950.0,  # 3950 - 1000 reserve
            'expected_reason': 'reserved 1000W'
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n--- Test {i}: {scenario['name']} ---")
        
        # Set up test states
        test_states = scenario['states']
        
        # Calculate allowed battery power
        allowed_power, reason = controller.calculate_allowed_battery_power(
            scenario['grid_power'],
            scenario['normal_battery_target']
        )
        
        print(f"Grid Power: {scenario['grid_power']}W (not used in simplified logic)")
        print(f"Normal Battery Target: {scenario['normal_battery_target']}W")
        print(f"Wallbox Power: {test_states['sensor.wallbox_power']}W")
        print(f"Expected Allowed: {scenario['expected_allowed']}W")
        print(f"Actual Allowed: {allowed_power}W")
        print(f"Reason: {reason}")
        
        assert allowed_power == scenario['expected_allowed'], \
            f"Expected {scenario['expected_allowed']}W, got {allowed_power}W"
        assert scenario['expected_reason'] in reason, \
            f"Expected reason containing '{scenario['expected_reason']}', got '{reason}'"
        
        print("✓ PASSED")
    
    print(f"\n✅ All {len(scenarios)} simplified wallbox priority scenarios passed!")


def test_simplified_error_handling_scenarios():
    """Test error handling and edge cases for simplified logic"""
    print("\n=== TESTING SIMPLIFIED ERROR HANDLING SCENARIOS ===")
    
    # Create mock app instance
    mock_app = Mock()
    mock_app.log = Mock()
    
    controller = WallboxPriorityController({
        'enabled': True,
        'wallbox_power_sensor': 'sensor.wallbox_power',
        'wallbox_power_threshold_w': 100,
        'wallbox_reserve_power_w': 1000
    }, mock_app)
    
    # Test scenarios with error conditions
    error_scenarios = [
        {
            'name': 'Missing wallbox power sensor',
            'mock_get_state': lambda entity_id: None if entity_id == 'sensor.wallbox_power' else 0.0,
            'grid_power': 2000.0,
            'normal_battery_target': 1950.0,
            'expected_allowed': 1950.0,  # Should fall back to normal operation
            'expected_reason': 'No wallbox activity'  # Controller handles None gracefully
        },
        {
            'name': 'Invalid wallbox power value',
            'mock_get_state': lambda entity_id: 'invalid' if entity_id == 'sensor.wallbox_power' else 0.0,
            'grid_power': 2000.0,
            'normal_battery_target': 1950.0,
            'expected_allowed': 1950.0,
            'expected_reason': 'No wallbox activity'  # Controller handles invalid values gracefully
        },
        {
            'name': 'Disabled controller',
            'controller_config': {'enabled': False},
            'mock_get_state': lambda entity_id: 1500.0 if 'wallbox' in entity_id else 0.0,
            'grid_power': 1500.0,
            'normal_battery_target': 1450.0,
            'expected_allowed': 1450.0,
            'expected_reason': 'Priority controller disabled'
        },
        {
            'name': 'Extreme power values',
            'mock_get_state': lambda entity_id: 50000.0 if entity_id == 'sensor.wallbox_power' else 0.0,
            'grid_power': -100000.0,  # Exporting 100kW
            'normal_battery_target': 99950.0,
            'expected_allowed': 98950.0,  # 99950 - 1000 reserve
            'expected_reason': 'reserved 1000W'
        },
        {
            'name': 'Zero battery target with wallbox active',
            'mock_get_state': lambda entity_id: 800.0 if entity_id == 'sensor.wallbox_power' else 0.0,
            'grid_power': -500.0,
            'normal_battery_target': 0.0,
            'expected_allowed': 0.0,  # max(0, 0-1000) = 0
            'expected_reason': 'reserved 1000W'
        },
        {
            'name': 'Negative battery target with wallbox active',
            'mock_get_state': lambda entity_id: 1200.0 if entity_id == 'sensor.wallbox_power' else 0.0,
            'grid_power': 300.0,
            'normal_battery_target': -200.0,
            'expected_allowed': 0.0,
            'expected_reason': 'prevent battery discharge'
        }
    ]
    
    for i, scenario in enumerate(error_scenarios, 1):
        print(f"\n--- Error Test {i}: {scenario['name']} ---")
        
        # Create controller with custom config if specified
        if 'controller_config' in scenario:
            test_mock_app = Mock()
            test_mock_app.log = Mock()
            test_controller = WallboxPriorityController(scenario['controller_config'], test_mock_app)
        else:
            test_controller = controller
        
        # Set up mock get_state
        test_controller.app.get_state = scenario['mock_get_state']
        
        # Calculate allowed battery power
        allowed_power, reason = test_controller.calculate_allowed_battery_power(
            scenario['grid_power'], 
            scenario['normal_battery_target']
        )
        
        print(f"Expected Allowed: {scenario['expected_allowed']}W")
        print(f"Actual Allowed: {allowed_power}W")
        print(f"Reason: {reason}")
        
        assert allowed_power == scenario['expected_allowed'], \
            f"Expected {scenario['expected_allowed']}W, got {allowed_power}W"
        assert scenario['expected_reason'] in reason, \
            f"Expected reason containing '{scenario['expected_reason']}', got '{reason}'"
        
        print("✓ PASSED")
    
    print(f"\n✅ All {len(error_scenarios)} error handling scenarios passed!")


def test_simplified_status_info():
    """Test status information methods for simplified logic"""
    print("\n=== TESTING SIMPLIFIED STATUS INFO METHODS ===")
    
    # Create mock app instance
    mock_app = Mock()
    mock_app.log = Mock()
    
    controller = WallboxPriorityController({
        'enabled': True,
        'wallbox_power_sensor': 'sensor.wallbox_power',
        'wallbox_power_threshold_w': 100,
        'wallbox_reserve_power_w': 1000
    }, mock_app)
    
    # Mock get_state function
    mock_app.get_state = lambda entity_id: {
        'sensor.wallbox_power': 1500.0
    }.get(entity_id, 0.0)
    
    # Test get_status_info
    status = controller.get_status_info()
    
    print("Simplified Status Info:")
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    assert status['enabled'] is True
    assert status['wallbox_current_power'] == 1500.0
    assert status['wallbox_is_active'] is True  # 1500W >= 100W threshold
    assert status['wallbox_power_threshold_w'] == 100
    assert status['wallbox_reserve_power_w'] == 1000
    
    print("✅ Simplified status info test passed!")


if __name__ == '__main__':
    test_simplified_wallbox_priority_scenarios()
    test_simplified_error_handling_scenarios()
    test_simplified_status_info()
    print("\n🎉 All simplified wallbox priority tests completed successfully!")