"""
MODULE 24: Configuration Validator

Validates all configuration files for consistency and safety.
Ensures configs are valid before runtime starts.
"""

import os
import sys
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


def validate_live_config(cfg: Dict[str, Any]) -> None:
    """
    Validate live.yaml configuration.
    
    Args:
        cfg: Parsed live config dictionary
        
    Raises:
        ConfigValidationError: If config is invalid
    """
    # Validate exchange field (Module 26: Binance US support)
    valid_exchanges = ["binance", "binance_us"]
    exchange = cfg.get("exchange")
    
    if exchange and exchange not in valid_exchanges:
        logger.warning(
            f"Exchange '{exchange}' not in known list: {', '.join(valid_exchanges)}. "
            "Proceeding anyway, but ensure it's supported."
        )
    
    # Validate ws_base_url if present (Module 26)
    ws_base_url = cfg.get("ws_base_url")
    if ws_base_url is not None:
        if not isinstance(ws_base_url, str) or not ws_base_url.strip():
            raise ConfigValidationError(
                f"ws_base_url must be a non-empty string, got: {ws_base_url}"
            )
        if not ws_base_url.startswith("wss://"):
            logger.warning(
                f"ws_base_url should start with 'wss://', got: {ws_base_url}"
            )


def validate_trading_mode_config(cfg: Dict[str, Any]) -> None:
    """
    Validate trading_mode.yaml configuration.
    
    Args:
        cfg: Parsed trading mode config dictionary
        
    Raises:
        ConfigValidationError: If config is invalid
    """
    # Validate mode field
    valid_modes = ["monitor", "paper", "dry_run", "live"]
    mode = cfg.get("mode")
    
    if not mode:
        raise ConfigValidationError("Missing required field: 'mode'")
    
    if mode not in valid_modes:
        raise ConfigValidationError(
            f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}"
        )
    
    # Live mode requires explicit permission
    if mode == "live":
        allow_live = cfg.get("allow_live_trading", False)
        if not allow_live:
            raise ConfigValidationError(
                "Live trading mode requires 'allow_live_trading: true'. "
                "This is a safety gate to prevent accidental live trading."
            )
    
    # Validate safety limits (required for non-monitor modes)
    if mode in ["paper", "dry_run", "live"]:
        required_limits = [
            "max_daily_loss_pct",
            "max_risk_per_trade_pct",
            "max_exposure_pct",
            "max_open_trades"
        ]
        
        for limit in required_limits:
            value = cfg.get(limit)
            
            if value is None:
                raise ConfigValidationError(
                    f"Missing required safety limit: '{limit}' for mode '{mode}'"
                )
            
            if not isinstance(value, (int, float)):
                raise ConfigValidationError(
                    f"Safety limit '{limit}' must be a number, got {type(value).__name__}"
                )
            
            if value <= 0:
                raise ConfigValidationError(
                    f"Safety limit '{limit}' must be positive, got {value}"
                )
        
        # Validate percentage limits are reasonable
        max_daily_loss = cfg.get("max_daily_loss_pct", 0)
        if max_daily_loss > 0.5:  # 50%
            logger.warning(
                f"max_daily_loss_pct is very high ({max_daily_loss*100:.1f}%). "
                "Consider lowering to protect capital."
            )
        
        max_risk_per_trade = cfg.get("max_risk_per_trade_pct", 0)
        if max_risk_per_trade > 0.05:  # 5%
            logger.warning(
                f"max_risk_per_trade_pct is high ({max_risk_per_trade*100:.1f}%). "
                "Conservative traders typically use 1-2%."
            )
        
        max_exposure = cfg.get("max_exposure_pct", 0)
        if max_exposure > 1.0:  # 100%
            logger.warning(
                f"max_exposure_pct exceeds 100% ({max_exposure*100:.1f}%). "
                "This allows leveraged positions."
            )
    
    # Validate default strategy is specified
    if not cfg.get("default_strategy"):
        raise ConfigValidationError("Missing required field: 'default_strategy'")
    
    logger.info(f"[OK] Trading mode config validated: mode='{mode}'")


