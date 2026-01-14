"""
MODULE 24: Safety Monitor and Global Safety Limits

Implements global trading safety limits and kill switch mechanism.
Protects capital by enforcing risk limits and enabling emergency shutdown.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime

from .order_types import OrderRequest, OrderSide

logger = logging.getLogger(__name__)


@dataclass
class SafetyLimits:
    """
    Global safety limits for trading.
    
    These limits apply across all strategies and symbols to protect capital.
    """
    # Maximum daily loss as percentage of starting equity
    max_daily_loss_pct: float
    
    # Maximum risk per trade as percentage of current equity
    max_risk_per_trade_pct: float
    
    # Maximum total exposure as percentage of equity
    max_exposure_pct: float
    
    # Maximum number of concurrent open trades
    max_open_trades: int
    
    # Environment variable name for kill switch
    kill_switch_env_var: str = "CRYPTOBOT_KILL_SWITCH"
    
    def __post_init__(self):
        """Validate limits on initialization."""
        if self.max_daily_loss_pct <= 0:
            raise ValueError("max_daily_loss_pct must be positive")
        
        if self.max_risk_per_trade_pct <= 0:
            raise ValueError("max_risk_per_trade_pct must be positive")
        
        if self.max_exposure_pct <= 0:
            raise ValueError("max_exposure_pct must be positive")
        
        if self.max_open_trades <= 0:
            raise ValueError("max_open_trades must be positive")


class SafetyMonitor:
    """
    Monitors trading activity and enforces global safety limits.
    
    Tracks:
    - Daily loss percentage
    - Per-trade risk
    - Total exposure
    - Open trade count
    - Kill switch state
    
    Prevents orders that would violate safety limits.
    Halts all trading if daily loss limit exceeded or kill switch engaged.
    """
    
    def __init__(
        self,
        limits: SafetyLimits,
        starting_equity: float,
        session_start: Optional[datetime] = None
    ):
        """
        Initialize safety monitor.
        
        Args:
            limits: SafetyLimits configuration
            starting_equity: Starting equity for this session/day
            session_start: Session start time (defaults to now)
        """
        self.limits = limits
        self.starting_equity = starting_equity
        self.session_start = session_start or datetime.now()
        
        # Module 27: Peak equity for drawdown tracking
        self.session_start_equity = starting_equity
        self.peak_equity = starting_equity
        
        # Trading state
        self.current_equity = starting_equity
        self.daily_pnl = 0.0
        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.consecutive_failures = 0
        
        # Kill switch
        self.trading_halted = False
        self.halt_reason: Optional[str] = None
        
        logger.info(
            f"SafetyMonitor initialized: "
            f"starting_equity=${starting_equity:.2f}, "
            f"max_daily_loss={limits.max_daily_loss_pct*100:.1f}%, "
            f"max_risk/trade={limits.max_risk_per_trade_pct*100:.1f}%, "
            f"max_exposure={limits.max_exposure_pct*100:.1f}%, "
            f"max_open_trades={limits.max_open_trades}"
        )
    
    def check_pre_trade(
        self,
        order: OrderRequest,
        risk_amount: float,
        position_value: float
    ) -> None:
        """
        Check if order can be submitted without violating safety limits.
        
        Called BEFORE submitting an order to the execution engine.
        
        Args:
            order: OrderRequest to validate
            risk_amount: Dollar amount at risk for this trade (distance to stop loss)
            position_value: Total value of position (quantity * price)
            
        Raises:
            SafetyViolation: If order would violate safety limits
        """
        # Check if trading is halted
        if self.kill_switch_engaged():
            raise SafetyViolation(
                f"Trading halted: {self.halt_reason or 'Kill switch engaged'}"
            )
        
        # Check per-trade risk limit
        max_risk_dollars = self.current_equity * self.limits.max_risk_per_trade_pct
        if risk_amount > max_risk_dollars:
            raise SafetyViolation(
                f"Trade risk ${risk_amount:.2f} exceeds max risk per trade "
                f"${max_risk_dollars:.2f} ({self.limits.max_risk_per_trade_pct*100:.1f}% "
                f"of ${self.current_equity:.2f} equity)"
            )
        
        # Check open trade count (only for new positions)
        if order.side in [OrderSide.LONG, OrderSide.BUY]:
            if len(self.open_positions) >= self.limits.max_open_trades:
                raise SafetyViolation(
                    f"Maximum open trades ({self.limits.max_open_trades}) reached. "
                    f"Currently have {len(self.open_positions)} open positions."
                )
        
        # Check exposure limit
        current_exposure = self._calculate_total_exposure()
        new_exposure = current_exposure + position_value
        max_exposure_dollars = self.current_equity * self.limits.max_exposure_pct
        
        if new_exposure > max_exposure_dollars:
            raise SafetyViolation(
                f"Total exposure ${new_exposure:.2f} would exceed max exposure "
                f"${max_exposure_dollars:.2f} ({self.limits.max_exposure_pct*100:.1f}% "
                f"of ${self.current_equity:.2f} equity). "
                f"Current exposure: ${current_exposure:.2f}"
            )
        
        logger.debug(
            f"Pre-trade check passed: risk=${risk_amount:.2f}, "
            f"exposure=${new_exposure:.2f}, "
            f"open_trades={len(self.open_positions)}"
        )
    
    def check_post_trade(self, new_equity: float) -> None:
        """
        Check equity after trade execution.
        
        Called AFTER a trade is executed and equity is updated.
        Trips kill switch if daily loss limit exceeded.
        
        Module 27: Uses peak_equity for drawdown calculation instead of starting_equity.
        This prevents false positives on normal intra-day fluctuations.
        
        Args:
            new_equity: Current equity after trade
        """
        self.current_equity = new_equity
        self.daily_pnl = new_equity - self.session_start_equity
        
        # Module 27: Update peak equity
        self.peak_equity = max(self.peak_equity, new_equity)
        
        # Module 27: Calculate drawdown from peak (not from starting equity)
        drawdown_pct = (self.peak_equity - new_equity) / self.peak_equity if self.peak_equity > 0 else 0.0
        drawdown_amount = self.peak_equity - new_equity
        
        # Check if drawdown limit exceeded
        if drawdown_pct >= self.limits.max_daily_loss_pct:
            self._halt_trading(
                f"Drawdown limit exceeded: {drawdown_pct*100:.2f}% "
                f"(max: {self.limits.max_daily_loss_pct*100:.2f}%). "
                f"Loss: ${drawdown_amount:.2f} from peak equity ${self.peak_equity:.2f}."
            )
            logger.critical(
                f"[KILL SWITCH] TRADING HALTED: Drawdown limit breached! "
                f"Drawdown: ${drawdown_amount:.2f} ({drawdown_pct*100:.2f}%) from peak ${self.peak_equity:.2f}"
            )
        
        logger.debug(
            f"Post-trade check: equity=${new_equity:.2f}, "
            f"peak=${self.peak_equity:.2f}, "
            f"drawdown=${drawdown_amount:.2f} ({drawdown_pct*100:.2f}%), "
            f"daily_pnl=${self.daily_pnl:+.2f}"
        )
    
    def kill_switch_engaged(self) -> bool:
        """
        Check if kill switch is engaged.
        
        Returns True if:
        1. Internal trading_halted flag is set, OR
        2. Kill switch environment variable is set to truthy value
        
        Returns:
            True if trading should be halted
        """
        # Check internal halt flag
        if self.trading_halted:
            return True
        
        # Check environment variable
        env_value = os.environ.get(self.limits.kill_switch_env_var, "").lower()
        if env_value in ["1", "true", "yes", "on"]:
            if not self.trading_halted:
                # First time detecting env kill switch
                self._halt_trading(
                    f"Environment kill switch engaged: "
                    f"{self.limits.kill_switch_env_var}={env_value}"
                )
            return True
        
        return False
    
    def record_position_open(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        side: OrderSide
    ) -> None:
        """
        Record a new open position.
        
        Args:
            symbol: Trading pair symbol
            quantity: Position size
            entry_price: Entry price
            side: OrderSide (LONG or SHORT)
        """
        position_value = quantity * entry_price
        
        self.open_positions[symbol] = {
            "quantity": quantity,
            "entry_price": entry_price,
            "position_value": position_value,
            "side": side,
            "opened_at": datetime.now()
        }
        
        logger.info(
            f"Position opened: {symbol} {side.value} "
            f"{quantity} @ ${entry_price:.2f} "
            f"(value: ${position_value:.2f})"
        )
    
    def record_position_close(self, symbol: str, exit_price: float, pnl: float) -> None:
        """
        Record position close.
        
        Args:
            symbol: Trading pair symbol
            exit_price: Exit price
            pnl: Realized profit/loss
        """
        if symbol in self.open_positions:
            position = self.open_positions.pop(symbol)
            logger.info(
                f"Position closed: {symbol} "
                f"exit=${exit_price:.2f}, "
                f"pnl=${pnl:+.2f}"
            )
        else:
            logger.warning(f"Attempted to close unknown position: {symbol}")
    
    def _calculate_total_exposure(self) -> float:
        """
        Calculate total exposure across all open positions.
        
        Returns:
            Total dollar value of all open positions
        """
        return sum(
            pos["position_value"]
            for pos in self.open_positions.values()
        )
    
    def _halt_trading(self, reason: str) -> None:
        """
        Halt all trading.
        
        Args:
            reason: Reason for halting
        """
        self.trading_halted = True
        self.halt_reason = reason
        logger.critical(f"[KILL SWITCH] TRADING HALTED: {reason}")
    
    def reset_daily_limits(self, new_starting_equity: Optional[float] = None) -> None:
        """
        Reset daily limits for a new trading day.
        
        Args:
            new_starting_equity: New starting equity (defaults to current equity)
        """
        self.starting_equity = new_starting_equity or self.current_equity
        self.daily_pnl = 0.0
        self.session_start = datetime.now()
        self.trading_halted = False
        self.halt_reason = None
        self.consecutive_failures = 0
        
        logger.info(
            f"Daily limits reset: starting_equity=${self.starting_equity:.2f}, "
            f"session_start={self.session_start}"
        )
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current safety monitor status.
        
        Returns:
            Dictionary with current state
        """
        current_exposure = self._calculate_total_exposure()
        
        daily_loss_pct = 0.0
        if self.current_equity < self.starting_equity:
            daily_loss_pct = (self.starting_equity - self.current_equity) / self.starting_equity
        
        return {
            "trading_halted": self.trading_halted,
            "halt_reason": self.halt_reason,
            "kill_switch_engaged": self.kill_switch_engaged(),
            "starting_equity": self.starting_equity,
            "current_equity": self.current_equity,
            "daily_pnl": self.daily_pnl,
            "daily_loss_pct": daily_loss_pct,
            "open_positions": len(self.open_positions),
            "total_exposure": current_exposure,
            "exposure_pct": current_exposure / self.current_equity if self.current_equity > 0 else 0,
            "limits": {
                "max_daily_loss_pct": self.limits.max_daily_loss_pct,
                "max_risk_per_trade_pct": self.limits.max_risk_per_trade_pct,
                "max_exposure_pct": self.limits.max_exposure_pct,
                "max_open_trades": self.limits.max_open_trades
            }
        }


class SafetyViolation(Exception):
    """Raised when a safety limit would be violated."""
    pass
