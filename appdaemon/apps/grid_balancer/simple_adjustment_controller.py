"""simple_adjustment_controller.py - Simple time-based cooldown for grid balancer adjustments"""
from datetime import datetime
from typing import Optional, Callable


class SimpleAdjustmentController:
    """
    SINGLE RESPONSIBILITY: Control when battery adjustments should be allowed
    using simple time-based cooldown to prevent oscillation
    
    Much simpler than the hybrid approach - just wait X seconds between any adjustments.
    """
    
    def __init__(self, cooldown_seconds: float = 4.0, time_provider: Optional[Callable[[], datetime]] = None):
        """
        Initialize simple adjustment controller
        
        Args:
            cooldown_seconds: Time to wait between any adjustments
            time_provider: Function to get current time (defaults to datetime.now)
        """
        self.cooldown_seconds = cooldown_seconds
        self.time_provider = time_provider or datetime.now
        
        # Simple state tracking
        self.last_adjustment_time: Optional[datetime] = None
    
    def should_allow_adjustment(self, current_grid_power: float, proposed_battery_target: float,
                               current_battery_target: float) -> bool:
        """
        Simple cooldown check - allow adjustment if enough time has passed
        
        Args:
            current_grid_power: Current grid power reading (unused in simple version)
            proposed_battery_target: New battery target power (unused in simple version)
            current_battery_target: Current battery target power (unused in simple version)
            
        Returns:
            True if adjustment is allowed, False if still in cooldown
        """
        if self.last_adjustment_time is None:
            return True  # First adjustment always allowed
            
        elapsed = (self.time_provider() - self.last_adjustment_time).total_seconds()
        return elapsed >= self.cooldown_seconds
    
    def record_adjustment(self, grid_power: float, new_battery_target: float,
                         previous_battery_target: float, timestamp: datetime) -> None:
        """
        Record adjustment timestamp for cooldown tracking
        
        Args:
            grid_power: Grid power at time of adjustment (unused)
            new_battery_target: New battery target power (unused)
            previous_battery_target: Previous battery target power (unused)
            timestamp: When the adjustment was made
        """
        self.last_adjustment_time = timestamp
    
    def get_status_info(self) -> dict:
        """
        Get current status information for logging/debugging
        
        Returns:
            Dictionary with current state information
        """
        return {
            'cooldown_seconds': self.cooldown_seconds,
            'time_since_last_adjustment': (
                (self.time_provider() - self.last_adjustment_time).total_seconds()
                if self.last_adjustment_time else None
            ),
            'last_adjustment_time': self.last_adjustment_time.isoformat() if self.last_adjustment_time else None
        }
    
    # Compatibility methods for existing code that expects feedback detection methods
    def get_feedback_details(self) -> Optional[dict]:
        """Compatibility method - returns None since we don't do feedback detection"""
        return None
    
    def get_feedback_success_info(self) -> Optional[dict]:
        """Compatibility method - returns None since we don't do feedback detection"""
        return None
    
    def get_feedback_timeout_info(self) -> Optional[dict]:
        """Compatibility method - returns None since we don't do feedback detection"""
        return None