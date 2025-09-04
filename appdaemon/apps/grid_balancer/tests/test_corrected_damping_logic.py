"""
Test to verify the corrected damping logic that uses baseline_target properly
"""
import unittest
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path to import oscillation_detector
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from oscillation_detector import OscillationDetector


class TestCorrectedDampingLogic(unittest.TestCase):
    """Test the corrected damping logic that uses baseline_target as starting point"""
    
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
    
    def test_damping_as_adjustment_not_replacement(self):
        """
        CRITICAL TEST: Damping should adjust baseline_target, not replace it
        
        This reproduces the scenario from your logs:
        - Priority Target: -1521W (what system needs)
        - Should result in target close to -1521W with small adjustment
        - NOT a completely different target like -286W
        """
        print("\n=== TEST: Damping as adjustment ===")
        
        # Create oscillation similar to your logs
        # Baseline around +221W, Amplitude around 237W
        for i in range(20):
            if i % 4 < 2:
                power = 340.0  # High phase
            else:
                power = 102.0  # Low phase
            
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            self.detector.add_power_reading(power, timestamp)
        
        # Verify oscillation is detected
        self.assertTrue(self.detector.is_oscillating(), "Should detect oscillation")
        
        info = self.detector.get_oscillation_info()
        baseline = info['baseline_w']
        amplitude = info['amplitude_w']
        
        print(f"Detected baseline: {baseline}W")
        print(f"Detected amplitude: {amplitude}W")
        
        # Test with realistic baseline_target (what system actually needs)
        baseline_target = -1521.0  # From your logs
        stabilized_target = self.detector.get_stabilized_target(baseline_target)
        
        print(f"Baseline target: {baseline_target}W")
        print(f"Stabilized target: {stabilized_target}W")
        print(f"Adjustment: {stabilized_target - baseline_target}W")
        
        # CRITICAL: Stabilized target should be CLOSE to baseline_target
        # The adjustment should be small compared to the baseline_target
        adjustment = abs(stabilized_target - baseline_target)
        baseline_magnitude = abs(baseline_target)
        adjustment_percentage = (adjustment / baseline_magnitude) * 100
        
        print(f"Adjustment percentage: {adjustment_percentage:.1f}%")
        
        # Adjustment should be reasonable (not more than 50% of baseline target)
        self.assertLess(adjustment_percentage, 50.0, 
                       f"Adjustment should be <50% of baseline target, got {adjustment_percentage:.1f}%")
        
        # Should still be negative (discharge)
        self.assertLess(stabilized_target, 0.0, "Should remain negative (discharge)")
        
        # Should be reasonable discharge value
        self.assertGreater(stabilized_target, -3000.0, "Should not be extreme discharge")
        
        print(f"✅ CORRECTED: Baseline target {baseline_target}W → Stabilized {stabilized_target}W (adjustment: {adjustment:.0f}W)")
    
    def test_damping_factor_effect_on_adjustment(self):
        """
        Test that damping factor affects the size of adjustment, not the base target
        """
        print("\n=== TEST: Damping factor effect ===")
        
        # Set up oscillation
        for i in range(16):
            power = 800.0 if i % 4 < 2 else 600.0  # 700W baseline, 200W amplitude
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            self.detector.add_power_reading(power, timestamp)
        
        self.assertTrue(self.detector.is_oscillating())
        
        baseline_target = -1000.0
        
        # Test different damping factors
        damping_factors = [0.0, 0.5, 1.0]
        results = {}
        
        for damping in damping_factors:
            self.detector.damping_factor = damping
            stabilized = self.detector.get_stabilized_target(baseline_target)
            adjustment = stabilized - baseline_target
            results[damping] = {'stabilized': stabilized, 'adjustment': adjustment}
            print(f"Damping {damping}: {baseline_target}W → {stabilized}W (adj: {adjustment:.0f}W)")
        
        # Verify damping factor affects adjustment size
        adj_0 = results[0.0]['adjustment']
        adj_05 = results[0.5]['adjustment']
        adj_1 = results[1.0]['adjustment']
        
        # With higher damping factor, adjustment should be more negative (more aggressive)
        self.assertGreaterEqual(adj_0, adj_05, "0.0 damping should have smaller adjustment than 0.5")
        self.assertGreaterEqual(adj_05, adj_1, "0.5 damping should have smaller adjustment than 1.0")
        
        # All should be close to baseline_target (within reasonable range)
        for damping, result in results.items():
            adjustment_pct = abs(result['adjustment'] / baseline_target) * 100
            self.assertLess(adjustment_pct, 50.0, 
                           f"Damping {damping} adjustment should be <50% of baseline")
        
        print(f"✅ Damping factor properly affects adjustment size")
    
    def test_zero_damping_returns_baseline_target(self):
        """
        Test that 0.0 damping factor returns baseline_target unchanged
        """
        print("\n=== TEST: Zero damping ===")
        
        # Set up oscillation
        for i in range(16):
            power = 900.0 if i % 4 < 2 else 700.0
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            self.detector.add_power_reading(power, timestamp)
        
        self.assertTrue(self.detector.is_oscillating())
        
        # Set damping to 0.0 (conservative)
        self.detector.damping_factor = 0.0
        
        baseline_target = -1234.0
        stabilized_target = self.detector.get_stabilized_target(baseline_target)
        
        print(f"Baseline target: {baseline_target}W")
        print(f"Stabilized target: {stabilized_target}W")
        
        # With 0.0 damping, should return baseline_target unchanged
        self.assertAlmostEqual(stabilized_target, baseline_target, delta=1.0,
                              msg="0.0 damping should return baseline_target unchanged")
        
        print(f"✅ Zero damping returns baseline target unchanged")


if __name__ == '__main__':
    unittest.main(verbosity=2)