"""
Test to verify the critical damping sign fix
"""
import unittest
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path to import oscillation_detector
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from oscillation_detector import OscillationDetector


class TestDampingSignFix(unittest.TestCase):
    """Test the critical damping sign fix"""
    
    def setUp(self):
        """Set up test with standard configuration"""
        self.config = {
            'enabled': True,
            'min_amplitude_w': 100.0,
            'min_cycles': 2,
            'max_cycle_duration_s': 10.0,
            'history_duration_s': 30.0,
            'stabilization_factor': 1.1,
            'detection_sensitivity': 0.8,
            'baseline_smoothing_factor': 0.3,
            'baseline_shift_threshold_w': 150.0,
            'damping_factor': 0.5,
            'damping_strategy': 'proportional'
        }
        self.detector = OscillationDetector(self.config)
        self.base_time = datetime.now()
    
    def test_negative_baseline_should_give_negative_battery_target(self):
        """
        CRITICAL TEST: When grid oscillates around negative values (export),
        battery target should still be negative (discharge) to counteract the oscillation
        
        This reproduces the bug from your logs:
        - Grid baseline: -19W (slight export)
        - Should result in negative battery target (discharge)
        - NOT positive battery target (charge)
        """
        print("\n=== TEST: Negative baseline fix ===")
        
        # Create oscillation around -19W (slight export, like in your logs)
        # Grid oscillating between -139W (export) and +101W (import)
        # Baseline = -19W, Amplitude = 240W
        
        oscillation_data = []
        for i in range(20):
            if i % 4 < 2:
                power = 101.0  # Import phase
            else:
                power = -139.0  # Export phase
            
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            oscillation_data.append((power, timestamp))
        
        # Feed data to detector
        for power, timestamp in oscillation_data:
            self.detector.add_power_reading(power, timestamp)
        
        # Verify oscillation is detected
        self.assertTrue(self.detector.is_oscillating(), "Should detect oscillation")
        
        info = self.detector.get_oscillation_info()
        baseline = info['baseline_w']
        amplitude = info['amplitude_w']
        
        print(f"Detected baseline: {baseline}W")
        print(f"Detected amplitude: {amplitude}W")
        
        # Should detect baseline around -19W and amplitude around 240W
        self.assertLess(baseline, 50.0, "Baseline should be close to -19W")
        self.assertGreater(amplitude, 200.0, "Amplitude should be around 240W")
        
        # Test damping calculation - this is the critical fix
        normal_target = -1500.0  # Some normal discharge target
        stabilized_target = self.detector.get_stabilized_target(normal_target)
        
        print(f"Normal target: {normal_target}W")
        print(f"Stabilized target: {stabilized_target}W")
        
        # CRITICAL: Stabilized target should be NEGATIVE (discharge)
        # The old bug would make this positive (charge)
        self.assertLess(stabilized_target, 0.0, 
                       "CRITICAL: Stabilized target must be negative (discharge), not positive (charge)")
        
        # Should be reasonable discharge value (not extreme)
        self.assertGreater(stabilized_target, -3000.0, 
                          "Stabilized target should be reasonable (not extreme discharge)")
        
        print(f"✅ FIXED: Negative baseline gives negative battery target: {stabilized_target}W")
    
    def test_positive_baseline_should_give_negative_battery_target(self):
        """
        Test: When grid oscillates around positive values (import),
        battery should discharge (negative target) to counteract
        """
        print("\n=== TEST: Positive baseline behavior ===")
        
        # Create oscillation around +750W (import)
        # Grid oscillating between 500W and 1000W
        for i in range(20):
            power = 1000.0 if i % 4 < 2 else 500.0
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            self.detector.add_power_reading(power, timestamp)
        
        self.assertTrue(self.detector.is_oscillating())
        
        info = self.detector.get_oscillation_info()
        baseline = info['baseline_w']
        
        print(f"Baseline: {baseline}W (should be ~750W)")
        
        # Test damping
        stabilized_target = self.detector.get_stabilized_target(-1000.0)
        
        print(f"Stabilized target: {stabilized_target}W")
        
        # Should be negative (discharge) to counteract positive grid baseline
        self.assertLess(stabilized_target, 0.0, 
                       "Should discharge to counteract grid import")
        
        print(f"✅ Positive baseline gives negative battery target: {stabilized_target}W")
    
    def test_damping_factor_math_with_negative_baseline(self):
        """
        Test the mathematical correctness of damping with negative baseline
        """
        print("\n=== TEST: Damping math with negative baseline ===")
        
        # Set up known oscillation with negative baseline
        # Grid: -100W ↔ +100W, baseline = 0W, amplitude = 200W
        for i in range(16):
            power = 100.0 if i % 4 < 2 else -100.0
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            self.detector.add_power_reading(power, timestamp)
        
        self.assertTrue(self.detector.is_oscillating())
        
        info = self.detector.get_oscillation_info()
        baseline = info['baseline_w']
        amplitude = info['amplitude_w']
        damping_factor = info['damping_factor']
        stabilization_factor = info['stabilization_factor']
        
        print(f"Baseline: {baseline}W")
        print(f"Amplitude: {amplitude}W")
        print(f"Damping factor: {damping_factor}")
        
        # Manual calculation with corrected logic
        min_battery_target = -baseline  # Just counteract baseline
        max_battery_target = -(baseline + (amplitude / 2) * stabilization_factor)
        expected_damped = min_battery_target + damping_factor * (max_battery_target - min_battery_target)
        
        print(f"Manual calculation:")
        print(f"  min_battery_target = -{baseline} = {min_battery_target}W")
        print(f"  max_battery_target = -({baseline} + {amplitude}/2 * {stabilization_factor}) = {max_battery_target}W")
        print(f"  expected_damped = {min_battery_target} + {damping_factor} * ({max_battery_target} - {min_battery_target}) = {expected_damped}W")
        
        # Test actual calculation
        actual_damped = self.detector.get_stabilized_target(-1000.0)
        
        print(f"Actual damped: {actual_damped}W")
        
        self.assertAlmostEqual(actual_damped, expected_damped, delta=10.0,
                              msg="Damped calculation should match manual calculation")
        
        print(f"✅ Math verification: {expected_damped}W ≈ {actual_damped}W")


if __name__ == '__main__':
    unittest.main(verbosity=2)