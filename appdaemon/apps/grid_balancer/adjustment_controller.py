"""adjustment_controller.py - Controls timing and feedback for grid balancer adjustments"""
from datetime import datetime
from typing import Optional, Callable


class AdjustmentController:
    """
    SINGLE RESPONSIBILITY: Control when battery adjustments should be allowed
    based on timing and feedback detection to prevent oscillation
    
    Prevents the "doubling effect" where grid measurements haven't updated yet
    to reflect recent battery adjustments, causing excessive corrections.
    """
    
    def __init__(self, feedback_threshold_ratio: float = 0.4, max_timeout_s: float = 2.0,
                 large_change_threshold_w: float = 100.0, time_provider: Optional[Callable[[], datetime]] = None):
        """
        Initialize adjustment controller
        
        Args:
            feedback_threshold_ratio: Minimum ratio of expected vs actual grid change
                                    to consider feedback detected (0.4 = 40%)
            max_timeout_s: Maximum time to wait for feedback before allowing new adjustment
            large_change_threshold_w: Battery changes >= this threshold use feedback detection,
                                    smaller changes use simple time-based cooldown
            time_provider: Function to get current time (defaults to datetime.now)
        """
        self.feedback_threshold_ratio = feedback_threshold_ratio
        self.max_timeout_s = max_timeout_s
        self.large_change_threshold_w = large_change_threshold_w
        self.time_provider = time_provider or datetime.now
        
        # State tracking for feedback detection (large changes)
        self.waiting_for_feedback = False
        self.grid_power_at_adjustment: Optional[float] = None
        self.expected_grid_change: Optional[float] = None
        self.adjustment_timestamp: Optional[datetime] = None
        
        # State tracking for time-based cooldown (small changes)
        self.last_small_adjustment_time: Optional[datetime] = None
        
        # Feedback detection result tracking for detailed logging
        self._last_feedback_check: Optional[dict] = None
        self._feedback_success_info: Optional[dict] = None
        self._feedback_timeout_info: Optional[dict] = None
    
    def should_allow_adjustment(self, current_grid_power: float, proposed_battery_target: float,
                               current_battery_target: float) -> bool:
        """
        Hybrid approach: small changes use time cooldown, large changes use feedback detection
        
        Args:
            current_grid_power: Current grid power reading
            proposed_battery_target: New battery target power
            current_battery_target: Current battery target power
            
        Returns:
            True if adjustment is allowed, False if blocked
        """
        battery_change = abs(proposed_battery_target - current_battery_target)
        
        if battery_change < self.large_change_threshold_w:
            # Small change: use simple time-based cooldown
            return self._time_based_cooldown_allows_adjustment()
        else:
            # Large change: use feedback detection logic
            return self._feedback_detection_allows_adjustment(current_grid_power)
    
    def _time_based_cooldown_allows_adjustment(self) -> bool:
        """Check time-based cooldown for small adjustments"""
        if self.last_small_adjustment_time is None:
            return True
            
        elapsed = (self.time_provider() - self.last_small_adjustment_time).total_seconds()
        return elapsed >= self.max_timeout_s
    
    def _feedback_detection_allows_adjustment(self, current_grid_power: float) -> bool:
        """Check feedback detection for large adjustments"""
        # If not waiting for feedback, always allow
        if not self.waiting_for_feedback:
            return True
            
        # Check if feedback has been detected
        if self._has_feedback_been_detected(current_grid_power):
            # Store the successful feedback detection for logging
            self._feedback_success_info = self._last_feedback_check.copy() if self._last_feedback_check else None
            self._clear_waiting_state()
            return True
            
        # Check if timeout exceeded
        if self._timeout_exceeded():
            # Store timeout info for logging
            elapsed = (self.time_provider() - self.adjustment_timestamp).total_seconds() if self.adjustment_timestamp else 0
            self._feedback_timeout_info = {
                'elapsed_time': elapsed,
                'max_timeout': self.max_timeout_s,
                'reason': 'timeout'
            }
            self._clear_waiting_state()
            return True
            
        # Still waiting for feedback
        return False
    
    def record_adjustment(self, grid_power: float, new_battery_target: float,
                         previous_battery_target: float, timestamp: datetime) -> None:
        """
        Record adjustment and set appropriate tracking based on change magnitude
        
        Args:
            grid_power: Grid power at time of adjustment
            new_battery_target: New battery target power
            previous_battery_target: Previous battery target power
            timestamp: When the adjustment was made
        """
        battery_change = new_battery_target - previous_battery_target
        battery_change_magnitude = abs(battery_change)
        
        if battery_change_magnitude < self.large_change_threshold_w:
            # Small change: record time for cooldown
            self.last_small_adjustment_time = timestamp
        else:
            # Large change: set up feedback tracking
            self.waiting_for_feedback = True
            self.grid_power_at_adjustment = grid_power
            # When battery discharge increases (negative), grid import should decrease (negative) - same direction
            self.expected_grid_change = battery_change
            self.adjustment_timestamp = timestamp
    
    def _has_feedback_been_detected(self, current_grid_power: float) -> bool:
        """
        Check if grid measurement shows expected response to battery adjustment
        
        Args:
            current_grid_power: Current grid power reading
            
        Returns:
            True if feedback detected, False otherwise
        """
        if self.grid_power_at_adjustment is None or self.expected_grid_change is None:
            return True  # No expectation set, allow adjustment
            
        # Calculate actual grid change since adjustment
        actual_grid_change = current_grid_power - self.grid_power_at_adjustment
        
        # Check direction and magnitude
        direction_correct = self._same_direction(actual_grid_change, self.expected_grid_change)
        magnitude_sufficient = self._magnitude_sufficient(actual_grid_change, self.expected_grid_change)
        
        feedback_detected = direction_correct and magnitude_sufficient
        
        # Store feedback detection result for logging
        self._last_feedback_check = {
            'detected': feedback_detected,
            'actual_change': actual_grid_change,
            'expected_change': self.expected_grid_change,
            'direction_correct': direction_correct,
            'magnitude_sufficient': magnitude_sufficient,
            'magnitude_ratio': abs(actual_grid_change) / abs(self.expected_grid_change) if self.expected_grid_change != 0 else 0,
            'elapsed_time': (self.time_provider() - self.adjustment_timestamp).total_seconds() if self.adjustment_timestamp else 0
        }
        
        return feedback_detected
    
    def _same_direction(self, actual: float, expected: float) -> bool:
        """Check if actual and expected changes have same direction (sign)"""
        if expected == 0:
            return True  # No change expected
        return (actual * expected) > 0  # Same sign = same direction
    
    def _magnitude_sufficient(self, actual: float, expected: float) -> bool:
        """Check if actual change magnitude is sufficient compared to expected"""
        if expected == 0:
            return True  # No change expected
            
        min_expected_magnitude = abs(expected) * self.feedback_threshold_ratio
        return abs(actual) >= min_expected_magnitude
    
    def _timeout_exceeded(self) -> bool:
        """Check if maximum wait time for feedback has been exceeded"""
        if self.adjustment_timestamp is None:
            return True
            
        elapsed = (self.time_provider() - self.adjustment_timestamp).total_seconds()
        return elapsed >= self.max_timeout_s
    
    def _clear_waiting_state(self) -> None:
        """Clear waiting state and reset tracking variables"""
        self.waiting_for_feedback = False
        self.grid_power_at_adjustment = None
        self.expected_grid_change = None
        self.adjustment_timestamp = None
        self._last_feedback_check = None
    
    def get_status_info(self) -> dict:
        """
        Get current status information for logging/debugging
        
        Returns:
            Dictionary with current state information
        """
        return {
            'waiting_for_feedback': self.waiting_for_feedback,
            'grid_power_at_adjustment': self.grid_power_at_adjustment,
            'expected_grid_change': self.expected_grid_change,
            'time_since_large_adjustment': (
                (self.time_provider() - self.adjustment_timestamp).total_seconds()
                if self.adjustment_timestamp else None
            ),
            'time_since_small_adjustment': (
                (self.time_provider() - self.last_small_adjustment_time).total_seconds()
                if self.last_small_adjustment_time else None
            ),
            'large_change_threshold_w': self.large_change_threshold_w
        }
    
    def get_feedback_details(self) -> Optional[dict]:
        """
        Get detailed feedback detection information for enhanced logging
        
        Returns:
            Dictionary with feedback detection details or None if no recent check
        """
        return self._last_feedback_check
    
    def get_feedback_success_info(self) -> Optional[dict]:
        """
        Get information about successful feedback detection
        
        Returns:
            Dictionary with successful feedback info or None
        """
        info = self._feedback_success_info
        self._feedback_success_info = None  # Clear after reading
        return info
    
    def get_feedback_timeout_info(self) -> Optional[dict]:
        """
        Get information about feedback timeout
        
        Returns:
            Dictionary with timeout info or None
        """
        info = self._feedback_timeout_info
        self._feedback_timeout_info = None  # Clear after reading
        return info