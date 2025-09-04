"""
Test to verify improved baseline response with increased smoothing factor
"""
import unittest
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path to import oscillation_detector
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from oscillation_detector import OscillationDetector


class TestImprovedBaselineResponse(unittest.TestCase):
    """Test improved baseline response with faster smoothing"""
    
    def setUp(self):
        """Set up test with improved baseline smoothing (0.3 instead of 0.1)"""
        self.config = {
            'enabled': True,
            'min_amplitude_w': 100.0,
            'min_cycles': 2,
            'max_cycle_duration_s': 10.0,
            'history_duration_s': 30.0,
            'stabilization_factor': 1.1,
            'detection_sensitivity': 0.8,
            'baseline_smoothing_factor': 0.6,  # IMPROVED: 0.6 instead of 0.1 for much faster response
            'baseline_shift_threshold_w': 150.0,
            'damping_factor': 0.5,
            'damping_strategy': 'proportional'
        }
        self.detector = OscillationDetector(self.config)
        self.base_time = datetime.now()
    
    def test_faster_baseline_adaptation_to_load_changes(self):
        """
        Test that the improved baseline smoothing responds faster to load changes
        """
        print("\n=== TEST: Faster baseline adaptation ===")
        
        # Phase 1: Establish initial oscillation 600W-800W (baseline 700W)
        print("Phase 1: Initial oscillation 600W-800W...")
        for i in range(16):
            power = 800.0 if i % 4 < 2 else 600.0
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            self.detector.add_power_reading(power, timestamp)
        
        initial_info = self.detector.get_oscillation_info()
        initial_baseline = initial_info['baseline_w']
        print(f"Initial baseline: {initial_baseline}W")
        
        # Phase 2: Sudden load change - shift to 1200W-1400W (baseline 1300W)
        print("Phase 2: Load change to 1200W-1400W...")
        shift_start_time = self.base_time + timedelta(seconds=8)
        
        for i in range(16):
            power = 1400.0 if i % 4 < 2 else 1200.0  # 600W higher baseline
            timestamp = shift_start_time + timedelta(seconds=i * 0.5)
            self.detector.add_power_reading(power, timestamp)
        
        final_info = self.detector.get_oscillation_info()
        final_baseline = final_info['baseline_w']
        baseline_shift = final_baseline - initial_baseline
        
        print(f"Final baseline: {final_baseline}W")
        print(f"Baseline shift: {baseline_shift}W")
        print(f"Shift detected: {final_info['baseline_shift_detected']}")
        
        # With 0.3 smoothing factor, we should see much better adaptation
        # Expected: Should detect significant portion of the 600W shift
        self.assertGreater(baseline_shift, 300.0, 
                          "Should detect at least 300W of the 600W baseline shift")
        
        # Should detect the shift
        self.assertTrue(final_info['baseline_shift_detected'], 
                       "Should detect baseline shift")
        
        print(f"✅ Improved baseline adaptation: {baseline_shift}W shift detected")
    
    def test_comparison_with_old_smoothing_factor(self):
        """
        Compare baseline adaptation between old (0.1) and new (0.3) smoothing factors
        """
        print("\n=== TEST: Comparison old vs new smoothing ===")
        
        # Test with old smoothing factor (0.1)
        old_config = self.config.copy()
        old_config['baseline_smoothing_factor'] = 0.1
        old_detector = OscillationDetector(old_config)
        
        # Test with new smoothing factor (0.3)
        new_detector = self.detector  # Already configured with 0.3
        
        # Same test data for both
        test_data = []
        
        # Initial oscillation 500W-1000W
        for i in range(12):
            power = 1000.0 if i % 4 < 2 else 500.0
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            test_data.append((power, timestamp))
        
        # Baseline shift to 1300W-1800W
        shift_time = self.base_time + timedelta(seconds=6)
        for i in range(12):
            power = 1800.0 if i % 4 < 2 else 1300.0  # 800W higher baseline
            timestamp = shift_time + timedelta(seconds=i * 0.5)
            test_data.append((power, timestamp))
        
        # Feed same data to both detectors
        for power, timestamp in test_data:
            old_detector.add_power_reading(power, timestamp)
            new_detector.add_power_reading(power, timestamp)
        
        old_info = old_detector.get_oscillation_info()
        new_info = new_detector.get_oscillation_info()
        
        old_baseline = old_info['baseline_w']
        new_baseline = new_info['baseline_w']
        
        print(f"Old smoothing (0.1) final baseline: {old_baseline}W")
        print(f"New smoothing (0.3) final baseline: {new_baseline}W")
        print(f"Expected final baseline: ~1550W")
        
        # New smoothing should be closer to the actual final baseline (1550W)
        expected_final = 1550.0
        old_error = abs(old_baseline - expected_final)
        new_error = abs(new_baseline - expected_final)
        
        print(f"Old smoothing error: {old_error}W")
        print(f"New smoothing error: {new_error}W")
        
        self.assertLess(new_error, old_error, 
                       "New smoothing should be more accurate")
        
        print(f"✅ Improved accuracy: {old_error}W → {new_error}W error")
    
    def test_oscillation_damping_still_works_with_faster_baseline(self):
        """
        Verify that oscillation damping still works correctly with faster baseline adaptation
        """
        print("\n=== TEST: Damping still works with faster baseline ===")
        
        # Create stable oscillation pattern
        for i in range(20):
            power = 900.0 if i % 4 < 2 else 700.0  # 800W baseline, 200W amplitude
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            self.detector.add_power_reading(power, timestamp)
        
        self.assertTrue(self.detector.is_oscillating(), "Should detect oscillation")
        
        info = self.detector.get_oscillation_info()
        print(f"Oscillation amplitude: {info['amplitude_w']}W")
        print(f"Oscillation baseline: {info['baseline_w']}W")
        
        # Test damping calculation
        normal_target = -850.0
        damped_target = self.detector.get_stabilized_target(normal_target)
        
        print(f"Normal target: {normal_target}W")
        print(f"Damped target: {damped_target}W")
        
        # Should still provide reasonable damping
        self.assertNotEqual(damped_target, normal_target, 
                           "Should apply damping")
        
        # Damped target should be reasonable for 800W baseline
        expected_range_min = -900.0
        expected_range_max = -700.0
        self.assertGreaterEqual(damped_target, expected_range_min, 
                               f"Damped target should be >= {expected_range_min}W")
        self.assertLessEqual(damped_target, expected_range_max, 
                            f"Damped target should be <= {expected_range_max}W")
        
        print(f"✅ Damping works correctly: {damped_target}W target")


if __name__ == '__main__':
    unittest.main(verbosity=2)