def validate_risk_config(cfg: Dict[str, Any]) -> None:
    """
    Validate risk.json configuration.
    
    Args:
        cfg: Parsed risk config dictionary
        
    Raises:
        ConfigValidationError: If config is invalid
    """
    required_fields = [
        "base_account_size",
        "default_risk_per_trade",
        "max_exposure",
        "default_slippage"
    ]
    
    for field in required_fields:
        if field not in cfg:
            raise ConfigValidationError(f"Missing required risk config field: '{field}'")
        
        value = cfg[field]
        if value is not None and not isinstance(value, (int, float)):
            raise ConfigValidationError(
                f"Risk config field '{field}' must be a number or null, "
                f"got {type(value).__name__}"
            )
    
    # Validate reasonable values
    if cfg["default_risk_per_trade"] > 0.05:  # 5%
        logger.warning(
            f"default_risk_per_trade is high ({cfg['default_risk_per_trade']*100:.1f}%). "
            "Consider using 1-2% for safer risk management."
        )
    
    # Validate trailing stop configuration (optional feature)
    enable_trailing_stop = cfg.get("enable_trailing_stop", False)
    if not isinstance(enable_trailing_stop, bool):
        raise ConfigValidationError(
            f"enable_trailing_stop must be boolean, got {type(enable_trailing_stop).__name__}"
        )
    
    if enable_trailing_stop:
        trailing_stop_pct = cfg.get("trailing_stop_pct")
        
        if trailing_stop_pct is None:
            raise ConfigValidationError(
                "trailing_stop_pct is required when enable_trailing_stop is true"
            )
        
        if not isinstance(trailing_stop_pct, (int, float)):
            raise ConfigValidationError(
                f"trailing_stop_pct must be a number, got {type(trailing_stop_pct).__name__}"
            )
        
        if trailing_stop_pct <= 0 or trailing_stop_pct >= 0.20:
            raise ConfigValidationError(
                f"trailing_stop_pct must be between 0 and 0.20 (0-20%), got {trailing_stop_pct}"
            )
        
        logger.info(f"[OK] Trailing stop config validated: enabled with {trailing_stop_pct*100:.1f}% trail")
    else:
        logger.info("[OK] Trailing stop config validated: disabled")
    
    logger.info("[OK] Risk config validated")


def validate_config_consistency(
    trading_mode_cfg: Dict[str, Any],
    risk_cfg: Dict[str, Any]
) -> None:
    """
    Validate consistency between trading_mode.yaml and risk.json.
    
    Args:
        trading_mode_cfg: Parsed trading mode config
        risk_cfg: Parsed risk config
        
    Raises:
        ConfigValidationError: If configs are inconsistent
    """
    # Check risk per trade alignment
    tm_risk = trading_mode_cfg.get("max_risk_per_trade_pct")
    risk_risk = risk_cfg.get("default_risk_per_trade")
    
    if tm_risk and risk_risk:
        # Allow small tolerance for rounding
        if abs(tm_risk - risk_risk) > 0.001:
            logger.warning(
                f"Risk per trade mismatch: trading_mode.yaml has {tm_risk*100:.2f}%, "
                f"risk.json has {risk_risk*100:.2f}%. "
                f"Consider aligning these values for consistency."
            )
    
    # Check exposure alignment
    tm_exposure = trading_mode_cfg.get("max_exposure_pct")
    risk_exposure = risk_cfg.get("max_exposure")
    
    if tm_exposure and risk_exposure:
        if abs(tm_exposure - risk_exposure) > 0.01:
            logger.warning(
                f"Max exposure mismatch: trading_mode.yaml has {tm_exposure*100:.1f}%, "
                f"risk.json has {risk_exposure*100:.1f}%. "
                f"The more restrictive limit will apply."
            )
    
    logger.info("[OK] Config consistency validated")


def load_yaml_config(path: str) -> Dict[str, Any]:
    """
    Load YAML configuration file.
    
    Args:
        path: Path to YAML file
        
    Returns:
        Parsed config dictionary
        
    Raises:
        ConfigValidationError: If file cannot be loaded
    """
    config_file = Path(path)
    
    if not config_file.exists():
        raise ConfigValidationError(f"Config file not found: {path}")
    
    try:
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigValidationError(f"Invalid YAML in {path}: {e}")
    except Exception as e:
        raise ConfigValidationError(f"Error loading {path}: {e}")


