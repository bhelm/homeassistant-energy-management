# Battery Savings Tracker

An AppDaemon app for Home Assistant that tracks battery energy flows and calculates financial savings by monitoring PV surplus charging, grid import charging, and battery discharge with dynamic pricing.

## Overview

The Battery Savings Tracker provides comprehensive financial tracking of your home battery system by:

1. **Tracking charging costs** - Differentiates between PV surplus charging (opportunity cost) and grid import charging (actual cost)
2. **Calculating discharge savings** - Uses dynamic Tibber pricing to calculate savings from battery discharge
3. **Creating persistent sensors** - All data survives app restarts and Home Assistant reboots
4. **Time-based tracking** - Provides daily, weekly, monthly, and yearly savings breakdowns
5. **Handling counter resets** - Robust handling of sensor resets with configurable strategies

## Features

### Financial Tracking
- **PV Surplus Charging Cost**: Tracks opportunity cost of using PV surplus for battery charging (default: -7.8ct/kWh)
- **Grid Import Charging Cost**: Uses dynamic Tibber pricing for grid-powered battery charging
- **Battery Discharge Savings**: Calculates savings using current Tibber electricity prices
- **Total Net Savings**: Combines all costs and savings for overall financial benefit

### Time-Based Analytics
- **Daily Savings**: Resets automatically at midnight
- **Weekly Savings**: Resets every Monday
- **Monthly Savings**: Resets on the first day of each month
- **Yearly Savings**: Resets on January 1st

### Robust Data Handling
- **Counter Reset Detection**: Automatically detects when energy counters reset
- **Configurable Reset Modes**: Choose how to handle counter resets per sensor type
- **Persistent State**: All tracking data survives app and Home Assistant restarts

## Dependencies

### Required Apps
- **Energy Distributor App**: Must be running to provide PV/Grid energy split data
  - Creates: [`sensor.battery_combined_pv_energy`](config/appdaemon/apps/energy_distributor.py)
  - Creates: [`sensor.battery_combined_grid_energy`](config/appdaemon/apps/energy_distributor.py)

### Required Sensors
- **Tibber Integration**: For dynamic electricity pricing
  - Required: [`sensor.tibber_future_statistics`](configuration.yaml) with `current_price` attribute
- **Combined Battery Discharge**: Template sensor for total battery discharge
  - Required: [`sensor.combined_battery_total_discharging_kwh`](configuration.yaml)

## Installation

1. **Copy the app files** to your AppDaemon apps directory:
   ```
   config/appdaemon/apps/battery_savings_tracker/
   ├── __init__.py
   ├── battery_savings_tracker.py
   └── README.md
   ```

2. **Add configuration** to your [`apps.yaml`](../apps.yaml):
   ```yaml
   battery_savings_tracker:
     module: battery_savings_tracker.battery_savings_tracker
     class: BatterySavingsTracker
     update_interval: 300
     pv_surplus_rate_ct: 7.8
     
     # Input sensor configuration (optional - uses defaults if not specified)
     battery_pv_energy_sensor: sensor.battery_combined_pv_energy
     battery_grid_energy_sensor: sensor.battery_combined_grid_energy
     battery_discharge_sensor: sensor.combined_battery_total_discharging_kwh
     tibber_price_sensor: sensor.tibber_future_statistics
   ```

3. **Restart AppDaemon** to load the app

## Configuration

### Basic Configuration

```yaml
battery_savings_tracker:
  module: battery_savings_tracker.battery_savings_tracker
  class: BatterySavingsTracker
  update_interval: 300              # Update interval in seconds (default: 300)
  pv_surplus_rate_ct: 7.8          # PV surplus opportunity cost in ct/kWh (default: 7.8)
  
  # Input sensor configuration (optional - defaults shown)
  battery_pv_energy_sensor: sensor.battery_combined_pv_energy
  battery_grid_energy_sensor: sensor.battery_combined_grid_energy
  battery_discharge_sensor: sensor.combined_battery_total_discharging_kwh
  tibber_price_sensor: sensor.tibber_future_statistics
```

### Advanced Configuration with Counter Reset Handling

