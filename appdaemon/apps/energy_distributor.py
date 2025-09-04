import appdaemon.plugins.hass.hassapi as hass
import datetime

class EnergyDistributor(hass.Hass):
    """
    AppDaemon app to track energy distribution between grid and PV for individual devices.
    
    This app monitors power-consuming devices and calculates how much energy each device
    is drawing from the grid versus from PV production. It creates and updates sensors
    for each tracked device showing both instantaneous power consumption and cumulative
    energy usage from each source.
    """
    
    def initialize(self):
        """Initialize the app and set up listeners."""
        self.log("Initializing Energy Distributor")
        
        # Configuration
        self.update_interval = self.args.get("update_interval", 60)
        self.min_consumption_threshold = self.args.get("min_consumption_threshold", 10)
        
        # Main sensors
        self.grid_power_sensor = self.args["grid_power_sensor"]
        self.pv_power_sensor = self.args["pv_power_sensor"]
        
        # Devices to track
        self.devices = self.args["devices"]
        
        # Initialize device-specific sensors
        self._initialize_sensors()
        
        # Register service for resetting counters
        self.register_service("energy_distributor/reset_counters", self._reset_counters_service)
        
        # Set up regular updates
        self.run_every(self._update_energy_distribution, 
                      "now", 
                      self.update_interval)
        
        self.log("Energy Distributor initialized")
    
    def _initialize_sensors(self):
        """Initialize sensors for each tracked device."""
        for device_id, device_config in self.devices.items():
            friendly_name = device_config.get("friendly_name", device_id)
            
            # Create power sensors (real-time)
            self._create_sensor(f"{device_id}_grid_power", 
                               f"{friendly_name} Grid Power", 
                               "W", 
                               "power",
                               "measurement")
            self._create_sensor(f"{device_id}_pv_power", 
                               f"{friendly_name} PV Power", 
                               "W", 
                               "power",
                               "measurement")
            
            # Create energy sensors (cumulative)
            self._create_sensor(f"{device_id}_grid_energy", 
                               f"{friendly_name} Grid Energy", 
                               "kWh", 
                               "energy",
                               "total_increasing")
            self._create_sensor(f"{device_id}_pv_energy", 
                               f"{friendly_name} PV Energy", 
                               "kWh", 
                               "energy",
                               "total_increasing")
    
    def _create_sensor(self, entity_id, friendly_name, unit, device_class, state_class):
        """Create a sensor if it doesn't exist."""
        full_entity_id = f"sensor.{entity_id}"
        if not self.entity_exists(full_entity_id):
            self.set_state(full_entity_id, 
                          state="0", 
                          attributes={
                              "friendly_name": friendly_name,
                              "unit_of_measurement": unit,
                              "device_class": device_class,
                              "state_class": state_class
                          })
    
    def _update_energy_distribution(self, kwargs):
        """Update energy distribution for all tracked devices."""
        # Get current values
        try:
            grid_power = float(self.get_state(self.grid_power_sensor) or 0)
            pv_power = float(self.get_state(self.pv_power_sensor) or 0)
        except (ValueError, TypeError):
            self.log("Invalid readings from main sensors, skipping update")
            return
        
        # Calculate total house consumption
        total_consumption = pv_power + grid_power  # If grid_power is negative (export), this works correctly
        
        # Handle edge cases
        if total_consumption < self.min_consumption_threshold:
            self.log(f"Total consumption too low ({total_consumption}W), skipping update")
            return
        
        # Determine energy source distribution
        if grid_power <= 0 or pv_power >= total_consumption:
            # If exporting to grid or PV covers all consumption, everything is from PV
            pv_coverage_ratio = 1.0
            grid_coverage_ratio = 0.0
        else:
            # Calculate normal distribution
            pv_coverage_ratio = min(1.0, max(0.0, pv_power / total_consumption))
            grid_coverage_ratio = 1.0 - pv_coverage_ratio
        
        self.log(f"Current distribution - Grid: {grid_coverage_ratio:.2%}, PV: {pv_coverage_ratio:.2%}")
        
        # Update each device
        for device_id, device_config in self.devices.items():
            self._update_device_energy(device_id, device_config, pv_coverage_ratio, grid_coverage_ratio)
    
    def _update_device_energy(self, device_id, device_config, pv_ratio, grid_ratio):
        """Update energy distribution for a specific device."""
        power_sensor = device_config["power_sensor"]
        
        try:
            device_power = float(self.get_state(power_sensor) or 0)
        except (ValueError, TypeError):
            self.log(f"Invalid power reading for {device_id}, skipping update")
            device_power = 0
        
        if device_power <= 0:
            # Device is not consuming power
            grid_power = 0
            pv_power = 0
        else:
            # Calculate power from each source
            grid_power = device_power * grid_ratio
            pv_power = device_power * pv_ratio
        
        # Update power sensors
        self.set_state(f"sensor.{device_id}_grid_power", state=str(round(grid_power, 2)))
        self.set_state(f"sensor.{device_id}_pv_power", state=str(round(pv_power, 2)))
        
        # Update energy counters (kWh)
        self._update_energy_counter(device_id, "grid", grid_power)
        self._update_energy_counter(device_id, "pv", pv_power)
    
    def _update_energy_counter(self, device_id, source, power):
        """Update cumulative energy counter for a device and source."""
        entity_id = f"sensor.{device_id}_{source}_energy"
        
        try:
            current_kwh = float(self.get_state(entity_id) or 0)
        except (ValueError, TypeError):
            self.log(f"Invalid energy reading for {entity_id}, resetting to 0")
            current_kwh = 0
        
        # Convert W to kWh for the interval
        kwh_increment = (power / 1000) * (self.update_interval / 3600)
        new_kwh = current_kwh + kwh_increment
        
        self.set_state(entity_id, state=str(round(new_kwh, 4)))
    
    def _reset_counters_service(self, service):
        """Service to reset energy counters."""
        device_id = service.data.get("device_id", None)
        
        if device_id is not None:
            # Reset counters for a specific device
            if device_id in self.devices:
                self._reset_device_counters(device_id)
                self.log(f"Reset energy counters for {device_id}")
            else:
                self.log(f"Device {device_id} not found")
        else:
            # Reset all counters
            for device_id in self.devices:
                self._reset_device_counters(device_id)
            self.log("Reset all energy counters")
    
    def _reset_device_counters(self, device_id):
        """Reset energy counters for a specific device."""
        self.set_state(f"sensor.{device_id}_grid_energy", state="0")
        self.set_state(f"sensor.{device_id}_pv_energy", state="0")