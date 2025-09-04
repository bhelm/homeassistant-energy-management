# Battery Management System

A modular, SOLID-compliant battery management system for Home Assistant using AppDaemon.

## Overview

This system manages multiple batteries as a unified system, providing:
- Combined battery metrics (SoC, power, capacity)
- Smart power distribution across batteries
- Dynamic adjustment when batteries underperform
- Home Assistant entity interface for control
- Extensible architecture for different battery types

## Architecture

### Core Components

- **Battery** (Abstract) - Interface for all battery implementations
- **MarstekBattery** - Implementation for Marstek battery systems
- **BatteryCollection** - Manages multiple batteries as one system
- **BatteryManager** - Main AppDaemon orchestrator

### Key Principles

- **SOLID Compliance**: Single responsibility, proper separation of concerns
- **No Grid Logic**: Pure battery management only (grid compensation is separate)
- **KISS**: Keep it simple and straightforward
- **DRY**: Don't repeat yourself

## Home Assistant Entities

### Control Entities (Input)
- `number.battery_manager_target_power` - Set total battery power (-7500 to +7500W)
- `input_boolean.battery_manager_enabled` - Enable/disable system

### Status Entities (Output)
- `sensor.combined_battery_soc` - Overall SoC % (Total Remaining / Total Capacity × 100)
- `sensor.combined_battery_power` - Current total power (W)
- `sensor.combined_battery_capacity` - Total capacity (kWh)
- `sensor.combined_battery_remaining` - Total remaining energy (kWh)
- `sensor.battery_manager_status` - System status
- `sensor.battery_manager_target_power` - Current target power
- `sensor.battery_manager_actual_power` - Actual achieved power
- `sensor.battery_[name]_status` - Individual battery status

## Configuration

Add to `apps.yaml`:

```yaml
battery_manager:
  module: battery_manager.battery_manager
  class: BatteryManager
  update_interval: 2
  batteries:
    - name: Akku1
      type: marstek
      device_prefix: akku1
    - name: Akku2
      type: marstek
      device_prefix: akku2
```

## Usage Examples

### Manual Control
- Set `number.battery_manager_target_power` to `5000` → Charge at 5kW total
- Set `number.battery_manager_target_power` to `-3000` → Discharge at 3kW total
- Set `number.battery_manager_target_power` to `0` → Stop all batteries
- Toggle `input_boolean.battery_manager_enabled` to `off` → Emergency stop

### External System Control
```python
# Future grid compensation system can use the same interface
self.call_service("number/set_value",
                 entity_id="number.battery_manager_target_power", 
                 value=calculated_compensation_power)
```

## Smart Features

### Power Distribution
- **Proportional**: Power distributed based on battery capacity ratios
- **Limits Applied**: Respects individual battery charge/discharge limits
- **Dynamic Adjustment**: Monitors actual vs requested power after 10 seconds
- **Compensation**: Redistributes power when batteries underperform

### SoC Calculation
Combined SoC = (Total Remaining Energy / Total Available Capacity) × 100

This provides accurate system-wide state of charge based on actual energy content.

### Response Monitoring
- Monitors battery response to power commands
- 10-second timeout for power adjustment
- Automatic redistribution to compensating batteries
- Handles real-world scenarios (SoC limits, temperature effects, BMS restrictions)

## Battery Interface

To add a new battery type, implement the `Battery` abstract class:

```python
class NewBatteryType(Battery):
    def get_soc(self) -> float: ...
    def get_remaining_kwh(self) -> float: ...
    def get_total_capacity_kwh(self) -> float: ...
    def get_current_power_w(self) -> float: ...
    def set_power_w(self, power_w: float) -> bool: ...
    def get_max_charge_power_w(self) -> float: ...
    def get_max_discharge_power_w(self) -> float: ...
    def get_state(self) -> BatteryState: ...
    def is_available(self) -> bool: ...
```

## Testing

Run tests with:
```bash
cd config/appdaemon/apps/battery_manager
python -m pytest tests/
```

## Logging

The system provides detailed logging:
- **INFO**: System status updates every 60 seconds
- **DEBUG**: Individual battery power settings and calculations
- **WARNING**: Battery availability issues
- **ERROR**: Command failures and exceptions

## Future Extensions

This system is designed to be extended with:
- Additional battery types (just implement the Battery interface)
- Grid compensation system (separate component that uses target_power)
- Scheduling and price optimization
- Advanced power allocation strategies
- Battery health monitoring and alerts

## Separation from Grid Logic

This battery manager is intentionally separate from grid compensation logic. A future grid controller will:
1. Monitor `sensor.netz_gesamt_w`
2. Calculate required compensation
3. Set `number.battery_manager_target_power`

This separation follows SOLID principles and makes the system more maintainable and testable.


the problem that i want to solve is this:

for example, there is a 1000w grid import and i have 2 batteries. the system sees the improt and setts the batteries to export 1000w to offset that. 

one battery then exports 500w as told, the other battery only exports 300w. the system then needs to realize that the battery has responded (by providing 300w) but is not responding fully to 500w. it then should distribute the remaining 200w to the other battery. 

so far, so easy. but in the same time the system redistributes the 200w to the other battery, the grid import also raises and we need additional 400w of power. the 2ndb battery was not responding to 500w, the extra 400w should then go to the first battery that is deliverying the requiested power.

So the system essentially needs to learn how the batteries behave and adopt when that behavior changes. besicly it would need to predict the batteries response in order to compensate for it.

how can that be solved in a solid way?