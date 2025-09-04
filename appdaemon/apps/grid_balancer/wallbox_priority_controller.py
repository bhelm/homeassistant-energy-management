"""
Simplified Wallbox Priority Controller - Acts only on actual wallbox power usage

This controller implements simple decision logic:
1. If wallbox consuming power: reduce battery target by 1000W to leave room for expansion
2. If wallbox charging: prevent battery discharge (safety rule)

Single Responsibility: Reserve power for active wallboxes based on actual consumption
"""

class WallboxPriorityController:
    """
    Simplified controller that reserves power for active wallboxes
    """
    
    def __init__(self, config: dict, app_instance):
        """
        Initialize the simplified wallbox priority controller
        
        Args:
            config: Configuration dictionary with simple parameters
            app_instance: AppDaemon app instance for sensor access and logging
        """
        self.app = app_instance
        
        # Simplified configuration with defaults
        self.enabled = config.get('enabled', True)
        self.wallbox_power_threshold_w = config.get('wallbox_power_threshold_w', 100)  # Minimum power to consider "active"
        self.wallbox_reserve_power_w = config.get('wallbox_reserve_power_w', 1000)    # Power to reserve when active
        
        # Only need wallbox power sensor - no more complex sensors
        self.wallbox_power_sensor = config.get('wallbox_power_sensor', 'sensor.gesamt_wallboxen_w')
        
        self.app.log(f"WallboxPriorityController initialized (SIMPLIFIED) - "
                    f"Power threshold: {self.wallbox_power_threshold_w}W, "
                    f"Reserve power: {self.wallbox_reserve_power_w}W, "
                    f"Enabled: {self.enabled}")
    
    def calculate_allowed_battery_power(self, grid_power: float, normal_battery_target: float, allow_wallbox_battery_use: bool = False) -> tuple[float, str]:
        """
        Simplified wallbox priority logic:
        1. If wallbox consuming power: reduce battery target by reserve amount
        2. If wallbox charging: prevent battery discharge (unless allow_wallbox_battery_use is True)
        
        Args:
            grid_power: Current grid power (+ = import, - = export) - UNUSED in simplified logic
            normal_battery_target: Normal battery target without wallbox priority
            allow_wallbox_battery_use: If True, allow battery discharge even when wallbox is charging
            
        Returns:
            tuple: (allowed_battery_power: float, reason: str)
        """
        if not self.enabled:
            return normal_battery_target, "Priority controller disabled"
        
        try:
            # Get actual wallbox power consumption
            wallbox_current_power = self._get_wallbox_current_power()
            wallbox_is_active = wallbox_current_power >= self.wallbox_power_threshold_w
            
            self.app.log(f"🔌 WALLBOX PRIORITY (SIMPLIFIED) - "
                        f"Wallbox power: {wallbox_current_power:.0f}W, "
                        f"Active: {wallbox_is_active} (threshold: {self.wallbox_power_threshold_w}W)")
            
            # Rule 2: Prevent battery discharge when wallbox is charging (unless toggle allows it)
            if wallbox_is_active and normal_battery_target < 0 and not allow_wallbox_battery_use:
                return 0, f"Wallbox active ({wallbox_current_power:.0f}W) - prevent battery discharge (was {normal_battery_target:.0f}W) [Toggle OFF]"
            
            # Rule 2 Override: Allow battery discharge when toggle is ON
            if wallbox_is_active and normal_battery_target < 0 and allow_wallbox_battery_use:
                self.app.log(f"🔋 TOGGLE OVERRIDE - Wallbox active ({wallbox_current_power:.0f}W) but allowing battery discharge ({normal_battery_target:.0f}W) [Toggle ON]")
                return normal_battery_target, f"Wallbox active ({wallbox_current_power:.0f}W) - allowing battery discharge ({normal_battery_target:.0f}W) [Toggle ON]"
            
            # Rule 1: Reserve power when wallbox is active (for charging scenarios)
            if wallbox_is_active:
                reserved_battery_target = max(0, normal_battery_target - self.wallbox_reserve_power_w)
                return reserved_battery_target, f"Wallbox active ({wallbox_current_power:.0f}W) - reserved {self.wallbox_reserve_power_w}W: {normal_battery_target:.0f}W → {reserved_battery_target:.0f}W"
            
            # No wallbox activity - normal battery operation
            return normal_battery_target, "No wallbox activity - normal battery operation"
                    
        except Exception as e:
            self.app.log(f"Error in wallbox priority check: {e}", level="ERROR")
            return normal_battery_target, f"Error in priority check: {e}"
    
    def _get_wallbox_current_power(self) -> float:
        """Get current wallbox power consumption"""
        state = self.app.get_state(self.wallbox_power_sensor)
        if state is None or state in ['unknown', 'unavailable']:
            return 0.0
        try:
            return float(state)
        except (ValueError, TypeError):
            return 0.0
    
    def get_status_info(self) -> dict:
        """Get current status information for debugging"""
        try:
            wallbox_current_power = self._get_wallbox_current_power()
            
            return {
                'enabled': self.enabled,
                'wallbox_current_power': wallbox_current_power,
                'wallbox_is_active': wallbox_current_power >= self.wallbox_power_threshold_w,
                'wallbox_power_threshold_w': self.wallbox_power_threshold_w,
                'wallbox_reserve_power_w': self.wallbox_reserve_power_w
            }
        except Exception as e:
            return {'error': str(e)}