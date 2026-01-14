"""
MODULE 14: Centralized Risk Management Engine

Provides a unified risk layer for all trading strategies (swing, scalper, ML).
All position sizing, stop-loss, and take-profit calculations route through this module.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass
class RiskConfig:
    """
    Risk configuration parameters loaded from config/risk.json.
    
    Attributes:
        base_account_size: Starting account size for backtests (USD)
        default_risk_per_trade: Fraction of account to risk per trade (0.01 = 1%)
        max_exposure: Maximum total exposure as fraction of account (optional)
        default_slippage: Expected slippage in percentage (optional, for live use)
        default_sl_atr_mult: Default stop-loss multiplier (in ATR units)
        default_tp_atr_mult: Default take-profit multiplier (in ATR units)
        min_position_size_usd: Minimum position size in USD
    """
    base_account_size: float = 1000.0
    default_risk_per_trade: float = 0.01  # 1% default
    max_exposure: Optional[float] = None  # e.g., 0.5 for 50% max exposure
    default_slippage: float = 0.001  # 0.1% default slippage
    default_sl_atr_mult: float = 1.5
    default_tp_atr_mult: float = 3.0
    min_position_size_usd: float = 10.0
    
    @classmethod
    def from_file(cls, config_path: Path) -> "RiskConfig":
        """
        Load risk configuration from a JSON file.
        
        Args:
            config_path: Path to risk.json config file
            
        Returns:
            RiskConfig instance with loaded parameters
        """
        if not config_path.exists():
            print(f"[RISK] Config file {config_path} not found, using defaults")
            return cls()
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return cls(
                base_account_size=float(data.get("base_account_size", 1000.0)),
                default_risk_per_trade=float(data.get("default_risk_per_trade", 0.01)),
                max_exposure=float(data["max_exposure"]) if data.get("max_exposure") is not None else None,
                default_slippage=float(data.get("default_slippage", 0.001)),
                default_sl_atr_mult=float(data.get("default_sl_atr_mult", 1.5)),
                default_tp_atr_mult=float(data.get("default_tp_atr_mult", 3.0)),
                min_position_size_usd=float(data.get("min_position_size_usd", 10.0))
            )
        except Exception as e:
            print(f"[RISK] Error loading config from {config_path}: {e}")
            return cls()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskConfig":
        """
        Create RiskConfig from a dictionary (useful for strategy profile overrides).
        
        Args:
            data: Dictionary with risk parameters
            
        Returns:
            RiskConfig instance
        """
        return cls(
            base_account_size=float(data.get("base_account_size", 1000.0)),
            default_risk_per_trade=float(data.get("default_risk_per_trade", 0.01)),
            max_exposure=float(data["max_exposure"]) if "max_exposure" in data else None,
            default_slippage=float(data.get("default_slippage", 0.001)),
            default_sl_atr_mult=float(data.get("default_sl_atr_mult", 1.5)),
            default_tp_atr_mult=float(data.get("default_tp_atr_mult", 3.0)),
            min_position_size_usd=float(data.get("min_position_size_usd", 10.0))
        )


class RiskEngine:
    """
    Centralized risk management engine for all trading strategies.
    
    Handles:
    - Position sizing based on account risk
    - Stop-loss and take-profit calculation
    - Risk validation before trade execution
    - Consistent risk application across swing, scalping, and ML strategies
    """
    
    def __init__(self, config: RiskConfig):
        """
        Initialize risk engine with configuration.
        
        Args:
            config: RiskConfig instance with risk parameters
        """
        self.config = config
    
    def compute_position_size(
        self,
        equity: float,
        entry_price: float,
        stop_loss_price: float,
        risk_per_trade: Optional[float] = None
    ) -> float:
        """
        Calculate position size based on account risk and stop-loss distance.
        
        Formula: position_size = (equity * risk_fraction) / abs(entry_price - stop_loss_price)
        
        Args:
            equity: Current account equity (USD)
            entry_price: Intended entry price
            stop_loss_price: Stop-loss price
            risk_per_trade: Risk fraction override (default uses config.default_risk_per_trade)
            
        Returns:
            Position size in base currency units (e.g., BTC, ETH)
            
        Raises:
            ValueError: If inputs are invalid or would result in division by zero
        """
        # Validate inputs
        if equity <= 0:
            raise ValueError(f"Invalid equity: {equity}. Must be positive.")
        if entry_price <= 0:
            raise ValueError(f"Invalid entry_price: {entry_price}. Must be positive.")
        if stop_loss_price <= 0:
            raise ValueError(f"Invalid stop_loss_price: {stop_loss_price}. Must be positive.")
        
        # Validate SL is not equal to entry (can't determine direction, but can check equality)
        if abs(entry_price - stop_loss_price) < 1e-8:
            raise ValueError(
                f"Stop-loss price {stop_loss_price} is equal to entry price {entry_price}"
            )
        
        # Use provided risk or default
        risk_fraction = risk_per_trade if risk_per_trade is not None else self.config.default_risk_per_trade
        
        if risk_fraction <= 0 or risk_fraction > 1.0:
            raise ValueError(f"Invalid risk_per_trade: {risk_fraction}. Must be between 0 and 1.")
        
        # Calculate stop-loss distance (always positive)
        sl_distance = abs(entry_price - stop_loss_price)
        
        if sl_distance <= 0:
            raise ValueError(
                f"Stop-loss distance is zero or negative. Entry: {entry_price}, SL: {stop_loss_price}"
            )
        
        # Calculate risk capital
        risk_capital = equity * risk_fraction
        
        # Calculate position size
        position_size = risk_capital / sl_distance
        
        return position_size
    
    def compute_sl_tp_from_atr(
        self,
        entry_price: float,
        atr: float,
        signal: str,
        sl_mult: Optional[float] = None,
        tp_mult: Optional[float] = None
    ) -> tuple[float, float]:
        """
        Calculate stop-loss and take-profit prices based on ATR.
        
        Args:
            entry_price: Entry price
            atr: Average True Range value
            signal: Trade direction ("LONG" or "SHORT")
            sl_mult: Stop-loss multiplier override (default uses config)
            tp_mult: Take-profit multiplier override (default uses config)
            
        Returns:
            Tuple of (stop_loss_price, take_profit_price)
            
        Raises:
            ValueError: If ATR is invalid or signal is unsupported
        """
        if atr <= 0:
            raise ValueError(f"Invalid ATR: {atr}. Must be positive.")
        if entry_price <= 0:
            raise ValueError(f"Invalid entry_price: {entry_price}. Must be positive.")
        
        sl_multiplier = sl_mult if sl_mult is not None else self.config.default_sl_atr_mult
        tp_multiplier = tp_mult if tp_mult is not None else self.config.default_tp_atr_mult
        
        if signal == "LONG":
            stop_loss = entry_price - (atr * sl_multiplier)
            take_profit = entry_price + (atr * tp_multiplier)
        elif signal == "SHORT":
            stop_loss = entry_price + (atr * sl_multiplier)
            take_profit = entry_price - (atr * tp_multiplier)
        else:
            raise ValueError(f"Unsupported signal type: {signal}. Must be 'LONG' or 'SHORT'.")
        
        # Ensure stop-loss is positive
        if stop_loss <= 0:
            raise ValueError(f"Calculated stop-loss {stop_loss} is invalid (must be positive).")
        
        return stop_loss, take_profit
    
    def apply_risk_to_signal(
        self,
        signal: str,
        equity: float,
        entry_price: float,
        atr: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        risk_per_trade: Optional[float] = None,
        sl_mult: Optional[float] = None,
        tp_mult: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Apply risk management to a trading signal and return a standardized order.
        
        This is the main entry point for strategies. Given a signal (LONG/SHORT/FLAT),
        it calculates position size, SL, TP, and validates the trade.
        
        Args:
            signal: Trade direction ("LONG", "SHORT", or "FLAT")
            equity: Current account equity
            entry_price: Entry price for the trade
            atr: Average True Range (required if stop_loss_price not provided)
            stop_loss_price: Explicit stop-loss price (overrides ATR calculation)
            take_profit_price: Explicit take-profit price (overrides ATR calculation)
            risk_per_trade: Risk fraction override
            sl_mult: Stop-loss ATR multiplier override
            tp_mult: Take-profit ATR multiplier override
            metadata: Optional metadata to include in order dict
            
        Returns:
            Dictionary with trade order details, or None if no trade should be taken
            Format: {
                "signal": str,
                "side": str,
                "entry_price": float,
                "stop_loss": float,
                "take_profit": float,
                "position_size": float,
                "risk_usd": float,
                "metadata": dict
            }
            
        Raises:
            ValueError: If signal requires a trade but essential parameters are missing
        """
        # FLAT signal or invalid signal means no trade
        if signal not in ["LONG", "SHORT"]:
            return None
        
        # Calculate SL/TP if not provided
        if stop_loss_price is None or take_profit_price is None:
            if atr is None:
                raise ValueError("Either (stop_loss_price, take_profit_price) or atr must be provided")
            
            stop_loss_price, take_profit_price = self.compute_sl_tp_from_atr(
                entry_price, atr, signal, sl_mult, tp_mult
            )
        
        # Calculate position size
        try:
            position_size = self.compute_position_size(
                equity, entry_price, stop_loss_price, risk_per_trade
            )
        except ValueError as e:
            print(f"[RISK] Cannot compute position size: {e}")
            return None
        
        # Calculate position value
        position_value = position_size * entry_price
        
        # Check minimum position size
        if position_value < self.config.min_position_size_usd:
            print(f"[RISK] Position value ${position_value:.2f} < minimum ${self.config.min_position_size_usd:.2f}. Rejecting trade.")
            return None
        
        # Check max exposure if configured
        if self.config.max_exposure is not None:
            max_position_value = equity * self.config.max_exposure
            if position_value > max_position_value:
                print(f"[RISK] Position value ${position_value:.2f} exceeds max exposure ${max_position_value:.2f}. Capping position.")
                position_size = max_position_value / entry_price
                position_value = position_size * entry_price
        
        # Calculate risk in USD
        sl_distance = abs(entry_price - stop_loss_price)
        risk_usd = position_size * sl_distance
        
        # Build order dictionary
        order = {
            "signal": signal,
            "side": "BUY" if signal == "LONG" else "SELL",
            "entry_price": entry_price,
            "stop_loss": stop_loss_price,
            "take_profit": take_profit_price,
            "position_size": position_size,
            "risk_usd": risk_usd,
            "position_value_usd": position_value,
            "metadata": metadata or {}
        }
        
        return order
    
    def validate_trade(
        self,
        signal: str,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float
    ) -> bool:
        """
        Validate that a trade setup is logically consistent.
        
        Args:
            signal: Trade direction ("LONG" or "SHORT")
            entry_price: Entry price
            stop_loss_price: Stop-loss price
            take_profit_price: Take-profit price
            
        Returns:
            True if trade is valid, False otherwise
        """
        if signal == "LONG":
            # For LONG: SL < Entry < TP
            if stop_loss_price >= entry_price:
                print(f"[RISK] Invalid LONG: SL {stop_loss_price} >= Entry {entry_price}")
                return False
            if take_profit_price <= entry_price:
                print(f"[RISK] Invalid LONG: TP {take_profit_price} <= Entry {entry_price}")
                return False
        elif signal == "SHORT":
            # For SHORT: SL > Entry > TP
            if stop_loss_price <= entry_price:
                print(f"[RISK] Invalid SHORT: SL {stop_loss_price} <= Entry {entry_price}")
                return False
            if take_profit_price >= entry_price:
                print(f"[RISK] Invalid SHORT: TP {take_profit_price} >= Entry {entry_price}")
                return False
        else:
            return False
        
        return True
