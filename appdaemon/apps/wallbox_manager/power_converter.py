"""
Power conversion utilities for wallbox management.

This module provides utilities for converting between power (watts) and current (amps)
with proper 3-phase electrical calculations.
"""


class PowerConverter:
    """
    Utility class for converting between power and current values.
    
    This class encapsulates the electrical calculations needed for 3-phase power
    conversion, eliminating duplicate conversion logic throughout the codebase.
    """
    
    def __init__(self, voltage=233.33, sqrt_3=1.0):
        """
        Initialize the power converter with electrical parameters.

        Args:
            voltage (float): Line voltage in volts (default: 233.33V)
            sqrt_3 (float): Square root of 3 for 3-phase calculations (default: 1.0 for single-phase)
        """
        self._voltage = voltage
        self._sqrt_3 = sqrt_3
        self._base_power = sqrt_3 * voltage  # Pre-calculate for efficiency
    
    def to_amps(self, watts):
        """
        Convert power in watts to current in amps.
        
        Args:
            watts (float): Power in watts
            
        Returns:
            float: Current in amps
        """
        if watts <= 0:
            return 0.0
        return watts / self._base_power
    
    def to_watts(self, amps):
        """
        Convert current in amps to power in watts.
        
        Args:
            amps (float): Current in amps
            
        Returns:
            float: Power in watts
        """
        if amps <= 0:
            return 0.0
        return amps * self._base_power
    
    def min_power_for_current(self, min_amps):
        """
        Calculate minimum power needed for given current.
        
        Args:
            min_amps (float): Minimum current in amps
            
        Returns:
            float: Minimum power in watts
        """
        return self.to_watts(min_amps)
    
    @property
    def voltage(self):
        """Get the configured voltage."""
        return self._voltage
    
    @property
    def sqrt_3(self):
        """Get the configured sqrt_3 factor."""
        return self._sqrt_3