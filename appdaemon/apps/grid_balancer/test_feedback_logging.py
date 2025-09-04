#!/usr/bin/env python3
"""Test script to verify enhanced feedback latency logging"""

import sys
import os
from datetime import datetime, timedelta

# Add the grid_balancer directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from adjustment_controller import AdjustmentController

def test_feedback_latency_logging():
    """Test the enhanced feedback latency logging functionality"""
    print("🧪 Testing Enhanced Feedback Latency Logging")
    print("=" * 50)
    
    # Create controller with short timeout for testing
    controller = AdjustmentController(
        feedback_threshold_ratio=0.4,
        max_timeout_s=1.0,  # Short timeout for testing
        large_change_threshold_w=500.0
    )
    
    base_time = datetime.now()
    
    # Test 1: Successful feedback detection
    print("\n📊 Test 1: Successful Feedback Detection")
    print("-" * 40)
    
    # Record a large adjustment
    controller.record_adjustment(
        grid_power=1000.0,
        new_battery_target=-2000.0,
        previous_battery_target=-1000.0,
        timestamp=base_time
    )
    
    # Simulate time passing and grid responding correctly
    controller.time_provider = lambda: base_time + timedelta(seconds=0.5)
    
    # Check if adjustment is blocked (should be waiting for feedback)
    blocked = not controller.should_allow_adjustment(
        current_grid_power=0.0,  # Grid responded well (1000W reduction)
        proposed_battery_target=-2500.0,
        current_battery_target=-2000.0
    )
    
    feedback_details = controller.get_feedback_details()
    feedback_success = controller.get_feedback_success_info()
    
    if feedback_details:
        print(f"⏱️ Feedback Check - Elapsed: {feedback_details['elapsed_time']:.3f}s")
        print(f"   Expected Change: {feedback_details['expected_change']:+.0f}W")
        print(f"   Actual Change: {feedback_details['actual_change']:+.0f}W")
        print(f"   Magnitude Ratio: {feedback_details['magnitude_ratio']:.1%}")
        print(f"   Direction OK: {'✓' if feedback_details['direction_correct'] else '✗'}")
        print(f"   Magnitude OK: {'✓' if feedback_details['magnitude_sufficient'] else '✗'}")
        print(f"   Feedback Detected: {'✅' if feedback_details['detected'] else '❌'}")
    
    if feedback_success:
        print(f"✅ SUCCESS - Latency: {feedback_success['elapsed_time']:.3f}s")
        print(f"   Expected: {feedback_success['expected_change']:+.0f}W")
        print(f"   Actual: {feedback_success['actual_change']:+.0f}W ({feedback_success['magnitude_ratio']:.1%})")
    
    # Test 2: Feedback timeout
    print("\n📊 Test 2: Feedback Timeout")
    print("-" * 40)
    
    # Reset controller
    controller = AdjustmentController(
        feedback_threshold_ratio=0.4,
        max_timeout_s=0.5,  # Very short timeout
        large_change_threshold_w=500.0
    )
    
    # Record another large adjustment
    controller.record_adjustment(
        grid_power=1000.0,
        new_battery_target=-2000.0,
        previous_battery_target=-1000.0,
        timestamp=base_time
    )
    
    # Simulate timeout (no grid response)
    controller.time_provider = lambda: base_time + timedelta(seconds=1.0)
    
    # Check if adjustment is allowed (should timeout and allow)
    allowed = controller.should_allow_adjustment(
        current_grid_power=1000.0,  # No grid response
        proposed_battery_target=-2500.0,
        current_battery_target=-2000.0
    )
    
    feedback_timeout = controller.get_feedback_timeout_info()
    
    if feedback_timeout:
        print(f"⏰ TIMEOUT - Waited {feedback_timeout['elapsed_time']:.3f}s")
        print(f"   Max Timeout: {feedback_timeout['max_timeout']:.1f}s")
        print(f"   Reason: {feedback_timeout['reason']}")
    
    # Test 3: Small change (time-based cooldown)
    print("\n📊 Test 3: Small Change (Time-based Cooldown)")
    print("-" * 40)
    
    controller = AdjustmentController(
        feedback_threshold_ratio=0.4,
        max_timeout_s=1.0,
        large_change_threshold_w=500.0
    )
    
    # Record a small adjustment
    controller.record_adjustment(
        grid_power=1000.0,
        new_battery_target=-1200.0,  # Only 200W change
        previous_battery_target=-1000.0,
        timestamp=base_time
    )
    
    # Check immediately (should be blocked)
    controller.time_provider = lambda: base_time + timedelta(seconds=0.1)
    blocked = not controller.should_allow_adjustment(
        current_grid_power=800.0,
        proposed_battery_target=-1400.0,
        current_battery_target=-1200.0
    )
    
    status = controller.get_status_info()
    print(f"Small change cooldown - Time since adjustment: {status['time_since_small_adjustment']:.3f}s")
    print(f"Blocked: {'Yes' if blocked else 'No'}")
    
    # Check after timeout
    controller.time_provider = lambda: base_time + timedelta(seconds=1.5)
    allowed = controller.should_allow_adjustment(
        current_grid_power=800.0,
        proposed_battery_target=-1400.0,
        current_battery_target=-1200.0
    )
    
    status = controller.get_status_info()
    print(f"After timeout - Time since adjustment: {status['time_since_small_adjustment']:.3f}s")
    print(f"Allowed: {'Yes' if allowed else 'No'}")
    
    print("\n✅ Enhanced feedback logging test completed!")
    print("\nNow your logs will show:")
    print("• ⏱️ FEEDBACK LATENCY - Real-time feedback waiting with detailed metrics")
    print("• ✅ FEEDBACK DETECTED - Successful feedback with precise timing")
    print("• ⏰ FEEDBACK TIMEOUT - When system doesn't respond in time")
    print("• Clear visibility into your system's response latency!")

if __name__ == "__main__":
    test_feedback_latency_logging()