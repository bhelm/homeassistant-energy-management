"""
Main WallboxManager class for coordinating wallbox charging operations.

This module provides the main WallboxManager class that coordinates all
wallbox charging operations based on available grid power.
"""

import appdaemon.plugins.hass.hassapi as hass
import time
import sys
import os

# Add the wallbox_manager directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from wallbox import Wallbox
from wallbox_collection import WallboxCollection, WALLBOX_CONFIGS
from power_converter import PowerConverter



class WallboxManager(hass.Hass):
    """
    AppDaemon app to manage charging of multiple wallboxes
    based on available power from the grid.
    
    This app monitors the grid power sensor and adjusts the charging current
    for wallboxes based on available surplus power, distributing it according
    to configurable priorities.
    
    The app creates a virtual boolean sensor called 'wallbox_power_required' that indicates
    whether any wallbox is currently requiring power. This sensor is:
    - ON when at least one wallbox is enabled, connected, and either charging or ready to charge
    - OFF when no wallbox is requiring power (all disabled, none connected, or all failed)
    
    This sensor can be used by other systems to determine if they can use surplus power freely.
    """
    
    def initialize(self):
        """Initialize the app and set up listeners."""
        self.log("Initializing Wallbox Manager")
        
        # Apply ratio from configuration to wallbox priorities if specified
        ratio_dani_to_elli = float(self.args.get("ratio_dani_to_elli", 2.0))
        
        # Update wallbox configs with custom ratio if provided
        configs = WALLBOX_CONFIGS.copy()
        for config in configs:
            if config['name'] == 'dani':
                config['priority'] = ratio_dani_to_elli
            elif config['name'] == 'elli':
                config['priority'] = 1.0
        
        # Constants
        voltage = float(self.args.get("voltage", 233.33))
        sqrt_3 = float(self.args.get("sqrt_3", 1.0))  # Default: 1.0 for single-phase
        self.min_current_a = float(self.args.get("min_current_a", 6))
        self.max_current_a = float(self.args.get("max_current_a", 32))
        self.buffer_watts = float(self.args.get("buffer_watts", 100))
        
        # Battery power integration configuration
        self.battery_power_sensor = self.args.get("battery_power_sensor", "sensor.battery_manager_actual_power")
        
        # Configuration for gradual adjustment
        max_power_change_per_cycle = float(self.args.get("max_power_change_per_cycle", 500))  # Watts
        self.timer_interval = int(self.args.get("timer_interval", 10))  # Seconds
        
        # Configuration for charging attempts
        self.max_attempts = int(self.args.get("max_charging_attempts", 3))
        self.retry_interval = int(self.args.get("charging_retry_interval", 300))  # 5 minutes
        self.power_threshold = float(self.args.get("charging_power_threshold", 100))  # 100W
        
        # Create clean utility classes
        self.power_converter = PowerConverter(voltage=voltage, sqrt_3=sqrt_3)
        
        # Create wallbox collection
        self.wallbox_collection = WallboxCollection(configs, self)
        
        # Keep backward compatibility reference for existing code
        self.wallboxes = self.wallbox_collection.wallboxes
        
        # Create the wallbox_power_required sensor
        self.set_state("binary_sensor.wallbox_power_required",
                      state="off",
                      attributes={
                          "friendly_name": "Wallbox Power Required",
                          "device_class": "power",
                          "icon": "mdi:ev-station"
                      })
        
        # Set up timer for gradual power adjustments (every 10 seconds)
        self.run_every(self.manage_wallboxes_timer, "now+10", self.timer_interval)
        
        # Set up listeners for charging state changes using collection
        for name in self.wallbox_collection.get_wallbox_names():
            wallbox = self.wallbox_collection.get_wallbox(name)
            self.listen_state(wallbox.on_charging_change, wallbox.get_entity_id("charging"))
        
        # Run once at startup
        self.run_in(self.initial_run, 10)
        
        self.log("Wallbox Manager initialized with clean architecture")
    
    def initial_run(self, kwargs):
        """Run the wallbox management logic once at startup."""
        self.manage_wallboxes(None, None, None, None, None)
        
    def manage_wallboxes_timer(self, kwargs):
        """Timer-based wrapper for manage_wallboxes - called every 10 seconds."""
        self.manage_wallboxes(None, None, None, None, None)
    
    def manage_wallboxes_wrapper(self, kwargs):
        """Wrapper for manage_wallboxes to be used with run_in."""
        self.manage_wallboxes(None, None, None, None, None)
    
    def calculate_min_power_for_wallbox(self):
        """
        Calculate the minimum power needed for a wallbox to operate.
        
        Returns:
            float: Minimum power in watts
        """
        return self.power_converter.min_power_for_current(self.min_current_a)
    
    def calculate_adjusted_surplus(self, surplus_watts):
        """
        Calculate the adjusted surplus power after applying the buffer.
        
        Args:
            surplus_watts (float): Raw surplus power in watts
            
        Returns:
            float: Adjusted surplus power in watts
        """
        return surplus_watts - self.buffer_watts
    
    def calculate_target_current(self, wallbox_name, power_watts, wallbox_state):
        """
        Calculate the target current based on power allocation and wallbox state.
        This handles all decision logic: stops, min/max limits, failed wallboxes.
        
        Args:
            wallbox_name (str): Name of the wallbox
            power_watts (float): Allocated power in watts
            wallbox_state (dict): Current wallbox state
            
        Returns:
            tuple: (target_current, should_start_charging)
        """
        # Handle failed wallboxes
        if wallbox_state.get("failed", False):
            self.log(f"DECISION: {wallbox_name.capitalize()} is failed - setting to minimum current without starting")
            return (self.min_current_a, False)
        
        # Convert power to current
        target_amps = self.power_converter.to_amps(power_watts)
        
        # Handle insufficient power (stop charging)
        if target_amps < 0:
            self.log(f"DECISION: {wallbox_name.capitalize()} insufficient power ({power_watts:.1f}W, {target_amps:.2f}A) - stopping")
            return (0, False)  # Stop charging
        
        # Handle below minimum current (stop charging)
        if target_amps > 0 and target_amps < self.min_current_a:
            self.log(f"DECISION: {wallbox_name.capitalize()} target {target_amps:.2f}A below minimum {self.min_current_a}A - stopping")
            return (0, False)  # Stop if below minimum viable current
            
        # Only clamp to operating range if we have sufficient power
        if target_amps >= self.min_current_a:
            target_amps = min(target_amps, self.max_current_a)
            self.log(f"DECISION: {wallbox_name.capitalize()} target current: {target_amps:.2f}A from {power_watts:.1f}W")
            return (target_amps, True)
        
        # This should never be reached, but safety fallback
        self.log(f"DECISION: {wallbox_name.capitalize()} unexpected case - stopping")
        return (0, False)
    
    def is_enough_power_for_both(self, total_power):
        """
        Check if there's enough power for both wallboxes to operate.
        
        Args:
            total_power (float): Total available power in watts
            
        Returns:
            bool: True if there's enough power for both wallboxes, False otherwise
        """
        min_watts_for_two = 2 * self.calculate_min_power_for_wallbox()
        return total_power >= min_watts_for_two
    
    def get_battery_power(self):
        """
        Get the current battery power from the configured sensor.
        
        Returns:
            float: Battery power in watts (positive = charging, negative = discharging)
                   Returns 0.0 if sensor is unavailable or invalid
        """
        try:
            battery_power_state = self.get_state(self.battery_power_sensor)
            if battery_power_state is None or battery_power_state in ['unknown', 'unavailable']:
                self.log(f"WARNING: Battery power sensor {self.battery_power_sensor} is {battery_power_state}, using 0.0W as default")
                return 0.0
            
            battery_power = float(battery_power_state)
            return battery_power
            
        except (ValueError, TypeError) as e:
            self.log(f"WARNING: Could not convert battery power state '{battery_power_state}' to float: {e}, using 0.0W as default")
            return 0.0
        except Exception as e:
            self.log(f"ERROR: Failed to read battery power sensor {self.battery_power_sensor}: {e}, using 0.0W as default")
            return 0.0
    
    def get_wallbox_states(self):
        """
        Get the current state of all wallboxes using the collection.
        
        Returns:
            dict: Dictionary containing the current state of all wallboxes and grid
        """
        # Get grid power
        grid_power_state = self.get_state("sensor.netz_gesamt_w")
        if grid_power_state is None or grid_power_state in ['unknown', 'unavailable']:
            self.log(f"WARNING: Grid power state is {grid_power_state}, using 0.0 as default")
            netz_gesamt_w = 0.0
        else:
            try:
                netz_gesamt_w = float(grid_power_state)
            except (ValueError, TypeError) as e:
                self.log(f"WARNING: Could not convert grid power state '{grid_power_state}' to float: {e}, using 0.0 as default")
                netz_gesamt_w = 0.0
        # Calculate base surplus from grid power
        base_surplus_watts = -1 * netz_gesamt_w  # Convert grid import (negative) to surplus (positive)
        
        # Get battery power and add to surplus if battery is charging (positive power)
        battery_power = self.get_battery_power()
        battery_contribution = 0.0
        
        if battery_power > 0:  # Battery is charging - add this power to available surplus
            battery_contribution = battery_power
            surplus_watts = base_surplus_watts + battery_contribution
            self.log(f"BATTERY INTEGRATION: Battery charging at {battery_power:.1f}W - adding to surplus")
        else:
            surplus_watts = base_surplus_watts
            if battery_power < 0:
                self.log(f"BATTERY INTEGRATION: Battery discharging at {abs(battery_power):.1f}W - no surplus contribution")
            else:
                self.log(f"BATTERY INTEGRATION: Battery idle (0W) - no surplus contribution")
        
        # Get wallbox states from collection
        states = self.wallbox_collection.get_all_states()
        
        # Add grid and battery information
        states["grid"] = {
            "power": netz_gesamt_w,
            "surplus": surplus_watts,
            "base_surplus": base_surplus_watts,
            "battery_power": battery_power,
            "battery_contribution": battery_contribution
        }
        
        return states
    
    def calculate_total_available_power(self, adjusted_surplus, states):
        """
        Calculate total available power based on adjusted surplus and current wallbox states.
        
        Args:
            adjusted_surplus (float): Adjusted surplus power after applying buffer
            states (dict): Current state of wallboxes
            
        Returns:
            float: Total available power in watts
        """
        total_available = adjusted_surplus
        
        # Add power from wallboxes that are actually charging and not failed (only active ones)
        for name in self.wallbox_collection.get_active_wallboxes():
            wallbox_state = states[name]
            
            if wallbox_state["charging"]:
                total_available += wallbox_state["current_power"]
                self.log(f"CALCULATION: Added {name.capitalize()}'s current power {wallbox_state['current_power']}W to available power")
            
            # Don't add phantom power for failed wallboxes that aren't actually consuming power
            # Failed wallboxes that aren't charging don't contribute to available power
        
        self.log(f"CALCULATION: Total available power = {total_available}W")
        return total_available
    
    def determine_active_wallboxes(self, states):
        """
        Determine which wallboxes are active and available for power allocation using collection.
        
        Args:
            states (dict): Current state of wallboxes (unused, collection has the data)
            
        Returns:
            tuple: (active_wallboxes, active_for_allocation, active_wallbox_names)
                active_wallboxes: Number of active wallboxes
                active_for_allocation: Number of wallboxes available for power allocation
                active_wallbox_names: List of active wallbox names
        """
        # Use collection methods instead of hardcoded logic
        active_wallbox_names = self.wallbox_collection.get_active_wallboxes()
        available_wallbox_names = self.wallbox_collection.get_available_for_allocation()
        
        active_wallboxes = len(active_wallbox_names)
        active_for_allocation = len(available_wallbox_names)
        
        self.log(f"DECISION: Found {active_wallboxes} active wallbox(es), {active_for_allocation} available for power allocation")
        self.log(f"DECISION: Active wallboxes: {active_wallbox_names}")
        self.log(f"DECISION: Available for allocation: {available_wallbox_names}")
        
        return active_wallboxes, active_for_allocation, active_wallbox_names
    
    def manage_wallboxes(self, entity, attribute, old, new, kwargs):
        """Main logic to manage wallbox charging based on grid power."""
        self.log("=========== WALLBOX MANAGER START ===========")
        
        # Get states of wallboxes
        states = self.get_wallbox_states()
        
        # Log initial state (generic)
        self.log(f"Initial state:")
        self.log(f"  Grid power: {states['grid']['power']}W (negative means export, positive means import)")
        self.log(f"  Base surplus: {states['grid']['base_surplus']}W")
        self.log(f"  Battery power: {states['grid']['battery_power']:+.1f}W ({'charging' if states['grid']['battery_power'] > 0 else 'discharging' if states['grid']['battery_power'] < 0 else 'idle'})")
        if states['grid']['battery_contribution'] > 0:
            self.log(f"  Battery contribution: +{states['grid']['battery_contribution']:.1f}W (added to surplus)")
        self.log(f"  Total surplus: {states['grid']['surplus']}W")
        
        # Log all wallbox states generically
        for name in self.wallbox_collection.get_wallbox_names():
            wallbox_state = states[name]
            priority = self.wallbox_collection.priorities[name]
            self.log(f"  {name.capitalize()}: enabled={wallbox_state['enabled']}, connected={wallbox_state['connected']}, charging={wallbox_state['charging']}, power={wallbox_state['current_power']}W, limit={wallbox_state['current_limit']}A, priority={priority}")
        
        self.log(f"Constants: Voltage={self.power_converter.voltage}V, MIN_CURRENT={self.min_current_a}A, MAX_CURRENT={self.max_current_a}A, BUFFER={self.buffer_watts}W")
        
        # Apply buffer
        adjusted_surplus = self.calculate_adjusted_surplus(states["grid"]["surplus"])
        self.log(f"CALCULATION: Adjusted surplus after {self.buffer_watts}W buffer = {adjusted_surplus}W")
        
        # Log failed wallboxes (generic)
        failed_wallboxes = self.wallbox_collection.get_failed_wallboxes()
        for name in failed_wallboxes:
            self.log(f"DECISION: {name.capitalize()} has failed to start charging")
        
        # Calculate total available power
        total_available = self.calculate_total_available_power(adjusted_surplus, states)
        
        # Determine which wallboxes are active
        active_wallboxes, active_for_allocation, active_wallbox_names = self.determine_active_wallboxes(states)
        
        # Schedule retries for failed wallboxes (generic)
        self.wallbox_collection.schedule_retry_for_failed_wallboxes()
        
        # Handle power distribution based on active wallboxes
        if active_for_allocation == 0:
            # No wallboxes available for allocation
            self.handle_no_active_wallboxes(states, active_wallboxes, active_wallbox_names)
        elif active_for_allocation == 1:
            # Only one wallbox available for allocation - use collection method
            available_wallboxes = self.wallbox_collection.get_available_for_allocation()
            if available_wallboxes:
                active_wallbox = available_wallboxes[0]  # Get the single available wallbox
                self.handle_single_active_wallbox(active_wallbox, total_available, states)
        else:
            # Multiple wallboxes available for allocation
            self.handle_multiple_active_wallboxes(total_available, states)
        
        # Update the power required sensor
        self.update_power_required_sensor(states)
        
        self.log("=========== WALLBOX MANAGER END ===========")
    
    def handle_no_active_wallboxes(self, states, active_wallboxes, active_wallbox_names):
        """
        Handle the case when no wallboxes are available for power allocation.
        
        Args:
            states (dict): Current state of wallboxes
            active_wallboxes (int): Number of active wallboxes
            active_wallbox_names (list): List of active wallbox names
        """
        if active_wallboxes == 0:
            self.log("DECISION: No wallboxes active - nothing to do")
        else:
            self.log("DECISION: All active wallboxes have failed to charge - keeping at minimum current")
            # Set minimum current for failed wallboxes
            for name in active_wallbox_names:
                if states[name]["failed"]:
                    # Use generic collection method instead of hardcoded names
                    power_allocation = {name: self.calculate_min_power_for_wallbox()}
                    self.apply_power_allocations(power_allocation, states)
    
    def handle_single_active_wallbox(self, active_wallbox, total_power, states):
        """
        Handle the case when only one wallbox is available for power allocation.
        
        Args:
            active_wallbox (str): Name of the active wallbox
            total_power (float): Total available power in watts
            states (dict): Current state of wallboxes
        """
        # Get all other wallboxes (generic approach)
        all_active = self.wallbox_collection.get_active_wallboxes()
        other_wallboxes = [name for name in all_active if name != active_wallbox]
        
        # Allocate all power to the active wallbox using generic method
        wallbox_watts = total_power
        wallbox_amps = self.power_converter.to_amps(wallbox_watts)
        self.log(f"CALCULATION: Single wallbox ({active_wallbox.capitalize()}) - allocating all {wallbox_watts}W → {wallbox_amps:.1f}A")
        
        power_allocation = {active_wallbox: wallbox_watts}
        self.apply_power_allocations(power_allocation, states)
        
        # Handle other wallboxes
        for other_wallbox in other_wallboxes:
            other_state = states[other_wallbox]
            if other_state["enabled"] and other_state["connected"] and other_state["failed"]:
                power_allocation = {other_wallbox: self.calculate_min_power_for_wallbox()}
                self.apply_power_allocations(power_allocation, states)
            elif other_state["charging"] and not other_state["failed"] and other_state["enabled"]:
                self.log(f"DECISION: {other_wallbox.capitalize()} shouldn't be charging - stopping")
                self.wallbox_collection.stop_charging_for_wallbox(other_wallbox)
    
    def distribute_power_proportionally(self, total_power, available_wallboxes=None):
        """
        Distribute power proportionally between wallboxes using collection method.
        
        Args:
            total_power (float): Total available power in watts
            available_wallboxes (list, optional): Wallboxes to allocate to. If None, uses all available.
            
        Returns:
            dict: Power allocation per wallbox {name: watts}
        """
        # Use collection method for proportional allocation
        power_allocations = self.wallbox_collection.allocate_power_proportionally(total_power, available_wallboxes)
        
        self.log(f"CALCULATION: Distributing {total_power:.1f}W proportionally among wallboxes")
        for name, watts in power_allocations.items():
            amps = self.power_converter.to_amps(watts)
            self.log(f"CALCULATION: {name.capitalize()} allocated {watts:.1f}W → {amps:.1f}A")
        
        return power_allocations
    
    def handle_prioritization(self, total_power, priority_wallbox, other_wallboxes, states):
        """
        Handle prioritization when there's not enough power for multiple wallboxes.
        Generic version that works with any number of wallboxes.
        
        Args:
            total_power (float): Total available power in watts
            priority_wallbox (str): Name of the priority wallbox
            other_wallboxes (list): List of other wallbox names
            states (dict): Current state of wallboxes
            
        Returns:
            bool: True if prioritization was successful, False otherwise
        """
        priority_state = states[priority_wallbox]
        
        # Calculate minimum power needed for the priority wallbox
        min_watts = self.calculate_min_power_for_wallbox()
        self.log(f"DECISION: {priority_wallbox.capitalize()} has priority. Minimum power needed: {min_watts}W")
        
        if total_power >= min_watts and not priority_state["failed"]:
            # Calculate maximum current based on available power
            max_amps = min(round(self.power_converter.to_amps(total_power)), self.max_current_a)
            max_amps = max(max_amps, self.min_current_a)  # Ensure at least minimum current
            max_watts = self.power_converter.to_watts(max_amps)
            
            self.log(f"DECISION: Enough power for {priority_wallbox.capitalize()} - allocating all {max_watts:.1f}W → {max_amps}A")
            
            # Set current for priority wallbox using collection
            power_allocation = {priority_wallbox: max_watts}
            
            # Handle other wallboxes generically
            for other_wallbox in other_wallboxes:
                other_state = states[other_wallbox]
                if other_state["failed"]:
                    # Set minimum power for failed wallbox
                    power_allocation[other_wallbox] = self.calculate_min_power_for_wallbox()
                elif other_state["charging"] and not other_state["failed"] and other_state["enabled"]:
                    # Stop the other wallbox if it's charging
                    self.log(f"DECISION: Not enough remaining power for {other_wallbox.capitalize()}")
                    self.wallbox_collection.stop_charging_for_wallbox(other_wallbox)
                    power_allocation[other_wallbox] = 0  # No power allocation
            
            # Apply allocations
            self.apply_power_allocations(power_allocation, states)
            return True
        else:
            self.log(f"DECISION: Not enough power even for priority wallbox")
            
            # Stop all wallboxes that are charging and handle failed ones
            all_wallboxes = [priority_wallbox] + other_wallboxes
            power_allocation = {}
            
            for wallbox_name in all_wallboxes:
                wallbox_state = states[wallbox_name]
                if wallbox_state["charging"] and not wallbox_state["failed"] and wallbox_state["enabled"]:
                    self.wallbox_collection.stop_charging_for_wallbox(wallbox_name)
                    power_allocation[wallbox_name] = 0
                elif wallbox_state["failed"]:
                    # Set minimum current for failed wallboxes
                    power_allocation[wallbox_name] = self.calculate_min_power_for_wallbox()
            
            if power_allocation:
                self.apply_power_allocations(power_allocation, states)
            
            return False
    
    def handle_multiple_active_wallboxes(self, total_power, states):
        """
        Handle the case when multiple wallboxes are active.
        
        Args:
            total_power (float): Total available power in watts
            states (dict): Current state of wallboxes
        """
        available_wallboxes = self.wallbox_collection.get_available_for_allocation()
        
        # Distribute power proportionally using collection method
        power_allocations = self.distribute_power_proportionally(total_power, available_wallboxes)
        
        # Apply max current limits to get realistic allocations
        realistic_allocations = {}
        total_realistic_power = 0
        
        for name, watts in power_allocations.items():
            amps = self.power_converter.to_amps(watts)
            # Clamp to max current limit
            realistic_amps = min(amps, self.max_current_a)
            realistic_watts = self.power_converter.to_watts(realistic_amps)
            realistic_allocations[name] = realistic_watts
            total_realistic_power += realistic_watts
            
            self.log(f"CALCULATION: {name.capitalize()} proportional {watts:.1f}W ({amps:.1f}A) → realistic {realistic_watts:.1f}W ({realistic_amps:.1f}A)")
        
        # Calculate remaining power after applying max limits
        remaining_power = total_power - total_realistic_power
        self.log(f"CALCULATION: Remaining power after max limits: {remaining_power:.1f}W")
        
        # If there's remaining power, distribute it to wallboxes that aren't at max
        if remaining_power > 0:
            for name in available_wallboxes:
                current_amps = self.power_converter.to_amps(realistic_allocations[name])
                if current_amps < self.max_current_a:
                    # This wallbox can take more power
                    additional_amps = min(remaining_power / self.power_converter.voltage, self.max_current_a - current_amps)
                    additional_watts = self.power_converter.to_watts(additional_amps)
                    
                    if additional_watts > 0:
                        realistic_allocations[name] += additional_watts
                        remaining_power -= additional_watts
                        self.log(f"CALCULATION: {name.capitalize()} gets additional {additional_watts:.1f}W ({additional_amps:.1f}A)")
                        
                        if remaining_power <= 0:
                            break
        
        # Now check if all wallboxes can operate at minimum current with realistic allocations
        realistic_amps = {name: self.power_converter.to_amps(watts) for name, watts in realistic_allocations.items()}
        insufficient_current = any(amps < self.min_current_a for amps in realistic_amps.values())
        
        # Check if both can charge with minimum current
        min_watts_for_all = len(available_wallboxes) * self.calculate_min_power_for_wallbox()
        self.log(f"CALCULATION: Minimum power needed for {len(available_wallboxes)} wallboxes: {min_watts_for_all}W")
        
        if insufficient_current:
            self.log(f"DECISION: Not enough power for all wallboxes at minimum current - prioritizing")
            priority_wallbox = self.wallbox_collection.get_priority_wallbox(available_wallboxes)
            other_wallboxes = [w for w in available_wallboxes if w != priority_wallbox]
            
            self.handle_prioritization(total_power, priority_wallbox, other_wallboxes, states)
        elif total_power >= min_watts_for_all:
            # Enough power for all wallboxes to charge at proper level
            self.log(f"DECISION: Enough power for all {len(available_wallboxes)} wallboxes")
            self.apply_power_allocations(realistic_allocations, states)
        else:
            # Not enough for all, prioritize based on priority
            self.log(f"DECISION: Not enough power for all wallboxes - prioritizing")
            priority_wallbox = self.wallbox_collection.get_priority_wallbox(available_wallboxes)
            other_wallboxes = [w for w in available_wallboxes if w != priority_wallbox]
            
            self.handle_prioritization(total_power, priority_wallbox, other_wallboxes, states)
    
    def apply_power_allocations(self, power_allocations, states):
        """
        Apply power allocations to wallboxes generically.
        
        Args:
            power_allocations (dict): Power allocations per wallbox {name: watts}
            states (dict): Current state of wallboxes
        """
        for wallbox_name, power_watts in power_allocations.items():
            wallbox_state = states.get(wallbox_name, {})
            
            # Phase 1: Calculate target current with all decision logic
            target_current, should_start = self.calculate_target_current(wallbox_name, power_watts, wallbox_state)
            
            # Phase 2: Apply to hardware directly (no rate limiting)
            self.wallbox_collection.set_current_for_wallbox(wallbox_name, target_current, should_start)
    
    def update_power_required_sensor(self, states):
        """
        Update the power required sensor based on wallbox states using collection.
        
        Args:
            states (dict): Current state of wallboxes (unused, collection has the data)
            
        Returns:
            bool: True if any wallbox requires power, False otherwise
        """
        # Use collection method to check if any wallbox requires power
        wallbox_power_required = self.wallbox_collection.requires_power()
        
        # Update the sensor
        self.set_state("binary_sensor.wallbox_power_required",
                      state="on" if wallbox_power_required else "off")
        
        self.log(f"DECISION: Wallbox power required: {wallbox_power_required}")
        return wallbox_power_required
    
    # Helper methods for wallbox operations
    def start_charging(self, wallbox_name):
        """Start charging for the specified wallbox."""
        wallbox = self.wallboxes[wallbox_name]
        wallbox.start_charging()
    
    def stop_charging(self, wallbox_name):
        """Stop charging for the specified wallbox."""
        wallbox = self.wallboxes[wallbox_name]
        wallbox.stop_charging()
    
    def set_current(self, wallbox_name, current_a, try_start=True):
        """Set the charging current for the specified wallbox."""
        wallbox = self.wallboxes[wallbox_name]
        wallbox.set_current(current_a, try_start)