def load_json_config(path: str) -> Dict[str, Any]:
    """
    Load JSON configuration file.
    
    Args:
        path: Path to JSON file
        
    Returns:
        Parsed config dictionary
        
    Raises:
        ConfigValidationError: If file cannot be loaded
    """
    config_file = Path(path)
    
    if not config_file.exists():
        raise ConfigValidationError(f"Config file not found: {path}")
    
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigValidationError(f"Invalid JSON in {path}: {e}")
    except Exception as e:
        raise ConfigValidationError(f"Error loading {path}: {e}")


def validate_all_configs(base_path: str = ".") -> Dict[str, Dict[str, Any]]:
    """
    Validate all configuration files.
    
    Loads and validates:
    - config/trading_mode.yaml
    - config/risk.json
    - config/live.yaml (optional)
    
    Args:
        base_path: Base directory containing config/ folder
        
    Returns:
        Dictionary of all loaded configs
        
    Raises:
        ConfigValidationError: If any validation fails
    """
    logger.info("=" * 60)
    logger.info("Starting configuration validation...")
    logger.info("=" * 60)
    
    configs = {}
    
    # Load trading_mode.yaml
    try:
        trading_mode_path = os.path.join(base_path, "config", "trading_mode.yaml")
        configs["trading_mode"] = load_yaml_config(trading_mode_path)
        validate_trading_mode_config(configs["trading_mode"])
    except Exception as e:
        raise ConfigValidationError(f"Trading mode config validation failed: {e}")
    
    # Load risk.json
    try:
        risk_path = os.path.join(base_path, "config", "risk.json")
        configs["risk"] = load_json_config(risk_path)
        validate_risk_config(configs["risk"])
    except Exception as e:
        raise ConfigValidationError(f"Risk config validation failed: {e}")
    
    # Validate consistency
    try:
        validate_config_consistency(configs["trading_mode"], configs["risk"])
    except Exception as e:
        raise ConfigValidationError(f"Config consistency validation failed: {e}")
    
    # Load live.yaml (optional, for additional checks)
    try:
        live_path = os.path.join(base_path, "config", "live.yaml")
        if os.path.exists(live_path):
            configs["live"] = load_yaml_config(live_path)
            validate_live_config(configs["live"])  # Module 26: validate live config
            logger.info("[OK] Live config loaded successfully")
    except Exception as e:
        logger.warning(f"Could not load live.yaml: {e}")
    
    logger.info("=" * 60)
    logger.info("[OK] ALL CONFIGURATIONS VALIDATED SUCCESSFULLY")
    logger.info("=" * 60)
    
    return configs


if __name__ == "__main__":
    """
    Standalone config validation script.
    
    Usage:
        python -m validation.config_validator
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    
    try:
        configs = validate_all_configs()
        print("\n✓ All configurations are valid and consistent.")
        print(f"\nCurrent trading mode: {configs['trading_mode']['mode']}")
        
        # Display safety limits
        mode = configs['trading_mode']['mode']
        if mode in ["paper", "dry_run", "live"]:
            print("\nSafety Limits:")
            print(f"  Max daily loss: {configs['trading_mode']['max_daily_loss_pct']*100:.1f}%")
            print(f"  Max risk/trade: {configs['trading_mode']['max_risk_per_trade_pct']*100:.1f}%")
            print(f"  Max exposure: {configs['trading_mode']['max_exposure_pct']*100:.1f}%")
            print(f"  Max open trades: {configs['trading_mode']['max_open_trades']}")
        
        # Check kill switch
        kill_switch_var = configs['trading_mode'].get('kill_switch_env_var', 'CRYPTOBOT_KILL_SWITCH')
        if os.environ.get(kill_switch_var, '').lower() in ['1', 'true', 'yes']:
            print(f"\n⚠️  WARNING: Kill switch is ENGAGED ({kill_switch_var}={os.environ[kill_switch_var]})")
            print("   All trading will be halted!")
        
    except ConfigValidationError as e:
        print(f"\n❌ Configuration validation failed: {e}")
        sys.exit(1)
