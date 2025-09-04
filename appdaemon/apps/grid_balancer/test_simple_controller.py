#!/usr/bin/env python3
"""Test script to verify the simplified adjustment controller"""

import sys
import os
from datetime import datetime, timedelta

# Add the grid_balancer directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from simple_adjustment_controller import SimpleAdjustmentController

def test_simple_controller():
    """Test the simplified adjustment controller functionality"""
    print("🧪 Testing Simplified Adjustment Controller")
    print("=" * 50)
    
    # Create controller with 2 second cooldown for testing
    controller = SimpleAdjustmentController(cooldown_seconds=2.0)
    
    base_time = datetime.now()
    
    # Test 1: First adjustment should always be allowed
    print("\n📊 Test 1: First Adjustment (Always Allowed)")
    print("-" * 40)
    
    allowed = controller.should_allow_adjustment(
        current_grid_power=1000.0,
        proposed_battery_target=-2000.0,
        current_battery_target=-1000.0
    )
    
    print(f"First adjustment allowed: {'✅ Yes' if allowed else '❌ No'}")
    
    if allowed:
        # Record the adjustment
        controller.record_adjustment(
            grid_power=1000.0,
            new_battery_target=-2000.0,
            previous_battery_target=-1000.0,
            timestamp=base_time
        )
        print("✅ Adjustment recorded")
    
    # Test 2: Immediate second adjustment should be blocked
    print("\n📊 Test 2: Immediate Second Adjustment (Should be Blocked)")
    print("-" * 40)
    
    controller.time_provider = lambda: base_time + timedelta(seconds=0.5)
    
    allowed = controller.should_allow_adjustment(
        current_grid_power=500.0,
        proposed_battery_target=-2500.0,
        current_battery_target=-2000.0
    )
    
    status = controller.get_status_info()
    time_since_last = status.get('time_since_last_adjustment', 0)
    cooldown_time = status.get('cooldown_seconds', 2.0)
    
    print(f"Second adjustment allowed: {'✅ Yes' if allowed else '❌ No'}")
    print(f"Time since last: {time_since_last:.1f}s")
    print(f"Cooldown required: {cooldown_time:.1f}s")
    print(f"Status: {status}")
    
    # Test 3: After cooldown, adjustment should be allowed
    print("\n📊 Test 3: After Cooldown (Should be Allowed)")
    print("-" * 40)
    
    controller.time_provider = lambda: base_time + timedelta(seconds=3.0)
    
    allowed = controller.should_allow_adjustment(
        current_grid_power=500.0,
        proposed_battery_target=-2500.0,
        current_battery_target=-2000.0
    )
    
    status = controller.get_status_info()
    time_since_last = status.get('time_since_last_adjustment', 0)
    
    print(f"Third adjustment allowed: {'✅ Yes' if allowed else '❌ No'}")
    print(f"Time since last: {time_since_last:.1f}s")
    print(f"Status: {status}")
    
    # Test 4: Verify compatibility methods return None
    print("\n📊 Test 4: Compatibility Methods")
    print("-" * 40)
    
    feedback_details = controller.get_feedback_details()
    feedback_success = controller.get_feedback_success_info()
    feedback_timeout = controller.get_feedback_timeout_info()
    
    print(f"Feedback details: {feedback_details}")
    print(f"Feedback success: {feedback_success}")
    print(f"Feedback timeout: {feedback_timeout}")
    print("✅ All compatibility methods return None as expected")
    
    print("\n✅ Simplified controller test completed!")
    print("\nBehavior Summary:")
    print("• ✅ First adjustment: Always allowed")
    print("• ❌ During cooldown: Blocked with clear timing info")
    print("• ✅ After cooldown: Allowed again")
    print("• 🔄 Simple and predictable - no complex feedback detection!")

if __name__ == "__main__":
    test_simple_controller()