```yaml
battery_savings_tracker:
  module: battery_savings_tracker.battery_savings_tracker
  class: BatterySavingsTracker
  update_interval: 300
  pv_surplus_rate_ct: 7.8
  
  # Input sensor configuration (customize for your setup)
  battery_pv_energy_sensor: sensor.my_custom_pv_energy
  battery_grid_energy_sensor: sensor.my_custom_grid_energy
  battery_discharge_sensor: sensor.my_custom_discharge_energy
  tibber_price_sensor: sensor.my_custom_price_sensor
  
  # Counter reset handling modes
  pv_counter_reset_mode: ignore_reset        # How to handle PV counter resets
  grid_counter_reset_mode: ignore_reset      # How to handle grid counter resets
  discharge_counter_reset_mode: ignore_reset # How to handle discharge counter resets
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `update_interval` | int | 300 | Update frequency in seconds (5 minutes recommended) |
| `pv_surplus_rate_ct` | float | 7.8 | Opportunity cost of PV surplus charging in ct/kWh |
| `battery_pv_energy_sensor` | string | "sensor.battery_combined_pv_energy" | Sensor for PV energy used for battery charging |
| `battery_grid_energy_sensor` | string | "sensor.battery_combined_grid_energy" | Sensor for grid energy used for battery charging |
| `battery_discharge_sensor` | string | "sensor.combined_battery_total_discharging_kwh" | Sensor for total battery discharge energy |
| `tibber_price_sensor` | string | "sensor.tibber_future_statistics" | Sensor for dynamic electricity pricing |
| `pv_counter_reset_mode` | string | "ignore_reset" | How to handle PV energy counter resets |
| `grid_counter_reset_mode` | string | "ignore_reset" | How to handle grid energy counter resets |
| `discharge_counter_reset_mode` | string | "ignore_reset" | How to handle discharge counter resets |

### Counter Reset Modes

The app supports three different strategies for handling counter resets:

#### `ignore_reset` (Recommended)
- **Behavior**: Ignores counter resets completely, waits for counter to recover
- **Use Case**: Best for temporary sensor outages or brief counter resets
- **Example**: Counter goes from 100 kWh → 0 kWh → 105 kWh, only the 5 kWh increase is tracked

#### `continue_from_reset`
- **Behavior**: Treats reset value as new starting point
- **Use Case**: When counters permanently reset and won't recover
- **Example**: Counter goes from 100 kWh → 5 kWh, the 5 kWh is treated as new energy

#### `daily_counter`
- **Behavior**: Treats reset value as actual energy delta (for daily counters)
- **Use Case**: For sensors that reset daily at midnight
- **Example**: Daily counter shows 15 kWh at reset, this 15 kWh is added to savings

## Configurable Input Sensors

The Battery Savings Tracker now supports configurable input sensor names, allowing you to customize which sensors are used for tracking energy flows. This makes the app more flexible and adaptable to different Home Assistant setups.

### Default Sensor Configuration

By default, the app uses these sensor names:
- **PV Energy**: `sensor.battery_combined_pv_energy` (from Energy Distributor app)
- **Grid Energy**: `sensor.battery_combined_grid_energy` (from Energy Distributor app)
- **Discharge Energy**: `sensor.combined_battery_total_discharging_kwh` (template sensor)
- **Price Data**: `sensor.tibber_future_statistics` (Tibber integration)

### Custom Sensor Configuration

You can override any or all of these sensors in your configuration:

```yaml
battery_savings_tracker:
  module: battery_savings_tracker.battery_savings_tracker
  class: BatterySavingsTracker
  
  # Custom sensor names for your setup
  battery_pv_energy_sensor: sensor.my_solar_battery_energy
  battery_grid_energy_sensor: sensor.my_grid_battery_energy
  battery_discharge_sensor: sensor.my_battery_discharge_total
  tibber_price_sensor: sensor.my_electricity_price
