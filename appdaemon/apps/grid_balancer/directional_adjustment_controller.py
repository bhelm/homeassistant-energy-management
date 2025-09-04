"""directional_adjustment_controller.py - Smart cooldown based on grid direction"""
from datetime import datetime
from typing import Optional, Callable


class DirectionalAdjustmentController:
    """
    SINGLE RESPONSIBILITY: Control when battery adjustments should be allowed
    using directional logic to prevent oscillation while allowing under-correction fixes
    
    Logic:
    - If grid moves in SAME direction as before adjustment: Allow immediate correction (under-adjusted)
    - If grid moves in OPPOSITE direction: Use cooldown to prevent oscillation (over-adjusted)
    """
    
    def __init__(self, cooldown_seconds: float = 4.0, min_change_threshold_w: float = 100.0,
                 time_provider: Optional[Callable[[], datetime]] = None):
        """
        Initialize directional adjustment controller
        
        Args:
            cooldown_seconds: Time to wait when grid moves opposite to expectation
            min_change_threshold_w: Minimum grid change to consider for direction logic
            time_provider: Function to get current time (defaults to datetime.now)
        """
        self.cooldown_seconds = cooldown_seconds
        self.min_change_threshold_w = min_change_threshold_w
        self.time_provider = time_provider or datetime.now
        
        # State tracking
        self.last_adjustment_time: Optional[datetime] = None
        self.grid_power_at_adjustment: Optional[float] = None
        self.expected_direction: Optional[str] = None  # 'toward_zero', 'away_from_zero'
    
    def should_allow_adjustment(self, current_grid_power: float, proposed_battery_target: float,
                               current_battery_target: float) -> bool:
        """
        Directional cooldown check
        
        Args:
            current_grid_power: Current grid power reading
            proposed_battery_target: New battery target power (unused)
            current_battery_target: Current battery target power (unused)
            
        Returns:
            True if adjustment is allowed, False if blocked by cooldown
        """
        # First adjustment always allowed
        if self.last_adjustment_time is None or self.grid_power_at_adjustment is None:
            return True
            
        elapsed = (self.time_provider() - self.last_adjustment_time).total_seconds()
        
        # Normal cooldown period passed
        if elapsed >= self.cooldown_seconds:
            return True
            
        # Check grid direction since last adjustment
        grid_change = current_grid_power - self.grid_power_at_adjustment
        
        # Ignore tiny changes
        if abs(grid_change) < self.min_change_threshold_w:
            return False  # Still in cooldown, no significant change
            
        # Determine actual direction
        if self.grid_power_at_adjustment == 0:
            actual_direction = 'away_from_zero'  # Any change from zero is away
        elif abs(current_grid_power) > abs(self.grid_power_at_adjustment):
            actual_direction = 'away_from_zero'  # Magnitude increased - under-correction
        else:
            actual_direction = 'toward_zero'  # Magnitude decreased - good correction
            
        # Key insight: If grid magnitude INCREASED (away_from_zero), we under-corrected - allow immediate fix
        if actual_direction == 'away_from_zero':
            return True  # Under-correction, safe to adjust more immediately
            
        # Grid moved toward zero - this is expected, but use cooldown to prevent over-correction
        return False
    
    def record_adjustment(self, grid_power: float, new_battery_target: float,
                         previous_battery_target: float, timestamp: datetime) -> None:
        """
        Record adjustment and expected grid direction
        
        Args:
            grid_power: Grid power at time of adjustment
            new_battery_target: New battery target power
            previous_battery_target: Previous battery target power
            timestamp: When the adjustment was made
        """
        self.last_adjustment_time = timestamp
        self.grid_power_at_adjustment = grid_power
        
        # Determine expected direction based on battery adjustment
        battery_change = new_battery_target - previous_battery_target
        
        # We always expect the grid to move toward zero after any battery adjustment
        # The key is detecting when it moves AWAY from zero (under-correction)
        self.expected_direction = 'toward_zero'
    
    def get_status_info(self) -> dict:
        """
        Get current status information for logging/debugging
        
        Returns:
            Dictionary with current state information
        """
        return {
            'cooldown_seconds': self.cooldown_seconds,
            'min_change_threshold_w': self.min_change_threshold_w,
            'time_since_last_adjustment': (
                (self.time_provider() - self.last_adjustment_time).total_seconds()
                if self.last_adjustment_time else None
            ),
            'grid_power_at_adjustment': self.grid_power_at_adjustment,
            'expected_direction': self.expected_direction
        }
    
    def get_direction_info(self, current_grid_power: float) -> Optional[dict]:
        """
        Get directional analysis for logging
        
        Args:
            current_grid_power: Current grid power reading
            
        Returns:
            Dictionary with direction analysis or None
        """
        if self.grid_power_at_adjustment is None:
            return None
            
        grid_change = current_grid_power - self.grid_power_at_adjustment
        
        if abs(grid_change) < self.min_change_threshold_w:
            return None  # Change too small to analyze
            
        # Determine actual direction
        if self.grid_power_at_adjustment == 0:
            actual_direction = 'away_from_zero'
        elif abs(current_grid_power) > abs(self.grid_power_at_adjustment):
            actual_direction = 'away_from_zero'
        else:
            actual_direction = 'toward_zero'
            
        return {
            'grid_at_adjustment': self.grid_power_at_adjustment,
            'current_grid': current_grid_power,
            'grid_change': grid_change,
            'expected_direction': self.expected_direction,
            'actual_direction': actual_direction,
            'direction_match': actual_direction == self.expected_direction,
            'under_corrected': actual_direction == 'away_from_zero'
        }
    
    # Compatibility methods for existing code
    def get_feedback_details(self) -> Optional[dict]:
        """Compatibility method - returns None since we don't do feedback detection"""
        return None
    
    def get_feedback_success_info(self) -> Optional[dict]:
        """Compatibility method - returns None since we don't do feedback detection"""
        return None
    
    def get_feedback_timeout_info(self) -> Optional[dict]:
        """Compatibility method - returns None since we don't do feedback detection"""
        return None