"""
Battery Energy Savings Tracker - AppDaemon App

Tracks battery energy flows and calculates financial savings by:
1. Using energy distributor's PV/Grid split for battery charging
2. Tracking discharge savings with Tibber pricing
3. Creating cumulative sensors that survive app restarts

Pricing:
- PV surplus charging cost: -7.8ct/kWh (opportunity cost - reduces total savings)
- Grid import charging cost: -Tibber current price
- Battery discharge savings: +Tibber current price
"""

import appdaemon.plugins.hass.hassapi as hass
import datetime
from typing import Optional, Dict, Any


class BatterySavingsTracker(hass.Hass):
    """Track battery energy savings using energy distributor data"""
    
    # Constants
    CT_TO_EUR_FACTOR = 100
    DEFAULT_UPDATE_INTERVAL = 300  # 5 minutes
    DEFAULT_PV_SURPLUS_RATE = 7.8  # ct/kWh
    
    def initialize(self):
        """Initialize the Battery Savings Tracker"""
        self._do_initialize()
    
    def _do_initialize(self):
        """Main initialization logic"""
        self.log("Initializing Battery Savings Tracker...")
        
        # Configuration
        self.update_interval = self.args.get('update_interval', self.DEFAULT_UPDATE_INTERVAL)
        self.pv_surplus_rate_ct = self.args.get('pv_surplus_rate_ct', self.DEFAULT_PV_SURPLUS_RATE)
        
        # Input sensor configuration (with defaults)
        self.battery_pv_energy_sensor = self.args.get('battery_pv_energy_sensor', 'sensor.battery_combined_pv_energy')
        self.battery_grid_energy_sensor = self.args.get('battery_grid_energy_sensor', 'sensor.battery_combined_grid_energy')
        self.battery_discharge_sensor = self.args.get('battery_discharge_sensor', 'sensor.combined_battery_total_discharging_kwh')
        self.tibber_price_sensor = self.args.get('tibber_price_sensor', 'sensor.tibber_future_statistics')
        
        # Counter reset handling modes (clearer names)
        self.pv_reset_mode = self.args.get('pv_counter_reset_mode', 'ignore_reset')
        self.grid_reset_mode = self.args.get('grid_counter_reset_mode', 'ignore_reset')
        self.discharge_reset_mode = self.args.get('discharge_counter_reset_mode', 'ignore_reset')
        
        # Define sensor mappings
        self._define_sensors()
        
        # Initialize all sensors
        self._create_tracking_sensors()
        
        # Schedule periodic updates
        self.run_every(self._update_savings, "now", self.update_interval)
        
        self.log(f"Battery Savings Tracker initialized - update interval: {self.update_interval}s")
    
    def _define_sensors(self):
        """Define all sensor entity IDs"""
        # Input sensors (configurable)
        self.BATTERY_PV_ENERGY_SENSOR = self.battery_pv_energy_sensor
        self.BATTERY_GRID_ENERGY_SENSOR = self.battery_grid_energy_sensor
        self.COMBINED_DISCHARGING_SENSOR = self.battery_discharge_sensor
        self.TIBBER_PRICE_SENSOR = self.tibber_price_sensor
        
        # State management sensors (created by this app)
        self.LAST_RUN_SENSOR = "sensor.battery_savings_last_run_timestamp"
        self.LAST_PV_KWH_SENSOR = "sensor.battery_savings_last_pv_kwh"
        self.LAST_GRID_KWH_SENSOR = "sensor.battery_savings_last_grid_kwh"
        self.LAST_DISCHARGE_KWH_SENSOR = "sensor.battery_savings_last_discharge_kwh"
        
        # Cumulative tracking sensors (created by this app)
        self.TOTAL_SAVINGS_SENSOR = "sensor.battery_total_money_saved_eur"
        self.PV_CHARGING_COST_SENSOR = "sensor.battery_pv_charging_cost_eur"
        self.GRID_CHARGING_COST_SENSOR = "sensor.battery_grid_charging_cost_eur"
        self.DISCHARGE_SAVINGS_SENSOR = "sensor.battery_discharge_savings_eur"
        
        # Time-based savings tracking sensors (created by this app)
        self.DAILY_SAVINGS_SENSOR = "sensor.battery_daily_money_saved_eur"
        self.WEEKLY_SAVINGS_SENSOR = "sensor.battery_weekly_money_saved_eur"
        self.MONTHLY_SAVINGS_SENSOR = "sensor.battery_monthly_money_saved_eur"
        self.YEARLY_SAVINGS_SENSOR = "sensor.battery_yearly_money_saved_eur"
        
        # Single reset tracking sensor (created by this app)
        self.LAST_RESET_DATE_SENSOR = "sensor.battery_savings_last_reset_date"
    
    def _create_tracking_sensors(self):
        """Create all tracking sensors with initial values"""
        # State management sensors
        state_sensors = {
            self.LAST_RUN_SENSOR: ("Battery Savings Last Run", "mdi:clock-outline", "timestamp"),
            self.LAST_PV_KWH_SENSOR: ("Battery Savings Last PV kWh", "mdi:solar-power", "energy"),
            self.LAST_GRID_KWH_SENSOR: ("Battery Savings Last Grid kWh", "mdi:transmission-tower", "energy"),
            self.LAST_DISCHARGE_KWH_SENSOR: ("Battery Savings Last Discharge kWh", "mdi:battery-arrow-down", "energy")
        }
        
        # Cumulative tracking sensors
        cumulative_sensors = {
            self.TOTAL_SAVINGS_SENSOR: ("Battery Total Money Saved", "mdi:currency-eur", "total"),
            self.PV_CHARGING_COST_SENSOR: ("Battery PV Charging Cost", "mdi:solar-power", "total"),
            self.GRID_CHARGING_COST_SENSOR: ("Battery Grid Charging Cost", "mdi:transmission-tower", "total"),
            self.DISCHARGE_SAVINGS_SENSOR: ("Battery Discharge Savings", "mdi:battery-arrow-down", "total_increasing")
        }
        
        # Time-based savings sensors
        time_based_sensors = {
            self.DAILY_SAVINGS_SENSOR: ("Battery Daily Money Saved", "mdi:calendar-today", "total"),
            self.WEEKLY_SAVINGS_SENSOR: ("Battery Weekly Money Saved", "mdi:calendar-week", "total"),
            self.MONTHLY_SAVINGS_SENSOR: ("Battery Monthly Money Saved", "mdi:calendar-month", "total"),
            self.YEARLY_SAVINGS_SENSOR: ("Battery Yearly Money Saved", "mdi:calendar", "total")
        }
        
        # Reset tracking sensor
        reset_sensor = {
            self.LAST_RESET_DATE_SENSOR: ("Battery Savings Last Reset Date", "mdi:calendar-clock", "timestamp")
        }
        
        # Create state management sensors
        for sensor_id, (friendly_name, icon, device_class) in state_sensors.items():
            unit = "kWh" if device_class == "energy" else None
            self._create_sensor(sensor_id, "0", friendly_name, icon, device_class, unit)
        
        # Create cumulative sensors
        for sensor_id, (friendly_name, icon, state_class) in cumulative_sensors.items():
            self._create_sensor(sensor_id, "0", friendly_name, icon, "monetary", "€", state_class)
        
        # Create time-based savings sensors
        for sensor_id, (friendly_name, icon, state_class) in time_based_sensors.items():
            self._create_sensor(sensor_id, "0", friendly_name, icon, "monetary", "€", state_class)
        
        # Create reset tracking sensor
        for sensor_id, (friendly_name, icon, device_class) in reset_sensor.items():
            self._create_sensor(sensor_id, "0", friendly_name, icon, device_class)
        
        # Initialize time-based tracking
        self._initialize_time_based_tracking()
    
    def _create_sensor(self, sensor_id: str, initial_state: str, friendly_name: str,
                      icon: str, device_class: str, unit: str = None, state_class: str = None):
        """Create a single sensor if it doesn't exist"""
        if not self.entity_exists(sensor_id):
            attributes = {
                "friendly_name": friendly_name,
                "icon": icon,
                "device_class": device_class
            }
            if unit:
                attributes["unit_of_measurement"] = unit
            if state_class:
                attributes["state_class"] = state_class
                
            self.set_state(sensor_id, state=initial_state, attributes=attributes)
            self.log(f"Created sensor: {sensor_id}")
    
    
    def _update_savings(self, kwargs):
        """Main update method - called every 5 minutes"""
        try:
            self._do_update_savings()
        except Exception as e:
            self.log(f"Error in savings update: {e}", level="ERROR")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}", level="ERROR")
    
    def _do_update_savings(self):
        """Main update logic"""
        self.log("Starting savings update...")
        
        # Check for time-based resets first
        self._check_and_handle_time_resets()
        
        # Get current energy values
        current_values = self._get_current_energy_values()
        if not current_values:
            self.log("Could not get all current energy values, skipping update", level="WARNING")
            return
        
        current_pv_kwh, current_grid_kwh, current_discharge_kwh = current_values
        
        # Get last known values
        last_values = self._get_last_energy_values()
        last_pv_kwh, last_grid_kwh, last_discharge_kwh = last_values
        
        # Calculate changes (with reset handling)
        deltas_and_updates = self._calculate_energy_deltas_with_updates(current_values, last_values)
        pv_delta, grid_delta, discharge_delta, should_update_pv, should_update_grid, should_update_discharge = deltas_and_updates
        
        self.log(f"Energy deltas - PV: {pv_delta:.3f} kWh, Grid: {grid_delta:.3f} kWh, Discharge: {discharge_delta:.3f} kWh")
        
        # Process energy changes
        if pv_delta > 0 or grid_delta > 0:
            self._process_charging(pv_delta, grid_delta)
        
        if discharge_delta > 0:
            self._process_discharging(discharge_delta)
        
        # Update state sensors (only if not ignoring resets)
        self._update_state_sensors_conditionally(current_pv_kwh, current_grid_kwh, current_discharge_kwh,
                                                should_update_pv, should_update_grid, should_update_discharge)
        
        self.log("Savings update completed successfully")
    
    def _get_current_energy_values(self) -> Optional[tuple]:
        """Get current energy values from sensors"""
        current_pv_kwh = self._get_sensor_value(self.BATTERY_PV_ENERGY_SENSOR)
        current_grid_kwh = self._get_sensor_value(self.BATTERY_GRID_ENERGY_SENSOR)
        current_discharge_kwh = self._get_sensor_value(self.COMBINED_DISCHARGING_SENSOR)
        
        if None in [current_pv_kwh, current_grid_kwh, current_discharge_kwh]:
            return None
        
        return (current_pv_kwh, current_grid_kwh, current_discharge_kwh)
    
    def _get_last_energy_values(self) -> tuple:
        """Get last known energy values"""
        last_pv_kwh = self._get_sensor_value(self.LAST_PV_KWH_SENSOR, default=0)
        last_grid_kwh = self._get_sensor_value(self.LAST_GRID_KWH_SENSOR, default=0)
        last_discharge_kwh = self._get_sensor_value(self.LAST_DISCHARGE_KWH_SENSOR, default=0)
        
        return (last_pv_kwh, last_grid_kwh, last_discharge_kwh)
    
    def _calculate_energy_deltas_with_updates(self, current_values: tuple, last_values: tuple) -> tuple:
        """Calculate energy deltas with reset handling and determine which sensors to update"""
        current_pv, current_grid, current_discharge = current_values
        last_pv, last_grid, last_discharge = last_values
        
        pv_result = self._handle_counter_reset_with_update_flag(current_pv, last_pv, "PV charging", self.pv_reset_mode)
        grid_result = self._handle_counter_reset_with_update_flag(current_grid, last_grid, "Grid charging", self.grid_reset_mode)
        discharge_result = self._handle_counter_reset_with_update_flag(current_discharge, last_discharge, "discharging", self.discharge_reset_mode)
        
        pv_delta, should_update_pv = pv_result
        grid_delta, should_update_grid = grid_result
        discharge_delta, should_update_discharge = discharge_result
        
        return (pv_delta, grid_delta, discharge_delta, should_update_pv, should_update_grid, should_update_discharge)
    
    def _get_sensor_value(self, sensor_id: str, default=None) -> Optional[float]:
        """Get sensor value as float"""
        try:
            state = self.get_state(sensor_id)
            return float(state) if state is not None else default
        except (ValueError, TypeError):
            self.log(f"Invalid state for {sensor_id}", level="WARNING")
            return default
    
    def _handle_counter_reset_with_update_flag(self, current: float, last: float, sensor_name: str, reset_mode: str = "ignore_reset") -> tuple:
        """
        Handle counter resets with different strategies and return update flag
        
        Args:
            current: Current sensor value
            last: Last known sensor value
            sensor_name: Name for logging
            reset_mode: How to handle resets:
                - "ignore_reset": Ignore resets completely, return 0 delta and don't update last value
                - "continue_from_reset": Start tracking from reset value as new delta
                - "daily_counter": Treat reset value as actual energy delta (for daily counters)
            
        Returns:
            Tuple of (energy_delta, should_update_last_sensor)
        """
        if current < last:
            self.log(f"Counter reset detected for {sensor_name}: {last} -> {current}", level="WARNING")
            
            if reset_mode == "ignore_reset":
                # Ignore the reset completely - return 0 delta and DON'T update last sensor
                self.log(f"Ignoring reset for {sensor_name}, waiting for recovery", level="INFO")
                return (0.0, False)
            elif reset_mode == "continue_from_reset":
                # Start tracking from the reset value - return current value as delta
                self.log(f"Continuing from reset value for {sensor_name}: using {current} kWh as delta", level="INFO")
                return (current, True)
            elif reset_mode == "daily_counter":
                # Treat reset value as the actual energy delta (for daily counters that reset at midnight)
                self.log(f"Preserving delta for {sensor_name}: estimated {current} kWh since reset", level="INFO")
                return (current, True)
            else:
                self.log(f"Unknown reset mode '{reset_mode}' for {sensor_name}, defaulting to ignore_reset", level="WARNING")
                return (0.0, False)
        
        return (current - last, True)
    
    def _process_charging(self, pv_delta: float, grid_delta: float):
        """Process battery charging and calculate costs"""
        if pv_delta <= 0 and grid_delta <= 0:
            return
            
        # Get current Tibber price
        tibber_price_ct = self._get_tibber_price_ct()
        if tibber_price_ct is None:
            self.log("Could not get Tibber price, skipping charging cost calculation", level="WARNING")
            return
        
        # Calculate costs (negative values = costs)
        costs = self._calculate_charging_costs(pv_delta, grid_delta, tibber_price_ct)
        pv_cost_eur, grid_cost_eur = costs
        
        # Update cumulative sensors
        if pv_cost_eur != 0:
            self._add_to_cumulative_sensor(self.PV_CHARGING_COST_SENSOR, pv_cost_eur)
        if grid_cost_eur != 0:
            self._add_to_cumulative_sensor(self.GRID_CHARGING_COST_SENSOR, grid_cost_eur)
        
        # Update total savings
        self._update_total_savings()
        
        # Update time-based savings
        total_cost = pv_cost_eur + grid_cost_eur
        if total_cost != 0:
            self._update_time_based_savings(total_cost)
    
    def _calculate_charging_costs(self, pv_delta: float, grid_delta: float, tibber_price_ct: float) -> tuple:
        """Calculate PV and grid charging costs"""
        pv_cost_eur = 0
        grid_cost_eur = 0
        
        if pv_delta > 0:
            # Use the correct PV surplus rate from configuration
            pv_cost_eur = (pv_delta * (-self.pv_surplus_rate_ct)) / self.CT_TO_EUR_FACTOR
            self.log(f"PV charging cost: {pv_delta:.3f} kWh * {-self.pv_surplus_rate_ct}ct = {pv_cost_eur:.6f}€")
        
        if grid_delta > 0:
            grid_cost_eur = (grid_delta * (-tibber_price_ct)) / self.CT_TO_EUR_FACTOR  # Negative because it's a cost
            self.log(f"Grid charging cost: {grid_delta:.3f} kWh * {-tibber_price_ct}ct = {grid_cost_eur:.6f}€")
        
        return (pv_cost_eur, grid_cost_eur)
    
    def _process_discharging(self, discharge_delta: float):
        """Process battery discharging and calculate savings"""
        if discharge_delta <= 0:
            return
            
        # Get current Tibber price
        tibber_price_ct = self._get_tibber_price_ct()
        if tibber_price_ct is None:
            self.log("Could not get Tibber price, skipping discharge savings calculation", level="WARNING")
            return
        
        # Calculate savings (positive value)
        discharge_savings_eur = (discharge_delta * tibber_price_ct) / self.CT_TO_EUR_FACTOR
        self.log(f"Discharge savings: {discharge_delta:.3f} kWh * {tibber_price_ct}ct = {discharge_savings_eur:.6f}€")
        
        # Update cumulative sensors
        self._add_to_cumulative_sensor(self.DISCHARGE_SAVINGS_SENSOR, discharge_savings_eur)
        
        # Update total savings
        self._update_total_savings()
        
        # Update time-based savings
        self._update_time_based_savings(discharge_savings_eur)
    
    def _get_tibber_price_ct(self) -> Optional[float]:
        """Get current Tibber price in ct/kWh"""
        try:
            # Get price from configurable Tibber sensor (in EUR/kWh)
            price_eur = self.get_state(self.TIBBER_PRICE_SENSOR, attribute="current_price")
            if price_eur is not None:
                return float(price_eur) * self.CT_TO_EUR_FACTOR  # Convert EUR/kWh to ct/kWh
            return None
        except (ValueError, TypeError):
            self.log("Error getting Tibber price", level="WARNING")
            return None
    
    def _add_to_cumulative_sensor(self, sensor_id: str, value: float):
        """Add value to cumulative sensor"""
        try:
            current_value = self._get_sensor_value(sensor_id, default=0)
            new_value = current_value + value
            
            self.set_state(sensor_id,
                          state=round(new_value, 6),
                          attributes=self.get_state(sensor_id, attribute="all")["attributes"])
            
            self.log(f"Updated {sensor_id}: {current_value:.6f} + {value:.6f} = {new_value:.6f}€")
        except Exception as e:
            self.log(f"Error updating cumulative sensor {sensor_id}: {e}", level="ERROR")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}", level="ERROR")
    
    def _update_total_savings(self):
        """Update total savings sensor"""
        try:
            # Get all cost/savings components
            savings_components = {
                "PV cost": self._get_sensor_value(self.PV_CHARGING_COST_SENSOR, default=0),
                "Grid cost": self._get_sensor_value(self.GRID_CHARGING_COST_SENSOR, default=0),
                "Discharge savings": self._get_sensor_value(self.DISCHARGE_SAVINGS_SENSOR, default=0)
            }
            
            # Total savings = discharge savings + charging costs (costs are negative)
            total_savings = sum(savings_components.values())
            
            self.set_state(self.TOTAL_SAVINGS_SENSOR,
                          state=round(total_savings, 6),
                          attributes=self.get_state(self.TOTAL_SAVINGS_SENSOR, attribute="all")["attributes"])
            
            # Create readable log message
            components_str = " + ".join([f"{v:.6f}" for v in savings_components.values()])
            self.log(f"Total savings updated: {components_str} = {total_savings:.6f}€")
        except Exception as e:
            self.log(f"Error updating total savings: {e}", level="ERROR")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}", level="ERROR")
    
    def _update_state_sensors_conditionally(self, pv_kwh: float, grid_kwh: float, discharge_kwh: float,
                                           should_update_pv: bool, should_update_grid: bool, should_update_discharge: bool):
        """Update state management sensors conditionally based on reset handling"""
        try:
            timestamp = self.datetime().isoformat()
            
            # Always update timestamp
            self.set_state(self.LAST_RUN_SENSOR, state=timestamp)
            
            # Conditionally update energy sensors (don't update if we're ignoring a reset)
            if should_update_pv:
                self.set_state(self.LAST_PV_KWH_SENSOR, state=str(round(pv_kwh, 6)))
            
            if should_update_grid:
                self.set_state(self.LAST_GRID_KWH_SENSOR, state=str(round(grid_kwh, 6)))
            
            if should_update_discharge:
                self.set_state(self.LAST_DISCHARGE_KWH_SENSOR, state=str(round(discharge_kwh, 6)))
                
        except Exception as e:
            self.log(f"Error updating state sensors: {e}", level="ERROR")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}", level="ERROR")
    
    def _initialize_time_based_tracking(self):
        """Initialize time-based tracking with current date"""
        now = self.datetime()
        current_date = now.strftime("%Y-%m-%d")
        
        # Initialize reset date if it doesn't exist
        current_state = self.get_state(self.LAST_RESET_DATE_SENSOR)
        if current_state is None or current_state == "0":
            self.set_state(self.LAST_RESET_DATE_SENSOR, state=current_date)
            self.log(f"Initialized {self.LAST_RESET_DATE_SENSOR} with {current_date}")
    
    def _check_and_handle_time_resets(self):
        """Check if we need to reset time-based sensors for new periods"""
        now = self.datetime()
        current_date = now.strftime("%Y-%m-%d")
        
        # Get last reset date
        last_reset_date_str = self.get_state(self.LAST_RESET_DATE_SENSOR)
        if not last_reset_date_str or last_reset_date_str == "0":
            # First run, initialize and return
            self.set_state(self.LAST_RESET_DATE_SENSOR, state=current_date)
            return
        
        try:
            last_reset_date = datetime.datetime.strptime(last_reset_date_str, "%Y-%m-%d")
            current_datetime = datetime.datetime.strptime(current_date, "%Y-%m-%d")
        except ValueError:
            self.log(f"Invalid date format in reset sensor: {last_reset_date_str}", level="WARNING")
            self.set_state(self.LAST_RESET_DATE_SENSOR, state=current_date)
            return
        
        # Check if we need to reset any periods
        if current_datetime > last_reset_date:
            self._process_period_resets(last_reset_date, current_datetime)
            # Update the reset date
            self.set_state(self.LAST_RESET_DATE_SENSOR, state=current_date)
    
    def _process_period_resets(self, last_date: datetime.datetime, current_date: datetime.datetime):
        """Process all applicable period resets based on date change"""
        
        # Always reset daily if date changed
        self._reset_time_based_sensor(self.DAILY_SAVINGS_SENSOR, "daily")
        self.log(f"Daily savings reset for new day: {current_date.strftime('%Y-%m-%d')}")
        
        # Check weekly reset (Monday = start of week)
        last_week_start = self._get_week_start_date(last_date)
        current_week_start = self._get_week_start_date(current_date)
        if current_week_start > last_week_start:
            self._reset_time_based_sensor(self.WEEKLY_SAVINGS_SENSOR, "weekly")
            self.log(f"Weekly savings reset for new week starting: {current_week_start.strftime('%Y-%m-%d')}")
        
        # Check monthly reset
        if current_date.month != last_date.month or current_date.year != last_date.year:
            self._reset_time_based_sensor(self.MONTHLY_SAVINGS_SENSOR, "monthly")
            self.log(f"Monthly savings reset for new month: {current_date.strftime('%Y-%m')}")
        
        # Check yearly reset
        if current_date.year != last_date.year:
            self._reset_time_based_sensor(self.YEARLY_SAVINGS_SENSOR, "yearly")
            self.log(f"Yearly savings reset for new year: {current_date.year}")
    
    def _get_week_start_date(self, date: datetime.datetime) -> datetime.datetime:
        """Get the start date of the week (Monday) for the given date"""
        days_since_monday = date.weekday()
        week_start = date - datetime.timedelta(days=days_since_monday)
        return week_start
    
    def _reset_time_based_sensor(self, sensor_id: str, period_name: str):
        """Reset a time-based sensor to 0"""
        self.set_state(sensor_id,
                      state="0",
                      attributes=self.get_state(sensor_id, attribute="all")["attributes"])
        self.log(f"Reset {period_name} savings sensor {sensor_id} to 0")
    
    def _update_time_based_savings(self, savings_amount: float):
        """Update daily, weekly, monthly, and yearly savings sensors"""
        time_sensors = [
            (self.DAILY_SAVINGS_SENSOR, "daily"),
            (self.WEEKLY_SAVINGS_SENSOR, "weekly"),
            (self.MONTHLY_SAVINGS_SENSOR, "monthly"),
            (self.YEARLY_SAVINGS_SENSOR, "yearly")
        ]
        
        for sensor_id, period_name in time_sensors:
            self._add_to_time_based_sensor(sensor_id, savings_amount, period_name)
    
    def _add_to_time_based_sensor(self, sensor_id: str, value: float, period_name: str):
        """Add value to time-based sensor"""
        try:
            current_value = self._get_sensor_value(sensor_id, default=0)
            new_value = current_value + value
            
            self.set_state(sensor_id,
                          state=round(new_value, 6),
                          attributes=self.get_state(sensor_id, attribute="all")["attributes"])
            
            self.log(f"Updated {period_name} savings: {current_value:.6f} + {value:.6f} = {new_value:.6f}€")
        except Exception as e:
            self.log(f"Error updating {period_name} savings sensor {sensor_id}: {e}", level="ERROR")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}", level="ERROR")