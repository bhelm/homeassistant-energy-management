"""grid_balancer.py - Simple grid power balancer using battery storage"""
import appdaemon.plugins.hass.hassapi as hass
import sys
import os

# Add the grid_balancer directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from simple_adjustment_controller import SimpleAdjustmentController
from oscillation_detector import OscillationDetector
from wallbox_priority_controller import WallboxPriorityController

class GridBalancer(hass.Hass):
    """
    SINGLE RESPONSIBILITY: Balance grid power to zero using battery storage
    
    Logic: battery_target_power = -grid_power
    - Negative grid power (export) = charge battery
    - Positive grid power (import) = discharge battery
    """
    
    def initialize(self):
        """Initialize grid balancer with minimal configuration"""
        self.log("Initializing Grid Balancer")
        
        # CONFIGURATION
        self.grid_sensor = self.args.get('grid_sensor', 'sensor.netz_gesamt_w')
        self.battery_target_entity = self.args.get('battery_target_entity',
                                                  'input_number.battery_manager_target_power')
        self.enabled_entity = self.args.get('enabled_entity',
                                           'input_boolean.grid_balancer_enabled')
        self.allow_wallbox_battery_use_entity = self.args.get('allow_wallbox_battery_use_entity',
                                                             'input_boolean.grid_balancer_allow_wallbox_battery_use')
        self.surplus_buffer_w = self.args.get('surplus_buffer_w', 50)
        
        
        self.deadband_w = self.args.get('deadband_w', 25)  # Only react to changes >25W
        self.max_adjustment_w = self.args.get('max_adjustment_w', 2000)  # Limit adjustment size
        self.max_adjustment_interval_s = self.args.get('max_adjustment_interval_s', 15)  # Max time to wait before forcing adjustment
        
        # Initialize simple adjustment controller
        cooldown_seconds = self.args.get('adjustment_cooldown_s', 6.0)  # Increased cooldown
        self.adjustment_controller = SimpleAdjustmentController(cooldown_seconds, self.datetime)
        
        # Initialize oscillation detector if enabled
        oscillation_config = self.args.get('oscillation_detection', {})
        if oscillation_config.get('enabled', False):
            self.oscillation_detector = OscillationDetector(oscillation_config)
            self.log(f"✓ Oscillation detector enabled - min amplitude: {oscillation_config.get('min_amplitude_w', 1000)}W, "
                    f"baseline smoothing: {oscillation_config.get('baseline_smoothing_factor', 0.1)}")
        else:
            self.oscillation_detector = None
            self.log("Oscillation detector disabled")
        
        # Initialize wallbox priority controller if enabled
        wallbox_priority_config = self.args.get('wallbox_priority', {})
        if wallbox_priority_config.get('enabled', False):
            self.wallbox_priority_controller = WallboxPriorityController(wallbox_priority_config, self)
            self.log(f"✓ Wallbox priority controller enabled (SIMPLIFIED) - "
                    f"Power threshold: {wallbox_priority_config.get('wallbox_power_threshold_w', 100)}W, "
                    f"Reserve power: {wallbox_priority_config.get('wallbox_reserve_power_w', 1000)}W, "
                    f"Toggle entity: {self.allow_wallbox_battery_use_entity}")
        else:
            self.wallbox_priority_controller = None
            self.log("Wallbox priority controller disabled")
        
        # Fast sensor polling configuration
        self.use_fast_sensor_polling = self.args.get('use_fast_sensor_polling', False)
        self.poll_interval = self.args.get('poll_interval_ms', 500)  # 500ms for fast sensor polling
        
        # Setup event listeners or fast sensor polling
        self.log(f"DEBUG: use_fast_sensor_polling = {self.use_fast_sensor_polling}")
        
        if self.use_fast_sensor_polling:
            self.log("DEBUG: Setting up FAST SENSOR polling")
            self._setup_fast_sensor_polling()
        else:
            self.log("DEBUG: Setting up HOME ASSISTANT sensor listening")
        
        # Always set up enabled/disabled listener, conditionally set up grid power listener
        self._setup_listeners()
        polling_info = f"fast sensor polling every {self.poll_interval}ms" if self.use_fast_sensor_polling else f"listening to {self.grid_sensor}"
        self.log(f"Grid Balancer initialized - {polling_info}, "
                f"surplus buffer: {self.surplus_buffer_w}W, "
                f"simple cooldown: {cooldown_seconds}s between all adjustments")
    
    def _setup_listeners(self):
        """Setup event listeners"""
        # Always listen to enabled/disabled changes
        self.listen_state(self._on_enabled_change, self.enabled_entity)
        self.log(f"Listening to {self.enabled_entity} for enable/disable")
        
        # Listen to wallbox battery use toggle changes
        self.listen_state(self._on_wallbox_battery_use_toggle_change, self.allow_wallbox_battery_use_entity)
        self.log(f"Listening to {self.allow_wallbox_battery_use_entity} for wallbox battery use toggle changes")
        
        # Only listen to grid power changes if NOT using fast polling
        if not self.use_fast_sensor_polling:
            self.listen_state(self._on_grid_power_change, self.grid_sensor)
            self.log(f"Listening to {self.grid_sensor} for grid power changes")
        else:
            self.log(f"Fast polling mode - NOT listening to {self.grid_sensor} events")
    
    def _on_grid_power_change(self, entity, attribute, old, new, kwargs):
        """Simple grid balancing logic"""
        if not self._is_enabled():
            return
            
        try:
            grid_power = self._get_grid_power(new)
            self._process_grid_power_change(grid_power, "")
            
        except Exception as e:
            self.log(f"Error processing grid power change: {e}", level="ERROR")
    
    def _on_enabled_change(self, entity, attribute, old, new, kwargs):
        """Handle enable/disable state changes"""
        if new == "off":
            self._set_battery_target(0)  # Safe state = no battery action
            self.log("Grid Balancer disabled - battery target set to 0W")
        elif new == "on":
            # Re-evaluate current grid state
            current_grid = self.get_state(self.grid_sensor)
            if current_grid:
                self._on_grid_power_change(self.grid_sensor, None, None, current_grid, {})
                self.log("Grid Balancer enabled - re-evaluating current grid state")
    
    def _on_wallbox_battery_use_toggle_change(self, entity, attribute, old, new, kwargs):
        """Handle wallbox battery use toggle changes"""
        toggle_state = "ON" if new == "on" else "OFF"
        self.log(f"🔋 WALLBOX BATTERY USE TOGGLE changed: {old} → {new} ({toggle_state})")
        
        # Re-evaluate current grid state with new toggle setting
        if self._is_enabled():
            current_grid = self.get_state(self.grid_sensor)
            if current_grid:
                self._on_grid_power_change(self.grid_sensor, None, None, current_grid, {})
                self.log(f"Re-evaluating grid state with wallbox battery use toggle {toggle_state}")
    
    def _get_grid_power(self, state_value) -> float:
        """Grid power validation and conversion"""
        if state_value is None or state_value in ['unknown', 'unavailable']:
            raise ValueError(f"Invalid grid sensor state: {state_value}")
        return float(state_value)
    
    def _calculate_battery_target(self, grid_power: float, current_target: float) -> float:
        """
        Core balancing logic with wallbox priority, oscillation detection and incremental adjustment
        
        Args:
            grid_power: Current grid power (+ = import, - = export)
            current_target: Current battery target power (+ = charge, - = discharge)
            
        Returns:
            Battery target power (+ = charge, - = discharge)
        """
        # Calculate normal battery target first
        # Normal balancing logic
        # Calculate grid adjustment from desired export target
        # Desired state: grid_power = -surplus_buffer_w (negative = export)
        grid_adjustment = grid_power + self.surplus_buffer_w
        
        # Incremental adjustment: current target minus grid imbalance from desired state
        normal_battery_target = current_target - grid_adjustment
        
        # Apply basic safety limits (same as battery manager limits)
        normal_battery_target = max(-7500, min(7500, normal_battery_target))
        
        # Check wallbox priority - this can modify the battery target
        # Apply wallbox priority for both export (negative) and import (positive) scenarios
        if self.wallbox_priority_controller:
            allow_wallbox_battery_use = self._get_allow_wallbox_battery_use()
            allowed_battery_power, reason = self.wallbox_priority_controller.calculate_allowed_battery_power(
                grid_power, normal_battery_target, allow_wallbox_battery_use)
            if allowed_battery_power != normal_battery_target:
                self.log(f"🔌 WALLBOX PRIORITY (SIMPLIFIED) - {reason}")
                # Apply wallbox priority adjustment, but still check oscillation detection
                battery_target = allowed_battery_power
            else:
                battery_target = normal_battery_target
        else:
            battery_target = normal_battery_target
        
        # Feed power reading to oscillation detector if enabled
        if self.oscillation_detector:
            self.oscillation_detector.add_power_reading(grid_power, self.datetime())
            
            # Check for oscillations and use stabilized target if detected
            if self.oscillation_detector.is_oscillating():
                # Get stabilized target from detector
                stabilized_target = self.oscillation_detector.get_stabilized_target(battery_target)
                
                # Enhanced logging with baseline shift information
                osc_info = self.oscillation_detector.get_oscillation_info()
                baseline_shift_info = ""
                if osc_info['baseline_shift_detected']:
                    shift_magnitude = osc_info['baseline_shift_magnitude_w']
                    baseline_shift_info = f", Baseline Shift: {shift_magnitude:+.0f}W"
                
                self.log(f"🌊 OSCILLATION DETECTED - Amplitude: {osc_info['amplitude_w']:.0f}W, "
                        f"Baseline: {osc_info['baseline_w']:.0f}W{baseline_shift_info}, "
                        f"Priority Target: {battery_target:.0f}W → Stabilized: {stabilized_target:.0f}W")
                
                # Apply safety limits and return stabilized target
                return max(-7500, min(7500, stabilized_target))
        
        return battery_target
    
    def _get_current_battery_target(self) -> float:
        """Current battery target validation and conversion"""
        state_value = self.get_state(self.battery_target_entity)
        if state_value is None or state_value in ['unknown', 'unavailable']:
            self.log(f"Battery target entity unavailable: {state_value}, using 0W", level="WARNING")
            return 0.0
        return float(state_value)
    
    def _set_battery_target(self, target_power: float) -> bool:
        """Set battery target power"""
        try:
            self.call_service("input_number/set_value",
                            entity_id=self.battery_target_entity,
                            value=target_power)
            return True
        except Exception as e:
            self.log(f"Failed to set battery target: {e}", level="ERROR")
            return False
    
    # Removed _can_make_adjustment - now handled by AdjustmentController
    
    def _is_enabled(self) -> bool:
        """Check if grid balancer is enabled"""
        enabled_state = self.get_state(self.enabled_entity)
        return enabled_state == "on"
    
    def _get_allow_wallbox_battery_use(self) -> bool:
        """Check if wallbox battery use is allowed"""
        toggle_state = self.get_state(self.allow_wallbox_battery_use_entity)
        return toggle_state == "on"
    
    def _process_grid_power_change(self, grid_power: float, source_tag: str):
        """
        Common processing logic for grid power changes
        
        Args:
            grid_power: Current grid power reading
            source_tag: Tag to identify the source (e.g., "[FAST SMOOTHED]")
        """
        current_target = self._get_current_battery_target()
        battery_target = self._calculate_battery_target(grid_power, current_target)
        
        # Check if adjustment controller allows new adjustment
        if not self.adjustment_controller.should_allow_adjustment(grid_power, battery_target, current_target):
            status_info = self.adjustment_controller.get_status_info()
            change_magnitude = abs(battery_target - current_target)
            time_since_last = status_info.get('time_since_last_adjustment', 0)
            cooldown_time = status_info.get('cooldown_seconds', 6.0)
            
            # Enhanced logging for oscillation detection during cooldown
            oscillation_info = ""
            if self.oscillation_detector and self.oscillation_detector.is_oscillating():
                osc_info = self.oscillation_detector.get_oscillation_info()
                oscillation_info = f" [OSC: {osc_info['amplitude_w']:.0f}W amplitude, damping: {osc_info['damping_factor']}]"
            
            cooldown_tag = f"⏱️ {source_tag.strip()} COOLDOWN" if source_tag else "⏱️ COOLDOWN"
            self.log(f"GRID: {grid_power:+.0f}W - {cooldown_tag} - Waiting {time_since_last:.1f}s/{cooldown_time:.1f}s. "
                    f"Change: {change_magnitude:.0f}W blocked until cooldown complete{oscillation_info}")
            return
        
        success = self._set_battery_target(battery_target)
        
        # Record adjustment for simple cooldown tracking if successful
        if success:
            self.adjustment_controller.record_adjustment(
                grid_power, battery_target, current_target, self.datetime()
            )
        
        # Generate logging information
        grid_state = "EXPORT" if grid_power < 0 else "IMPORT" if grid_power > 0 else "BALANCED"
        battery_action = "CHARGE" if battery_target > 0 else "DISCHARGE" if battery_target < 0 else "IDLE"
        adjustment = battery_target - current_target
        
        # Create log message with appropriate tag
        balance_tag = f"Grid Balance {source_tag}" if source_tag else "Grid Balance"
        self.log(f"GRID: {grid_power:+.0f}W - {balance_tag} - Grid: {grid_power:+.0f}W ({grid_state}), "
                f"Battery: {current_target:+.0f}W → {battery_target:+.0f}W ({battery_action}), "
                f"Adjustment: {adjustment:+.0f}W {'✓' if success else '✗'}")

    def terminate(self):
        """Clean shutdown"""
        self.log("Grid Balancer terminated")
    
    
    def _setup_fast_sensor_polling(self):
        """Setup fast sensor polling - update HA sensor every 500ms then process"""
        try:
            # Convert ms to seconds for AppDaemon
            update_interval_seconds = self.poll_interval / 1000.0
            
            # Start the update timer
            self.run_every(
                self._fast_sensor_update,
                "now",  # Start immediately
                update_interval_seconds
            )
            
            self.log(f"✓ Fast sensor polling started - updating {self.grid_sensor} every {self.poll_interval}ms")
                
        except Exception as e:
            self.log(f"✗ Fast sensor polling setup failed: {e}, falling back to sensor listening", level="ERROR")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}", level="ERROR")
            self._setup_listeners()
    
    def _fast_sensor_update(self, kwargs):
        """Update the HA sensor and process directly for fast response"""
        try:
            # Update sensor
            self.call_service(
                "homeassistant/update_entity",
                entity_id=self.grid_sensor
            )
            
            # Process directly without waiting for events (for fast response)
            if self._is_enabled():
                grid_power_state = self.get_state(self.grid_sensor)
                if grid_power_state is not None and grid_power_state not in ['unknown', 'unavailable']:
                    grid_power = self._get_grid_power(grid_power_state)
                    self._process_grid_power_change(grid_power, "[FAST]")
                    
        except Exception as e:
            self.log(f"Error in fast sensor update: {e}", level="ERROR")