"""
Test to verify damping behavior matches expected logic:
1. Oscillation between 500W and 1000W with 0.5 damping → should settle at ~750W
2. Baseline shift to 1500W → should respond immediately to 1500W
"""
import unittest
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path to import oscillation_detector
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from oscillation_detector import OscillationDetector


class TestDampingBehaviorVerification(unittest.TestCase):
    """Verify damping behavior matches user expectations"""
    
    def setUp(self):
        """Set up test with 0.5 damping factor"""
        self.config = {
            'enabled': True,
            'min_amplitude_w': 100.0,
            'min_cycles': 2,
            'max_cycle_duration_s': 10.0,
            'history_duration_s': 30.0,
            'stabilization_factor': 1.1,
            'detection_sensitivity': 0.8,
            'baseline_smoothing_factor': 0.1,
            'baseline_shift_threshold_w': 300.0,
            'damping_factor': 0.5,  # 50% damping
            'damping_strategy': 'proportional'
        }
        self.detector = OscillationDetector(self.config)
        self.base_time = datetime.now()
    
    def test_oscillation_500_to_1000w_should_settle_at_750w(self):
        """
        Test: Battery oscillating between 500W and 1000W with 0.5 damping
        Expected: Should settle at approximately 750W (the middle)
        """
        print("\n=== TEST: Oscillation 500W-1000W with 0.5 damping ===")
        
        # Create oscillation pattern: 500W ↔ 1000W
        oscillation_data = []
        for i in range(20):  # 10 complete cycles
            if i % 4 < 2:  # High phase (1000W)
                power = 1000.0
            else:  # Low phase (500W)
                power = 500.0
            
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            oscillation_data.append((power, timestamp))
        
        # Feed data to detector
        for power, timestamp in oscillation_data:
            self.detector.add_power_reading(power, timestamp)
        
        # Verify oscillation is detected
        self.assertTrue(self.detector.is_oscillating(), "Should detect oscillation")
        
        # Get oscillation info
        info = self.detector.get_oscillation_info()
        print(f"Detected amplitude: {info['amplitude_w']}W")
        print(f"Detected baseline: {info['baseline_w']}W")
        
        # Verify amplitude and baseline
        expected_amplitude = 500.0  # 1000W - 500W = 500W
        expected_baseline = 750.0   # (1000W + 500W) / 2 = 750W
        
        self.assertAlmostEqual(info['amplitude_w'], expected_amplitude, delta=50.0,
                              msg=f"Amplitude should be ~{expected_amplitude}W")
        self.assertAlmostEqual(info['baseline_w'], expected_baseline, delta=50.0,
                              msg=f"Baseline should be ~{expected_baseline}W")
        
        # Test damped target calculation
        # Simulate normal battery target that would oscillate
        normal_battery_target = -800.0  # Would normally discharge 800W
        
        # Get stabilized target with 0.5 damping
        stabilized_target = self.detector.get_stabilized_target(normal_battery_target)
        
        print(f"Normal battery target: {normal_battery_target}W")
        print(f"Stabilized target: {stabilized_target}W")
        
        # With 0.5 damping factor, let's calculate expected result:
        # min_discharge = -(baseline - amplitude/2) = -(750 - 250) = -500W
        # max_discharge = -(baseline + amplitude/2 * stabilization_factor) = -(750 + 250*1.1) = -1025W
        # damped_target = min_discharge + 0.5 * (max_discharge - min_discharge)
        #               = -500 + 0.5 * (-1025 - (-500))
        #               = -500 + 0.5 * (-525)
        #               = -500 + (-262.5) = -762.5W
        
        expected_stabilized = -762.5
        self.assertAlmostEqual(stabilized_target, expected_stabilized, delta=50.0,
                              msg=f"With 0.5 damping, should settle at ~{expected_stabilized}W")
        
        print(f"✅ Expected ~{expected_stabilized}W, got {stabilized_target}W")
    
    def test_baseline_shift_should_respond_immediately(self):
        """
        Test: After oscillation stabilizes, if baseline shifts to 1500W, should respond immediately
        Expected: Should immediately adjust to handle 1500W requirement
        """
        print("\n=== TEST: Baseline shift should respond immediately ===")
        
        # Phase 1: Establish oscillation pattern 500W-1000W
        print("Phase 1: Establishing 500W-1000W oscillation...")
        for i in range(20):
            power = 1000.0 if i % 4 < 2 else 500.0
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            self.detector.add_power_reading(power, timestamp)
        
        # Verify initial oscillation
        self.assertTrue(self.detector.is_oscillating())
        initial_info = self.detector.get_oscillation_info()
        print(f"Initial baseline: {initial_info['baseline_w']}W")
        
        # Phase 2: Sudden baseline shift to 1500W (load change)
        print("Phase 2: Baseline shift to 1500W...")
        shift_start_time = self.base_time + timedelta(seconds=10)
        
        # Create new oscillation pattern: 1300W ↔ 1700W (centered at 1500W)
        for i in range(20):
            power = 1700.0 if i % 4 < 2 else 1300.0  # Still 400W amplitude, but centered at 1500W
            timestamp = shift_start_time + timedelta(seconds=i * 0.5)
            self.detector.add_power_reading(power, timestamp)
        
        # Check if baseline shift was detected
        shift_info = self.detector.get_oscillation_info()
        print(f"New baseline: {shift_info['baseline_w']}W")
        print(f"Baseline shift detected: {shift_info['baseline_shift_detected']}")
        print(f"Baseline shift magnitude: {shift_info['baseline_shift_magnitude_w']}W")
        
        # Verify baseline shift detection
        baseline_shift = abs(shift_info['baseline_w'] - initial_info['baseline_w'])
        print(f"Actual baseline shift: {baseline_shift}W")
        
        # Should detect significant baseline shift (750W → 1500W = 750W shift)
        self.assertGreater(baseline_shift, 500.0, 
                          "Should detect significant baseline shift")
        
        # Test that new stabilized target reflects the new baseline
        normal_battery_target = -1600.0  # Would normally discharge 1600W for new load
        new_stabilized_target = self.detector.get_stabilized_target(normal_battery_target)
        
        print(f"New normal battery target: {normal_battery_target}W")
        print(f"New stabilized target: {new_stabilized_target}W")
        
        # The new stabilized target should be much higher (more discharge) to handle 1500W baseline
        # Expected calculation with new baseline ~1500W and amplitude ~400W:
        # min_discharge = -(1500 - 200) = -1300W
        # max_discharge = -(1500 + 200*1.1) = -1720W
        # damped_target = -1300 + 0.5 * (-1720 - (-1300)) = -1300 + 0.5 * (-420) = -1510W
        
        expected_new_stabilized = -1510.0
        self.assertAlmostEqual(new_stabilized_target, expected_new_stabilized, delta=100.0,
                              msg=f"New stabilized target should be ~{expected_new_stabilized}W")
        
        print(f"✅ Expected ~{expected_new_stabilized}W, got {new_stabilized_target}W")
        
        # Verify the target increased significantly (more discharge for higher load)
        target_increase = abs(new_stabilized_target) - abs(stabilized_target if 'stabilized_target' in locals() else -762.5)
        print(f"Target increase: {target_increase}W")
        self.assertGreater(target_increase, 500.0, 
                          "Target should increase significantly for baseline shift")
    
    def test_damping_factor_math_verification(self):
        """
        Test: Verify the mathematical calculation of damping factor
        """
        print("\n=== TEST: Damping factor math verification ===")
        
        # Set up known oscillation: 600W ↔ 800W (amplitude=200W, baseline=700W)
        for i in range(16):
            power = 800.0 if i % 4 < 2 else 600.0
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            self.detector.add_power_reading(power, timestamp)
        
        self.assertTrue(self.detector.is_oscillating())
        info = self.detector.get_oscillation_info()
        
        amplitude = info['amplitude_w']
        baseline = info['baseline_w']
        stabilization_factor = info['stabilization_factor']
        damping_factor = info['damping_factor']
        
        print(f"Amplitude: {amplitude}W")
        print(f"Baseline: {baseline}W")
        print(f"Stabilization factor: {stabilization_factor}")
        print(f"Damping factor: {damping_factor}")
        
        # Manual calculation
        min_discharge = -(baseline - amplitude / 2)
        max_discharge = -(baseline + (amplitude / 2) * stabilization_factor)
        expected_damped = min_discharge + damping_factor * (max_discharge - min_discharge)
        
        print(f"Manual calculation:")
        print(f"  min_discharge = -({baseline} - {amplitude}/2) = {min_discharge}W")
        print(f"  max_discharge = -({baseline} + {amplitude}/2 * {stabilization_factor}) = {max_discharge}W")
        print(f"  damped_target = {min_discharge} + {damping_factor} * ({max_discharge} - {min_discharge}) = {expected_damped}W")
        
        # Test with dummy baseline target
        actual_damped = self.detector.get_stabilized_target(-1000.0)
        print(f"Actual damped target: {actual_damped}W")
        
        self.assertAlmostEqual(actual_damped, expected_damped, delta=10.0,
                              msg="Damped target should match manual calculation")
        
        print(f"✅ Math verification passed: {expected_damped}W ≈ {actual_damped}W")


if __name__ == '__main__':
    unittest.main(verbosity=2)