"""Abstract Battery Interface"""
from abc import ABC, abstractmethod
from enum import Enum


class BatteryState(Enum):
    """Battery operational states"""
    AVAILABLE = "available"
    CHARGING = "charging"
    DISCHARGING = "discharging"
    FAULT = "fault"
    OFFLINE = "offline"


class Battery(ABC):
    """Abstract base class for all battery implementations"""
    
    def __init__(self, name: str, app):
        self.name = name
        self.app = app
    
    @abstractmethod
    def get_soc(self) -> float:
        """Return State of Charge as percentage (0-100)"""
        pass
    
    @abstractmethod
    def get_remaining_kwh(self) -> float:
        """Return remaining energy in kWh"""
        pass
    
    @abstractmethod
    def get_total_capacity_kwh(self) -> float:
        """Return total battery capacity in kWh"""
        pass
    
    @abstractmethod
    def get_current_power_w(self) -> float:
        """Return current power in watts (positive=charge, negative=discharge)"""
        pass
    
    @abstractmethod
    def set_power_w(self, power_w: float) -> bool:
        """Set battery power in watts (positive=charge, negative=discharge)"""
        pass
    
    @abstractmethod
    def get_max_charge_power_w(self) -> float:
        """Return maximum charge power in watts"""
        pass
    
    @abstractmethod
    def get_max_discharge_power_w(self) -> float:
        """Return maximum discharge power in watts"""
        pass
    
    @abstractmethod
    def get_state(self) -> BatteryState:
        """Return current battery state"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if battery is available for power control"""
        pass