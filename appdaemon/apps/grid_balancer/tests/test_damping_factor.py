"""Test damping factor functionality in oscillation detection

This test suite validates the new damping factor feature that allows configurable
oscillation handling strategies from minimum discharge (0.0) to maximum discharge (1.0).
"""
import unittest
from datetime import datetime, timedelta
import sys
import os

# Add the parent directory to the path to import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from oscillation_detector import OscillationDetector


class TestDampingFactor(unittest.TestCase):
    """Test damping factor functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.base_config = {
            'enabled': True,
            'min_amplitude_w': 1000.0,
            'min_cycles': 2,
            'max_cycle_duration_s': 8.0,
            'history_duration_s': 30.0,
            'stabilization_factor': 1.1,
            'detection_sensitivity': 0.8,
            'baseline_smoothing_factor': 0.1,
            'baseline_shift_threshold_w': 500.0,
            'damping_strategy': 'proportional'
        }
        self.base_time = datetime.now()
        
        # Standard oscillation pattern for testing
        self.test_oscillation = [
            (+2000, 0.0), (+2000, 1.0), (-2000, 2.0), (-2000, 3.0),  # Cycle 1
            (+2000, 4.0), (+2000, 5.0), (-2000, 6.0), (-2000, 7.0),  # Cycle 2
            (+2000, 8.0), (+2000, 9.0), (-2000, 10.0), (-2000, 11.0),  # Cycle 3
        ]
    
    def _create_detector_with_damping(self, damping_factor: float) -> OscillationDetector:
        """Create detector with specific damping factor"""
        config = self.base_config.copy()
        config['damping_factor'] = damping_factor
        return OscillationDetector(config)
    
    def _feed_oscillation_data(self, detector: OscillationDetector):
        """Feed standard oscillation data to detector"""
        for power, time_offset in self.test_oscillation:
            timestamp = self.base_time + timedelta(seconds=time_offset)
            detector.add_power_reading(power, timestamp)
    
    def test_damping_factor_range_validation(self):
        """Test that damping factor is properly clamped to 0.0-1.0 range"""
        test_cases = [
            (-0.5, 0.0),  # Negative should clamp to 0.0
            (0.0, 0.0),   # Valid minimum
            (0.5, 0.5),   # Valid middle
            (1.0, 1.0),   # Valid maximum
            (1.5, 1.0),   # Above 1.0 should clamp to 1.0
            (2.0, 1.0),   # Way above should clamp to 1.0
        ]
        
        for input_damping, expected_damping in test_cases:
            config = self.base_config.copy()
            config['damping_factor'] = input_damping
            detector = OscillationDetector(config)
            
            self.assertEqual(detector.damping_factor, expected_damping,
                           f"Damping factor {input_damping} should clamp to {expected_damping}")
    
    def test_proportional_damping_extremes(self):
        """Test proportional damping at extreme values (0.0 and 1.0)"""
        # Test minimum damping (0.0)
        detector_min = self._create_detector_with_damping(0.0)
        self._feed_oscillation_data(detector_min)
        
        self.assertTrue(detector_min.is_oscillating())
        
        baseline_target = -1500.0
        min_target = detector_min.get_stabilized_target(baseline_target)
        
        # Test maximum damping (1.0)
        detector_max = self._create_detector_with_damping(1.0)
        self._feed_oscillation_data(detector_max)
        
        self.assertTrue(detector_max.is_oscillating())
        
        max_target = detector_max.get_stabilized_target(baseline_target)
        
        # Max target should be more negative (higher discharge) than min target
        self.assertLess(max_target, min_target,
                       f"Max damping target {max_target}W should be more negative than min {min_target}W")
        
        print(f"✓ Damping extremes: Min (0.0): {min_target:.0f}W, Max (1.0): {max_target:.0f}W")
    
    def test_proportional_damping_interpolation(self):
        """Test that proportional damping properly interpolates between min and max"""
        damping_factors = [0.0, 0.25, 0.5, 0.75, 1.0]
        targets = []
        
        baseline_target = -1500.0
        
        for damping in damping_factors:
            detector = self._create_detector_with_damping(damping)
            self._feed_oscillation_data(detector)
            
            self.assertTrue(detector.is_oscillating())
            
            target = detector.get_stabilized_target(baseline_target)
            targets.append((damping, target))
            
            print(f"Damping {damping}: {target:.0f}W")
        
        # Verify monotonic progression (higher damping = more negative target)
        for i in range(1, len(targets)):
            prev_damping, prev_target = targets[i-1]
            curr_damping, curr_target = targets[i]
            
            self.assertLessEqual(curr_target, prev_target,
                               f"Target should decrease (more negative) as damping increases: "
                               f"{prev_damping}→{curr_damping}: {prev_target:.0f}W→{curr_target:.0f}W")
        
        # Test specific interpolation at 0.5 (should be midpoint)
        min_target = targets[0][1]  # damping = 0.0
        max_target = targets[4][1]  # damping = 1.0
        mid_target = targets[2][1]  # damping = 0.5
        
        expected_mid = (min_target + max_target) / 2
        
        self.assertAlmostEqual(mid_target, expected_mid, delta=50,
                              msg=f"Mid damping (0.5) should be close to average: "
                                  f"got {mid_target:.0f}W, expected {expected_mid:.0f}W")
    
    def test_damping_strategies(self):
        """Test different damping strategies"""
        strategies = ['proportional', 'min', 'max', 'average']
        baseline_target = -1500.0
        
        results = {}
        
        for strategy in strategies:
            config = self.base_config.copy()
            config['damping_strategy'] = strategy
            config['damping_factor'] = 0.7  # Use non-default value for proportional
            
            detector = OscillationDetector(config)
            self._feed_oscillation_data(detector)
            
            self.assertTrue(detector.is_oscillating())
            
            target = detector.get_stabilized_target(baseline_target)
            results[strategy] = target
            
            print(f"Strategy '{strategy}': {target:.0f}W")
        
        # Verify strategy relationships
        self.assertLessEqual(results['max'], results['min'],
                           "Max strategy should be more negative than min strategy")
        
        # Average should be between min and max
        self.assertLessEqual(results['max'], results['average'])
        self.assertLessEqual(results['average'], results['min'])
        
        # Proportional with 0.7 should be closer to max than min
        prop_position = (results['proportional'] - results['min']) / (results['max'] - results['min'])
        self.assertGreater(prop_position, 0.6,
                          f"Proportional with 0.7 damping should be closer to max: position {prop_position:.2f}")
    
    def test_damping_with_baseline_offset(self):
        """Test damping behavior with oscillation that has DC offset"""
        # Create oscillation with +500W offset (baseline = 500W)
        offset_oscillation = [
            (2500, 0.0), (2500, 1.0), (-1500, 2.0), (-1500, 3.0),  # +500W offset
            (2500, 4.0), (2500, 5.0), (-1500, 6.0), (-1500, 7.0),
            (2500, 8.0), (2500, 9.0), (-1500, 10.0), (-1500, 11.0),
        ]
        
        detector_min = self._create_detector_with_damping(0.0)
        detector_max = self._create_detector_with_damping(1.0)
        
        # Feed offset data to both detectors
        for power, time_offset in offset_oscillation:
            timestamp = self.base_time + timedelta(seconds=time_offset)
            detector_min.add_power_reading(power, timestamp)
            detector_max.add_power_reading(power, timestamp)
        
        self.assertTrue(detector_min.is_oscillating())
        self.assertTrue(detector_max.is_oscillating())
        
        baseline_target = -1500.0
        min_target = detector_min.get_stabilized_target(baseline_target)
        max_target = detector_max.get_stabilized_target(baseline_target)
        
        # Both should handle the offset properly
        self.assertLess(max_target, min_target,
                       "Max damping should still be more negative with offset")
        
        # Get oscillation info to verify baseline detection
        min_info = detector_min.get_oscillation_info()
        max_info = detector_max.get_oscillation_info()
        
        # Both should detect similar baseline (around +500W)
        self.assertAlmostEqual(min_info['baseline_w'], max_info['baseline_w'], delta=100,
                              msg="Both detectors should detect similar baseline")
        
        self.assertGreater(min_info['baseline_w'], 300,
                          f"Should detect positive baseline: {min_info['baseline_w']:.0f}W")
        
        print(f"✓ Offset oscillation - Min: {min_target:.0f}W, Max: {max_target:.0f}W, "
              f"Baseline: {min_info['baseline_w']:.0f}W")
    
    def test_damping_info_in_oscillation_info(self):
        """Test that damping parameters are included in oscillation info"""
        detector = self._create_detector_with_damping(0.3)
        self._feed_oscillation_data(detector)
        
        self.assertTrue(detector.is_oscillating())
        
        info = detector.get_oscillation_info()
        
        # Check that damping info is included
        self.assertIn('damping_factor', info)
        self.assertIn('damping_strategy', info)
        
        self.assertEqual(info['damping_factor'], 0.3)
        self.assertEqual(info['damping_strategy'], 'proportional')
        
        print(f"✓ Oscillation info includes damping: factor={info['damping_factor']}, "
              f"strategy='{info['damping_strategy']}'")
    
    def test_damping_with_real_world_pattern(self):
        """Test damping with complex real-world oscillation pattern"""
        # Use a pattern similar to the log data but simplified
        real_world_pattern = [
            (+1400, 0.0), (+1100, 0.5), (+800, 1.0), (-300, 1.5),
            (-600, 2.0), (-1200, 2.5), (-1500, 3.0), (-1200, 3.5),
            (-800, 4.0), (+400, 4.5), (+1000, 5.0), (+1400, 5.5),
            (+1200, 6.0), (+800, 6.5), (-200, 7.0), (-800, 7.5),
            (-1400, 8.0), (-1600, 8.5), (-1200, 9.0), (-400, 9.5),
            (+600, 10.0), (+1200, 10.5), (+1500, 11.0), (+1300, 11.5),
        ]
        
        damping_factors = [0.0, 0.5, 1.0]
        results = {}
        
        for damping in damping_factors:
            detector = self._create_detector_with_damping(damping)
            
            for power, time_offset in real_world_pattern:
                timestamp = self.base_time + timedelta(seconds=time_offset)
                detector.add_power_reading(power, timestamp)
            
            if detector.is_oscillating():
                baseline_target = -1500.0
                target = detector.get_stabilized_target(baseline_target)
                results[damping] = target
                
                info = detector.get_oscillation_info()
                print(f"Real-world damping {damping}: {target:.0f}W "
                      f"(amplitude: {info['amplitude_w']:.0f}W, baseline: {info['baseline_w']:.0f}W)")
            else:
                print(f"Real-world damping {damping}: No oscillation detected")
        
        # If oscillation was detected, verify damping behavior
        if results:
            damping_values = sorted(results.keys())
            for i in range(1, len(damping_values)):
                prev_damping = damping_values[i-1]
                curr_damping = damping_values[i]
                
                self.assertLessEqual(results[curr_damping], results[prev_damping],
                                   f"Higher damping should result in more negative target: "
                                   f"{prev_damping}→{curr_damping}: "
                                   f"{results[prev_damping]:.0f}W→{results[curr_damping]:.0f}W")
    
    def test_damping_factor_configuration_validation(self):
        """Test configuration validation and error handling"""
        # Test invalid strategy
        config = self.base_config.copy()
        config['damping_strategy'] = 'invalid_strategy'
        config['damping_factor'] = 0.5
        
        detector = OscillationDetector(config)
        self._feed_oscillation_data(detector)
        
        # Should fall back to proportional strategy
        baseline_target = -1500.0
        target = detector.get_stabilized_target(baseline_target)
        
        # Should not crash and should return a reasonable value
        self.assertIsInstance(target, (int, float))
        self.assertGreater(target, -10000)  # Sanity check
        self.assertLess(target, 5000)       # Sanity check
        
        print(f"✓ Invalid strategy handled gracefully: {target:.0f}W")
    
    def test_damping_performance_with_continuous_data(self):
        """Test damping performance with continuous oscillation data"""
        detector = self._create_detector_with_damping(0.5)
        
        # Generate 60 seconds of oscillation data (120 data points)
        continuous_data = []
        for i in range(120):
            time_offset = i * 0.5  # 0.5s intervals
            # Create oscillation with some noise
            base_power = 2000 if (i // 4) % 2 == 0 else -2000  # 2s on/off
            noise = (hash(str(i)) % 200) - 100  # ±100W noise
            power = base_power + noise
            continuous_data.append((power, time_offset))
        
        # Feed all data
        for power, time_offset in continuous_data:
            timestamp = self.base_time + timedelta(seconds=time_offset)
            detector.add_power_reading(power, timestamp)
        
        # Should maintain oscillation detection
        self.assertTrue(detector.is_oscillating())
        
        # Should provide stable damped target
        baseline_target = -1500.0
        target = detector.get_stabilized_target(baseline_target)
        
        self.assertIsInstance(target, (int, float))
        self.assertGreater(target, -8000)
        self.assertLess(target, 2000)
        
        info = detector.get_oscillation_info()
        print(f"✓ Continuous data performance: {len(continuous_data)} points, "
              f"target: {target:.0f}W, amplitude: {info['amplitude_w']:.0f}W")


if __name__ == '__main__':
    # Run the tests with detailed output
    unittest.main(verbosity=2)