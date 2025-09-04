"""
Battery Manager Integration Test Base

Specialized integration test utilities for the Battery Manager application.
Provides battery manager specific test data, scenarios, and assertions.
"""

import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add the apps directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ...tests.integration_test_base import IntegrationTestBase


class BatteryManagerIntegrationTest(IntegrationTestBase):
    """
    Specialized integration test base for Battery Manager
    
    Provides battery manager specific utilities and realistic test data.
    """
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for battery manager tests"""
        return {
            'update_interval': 2,
            'batteries': [
                {
                    'name': 'Battery1',
                    'type': 'marstek',
                    'device_prefix': 'battery1'
                },
                {
                    'name': 'Battery2', 
                    'type': 'marstek',
                    'device_prefix': 'battery2'
                },
                {
                    'name': 'Battery3',
                    'type': 'marstek', 
                    'device_prefix': 'battery3'
                }
            ]
        }
    
    def get_battery_sensor_names(self, battery_prefix: str) -> Dict[str, str]:
        """Get sensor names for a specific battery"""
        return {
            'soc': f'sensor.{battery_prefix}_battery_state_of_charge',
            'remaining': f'sensor.{battery_prefix}_battery_remaining_capacity',
            'total': f'sensor.{battery_prefix}_battery_total_energy',
            'power': f'sensor.{battery_prefix}_ac_power',
            'state': f'sensor.{battery_prefix}_inverter_state',
            'control': f'select.{battery_prefix}_rs485_control_mode',
            'max_charge': f'number.{battery_prefix}_max_charge_power',
            'max_discharge': f'number.{battery_prefix}_max_discharge_power',
            'force_charge': f'number.{battery_prefix}_forcible_charge_power',
            'force_discharge': f'number.{battery_prefix}_forcible_discharge_power',
            'force_mode': f'select.{battery_prefix}_forcible_chargedischarge'
        }
    
    def setup_realistic_battery_states(self) -> None:
        """Set up realistic initial battery states for all configured batteries"""
        battery_states = {}
        
        # Battery 1 - 75% SoC, 5kWh capacity, available
        battery1_sensors = self.get_battery_sensor_names('battery1')
        battery_states.update({
            battery1_sensors['soc']: {"state": "75.0"},
            battery1_sensors['remaining']: {"state": "3.75"},
            battery1_sensors['total']: {"state": "5.0"},
            battery1_sensors['power']: {"state": "0"},
            battery1_sensors['state']: {"state": "Sleep"},
            battery1_sensors['control']: {"state": "enable"},
            battery1_sensors['max_charge']: {"state": "2500"},
            battery1_sensors['max_discharge']: {"state": "2500"}
        })
        
        # Battery 2 - 60% SoC, 10kWh capacity, available
        battery2_sensors = self.get_battery_sensor_names('battery2')
        battery_states.update({
            battery2_sensors['soc']: {"state": "60.0"},
            battery2_sensors['remaining']: {"state": "6.0"},
            battery2_sensors['total']: {"state": "10.0"},
            battery2_sensors['power']: {"state": "0"},
            battery2_sensors['state']: {"state": "Standby"},
            battery2_sensors['control']: {"state": "enable"},
            battery2_sensors['max_charge']: {"state": "5000"},
            battery2_sensors['max_discharge']: {"state": "5000"}
        })
        
        # Battery 3 - 85% SoC, 5kWh capacity, available
        battery3_sensors = self.get_battery_sensor_names('battery3')
        battery_states.update({
            battery3_sensors['soc']: {"state": "85.0"},
            battery3_sensors['remaining']: {"state": "4.25"},
            battery3_sensors['total']: {"state": "5.0"},
            battery3_sensors['power']: {"state": "0"},
            battery3_sensors['state']: {"state": "Idle"},
            battery3_sensors['control']: {"state": "enable"},
            battery3_sensors['max_charge']: {"state": "2500"},
            battery3_sensors['max_discharge']: {"state": "2500"}
        })
        
        # Control entities
        battery_states.update({
            'input_number.battery_manager_target_power': {"state": "0"},
            'input_boolean.battery_manager_enabled': {"state": "on"}
        })
        
        self.set_initial_states(battery_states)
    
    def simulate_power_request(self, target_power: float) -> None:
        """Simulate a power request through the target power entity"""
        self.simulate_sensor_update('input_number.battery_manager_target_power', str(target_power))
    
    def simulate_battery_response(self, battery_prefix: str, actual_power: float, delay_seconds: float = 0) -> None:
        """Simulate a battery responding to power command after optional delay"""
        if delay_seconds > 0:
            self.advance_time(int(delay_seconds))
        
        power_sensor = f'sensor.{battery_prefix}_ac_power'
        self.simulate_sensor_update(power_sensor, str(actual_power))
    
    def simulate_battery_state_change(self, battery_prefix: str, new_state: str) -> None:
        """Simulate a battery state change (e.g., Sleep -> Charge -> Discharge)"""
        state_sensor = f'sensor.{battery_prefix}_inverter_state'
        self.simulate_sensor_update(state_sensor, new_state)
    
    def simulate_battery_unavailable(self, battery_prefix: str) -> None:
        """Simulate a battery becoming unavailable (fault state)"""
        self.simulate_battery_state_change(battery_prefix, "Fault")
    
    def simulate_battery_available(self, battery_prefix: str) -> None:
        """Simulate a battery becoming available again"""
        self.simulate_battery_state_change(battery_prefix, "Sleep")
    
    def get_battery_actual_power(self, battery_prefix: str) -> float:
        """Get actual power from a specific battery"""
        power_sensor = f'sensor.{battery_prefix}_ac_power'
        power_str = self.get_sensor_value(power_sensor)
        return float(power_str) if power_str else 0.0
    
    def get_combined_actual_power(self) -> float:
        """Get combined actual power from all batteries"""
        total_power = 0.0
        for battery_config in self.get_default_config()['batteries']:
            prefix = battery_config['device_prefix']
            total_power += self.get_battery_actual_power(prefix)
        return total_power
    
    def get_combined_soc(self) -> float:
        """Get combined SoC from the manager sensor"""
        soc_str = self.get_sensor_value('sensor.combined_battery_soc')
        return float(soc_str) if soc_str else 0.0
    
    def assert_power_distribution_correct(self, target_power: float, expected_distribution: Dict[str, float], tolerance: float = 50.0) -> None:
        """Assert that power was distributed correctly among batteries"""
        for battery_prefix, expected_power in expected_distribution.items():
            actual_power = self.get_battery_actual_power(battery_prefix)
            assert abs(actual_power - expected_power) <= tolerance, \
                f"Battery {battery_prefix}: expected {expected_power}W, got {actual_power}W (tolerance: {tolerance}W)"
    
    def assert_total_power_correct(self, expected_total: float, tolerance: float = 50.0) -> None:
        """Assert that total actual power matches expected"""
        actual_total = self.get_combined_actual_power()
        assert abs(actual_total - expected_total) <= tolerance, \
            f"Total power: expected {expected_total}W, got {actual_total}W (tolerance: {tolerance}W)"
    
    def assert_battery_service_called(self, battery_prefix: str, service: str, expected_params: Dict[str, Any]) -> None:
        """Assert that a specific battery service was called with expected parameters"""
        service_calls = self.get_service_calls(service)
        
        # Find calls that match the battery and parameters
        matching_calls = []
        for call in service_calls:
            call_kwargs = call.get("kwargs", {})
            entity_id = call_kwargs.get("entity_id", "")
            
            # Check if this call is for the specified battery
            if battery_prefix in entity_id:
                # Check if all expected parameters match
                if all(call_kwargs.get(k) == v for k, v in expected_params.items()):
                    matching_calls.append(call)
        
        assert len(matching_calls) > 0, \
            f"Service {service} should have been called for {battery_prefix} with {expected_params}"
    
    def assert_manager_sensors_created(self) -> None:
        """Assert that all expected manager sensors were created"""
        expected_sensors = [
            "sensor.combined_battery_soc",
            "sensor.combined_battery_power", 
            "sensor.combined_battery_capacity",
            "sensor.combined_battery_remaining",
            "sensor.battery_manager_status",
            "sensor.battery_manager_actual_power"
        ]
        
        for sensor_id in expected_sensors:
            self.assert_sensor_exists(sensor_id)
    
    def assert_battery_status_sensors_created(self) -> None:
        """Assert that individual battery status sensors were created"""
        for battery_config in self.get_default_config()['batteries']:
            battery_name = battery_config['name'].lower()
            sensor_id = f"sensor.battery_{battery_name}_status"
            self.assert_sensor_exists(sensor_id)
    
    def simulate_realistic_charge_scenario(self, target_power: float = 3000) -> None:
        """Simulate a realistic charging scenario with gradual ramp-up"""
        # Set target power
        self.simulate_power_request(target_power)
        
        # Trigger update cycle to process the request
        self.simulate_update_cycle()
        
        # Simulate gradual battery ramp-up over 6-8 seconds
        config = self.get_default_config()
        total_capacity = sum(5.0 if 'Battery1' in b['name'] or 'Battery3' in b['name'] else 10.0 
                           for b in config['batteries'])  # 5+10+5 = 20kWh total
        
        for seconds in range(1, 9):  # 8 seconds of ramp-up
            self.advance_time(1)
            
            # Calculate ramp progress (0.0 to 1.0)
            ramp_progress = min(seconds / 6.0, 1.0)  # 6 second ramp time
            
            # Simulate each battery ramping up proportionally
            for battery_config in config['batteries']:
                prefix = battery_config['device_prefix']
                capacity = 5.0 if 'battery1' in prefix or 'battery3' in prefix else 10.0
                
                # Proportional power allocation
                battery_target = target_power * (capacity / total_capacity)
                battery_actual = battery_target * ramp_progress
                
                self.simulate_battery_response(prefix, battery_actual)
            
            # Trigger periodic update
            self.simulate_update_cycle()
    
    def simulate_realistic_discharge_scenario(self, target_power: float = -2000) -> None:
        """Simulate a realistic discharging scenario"""
        self.simulate_realistic_charge_scenario(target_power)  # Same logic, different sign
    
    def wait_for_response_monitoring_period(self) -> None:
        """Wait for the 10-second response monitoring period"""
        self.advance_time(10)
        self.simulate_update_cycle()
    
    def assert_system_status(self, expected_status: str) -> None:
        """Assert the system status matches expected value"""
        actual_status = self.get_sensor_value("sensor.battery_manager_status")
        assert actual_status == expected_status, \
            f"System status: expected '{expected_status}', got '{actual_status}'"