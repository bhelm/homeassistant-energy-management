"""
Rate limiting functionality for wallbox power management.

This module provides rate limiting to prevent sudden power changes that could
destabilize the electrical grid or cause hardware issues.
"""

from power_converter import PowerConverter


class RateLimiter:
    """
    Rate limiter for wallbox power changes.
    
    Prevents sudden power changes by gradually transitioning between current levels,
    ensuring grid stability and hardware protection.
    """
    
    def __init__(self, max_change_watts, power_converter, min_current_a=6.0, logger=None):
        """
        Initialize the rate limiter.
        
        Args:
            max_change_watts (float): Maximum power change per cycle in watts
            power_converter (PowerConverter): Power conversion utility
            min_current_a (float): Minimum current in amps (default: 6.0)
            logger (callable): Optional logging function
        """
        self._max_change = max_change_watts
        self._converter = power_converter
        self._min_current = min_current_a
        self._log = logger or (lambda msg: None)
    
    def apply_limit(self, wallbox_name, current_amps, target_amps, allow_immediate_stop=True):
        """
        Apply rate limiting to prevent sudden power changes.
        
        Args:
            wallbox_name (str): Name of the wallbox for logging
            current_amps (float): Current charging current in amps
            target_amps (float): Desired target current in amps
            allow_immediate_stop (bool): Whether to allow immediate stops (default: True)
            
        Returns:
            float: Rate-limited current in amps
        """
        # Handle immediate stops - no rate limiting for safety
        if target_amps <= 0 and allow_immediate_stop:
            self._log(f"RATE_LIMIT: {wallbox_name.capitalize()} stopping immediately (no rate limiting for stops)")
            return target_amps
        
        # Handle negative target (insufficient power) - allow immediate stop
        if target_amps < 0:
            self._log(f"RATE_LIMIT: {wallbox_name.capitalize()} target current is negative ({target_amps:.2f}A) - insufficient power, stopping immediately")
            return target_amps
        
        # Convert to watts for calculation
        current_watts = self._converter.to_watts(current_amps)
        target_watts = self._converter.to_watts(target_amps)
        watts_difference = target_watts - current_watts
        
        # Check if change is within limits
        if abs(watts_difference) <= self._max_change:
            if abs(watts_difference) > 10:  # Only log significant changes
                self._log(f"RATE_LIMIT: {wallbox_name.capitalize()} change within limit ({current_watts:.0f}W → {target_watts:.0f}W)")
            return target_amps
        
        # Apply rate limiting
        if watts_difference > self._max_change:
            # Limiting increase
            limited_watts = current_watts + self._max_change
            limited_amps = self._converter.to_amps(limited_watts)
            
            # Special case: When starting from 0A, ensure we start at minimum current
            if current_amps == 0 and limited_amps < self._min_current:
                limited_amps = self._min_current
                limited_watts = self._converter.to_watts(limited_amps)
                self._log(f"RATE_LIMIT: {wallbox_name.capitalize()} starting at minimum {self._min_current}A instead of calculated {self._converter.to_amps(current_watts + self._max_change):.1f}A")
            else:
                self._log(f"RATE_LIMIT: {wallbox_name.capitalize()} increase limited to +{self._max_change}W ({current_watts:.0f}W → {limited_watts:.0f}W, {limited_amps:.1f}A)")
            
            return limited_amps
            
        elif watts_difference < -self._max_change:
            # Limiting decrease
            limited_watts = current_watts - self._max_change
            limited_amps = self._converter.to_amps(limited_watts)
            self._log(f"RATE_LIMIT: {wallbox_name.capitalize()} decrease limited to -{self._max_change}W ({current_watts:.0f}W → {limited_watts:.0f}W, {limited_amps:.1f}A)")
            return limited_amps
        
        # This should never be reached, but return target as fallback
        return target_amps
    
    def is_change_within_limit(self, current_amps, target_amps):
        """
        Check if a power change is within the rate limit without applying it.
        
        Args:
            current_amps (float): Current charging current in amps
            target_amps (float): Desired target current in amps
            
        Returns:
            bool: True if change is within limit, False otherwise
        """
        if target_amps <= 0:  # Stops are always allowed
            return True
            
        current_watts = self._converter.to_watts(current_amps)
        target_watts = self._converter.to_watts(target_amps)
        watts_difference = abs(target_watts - current_watts)
        
        return watts_difference <= self._max_change
    
    @property
    def max_change_watts(self):
        """Get the maximum power change per cycle."""
        return self._max_change
    
    @max_change_watts.setter
    def max_change_watts(self, value):
        """Set the maximum power change per cycle."""
        if value <= 0:
            raise ValueError("Maximum power change must be positive")
        self._max_change = value