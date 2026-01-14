"""
Parameter Drift Monitoring & Constraints

Tracks parameter evolution across optimization generations and enforces
soft/hard bounds to prevent convergence on unrealistic values.

Features:
- Parameter bounds definition (hard limits, soft bounds)
- Drift penalty calculation
- Parameter history tracking
- Health monitoring (flag if parameters exceeding bounds)
- Integration hooks for auto_optimizer fitness functions
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class ParameterBounds:
    """Definition of valid parameter ranges."""
    
    name: str  # Parameter name (e.g., "ema_fast")
    min_value: float
    max_value: float
    soft_min: Optional[float] = None  # Penalty zone
    soft_max: Optional[float] = None  # Penalty zone
    ideal_range: Optional[Tuple[float, float]] = None  # Preferred range
    
    def is_within_hard_bounds(self, value: float) -> bool:
        """Check if value is within hard bounds."""
        return self.min_value <= value <= self.max_value
    
    def is_within_soft_bounds(self, value: float) -> bool:
        """Check if value is within soft bounds (preferred range)."""
        if self.soft_min is None or self.soft_max is None:
            return True
        return self.soft_min <= value <= self.soft_max
    
    def compute_soft_penalty(self, value: float) -> float:
        """
        Compute penalty for exceeding soft bounds.
        
        Returns 0 if within soft bounds, increases with distance.
        """
        if self.soft_min is None or self.soft_max is None:
            return 0.0
        
        if value < self.soft_min:
            distance = self.soft_min - value
            max_distance = self.soft_min - self.min_value
        elif value > self.soft_max:
            distance = value - self.soft_max
            max_distance = self.max_value - self.soft_max
        else:
            return 0.0
        
        if max_distance == 0:
            return 0.0
        
        # Penalty ranges from 0 to 1
        penalty = min(1.0, distance / max_distance)
        return penalty


@dataclass
class DriftPenalty:
    """Penalty for parameter drift from previous generation."""
    
    parameter_name: str
    previous_value: float
    current_value: float
    allowed_drift: float
    drift_distance: float
    penalty: float
    is_excessive: bool


@dataclass
class ParameterHistory:
    """Track parameter values across generations."""
    
    parameter_name: str
    values: List[float] = field(default_factory=list)
    
    def add(self, value: float):
        """Record parameter value."""
        self.values.append(value)
    
    def get_latest(self) -> Optional[float]:
        """Get most recent value."""
        return self.values[-1] if self.values else None
    
    def get_drift_from_start(self) -> float:
        """Get total drift from first to last value."""
        if len(self.values) < 2:
            return 0.0
        
        return abs(self.values[-1] - self.values[0])
    
    def get_avg_drift_per_generation(self) -> float:
        """Get average drift between consecutive generations."""
        if len(self.values) < 2:
            return 0.0
        
        total_drift = 0.0
        for i in range(1, len(self.values)):
            total_drift += abs(self.values[i] - self.values[i-1])
        
        return total_drift / (len(self.values) - 1)


class DriftMonitor:
    """Monitor parameter drift across optimization generations."""
    
    def __init__(self):
        """Initialize drift monitor."""
        self.bounds: Dict[str, ParameterBounds] = {}
        self.history: Dict[str, ParameterHistory] = {}
        self.generation_count = 0
    
    def add_parameter_bounds(self, bounds: ParameterBounds):
        """Register parameter bounds."""
        self.bounds[bounds.name] = bounds
        
        if bounds.name not in self.history:
            self.history[bounds.name] = ParameterHistory(bounds.name)
        
        logger.info(
            f"[DRIFT] Registered {bounds.name}: "
            f"[{bounds.min_value}, {bounds.max_value}]"
        )
    
    def add_parameters_from_dict(
        self,
        params_dict: Dict[str, Dict[str, Any]]
    ):
        """
        Add parameters from dictionary format.
        
        Expected format:
        {
            'ema_fast': {
                'min': 5, 'max': 50,
                'soft_min': 8, 'soft_max': 30,
                'ideal': [10, 20]
            },
            ...
        }
        """
        for param_name, bounds_spec in params_dict.items():
            bounds = ParameterBounds(
                name=param_name,
                min_value=bounds_spec.get('min', 0),
                max_value=bounds_spec.get('max', 100),
                soft_min=bounds_spec.get('soft_min'),
                soft_max=bounds_spec.get('soft_max'),
                ideal_range=tuple(bounds_spec.get('ideal', []))
                    if bounds_spec.get('ideal') else None
            )
            self.add_parameter_bounds(bounds)
    
    def record_generation(self, parameters: Dict[str, float]):
        """Record parameter values for current generation."""
        self.generation_count += 1
        
        for param_name, value in parameters.items():
            if param_name not in self.history:
                self.history[param_name] = ParameterHistory(param_name)
            
            self.history[param_name].add(value)
    
    def check_hard_bounds(self, parameters: Dict[str, float]) -> Dict[str, bool]:
        """
        Check if parameters violate hard bounds.
        
        Returns:
            Dictionary of {parameter_name: is_valid}
        """
        violations = {}
        
        for param_name, value in parameters.items():
            if param_name not in self.bounds:
                violations[param_name] = True
                continue
            
            bounds = self.bounds[param_name]
            is_valid = bounds.is_within_hard_bounds(value)
            
            if not is_valid:
                logger.warning(
                    f"[DRIFT] Hard bound violation: {param_name}={value} "
                    f"(valid range: [{bounds.min_value}, {bounds.max_value}])"
                )
            
            violations[param_name] = is_valid
        
        return violations
    
    def compute_drift_penalties(
        self,
        parameters: Dict[str, float],
        max_drift_per_gen: float = 0.1
    ) -> Tuple[float, List[DriftPenalty]]:
        """
        Compute total drift penalty and per-parameter details.
        
        Args:
            parameters: Current generation parameters
            max_drift_per_gen: Maximum allowed drift per generation (as fraction)
        
        Returns:
            (total_penalty, list of drift penalties)
        """
        penalties = []
        total_penalty = 0.0
        
        for param_name, current_value in parameters.items():
            # Get previous value
            history = self.history.get(param_name)
            
            if history is None or len(history.values) < 2:
                continue  # No previous value
            
            previous_value = history.values[-2]
            bounds = self.bounds.get(param_name)
            
            if bounds is None:
                continue
            
            # Calculate drift
            drift_distance = abs(current_value - previous_value)
            
            # Allowed drift based on parameter range
            param_range = bounds.max_value - bounds.min_value
            allowed_drift = param_range * max_drift_per_gen
            
            # Compute penalty (0 if within allowed, increases beyond)
            if drift_distance <= allowed_drift:
                penalty = 0.0
                is_excessive = False
            else:
                excess_drift = drift_distance - allowed_drift
                penalty = min(1.0, excess_drift / allowed_drift)
                is_excessive = True
            
            if penalty > 0:
                logger.warning(
                    f"[DRIFT] Parameter drift: {param_name} "
                    f"{previous_value:.4f} → {current_value:.4f} "
                    f"(drift: {drift_distance:.4f}, allowed: {allowed_drift:.4f}, "
                    f"penalty: {penalty:.3f})"
                )
            
            penalties.append(DriftPenalty(
                parameter_name=param_name,
                previous_value=previous_value,
                current_value=current_value,
                allowed_drift=allowed_drift,
                drift_distance=drift_distance,
                penalty=penalty,
                is_excessive=is_excessive
            ))
            
            total_penalty += penalty
        
        return total_penalty, penalties
    
    def compute_soft_bound_penalties(
        self,
        parameters: Dict[str, float]
    ) -> Tuple[float, Dict[str, float]]:
        """
        Compute penalties for exceeding soft bounds.
        
        Returns:
            (total_penalty, per_parameter_penalty)
        """
        penalties_dict = {}
        total_penalty = 0.0
        
        for param_name, value in parameters.items():
            bounds = self.bounds.get(param_name)
            
            if bounds is None:
                continue
            
            penalty = bounds.compute_soft_penalty(value)
            
            if penalty > 0:
                logger.info(
                    f"[DRIFT] Soft bound penalty: {param_name}={value:.4f} "
                    f"(penalty: {penalty:.3f})"
                )
            
            penalties_dict[param_name] = penalty
            total_penalty += penalty
        
        return total_penalty, penalties_dict
    
    def check_health(self) -> Dict[str, Any]:
        """
        Health check across all tracked parameters.
        
        Returns:
            Dictionary with health metrics
        """
        health = {
            'generation': self.generation_count,
            'num_parameters': len(self.history),
            'parameters_exceeding_soft_bounds': [],
            'parameters_with_high_drift': [],
            'overall_status': 'HEALTHY'
        }
        
        if self.generation_count == 0:
            health['overall_status'] = 'NO_DATA'
            return health
        
        # Check soft bounds
        for param_name, bounds in self.bounds.items():
            if param_name not in self.history:
                continue
            
            latest_value = self.history[param_name].get_latest()
            
            if latest_value is not None:
                if not bounds.is_within_soft_bounds(latest_value):
                    health['parameters_exceeding_soft_bounds'].append({
                        'name': param_name,
                        'value': latest_value,
                        'soft_range': [bounds.soft_min, bounds.soft_max]
                    })
        
        # Check drift
        for param_name, history in self.history.items():
            avg_drift = history.get_avg_drift_per_generation()
            
            if avg_drift > 0.05:  # Threshold: 5% drift per gen is high
                health['parameters_with_high_drift'].append({
                    'name': param_name,
                    'avg_drift_per_gen': avg_drift
                })
        
        # Overall status
        if len(health['parameters_exceeding_soft_bounds']) > 3:
            health['overall_status'] = 'CONCERNING'
        elif len(health['parameters_with_high_drift']) > 2:
            health['overall_status'] = 'CONCERNING'
        
        return health
    
    def export_history_json(self, output_path: Path):
        """Export parameter history to JSON."""
        export_data = {
            'generation_count': self.generation_count,
            'parameter_history': {}
        }
        
        for param_name, history in self.history.items():
            export_data['parameter_history'][param_name] = {
                'values': history.values,
                'latest': history.get_latest(),
                'avg_drift_per_gen': history.get_avg_drift_per_generation()
            }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"[DRIFT] Exported parameter history to {output_path}")
    
    def export_bounds_json(self, output_path: Path):
        """Export parameter bounds to JSON."""
        export_data = {}
        
        for param_name, bounds in self.bounds.items():
            export_data[param_name] = {
                'min': bounds.min_value,
                'max': bounds.max_value,
                'soft_min': bounds.soft_min,
                'soft_max': bounds.soft_max,
                'ideal': list(bounds.ideal_range) if bounds.ideal_range else None
            }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"[DRIFT] Exported parameter bounds to {output_path}")


if __name__ == "__main__":
    # Example usage
    monitor = DriftMonitor()
    
    # Define parameter bounds
    monitor.add_parameters_from_dict({
        'ema_fast': {
            'min': 5, 'max': 50,
            'soft_min': 8, 'soft_max': 25,
            'ideal': [10, 15]
        },
        'ema_slow': {
            'min': 20, 'max': 200,
            'soft_min': 30, 'soft_max': 100,
            'ideal': [40, 60]
        },
        'rsi_threshold': {
            'min': 20, 'max': 80,
            'soft_min': 30, 'soft_max': 70,
            'ideal': [30, 70]
        }
    })
    
    # Simulate generations
    gen1 = {'ema_fast': 12, 'ema_slow': 50, 'rsi_threshold': 40}
    gen2 = {'ema_fast': 15, 'ema_slow': 55, 'rsi_threshold': 100}  # Bad: RSI exceeds max
    gen3 = {'ema_fast': 20, 'ema_slow': 40, 'rsi_threshold': 35}
    
    for i, params in enumerate([gen1, gen2, gen3], 1):
        print(f"\n=== Generation {i} ===")
        monitor.record_generation(params)
        
        # Check bounds
        violations = monitor.check_hard_bounds(params)
        print(f"Hard bounds violations: {violations}")
        
        # Check drift (skip first generation)
        if i > 1:
            drift_pen, details = monitor.compute_drift_penalties(params)
            print(f"Drift penalty: {drift_pen:.3f}")
        
        # Soft bounds
        soft_pen, soft_dict = monitor.compute_soft_bound_penalties(params)
        print(f"Soft bound penalty: {soft_pen:.3f}")
        
        # Health
        health = monitor.check_health()
        print(f"Health status: {health['overall_status']}")
    
    # Export
    monitor.export_history_json(Path('/tmp/param_history.json'))
    monitor.export_bounds_json(Path('/tmp/param_bounds.json'))
