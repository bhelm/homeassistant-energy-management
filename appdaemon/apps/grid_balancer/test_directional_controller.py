#!/usr/bin/env python3
"""Test script to verify the directional adjustment controller"""

import sys
import os
from datetime import datetime, timedelta

# Add the grid_balancer directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from directional_adjustment_controller import DirectionalAdjustmentController

def test_directional_controller():
    """Test the directional adjustment controller functionality"""
    print("🧪 Testing Directional Adjustment Controller")
    print("=" * 60)
    
    # Create controller with 4 second cooldown for testing
    controller = DirectionalAdjustmentController(cooldown_seconds=4.0, min_change_threshold_w=100.0)
    
    base_time = datetime.now()
    
    # Test 1: Under-correction scenario (your main concern)
    print("\n📊 Test 1: Under-Correction Scenario")
    print("-" * 50)
    print("Scenario: Grid -2000W → Battery +2000W → Grid goes to -4000W (under-corrected)")
    
    # First adjustment
    controller.record_adjustment(
        grid_power=-2000.0,  # Exporting 2kW
        new_battery_target=2000.0,  # Charge battery
        previous_battery_target=0.0,
        timestamp=base_time
    )
    
    # Simulate under-correction: grid goes even more negative (more export)
    controller.time_provider = lambda: base_time + timedelta(seconds=1.0)
    
    allowed = controller.should_allow_adjustment(
        current_grid_power=-4000.0,  # Even more export - under-corrected!
        proposed_battery_target=4000.0,
        current_battery_target=2000.0
    )
    
    direction_info = controller.get_direction_info(-4000.0)
    
    print(f"Grid at adjustment: {direction_info['grid_at_adjustment']:+.0f}W")
    print(f"Current grid: {direction_info['current_grid']:+.0f}W")
    print(f"Grid change: {direction_info['grid_change']:+.0f}W")
    print(f"Expected direction: {direction_info['expected_direction']}")
    print(f"Actual direction: {direction_info['actual_direction']}")
    print(f"Under-corrected: {'✅ Yes' if direction_info['under_corrected'] else '❌ No'}")
    print(f"Immediate adjustment allowed: {'✅ Yes' if allowed else '❌ No'}")
    
    # Test 2: Over-correction scenario (oscillation risk)
    print("\n📊 Test 2: Over-Correction Scenario")
    print("-" * 50)
    print("Scenario: Grid +2000W → Battery -2000W → Grid goes to -1000W (over-corrected)")
    
    controller = DirectionalAdjustmentController(cooldown_seconds=4.0, min_change_threshold_w=100.0)
    
    # First adjustment
    controller.record_adjustment(
        grid_power=2000.0,  # Importing 2kW
        new_battery_target=-2000.0,  # Discharge battery
        previous_battery_target=0.0,
        timestamp=base_time
    )
    
    # Simulate over-correction: grid swings to export (opposite direction)
    controller.time_provider = lambda: base_time + timedelta(seconds=1.0)
    
    allowed = controller.should_allow_adjustment(
        current_grid_power=-1000.0,  # Now exporting - over-corrected!
        proposed_battery_target=-1000.0,
        current_battery_target=-2000.0
    )
    
    direction_info = controller.get_direction_info(-1000.0)
    
    print(f"Grid at adjustment: {direction_info['grid_at_adjustment']:+.0f}W")
    print(f"Current grid: {direction_info['current_grid']:+.0f}W")
    print(f"Grid change: {direction_info['grid_change']:+.0f}W")
    print(f"Expected direction: {direction_info['expected_direction']}")
    print(f"Actual direction: {direction_info['actual_direction']}")
    print(f"Over-corrected: {'✅ Yes' if not direction_info['under_corrected'] else '❌ No'}")
    print(f"Immediate adjustment blocked: {'✅ Yes' if not allowed else '❌ No'}")
    
    # Test 3: Normal correction (grid moves toward zero as expected)
    print("\n📊 Test 3: Normal Correction")
    print("-" * 50)
    print("Scenario: Grid +2000W → Battery -2000W → Grid goes to +500W (good correction)")
    
    controller = DirectionalAdjustmentController(cooldown_seconds=4.0, min_change_threshold_w=100.0)
    
    # First adjustment
    controller.record_adjustment(
        grid_power=2000.0,  # Importing 2kW
        new_battery_target=-2000.0,  # Discharge battery
        previous_battery_target=0.0,
        timestamp=base_time
    )
    
    # Simulate good correction: grid moves toward zero but not quite there
    controller.time_provider = lambda: base_time + timedelta(seconds=1.0)
    
    allowed = controller.should_allow_adjustment(
        current_grid_power=500.0,  # Still importing but much less
        proposed_battery_target=-2500.0,
        current_battery_target=-2000.0
    )
    
    direction_info = controller.get_direction_info(500.0)
    
    print(f"Grid at adjustment: {direction_info['grid_at_adjustment']:+.0f}W")
    print(f"Current grid: {direction_info['current_grid']:+.0f}W")
    print(f"Grid change: {direction_info['grid_change']:+.0f}W")
    print(f"Expected direction: {direction_info['expected_direction']}")
    print(f"Actual direction: {direction_info['actual_direction']}")
    print(f"Good correction: {'✅ Yes' if direction_info['direction_match'] else '❌ No'}")
    print(f"Fine-tuning allowed: {'✅ Yes' if allowed else '❌ No'}")
    
    # Test 4: After cooldown period
    print("\n📊 Test 4: After Cooldown Period")
    print("-" * 50)
    
    controller.time_provider = lambda: base_time + timedelta(seconds=5.0)
    
    allowed = controller.should_allow_adjustment(
        current_grid_power=-1000.0,  # Any grid state
        proposed_battery_target=-1000.0,
        current_battery_target=-2000.0
    )
    
    status = controller.get_status_info()
    time_since_last = status.get('time_since_last_adjustment', 0)
    
    print(f"Time since last adjustment: {time_since_last:.1f}s")
    print(f"Cooldown period: {status['cooldown_seconds']:.1f}s")
    print(f"Adjustment allowed: {'✅ Yes' if allowed else '❌ No'}")
    
    print("\n✅ Directional controller test completed!")
    print("\nBehavior Summary:")
    print("• 🎯 Under-correction: Immediate fix allowed (grid moves same direction)")
    print("• 🛡️ Over-correction: Cooldown enforced (grid moves opposite direction)")
    print("• ⚡ Normal correction: Fine-tuning allowed")
    print("• ⏰ After cooldown: All adjustments allowed")
    print("• 🧠 Smart logic prevents oscillation while allowing rapid under-correction fixes!")

if __name__ == "__main__":
    test_directional_controller()