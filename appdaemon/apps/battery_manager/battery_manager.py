"""Battery Manager - Main orchestrator for battery management system"""
import appdaemon.plugins.hass.hassapi as hass
import sys
import os
import time
from typing import Dict, List

# Add the battery_manager directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

# Force reload of modules to ensure latest changes are loaded
import importlib
try:
    import marstek_battery
    importlib.reload(marstek_battery)
    from marstek_battery import MarstekBattery
except Exception as e:
    # Fallback to normal import if reload fails
    from marstek_battery import MarstekBattery

from battery_collection import BatteryCollection


class BatteryManager(hass.Hass):
    """Main battery management orchestrator - SOLID principle: only manages batteries"""
    
    def initialize(self):
        """Initialize the Battery Manager"""
        try:
            self.log("Starting Battery Manager initialization...")
            self.log("Initializing Battery Manager")
            
            # Configuration
            self.log("Loading configuration...")
            self.update_interval = self.args.get('update_interval', 2)
            
            # Initialize batteries from configuration
            self.log("Initializing batteries...")
            self.batteries = self._initialize_batteries()
            self.log("Creating battery collection...")
            self.battery_collection = BatteryCollection(list(self.batteries.values()), self)
            
            # Create and set up Home Assistant entities
            self.log("Creating control entities...")
            self._create_control_entities()
            self.log("Creating status sensors...")
            self._create_status_sensors()
            
            # Set up listeners for control entities
            self.log("Setting up entity listeners...")
            self._setup_entity_listeners()
            
            # Schedule periodic updates
            self.log("Scheduling periodic updates...")
            self.run_every(self._periodic_update, "now", self.update_interval)
            
            # Ensure clean state after restart
            self.log("Ensuring clean state after restart...")
            self._ensure_clean_startup_state()
            
            self.log(f"Battery Manager initialized with {len(self.batteries)} batteries")
        except Exception as e:
            self.log(f"ERROR: Failed to initialize Battery Manager: {e}", level="ERROR")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}", level="ERROR")
            raise
    
    def terminate(self):
        """Called when the app is being shut down - reset to safe state"""
        try:
            self.log("Battery Manager terminating - resetting to safe state")
            self._reset_to_safe_state()
        except Exception as e:
            self.log(f"Error during termination cleanup: {e}", level="ERROR")
    
    def _initialize_batteries(self) -> Dict[str, any]:
        """Initialize batteries from configuration"""
        batteries = {}
        battery_configs = self.args.get('batteries', [])
        
        for config in battery_configs:
            battery_type = config.get('type')
            name = config.get('name')
            
            if battery_type == 'marstek':
                device_prefix = config.get('device_prefix', name.lower())
                self.log(f"Creating MarstekBattery with name={name}, app={self}, prefix={device_prefix}", level="INFO")
                try:
                    battery = MarstekBattery(name, self, device_prefix)
                    self.log(f"MarstekBattery created successfully: {type(battery)}", level="INFO")
                    self.log(f"Battery has is_available method: {hasattr(battery, 'is_available')}", level="INFO")
                    batteries[name] = battery
                    self.log(f"Initialized Marstek battery: {name} (prefix: {device_prefix})")
                except Exception as e:
                    self.log(f"ERROR creating MarstekBattery: {e}", level="ERROR")
                    import traceback
                    self.log(f"Traceback: {traceback.format_exc()}", level="ERROR")
            else:
                self.log(f"Unknown battery type: {battery_type}", level="ERROR")
        
        return batteries
    
    def _create_control_entities(self):
        """Set up Home Assistant control entities (they're defined in configuration.yaml)"""
        # Check if the entities exist and log their current state
        target_power_state = self.get_state("input_number.battery_manager_target_power")
        enabled_state = self.get_state("input_boolean.battery_manager_enabled")
        
        if target_power_state is not None:
            self.log(f"Target power entity found with state: {target_power_state}")
        else:
            self.log("WARNING: input_number.battery_manager_target_power not found", level="WARNING")
            
        if enabled_state is not None:
            self.log(f"Enabled entity found with state: {enabled_state}")
        else:
            self.log("WARNING: input_boolean.battery_manager_enabled not found", level="WARNING")
    
    def _create_status_sensors(self):
        """Create Home Assistant status sensors"""
        # Combined battery sensors
        self.set_state("sensor.combined_battery_soc",
                      state=self.battery_collection.get_combined_soc(),
                      attributes={
                          "unit_of_measurement": "%",
                          "device_class": "battery",
                          "state_class": "measurement",
                          "friendly_name": "Combined Battery SoC",
                          "icon": "mdi:battery"
                      })
        
        self.set_state("sensor.combined_battery_power",
                      state=self.battery_collection.get_combined_current_power_w(),
                      attributes={
                          "unit_of_measurement": "W",
                          "device_class": "power",
                          "state_class": "measurement",
                          "friendly_name": "Combined Battery Power",
                          "icon": "mdi:flash"
                      })
        
        self.set_state("sensor.combined_battery_capacity",
                      state=self.battery_collection.get_combined_capacity_kwh(),
                      attributes={
                          "unit_of_measurement": "kWh",
                          "device_class": "energy_storage",
                          "state_class": "measurement",
                          "friendly_name": "Combined Battery Capacity",
                          "icon": "mdi:battery-charging-100"
                      })
        
        self.set_state("sensor.combined_battery_remaining",
                      state=self.battery_collection.get_combined_remaining_kwh(),
                      attributes={
                          "unit_of_measurement": "kWh",
                          "device_class": "energy_storage",
                          "state_class": "measurement",
                          "friendly_name": "Combined Battery Remaining",
                          "icon": "mdi:battery-arrow-down"
                      })
        
        # System status sensors
        self.set_state("sensor.battery_manager_status",
                      state=self._get_system_status(),
                      attributes={
                          "friendly_name": "Battery Manager Status",
                          "icon": "mdi:cog"
                      })
        
        # Invert the actual power to match our convention (positive=charge, negative=discharge)
        actual_power = -self.battery_collection.get_combined_current_power_w()
        self.set_state("sensor.battery_manager_actual_power",
                      state=actual_power,
                      attributes={
                          "unit_of_measurement": "W",
                          "device_class": "power",
                          "friendly_name": "Battery Manager Actual Power",
                          "icon": "mdi:flash-outline"
                      })
        
        # Individual battery status sensors
        for name, battery in self.batteries.items():
            entity_id = f"sensor.battery_{name.lower()}_status"
            self.set_state(entity_id,
                          state=battery.get_state().value,
                          attributes={
                              "friendly_name": f"Battery {name} Status",
                              "soc": battery.get_soc(),
                              "power_w": battery.get_current_power_w(),
                              "available": battery.is_available(),
                              "icon": "mdi:battery-outline"
                          })
    
    def _setup_entity_listeners(self):
        """Set up listeners for control entities"""
        # Re-enabled to fix discharge issue - monitor for feedback loops
        self.listen_state(self._on_target_power_change, "input_number.battery_manager_target_power")
        self.log("Target power state listener ENABLED - monitoring for feedback loops", level="INFO")
        
        # Active listeners
        self.listen_state(self._on_enabled_change, "input_boolean.battery_manager_enabled")
    
    def _apply_target_power(self, target_power: float):
        """Apply target power to batteries"""
        enabled = self.get_state("input_boolean.battery_manager_enabled") == "on"
        
        if enabled:
            success = self.battery_collection.set_total_power_w(target_power)
            return success
        return False
    
    def _on_target_power_change(self, entity, attribute, old, new, kwargs):
        """Handle target power changes from HA number entity"""
        try:
            target_power = float(new)
            success = self._apply_target_power(target_power)
            self.log(f"Target power set to {target_power:.0f}W: {'Success' if success else 'Failed'}")
        except (ValueError, TypeError) as e:
            self.log(f"Error processing target power change: {e}", level="ERROR")
    
    def _on_enabled_change(self, entity, attribute, old, new, kwargs):
        """Handle enable/disable from HA boolean entity"""
        if new == "off":
            self._reset_to_safe_state()
            self.log("Battery Manager disabled - reset to safe state")
        elif new == "on":
            self._reset_to_safe_state()
            self.log("Battery Manager enabled - reset to safe state")
    
    def _periodic_update(self, kwargs):
        """Periodic update of sensors and system health"""
        try:
            # Update all status sensors
            self._create_status_sensors()
            
            # Redistribute power every update (handles newly available batteries)
            target_power_state = self.get_state("input_number.battery_manager_target_power")
            if target_power_state is not None:
                target_power = float(target_power_state)
                self._apply_target_power(target_power)
            
            # Log system status periodically
            if hasattr(self, '_update_counter'):
                self._update_counter += 1
            else:
                self._update_counter = 1
            
            # Log every update (every 2 seconds)
            self._log_system_status()
        
        except Exception as e:
            self.log(f"Error in periodic update: {e}", level="ERROR")
    
    def _get_system_status(self) -> str:
        """Get current system status"""
        enabled = self.get_state("input_boolean.battery_manager_enabled") == "on"
        available_batteries = self.battery_collection.get_available_batteries()
        available_count = len(available_batteries)
        total_count = len(self.batteries)
        
        # Clean status check without excessive logging
        
        if not enabled:
            return "disabled"
        elif available_count == 0:
            return "no_batteries"
        elif available_count < total_count:
            return "degraded"
        else:
            return "active"
    
    def _log_system_status(self):
        """Log current system status"""
        soc = self.battery_collection.get_combined_soc()
        power = self.battery_collection.get_combined_current_power_w()
        target = self.battery_collection._target_power
        available_count = len(self.battery_collection.get_available_batteries())
        total_count = len(self.batteries)
        
        self.log(f"System Status - SoC: {soc:.1f}%, Power: {power:.0f}W "
                f"(Target: {target:.0f}W), Batteries: {available_count}/{total_count}",
                level="INFO")
    
    def _reset_to_safe_state(self):
        """Reset system to safe state: target power = 0, all batteries stopped"""
        try:
            # Reset target power to 0 in Home Assistant
            self.call_service("input_number/set_value",
                            entity_id="input_number.battery_manager_target_power",
                            value=0)
            
            # Stop all batteries
            self.battery_collection.stop_all_batteries()
            
            # Reset internal target power
            self.battery_collection._target_power = 0
            
            self.log("System reset to safe state - target power: 0W, all batteries stopped")
            
        except Exception as e:
            self.log(f"Error resetting to safe state: {e}", level="ERROR")
    
    def _ensure_clean_startup_state(self):
        """Ensure clean state after restart"""
        self.log("Ensuring clean startup state...")
        self._reset_to_safe_state()
        self.log("Clean startup state ensured")