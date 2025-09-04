"""
Battery Savings Tracker Integration Tests

Comprehensive integration tests that test the complete Battery Savings Tracker
application lifecycle using production functions and realistic HASS API simulation.

These tests replace the previous approach of testing private methods directly
with end-to-end integration testing of the complete application workflow.
"""

import pytest
import sys
import os

# Add the apps directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from battery_savings_tracker.battery_savings_tracker import BatterySavingsTracker
from .battery_tracker_integration_base import BatteryTrackerIntegrationTest


@pytest.fixture
def battery_tracker_test():
    """Pytest fixture that provides a fresh BatteryTrackerIntegrationTest instance for each test"""
    test_base = BatteryTrackerIntegrationTest()
    test_base.setup_app(BatterySavingsTracker, test_base.get_default_config())
    yield test_base
    test_base.teardown_app()


class TestBatterySavingsTrackerIntegration:
    """Integration tests for Battery Savings Tracker using complete application workflows"""
    
    def test_complete_application_initialization(self, battery_tracker_test):
        """Test complete application initialization and sensor creation"""
        # Set up realistic initial states
        battery_tracker_test.setup_realistic_initial_states()
        
        # Initialize the application
        battery_tracker_test.initialize_app()
        
        # Verify all tracking sensors were created
        battery_tracker_test.assert_all_tracking_sensors_created()
        
        # Verify initial sensor values are set correctly
        battery_tracker_test.assert_sensor_value("sensor.battery_total_money_saved_eur", "0")
        battery_tracker_test.assert_sensor_value("sensor.battery_pv_charging_cost_eur", "0")
        battery_tracker_test.assert_sensor_value("sensor.battery_grid_charging_cost_eur", "0")
        battery_tracker_test.assert_sensor_value("sensor.battery_discharge_savings_eur", "0")
        
        # Verify no errors were logged during initialization
        battery_tracker_test.assert_no_errors_logged()
        
        # Verify initialization log message
        battery_tracker_test.assert_log_contains("Battery Savings Tracker initialized")
    
    def test_complete_pv_charging_workflow(self, battery_tracker_test):
        """Test complete PV charging workflow using production functions"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up clean initial state with zero values
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "0.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.25}  # 25 ct/kWh
            }
        })
        battery_tracker_test.initialize_app()
        
        # Clear initial logs
        battery_tracker_test.clear_log_messages()
        
        # Simulate PV charging scenario (2.0 kWh from zero)
        battery_tracker_test.simulate_sensor_update(sensors['pv_energy'], "2.0")
        
        # Trigger the complete update cycle
        battery_tracker_test.simulate_update_cycle()
        
        # Verify PV charging cost calculation: 2.0 kWh * -7.8 ct/kWh = -0.156€
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_pv_charging_cost_eur", -0.156)
        
        # Verify other costs remain zero
        battery_tracker_test.assert_sensor_value("sensor.battery_grid_charging_cost_eur", "0")
        battery_tracker_test.assert_sensor_value("sensor.battery_discharge_savings_eur", "0")
        
        # Verify total savings calculation
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_total_money_saved_eur", -0.156)
        
        # Verify state sensors were updated
        battery_tracker_test.assert_sensor_value("sensor.battery_savings_last_pv_kwh", "2.0")
        
        # Verify logging shows correct delta
        battery_tracker_test.assert_log_contains("PV charging cost")
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 2.000 kWh, Grid: 0.000 kWh, Discharge: 0.000 kWh")
        battery_tracker_test.assert_no_errors_logged()
    
    def test_complete_grid_charging_workflow(self, battery_tracker_test):
        """Test complete grid charging workflow using production functions"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up clean initial state with zero values
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "0.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.30}  # 30 ct/kWh
            }
        })
        battery_tracker_test.initialize_app()
        
        # Clear initial logs
        battery_tracker_test.clear_log_messages()
        
        # Simulate grid charging scenario (1.5 kWh from zero)
        battery_tracker_test.simulate_sensor_update(sensors['grid_energy'], "1.5")
        
        # Trigger the complete update cycle
        battery_tracker_test.simulate_update_cycle()
        
        # Verify grid charging cost calculation: 1.5 kWh * -30 ct/kWh = -0.45€
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_grid_charging_cost_eur", -0.45)
        
        # Verify other costs remain zero
        battery_tracker_test.assert_sensor_value("sensor.battery_pv_charging_cost_eur", "0")
        battery_tracker_test.assert_sensor_value("sensor.battery_discharge_savings_eur", "0")
        
        # Verify total savings calculation
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_total_money_saved_eur", -0.45)
        
        # Verify state sensors were updated
        battery_tracker_test.assert_sensor_value("sensor.battery_savings_last_grid_kwh", "1.5")
        
        # Verify logging
        battery_tracker_test.assert_log_contains("Grid charging cost")
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 0.000 kWh, Grid: 1.500 kWh")
        battery_tracker_test.assert_no_errors_logged()
    
    def test_complete_discharge_workflow(self, battery_tracker_test):
        """Test complete battery discharge workflow using production functions"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up clean initial state with zero values
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "0.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.32}  # 32 ct/kWh
            }
        })
        battery_tracker_test.initialize_app()
        
        # Clear initial logs
        battery_tracker_test.clear_log_messages()
        
        # Simulate discharge scenario (3.0 kWh from zero)
        battery_tracker_test.simulate_sensor_update(sensors['discharge'], "3.0")
        
        # Trigger the complete update cycle
        battery_tracker_test.simulate_update_cycle()
        
        # Verify discharge savings calculation: 3.0 kWh * 32 ct/kWh = 0.96€
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_discharge_savings_eur", 0.96)
        
        # Verify other costs remain zero
        battery_tracker_test.assert_sensor_value("sensor.battery_pv_charging_cost_eur", "0")
        battery_tracker_test.assert_sensor_value("sensor.battery_grid_charging_cost_eur", "0")
        
        # Verify total savings calculation
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_total_money_saved_eur", 0.96)
        
        # Verify state sensors were updated
        battery_tracker_test.assert_sensor_value("sensor.battery_savings_last_discharge_kwh", "3.0")
        
        # Verify logging
        battery_tracker_test.assert_log_contains("Discharge savings")
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 0.000 kWh, Grid: 0.000 kWh, Discharge: 3.000 kWh")
        battery_tracker_test.assert_no_errors_logged()
    
    def test_combined_energy_flow_scenario(self, battery_tracker_test):
        """Test a realistic scenario with combined PV charging, grid charging, and discharge"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up clean initial state with zero values
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "0.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.28}  # 28 ct/kWh
            }
        })
        battery_tracker_test.initialize_app()
        
        # Clear initial logs
        battery_tracker_test.clear_log_messages()
        
        # Simulate combined energy flows from zero
        battery_tracker_test.simulate_sensor_update(sensors['pv_energy'], "1.5")
        battery_tracker_test.simulate_sensor_update(sensors['grid_energy'], "1.0")
        battery_tracker_test.simulate_sensor_update(sensors['discharge'], "2.5")
        
        # Trigger the complete update cycle
        battery_tracker_test.simulate_update_cycle()
        
        # Calculate expected values:
        # PV: 1.5 kWh * -7.8 ct/kWh = -0.117€
        # Grid: 1.0 kWh * -28 ct/kWh = -0.28€
        # Discharge: 2.5 kWh * 28 ct/kWh = 0.70€
        # Total: -0.117 + -0.28 + 0.70 = 0.303€
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_pv_charging_cost_eur", -0.117)
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_grid_charging_cost_eur", -0.28)
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_discharge_savings_eur", 0.70)
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_total_money_saved_eur", 0.303)
        
        # Verify all state sensors were updated
        battery_tracker_test.assert_sensor_value("sensor.battery_savings_last_pv_kwh", "1.5")
        battery_tracker_test.assert_sensor_value("sensor.battery_savings_last_grid_kwh", "1.0")
        battery_tracker_test.assert_sensor_value("sensor.battery_savings_last_discharge_kwh", "2.5")
        
        # Verify comprehensive logging
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 1.500 kWh, Grid: 1.000 kWh, Discharge: 2.500 kWh")
        battery_tracker_test.assert_log_contains("PV charging cost")
        battery_tracker_test.assert_log_contains("Grid charging cost")
        battery_tracker_test.assert_log_contains("Discharge savings")
        battery_tracker_test.assert_no_errors_logged()
    
    def test_counter_reset_handling(self, battery_tracker_test):
        """Test counter reset detection and handling using production functions"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up initial state with higher values
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "10.5"},
            sensors['grid_energy']: {"state": "5.2"},
            sensors['discharge']: {"state": "8.7"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.25}
            }
        })
        battery_tracker_test.initialize_app()
        
        # Run one update cycle to establish "last" values
        battery_tracker_test.simulate_update_cycle()
        
        # Clear logs to focus on reset handling
        battery_tracker_test.clear_log_messages()
        
        # Simulate counter resets (current < last)
        battery_tracker_test.simulate_sensor_update(sensors['pv_energy'], "0.5")  # Reset from 10.5
        battery_tracker_test.simulate_sensor_update(sensors['grid_energy'], "0.2")  # Reset from 5.2
        battery_tracker_test.simulate_sensor_update(sensors['discharge'], "1.1")  # Reset from 8.7
        
        # Trigger update cycle
        battery_tracker_test.simulate_update_cycle()
        
        # Verify reset detection was logged
        battery_tracker_test.assert_log_contains("Counter reset detected for PV charging")
        battery_tracker_test.assert_log_contains("Counter reset detected for Grid charging")
        battery_tracker_test.assert_log_contains("Counter reset detected for discharging")
        
        # Verify no cost calculations were made (deltas should be 0)
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 0.000 kWh, Grid: 0.000 kWh, Discharge: 0.000 kWh")
        
        # Verify no errors were logged
        battery_tracker_test.assert_no_errors_logged()
    
    def test_tibber_price_unavailable_handling(self, battery_tracker_test):
        """Test application behavior when Tibber price is unavailable"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up clean initial state with zero values and unavailable Tibber
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "0.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "unavailable",
                "attributes": {"current_price": None}
            }
        })
        battery_tracker_test.initialize_app()
        
        # Clear initial logs
        battery_tracker_test.clear_log_messages()
        
        # Simulate energy changes from zero
        battery_tracker_test.simulate_sensor_update(sensors['pv_energy'], "2.0")
        battery_tracker_test.simulate_sensor_update(sensors['grid_energy'], "1.0")
        battery_tracker_test.simulate_sensor_update(sensors['discharge'], "1.5")
        
        # Trigger update cycle
        battery_tracker_test.simulate_update_cycle()
        
        # Verify energy deltas are still calculated
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 2.000 kWh, Grid: 1.000 kWh, Discharge: 1.500 kWh")
        
        # Verify appropriate warnings for missing price
        battery_tracker_test.assert_log_contains("Could not get Tibber price, skipping charging cost calculation")
        battery_tracker_test.assert_log_contains("Could not get Tibber price, skipping discharge savings calculation")
        
        # Verify cost sensors remain unchanged (should still be 0)
        battery_tracker_test.assert_sensor_value("sensor.battery_pv_charging_cost_eur", "0")
        battery_tracker_test.assert_sensor_value("sensor.battery_grid_charging_cost_eur", "0")
        battery_tracker_test.assert_sensor_value("sensor.battery_discharge_savings_eur", "0")
        
        # Verify state sensors are still updated (energy tracking works without price)
        battery_tracker_test.assert_sensor_value("sensor.battery_savings_last_pv_kwh", "2.0")
        battery_tracker_test.assert_sensor_value("sensor.battery_savings_last_grid_kwh", "1.0")
        battery_tracker_test.assert_sensor_value("sensor.battery_savings_last_discharge_kwh", "1.5")
        
        # Verify no errors were logged (warnings are expected, errors are not)
        battery_tracker_test.assert_no_errors_logged()
    
    def test_realistic_daily_scenario(self, battery_tracker_test):
        """Test a complete realistic daily energy flow scenario"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up clean initial state with zero values
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "0.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.20}  # Start with 20 ct/kWh
            }
        })
        battery_tracker_test.initialize_app()
        
        # Clear initial logs
        battery_tracker_test.clear_log_messages()
        
        # Simulate a realistic daily scenario with multiple price changes
        # Morning PV charging (20 ct/kWh)
        battery_tracker_test.simulate_sensor_update(sensors['pv_energy'], "1.0")
        battery_tracker_test.simulate_update_cycle()
        
        # Midday high PV charging (15 ct/kWh)
        battery_tracker_test.simulate_sensor_update(sensors['tibber_price'], "available", {"current_price": 0.15})
        battery_tracker_test.simulate_sensor_update(sensors['pv_energy'], "4.0")  # 1.0 + 3.0
        battery_tracker_test.simulate_update_cycle()
        
        # Evening grid charging (25 ct/kWh)
        battery_tracker_test.simulate_sensor_update(sensors['tibber_price'], "available", {"current_price": 0.25})
        battery_tracker_test.simulate_sensor_update(sensors['grid_energy'], "2.0")
        battery_tracker_test.simulate_update_cycle()
        
        # Night discharge (35 ct/kWh)
        battery_tracker_test.simulate_sensor_update(sensors['tibber_price'], "available", {"current_price": 0.35})
        battery_tracker_test.simulate_sensor_update(sensors['discharge'], "4.0")
        battery_tracker_test.simulate_update_cycle()
        
        # Check that PV charging costs accumulated (should be negative)
        pv_cost_sensor_value = float(battery_tracker_test.get_sensor_value("sensor.battery_pv_charging_cost_eur"))
        assert pv_cost_sensor_value < 0, "PV charging should have negative cost"
        
        # Check that grid charging costs accumulated (should be negative)
        grid_cost_sensor_value = float(battery_tracker_test.get_sensor_value("sensor.battery_grid_charging_cost_eur"))
        assert grid_cost_sensor_value < 0, "Grid charging should have negative cost"
        
        # Check that discharge savings accumulated (should be positive)
        discharge_savings_value = float(battery_tracker_test.get_sensor_value("sensor.battery_discharge_savings_eur"))
        assert discharge_savings_value > 0, "Discharge should have positive savings"
        
        # Check that total savings is calculated correctly
        total_savings = float(battery_tracker_test.get_sensor_value("sensor.battery_total_money_saved_eur"))
        expected_total = pv_cost_sensor_value + grid_cost_sensor_value + discharge_savings_value
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_total_money_saved_eur", expected_total)
        
        # Verify comprehensive logging occurred
        battery_tracker_test.assert_log_contains("PV charging cost")
        battery_tracker_test.assert_log_contains("Grid charging cost")
        battery_tracker_test.assert_log_contains("Discharge savings")
        battery_tracker_test.assert_no_errors_logged()
    
    def test_application_restart_scenario(self, battery_tracker_test):
        """Test that the application handles restart scenarios correctly"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up clean initial state and initialize
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "0.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.25}
            }
        })
        battery_tracker_test.initialize_app()
        
        # Run some energy flows to establish state
        battery_tracker_test.simulate_sensor_update(sensors['pv_energy'], "1.0")
        battery_tracker_test.simulate_update_cycle()
        
        # Store current sensor values
        pv_cost_before = battery_tracker_test.get_sensor_value("sensor.battery_pv_charging_cost_eur")
        total_savings_before = battery_tracker_test.get_sensor_value("sensor.battery_total_money_saved_eur")
        
        # Simulate application restart by creating a new instance
        battery_tracker_test.teardown_app()
        battery_tracker_test.setup_app(BatterySavingsTracker, battery_tracker_test.get_default_config())
        
        # Set up the same sensor states (simulating persistence)
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "1.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.25}
            }
        })
        # Simulate that the cost sensors retained their values (as they would in real HA)
        battery_tracker_test.mock.set_state("sensor.battery_pv_charging_cost_eur", pv_cost_before)
        battery_tracker_test.mock.set_state("sensor.battery_total_money_saved_eur", total_savings_before)
        
        # Initialize the "restarted" application
        battery_tracker_test.initialize_app()
        
        # Verify the application doesn't recreate existing sensors
        battery_tracker_test.assert_sensor_value("sensor.battery_pv_charging_cost_eur", pv_cost_before)
        battery_tracker_test.assert_sensor_value("sensor.battery_total_money_saved_eur", total_savings_before)
        
        # Verify the application can continue processing new energy flows
        battery_tracker_test.clear_log_messages()
        battery_tracker_test.simulate_sensor_update(sensors['grid_energy'], "0.5")
        battery_tracker_test.simulate_update_cycle()
        
        # Verify new energy flows are processed correctly
        battery_tracker_test.assert_log_contains("Grid charging cost")
        battery_tracker_test.assert_no_errors_logged()
    
    def test_daily_savings_reset_at_midnight(self, battery_tracker_test):
        """Test that daily savings reset when date changes"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up initial state with some savings
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "0.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.25}
            }
        })
        
        # Set initial date to December 31st
        battery_tracker_test.set_mock_date(2023, 12, 31, 23, 30)
        battery_tracker_test.initialize_app()
        
        # Generate some savings on December 31st
        battery_tracker_test.simulate_sensor_update(sensors['discharge'], "2.0")
        battery_tracker_test.simulate_update_cycle()
        
        # Verify savings were recorded
        daily_savings_before = float(battery_tracker_test.get_sensor_value("sensor.battery_daily_money_saved_eur"))
        assert daily_savings_before > 0, "Should have daily savings before reset"
        
        # Clear logs to focus on reset behavior
        battery_tracker_test.clear_log_messages()
        
        # Advance time to January 1st (next day)
        battery_tracker_test.set_mock_date(2024, 1, 1, 0, 30)
        
        # Trigger update cycle to process date change
        battery_tracker_test.simulate_update_cycle()
        
        # Verify daily savings were reset
        battery_tracker_test.assert_time_based_sensor_reset("sensor.battery_daily_money_saved_eur")
        battery_tracker_test.assert_log_contains("Daily savings reset for new day: 2024-01-01")
        battery_tracker_test.assert_no_errors_logged()
    
    def test_weekly_savings_reset_on_monday(self, battery_tracker_test):
        """Test that weekly savings reset on Monday"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up initial state
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "0.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.30}
            }
        })
        
        # Set date to Sunday (end of week)
        battery_tracker_test.set_mock_date(2024, 1, 7, 23, 30)  # Sunday
        battery_tracker_test.initialize_app()
        
        # Generate some savings on Sunday
        battery_tracker_test.simulate_sensor_update(sensors['pv_energy'], "1.5")
        battery_tracker_test.simulate_update_cycle()
        
        # Verify weekly savings were recorded
        weekly_savings_before = float(battery_tracker_test.get_sensor_value("sensor.battery_weekly_money_saved_eur"))
        assert weekly_savings_before != 0, "Should have weekly savings before reset"
        
        # Clear logs
        battery_tracker_test.clear_log_messages()
        
        # Advance to Monday (new week)
        battery_tracker_test.set_mock_date(2024, 1, 8, 0, 30)  # Monday
        
        # Trigger update cycle
        battery_tracker_test.simulate_update_cycle()
        
        # Verify weekly savings were reset
        battery_tracker_test.assert_time_based_sensor_reset("sensor.battery_weekly_money_saved_eur")
        battery_tracker_test.assert_log_contains("Weekly savings reset for new week starting: 2024-01-08")
        battery_tracker_test.assert_no_errors_logged()
    
    def test_monthly_savings_reset_at_month_boundary(self, battery_tracker_test):
        """Test that monthly savings reset when month changes"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up initial state
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "0.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.28}
            }
        })
        
        # Set date to end of January
        battery_tracker_test.set_mock_date(2024, 1, 31, 23, 30)
        battery_tracker_test.initialize_app()
        
        # Generate some savings in January
        battery_tracker_test.simulate_sensor_update(sensors['grid_energy'], "2.0")
        battery_tracker_test.simulate_update_cycle()
        
        # Verify monthly savings were recorded
        monthly_savings_before = float(battery_tracker_test.get_sensor_value("sensor.battery_monthly_money_saved_eur"))
        assert monthly_savings_before != 0, "Should have monthly savings before reset"
        
        # Clear logs
        battery_tracker_test.clear_log_messages()
        
        # Advance to February 1st
        battery_tracker_test.set_mock_date(2024, 2, 1, 0, 30)
        
        # Trigger update cycle
        battery_tracker_test.simulate_update_cycle()
        
        # Verify monthly savings were reset
        battery_tracker_test.assert_time_based_sensor_reset("sensor.battery_monthly_money_saved_eur")
        battery_tracker_test.assert_log_contains("Monthly savings reset for new month: 2024-02")
        battery_tracker_test.assert_no_errors_logged()
    
    def test_yearly_savings_reset_at_year_boundary(self, battery_tracker_test):
        """Test that yearly savings reset when year changes"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up initial state
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "0.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.35}
            }
        })
        
        # Set date to end of 2023
        battery_tracker_test.set_mock_date(2023, 12, 31, 23, 30)
        battery_tracker_test.initialize_app()
        
        # Generate some savings in 2023
        battery_tracker_test.simulate_sensor_update(sensors['discharge'], "3.0")
        battery_tracker_test.simulate_update_cycle()
        
        # Verify yearly savings were recorded
        yearly_savings_before = float(battery_tracker_test.get_sensor_value("sensor.battery_yearly_money_saved_eur"))
        assert yearly_savings_before > 0, "Should have yearly savings before reset"
        
        # Clear logs
        battery_tracker_test.clear_log_messages()
        
        # Advance to 2024
        battery_tracker_test.set_mock_date(2024, 1, 1, 0, 30)
        
        # Trigger update cycle
        battery_tracker_test.simulate_update_cycle()
        
        # Verify yearly savings were reset
        battery_tracker_test.assert_time_based_sensor_reset("sensor.battery_yearly_money_saved_eur")
        battery_tracker_test.assert_log_contains("Yearly savings reset for new year: 2024")
        battery_tracker_test.assert_no_errors_logged()
    
    def test_energy_sensor_drop_and_recovery_pv_charging(self, battery_tracker_test):
        """Test that PV energy sensor drops are ignored and only increases are tracked"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up initial state with established PV energy
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "10.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.25}
            }
        })
        battery_tracker_test.initialize_app()
        
        # Run initial cycle to establish baseline
        battery_tracker_test.simulate_update_cycle()
        
        # Clear logs to focus on drop/recovery behavior
        battery_tracker_test.clear_log_messages()
        
        # Simulate sensor drop (counter reset scenario)
        battery_tracker_test.simulate_sensor_update(sensors['pv_energy'], "2.0")  # Drop from 10.0 to 2.0
        battery_tracker_test.simulate_update_cycle()
        
        # Verify drop was detected and ignored (default ignore_reset mode)
        battery_tracker_test.assert_energy_delta_ignored("Counter reset detected for PV charging")
        battery_tracker_test.assert_log_contains("Ignoring reset for PV charging, waiting for recovery")
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 0.000 kWh")
        
        # Verify no cost calculation was made for the drop
        pv_cost_after_drop = battery_tracker_test.get_sensor_value("sensor.battery_pv_charging_cost_eur")
        
        # Clear logs for recovery test
        battery_tracker_test.clear_log_messages()
        
        # Simulate recovery to higher value than original
        battery_tracker_test.simulate_sensor_update(sensors['pv_energy'], "12.0")  # Recover to 12.0 (10.0 increase from 2.0 reset baseline)
        battery_tracker_test.simulate_update_cycle()
        
        # Verify recovery was tracked correctly (with ignore_reset mode, tracks from reset value to recovery)
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 2.000 kWh")
        battery_tracker_test.assert_log_contains("PV charging cost")
        
        # Verify cost calculation for the recovery (2.0 kWh delta from 2.0 to 12.0)
        expected_pv_cost = battery_tracker_test.get_expected_pv_cost(2.0)  # 2.0 kWh from reset baseline
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_pv_charging_cost_eur",
                                                           float(pv_cost_after_drop) + expected_pv_cost)
        
        battery_tracker_test.assert_no_errors_logged()
    
    def test_energy_sensor_drop_and_recovery_ignore_mode(self, battery_tracker_test):
        """Test energy sensor drop/recovery with ignore_reset mode (original behavior)"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up with ignore_reset mode for PV counter resets
        config = battery_tracker_test.get_default_config()
        config['pv_counter_reset_mode'] = 'ignore_reset'
        battery_tracker_test.setup_app(BatterySavingsTracker, config)
        
        # Set up initial state with established PV energy
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "10.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.25}
            }
        })
        battery_tracker_test.initialize_app()
        
        # Run initial cycle to establish baseline
        battery_tracker_test.simulate_update_cycle()
        
        # Clear logs to focus on drop/recovery behavior
        battery_tracker_test.clear_log_messages()
        
        # Simulate sensor drop (counter reset scenario)
        battery_tracker_test.simulate_sensor_update(sensors['pv_energy'], "2.0")  # Drop from 10.0 to 2.0
        battery_tracker_test.simulate_update_cycle()
        
        # Verify drop was detected and ignored
        battery_tracker_test.assert_energy_delta_ignored("Counter reset detected for PV charging")
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 0.000 kWh")
        
        # Store cost after drop
        pv_cost_after_drop = battery_tracker_test.get_sensor_value("sensor.battery_pv_charging_cost_eur")
        
        # Clear logs for recovery test
        battery_tracker_test.clear_log_messages()
        
        # Simulate recovery to higher value than original
        battery_tracker_test.simulate_sensor_update(sensors['pv_energy'], "12.0")  # Recover to 12.0
        battery_tracker_test.simulate_update_cycle()
        
        # With ignore_reset mode, recovery should track from the reset baseline (2.0), so delta = 12.0 - 2.0 = 2.0
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 2.000 kWh")
        battery_tracker_test.assert_log_contains("PV charging cost")
        
        # Verify cost calculation for the recovery
        expected_pv_cost = battery_tracker_test.get_expected_pv_cost(2.0)  # 2.0 kWh from reset baseline
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_pv_charging_cost_eur",
                                                           float(pv_cost_after_drop) + expected_pv_cost)
        
        battery_tracker_test.assert_no_errors_logged()
    
    def test_energy_sensor_drop_and_recovery_preserve_delta_mode(self, battery_tracker_test):
        """Test energy sensor drop/recovery with daily_counter mode (for daily counters)"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up with daily_counter mode for PV counter resets
        config = battery_tracker_test.get_default_config()
        config['pv_counter_reset_mode'] = 'daily_counter'
        battery_tracker_test.setup_app(BatterySavingsTracker, config)
        
        # Set up initial state with established PV energy
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "10.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.25}
            }
        })
        battery_tracker_test.initialize_app()
        
        # Run initial cycle to establish baseline
        battery_tracker_test.simulate_update_cycle()
        
        # Clear logs to focus on drop/recovery behavior
        battery_tracker_test.clear_log_messages()
        
        # Simulate sensor drop (counter reset scenario - like daily reset at midnight)
        battery_tracker_test.simulate_sensor_update(sensors['pv_energy'], "2.0")  # Reset to 2.0 (new daily accumulation)
        battery_tracker_test.simulate_update_cycle()
        
        # With daily_counter mode, the reset value should be treated as the delta
        battery_tracker_test.assert_log_contains("Counter reset detected for PV charging")
        battery_tracker_test.assert_log_contains("Preserving delta for PV charging: estimated 2.0 kWh since reset")
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 2.000 kWh")
        battery_tracker_test.assert_log_contains("PV charging cost")
        
        # Verify cost calculation for the preserved delta (should be cumulative with initial cost)
        initial_cost = battery_tracker_test.get_expected_pv_cost(10.0)  # Initial 10.0 kWh cost
        preserved_delta_cost = battery_tracker_test.get_expected_pv_cost(2.0)  # 2.0 kWh preserved delta
        total_expected_cost = initial_cost + preserved_delta_cost
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_pv_charging_cost_eur", total_expected_cost)
        
        battery_tracker_test.assert_no_errors_logged()
    
    def test_energy_sensor_drop_and_recovery_grid_charging(self, battery_tracker_test):
        """Test that grid energy sensor drops are ignored and only increases are tracked"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up with explicit ignore_reset mode for grid counter resets
        config = battery_tracker_test.get_default_config()
        config['grid_counter_reset_mode'] = 'ignore_reset'
        battery_tracker_test.setup_app(BatterySavingsTracker, config)
        
        # Set up initial state with established grid energy
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "0.0"},
            sensors['grid_energy']: {"state": "8.0"},
            sensors['discharge']: {"state": "0.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.30}
            }
        })
        battery_tracker_test.initialize_app()
        
        # Run initial cycle to establish baseline
        battery_tracker_test.simulate_update_cycle()
        
        # Clear logs
        battery_tracker_test.clear_log_messages()
        
        # Simulate sensor drop
        battery_tracker_test.simulate_sensor_update(sensors['grid_energy'], "1.5")  # Drop from 8.0 to 1.5
        battery_tracker_test.simulate_update_cycle()
        
        # Verify drop was detected and ignored (no delta should be calculated)
        battery_tracker_test.assert_energy_delta_ignored("Counter reset detected for Grid charging")
        # With ignore_reset mode, no energy delta should be processed for the reset
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 0.000 kWh, Grid: 0.000 kWh")
        
        # Store cost after drop
        grid_cost_after_drop = battery_tracker_test.get_sensor_value("sensor.battery_grid_charging_cost_eur")
        
        # Clear logs for recovery test
        battery_tracker_test.clear_log_messages()
        
        # Simulate recovery to higher value
        battery_tracker_test.simulate_sensor_update(sensors['grid_energy'], "10.0")  # Recover to 10.0 (2.0 increase from 8.0 baseline)
        battery_tracker_test.simulate_update_cycle()
        
        # Verify recovery was tracked correctly
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 0.000 kWh, Grid: 2.000 kWh")
        battery_tracker_test.assert_log_contains("Grid charging cost")
        
        # Verify cost calculation for the recovery
        expected_grid_cost = battery_tracker_test.get_expected_grid_cost(2.0, 30.0)  # 2.0 kWh at 30 ct/kWh
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_grid_charging_cost_eur",
                                                           float(grid_cost_after_drop) + expected_grid_cost)
        
        battery_tracker_test.assert_no_errors_logged()
    
    def test_energy_sensor_drop_and_recovery_discharge(self, battery_tracker_test):
        """Test that discharge energy sensor drops are ignored and only increases are tracked"""
        # Set up with explicit ignore_reset mode for discharge counter resets
        config = battery_tracker_test.get_default_config()
        config['discharge_counter_reset_mode'] = 'ignore_reset'
        battery_tracker_test.setup_app(BatterySavingsTracker, config)
        
        # Set up initial state with established discharge energy
        sensors = battery_tracker_test.get_sensor_names()
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "0.0"},
            sensors['grid_energy']: {"state": "0.0"},
            sensors['discharge']: {"state": "15.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.32}
            }
        })
        battery_tracker_test.initialize_app()
        
        # Run initial cycle to establish baseline
        battery_tracker_test.simulate_update_cycle()
        
        # Clear logs
        battery_tracker_test.clear_log_messages()
        
        # Simulate sensor drop
        battery_tracker_test.simulate_sensor_update(sensors['discharge'], "3.0")  # Drop from 15.0 to 3.0
        battery_tracker_test.simulate_update_cycle()
        
        # Verify drop was detected and ignored
        battery_tracker_test.assert_energy_delta_ignored("Counter reset detected for discharging")
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 0.000 kWh, Grid: 0.000 kWh, Discharge: 0.000 kWh")
        
        # Store savings after drop
        discharge_savings_after_drop = battery_tracker_test.get_sensor_value("sensor.battery_discharge_savings_eur")
        
        # Clear logs for recovery test
        battery_tracker_test.clear_log_messages()
        
        # Simulate recovery to higher value
        battery_tracker_test.simulate_sensor_update(sensors['discharge'], "18.0")  # Recover to 18.0 (3.0 increase from 15.0 baseline)
        battery_tracker_test.simulate_update_cycle()
        
        # Verify recovery was tracked correctly
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 0.000 kWh, Grid: 0.000 kWh, Discharge: 3.000 kWh")
        battery_tracker_test.assert_log_contains("Discharge savings")
        
        # Verify savings calculation for the recovery
        expected_discharge_savings = battery_tracker_test.get_expected_discharge_savings(3.0, 32.0)  # 3.0 kWh at 32 ct/kWh
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_discharge_savings_eur",
                                                           float(discharge_savings_after_drop) + expected_discharge_savings)
        
        battery_tracker_test.assert_no_errors_logged()
    
    def test_multiple_sensor_drops_and_recoveries(self, battery_tracker_test):
        """Test handling of multiple simultaneous sensor drops and recoveries"""
        # Get configurable sensor names
        sensors = battery_tracker_test.get_sensor_names()
        
        # Set up initial state with all sensors having established values
        battery_tracker_test.set_initial_states({
            sensors['pv_energy']: {"state": "20.0"},
            sensors['grid_energy']: {"state": "15.0"},
            sensors['discharge']: {"state": "25.0"},
            sensors['tibber_price']: {
                "state": "available",
                "attributes": {"current_price": 0.28}
            }
        })
        battery_tracker_test.initialize_app()
        
        # Run initial cycle to establish baseline
        battery_tracker_test.simulate_update_cycle()
        
        # Clear logs
        battery_tracker_test.clear_log_messages()
        
        # Simulate all sensors dropping simultaneously
        battery_tracker_test.simulate_sensor_update(sensors['pv_energy'], "2.0")
        battery_tracker_test.simulate_sensor_update(sensors['grid_energy'], "1.0")
        battery_tracker_test.simulate_sensor_update(sensors['discharge'], "3.0")
        battery_tracker_test.simulate_update_cycle()
        
        # Verify all drops were detected and ignored
        battery_tracker_test.assert_energy_delta_ignored("Counter reset detected for PV charging")
        battery_tracker_test.assert_energy_delta_ignored("Counter reset detected for Grid charging")
        battery_tracker_test.assert_energy_delta_ignored("Counter reset detected for discharging")
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 0.000 kWh, Grid: 0.000 kWh, Discharge: 0.000 kWh")
        
        # Store values after drops
        pv_cost_after_drop = battery_tracker_test.get_sensor_value("sensor.battery_pv_charging_cost_eur")
        grid_cost_after_drop = battery_tracker_test.get_sensor_value("sensor.battery_grid_charging_cost_eur")
        discharge_savings_after_drop = battery_tracker_test.get_sensor_value("sensor.battery_discharge_savings_eur")
        
        # Clear logs for recovery test
        battery_tracker_test.clear_log_messages()
        
        # Simulate all sensors recovering to higher values
        battery_tracker_test.simulate_sensor_update(sensors['pv_energy'], "22.0")  # +2.0 from baseline 20.0
        battery_tracker_test.simulate_sensor_update(sensors['grid_energy'], "16.5")  # +1.5 from baseline 15.0
        battery_tracker_test.simulate_sensor_update(sensors['discharge'], "28.0")  # +3.0 from baseline 25.0
        battery_tracker_test.simulate_update_cycle()
        
        # Verify all recoveries were tracked correctly
        battery_tracker_test.assert_log_contains("Energy deltas - PV: 2.000 kWh, Grid: 1.500 kWh, Discharge: 3.000 kWh")
        battery_tracker_test.assert_log_contains("PV charging cost")
        battery_tracker_test.assert_log_contains("Grid charging cost")
        battery_tracker_test.assert_log_contains("Discharge savings")
        
        # Verify all cost calculations for recoveries
        expected_pv_cost = battery_tracker_test.get_expected_pv_cost(2.0)
        expected_grid_cost = battery_tracker_test.get_expected_grid_cost(1.5, 28.0)
        expected_discharge_savings = battery_tracker_test.get_expected_discharge_savings(3.0, 28.0)
        
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_pv_charging_cost_eur",
                                                           float(pv_cost_after_drop) + expected_pv_cost)
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_grid_charging_cost_eur",
                                                           float(grid_cost_after_drop) + expected_grid_cost)
        battery_tracker_test.assert_cost_calculation_correct("sensor.battery_discharge_savings_eur",
                                                           float(discharge_savings_after_drop) + expected_discharge_savings)
        
        battery_tracker_test.assert_no_errors_logged()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])