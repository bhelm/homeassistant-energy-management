"""
Wallbox class for managing individual wallbox operations.

This module provides the Wallbox class that encapsulates all operations
related to a specific wallbox instance.
"""

import time


class Wallbox:
    """
    Class to encapsulate wallbox-specific functionality and state.
    
    This class handles all operations related to a specific wallbox, including:
    - Checking status (enabled, connected, charging)
    - Starting and stopping charging
    - Setting charging current
    - Managing retry attempts for failed charging
    - Tracking charging state
    
    By encapsulating wallbox-specific functionality, this class eliminates
    code duplication between different wallboxes in the WallboxManager.
    """
    
    def __init__(self, name, app):
        """
        Initialize a Wallbox instance.
        
        Args:
            name (str): The name of the wallbox (e.g., "dani" or "elli")
            app (WallboxManager): Reference to the parent WallboxManager app
        """
        self.name = name.lower()  # Ensure lowercase for consistency
        self.app = app
        
        # Tracking variables for charging attempts
        self.attempt_count = 0
        self.last_attempt_time = 0
        self.retry_timer = None
        self.last_charging = False
    
    def get_entity_id(self, type):
        """
        Generate entity IDs based on the wallbox name.
        
        Args:
            type (str): The type of entity (e.g., "charging", "cable", "powernow", "globalcurrent")
            
        Returns:
            str: The full entity ID
        """
        # Map name to entity name (dani -> daniel)
        entity_name = "daniel" if self.name == "dani" else self.name
        
        # Map of entity types to their prefixes and suffixes
        entity_map = {
            "enabled": (f"input_boolean.wallbox_{self.name}_ueberschuss", ""),
            "charging": (f"binary_sensor.warp2_22vo_{entity_name}", "_charging"),
            "cable": (f"binary_sensor.warp2_22vo_{entity_name}", "_cable"),
            "power": (f"sensor.warp2_22vo_{entity_name}", "_powernow"),
            "current": (f"number.warp2_22vo_{entity_name}", "_globalcurrent"),
            "start": (f"button.warp2_22vo_{entity_name}", "_startcharge"),
            "stop": (f"button.warp2_22vo_{entity_name}", "_stopcharge")
        }
        
        if type in entity_map:
            prefix, suffix = entity_map[type]
            return f"{prefix}{suffix}"
        
        # If type not found in map, construct a default entity ID
        entity_name = "daniel" if self.name == "dani" else self.name
        return f"sensor.warp2_22vo_{entity_name}_{type}"
    
    def is_enabled(self):
        """
        Check if the wallbox is enabled.
        
        Returns:
            bool: True if enabled, False otherwise
        """
        return self.app.get_state(self.get_entity_id("enabled")) == "on"
    
    def is_connected(self):
        """
        Check if a cable is connected to the wallbox.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self.app.get_state(self.get_entity_id("cable")) == "on"
    
    def is_charging(self):
        """
        Check if the wallbox is currently charging.
        
        Returns:
            bool: True if charging, False otherwise
        """
        return self.app.get_state(self.get_entity_id("charging")) == "on"
    
    def get_current_power(self):
        """
        Get the current power consumption of the wallbox. 
        
        Returns:
            float: Current power consumption in watts, or 0.0 if the state is None
        """
        state = self.app.get_state(self.get_entity_id("power"))
        if state is None:
            self.app.log(f"WARNING: Power state for {self.name} is None, returning 0.0")
            return 0.0
        return float(state)
    
    def get_current_limit(self):
        """
        Get the current limit setting of the wallbox.
        
        Returns:
            float: Current limit in amperes, or 0.0 if the state is None
        """
        state = self.app.get_state(self.get_entity_id("current"))
        if state is None:
            self.app.log(f"WARNING: Current limit state for {self.name} is None, returning 0.0")
            return 0.0
        return float(state)
    
    def start_charging(self):
        """
        Start charging with initial current 6A.
        
        This method:
        1. Sets the initial current to 6A
        2. Presses the start charge button
        3. Tracks the attempt count and timestamp
        4. Schedules a check to verify charging started successfully
        """
        self.app.log(f"ACTION: Starting charging for {self.name.capitalize()} with initial current 6A")
        self.app.call_service("number/set_value", entity_id=self.get_entity_id("current"), value=6)
        self.app.call_service("button/press", entity_id=self.get_entity_id("start"))
        
        # Track attempt
        self.attempt_count += 1
        self.last_attempt_time = time.time()
        self.app.log(f"INFO: {self.name.capitalize()} charging attempt {self.attempt_count} of {self.app.max_attempts}")
        
        # Schedule a check to see if charging started
        self.app.run_in(self.check_charging, 30)  # Check after 30 seconds
    
    def stop_charging(self):
        """
        Stop charging.
        
        This method:
        1. Presses the stop charge button
        2. Sets the current to 0A
        """
        self.app.log(f"ACTION: Stopping charging for {self.name.capitalize()}")
        self.app.call_service("button/press", entity_id=self.get_entity_id("stop"))
        self.app.call_service("number/set_value", entity_id=self.get_entity_id("current"), value=0)
    
    def set_current(self, current_a, try_start=True):
        """
        Set the charging current.
        
        This method:
        1. Ensures the current is within valid bounds
        2. Stops charging if current is below minimum
        3. Sets the new current if different from current setting
        4. Starts charging if not already charging and try_start is True
        
        Args:
            current_a (float): The current to set in amperes
            try_start (bool, optional): Whether to try starting charging if not already charging. Defaults to True.
        """
        original_current = current_a
        current_a = max(min(int(current_a), self.app.max_current_a), 0)
        
        self.app.log(f"DEBUG: {self.name.capitalize()} set_current called with {original_current:.2f}A, clamped to {current_a}A")
        
        if current_a < self.app.min_current_a:
            self.app.log(f"DECISION: {self.name.capitalize()} current {current_a}A is below minimum - stopping charge")
            if self.is_charging():
                self.stop_charging()
        else:
            current_limit = self.get_current_limit()
            if current_a != current_limit:
                self.app.log(f"ACTION: Setting {self.name.capitalize()} current to {current_a}A (was {current_limit}A)")
                self.app.call_service("number/set_value", entity_id=self.get_entity_id("current"), value=current_a)
            else:
                self.app.log(f"INFO: {self.name.capitalize()} current remains at {current_a}A (no change needed)")
                
            if try_start and not self.is_charging() and self.is_connected():
                self.app.log(f"DECISION: {self.name.capitalize()} is connected but not charging - starting charge")
                self.start_charging()
            elif try_start and not self.is_charging():
                self.app.log(f"DEBUG: {self.name.capitalize()} try_start=True but not charging because: connected={self.is_connected()}")
            elif not try_start:
                self.app.log(f"DEBUG: {self.name.capitalize()} try_start=False, not attempting to start charging")
    
    def check_charging(self, kwargs):
        """
        Check if charging started successfully.
        
        This method:
        1. Checks if the wallbox is charging and consuming power
        2. Resets attempt counter if charging successfully
        3. Schedules a retry if charging failed after max attempts
        4. Triggers reallocation of power if charging failed
        
        Args:
            kwargs: AppDaemon callback arguments
        """
        charging = self.is_charging()
        power = self.get_current_power()
        
        self.app.log(f"DEBUG: Checking if {self.name.capitalize()} is charging: charging={charging}, power={power}W, attempt_count={self.attempt_count}")
        
        if charging and power > self.app.power_threshold:
            self.app.log(f"INFO: {self.name.capitalize()} charging started successfully, consuming {power}W")
            self.attempt_count = 0  # Reset attempt counter
        else:
            self.app.log(f"WARNING: {self.name.capitalize()} charging did not start properly. Attempt {self.attempt_count} of {self.app.max_attempts}")
            
            if self.attempt_count >= self.app.max_attempts:
                # Only log and schedule retry if not already scheduled
                if self.retry_timer is None:
                    self.app.log(f"DECISION: {self.name.capitalize()} has failed to start charging - scheduling retry")
                    self.schedule_retry()
                
                # Run the manager again to reallocate power
                self.app.run_in(self.app.manage_wallboxes_wrapper, 5)
    
    def on_charging_change(self, entity, attribute, old, new, kwargs):
        """
        Handle changes in charging state.
        
        This method:
        1. Detects when charging starts or stops
        2. Resets attempt counter when charging starts successfully
        3. Logs charging state changes
        
        Args:
            entity: Entity that changed
            attribute: Attribute that changed
            old: Old state value
            new: New state value
            kwargs: AppDaemon callback arguments
        """
        if new == "on" and old == "off":
            # Charging started successfully
            self.app.log(f"INFO: {self.name.capitalize()} charging started successfully")
            self.attempt_count = 0
        elif new == "off" and old == "on":
            # Charging stopped
            self.app.log(f"INFO: {self.name.capitalize()} charging stopped")
    
    def is_charging_failed(self):
        """
        Determine if the wallbox has failed to start charging.
        
        This method checks:
        1. If the wallbox is charging and consuming power
        2. If maximum attempts have been reached
        
        Returns:
            bool: True if charging has failed, False otherwise
        """
        charging = self.is_charging()
        power = self.get_current_power()
        
        # If charging and consuming power, not failed
        if charging and power > self.app.power_threshold:
            return False
        
        # If we've tried multiple times
        if self.attempt_count >= self.app.max_attempts:
            return True
            
        return False
    
    def schedule_retry(self):
        """
        Schedule a retry for a failed wallbox.
        
        This method schedules a retry only if one is not already scheduled.
        """
        # Only schedule if not already scheduled
        if self.retry_timer is None:
            self.retry_timer = self.app.run_in(self.retry, self.app.retry_interval)
    
    def retry(self, kwargs):
        """
        Retry charging after a failure.
        
        This method:
        1. Resets the attempt counter
        2. Clears the retry timer
        3. Starts charging if the wallbox is still enabled and connected
        
        Args:
            kwargs: AppDaemon callback arguments
        """
        self.app.log(f"ACTION: Retrying charging for {self.name.capitalize()}")
        self.attempt_count = 0
        self.retry_timer = None
        
        # Only retry if still enabled and connected
        if self.is_enabled() and self.is_connected():
            self.start_charging()
    
    def requires_power(self):
        """
        Check if the wallbox requires power.
        
        A wallbox requires power if it is:
        1. Enabled
        2. Connected
        3. Either currently charging or not in a failed state
        
        Returns:
            bool: True if the wallbox requires power, False otherwise
        """
        return self.is_enabled() and self.is_connected() and (self.is_charging() or not self.is_charging_failed())