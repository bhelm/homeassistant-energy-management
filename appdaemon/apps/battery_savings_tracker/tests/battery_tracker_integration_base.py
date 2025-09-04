"""
Battery Tracker Integration Test Base

Specialized integration test utilities for the Battery Savings Tracker application.
Provides battery tracker specific test data, scenarios, and assertions.
"""

import sys
import os
from typing import Dict, Any

# Add the apps directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ...tests.integration_test_base import IntegrationTestBase


class BatteryTrackerIntegrationTest(IntegrationTestBase):
    """
    Specialized integration test base for Battery Savings Tracker
    
    Provides battery tracker specific utilities and realistic test data.
    """
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for battery tracker tests"""
        return {
            'update_interval': 300,
            'pv_surplus_rate_ct': 7.8,
            # Configurable sensor names (using defaults)
            'battery_pv_energy_sensor': 'sensor.battery_combined_pv_energy',
            'battery_grid_energy_sensor': 'sensor.battery_combined_grid_energy',
            'battery_discharge_sensor': 'sensor.combined_battery_total_discharging_kwh',
            'tibber_price_sensor': 'sensor.tibber_future_statistics'
        }
    
    def get_sensor_names(self) -> Dict[str, str]:
        """Get the sensor names from the current configuration"""
        config = self.get_default_config()
        return {
            'pv_energy': config['battery_pv_energy_sensor'],
            'grid_energy': config['battery_grid_energy_sensor'],
            'discharge': config['battery_discharge_sensor'],
            'tibber_price': config['tibber_price_sensor']
        }
    
    def setup_realistic_initial_states(self) -> None:
        """Set up realistic initial sensor states for battery tracker testing"""
        sensors = self.get_sensor_names()
        initial_states = {
            # Energy distributor sensors (source sensors)
            sensors['pv_energy']: {
                "state": "10.5",
                "attributes": {
                    "unit_of_measurement": "kWh",
                    "device_class": "energy",
                    "state_class": "total_increasing"
                }
            },
            sensors['grid_energy']: {
                "state": "5.2",
                "attributes": {
                    "unit_of_measurement": "kWh",
                    "device_class": "energy",
                    "state_class": "total_increasing"
                }
            },
            sensors['discharge']: {
                "state": "8.7",
                "attributes": {
                    "unit_of_measurement": "kWh",
                    "device_class": "energy",
                    "state_class": "total_increasing"
                }
            },
            # Tibber pricing sensor
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {
                    "current_price": 0.25,  # EUR/kWh
                    "unit_of_measurement": "EUR/kWh"
                }
            }
        }
        
        self.set_initial_states(initial_states)
    
    def simulate_pv_charging_scenario(self, pv_kwh_increase: float = 2.0) -> None:
        """
        Simulate a PV charging scenario
        
        Args:
            pv_kwh_increase: Amount of PV energy increase in kWh
        """
        sensors = self.get_sensor_names()
        current_pv = float(self.get_sensor_value(sensors['pv_energy']))
        new_pv = current_pv + pv_kwh_increase
        self.simulate_sensor_update(sensors['pv_energy'], str(new_pv))
    
    def simulate_grid_charging_scenario(self, grid_kwh_increase: float = 1.5) -> None:
        """
        Simulate a grid charging scenario
        
        Args:
            grid_kwh_increase: Amount of grid energy increase in kWh
        """
        sensors = self.get_sensor_names()
        current_grid = float(self.get_sensor_value(sensors['grid_energy']))
        new_grid = current_grid + grid_kwh_increase
        self.simulate_sensor_update(sensors['grid_energy'], str(new_grid))
    
    def simulate_discharge_scenario(self, discharge_kwh_increase: float = 3.0) -> None:
        """
        Simulate a battery discharge scenario
        
        Args:
            discharge_kwh_increase: Amount of discharge energy increase in kWh
        """
        sensors = self.get_sensor_names()
        current_discharge = float(self.get_sensor_value(sensors['discharge']))
        new_discharge = current_discharge + discharge_kwh_increase
        self.simulate_sensor_update(sensors['discharge'], str(new_discharge))
    
    def set_tibber_price(self, price_eur_per_kwh: float) -> None:
        """
        Set the Tibber price for testing
        
        Args:
            price_eur_per_kwh: Price in EUR per kWh
        """
        sensors = self.get_sensor_names()
        self.simulate_sensor_update(
            sensors['tibber_price'],
            "available",
            {"current_price": price_eur_per_kwh}
        )
    
    def set_tibber_unavailable(self) -> None:
        """Set Tibber sensor to unavailable state"""
        sensors = self.get_sensor_names()
        self.simulate_sensor_update(
            sensors['tibber_price'],
            "unavailable",
            {"current_price": None}
        )
    
    def assert_cost_calculation_correct(self, sensor_id: str, expected_cost: float, tolerance: float = 0.000001) -> None:
        """
        Assert that a cost calculation is correct within tolerance
        
        Args:
            sensor_id: The cost sensor to check
            expected_cost: Expected cost value
            tolerance: Tolerance for floating point comparison
        """
        actual_cost = float(self.get_sensor_value(sensor_id))
        assert abs(actual_cost - expected_cost) < tolerance, \
            f"Cost calculation for {sensor_id}: expected {expected_cost:.6f}€, got {actual_cost:.6f}€"
    
    def assert_all_tracking_sensors_created(self) -> None:
        """Assert that all expected tracking sensors were created"""
        expected_sensors = [
            # State management sensors
            "sensor.battery_savings_last_run_timestamp",
            "sensor.battery_savings_last_pv_kwh",
            "sensor.battery_savings_last_grid_kwh", 
            "sensor.battery_savings_last_discharge_kwh",
            
            # Cumulative tracking sensors
            "sensor.battery_total_money_saved_eur",
            "sensor.battery_pv_charging_cost_eur",
            "sensor.battery_grid_charging_cost_eur",
            "sensor.battery_discharge_savings_eur",
            
            # Time-based savings tracking sensors
            "sensor.battery_daily_money_saved_eur",
            "sensor.battery_weekly_money_saved_eur",
            "sensor.battery_monthly_money_saved_eur",
            "sensor.battery_yearly_money_saved_eur",
            
            # Reset tracking sensor
            "sensor.battery_savings_last_reset_date"
        ]
        
        for sensor_id in expected_sensors:
            self.assert_sensor_exists(sensor_id)
    
    def simulate_counter_reset_scenario(self) -> None:
        """Simulate a counter reset scenario where current values are less than last values"""
        # Set up scenario where counters have reset (current < last)
        sensors = self.get_sensor_names()
        self.simulate_sensor_update(sensors['pv_energy'], "0.5")  # Reset from 10.5
        self.simulate_sensor_update(sensors['grid_energy'], "0.2")  # Reset from 5.2
        self.simulate_sensor_update(sensors['discharge'], "1.1")  # Reset from 8.7
    
    def simulate_realistic_daily_scenario(self) -> None:
        """
        Simulate a realistic daily energy flow scenario
        
        This simulates:
        1. Morning: PV charging starts
        2. Midday: High PV charging
        3. Evening: Grid charging (low rates)
        4. Night: Battery discharge (high rates)
        """
        # Morning PV charging (low rate)
        self.set_tibber_price(0.20)  # 20 ct/kWh
        self.simulate_pv_charging_scenario(1.0)
        self.simulate_update_cycle()
        
        # Midday high PV charging
        self.set_tibber_price(0.15)  # 15 ct/kWh (low midday rates)
        self.simulate_pv_charging_scenario(3.0)
        self.simulate_update_cycle()
        
        # Evening grid charging (still reasonable rates)
        self.set_tibber_price(0.25)  # 25 ct/kWh
        self.simulate_grid_charging_scenario(2.0)
        self.simulate_update_cycle()
        
        # Night discharge (high rates)
        self.set_tibber_price(0.35)  # 35 ct/kWh (peak rates)
        self.simulate_discharge_scenario(4.0)
        self.simulate_update_cycle()
    
    def get_expected_pv_cost(self, pv_kwh: float, pv_rate_ct: float = 7.8) -> float:
        """
        Calculate expected PV charging cost
        
        Args:
            pv_kwh: PV energy in kWh
            pv_rate_ct: PV surplus rate in ct/kWh
            
        Returns:
            Expected cost in EUR (negative value)
        """
        return (pv_kwh * (-pv_rate_ct)) / 100
    
    def get_expected_grid_cost(self, grid_kwh: float, tibber_price_ct: float) -> float:
        """
        Calculate expected grid charging cost
        
        Args:
            grid_kwh: Grid energy in kWh
            tibber_price_ct: Tibber price in ct/kWh
            
        Returns:
            Expected cost in EUR (negative value)
        """
        return (grid_kwh * (-tibber_price_ct)) / 100
    
    def get_expected_discharge_savings(self, discharge_kwh: float, tibber_price_ct: float) -> float:
        """
        Calculate expected discharge savings
        
        Args:
            discharge_kwh: Discharge energy in kWh
            tibber_price_ct: Tibber price in ct/kWh
            
        Returns:
            Expected savings in EUR (positive value)
        """
        return (discharge_kwh * tibber_price_ct) / 100
    
    def simulate_time_advance(self, days: int = 0, hours: int = 0, minutes: int = 0) -> None:
        """
        Simulate time advancement for testing time-based resets
        
        Args:
            days: Number of days to advance
            hours: Number of hours to advance
            minutes: Number of minutes to advance
        """
        total_seconds = (days * 24 * 3600) + (hours * 3600) + (minutes * 60)
        if total_seconds > 0:
            self.mock.advance_time(total_seconds)
    
    def simulate_energy_sensor_drop_and_recovery(self, sensor_id: str, drop_value: str, recovery_value: str) -> None:
        """
        Simulate an energy sensor dropping to a lower value and then recovering
        
        Args:
            sensor_id: The sensor to simulate drop/recovery for
            drop_value: The lower value to drop to
            recovery_value: The higher value to recover to
        """
        # First simulate the drop
        self.simulate_sensor_update(sensor_id, drop_value)
        self.simulate_update_cycle()
        
        # Then simulate the recovery
        self.simulate_sensor_update(sensor_id, recovery_value)
        self.simulate_update_cycle()
    
    def set_mock_date(self, year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> None:
        """
        Set the mock's current date/time for testing time-based functionality
        
        Args:
            year: Year to set
            month: Month to set (1-12)
            day: Day to set (1-31)
            hour: Hour to set (0-23)
            minute: Minute to set (0-59)
        """
        from datetime import datetime
        new_time = datetime(year, month, day, hour, minute)
        self.mock.set_current_time(new_time)
    
    def assert_time_based_sensor_reset(self, sensor_id: str) -> None:
        """
        Assert that a time-based sensor was reset to 0
        
        Args:
            sensor_id: The sensor to check for reset
        """
        self.assert_sensor_value(sensor_id, "0")
    
    def assert_energy_delta_ignored(self, expected_message: str) -> None:
        """
        Assert that an energy delta was ignored (logged as counter reset)
        
        Args:
            expected_message: Expected log message indicating counter reset
        """
        self.assert_log_contains(expected_message)