```

### Sensor Requirements

Regardless of the sensor names you choose, they must meet these requirements:

#### PV and Grid Energy Sensors
- **Unit**: kWh
- **State Class**: `total_increasing` or `total`
- **Behavior**: Cumulative energy counters that increase over time
- **Source**: Typically from energy distributor or battery management systems

#### Discharge Energy Sensor
- **Unit**: kWh
- **State Class**: `total_increasing`
- **Behavior**: Cumulative discharge counter that increases over time
- **Source**: Battery inverter or combined template sensor

#### Price Sensor
- **Attributes**: Must have `current_price` attribute in EUR/kWh
- **Source**: Dynamic pricing integration (Tibber, Nordpool, etc.)
- **Example**: `sensor.tibber_future_statistics` with `current_price: 0.25`

### Migration from Hardcoded Sensors

If you're upgrading from a previous version with hardcoded sensor names, the app will continue to work without any configuration changes. The new sensor configuration parameters are optional and use the original hardcoded names as defaults.

## Created Sensors

The app creates the following sensors in Home Assistant:

### Financial Tracking Sensors

| Sensor | Description | Unit | State Class |
|--------|-------------|------|-------------|
| [`sensor.battery_total_money_saved_eur`](battery_savings_tracker.py:72) | Total net savings (discharge savings - charging costs) | € | total |
| [`sensor.battery_pv_charging_cost_eur`](battery_savings_tracker.py:73) | Cumulative PV charging opportunity cost | € | total |
| [`sensor.battery_grid_charging_cost_eur`](battery_savings_tracker.py:74) | Cumulative grid charging cost | € | total |
| [`sensor.battery_discharge_savings_eur`](battery_savings_tracker.py:75) | Cumulative discharge savings | € | total_increasing |

### Time-Based Tracking Sensors

| Sensor | Description | Unit | Reset Period |
|--------|-------------|------|--------------|
| [`sensor.battery_daily_money_saved_eur`](battery_savings_tracker.py:78) | Daily savings | € | Midnight |
| [`sensor.battery_weekly_money_saved_eur`](battery_savings_tracker.py:79) | Weekly savings | € | Monday |
| [`sensor.battery_monthly_money_saved_eur`](battery_savings_tracker.py:80) | Monthly savings | € | 1st of month |
| [`sensor.battery_yearly_money_saved_eur`](battery_savings_tracker.py:81) | Yearly savings | € | January 1st |

### State Management Sensors

| Sensor | Description | Unit | Purpose |
|--------|-------------|------|---------|
| [`sensor.battery_savings_last_run_timestamp`](battery_savings_tracker.py:66) | Last update timestamp | - | Monitoring |
| [`sensor.battery_savings_last_pv_kwh`](battery_savings_tracker.py:67) | Last PV energy value | kWh | Delta calculation |
| [`sensor.battery_savings_last_grid_kwh`](battery_savings_tracker.py:68) | Last grid energy value | kWh | Delta calculation |
| [`sensor.battery_savings_last_discharge_kwh`](battery_savings_tracker.py:69) | Last discharge energy value | kWh | Delta calculation |
| [`sensor.battery_savings_last_reset_date`](battery_savings_tracker.py:84) | Last time-based reset date | - | Time tracking |

## Usage Examples

### Basic Dashboard Card

```yaml
type: entities
title: Battery Savings
entities:
  - sensor.battery_total_money_saved_eur
  - sensor.battery_daily_money_saved_eur
  - sensor.battery_weekly_money_saved_eur
  - sensor.battery_monthly_money_saved_eur
```

### Detailed Financial Breakdown

```yaml
type: entities
title: Battery Financial Details
entities:
  - entity: sensor.battery_discharge_savings_eur
    name: "Discharge Savings"
  - entity: sensor.battery_pv_charging_cost_eur
    name: "PV Charging Cost"
  - entity: sensor.battery_grid_charging_cost_eur
    name: "Grid Charging Cost"
  - entity: sensor.battery_total_money_saved_eur
    name: "Net Savings"
```

### Historical Chart

```yaml
type: history-graph
title: Battery Savings Trend
entities:
  - sensor.battery_total_money_saved_eur
  - sensor.battery_discharge_savings_eur
