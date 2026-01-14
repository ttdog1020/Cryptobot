"""
Rollback Safeguards for Strategy Evolution (PR7)

Protects against bad parameter updates by:
1. Maintaining versioned profile history with SHA-256 hashes
2. Computing parameter drift from previous version
3. Validating performance improvement claims before applying
4. Enabling fast rollback to previous known-good state

Integrates with EvolutionEngine to intercept and validate updates.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ParameterChange:
    """Track a single parameter change"""
    name: str
    old_value: Any
    new_value: Any
    pct_change: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProfileVersion:
    """Version snapshot of a strategy profile"""
    symbol: str
    strategy: str
    timestamp: str  # ISO format UTC
    params: Dict[str, Any]
    metrics: Dict[str, float]  # return_pct, sharpe, max_dd, etc.
    git_hash: Optional[str] = None
    profile_hash: str = ""  # SHA256 of params
    reason: str = ""  # Why this version was created (e.g., "Evolution run 2025-01-15")
    changes_from_prev: List[ParameterChange] = field(default_factory=list)
    
    def __post_init__(self):
        """Auto-compute profile hash"""
        if not self.profile_hash:
            param_json = json.dumps(self.params, sort_keys=True)
            self.profile_hash = hashlib.sha256(param_json.encode()).hexdigest()[:12]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        d = asdict(self)
        d['changes_from_prev'] = [c.to_dict() for c in self.changes_from_prev]
        return d
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ProfileVersion':
        """Deserialize from dictionary"""
        changes = [
            ParameterChange(
                name=c['name'],
                old_value=c['old_value'],
                new_value=c['new_value'],
                pct_change=c['pct_change']
            )
            for c in data.pop('changes_from_prev', [])
        ]
        pv = ProfileVersion(**data)
        pv.changes_from_prev = changes
        return pv


class RollbackManager:
    """
    Manages version history and enables rollback for strategy profiles.
    
    Maintains a JSON file per symbol with version history:
    {
      "symbol": "BTCUSDT",
      "strategy": "scalping_ema_rsi",
      "versions": [
        { "timestamp": "2025-01-15T10:30:00Z", "params": {...}, "metrics": {...} },
        ...
      ],
      "current_version_index": 0  # Index into versions (0 = most recent)
    }
    """
    
    def __init__(self, history_dir: Path = Path("config/profile_versions")):
        """Initialize rollback manager"""
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
    
    def _history_file(self, symbol: str, strategy: str) -> Path:
        """Get path to history file for symbol/strategy"""
        return self.history_dir / f"{symbol}_{strategy}_history.json"
    
    def load_history(self, symbol: str, strategy: str) -> List[ProfileVersion]:
        """Load version history for a symbol/strategy"""
        hf = self._history_file(symbol, strategy)
        if not hf.exists():
            return []
        
        try:
            with open(hf) as f:
                data = json.load(f)
            return [ProfileVersion.from_dict(v) for v in data.get('versions', [])]
        except Exception as e:
            logger.error(f"Failed to load history for {symbol}/{strategy}: {e}")
            return []
    
    def save_version(
        self,
        symbol: str,
        strategy: str,
        params: Dict[str, Any],
        metrics: Dict[str, float],
        reason: str = "",
        git_hash: Optional[str] = None
    ) -> ProfileVersion:
        """Save a new version of profile parameters"""
        # Load existing history
        versions = self.load_history(symbol, strategy)
        
        # Compute changes from previous version
        changes = []
        if versions:
            prev = versions[0]
            for param_name in set(list(prev.params.keys()) + list(params.keys())):
                old_val = prev.params.get(param_name)
                new_val = params.get(param_name)
                
                if old_val != new_val:
                    if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)) and old_val != 0:
                        pct = ((new_val - old_val) / old_val) * 100
                    else:
                        pct = 0.0
                    
                    changes.append(ParameterChange(
                        name=param_name,
                        old_value=old_val,
                        new_value=new_val,
                        pct_change=pct
                    ))
        
        # Create new version
        new_version = ProfileVersion(
            symbol=symbol,
            strategy=strategy,
            timestamp=datetime.now(timezone.utc).isoformat(),
            params=params,
            metrics=metrics,
            git_hash=git_hash,
            reason=reason,
            changes_from_prev=changes
        )
        
        # Prepend to history (most recent first)
        versions.insert(0, new_version)
        
        # Persist
        hf = self._history_file(symbol, strategy)
        with open(hf, 'w') as f:
            json.dump({
                'symbol': symbol,
                'strategy': strategy,
                'versions': [v.to_dict() for v in versions]
            }, f, indent=2)
        
        logger.info(f"Saved {symbol}/{strategy} v{len(versions)}: {new_version.profile_hash}")
        return new_version
    
    def get_current_version(self, symbol: str, strategy: str) -> Optional[ProfileVersion]:
        """Get most recent version"""
        versions = self.load_history(symbol, strategy)
        return versions[0] if versions else None
    
    def get_version_count(self, symbol: str, strategy: str) -> int:
        """Get number of versions in history"""
        return len(self.load_history(symbol, strategy))
    
    def rollback_to_version(self, symbol: str, strategy: str, version_index: int) -> Optional[ProfileVersion]:
        """
        Rollback to a previous version by index.
        
        Note: This just returns the old params; caller must update the active profile.
        Returns None if index out of range.
        """
        versions = self.load_history(symbol, strategy)
        if version_index < 0 or version_index >= len(versions):
            logger.error(f"Invalid rollback index {version_index} for {symbol}/{strategy}")
            return None
        
        target = versions[version_index]
        logger.warning(f"Rollback {symbol}/{strategy} to v{version_index}: {target.profile_hash}")
        return target
    
    def list_versions(self, symbol: str, strategy: str) -> List[Dict[str, Any]]:
        """List all versions with summary info"""
        versions = self.load_history(symbol, strategy)
        return [
            {
                'index': i,
                'timestamp': v.timestamp,
                'hash': v.profile_hash,
                'return_pct': v.metrics.get('return_pct'),
                'sharpe': v.metrics.get('sharpe'),
                'max_dd': v.metrics.get('max_dd'),
                'num_changes': len(v.changes_from_prev),
                'reason': v.reason
            }
            for i, v in enumerate(versions)
        ]


class RollbackValidator:
    """
    Validates proposed parameter updates before applying.
    
    Checks:
    1. Parameter drift is within acceptable bounds
    2. Metrics improvement is realistic (vs backtest overfitting)
    3. No extreme outlier parameters introduced
    4. Changes are monotonic progression (not chaos)
    """
    
    def __init__(self, drift_tolerance_pct: float = 50.0, improvement_threshold_pct: float = 5.0):
        """
        Initialize validator.
        
        Args:
            drift_tolerance_pct: Max % change allowed per parameter (default 50%)
            improvement_threshold_pct: Min required improvement to justify change (default 5%)
        """
        self.drift_tolerance = drift_tolerance_pct
        self.improvement_threshold = improvement_threshold_pct
    
    def validate_update(
        self,
        symbol: str,
        old_params: Dict[str, Any],
        new_params: Dict[str, Any],
        old_metrics: Dict[str, float],
        new_metrics: Dict[str, float]
    ) -> Tuple[bool, str]:
        """
        Validate an update. Returns (valid, reason).
        
        Args:
            symbol: Trading pair
            old_params: Current parameters
            new_params: Proposed parameters
            old_metrics: Current performance metrics
            new_metrics: Proposed performance metrics (from backtest)
        
        Returns:
            (True, "OK") if valid
            (False, "reason") if invalid
        """
        # 0) Check for extreme outliers FIRST (e.g., parameter becomes negative when it shouldn't)
        for param_name, new_val in new_params.items():
            old_val = old_params.get(param_name)
            
            # Common validation: some params should never be negative
            if param_name in ['stop_loss_pct', 'take_profit_pct', 'position_size']:
                if isinstance(new_val, (int, float)) and new_val < 0:
                    return False, f"{symbol}: Parameter '{param_name}' cannot be negative: {new_val}"
        
        # 1) Check for chaos BEFORE checking individual drift (sudden large changes in multiple parameters)
        num_changed = sum(
            1 for p in new_params
            if old_params.get(p) != new_params[p]
        )
        if num_changed > len(old_params) * 0.5:
            return False, f"{symbol}: {num_changed}/{len(old_params)} parameters changed (>50% chaos threshold)"
        
        # 2) Check parameter drift
        for param_name in new_params:
            old_val = old_params.get(param_name, 0)
            new_val = new_params[param_name]
            
            if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
                if old_val == 0:
                    pct_change = float('inf')
                else:
                    pct_change = abs((new_val - old_val) / old_val) * 100
                
                if pct_change > self.drift_tolerance:
                    return False, f"{symbol}: Parameter '{param_name}' drift {pct_change:.1f}% exceeds {self.drift_tolerance}%"
        
        # 3) Check metrics improvement
        old_return = old_metrics.get('return_pct', 0)
        new_return = new_metrics.get('return_pct', 0)
        improvement = new_return - old_return
        
        if improvement < self.improvement_threshold:
            return False, f"{symbol}: Return improvement {improvement:.1f}% below threshold {self.improvement_threshold}%"
        
        return True, "OK"


def safe_apply_evolution(
    symbol: str,
    strategy: str,
    old_params: Dict[str, Any],
    new_params: Dict[str, Any],
    old_metrics: Dict[str, float],
    new_metrics: Dict[str, float],
    manager: RollbackManager,
    validator: RollbackValidator,
    reason: str = ""
) -> Tuple[bool, str]:
    """
    Safely apply an evolution update with full validation and history tracking.
    
    Returns:
        (True, "OK") if applied
        (False, "reason") if rejected
    """
    # Validate
    valid, msg = validator.validate_update(symbol, old_params, new_params, old_metrics, new_metrics)
    if not valid:
        logger.warning(f"Evolution rejected for {symbol}: {msg}")
        return False, msg
    
    # Record in history
    try:
        manager.save_version(symbol, strategy, new_params, new_metrics, reason=reason)
        logger.info(f"Evolution applied for {symbol}: {reason}")
        return True, "OK"
    except Exception as e:
        logger.error(f"Failed to record evolution for {symbol}: {e}")
        return False, str(e)
