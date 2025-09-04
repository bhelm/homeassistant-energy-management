"""Marstek Battery Implementation"""
from battery import Battery, BatteryState
import time


class MarstekBattery(Battery):
    """Implementation for Marstek battery systems (like Akku1)"""
    
    def __init__(self, name: str, app, device_prefix: str):
        super().__init__(name, app)
        self.device_prefix = device_prefix
        self._entity_ids = self._build_entity_ids()
        
        # Cache last set values to avoid redundant service calls
        self._cached_force_mode = None
        self._cached_charge_power = None
        self._cached_discharge_power = None
    
    def _build_entity_ids(self) -> dict:
        """Build entity ID mapping for this battery"""
        return {
            'soc': f'sensor.{self.device_prefix}_battery_state_of_charge',
            'remaining_kwh': f'sensor.{self.device_prefix}_battery_remaining_capacity',
            'total_kwh': f'sensor.{self.device_prefix}_battery_total_energy',
            'ac_power': f'sensor.{self.device_prefix}_ac_power',
            'inverter_state': f'sensor.{self.device_prefix}_inverter_state',
            'control_mode': f'select.{self.device_prefix}_rs485_control_mode',
            'force_mode': f'select.{self.device_prefix}_forcible_charge_discharge',
            'charge_power': f'number.{self.device_prefix}_forcible_charge_power',
            'discharge_power': f'number.{self.device_prefix}_forcible_discharge_power',
            'max_charge': f'number.{self.device_prefix}_max_charge_power',
            'max_discharge': f'number.{self.device_prefix}_max_discharge_power'
        }
    
    def get_soc(self) -> float:
        """Get State of Charge percentage"""
        return float(self.app.get_state(self._entity_ids['soc']) or 0)
    
    def get_remaining_kwh(self) -> float:
        """Get remaining energy in kWh"""
        return float(self.app.get_state(self._entity_ids['remaining_kwh']) or 0)
    
    def get_total_capacity_kwh(self) -> float:
        """Get total battery capacity in kWh"""
        return float(self.app.get_state(self._entity_ids['total_kwh']) or 0)
    
    def get_current_power_w(self) -> float:
        """Get current AC power (positive=charge, negative=discharge)"""
        return float(self.app.get_state(self._entity_ids['ac_power']) or 0)
    
    def get_state(self) -> BatteryState:
        """Get current battery operational state"""
        inverter_state = self.app.get_state(self._entity_ids['inverter_state'])
        
        state_mapping = {
            'Sleep': BatteryState.AVAILABLE,
            'Standby': BatteryState.AVAILABLE,
            'Charge': BatteryState.CHARGING,
            'Discharge': BatteryState.DISCHARGING,
            'Fault': BatteryState.FAULT,
            'Idle': BatteryState.AVAILABLE,
            'AC bypass': BatteryState.AVAILABLE
        }
        
        return state_mapping.get(inverter_state, BatteryState.OFFLINE)
    
    def is_available(self) -> bool:
        """Check if battery is available for power control"""
        state = self.get_state()
        control_mode_value = self.app.get_state(self._entity_ids['control_mode'])
        control_enabled = control_mode_value == 'enable'
        
        return (state != BatteryState.FAULT and
                state != BatteryState.OFFLINE and
                control_enabled)
    
    def set_power_w(self, power_w: float) -> bool:
        """Set battery power (positive=charge, negative=discharge)"""
        if not self.is_available():
            self.app.log(f"Battery {self.name} not available for power control", level="WARNING")
            return False
        
        try:
            if abs(power_w) < 10:  # Stop battery (power close to 0)
                self.app.log(f"Setting {self.name} to STOP mode (power: {power_w:.0f}W)", level="INFO")
                self._stop_battery()
            elif power_w > 0:  # Charge (positive power)
                self.app.log(f"Setting {self.name} to CHARGE mode at {power_w:.0f}W", level="INFO")
                self._set_charge_power(power_w)
            else:  # Discharge (negative power)
                discharge_power = abs(power_w)
                self.app.log(f"Setting {self.name} to DISCHARGE mode at {discharge_power:.0f}W", level="INFO")
                self._set_discharge_power(discharge_power)
            
            return True
            
        except Exception as e:
            self.app.log(f"Error setting power for {self.name}: {e}", level="ERROR")
            return False
    
    def get_max_charge_power_w(self) -> float:
        """Get maximum charge power"""
        return float(2500)
    
    def get_max_discharge_power_w(self) -> float:
        """Get maximum discharge power"""
        return float(2500)
    
    
    def _set_entity_if_changed(self, entity_id: str, new_value, cached_attr: str, service_domain: str, service_name: str, **service_data):
        """DRY helper: Set entity value only if it differs from cached value"""
        current_cached = getattr(self, cached_attr)
        
        # Check if value actually changed (with tolerance for numbers)
        if isinstance(new_value, (int, float)) and isinstance(current_cached, (int, float)):
            changed = abs(new_value - current_cached) > 0.5
        else:
            changed = new_value != current_cached
            
        if changed or current_cached is None:
            self.app.log(f"Setting {entity_id} from {current_cached} to {new_value}", level="INFO")
            try:
                self.app.call_service(f'{service_domain}/{service_name}',
                                    entity_id=entity_id,
                                    **service_data)
                setattr(self, cached_attr, new_value)
                return True
            except Exception as e:
                self.app.log(f"Error setting {entity_id}: {e}", level="ERROR")
                return False
        else:
            self.app.log(f"{entity_id} already {current_cached}, skipping", level="DEBUG")
            return True
    
    def _stop_battery(self):
        """Stop battery charging/discharging"""
        self._set_entity_if_changed(
            entity_id=self._entity_ids['force_mode'],
            new_value='stop',
            cached_attr='_cached_force_mode',
            service_domain='select',
            service_name='select_option',
            option='stop'
        )
    
    def _set_discharge_power(self, power_w: float):
        """Set battery to discharge at specified power"""
        max_power = self.get_max_discharge_power_w()
        limited_power = min(power_w, max_power)
        rounded_power = round(limited_power)
        
        # Set discharge power if changed
        self._set_entity_if_changed(
            entity_id=self._entity_ids['discharge_power'],
            new_value=rounded_power,
            cached_attr='_cached_discharge_power',
            service_domain='number',
            service_name='set_value',
            value=rounded_power
        )
        
        # Set force mode to discharge if changed
        self._set_entity_if_changed(
            entity_id=self._entity_ids['force_mode'],
            new_value='discharge',
            cached_attr='_cached_force_mode',
            service_domain='select',
            service_name='select_option',
            option='discharge'
        )
    
    def _set_charge_power(self, power_w: float):
        """Set battery to charge at specified power"""
        max_power = self.get_max_charge_power_w()
        limited_power = min(power_w, max_power)
        rounded_power = round(limited_power)
        
        # Set charge power if changed
        self._set_entity_if_changed(
            entity_id=self._entity_ids['charge_power'],
            new_value=rounded_power,
            cached_attr='_cached_charge_power',
            service_domain='number',
            service_name='set_value',
            value=rounded_power
        )
        
        # Set force mode to charge if changed
        self._set_entity_if_changed(
            entity_id=self._entity_ids['force_mode'],
            new_value='charge',
            cached_attr='_cached_force_mode',
            service_domain='select',
            service_name='select_option',
            option='charge'
        )