hours_to_show: 168  # 1 week
```

## Pricing Logic

### PV Surplus Charging
- **Cost**: Configurable opportunity cost (default: 7.8ct/kWh)
- **Rationale**: PV surplus used for battery charging could have been exported
- **Calculation**: `PV_energy_kWh × (-pv_surplus_rate_ct) / 100`

### Grid Import Charging
- **Cost**: Dynamic Tibber pricing
- **Source**: [`sensor.tibber_future_statistics`](configuration.yaml) `current_price` attribute
- **Calculation**: `Grid_energy_kWh × (-tibber_price_ct) / 100`

### Battery Discharge Savings
- **Savings**: Dynamic Tibber pricing
- **Source**: [`sensor.tibber_future_statistics`](configuration.yaml) `current_price` attribute
- **Calculation**: `Discharge_energy_kWh × tibber_price_ct / 100`

### Total Savings Formula
```
Total Savings = Discharge Savings + PV Charging Cost + Grid Charging Cost
```
*Note: Charging costs are negative values, so they reduce total savings*

## Troubleshooting

### Common Issues

#### 1. "Could not get all current energy values"
**Cause**: Required sensors are unavailable or returning invalid values

**Solution**:
- Verify Energy Distributor app is running
- Check that these sensors exist and have valid values:
  - [`sensor.battery_combined_pv_energy`](config/appdaemon/apps/energy_distributor.py)
  - [`sensor.battery_combined_grid_energy`](config/appdaemon/apps/energy_distributor.py)
  - [`sensor.combined_battery_total_discharging_kwh`](configuration.yaml)

#### 2. "Could not get Tibber price"
**Cause**: Tibber integration not working or sensor unavailable

**Solution**:
- Verify Tibber integration is installed and configured
- Check [`sensor.tibber_future_statistics`](configuration.yaml) exists
- Ensure sensor has `current_price` attribute

#### 3. Savings not accumulating
**Cause**: Counter reset mode preventing updates

**Solution**:
- Check AppDaemon logs for "Counter reset detected" messages
- Consider changing reset mode from `ignore_reset` to `continue_from_reset`
- Verify energy sensors are increasing over time

#### 4. Time-based sensors not resetting
**Cause**: Date tracking sensor issues

**Solution**:
- Check [`sensor.battery_savings_last_reset_date`](battery_savings_tracker.py:84) has valid date
- Restart AppDaemon to reinitialize date tracking
- Check system timezone settings

### Debug Information

Enable debug logging in [`appdaemon.yaml`](../appdaemon.yaml):

```yaml
logs:
  battery_savings_tracker:
    name: BatterySavingsTracker
    level: DEBUG
```

### Log Messages to Monitor

- `"Starting savings update..."` - Normal operation
- `"Counter reset detected"` - Sensor reset handling
- `"Energy deltas - PV: X kWh, Grid: Y kWh, Discharge: Z kWh"` - Energy changes
- `"Total savings updated"` - Financial calculations

## Integration with Other Apps

### Energy Distributor Dependency
The Battery Savings Tracker requires the Energy Distributor app to provide accurate PV/Grid energy split:

```yaml
# Required in apps.yaml
energy_distributor:
  module: energy_distributor
  class: EnergyDistributor
  # ... configuration
  devices:
    battery_combined:
      power_sensor: sensor.akku_charging_in_w
      friendly_name: "Combined Battery Charging"
```

### Template Sensors Required
Add to [`configuration.yaml`](../../configuration.yaml):

```yaml
template:
  - sensor:
      - name: "Combined Battery Total Discharging kWh"
        unique_id: combined_battery_total_discharging_kwh
        state: >
          {{ (states('sensor.akku1_total_discharging_kwh') | float(0)) +
             (states('sensor.akku2_total_discharging_kwh') | float(0)) +
             (states('sensor.akku3_total_discharging_kwh') | float(0)) }}
        unit_of_measurement: "kWh"
        device_class: energy
        state_class: total_increasing
```

## Version History

- **v1.0**: Initial release with basic savings tracking
- **v1.1**: Added counter reset handling with configurable modes
- **v1.2**: Added time-based savings tracking (daily/weekly/monthly/yearly)
- **v1.3**: Enhanced error handling and logging
- **v1.4**: Added configurable input sensor names for flexible sensor mapping

## License

This project is part of a Home Assistant AppDaemon setup for home energy management.