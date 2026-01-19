"""
Tests for parameter drift monitoring and constraints.

Tests:
- Parameter bounds definition
- Hard bound checking
- Drift penalty calculation
- Soft bound penalties
- Health monitoring
- History tracking
"""

import pytest
from pathlib import Path
import tempfile
import json

from optimizer.drift_monitor import (
    DriftMonitor, ParameterBounds, ParameterHistory
)


class TestParameterBounds:
    """Tests for ParameterBounds class."""
    
    def test_bounds_creation(self):
        """Test creating parameter bounds."""
        bounds = ParameterBounds(
            name="ema_fast",
            min_value=5,
            max_value=50,
            soft_min=8,
            soft_max=30
        )
        
        assert bounds.name == "ema_fast"
        assert bounds.min_value == 5
        assert bounds.max_value == 50
        assert bounds.soft_min == 8
        assert bounds.soft_max == 30
    
    def test_hard_bounds_check(self):
        """Test hard bounds enforcement."""
        bounds = ParameterBounds(name="test", min_value=10, max_value=20)
        
        assert bounds.is_within_hard_bounds(10)
        assert bounds.is_within_hard_bounds(15)
        assert bounds.is_within_hard_bounds(20)
        assert not bounds.is_within_hard_bounds(5)
        assert not bounds.is_within_hard_bounds(25)
    
    def test_soft_bounds_check(self):
        """Test soft bounds enforcement."""
        bounds = ParameterBounds(
            name="test",
            min_value=10,
            max_value=20,
            soft_min=12,
            soft_max=18
        )
        
        assert bounds.is_within_soft_bounds(12)
        assert bounds.is_within_soft_bounds(15)
        assert bounds.is_within_soft_bounds(18)
        assert not bounds.is_within_soft_bounds(10)
        assert not bounds.is_within_soft_bounds(20)
    
    def test_soft_bound_penalty(self):
        """Test soft bound penalty calculation."""
        bounds = ParameterBounds(
            name="test",
            min_value=10,
            max_value=20,
            soft_min=12,
            soft_max=18
        )
        
        # Within soft bounds: 0 penalty
        assert bounds.compute_soft_penalty(15) == 0.0
        
        # At soft bounds: 0 penalty
        assert bounds.compute_soft_penalty(12) == 0.0
        assert bounds.compute_soft_penalty(18) == 0.0
        
        # Outside soft bounds: positive penalty
        penalty_low = bounds.compute_soft_penalty(10)
        assert 0 < penalty_low <= 1.0
        
        penalty_high = bounds.compute_soft_penalty(20)
        assert 0 < penalty_high <= 1.0
    
    def test_soft_bound_penalty_scaling(self):
        """Test that penalty scales with distance from soft bounds."""
        bounds = ParameterBounds(
            name="test",
            min_value=0,
            max_value=100,
            soft_min=25,
            soft_max=75
        )
        
        # Further from soft bounds = higher penalty
        penalty_5 = bounds.compute_soft_penalty(5)
        penalty_15 = bounds.compute_soft_penalty(15)
        
        assert penalty_5 > penalty_15


class TestParameterHistory:
    """Tests for ParameterHistory class."""
    
    def test_history_creation(self):
        """Test creating parameter history."""
        history = ParameterHistory("ema_fast")
        
        assert history.parameter_name == "ema_fast"
        assert len(history.values) == 0
    
    def test_add_and_retrieve(self):
        """Test adding and retrieving values."""
        history = ParameterHistory("ema_fast")
        
        history.add(10)
        history.add(12)
        history.add(15)
        
        assert len(history.values) == 3
        assert history.values == [10, 12, 15]
        assert history.get_latest() == 15
    
    def test_drift_from_start(self):
        """Test total drift calculation."""
        history = ParameterHistory("ema_fast")
        
        history.add(10)
        history.add(20)
        
        drift = history.get_drift_from_start()
        assert drift == 10
    
    def test_avg_drift_per_generation(self):
        """Test average drift per generation."""
        history = ParameterHistory("ema_fast")
        
        # Values: 10 -> 12 -> 15 -> 16
        # Drifts: 2, 3, 1 = avg 2
        history.add(10)
        history.add(12)
        history.add(15)
        history.add(16)
        
        avg_drift = history.get_avg_drift_per_generation()
        assert avg_drift == pytest.approx(2.0, rel=0.01)


