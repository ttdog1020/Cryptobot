#!/usr/bin/env python3
"""
Risk Parameter Validation Script

Validates trading configuration files to ensure they meet safety requirements.
Used as a CI/CD gate to prevent deployment of unsafe configurations.

Safety checks:
- Position size limits
- Risk per trade limits
- Stop-loss requirements
- Maximum exposure limits
- Leverage limits
"""

import json
import yaml
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple


class RiskValidator:
    """Validates risk parameters against safety thresholds."""

    # Safety thresholds (conservative defaults)
    MAX_RISK_PER_TRADE = 0.02  # 2% max risk per trade
    MAX_EXPOSURE = 0.30  # 30% max total exposure
    MIN_SL_ATR_MULT = 0.5  # Minimum stop-loss distance (in ATR)
    MAX_LEVERAGE = 3  # Maximum leverage allowed
    MAX_DAILY_LOSS_PCT = 0.05  # 5% max daily loss
    MAX_OPEN_TRADES = 20  # Maximum concurrent positions

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_risk_json(self, config: Dict[str, Any]) -> bool:
        """Validate config/risk.json parameters."""
        print("\n[Validating risk.json]")

        # Check risk per trade
        risk_per_trade = config.get("default_risk_per_trade", 0)
        if risk_per_trade > self.MAX_RISK_PER_TRADE:
            self.errors.append(
                f"Risk per trade too high: {risk_per_trade:.2%} > {self.MAX_RISK_PER_TRADE:.2%}"
            )
        elif risk_per_trade > 0:
            print(f"  ✓ Risk per trade: {risk_per_trade:.2%}")

        # Check max exposure
        max_exposure = config.get("max_exposure")
        if max_exposure is not None:
            if max_exposure > self.MAX_EXPOSURE:
                self.errors.append(
                    f"Max exposure too high: {max_exposure:.2%} > {self.MAX_EXPOSURE:.2%}"
                )
            else:
                print(f"  ✓ Max exposure: {max_exposure:.2%}")
        else:
            self.warnings.append("Max exposure not set (unlimited exposure allowed)")

        # Check stop-loss multiplier
        sl_atr_mult = config.get("default_sl_atr_mult", 0)
        if sl_atr_mult < self.MIN_SL_ATR_MULT:
            self.errors.append(
                f"Stop-loss too tight: {sl_atr_mult} < {self.MIN_SL_ATR_MULT} ATR"
            )
        elif sl_atr_mult > 0:
            print(f"  ✓ Stop-loss multiplier: {sl_atr_mult} ATR")

        # Check minimum position size
        min_position = config.get("min_position_size_usd", 0)
        if min_position < 5.0:
            self.warnings.append(
                f"Min position size very small: ${min_position} (dust trades possible)"
            )
        else:
            print(f"  ✓ Min position size: ${min_position}")

        return len(self.errors) == 0

    def validate_trading_mode_yaml(self, config: Dict[str, Any]) -> bool:
        """Validate config/trading_mode.yaml parameters."""
        print("\n[Validating trading_mode.yaml]")

        # Check trading mode
        mode = config.get("mode", "unknown")
        print(f"  → Trading mode: {mode}")

        # Check live trading gate
        allow_live = config.get("allow_live_trading", False)
        if mode == "live" and not allow_live:
            self.errors.append(
                "Live trading mode enabled but allow_live_trading is false"
            )
        elif mode == "live" and allow_live:
            self.warnings.append(
                "⚠️  LIVE TRADING ENABLED - Ensure this is intentional!"
            )
        else:
            print(f"  ✓ Live trading gate: {'enabled' if allow_live else 'disabled'}")

        # Check max daily loss
        max_daily_loss = config.get("max_daily_loss_pct", 0)
        if max_daily_loss > self.MAX_DAILY_LOSS_PCT:
            self.errors.append(
                f"Max daily loss too high: {max_daily_loss:.2%} > {self.MAX_DAILY_LOSS_PCT:.2%}"
            )
        elif max_daily_loss > 0:
            print(f"  ✓ Max daily loss: {max_daily_loss:.2%}")

        # Check max risk per trade
        max_risk_per_trade = config.get("max_risk_per_trade_pct", 0)
        if max_risk_per_trade > self.MAX_RISK_PER_TRADE:
            self.errors.append(
                f"Max risk per trade too high: {max_risk_per_trade:.2%} > {self.MAX_RISK_PER_TRADE:.2%}"
            )
        elif max_risk_per_trade > 0:
            print(f"  ✓ Max risk per trade: {max_risk_per_trade:.2%}")

        # Check max open trades
        max_open = config.get("max_open_trades", 0)
        if max_open > self.MAX_OPEN_TRADES:
            self.warnings.append(
                f"High number of max open trades: {max_open} > {self.MAX_OPEN_TRADES}"
            )
        elif max_open > 0:
            print(f"  ✓ Max open trades: {max_open}")

        # Check max exposure
        max_exposure = config.get("max_exposure_pct", 0)
        if max_exposure > self.MAX_EXPOSURE:
            self.errors.append(
                f"Max exposure too high: {max_exposure:.2%} > {self.MAX_EXPOSURE:.2%}"
            )
        elif max_exposure > 0:
            print(f"  ✓ Max exposure: {max_exposure:.2%}")

        return len(self.errors) == 0

    def validate_strategy_configs(self, config_dir: Path) -> bool:
        """Validate strategy-specific configurations."""
        print("\n[Validating strategy configs]")

        strategy_dir = config_dir / "strategies"
        if not strategy_dir.exists():
            print("  → No strategy configs found (optional)")
            return True

        # Check for strategy files with leverage settings
        strategy_files = list(strategy_dir.glob("*.yaml")) + list(
            strategy_dir.glob("*.json")
        )

        if not strategy_files:
            print("  → No strategy config files found")
            return True

        for strategy_file in strategy_files:
            print(f"  → Checking {strategy_file.name}...")

            try:
                if strategy_file.suffix == ".yaml":
                    with open(strategy_file, "r") as f:
                        config = yaml.safe_load(f)
                else:
                    with open(strategy_file, "r") as f:
                        config = json.load(f)

                # Check for leverage settings
                if isinstance(config, dict):
                    leverage = config.get("leverage", 1)
                    if leverage > self.MAX_LEVERAGE:
                        self.errors.append(
                            f"{strategy_file.name}: Leverage too high: {leverage}x > {self.MAX_LEVERAGE}x"
                        )
                    elif leverage > 1:
                        print(f"    ✓ Leverage: {leverage}x")

            except Exception as e:
                self.warnings.append(f"Could not parse {strategy_file.name}: {e}")

        return len(self.errors) == 0

    def print_summary(self) -> bool:
        """Print validation summary and return overall status."""
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)

        if self.errors:
            print(f"\n❌ FAILED: {len(self.errors)} error(s) found:")
            for error in self.errors:
                print(f"  • {error}")

        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} warning(s):")
            for warning in self.warnings:
                print(f"  • {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ All safety checks passed!")
        elif not self.errors:
            print("\n✅ No critical errors found (warnings are informational)")

        print("=" * 70)
        return len(self.errors) == 0


