"""
Test für Akkuaufladung mit oszillierendem PV-Überschuss
Simuliert Szenarien wo der Akku geladen werden soll, aber der verfügbare Überschuss oszilliert
"""
import unittest
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path to import oscillation_detector
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from oscillation_detector import OscillationDetector


class TestChargingWithOscillatingSurplus(unittest.TestCase):
    """Test Oszillationsdämpfung beim Laden mit oszillierendem Überschuss"""
    
    def setUp(self):
        """Standard Konfiguration für Tests"""
        self.config = {
            'enabled': True,
            'min_amplitude_w': 100.0,
            'min_cycles': 2,
            'max_cycle_duration_s': 10.0,
            'history_duration_s': 30.0,
            'stabilization_factor': 1.1,
            'detection_sensitivity': 0.8,
            'baseline_smoothing_factor': 0.6,
            'baseline_shift_threshold_w': 150.0,
            'damping_factor': 0.5,
            'damping_strategy': 'proportional'
        }
        self.detector = OscillationDetector(self.config)
        self.base_time = datetime.now()
    
    def test_charging_with_oscillating_pv_surplus(self):
        """
        Test: Akku soll mit PV-Überschuss geladen werden, aber PV oszilliert
        
        Szenario:
        - PV-Anlage produziert 2000W
        - Grundlast: 500W konstant
        - Verfügbarer Überschuss: 1500W
        - Aber PV oszilliert ±300W (Wolken, etc.)
        - Netz oszilliert zwischen -1200W und -1800W (Export)
        - Akku sollte mit ~1500W geladen werden, gedämpft
        """
        print("\n=== TEST: Laden mit oszillierendem PV-Überschuss ===")
        
        # Simuliere oszillierenden PV-Überschuss
        # Netz oszilliert zwischen -1200W (wenig Export) und -1800W (viel Export)
        # Baseline sollte bei -1500W liegen (mittlerer Export)
        
        oscillation_data = []
        for i in range(20):
            if i % 4 < 2:
                power = -1200.0  # Weniger Export (weniger PV)
            else:
                power = -1800.0  # Mehr Export (mehr PV)
            
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            oscillation_data.append((power, timestamp))
        
        # Daten an Detektor senden
        for power, timestamp in oscillation_data:
            self.detector.add_power_reading(power, timestamp)
        
        # Oszillation sollte erkannt werden
        self.assertTrue(self.detector.is_oscillating(), "Sollte PV-Oszillation erkennen")
        
        info = self.detector.get_oscillation_info()
        baseline = info['baseline_w']
        amplitude = info['amplitude_w']
        
        print(f"Erkannte Baseline: {baseline}W (erwartet: ~-1500W)")
        print(f"Erkannte Amplitude: {amplitude}W (erwartet: ~600W)")
        
        # Baseline sollte bei ca. -1500W liegen (mittlerer Export)
        self.assertLess(baseline, -1200.0, "Baseline sollte negativ sein (Export)")
        self.assertGreater(baseline, -1800.0, "Baseline sollte nicht zu negativ sein")
        
        # Amplitude sollte ca. 600W sein (1800-1200=600)
        self.assertGreater(amplitude, 500.0, "Amplitude sollte ~600W sein")
        
        # Test mit Lade-Target (positiv)
        normal_charge_target = +1500.0  # Akku soll mit 1500W geladen werden
        stabilized_target = self.detector.get_stabilized_target(normal_charge_target)
        
        print(f"Normal Lade-Target: {normal_charge_target}W")
        print(f"Gedämpftes Target: {stabilized_target}W")
        print(f"Dämpfung: {stabilized_target - normal_charge_target}W")
        
        # Gedämpftes Target sollte immer noch positiv sein (laden)
        self.assertGreater(stabilized_target, 0.0, "Sollte immer noch laden (positiv)")
        
        # Dämpfung sollte das Laden reduzieren (weniger als 1500W)
        self.assertLess(stabilized_target, normal_charge_target, 
                       "Dämpfung sollte Ladeleistung reduzieren")
        
        # Aber nicht zu stark reduzieren (mindestens 50% des Originals)
        self.assertGreater(stabilized_target, normal_charge_target * 0.5,
                          "Dämpfung sollte nicht zu aggressiv sein")
        
        print(f"✅ PV-Überschuss Oszillation: {normal_charge_target}W → {stabilized_target}W")
    
    def test_charging_oscillation_around_zero_export(self):
        """
        Test: Oszillation um 0W herum beim Laden
        
        Szenario:
        - PV-Produktion schwankt um den Verbrauch
        - Netz oszilliert zwischen +200W (Import) und -200W (Export)
        - Akku sollte minimal laden/entladen um zu stabilisieren
        """
        print("\n=== TEST: Oszillation um 0W beim Laden ===")
        
        # Oszillation um 0W: +200W Import ↔ -200W Export
        for i in range(20):
            if i % 4 < 2:
                power = +200.0  # Import (zu wenig PV)
            else:
                power = -200.0  # Export (zu viel PV)
            
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            self.detector.add_power_reading(power, timestamp)
        
        self.assertTrue(self.detector.is_oscillating(), "Sollte Oszillation um 0W erkennen")
        
        info = self.detector.get_oscillation_info()
        baseline = info['baseline_w']
        amplitude = info['amplitude_w']
        
        print(f"Baseline: {baseline}W (erwartet: ~0W)")
        print(f"Amplitude: {amplitude}W (erwartet: ~400W)")
        
        # Baseline sollte nahe 0W sein
        self.assertLess(abs(baseline), 100.0, "Baseline sollte nahe 0W sein")
        
        # Test mit kleinem Lade-Target
        small_charge_target = +300.0  # Kleines Laden
        stabilized_target = self.detector.get_stabilized_target(small_charge_target)
        
        print(f"Kleines Lade-Target: {small_charge_target}W")
        print(f"Gedämpftes Target: {stabilized_target}W")
        
        # Sollte immer noch positiv sein, aber reduziert
        self.assertGreater(stabilized_target, 0.0, "Sollte immer noch laden")
        self.assertLess(stabilized_target, small_charge_target, "Sollte reduziert werden")
        
        print(f"✅ Oszillation um 0W: {small_charge_target}W → {stabilized_target}W")
    
    def test_mixed_charging_discharging_oscillation(self):
        """
        Test: Oszillation die zwischen Laden und Entladen wechselt
        
        Szenario:
        - Netz oszilliert zwischen +800W (Import, Akku sollte entladen) 
          und -400W (Export, Akku sollte laden)
        - Baseline bei +200W (leichter Import)
        - System muss zwischen Laden und Entladen wechseln
        """
        print("\n=== TEST: Gemischte Lade/Entlade-Oszillation ===")
        
        # Oszillation zwischen Import und Export
        for i in range(20):
            if i % 4 < 2:
                power = +800.0  # Import (Akku sollte entladen)
            else:
                power = -400.0  # Export (Akku sollte laden)
            
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            self.detector.add_power_reading(power, timestamp)
        
        self.assertTrue(self.detector.is_oscillating(), "Sollte gemischte Oszillation erkennen")
        
        info = self.detector.get_oscillation_info()
        baseline = info['baseline_w']
        amplitude = info['amplitude_w']
        
        print(f"Baseline: {baseline}W (erwartet: ~+200W)")
        print(f"Amplitude: {amplitude}W (erwartet: ~1200W)")
        
        # Baseline sollte leicht positiv sein (mehr Import als Export)
        self.assertGreater(baseline, 0.0, "Baseline sollte positiv sein (leichter Import)")
        self.assertLess(baseline, 500.0, "Baseline sollte nicht zu hoch sein")
        
        # Test mit verschiedenen Targets
        test_cases = [
            ("Entlade-Target", -600.0),  # Normal entladen
            ("Lade-Target", +300.0),     # Normal laden
            ("Null-Target", 0.0)         # Neutral
        ]
        
        for name, target in test_cases:
            stabilized = self.detector.get_stabilized_target(target)
            adjustment = stabilized - target
            
            print(f"{name}: {target}W → {stabilized}W (Anpassung: {adjustment:.0f}W)")
            
            # Anpassung sollte vernünftig sein (nicht mehr als 50% des Targets)
            if target != 0:
                adjustment_pct = abs(adjustment / target) * 100
                self.assertLess(adjustment_pct, 50.0, 
                               f"{name} Anpassung sollte <50% sein, war {adjustment_pct:.1f}%")
        
        print(f"✅ Gemischte Oszillation erfolgreich gedämpft")
    
    def test_damping_factor_effect_during_charging(self):
        """
        Test: Effekt des Dämpfungsfaktors beim Laden
        """
        print("\n=== TEST: Dämpfungsfaktor beim Laden ===")
        
        # Oszillierender Export (PV-Überschuss schwankt)
        for i in range(16):
            power = -1000.0 if i % 4 < 2 else -1600.0  # -1300W Baseline, 600W Amplitude
            timestamp = self.base_time + timedelta(seconds=i * 0.5)
            self.detector.add_power_reading(power, timestamp)
        
        self.assertTrue(self.detector.is_oscillating())
        
        charge_target = +1200.0  # Akku soll mit 1200W geladen werden
        
        # Test verschiedene Dämpfungsfaktoren
        damping_tests = [0.0, 0.3, 0.5, 0.8, 1.0]
        results = {}
        
        for damping in damping_tests:
            self.detector.damping_factor = damping
            stabilized = self.detector.get_stabilized_target(charge_target)
            adjustment = stabilized - charge_target
            results[damping] = {'stabilized': stabilized, 'adjustment': adjustment}
            
            print(f"Dämpfung {damping}: {charge_target}W → {stabilized}W (Anpassung: {adjustment:.0f}W)")
        
        # Höhere Dämpfung sollte stärkere Anpassung bedeuten
        self.assertGreaterEqual(results[0.0]['adjustment'], results[0.5]['adjustment'],
                               "0.0 Dämpfung sollte weniger Anpassung haben als 0.5")
        self.assertGreaterEqual(results[0.5]['adjustment'], results[1.0]['adjustment'],
                               "0.5 Dämpfung sollte weniger Anpassung haben als 1.0")
        
        # Alle sollten immer noch positiv sein (laden)
        for damping, result in results.items():
            self.assertGreater(result['stabilized'], 0.0, 
                              f"Dämpfung {damping} sollte immer noch laden")
        
        print(f"✅ Dämpfungsfaktor funktioniert korrekt beim Laden")


if __name__ == '__main__':
    unittest.main(verbosity=2)