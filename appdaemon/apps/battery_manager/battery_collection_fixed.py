"""Battery Collection - Multi-battery coordination"""
import time
from typing import List, Dict
from battery import Battery


class BatteryCollection:
    """Manages multiple batteries as a unified system"""
    
    def __init__(self, batteries: List[Battery], app):
        self.batteries = {battery.name: battery for battery in batteries}
        self.app = app
        self._target_power = 0
        # Per-battery power caching to avoid redundant service calls
        self._last_applied_power = {}  # battery_name -> last_applied_power_w
        self._power_tolerance = 5.0    # Skip if power change < 5W
        self._last_available_batteries = set()  # Track battery availability changes
    
    def get_available_batteries(self) -> List[Battery]:
        """Get list of available batteries"""
        return [bat for bat in self.batteries.values() if bat.is_available()]
    
    def _clear_power_cache(self):
        """Clear the power cache when battery configuration changes"""
        if self._last_applied_power:
            self.app.log(f"Cleared power cache for {len(self._last_applied_power)} batteries", level="INFO")
            self._last_applied_power.clear()
    
    
    def get_combined_soc(self) -> float:
        """Calculate combined SoC: Total Remaining / Total Capacity * 100"""
        available = self.get_available_batteries()
        if not available:
            return 0.0
        
        total_remaining = sum(bat.get_remaining_kwh() for bat in available)
        total_capacity = sum(bat.get_total_capacity_kwh() for bat in available)
        
        if total_capacity == 0:
            return 0.0
        
        return (total_remaining / total_capacity) * 100
    
    def get_combined_remaining_kwh(self) -> float:
        """Get total remaining energy across all batteries"""
        return sum(bat.get_remaining_kwh() for bat in self.get_available_batteries())
    
    def get_combined_capacity_kwh(self) -> float:
        """Get total capacity across all batteries"""
        return sum(bat.get_total_capacity_kwh() for bat in self.get_available_batteries())
    
    def get_combined_current_power_w(self) -> float:
        """Get total current power across all batteries"""
        return sum(bat.get_current_power_w() for bat in self.get_available_batteries())
    
    def set_total_power_w(self, total_power_w: float) -> bool:
        """Set total power across all batteries with smart distribution"""
        self._target_power = total_power_w
        
        available_batteries = self.get_available_batteries()
        current_available_names = {bat.name for bat in available_batteries}
        
        # Clear cache if available batteries changed
        if current_available_names != self._last_available_batteries:
            self._clear_power_cache()
            self._last_available_batteries = current_available_names.copy()
        
        if not available_batteries:
            self.app.log("No available batteries for power setting", level="WARNING")
            return False
        
        # Distribute power proportionally
        success = self._distribute_power_proportionally(total_power_w, available_batteries)
        
        return success
    
    def _distribute_power_proportionally(self, total_power_w: float, batteries: List[Battery]) -> bool:
        """Distribute power proportionally based on battery capacity with SoC-aware charging"""
        if not batteries:
            return False
        
        # Filter batteries based on SoC and power direction
        eligible_batteries = self._get_eligible_batteries_for_power(batteries, total_power_w)
        
        if not eligible_batteries:
            self.app.log(f"No eligible batteries for {total_power_w}W power request", level="WARNING")
            return False
        
        # Calculate total capacity of eligible batteries only
        total_eligible_capacity = sum(bat.get_total_capacity_kwh() for bat in eligible_batteries)
        if total_eligible_capacity == 0:
            return False
        
        success = True
        actual_total = 0
        
        # Log power redistribution if batteries were filtered out
        if len(eligible_batteries) < len(batteries):
            filtered_count = len(batteries) - len(eligible_batteries)
            self.app.log(f"Redistributing {total_power_w}W among {len(eligible_batteries)} eligible batteries "
                        f"({filtered_count} batteries filtered out due to SoC)", level="INFO")
        
        for battery in eligible_batteries:
            # Calculate proportional power based on eligible batteries only
            capacity_ratio = battery.get_total_capacity_kwh() / total_eligible_capacity
            battery_power_before_limits = total_power_w * capacity_ratio
            
            # Apply battery limits
            battery_power_after_limits = self._apply_battery_limits(battery, battery_power_before_limits)
            
            battery_power = round(battery_power_after_limits)
            
            # Check if power has changed significantly (with tolerance)
            last_applied_power = self._last_applied_power.get(battery.name)
            
            if (last_applied_power is None or
                abs(battery_power - last_applied_power) > self._power_tolerance):
                
                # Set battery power only if it changed significantly
                if battery.set_power_w(battery_power):
                    # Update cache only on successful power application
                    self._last_applied_power[battery.name] = battery_power
                    actual_total += battery_power
                    self.app.log(f"Applied {battery.name}: {battery_power}W", level="INFO")
                else:
                    success = False
                    self.app.log(f"Failed to set power for {battery.name}", level="ERROR")
            else:
                # Power unchanged within tolerance, skip the call
                actual_total += last_applied_power
                self.app.log(f"Skipped {battery.name}: {battery_power}W (unchanged)", level="DEBUG")
        
        # Set filtered batteries to 0W (stop mode) if they were excluded
        for battery in batteries:
            if battery not in eligible_batteries:
                # Set excluded batteries to 0W
                if battery.set_power_w(0):
                    self._last_applied_power[battery.name] = 0
                    self.app.log(f"Set {battery.name} to 0W (SoC: {battery.get_soc():.1f}%)", level="INFO")
        
        return success
    
    def _get_eligible_batteries_for_power(self, batteries: List[Battery], total_power_w: float) -> List[Battery]:
        """Filter batteries based on SoC and power direction"""
        eligible = []
        
        for battery in batteries:
            soc = battery.get_soc()
            
            if total_power_w > 0:  # Charging request
                # Skip batteries at 100% SoC for charging
                if soc >= 100.0:
                    self.app.log(f"Skipping {battery.name} for charging (SoC: {soc:.1f}%)", level="DEBUG")
                    continue
                else:
                    eligible.append(battery)
            elif total_power_w < 0:  # Discharging request
                # Skip batteries at very low SoC for discharging (e.g., below 5%)
                if soc <= 5.0:
                    self.app.log(f"Skipping {battery.name} for discharging (SoC: {soc:.1f}%)", level="DEBUG")
                    continue
                else:
                    eligible.append(battery)
            else:  # Zero power request
                # All batteries are eligible for stop command
                eligible.append(battery)
        
        return eligible
    
    def _apply_battery_limits(self, battery: Battery, requested_power: float) -> float:
        """Apply battery power limits"""
        if requested_power > 0:  # Charge (positive power)
            limited_power = min(requested_power, battery.get_max_charge_power_w())
        else:  # Discharge (negative power)
            limited_power = max(requested_power, -battery.get_max_discharge_power_w())
        
        
        return limited_power
    
    def stop_all_batteries(self):
        """Stop all batteries"""
        self._target_power = 0
        
        # Clear cache when stopping all batteries
        self._clear_power_cache()
        
        for battery in self.batteries.values():
            if battery.is_available():
                battery.set_power_w(0)
        
        self.app.log("All batteries stopped", level="INFO")
    
    def get_battery_status(self) -> Dict:
        """Get detailed status of all batteries"""
        status = {}
        for name, battery in self.batteries.items():
            status[name] = {
                'soc': battery.get_soc(),
                'remaining_kwh': battery.get_remaining_kwh(),
                'total_capacity_kwh': battery.get_total_capacity_kwh(),
                'current_power_w': battery.get_current_power_w(),
                'state': battery.get_state().value,
                'available': battery.is_available()
            }
        return status