"""
Wallbox collection management for handling multiple wallboxes generically.

This module provides the WallboxCollection class and configuration for managing
multiple wallboxes in a generic, extensible way.
"""

from wallbox import Wallbox

# Wallbox Configuration - Easy to extend by adding more wallboxes here
WALLBOX_CONFIGS = [
    {'name': 'dani', 'priority': 2.0},  # Higher priority gets more power
    {'name': 'elli', 'priority': 1.0}   # Standard priority
    # Adding a third wallbox would be as simple as:
    # {'name': 'garage', 'priority': 1.5}
]


class WallboxCollection:
    """
    Collection class to manage multiple wallboxes generically.
    Eliminates hardcoded wallbox names and provides generic operations.
    
    This class follows the Single Responsibility Principle by handling only
    wallbox collection management and power allocation logic.
    """
    
    def __init__(self, configs, app):
        """
        Initialize wallbox collection from configuration.
        
        Args:
            configs (list): List of wallbox configurations with 'name' and 'priority' keys
            app (WallboxManager): Reference to parent app
        """
        self.app = app
        self.wallboxes = {}
        self.priorities = {}
        
        for config in configs:
            name = config['name']
            self.wallboxes[name] = Wallbox(name, app)
            self.priorities[name] = config['priority']
        
        self.app.log(f"Initialized wallbox collection with {len(self.wallboxes)} wallboxes: {list(self.wallboxes.keys())}")
    
    def get_wallbox_names(self):
        """Get all configured wallbox names."""
        return list(self.wallboxes.keys())
    
    def get_wallbox(self, name):
        """Get a specific wallbox instance by name."""
        return self.wallboxes.get(name)
    
    def get_active_wallboxes(self):
        """
        Get wallboxes that are enabled and connected.
        
        Returns:
            list: Names of wallboxes that are active (enabled and connected)
        """
        active = []
        for name, wallbox in self.wallboxes.items():
            if wallbox.is_enabled() and wallbox.is_connected():
                active.append(name)
        return active
    
    def get_available_for_allocation(self):
        """
        Get wallboxes available for power allocation (active and not failed).
        
        Returns:
            list: Names of wallboxes that can receive power allocation
        """
        available = []
        for name in self.get_active_wallboxes():
            if not self.wallboxes[name].is_charging_failed():
                available.append(name)
        return available
    
    def get_failed_wallboxes(self):
        """
        Get wallboxes that are active but have failed to charge.
        
        Returns:
            list: Names of wallboxes that are failed
        """
        failed = []
        for name in self.get_active_wallboxes():
            if self.wallboxes[name].is_charging_failed():
                failed.append(name)
        return failed
    
    def get_priority_wallbox(self, wallbox_names):
        """
        Get the highest priority wallbox from a list of names.
        
        Args:
            wallbox_names (list): List of wallbox names to choose from
            
        Returns:
            str: Name of the highest priority wallbox, or None if list is empty
        """
        if not wallbox_names:
            return None
        return max(wallbox_names, key=lambda name: self.priorities[name])
    
    def get_all_states(self):
        """
        Get current state of all wallboxes.
        
        Returns:
            dict: State information for each wallbox {name: state_dict}
        """
        states = {}
        for name, wallbox in self.wallboxes.items():
            states[name] = {
                "wallbox": wallbox,
                "enabled": wallbox.is_enabled(),
                "connected": wallbox.is_connected(),
                "charging": wallbox.is_charging(),
                "current_power": wallbox.get_current_power(),
                "current_limit": wallbox.get_current_limit(),
                "failed": wallbox.is_charging_failed()
            }
        return states
    
    def allocate_power_proportionally(self, total_power, available_wallboxes=None):
        """
        Allocate power proportionally based on priorities.
        
        Args:
            total_power (float): Total power to allocate in watts
            available_wallboxes (list, optional): List of wallbox names to allocate to.
                                                 If None, uses all available wallboxes.
            
        Returns:
            dict: Power allocation per wallbox {name: watts}
        """
        if available_wallboxes is None:
            available_wallboxes = self.get_available_for_allocation()
        
        if not available_wallboxes:
            return {}
        
        total_priority = sum(self.priorities[name] for name in available_wallboxes)
        allocations = {}
        
        for name in available_wallboxes:
            proportion = self.priorities[name] / total_priority
            allocations[name] = total_power * proportion
        
        self.app.log(f"Power allocation: {allocations}")
        return allocations
    
    def requires_power(self):
        """
        Check if any wallbox in the collection requires power.
        
        Returns:
            bool: True if any wallbox requires power, False otherwise
        """
        for wallbox in self.wallboxes.values():
            if wallbox.requires_power():
                return True
        return False
    
    def set_current_for_wallbox(self, name, current_a, try_start=True):
        """
        Set charging current for a specific wallbox.
        
        Args:
            name (str): Wallbox name
            current_a (float): Current to set in amperes
            try_start (bool): Whether to try starting charging
        """
        wallbox = self.get_wallbox(name)
        if wallbox:
            wallbox.set_current(current_a, try_start)
        else:
            self.app.log(f"ERROR: Wallbox '{name}' not found")
    
    def start_charging_for_wallbox(self, name):
        """Start charging for a specific wallbox."""
        wallbox = self.get_wallbox(name)
        if wallbox:
            wallbox.start_charging()
        else:
            self.app.log(f"ERROR: Wallbox '{name}' not found")
    
    def stop_charging_for_wallbox(self, name):
        """Stop charging for a specific wallbox."""
        wallbox = self.get_wallbox(name)
        if wallbox:
            wallbox.stop_charging()
        else:
            self.app.log(f"ERROR: Wallbox '{name}' not found")
    
    def schedule_retry_for_failed_wallboxes(self):
        """Schedule retries for all failed wallboxes."""
        failed = self.get_failed_wallboxes()
        for name in failed:
            wallbox = self.get_wallbox(name)
            if wallbox:
                wallbox.schedule_retry()
    
    def limit_power_change_for_wallbox(self, name, target_amps):
        """
        Apply gradual power change limiting for a specific wallbox.
        
        Args:
            name (str): Wallbox name
            target_amps (float): Target current in amps
            
        Returns:
            float: Limited current in amps
        """
        wallbox = self.get_wallbox(name)
        if wallbox:
            return self.app.limit_power_change(name, target_amps)
        return target_amps