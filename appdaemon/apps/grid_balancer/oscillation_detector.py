"""oscillation_detector.py - Enhanced oscillation detection with adaptive baseline tracking"""
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional
import statistics


class OscillationDetector:
    """
    SINGLE RESPONSIBILITY: Detect oscillating power patterns with adaptive baseline tracking
    
    Enhanced to handle baseline shifts during oscillations (e.g., additional loads turning on/off
    while oscillating load continues). Maintains oscillation tracking while adapting to new
    power levels.
    
    Algorithm:
    1. Maintain rolling history of power readings with timestamps
    2. Detect peaks and valleys using configurable sensitivity
    3. Calculate dynamic baseline using moving average of oscillation centers
    4. Detect baseline shifts and adapt stabilization accordingly
    5. Provide smooth transitions during baseline changes
    """
    
    def __init__(self, config: Dict):
        """
        Initialize enhanced oscillation detector with configuration
        
        Args:
            config: Configuration dictionary with keys:
                - enabled: bool - Master enable/disable switch
                - min_amplitude_w: float - Minimum power swing to detect (W)
                - min_cycles: int - Minimum complete cycles required
                - max_cycle_duration_s: float - Maximum time per cycle (s)
                - history_duration_s: float - Analysis window duration (s)
                - stabilization_factor: float - Safety margin multiplier
                - detection_sensitivity: float - Peak detection sensitivity (0-1)
                - baseline_smoothing_factor: float - Baseline adaptation rate (0-1)
                - baseline_shift_threshold_w: float - Minimum shift to trigger adaptation
                - damping_factor: float - Oscillation damping strategy (0.0-1.0)
                - damping_strategy: str - Damping strategy type
        """
        self.enabled = config.get('enabled', True)
        self.min_amplitude_w = config.get('min_amplitude_w', 1000.0)
        self.min_cycles = config.get('min_cycles', 2)
        self.max_cycle_duration_s = config.get('max_cycle_duration_s', 10.0)
        self.history_duration_s = config.get('history_duration_s', 30.0)
        self.stabilization_factor = config.get('stabilization_factor', 1.1)
        self.detection_sensitivity = config.get('detection_sensitivity', 0.8)
        
        # Enhanced baseline tracking parameters
        self.baseline_smoothing_factor = config.get('baseline_smoothing_factor', 0.1)
        self.baseline_shift_threshold_w = config.get('baseline_shift_threshold_w', 500.0)
        
        # NEW: Damping factor configuration
        self.damping_factor = max(0.0, min(1.0, config.get('damping_factor', 0.5)))  # Clamp to 0.0-1.0
        self.damping_strategy = config.get('damping_strategy', 'proportional')
        
        # State tracking
        self.power_history: List[Tuple[float, datetime]] = []
        self.is_oscillating_state = False
        self.oscillation_amplitude = 0.0
        self.oscillation_baseline = 0.0
        self.previous_baseline = 0.0
        self.baseline_shift_detected = False
        self.last_analysis_time: Optional[datetime] = None
        
        # Enhanced tracking for baseline adaptation
        self.oscillation_centers: List[float] = []  # Track center points of oscillations
        self.baseline_history: List[Tuple[float, datetime]] = []  # Track baseline evolution
        
    def add_power_reading(self, power_w: float, timestamp: datetime) -> None:
        """
        Add a new power reading for analysis with enhanced baseline tracking
        
        Args:
            power_w: Power reading in watts
            timestamp: When the reading was taken
        """
        if not self.enabled:
            return
            
        # Add new reading
        self.power_history.append((power_w, timestamp))
        
        # Clean old readings outside history window
        cutoff_time = timestamp - timedelta(seconds=self.history_duration_s)
        self.power_history = [(p, t) for p, t in self.power_history if t > cutoff_time]
        self.baseline_history = [(b, t) for b, t in self.baseline_history if t > cutoff_time]
        
        # Analyze for oscillations (throttle analysis to avoid excessive computation)
        if (self.last_analysis_time is None or 
            (timestamp - self.last_analysis_time).total_seconds() >= 1.0):
            self._analyze_oscillations_with_baseline_tracking(timestamp)
            self.last_analysis_time = timestamp
    
    def is_oscillating(self) -> bool:
        """Check if oscillation is currently detected"""
        return self.enabled and self.is_oscillating_state
    
    def get_stabilized_target(self, baseline_target: float) -> float:
        """
        Get recommended stabilized battery target with adaptive baseline and damping
        
        Args:
            baseline_target: Normal battery target calculation
            
        Returns:
            Stabilized battery target (negative = discharge)
        """
        if not self.is_oscillating():
            return baseline_target
            
        # Calculate damped target based on strategy
        return self._calculate_damped_target(baseline_target)
    
    def _calculate_damped_target(self, baseline_target: float) -> float:
        """
        Calculate damped battery target based on oscillation and damping factor
        
        Args:
            baseline_target: Normal battery target calculation
            
        Returns:
            Damped battery target
        """
        if self.damping_strategy == 'proportional':
            return self._calculate_proportional_damping(baseline_target)
        elif self.damping_strategy == 'min':
            return self._calculate_min_discharge_target(baseline_target)
        elif self.damping_strategy == 'max':
            return self._calculate_max_discharge_target(baseline_target)
        elif self.damping_strategy == 'average':
            return self._calculate_average_discharge_target(baseline_target)
        else:
            # Default to proportional
            return self._calculate_proportional_damping(baseline_target)
    
    def _calculate_proportional_damping(self, baseline_target: float) -> float:
        """
        Calculate proportional damping adjustment to baseline target
        
        CORRECTED LOGIC: The baseline_target is what the system needs to discharge.
        Damping should be an ADJUSTMENT to that target, not a replacement.
        
        damping_factor = 0.0: Conservative adjustment (closer to baseline_target)
        damping_factor = 1.0: Aggressive adjustment (more stabilization)
        damping_factor = 0.5: Balanced adjustment
        """
        # Calculate the range of possible adjustments based on oscillation
        # Conservative: minimal adjustment to baseline_target
        conservative_adjustment = 0  # No change to baseline_target
        
        # Aggressive: adjust to handle oscillation amplitude with safety margin
        aggressive_adjustment = -(self.oscillation_amplitude / 2) * self.stabilization_factor
        
        # Apply damping factor to interpolate between conservative and aggressive
        damping_adjustment = conservative_adjustment + self.damping_factor * (aggressive_adjustment - conservative_adjustment)
        
        # Apply adjustment to baseline target
        damped_target = baseline_target + damping_adjustment
        
        return damped_target
    
    def _calculate_min_discharge_target(self, baseline_target: float) -> float:
        """Calculate minimum adjustment (conservative) - return baseline_target unchanged"""
        return baseline_target
    
    def _calculate_max_discharge_target(self, baseline_target: float) -> float:
        """Calculate maximum adjustment (aggressive) - add full oscillation handling"""
        aggressive_adjustment = -(self.oscillation_amplitude / 2) * self.stabilization_factor
        return baseline_target + aggressive_adjustment
    
    def _calculate_average_discharge_target(self, baseline_target: float) -> float:
        """Calculate average between min and max adjustments"""
        min_target = self._calculate_min_discharge_target(baseline_target)
        max_target = self._calculate_max_discharge_target(baseline_target)
        return (min_target + max_target) / 2
    
    def get_oscillation_info(self) -> Dict:
        """
        Get enhanced oscillation analysis information for logging/debugging
        
        Returns:
            Dictionary with oscillation state information including baseline tracking and damping
        """
        return {
            'enabled': self.enabled,
            'is_oscillating': self.is_oscillating_state,
            'amplitude_w': self.oscillation_amplitude,
            'baseline_w': self.oscillation_baseline,
            'previous_baseline_w': self.previous_baseline,
            'baseline_shift_detected': self.baseline_shift_detected,
            'baseline_shift_magnitude_w': self.oscillation_baseline - self.previous_baseline,
            'history_points': len(self.power_history),
            'oscillation_centers_count': len(self.oscillation_centers),
            'stabilization_factor': self.stabilization_factor,
            'min_amplitude_w': self.min_amplitude_w,
            'damping_factor': self.damping_factor,
            'damping_strategy': self.damping_strategy
        }
    
    def reset(self) -> None:
        """Reset detection state and clear all history"""
        self.power_history.clear()
        self.baseline_history.clear()
        self.oscillation_centers.clear()
        self.is_oscillating_state = False
        self.oscillation_amplitude = 0.0
        self.oscillation_baseline = 0.0
        self.previous_baseline = 0.0
        self.baseline_shift_detected = False
        self.last_analysis_time = None
    
    def _analyze_oscillations_with_baseline_tracking(self, current_time: datetime) -> None:
        """
        Enhanced oscillation analysis with adaptive baseline tracking
        
        Args:
            current_time: Current timestamp for analysis
        """
        if len(self.power_history) < 10:  # Need minimum data points
            self._clear_oscillation_state()
            return
            
        powers = [p for p, t in self.power_history]
        times = [t for p, t in self.power_history]
        
        # Find peaks and valleys
        peaks, valleys = self._find_peaks_and_valleys(powers, times)
        
        if len(peaks) < self.min_cycles or len(valleys) < self.min_cycles:
            self._clear_oscillation_state()
            return
            
        # Validate oscillation pattern
        if not self._validate_oscillation_pattern(peaks, valleys, powers):
            self._clear_oscillation_state()
            return
            
        # Enhanced oscillation detected - calculate parameters with baseline tracking
        self.is_oscillating_state = True
        self.oscillation_amplitude = self._calculate_amplitude(peaks, valleys, powers)
        
        # Calculate adaptive baseline from oscillation centers
        new_baseline = self._calculate_adaptive_baseline(peaks, valleys, powers, current_time)
        
        # Detect baseline shifts
        if self.oscillation_baseline > 0:  # Not first detection
            baseline_shift = abs(new_baseline - self.oscillation_baseline)
            if baseline_shift >= self.baseline_shift_threshold_w:
                self.baseline_shift_detected = True
                self.previous_baseline = self.oscillation_baseline
            else:
                # Keep previous shift state if shift is smaller than threshold
                # This prevents flickering of shift detection
                pass
        
        # Update baseline with smoothing to prevent abrupt changes
        if self.oscillation_baseline == 0:  # First detection
            self.oscillation_baseline = new_baseline
        else:
            # Smooth baseline adaptation
            self.oscillation_baseline = (
                self.oscillation_baseline * (1 - self.baseline_smoothing_factor) +
                new_baseline * self.baseline_smoothing_factor
            )
        
        # Record baseline history
        self.baseline_history.append((self.oscillation_baseline, current_time))
    
    def _calculate_adaptive_baseline(self, peaks: List[int], valleys: List[int], 
                                   powers: List[float], timestamp: datetime) -> float:
        """
        Calculate adaptive baseline from oscillation centers
        
        Args:
            peaks: Peak indices
            valleys: Valley indices
            powers: Power values
            timestamp: Current timestamp
            
        Returns:
            Calculated baseline power level
        """
        # Calculate oscillation centers (midpoint between each peak-valley pair)
        centers = []
        
        # Get recent peaks and valleys
        recent_peaks = peaks[-5:] if len(peaks) >= 5 else peaks
        recent_valleys = valleys[-5:] if len(valleys) >= 5 else valleys
        
        # Calculate centers from peak-valley pairs
        for peak_idx in recent_peaks:
            # Find closest valley
            closest_valley_idx = min(recent_valleys, 
                                   key=lambda v: abs(v - peak_idx), 
                                   default=None)
            if closest_valley_idx is not None:
                center = (powers[peak_idx] + powers[closest_valley_idx]) / 2
                centers.append(center)
        
        # Add centers to history
        self.oscillation_centers.extend(centers)
        
        # Keep only recent centers (last 10)
        self.oscillation_centers = self.oscillation_centers[-10:]
        
        # Calculate baseline from recent centers
        if self.oscillation_centers:
            return statistics.mean(self.oscillation_centers)
        else:
            # Fallback to simple average of recent power readings
            return statistics.mean(powers[-10:])
    
    def _find_peaks_and_valleys(self, powers: List[float], times: List[datetime]) -> Tuple[List[int], List[int]]:
        """
        Find peaks and valleys in power data using level change detection
        Enhanced to handle patterns with consecutive identical values (like square waves)
        """
        if len(powers) < 6:  # Need at least 6 points for meaningful pattern
            return [], []
            
        peaks = []
        valleys = []
        
        # Calculate threshold based on power range
        recent_powers = powers[-15:] if len(powers) >= 15 else powers
        if len(recent_powers) > 1:
            power_range = max(recent_powers) - min(recent_powers)
            threshold = power_range * 0.2  # 20% of range
        else:
            threshold = 100.0  # Minimum threshold
        
        # Find level changes (transitions between different power levels)
        i = 1
        while i < len(powers) - 1:
            current_power = powers[i]
            
            # Look for start of a high level (potential peak region)
            if (powers[i] > powers[i-1] + threshold):
                # Find the end of this high level
                peak_start = i
                while i < len(powers) - 1 and abs(powers[i] - current_power) < threshold/2:
                    i += 1
                peak_end = i - 1
                
                # Mark the middle of the high level as peak
                peak_idx = (peak_start + peak_end) // 2
                if peak_idx < len(powers):
                    peaks.append(peak_idx)
            
            # Look for start of a low level (potential valley region)
            elif (powers[i] < powers[i-1] - threshold):
                # Find the end of this low level
                valley_start = i
                while i < len(powers) - 1 and abs(powers[i] - current_power) < threshold/2:
                    i += 1
                valley_end = i - 1
                
                # Mark the middle of the low level as valley
                valley_idx = (valley_start + valley_end) // 2
                if valley_idx < len(powers):
                    valleys.append(valley_idx)
            else:
                i += 1
        
        return peaks, valleys
    
    def _validate_oscillation_pattern(self, peaks: List[int], valleys: List[int], 
                                    powers: List[float]) -> bool:
        """
        Enhanced validation that accounts for baseline shifts
        """
        # Check amplitude requirement (more flexible during baseline shifts)
        if not self._check_amplitude_requirement_enhanced(peaks, valleys, powers):
            return False
            
        # Check cycle timing requirement
        if not self._check_cycle_timing(peaks, valleys):
            return False
            
        # Enhanced pattern consistency check (more tolerant of baseline shifts)
        if not self._check_pattern_consistency_enhanced(peaks, valleys, powers):
            return False
            
        return True
    
    def _check_amplitude_requirement_enhanced(self, peaks: List[int], valleys: List[int], 
                                            powers: List[float]) -> bool:
        """Enhanced amplitude check that handles baseline shifts"""
        if not peaks or not valleys:
            return False
            
        # Check multiple recent peak-valley pairs
        recent_amplitudes = []
        recent_peaks = peaks[-5:]
        recent_valleys = valleys[-5:]
        
        for peak_idx in recent_peaks:
            # Find closest valley to this peak
            closest_valley_idx = min(recent_valleys, 
                                   key=lambda v: abs(v - peak_idx), 
                                   default=None)
            if closest_valley_idx is not None:
                amplitude = abs(powers[peak_idx] - powers[closest_valley_idx])
                recent_amplitudes.append(amplitude)
        
        if not recent_amplitudes:
            return False
            
        # Check if average amplitude meets requirement
        avg_amplitude = statistics.mean(recent_amplitudes)
        return avg_amplitude >= self.min_amplitude_w
    
    def _check_cycle_timing(self, peaks: List[int], valleys: List[int]) -> bool:
        """Check if cycle timing is within acceptable range"""
        # Combine and sort all extrema by index
        all_extrema = sorted(peaks + valleys)
        
        if len(all_extrema) < 4:  # Need at least 2 complete cycles
            return False
            
        # Check intervals between extrema (half-cycles) using actual timestamps
        intervals = []
        for i in range(1, len(all_extrema)):
            idx1, idx2 = all_extrema[i-1], all_extrema[i]
            if idx1 < len(self.power_history) and idx2 < len(self.power_history):
                time_diff = (self.power_history[idx2][1] - self.power_history[idx1][1]).total_seconds()
                intervals.append(time_diff)
        
        if not intervals:
            return False
            
        # Check if cycle times are reasonable - only reject extremely fast (< 0.01s) or too slow
        # This allows detection of very fast oscillations like 0.5s cycles
        min_half_cycle = 0.01  # Minimum 0.01s half-cycle (only reject sensor noise)
        max_half_cycle = self.max_cycle_duration_s / 2
        
        return all(min_half_cycle <= interval <= max_half_cycle for interval in intervals)
    
    def _check_pattern_consistency_enhanced(self, peaks: List[int], valleys: List[int], 
                                          powers: List[float]) -> bool:
        """Enhanced consistency check that tolerates baseline shifts"""
        # Check amplitude consistency rather than absolute value consistency
        if len(peaks) >= 2 and len(valleys) >= 2:
            amplitudes = []
            recent_peaks = peaks[-3:]
            recent_valleys = valleys[-3:]
            
            for peak_idx in recent_peaks:
                closest_valley_idx = min(recent_valleys, 
                                       key=lambda v: abs(v - peak_idx), 
                                       default=None)
                if closest_valley_idx is not None:
                    amplitude = abs(powers[peak_idx] - powers[closest_valley_idx])
                    amplitudes.append(amplitude)
            
            if len(amplitudes) >= 2:
                amplitude_variation = statistics.stdev(amplitudes)
                amplitude_mean = statistics.mean(amplitudes)
                if amplitude_mean > 0 and amplitude_variation / amplitude_mean > 0.4:  # 40% variation allowed
                    return False
        
        return True
    
    def _calculate_amplitude(self, peaks: List[int], valleys: List[int], 
                           powers: List[float]) -> float:
        """Calculate oscillation amplitude from recent peaks and valleys"""
        if not peaks or not valleys:
            return 0.0
            
        # Calculate amplitudes from recent peak-valley pairs
        amplitudes = []
        recent_peaks = peaks[-3:]
        recent_valleys = valleys[-3:]
        
        for peak_idx in recent_peaks:
            closest_valley_idx = min(recent_valleys, 
                                   key=lambda v: abs(v - peak_idx), 
                                   default=None)
            if closest_valley_idx is not None:
                amplitude = abs(powers[peak_idx] - powers[closest_valley_idx])
                amplitudes.append(amplitude)
        
        return statistics.mean(amplitudes) if amplitudes else 0.0
    
    def _clear_oscillation_state(self) -> None:
        """Clear oscillation detection state but preserve baseline history for continuity"""
        self.is_oscillating_state = False
        self.oscillation_amplitude = 0.0
        # Don't clear baseline immediately - allow for brief interruptions
        # self.oscillation_baseline = 0.0
        self.baseline_shift_detected = False