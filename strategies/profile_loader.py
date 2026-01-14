"""
MODULE 31: Strategy Profile Loader

Loads per-symbol strategy profiles for auto-tuned parameters.

Profiles are JSON files in config/strategy_profiles/ that contain
optimized strategy parameters for specific symbols.

Example usage:
    from strategies.profile_loader import StrategyProfileLoader
    
    loader = StrategyProfileLoader()
    
    # Load single profile
    profile = loader.load_profile("BTCUSDT", "scalping_ema_rsi")
    if profile:
        strategy = ScalpingEMARSI(config=profile)
    
    # Load all profiles for a strategy
    profiles = loader.load_all_profiles("scalping_ema_rsi")
    for symbol, params in profiles.items():
        print(f"{symbol}: {params}")
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class StrategyProfileLoader:
    """
    Loads and validates per-symbol strategy profiles.
    
    Profiles are stored as JSON files in the profiles directory,
    one file per symbol (e.g., BTCUSDT.json, ETHUSDT.json).
    
    Attributes:
        profile_dir: Path to directory containing profile files
    """
    
    def __init__(self, profile_dir: str = "config/strategy_profiles"):
        """
        Initialize profile loader.
        
        Args:
            profile_dir: Directory path containing strategy profiles
        """
        self.profile_dir = Path(profile_dir)
        
        if not self.profile_dir.exists():
            logger.warning(f"Profile directory does not exist: {self.profile_dir}")
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created profile directory: {self.profile_dir}")
    
    def load_profile(
        self,
        symbol: str,
        strategy: str,
        require_enabled: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Load strategy profile for a specific symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            strategy: Strategy name (e.g., "scalping_ema_rsi")
            require_enabled: If True, return None if profile is disabled
            
        Returns:
            Dictionary with strategy parameters, or None if:
            - Profile file doesn't exist
            - Profile is disabled (and require_enabled=True)
            - Profile is invalid (schema errors, wrong strategy, etc.)
        """
        profile_path = self.profile_dir / f"{symbol}.json"
        
        # Check if profile exists
        if not profile_path.exists():
            logger.debug(f"No profile found for {symbol} at {profile_path}")
            return None
        
        try:
            # Load JSON
            with open(profile_path, 'r', encoding='utf-8') as f:
                profile = json.load(f)
            
            # Validate schema
            if not self._validate_profile(profile, symbol, strategy):
                return None
            
            # Check if enabled
            if require_enabled and not profile.get("enabled", False):
                logger.debug(f"Profile for {symbol} is disabled")
                return None
            
            # Module 32: Add default meta if missing (backward compatibility)
            if "meta" not in profile:
                profile["meta"] = {
                    "version": 1,
                    "created_at": None,
                    "updated_at": None,
                    "source": "manual",
                    "run_id": None,
                    "notes": ""
                }
                logger.debug(f"Added default meta to {symbol} profile (legacy format)")
            
            # Module 32: Add default metrics if missing (backward compatibility)
            if "metrics" not in profile:
                profile["metrics"] = {
                    "trades": 0,
                    "win_rate_pct": 0.0,
                    "total_return_pct": 0.0,
                    "max_drawdown_pct": 0.0,
                    "avg_R_multiple": 0.0,
                    "sample_period_days": 0
                }
                logger.debug(f"Added default metrics to {symbol} profile (legacy format)")
            
            # Module 32: Extract parameters from new structure or legacy structure
            if "params" in profile:
                # New structure: params is a separate section
                params = profile["params"].copy()
                params["symbol"] = profile.get("symbol", symbol)
                params["meta"] = profile["meta"]
                params["metrics"] = profile["metrics"]
            else:
                # Legacy structure: params are top-level fields
                params = {
                    k: v for k, v in profile.items()
                    if k not in ["strategy", "enabled", "source", "as_of", "comment", "symbol", "meta", "metrics"]
                }
                params["symbol"] = profile.get("symbol", symbol)
                params["meta"] = profile["meta"]
                params["metrics"] = profile["metrics"]
            
            logger.debug(f"Loaded profile for {symbol}: {params}")
            return params
        
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in profile {profile_path}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error loading profile for {symbol}: {e}")
            return None
    
    def load_all_profiles(
        self,
        strategy: str,
        require_enabled: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        Load all strategy profiles for a given strategy.
        
        Args:
            strategy: Strategy name (e.g., "scalping_ema_rsi")
            require_enabled: If True, skip disabled profiles
            
        Returns:
            Dictionary mapping symbol -> parameters
            Only includes valid, enabled profiles
        """
        profiles = {}
        
        # Find all JSON files in profile directory
        if not self.profile_dir.exists():
            logger.warning(f"Profile directory not found: {self.profile_dir}")
            return profiles
        
        for profile_file in self.profile_dir.glob("*.json"):
            # Skip example files
            if profile_file.stem.startswith("EXAMPLE_"):
                continue
            
            symbol = profile_file.stem
            profile = self.load_profile(symbol, strategy, require_enabled)
            
            if profile is not None:
                profiles[symbol] = profile
        
        logger.info(f"Loaded {len(profiles)} profile(s) for {strategy}")
        return profiles
    
    def _validate_profile(
        self,
        profile: Dict[str, Any],
        symbol: str,
        expected_strategy: str
    ) -> bool:
        """
        Validate profile schema and content.
        
        Args:
            profile: Profile dictionary
            symbol: Symbol name (for logging)
            expected_strategy: Expected strategy name
            
        Returns:
            True if valid, False otherwise
        """
        # Required fields (Module 32: updated schema)
        required_fields = ["strategy", "enabled"]
        for field in required_fields:
            if field not in profile:
                logger.warning(f"Profile for {symbol} missing required field: {field}")
                return False
        
        # Check strategy match
        if profile["strategy"] != expected_strategy:
            logger.warning(
                f"Profile for {symbol} is for strategy '{profile['strategy']}', "
                f"expected '{expected_strategy}'"
            )
            return False
        
        # Validate enabled field type
        if not isinstance(profile["enabled"], bool):
            logger.warning(f"Profile for {symbol} has invalid 'enabled' field (not boolean)")
            return False
        
        # Validate meta if present (Module 32)
        if "meta" in profile:
            if not isinstance(profile["meta"], dict):
                logger.warning(f"Profile for {symbol} has invalid 'meta' field (not dict)")
                return False
            meta = profile["meta"]
            if "version" in meta and not isinstance(meta["version"], int):
                logger.warning(f"Profile for {symbol} has invalid 'meta.version' (not int)")
                return False
        
        # Validate metrics if present
        if "metrics" in profile:
            if not isinstance(profile["metrics"], dict):
                logger.warning(f"Profile for {symbol} has invalid 'metrics' field (not dict)")
                return False
            metrics = profile["metrics"]
            # Check numeric fields
            for field in ["trades", "win_rate_pct", "total_return_pct", "max_drawdown_pct", "avg_R_multiple"]:
                if field in metrics and not isinstance(metrics[field], (int, float)):
                    logger.warning(f"Profile for {symbol} has invalid metrics.{field} (not numeric)")
                    return False
            if "trades" in metrics and metrics["trades"] < 0:
                logger.warning(f"Profile for {symbol} has negative trades count")
                return False
        
        # Validate timestamp if present (legacy field)
        if "as_of" in profile:
            try:
                datetime.fromisoformat(profile["as_of"].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                logger.warning(f"Profile for {symbol} has invalid 'as_of' timestamp")
                # Non-fatal - continue anyway
        
        return True
    
    def save_profile(
        self,
        symbol: str,
        strategy: str,
        params: Dict[str, Any],
        metrics: Optional[Dict[str, Any]] = None,
        source: str = "optimizer",
        enabled: bool = True,
        run_id: Optional[str] = None
    ) -> Path:
        """
        Save strategy profile for a symbol.
        
        Module 32: Now uses versioned schema with meta and metrics sections.
        
        Args:
            symbol: Trading pair symbol
            strategy: Strategy name
            params: Strategy parameters
            metrics: Optional performance metrics
            source: Source of parameters (e.g., "optimizer", "manual")
            enabled: Whether profile is enabled
            run_id: Optional optimizer run_id for tracking
            
        Returns:
            Path to saved profile file
        """
        profile_path = self.profile_dir / f"{symbol}.json"
        
        # Current timestamp
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Build versioned profile document (Module 32)
        profile = {
            "symbol": symbol,
            "strategy": strategy,
            "enabled": enabled,
            "params": params.copy() if params else {},
            "meta": {
                "version": 1,
                "created_at": now,
                "updated_at": now,
                "source": source,
                "run_id": run_id,
                "notes": ""
            },
            "metrics": metrics if metrics else {
                "trades": 0,
                "win_rate_pct": 0.0,
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "avg_R_multiple": 0.0,
                "sample_period_days": 0
            }
        }
        
        # Create directory if needed
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        # Write profile (pretty-printed)
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved profile for {symbol} to {profile_path}")
        return profile_path
