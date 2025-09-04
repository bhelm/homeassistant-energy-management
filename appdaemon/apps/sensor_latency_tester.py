import appdaemon.plugins.hass.hassapi as hass
import time
import statistics
from datetime import datetime, timedelta


class SensorLatencyTester(hass.Hass):
    """
    AppDaemon app to test sensor latency by writing to a sensor and measuring
    the delay between the write operation and receiving the state change event.
    """

    def initialize(self):
        """Initialize the latency tester app."""
        # Configuration parameters
        self.test_sensor = self.args.get("test_sensor", "input_number.latency_test_sensor")
        self.test_interval = self.args.get("test_interval", 30)  # seconds between tests
        self.max_latency_ms = self.args.get("max_latency_ms", 5000)  # max expected latency
        self.log_level = self.args.get("log_level", "INFO")
        self.statistics_window = self.args.get("statistics_window", 10)  # number of measurements for stats
        
        # Internal state
        self.pending_tests = {}  # Track pending latency tests
        self.latency_measurements = []  # Store recent measurements
        self.test_counter = 0
        
        # Set up logging level
        if hasattr(self, 'set_log_level'):
            self.set_log_level(self.log_level)
        
        self.log(f"Sensor Latency Tester initialized", level="INFO")
        self.log(f"Test sensor: {self.test_sensor}", level="INFO")
        self.log(f"Test interval: {self.test_interval} seconds", level="INFO")
        self.log(f"Max expected latency: {self.max_latency_ms} ms", level="INFO")
        
        # Check if test sensor exists, create if it doesn't
        self.setup_test_sensor()
        
        # Listen for state changes on the test sensor
        self.listen_state(self.on_sensor_change, self.test_sensor)
        
        # Schedule periodic latency tests
        self.run_every(self.perform_latency_test, "now+5", self.test_interval)
        
        # Schedule periodic statistics reporting
        self.run_every(self.report_statistics, "now+60", 300)  # Every 5 minutes

    def setup_test_sensor(self):
        """Ensure the test sensor exists and is properly configured."""
        try:
            # Check if sensor exists by trying to get its state
            current_state = self.get_state(self.test_sensor)
            if current_state is None:
                self.log(f"Test sensor {self.test_sensor} does not exist. Please create it manually in Home Assistant.", level="WARNING")
                self.log("You can create it by adding this to your configuration.yaml:", level="INFO")
                self.log("input_number:", level="INFO")
                self.log("  latency_test_sensor:", level="INFO")
                self.log("    name: 'Latency Test Sensor'", level="INFO")
                self.log("    min: 0", level="INFO")
                self.log("    max: 1000000", level="INFO")
                self.log("    step: 1", level="INFO")
            else:
                self.log(f"Test sensor {self.test_sensor} found with current value: {current_state}", level="INFO")
        except Exception as e:
            self.log(f"Error checking test sensor: {e}", level="ERROR")

    def perform_latency_test(self, kwargs):
        """Perform a latency test by writing to the sensor and measuring response time."""
        try:
            self.test_counter += 1
            test_id = f"test_{self.test_counter}_{int(time.time() * 1000)}"
            
            # Generate a unique test value (timestamp in milliseconds)
            test_value = int(time.time() * 1000) % 1000000  # Keep it within reasonable range
            
            # Record the start time with high precision
            start_time = time.time()
            
            # Store the pending test
            self.pending_tests[test_id] = {
                'start_time': start_time,
                'test_value': test_value,
                'expected_state': str(test_value)
            }
            
            # Write to the sensor
            self.call_service("input_number/set_value",
                            entity_id=self.test_sensor,
                            value=test_value)
            
            # Set up a timeout to clean up if no response is received
            self.run_in(self.cleanup_timeout_test, self.max_latency_ms / 1000, test_id=test_id)
            
        except Exception as e:
            self.log(f"Error performing latency test: {e}", level="ERROR")

    def on_sensor_change(self, entity, attribute, old, new, kwargs):
        """Handle sensor state changes and calculate latency."""
        try:
            if new is None:
                return
                
            current_time = time.time()
            new_value = str(new)
            
            # Find matching pending test
            matching_test = None
            test_id_to_remove = None
            
            for test_id, test_data in self.pending_tests.items():
                # Compare as numbers to handle float vs int comparison
                expected_num = float(test_data['expected_state'])
                new_num = float(new_value)
                if abs(expected_num - new_num) < 0.001:  # Allow for small floating point differences
                    matching_test = test_data
                    test_id_to_remove = test_id
                    break
            
            if matching_test:
                # Calculate latency
                latency_seconds = current_time - matching_test['start_time']
                latency_ms = latency_seconds * 1000
                
                # Store the measurement
                self.latency_measurements.append({
                    'timestamp': datetime.now(),
                    'latency_ms': latency_ms,
                    'test_value': matching_test['test_value']
                })
                
                # Keep only recent measurements
                if len(self.latency_measurements) > self.statistics_window * 2:
                    self.latency_measurements = self.latency_measurements[-self.statistics_window:]
                
                # Log the result - single concise line
                if latency_ms > self.max_latency_ms:
                    self.log(f"⚠️ Latency: {latency_ms:.1f} ms (HIGH - exceeds {self.max_latency_ms} ms threshold)", level="WARNING")
                else:
                    self.log(f"Latency: {latency_ms:.1f} ms", level="INFO")
                
                # Remove the completed test
                del self.pending_tests[test_id_to_remove]
                
        except Exception as e:
            self.log(f"Error handling sensor change: {e}", level="ERROR")

    def cleanup_timeout_test(self, kwargs):
        """Clean up tests that didn't receive a response within the timeout period."""
        test_id = kwargs.get('test_id')
        if test_id in self.pending_tests:
            test_data = self.pending_tests[test_id]
            timeout_ms = (time.time() - test_data['start_time']) * 1000
            
            self.log(f"⏰ Timeout: {timeout_ms:.1f} ms (no response)", level="WARNING")
            
            # Record timeout as a measurement
            self.latency_measurements.append({
                'timestamp': datetime.now(),
                'latency_ms': timeout_ms,
                'test_value': test_data['test_value'],
                'timeout': True
            })
            
            del self.pending_tests[test_id]

    def report_statistics(self, kwargs):
        """Report latency statistics."""
        try:
            if not self.latency_measurements:
                self.log("No latency measurements available for statistics", level="INFO")
                return
            
            # Get recent measurements (within statistics window)
            recent_measurements = self.latency_measurements[-self.statistics_window:]
            latencies = [m['latency_ms'] for m in recent_measurements if not m.get('timeout', False)]
            timeouts = [m for m in recent_measurements if m.get('timeout', False)]
            
            if latencies:
                avg_latency = statistics.mean(latencies)
                min_latency = min(latencies)
                max_latency = max(latencies)
                
                if len(latencies) > 1:
                    std_dev = statistics.stdev(latencies)
                    median_latency = statistics.median(latencies)
                else:
                    std_dev = 0
                    median_latency = latencies[0]
                
                self.log("=== LATENCY STATISTICS ===", level="INFO")
                self.log(f"Measurements: {len(latencies)} successful, {len(timeouts)} timeouts", level="INFO")
                self.log(f"Average latency: {avg_latency:.2f} ms", level="INFO")
                self.log(f"Median latency: {median_latency:.2f} ms", level="INFO")
                self.log(f"Min latency: {min_latency:.2f} ms", level="INFO")
                self.log(f"Max latency: {max_latency:.2f} ms", level="INFO")
                self.log(f"Standard deviation: {std_dev:.2f} ms", level="INFO")
                self.log("========================", level="INFO")
                
                # Create sensor entities for the statistics (optional)
                self.create_statistics_sensors(avg_latency, min_latency, max_latency, median_latency, std_dev, len(timeouts))
                
            else:
                self.log(f"No successful measurements in recent window. Timeouts: {len(timeouts)}", level="WARNING")
                
        except Exception as e:
            self.log(f"Error reporting statistics: {e}", level="ERROR")

    def create_statistics_sensors(self, avg, min_val, max_val, median, std_dev, timeout_count):
        """Create sensor entities for latency statistics (if supported)."""
        try:
            # Try to create/update sensor entities for the statistics
            # Note: This requires the sensor integration to be properly configured
            stats = {
                'sensor.latency_test_average': avg,
                'sensor.latency_test_minimum': min_val,
                'sensor.latency_test_maximum': max_val,
                'sensor.latency_test_median': median,
                'sensor.latency_test_std_dev': std_dev,
                'sensor.latency_test_timeouts': timeout_count
            }
            
            for entity_id, value in stats.items():
                try:
                    self.set_state(entity_id, state=round(value, 2), 
                                 attributes={
                                     'unit_of_measurement': 'ms' if 'timeout' not in entity_id else 'count',
                                     'friendly_name': entity_id.replace('sensor.latency_test_', 'Latency Test ').title(),
                                     'last_updated': datetime.now().isoformat()
                                 })
                except Exception as e:
                    self.log(f"Could not create sensor {entity_id}: {e}", level="DEBUG")
                    
        except Exception as e:
            self.log(f"Error creating statistics sensors: {e}", level="DEBUG")

    def terminate(self):
        """Clean up when the app is terminated."""
        self.log("Sensor Latency Tester terminated", level="INFO")
        if self.latency_measurements:
            self.log(f"Final measurement count: {len(self.latency_measurements)}", level="INFO")