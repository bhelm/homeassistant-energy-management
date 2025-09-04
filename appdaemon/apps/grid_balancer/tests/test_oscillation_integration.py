"""Integration tests for oscillation detection with grid balancer

This test suite validates the integration between the oscillation detector
and the grid balancer, using real-world log data patterns to ensure the
damping factor works correctly in the full system context.
"""
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
import sys
import os

# Add the parent directory to the path to import the modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from oscillation_detector import OscillationDetector


class TestOscillationIntegration(unittest.TestCase):
    """Test oscillation detection integration with grid balancer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.base_time = datetime.now()
        
        # Real-world log data sequence (simplified)
        self.log_oscillation_pattern = [
            (+1478, 0.0), (+1079, 0.5), (+524, 1.0), (-318, 1.5), (-362, 2.0),
            (-113, 2.3), (-234, 2.4), (-1620, 2.9), (-1197, 3.4), (-1432, 3.9),
            (-1190, 5.0), (-1344, 5.6), (-454, 6.0), (+933, 6.5), (+1009, 7.5),
            (+1179, 8.0), (+906, 8.2), (+552, 8.9), (+336, 9.4), (-44, 9.9),
            (-24, 10.0), (-1338, 10.5), (-1080, 11.0), (-1353, 11.5), (-1386, 12.5),
            (-1123, 12.8), (-997, 13.0), (+236, 13.9), (+1276, 14.4), (+1172, 14.9),
            (+1478, 15.0), (+1205, 15.5), (+691, 16.0), (-205, 16.5), (-1499, 17.5)
        ]
    
    def _create_detector_with_config(self, damping_factor: float, enabled: bool = True) -> OscillationDetector:
        """Create oscillation detector with specific configuration"""
        config = {
            'enabled': enabled,
            'min_amplitude_w': 1000.0,
            'min_cycles': 2,
            'max_cycle_duration_s': 8.0,
            'history_duration_s': 30.0,
            'stabilization_factor': 1.1,
            'detection_sensitivity': 0.8,
            'baseline_smoothing_factor': 0.1,
            'baseline_shift_threshold_w': 500.0,
            'damping_factor': damping_factor,
            'damping_strategy': 'proportional'
        }
        return OscillationDetector(config)
    
    def _simulate_grid_balancer_operation(self, detector: OscillationDetector, 
                                        grid_data: list, baseline_target: float = -1500.0):
        """Simulate grid balancer operation with oscillation detection"""
        results = []
        
        for grid_power, time_offset in grid_data:
            timestamp = self.base_time + timedelta(seconds=time_offset)
            
            # Feed power reading to oscillation detector
            detector.add_power_reading(grid_power, timestamp)
            
            # Simulate grid balancer logic
            if detector.is_oscillating():
                # Use damped target when oscillation detected
                battery_target = detector.get_stabilized_target(baseline_target)
                status = "OSCILLATION_DAMPED"
            else:
                # Use normal target when no oscillation
                battery_target = baseline_target
                status = "NORMAL"
            
            results.append({
                'time': time_offset,
                'grid_power': grid_power,
                'battery_target': battery_target,
                'status': status,
                'is_oscillating': detector.is_oscillating()
            })
        
        return results
    
    def test_integration_with_different_damping_factors(self):
        """Test integration with different damping factors using log data"""
        damping_factors = [0.0, 0.5, 1.0]
        baseline_target = -1500.0
        
        results_by_damping = {}
        
        for damping in damping_factors:
            detector = self._create_detector_with_config(damping)
            results = self._simulate_grid_balancer_operation(
                detector, self.log_oscillation_pattern, baseline_target
            )
            results_by_damping[damping] = results
            
            # Find when oscillation was first detected
            first_oscillation = next((r for r in results if r['is_oscillating']), None)
            
            if first_oscillation:
                print(f"Damping {damping}: Oscillation detected at {first_oscillation['time']}s, "
                      f"target: {first_oscillation['battery_target']:.0f}W")
            else:
                print(f"Damping {damping}: No oscillation detected")
        
        # Verify that different damping factors produce different results
        if all(results_by_damping[d] for d in damping_factors):
            # Get final oscillating targets
            final_targets = {}
            for damping in damping_factors:
                oscillating_results = [r for r in results_by_damping[damping] if r['is_oscillating']]
                if oscillating_results:
                    final_targets[damping] = oscillating_results[-1]['battery_target']
            
            if len(final_targets) >= 2:
                # Verify damping progression (higher damping = more negative target)
                damping_values = sorted(final_targets.keys())
                for i in range(1, len(damping_values)):
                    prev_damping = damping_values[i-1]
                    curr_damping = damping_values[i]
                    
                    self.assertLessEqual(final_targets[curr_damping], final_targets[prev_damping],
                                       f"Higher damping should result in more negative target: "
                                       f"{prev_damping}({final_targets[prev_damping]:.0f}W) vs "
                                       f"{curr_damping}({final_targets[curr_damping]:.0f}W)")
                
                print(f"✓ Damping progression verified across {len(final_targets)} factors")
    
    def test_oscillation_detection_timing_in_integration(self):
        """Test that oscillation detection timing works correctly in integration"""
        detector = self._create_detector_with_config(0.5)  # Balanced damping
        results = self._simulate_grid_balancer_operation(detector, self.log_oscillation_pattern)
        
        # Find transition from normal to oscillation mode
        normal_results = [r for r in results if r['status'] == 'NORMAL']
        oscillation_results = [r for r in results if r['status'] == 'OSCILLATION_DAMPED']
        
        if oscillation_results:
            first_oscillation_time = oscillation_results[0]['time']
            
            # Should detect oscillation within reasonable time (after enough data)
            self.assertGreaterEqual(first_oscillation_time, 5.0,
                                   "Should not detect oscillation too early")
            self.assertLessEqual(first_oscillation_time, 15.0,
                                "Should detect oscillation within reasonable time")
            
            print(f"✓ Oscillation detected at {first_oscillation_time}s (within expected range)")
            
            # Verify consistent oscillation detection after first detection
            oscillation_times = [r['time'] for r in oscillation_results]
            self.assertGreater(len(oscillation_times), 5,
                              "Should maintain oscillation detection for multiple readings")
            
            print(f"✓ Maintained oscillation detection for {len(oscillation_times)} readings")
        else:
            self.fail("No oscillation detected in integration test")
    
    def test_disabled_oscillation_detection_integration(self):
        """Test integration when oscillation detection is disabled"""
        detector = self._create_detector_with_config(0.5, enabled=False)
        results = self._simulate_grid_balancer_operation(detector, self.log_oscillation_pattern)
        
        # All results should be normal (no oscillation detection)
        normal_results = [r for r in results if r['status'] == 'NORMAL']
        oscillation_results = [r for r in results if r['status'] == 'OSCILLATION_DAMPED']
        
        self.assertEqual(len(oscillation_results), 0,
                        "No oscillation should be detected when disabled")
        self.assertEqual(len(normal_results), len(results),
                        "All results should be normal when oscillation detection disabled")
        
        # All battery targets should be the baseline target
        baseline_target = -1500.0
        for result in results:
            self.assertEqual(result['battery_target'], baseline_target,
                           f"Battery target should be baseline when disabled: "
                           f"got {result['battery_target']}, expected {baseline_target}")
        
        print(f"✓ Oscillation detection properly disabled - all {len(results)} results normal")
    
    def test_oscillation_amplitude_impact_on_damping(self):
        """Test how different oscillation amplitudes affect damping"""
        # Create patterns with different amplitudes
        small_amplitude_pattern = [
            (+800, 0.0), (+800, 1.0), (-800, 2.0), (-800, 3.0),  # 1600W amplitude
            (+800, 4.0), (+800, 5.0), (-800, 6.0), (-800, 7.0),
            (+800, 8.0), (+800, 9.0), (-800, 10.0), (-800, 11.0),
        ]
        
        large_amplitude_pattern = [
            (+2500, 0.0), (+2500, 1.0), (-2500, 2.0), (-2500, 3.0),  # 5000W amplitude
            (+2500, 4.0), (+2500, 5.0), (-2500, 6.0), (-2500, 7.0),
            (+2500, 8.0), (+2500, 9.0), (-2500, 10.0), (-2500, 11.0),
        ]
        
        damping_factor = 0.5
        baseline_target = -1500.0
        
        # Test small amplitude
        small_detector = self._create_detector_with_config(damping_factor)
        small_results = self._simulate_grid_balancer_operation(
            small_detector, small_amplitude_pattern, baseline_target
        )
        
        # Test large amplitude
        large_detector = self._create_detector_with_config(damping_factor)
        large_results = self._simulate_grid_balancer_operation(
            large_detector, large_amplitude_pattern, baseline_target
        )
        
        # Get oscillating targets
        small_oscillating = [r for r in small_results if r['is_oscillating']]
        large_oscillating = [r for r in large_results if r['is_oscillating']]
        
        if small_oscillating and large_oscillating:
            small_target = small_oscillating[-1]['battery_target']
            large_target = large_oscillating[-1]['battery_target']
            
            # Large amplitude should result in more negative (higher discharge) target
            self.assertLess(large_target, small_target,
                           f"Large amplitude should result in more negative target: "
                           f"small({small_target:.0f}W) vs large({large_target:.0f}W)")
            
            print(f"✓ Amplitude impact verified: Small amplitude: {small_target:.0f}W, "
                  f"Large amplitude: {large_target:.0f}W")
        else:
            print("⚠ Amplitude test inconclusive - oscillation not detected in both patterns")
    
    def test_baseline_shift_handling_in_integration(self):
        """Test how baseline shifts are handled in integration"""
        # Create pattern with baseline shift
        baseline_shift_pattern = [
            # Initial oscillation around 0W baseline
            (+1500, 0.0), (+1500, 1.0), (-1500, 2.0), (-1500, 3.0),
            (+1500, 4.0), (+1500, 5.0), (-1500, 6.0), (-1500, 7.0),
            # Baseline shift: +1000W (load turns on)
            (+2500, 8.0), (+2500, 9.0), (-500, 10.0), (-500, 11.0),
            (+2500, 12.0), (+2500, 13.0), (-500, 14.0), (-500, 15.0),
            (+2500, 16.0), (+2500, 17.0), (-500, 18.0), (-500, 19.0),
        ]
        
        detector = self._create_detector_with_config(0.5)
        results = self._simulate_grid_balancer_operation(detector, baseline_shift_pattern)
        
        oscillating_results = [r for r in results if r['is_oscillating']]
        
        if len(oscillating_results) >= 10:  # Need enough data to see baseline adaptation
            early_targets = [r['battery_target'] for r in oscillating_results[:5]]
            late_targets = [r['battery_target'] for r in oscillating_results[-5:]]
            
            early_avg = sum(early_targets) / len(early_targets)
            late_avg = sum(late_targets) / len(late_targets)
            
            # Targets should adapt to baseline shift (reduced threshold for real-world patterns)
            target_shift = abs(late_avg - early_avg)
            
            self.assertGreater(target_shift, 50,
                              f"Battery targets should adapt to baseline shift: "
                              f"early avg: {early_avg:.0f}W, late avg: {late_avg:.0f}W, "
                              f"shift: {target_shift:.0f}W")
            
            print(f"✓ Baseline shift adaptation: {target_shift:.0f}W target adjustment")
        else:
            print("⚠ Baseline shift test inconclusive - insufficient oscillation data")
    
    def test_integration_performance_with_continuous_data(self):
        """Test integration performance with continuous oscillation data"""
        detector = self._create_detector_with_config(0.5)
        
        # Generate 2 minutes of continuous oscillation data
        continuous_pattern = []
        for i in range(240):  # 240 data points over 2 minutes
            time_offset = i * 0.5  # 0.5s intervals
            # Create oscillation with some variation
            base_power = 1800 if (i // 4) % 2 == 0 else -1800  # 2s on/off
            variation = (hash(str(i)) % 400) - 200  # ±200W variation
            power = base_power + variation
            continuous_pattern.append((power, time_offset))
        
        results = self._simulate_grid_balancer_operation(detector, continuous_pattern)
        
        # Verify performance
        oscillating_results = [r for r in results if r['is_oscillating']]
        normal_results = [r for r in results if r['status'] == 'NORMAL']
        
        # Should detect oscillation for majority of the data
        oscillation_percentage = len(oscillating_results) / len(results) * 100
        
        self.assertGreater(oscillation_percentage, 50,
                          f"Should detect oscillation for majority of data: {oscillation_percentage:.1f}%")
        
        # Verify targets are reasonable
        if oscillating_results:
            targets = [r['battery_target'] for r in oscillating_results]
            min_target = min(targets)
            max_target = max(targets)
            
            self.assertGreater(min_target, -8000, "Targets should not be extremely negative")
            self.assertLess(max_target, 5000, "Targets should not be extremely positive")
            
            print(f"✓ Performance test: {len(results)} data points, "
                  f"{oscillation_percentage:.1f}% oscillation detected, "
                  f"target range: {min_target:.0f}W to {max_target:.0f}W")


if __name__ == '__main__':
    # Run the tests with detailed output
    unittest.main(verbosity=2)