class TestDriftMonitor:
    """Tests for DriftMonitor class."""
    
    def test_initialization(self):
        """Test drift monitor initialization."""
        monitor = DriftMonitor()
        
        assert monitor.generation_count == 0
        assert len(monitor.bounds) == 0
        assert len(monitor.history) == 0
    
    def test_add_bounds(self):
        """Test adding parameter bounds."""
        monitor = DriftMonitor()
        
        bounds = ParameterBounds(
            name="ema_fast",
            min_value=5,
            max_value=50
        )
        monitor.add_parameter_bounds(bounds)
        
        assert "ema_fast" in monitor.bounds
        assert monitor.bounds["ema_fast"] == bounds
    
    def test_add_bounds_from_dict(self):
        """Test adding bounds from dictionary."""
        monitor = DriftMonitor()
        
        bounds_dict = {
            'ema_fast': {'min': 5, 'max': 50, 'soft_min': 8, 'soft_max': 30},
            'ema_slow': {'min': 20, 'max': 200}
        }
        monitor.add_parameters_from_dict(bounds_dict)
        
        assert 'ema_fast' in monitor.bounds
        assert 'ema_slow' in monitor.bounds
        assert monitor.bounds['ema_fast'].soft_min == 8
    
    def test_record_generation(self):
        """Test recording generation parameters."""
        monitor = DriftMonitor()
        monitor.add_parameter_bounds(ParameterBounds("test", 0, 100))
        
        params1 = {'test': 25}
        monitor.record_generation(params1)
        
        assert monitor.generation_count == 1
        assert monitor.history['test'].get_latest() == 25
    
    def test_check_hard_bounds(self):
        """Test hard bounds checking."""
        monitor = DriftMonitor()
        monitor.add_parameter_bounds(ParameterBounds("test", 10, 20))
        
        # Valid parameters
        valid = monitor.check_hard_bounds({'test': 15})
        assert valid['test'] == True
        
        # Invalid parameters
        invalid = monitor.check_hard_bounds({'test': 25})
        assert invalid['test'] == False
    
    def test_compute_drift_penalties(self):
        """Test drift penalty computation."""
        monitor = DriftMonitor()
        monitor.add_parameter_bounds(ParameterBounds("test", 0, 100))
        
        # First generation: no previous value
        monitor.record_generation({'test': 20})
        total_pen, penalties = monitor.compute_drift_penalties({'test': 20})
        assert total_pen == 0.0
        assert len(penalties) == 0
        
        # Second generation: small drift
        monitor.record_generation({'test': 22})
        total_pen, penalties = monitor.compute_drift_penalties({'test': 22})
        assert total_pen == pytest.approx(0.0, abs=0.01)
        
        # Third generation: large drift
        monitor.record_generation({'test': 50})
        total_pen, penalties = monitor.compute_drift_penalties({'test': 50})
        assert len(penalties) > 0
        assert penalties[0].is_excessive
    
    def test_compute_soft_bound_penalties(self):
        """Test soft bound penalty computation."""
        monitor = DriftMonitor()
        bounds = ParameterBounds(
            name="test",
            min_value=0,
            max_value=100,
            soft_min=20,
            soft_max=80
        )
        monitor.add_parameter_bounds(bounds)
        
        # Within soft bounds
        total_pen, penalties = monitor.compute_soft_bound_penalties({'test': 50})
        assert total_pen == 0.0
        
        # Outside soft bounds
        total_pen, penalties = monitor.compute_soft_bound_penalties({'test': 5})
        assert total_pen > 0.0
        assert penalties['test'] > 0.0
    
    def test_health_check_no_data(self):
        """Test health check with no data."""
        monitor = DriftMonitor()
        
        health = monitor.check_health()
        
        assert health['overall_status'] == 'NO_DATA'
        assert health['generation'] == 0
    
    def test_health_check_healthy(self):
        """Test health check for healthy parameters."""
        monitor = DriftMonitor()
        monitor.add_parameter_bounds(ParameterBounds("test", 0, 100, 20, 80))
        
        # Record healthy generation
        monitor.record_generation({'test': 50})
        health = monitor.check_health()
        
        assert health['overall_status'] == 'HEALTHY'
        assert len(health['parameters_exceeding_soft_bounds']) == 0
    
    def test_health_check_concerning(self):
        """Test health check for concerning parameters."""
        monitor = DriftMonitor()
        
        # Add parameters with soft bounds
        for i in range(5):
            monitor.add_parameter_bounds(
                ParameterBounds(f"param{i}", 0, 100, 20, 80)
            )
        
        # Record generation with many soft bound violations
        params = {f'param{i}': 10 for i in range(5)}
        monitor.record_generation(params)
        
        health = monitor.check_health()
        
        # More than 3 soft bound violations = CONCERNING
        assert len(health['parameters_exceeding_soft_bounds']) > 3
        assert health['overall_status'] == 'CONCERNING'
    
    def test_high_drift_detection(self):
        """Test detection of high parameter drift."""
        monitor = DriftMonitor()
        monitor.add_parameter_bounds(ParameterBounds("test", 0, 100))
        
        # Large drift each generation
        monitor.record_generation({'test': 10})
        monitor.record_generation({'test': 20})  # 10% drift
        monitor.record_generation({'test': 30})  # 10% drift
        
        health = monitor.check_health()
        
        # High drift should be flagged
        assert len(health['parameters_with_high_drift']) > 0