def main():
    """Main validation entry point."""
    print("=" * 70)
    print("CRYPTOBOT RISK PARAMETER VALIDATOR")
    print("=" * 70)

    # Find config directory
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    config_dir = repo_root / "config"

    if not config_dir.exists():
        print(f"\n❌ ERROR: Config directory not found: {config_dir}")
        sys.exit(1)

    validator = RiskValidator()
    all_passed = True

    # Validate risk.json
    risk_file = config_dir / "risk.json"
    if risk_file.exists():
        try:
            with open(risk_file, "r") as f:
                risk_config = json.load(f)
            if not validator.validate_risk_json(risk_config):
                all_passed = False
        except Exception as e:
            print(f"\n❌ ERROR: Could not parse risk.json: {e}")
            sys.exit(1)
    else:
        print("\n⚠️  WARNING: risk.json not found")

    # Validate trading_mode.yaml
    trading_mode_file = config_dir / "trading_mode.yaml"
    if trading_mode_file.exists():
        try:
            with open(trading_mode_file, "r") as f:
                trading_mode_config = yaml.safe_load(f)
            if not validator.validate_trading_mode_yaml(trading_mode_config):
                all_passed = False
        except Exception as e:
            print(f"\n❌ ERROR: Could not parse trading_mode.yaml: {e}")
            sys.exit(1)
    else:
        print("\n⚠️  WARNING: trading_mode.yaml not found")

    # Validate strategy configs
    if not validator.validate_strategy_configs(config_dir):
        all_passed = False

    # Print summary and exit
    if validator.print_summary() and all_passed:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
