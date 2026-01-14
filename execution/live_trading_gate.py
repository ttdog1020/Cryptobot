"""
Live Trading Safety Gate

Two-key gate system to prevent accidental live trading with real money.

REQUIREMENTS FOR LIVE TRADING:
1. config/trading_mode.yaml must have mode: "live"
2. Environment variable LIVE_TRADING_ENABLED must equal "true"

Both conditions must be satisfied. Otherwise, system forces paper/monitor mode.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Tuple
import yaml

logger = logging.getLogger(__name__)


class LiveTradingGateError(Exception):
    """Raised when live trading gate checks fail."""
    pass


def check_live_trading_gate(config_path: str = "config/trading_mode.yaml") -> Tuple[bool, str, str]:
    """
    Check if live trading is properly unlocked.
    
    Returns:
        Tuple of (is_live_enabled, actual_mode, reason)
        - is_live_enabled: True if both gates pass
        - actual_mode: The mode that should be used ("paper", "monitor", or "live")
        - reason: Human-readable explanation
    """
    # Load trading mode config
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        return False, "paper", f"Config file not found: {config_path}"
    except Exception as e:
        return False, "paper", f"Failed to load config: {e}"
    
    mode = config.get("mode", "paper")
    allow_live = config.get("allow_live_trading", False)
    
    # Check environment variable
    env_enabled = os.getenv("LIVE_TRADING_ENABLED", "false").lower() in ("true", "1", "yes")
    
    # Gate logic
    if mode == "live":
        if not allow_live:
            return False, "paper", (
                "Live trading blocked: config mode='live' but allow_live_trading=false. "
                "Set allow_live_trading: true in config/trading_mode.yaml to enable."
            )
        if not env_enabled:
            return False, "paper", (
                "Live trading blocked: config mode='live' and allow_live_trading=true, "
                "but environment variable LIVE_TRADING_ENABLED is not 'true'. "
                "Set: export LIVE_TRADING_ENABLED=true (Linux/Mac) or "
                "$env:LIVE_TRADING_ENABLED='true' (PowerShell)"
            )
        # Both gates pass
        return True, "live", "Live trading enabled (both gates passed)"
    
    elif mode == "monitor":
        return False, "monitor", "Monitor mode active (signal generation only, no orders)"
    
    elif mode == "paper":
        return False, "paper", "Paper trading mode active (simulated orders)"
    
    elif mode == "dry_run":
        # dry_run also requires the gates for safety
        if allow_live and env_enabled:
            return False, "dry_run", "Dry-run mode active (exchange client initialized but orders logged only)"
        else:
            return False, "paper", (
                "Dry-run mode requested but gates not passed. Forcing paper mode. "
                "To use dry_run, set allow_live_trading: true and LIVE_TRADING_ENABLED=true"
            )
    
    else:
        return False, "paper", f"Unknown mode '{mode}', defaulting to paper mode"


def validate_no_live_keys_in_safe_mode(
    api_key: str = None,
    api_secret: str = None,
    mode: str = "paper"
) -> None:
    """
    Validate that live API keys are not present when running in safe modes.
    
    Raises LiveTradingGateError if keys are detected in paper/monitor mode.
    
    Args:
        api_key: API key (if provided)
        api_secret: API secret (if provided)
        mode: Current trading mode
    """
    has_keys = bool(api_key and api_key.strip() and len(api_key.strip()) > 10)
    has_secret = bool(api_secret and api_secret.strip() and len(api_secret.strip()) > 10)
    
    if (has_keys or has_secret) and mode in ["paper", "monitor"]:
        raise LiveTradingGateError(
            f"\n"
            f"{'='*70}\n"
            f"CRITICAL SAFETY ERROR: Live API keys detected in {mode.upper()} mode!\n"
            f"{'='*70}\n"
            f"\n"
            f"Live API keys were found but trading mode is '{mode}'.\n"
            f"This is a safety violation - keys should only be present in live mode.\n"
            f"\n"
            f"Actions:\n"
            f"  1. Remove API keys from environment/config files\n"
            f"  2. Ensure .env files are in .gitignore\n"
            f"  3. Use paper trading for development and testing\n"
            f"\n"
            f"If you need live trading:\n"
            f"  1. Set mode: 'live' in config/trading_mode.yaml\n"
            f"  2. Set allow_live_trading: true in config/trading_mode.yaml\n"
            f"  3. Set environment: export LIVE_TRADING_ENABLED=true\n"
            f"\n"
            f"Program will now exit for safety.\n"
            f"{'='*70}\n"
        )


def enforce_paper_mode_default() -> str:
    """
    Enforce paper mode as the default if no config is found.
    
    Returns:
        "paper" (always)
    """
    logger.warning(
        "No trading mode config found or gates not passed. "
        "Defaulting to PAPER mode for safety."
    )
    return "paper"


def log_trading_mode_status(is_live: bool, mode: str, reason: str) -> None:
    """
    Log trading mode status with clear visual separation.
    
    Args:
        is_live: Whether live trading is enabled
        mode: Current trading mode
        reason: Human-readable explanation
    """
    if is_live and mode == "live":
        logger.critical("="*70)
        logger.critical("⚠️  LIVE TRADING MODE ACTIVE - REAL MONEY AT RISK ⚠️")
        logger.critical("="*70)
        logger.critical(f"Reason: {reason}")
        logger.critical("="*70)
    elif mode == "monitor":
        logger.info("="*70)
        logger.info("📊 MONITOR MODE - Signal Generation Only")
        logger.info("="*70)
        logger.info(f"Reason: {reason}")
        logger.info("="*70)
    elif mode == "paper":
        logger.info("="*70)
        logger.info("📝 PAPER TRADING MODE - Simulated Orders")
        logger.info("="*70)
        logger.info(f"Reason: {reason}")
        logger.info("="*70)
    elif mode == "dry_run":
        logger.warning("="*70)
        logger.warning("🔧 DRY-RUN MODE - Exchange Client Active But Logging Only")
        logger.warning("="*70)
        logger.warning(f"Reason: {reason}")
        logger.warning("="*70)
