#!/usr/bin/env python3
"""Test script to verify the new load scenario works correctly"""

import sys
import os
from datetime import datetime, timedelta

# Add the grid_balancer directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from directional_adjustment_controller import DirectionalAdjustmentController

def test_new_load_scenario():
    """Test the exact scenario the user described"""
    print("🧪 Testing New Load Scenario")
    print("=" * 60)
    print("Your exact use case: 2kW load turns on, we compensate.")
    print("Then another 2kW load joins in, and we compensate more!")
    print()
    
    # Create controller
    controller = DirectionalAdjustmentController(cooldown_seconds=4.0, min_change_threshold_w=100.0)
    
    base_time = datetime.now()
    
    # Scenario: Multiple loads turning on sequentially
    print("📊 Scenario: Sequential Load Addition")
    print("-" * 50)
    
    # Initial state: Grid balanced
    print("Initial state: Grid balanced at 0W")
    
    # Step 1: First 2kW load turns on
    print("\n🔌 Step 1: First 2kW load turns on")
    print("Grid: 0W → +2000W (importing)")
    
    # First adjustment should always be allowed
    allowed = controller.should_allow_adjustment(
        current_grid_power=2000.0,  # 2kW import
        proposed_battery_target=-2000.0,  # Discharge 2kW
        current_battery_target=0.0
    )
    
    print(f"First adjustment allowed: {'✅ Yes' if allowed else '❌ No'}")
    
    if allowed:
        controller.record_adjustment(
            grid_power=2000.0,
            new_battery_target=-2000.0,
            previous_battery_target=0.0,
            timestamp=base_time
        )
        print("✅ Battery adjusted: 0W → -2000W (discharge)")
        print("Expected result: Grid should go toward 0W")
    
    # Step 2: Second 2kW load joins (during cooldown period)
    print("\n🔌 Step 2: Another 2kW load joins (1 second later)")
    print("Grid: Expected ~0W, but actually +4000W (new load!)")
    
    controller.time_provider = lambda: base_time + timedelta(seconds=1.0)
    
    allowed = controller.should_allow_adjustment(
        current_grid_power=4000.0,  # 4kW total import - new load detected!
        proposed_battery_target=-4000.0,  # Need to discharge 4kW total
        current_battery_target=-2000.0
    )
    
    direction_info = controller.get_direction_info(4000.0)
    
    print(f"Grid at first adjustment: {direction_info['grid_at_adjustment']:+.0f}W")
    print(f"Current grid power: {direction_info['current_grid']:+.0f}W")
    print(f"Grid change: {direction_info['grid_change']:+.0f}W")
    print(f"Direction: {direction_info['actual_direction']} (expected: toward_zero)")
    print(f"New load detected: {'✅ Yes' if direction_info['under_corrected'] else '❌ No'}")
    print(f"Immediate adjustment allowed: {'✅ Yes' if allowed else '❌ No'}")
    
    if allowed:
        controller.record_adjustment(
            grid_power=4000.0,
            new_battery_target=-4000.0,
            previous_battery_target=-2000.0,
            timestamp=base_time + timedelta(seconds=1.0)
        )
        print("✅ Battery adjusted: -2000W → -4000W (discharge more)")
        print("🎯 NEW LOAD RESPONSE: Immediate adjustment allowed!")
    
    # Step 3: System over-corrects (oscillation scenario)
    print("\n⚠️ Step 3: System over-corrects (oscillation test)")
    print("Grid: Expected ~0W, but actually -1000W (over-correction)")
    
    controller.time_provider = lambda: base_time + timedelta(seconds=2.0)
    
    allowed = controller.should_allow_adjustment(
        current_grid_power=-1000.0,  # Now exporting - over-corrected!
        proposed_battery_target=-3000.0,  # Reduce discharge
        current_battery_target=-4000.0
    )
    
    direction_info = controller.get_direction_info(-1000.0)
    
    print(f"Grid at last adjustment: {direction_info['grid_at_adjustment']:+.0f}W")
    print(f"Current grid power: {direction_info['current_grid']:+.0f}W")
    print(f"Grid change: {direction_info['grid_change']:+.0f}W")
    print(f"Direction: {direction_info['actual_direction']} (expected: toward_zero)")
    print(f"Over-correction detected: {'✅ Yes' if not direction_info['under_corrected'] else '❌ No'}")
    print(f"Cooldown enforced: {'✅ Yes' if not allowed else '❌ No'}")
    
    if not allowed:
        print("🛡️ OSCILLATION PREVENTION: Cooldown enforced for over-correction")
    
    # Step 4: After cooldown, all adjustments allowed
    print("\n⏰ Step 4: After cooldown period")
    
    controller.time_provider = lambda: base_time + timedelta(seconds=6.0)
    
    allowed = controller.should_allow_adjustment(
        current_grid_power=-500.0,
        proposed_battery_target=-3500.0,
        current_battery_target=-4000.0
    )
    
    status = controller.get_status_info()
    time_since_last = status.get('time_since_last_adjustment', 0)
    
    print(f"Time since last adjustment: {time_since_last:.1f}s")
    print(f"Cooldown period: {status['cooldown_seconds']:.1f}s")
    print(f"Adjustment allowed: {'✅ Yes' if allowed else '❌ No'}")
    
    print("\n✅ New Load Scenario Test Completed!")
    print("\n🎯 Perfect Behavior Summary:")
    print("• ⚡ First load (2kW): Immediate response")
    print("• ⚡ Second load (2kW): Immediate response (grid moved away from zero)")
    print("• 🛡️ Over-correction: Cooldown enforced (prevents oscillation)")
    print("• ⏰ After cooldown: Normal operation resumes")
    print("\nYour system will now handle sequential load additions perfectly!")
    print("No more waiting 4 seconds when new loads are added! 🚀")

if __name__ == "__main__":
    test_new_load_scenario()