class TestExport:
    """Tests for exporting history and bounds."""
    
    def test_export_history_json(self):
        """Test exporting parameter history."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            monitor = DriftMonitor()
            monitor.add_parameter_bounds(ParameterBounds("test", 0, 100))
            
            monitor.record_generation({'test': 20})
            monitor.record_generation({'test': 25})
            
            output_path = tmpdir / "history.json"
            monitor.export_history_json(output_path)
            
            assert output_path.exists()
            
            with open(output_path, 'r') as f:
                data = json.load(f)
            
            assert data['generation_count'] == 2
            assert 'test' in data['parameter_history']
            assert data['parameter_history']['test']['values'] == [20, 25]
    
    def test_export_bounds_json(self):
        """Test exporting parameter bounds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            monitor = DriftMonitor()
            bounds = ParameterBounds(
                name="test",
                min_value=10,
                max_value=50,
                soft_min=15,
                soft_max=45
            )
            monitor.add_parameter_bounds(bounds)
            
            output_path = tmpdir / "bounds.json"
            monitor.export_bounds_json(output_path)
            
            assert output_path.exists()
            
            with open(output_path, 'r') as f:
                data = json.load(f)
            
            assert 'test' in data
            assert data['test']['min'] == 10
            assert data['test']['max'] == 50
            assert data['test']['soft_min'] == 15


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_unknown_parameter_in_check(self):
        """Test checking bounds for unknown parameter."""
        monitor = DriftMonitor()
        monitor.add_parameter_bounds(ParameterBounds("known", 0, 100))
        
        violations = monitor.check_hard_bounds({'unknown': 50})
        
        # Unknown parameter treated as valid
        assert violations['unknown'] == True
    
    def test_zero_drift(self):
        """Test with zero drift between generations."""
        monitor = DriftMonitor()
        monitor.add_parameter_bounds(ParameterBounds("test", 0, 100))
        
        monitor.record_generation({'test': 50})
        monitor.record_generation({'test': 50})  # No drift
        
        total_pen, penalties = monitor.compute_drift_penalties({'test': 50})
        
        assert total_pen == 0.0
    
    def test_negative_parameters(self):
        """Test with negative parameter values."""
        bounds = ParameterBounds(name="test", min_value=-50, max_value=50)
        
        assert bounds.is_within_hard_bounds(-25)
        assert bounds.is_within_hard_bounds(0)
        assert bounds.is_within_hard_bounds(25)
        assert not bounds.is_within_hard_bounds(-100)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
