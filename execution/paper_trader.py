"""
MODULE 18/19: Paper Trader

Fully offline, safe paper trading engine for virtual order execution.
Tracks positions, balance, and PnL without any real exchange interaction.

Module 19: Added session-based logging with timestamped log files.
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pathlib import Path
import uuid
import pandas as pd

from .order_types import (
    OrderRequest,
    OrderFill,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    ExecutionResult
)

logger = logging.getLogger(__name__)


class PaperTrader:
    """
    Virtual trading engine for paper trading.
    
    Features:
    - Maintain virtual balance
    - Track open positions per symbol
    - Fill orders at next-tick prices with slippage
    - Calculate realized and unrealized PnL
    - Full trade history logging
    - Session-based timestamped log files (Module 19)
    """
    
    def __init__(
        self,
        starting_balance: float = 10000.0,
        slippage: float = 0.0005,  # 0.05% slippage
        commission_rate: float = 0.001,  # 0.1% commission
        allow_shorting: bool = True,
        log_trades: bool = True,
        log_file: Optional[Union[str, Path]] = None
    ):
        """
        Initialize paper trader.
        
        Args:
            starting_balance: Initial virtual balance (USD)
            slippage: Slippage as fraction (0.0005 = 0.05%)
            commission_rate: Commission as fraction (0.001 = 0.1%)
            allow_shorting: Whether to allow short positions
            log_trades: Whether to log trades to file
            log_file: Path to trade log file (None = auto-generate timestamped path)
        """
        self.starting_balance = starting_balance
        self.balance = starting_balance
        self.slippage = slippage
        self.commission_rate = commission_rate
        self.allow_shorting = allow_shorting
        self.log_trades = log_trades
        
        # Positions: {symbol: Position}
        self.positions: Dict[str, Position] = {}
        
        # Trade history
        self.trade_history: List[OrderFill] = []
        self.closed_trades: List[Dict[str, Any]] = []
        
        # Performance tracking
        self.realized_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        # Session timestamp for logging
        self.session_start = datetime.now()
        
        # Log file - auto-generate timestamped path if None
        if log_file is None:
            timestamp = self.session_start.strftime("%Y%m%d_%H%M%S")
            self.log_file = Path(f"logs/paper_trades/paper_trades_{timestamp}.csv")
        else:
            self.log_file = Path(log_file)
        
        if self.log_trades:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self._log_initial_state()
            logger.info(f"[LOG] Paper trades will be logged to: {self.log_file}")
        
        # Peak equity for drawdown tracking (Module 27)
        self.peak_equity = starting_balance
        
        # Trailing stop configuration (optional feature)
        self.enable_trailing_stop = False
        self.trailing_stop_pct = 0.02  # Default 2%
        
        logger.info(f"PaperTrader initialized: Balance=${starting_balance:.2f}, "
                   f"Slippage={slippage*100:.2f}%, Commission={commission_rate*100:.2f}%")
    
    def set_risk_config(self, risk_config: Dict[str, Any]):
        """
        Set risk configuration for optional features like trailing stops.
        
        Args:
            risk_config: Risk configuration dictionary
        """
        self.enable_trailing_stop = risk_config.get("enable_trailing_stop", False)
        self.trailing_stop_pct = risk_config.get("trailing_stop_pct", 0.02)
        
        if self.enable_trailing_stop:
            logger.info(f"[OK] Trailing stop enabled: {self.trailing_stop_pct*100:.1f}% trail")
        else:
            logger.info("[OK] Trailing stop disabled")
    
    @staticmethod
    def apply_trade_result(balance: float, realized_pnl: float, commission: float = 0.0, slippage: float = 0.0) -> float:
        """
        Apply trade result to balance.
        
        Module 27: ONLY way to update balance after a closed trade.
        Never use fill_value directly - only realized PnL minus costs.
        
        Args:
            balance: Current balance
            realized_pnl: Realized profit/loss from trade
            commission: Commission paid
            slippage: Slippage cost
            
        Returns:
            Updated balance rounded to 2 decimals
        """
        net = realized_pnl - commission - slippage
        balance += net
        return round(balance, 2)
    
    def _log_initial_state(self):
        """Log initial account state before any trades to capture true starting balance."""
        if not self.log_file:
            return
        
        # Create log file with headers if it doesn't exist
        # Use pandas DataFrame columns to match _log_trade format
        import pandas as pd
        
        init_data = {
            'timestamp': datetime.now().isoformat(),
            'session_start': self.session_start.isoformat(),
            'order_id': '',
            'symbol': '',
            'action': 'INIT',
            'side': '',
            'quantity': 0.0,
            'entry_price': 0.0,
            'fill_price': 0.0,
            'fill_value': 0.0,
            'commission': 0.0,
            'slippage': 0.0,
            'realized_pnl': 0.0,
            'pnl_pct': 0.0,
            'balance': self.balance,
            'equity': self.balance,
            'open_positions': 0
        }
        
        df = pd.DataFrame([init_data])
        df.to_csv(self.log_file, index=False)
    
    def submit_order(
        self,
        order: OrderRequest,
        current_price: float
    ) -> ExecutionResult:
        """
        Submit an order for paper trading execution.
        
        Args:
            order: OrderRequest to execute
            current_price: Current market price
            
        Returns:
            ExecutionResult with fill details
        """
        # Generate order ID
        if not order.order_id:
            order.order_id = f"PAPER_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"[PAPER] Submitting {order.side.value} order: "
                   f"{order.quantity} {order.symbol} @ ${current_price:.2f}")
        
        # Validate order
        validation_error = self._validate_order(order, current_price)
        if validation_error:
            logger.warning(f"[PAPER] Order rejected: {validation_error}")
            return ExecutionResult.failure_result(
                status=OrderStatus.REJECTED,
                error=validation_error
            )
        
        # Execute order
        try:
            fill = self._execute_order(order, current_price)
            
            # Update positions and balance
            self._update_position(order, fill)
            
            # Log trade
            if self.log_trades:
                self._log_trade(fill)
            
            logger.info(f"[PAPER] Order filled: {fill.order_id} - "
                       f"{fill.quantity} @ ${fill.fill_price:.2f} "
                       f"(slippage: ${fill.slippage:.2f})")
            
            return ExecutionResult.success_result(
                order_id=order.order_id,
                fill=fill,
                metadata={'paper_trade': True}
            )
        
        except Exception as e:
            logger.error(f"[PAPER] Error executing order: {e}", exc_info=True)
            return ExecutionResult.failure_result(
                status=OrderStatus.REJECTED,
                error=str(e)
            )
    
    def _validate_order(self, order: OrderRequest, current_price: float) -> Optional[str]:
        """Validate order can be executed."""
        # Check shorting
        if not self.allow_shorting and order.side in [OrderSide.SHORT, OrderSide.SELL]:
            return "Shorting not allowed"
        
        # Check balance for long positions
        if order.side in [OrderSide.LONG, OrderSide.BUY]:
            estimated_cost = current_price * order.quantity * (1 + self.commission_rate + self.slippage)
            
            if estimated_cost > self.balance:
                return f"Insufficient balance: need ${estimated_cost:.2f}, have ${self.balance:.2f}"
        
        # Check for conflicting positions
        if order.symbol in self.positions:
            existing_side = self.positions[order.symbol].side
            
            # If closing a position, that's OK
            if (existing_side in [OrderSide.LONG, OrderSide.BUY] and 
                order.side in [OrderSide.SHORT, OrderSide.SELL]):
                # Closing long
                pass
            elif (existing_side in [OrderSide.SHORT, OrderSide.SELL] and 
                  order.side in [OrderSide.LONG, OrderSide.BUY]):
                # Closing short
                pass
            else:
                return f"Cannot add to existing {existing_side.value} position"
        
        return None
    
    def _execute_order(self, order: OrderRequest, current_price: float) -> OrderFill:
        """Execute order and create fill."""
        # Calculate fill price with slippage
        if order.side in [OrderSide.LONG, OrderSide.BUY]:
            # Buying - pay more
            slippage_amount = current_price * self.slippage
            fill_price = current_price + slippage_amount
        else:
            # Selling/Shorting - receive less
            slippage_amount = current_price * self.slippage
            fill_price = current_price - slippage_amount
        
        # Calculate commission
        fill_value = fill_price * order.quantity
        commission = fill_value * self.commission_rate
        
        # Create fill
        fill = OrderFill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=fill_price,
            commission=commission,
            slippage=slippage_amount * order.quantity,
            execution_venue="PAPER",
            metadata={
                'strategy': order.strategy_name,
                'confidence': order.signal_confidence,
                'stop_loss': order.stop_loss,
                'take_profit': order.take_profit
            }
        )
        
        return fill
    
    def _update_position(self, order: OrderRequest, fill: OrderFill):
        """Update positions and balance after fill."""
        symbol = order.symbol
        
        # Check if closing existing position
        if symbol in self.positions:
            self._close_position(symbol, fill)
        else:
            self._open_position(order, fill)
    
    def _open_position(self, order: OrderRequest, fill: OrderFill):
        """Open a new position."""
        symbol = order.symbol
        
        # Create position
        position = Position(
            symbol=symbol,
            side=order.side,
            quantity=order.quantity,
            entry_price=fill.fill_price,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            current_price=fill.fill_price,
            highest_price=fill.fill_price,  # Initialize for trailing stop
            strategy_name=order.strategy_name,
            metadata=fill.metadata
        )
        
        self.positions[symbol] = position
        
        # CASH+EQUITY MODEL: Balance does NOT change on OPEN
        # Only unrealized PnL changes, which affects equity but not cash balance
        
        # Update peak equity (equity = balance + unrealized PnL)
        self.peak_equity = max(self.peak_equity, self.get_equity())
        
        logger.info(f"[PAPER] Opened {position.side.value} position: "
                   f"{position.quantity} {symbol} @ ${position.entry_price:.2f}, "
                   f"Equity: ${self.get_equity():.2f}, Balance: ${self.balance:.2f}")
        
        self.trade_history.append(fill)
    
    def _close_position(self, symbol: str, fill: OrderFill):
        """Close an existing position."""
        position = self.positions[symbol]
        
        # Calculate realized PnL (price difference * quantity)
        if position.side in [OrderSide.LONG, OrderSide.BUY]:
            # Closing long with sell: (exit - entry) * quantity
            realized_pnl = (fill.fill_price - position.entry_price) * position.quantity
        else:
            # Closing short with buy: (entry - exit) * quantity
            realized_pnl = (position.entry_price - fill.fill_price) * position.quantity
        
        # CASH+EQUITY MODEL: Update balance ONLY via apply_trade_result on CLOSE
        # This is the ONLY place where balance (cash) changes
        self.balance = self.apply_trade_result(
            balance=self.balance,
            realized_pnl=realized_pnl,
            commission=fill.commission,
            slippage=fill.slippage
        )
        
        # Update stats (store net PnL after costs)
        net_pnl = realized_pnl - fill.commission - fill.slippage
        self.realized_pnl += net_pnl
        self.total_trades += 1
        
        # Update peak equity after closing trade
        self.peak_equity = max(self.peak_equity, self.get_equity())
        
        if net_pnl > 0:
            self.winning_trades += 1
        elif net_pnl < 0:
            self.losing_trades += 1
        
        # Log closed trade (Module 27: Use net PnL after costs)
        closed_trade = {
            'symbol': symbol,
            'side': position.side.value,
            'quantity': position.quantity,
            'entry_price': position.entry_price,
            'exit_price': fill.fill_price,
            'entry_time': position.entry_time,
            'exit_time': fill.fill_time,
            'realized_pnl': net_pnl,
            'pnl_pct': (net_pnl / (position.entry_price * position.quantity)) * 100,
            'strategy': position.strategy_name
        }
        self.closed_trades.append(closed_trade)
        
        logger.info(f"[PAPER] Closed {position.side.value} position: "
                   f"{position.quantity} {symbol} - "
                   f"Entry: ${position.entry_price:.2f}, Exit: ${fill.fill_price:.2f}, "
                   f"PnL: ${net_pnl:.2f} ({closed_trade['pnl_pct']:.2f}%), "
                   f"Balance: ${self.balance:.2f}")
        
        # Remove position
        del self.positions[symbol]
        self.trade_history.append(fill)
    
    def update_positions(self, prices: Dict[str, float]):
        """
        Update all position prices for unrealized PnL calculation.
        Also applies trailing stop logic if enabled.
        
        Args:
            prices: Dict of {symbol: current_price}
        """
        for symbol, position in self.positions.items():
            if symbol in prices:
                current_price = prices[symbol]
                position.update_price(current_price)
                
                # Apply trailing stop logic if enabled
                if self.enable_trailing_stop:
                    self._apply_trailing_stop(position, current_price)
    
    def _apply_trailing_stop(self, position: 'Position', current_price: float):
        """
        Apply trailing stop logic to a position.
        Only tightens the stop, never loosens it.
        
        Args:
            position: Position to update
            current_price: Current market price
        """
        # Only support LONG positions for now
        if position.side not in [OrderSide.LONG, OrderSide.BUY]:
            return
        
        # Update highest price seen
        if current_price > position.highest_price:
            old_highest = position.highest_price
            position.highest_price = current_price
            
            # Calculate new trailing stop
            new_trail_stop = position.highest_price * (1 - self.trailing_stop_pct)
            
            # Only tighten stop, never loosen
            if position.stop_loss is not None:
                old_stop = position.stop_loss
                position.stop_loss = max(position.stop_loss, new_trail_stop)
                
                # Log only when stop actually tightens
                if position.stop_loss > old_stop:
                    logger.info(
                        f"[INFO] Trailing stop updated: symbol={position.symbol}, "
                        f"highest=${position.highest_price:.2f}, "
                        f"stop=${position.stop_loss:.2f} "
                        f"(+${position.stop_loss - old_stop:.2f})"
                    )
            else:
                # No initial stop loss, set one based on trailing logic
                position.stop_loss = new_trail_stop
                logger.info(
                    f"[INFO] Trailing stop initialized: symbol={position.symbol}, "
                    f"stop=${position.stop_loss:.2f}"
                )
    
    def check_exit_conditions(self, prices: Dict[str, float]) -> List[str]:
        """
        Check if any positions should be closed based on SL/TP.
        
        Args:
            prices: Dict of {symbol: current_price}
            
        Returns:
            List of symbols that should be closed
        """
        symbols_to_close = []
        
        for symbol, position in self.positions.items():
            if symbol not in prices:
                continue
            
            current_price = prices[symbol]
            should_close = False
            close_reason = ""
            
            # Check stop loss
            if position.stop_loss is not None:
                if position.side in [OrderSide.LONG, OrderSide.BUY]:
                    # Long: close if price <= stop
                    if current_price <= position.stop_loss:
                        should_close = True
                        close_reason = f"STOP LOSS (${current_price:.2f} <= ${position.stop_loss:.2f})"
                else:
                    # Short: close if price >= stop
                    if current_price >= position.stop_loss:
                        should_close = True
                        close_reason = f"STOP LOSS (${current_price:.2f} >= ${position.stop_loss:.2f})"
            
            # Check take profit
            if not should_close and position.take_profit is not None:
                if position.side in [OrderSide.LONG, OrderSide.BUY]:
                    # Long: close if price >= TP
                    if current_price >= position.take_profit:
                        should_close = True
                        close_reason = f"TAKE PROFIT (${current_price:.2f} >= ${position.take_profit:.2f})"
                else:
                    # Short: close if price <= TP
                    if current_price <= position.take_profit:
                        should_close = True
                        close_reason = f"TAKE PROFIT (${current_price:.2f} <= ${position.take_profit:.2f})"
            
            if should_close:
                logger.info(f"[EXIT] {symbol}: {close_reason}")
                symbols_to_close.append(symbol)
        
        return symbols_to_close
    
    def get_open_positions(self) -> Dict[str, Position]:
        """Get all open positions."""
        return self.positions.copy()
    
    def close_all_positions(self, market_price_provider):
        """
        Market-close all open positions using the latest available price.
        
        This is called on shutdown to flatten the portfolio and ensure all
        trades are logged as complete round-trips (OPEN + CLOSE).
        
        Args:
            market_price_provider: Callable that takes symbol and returns current price
        """
        if not self.positions:
            logger.info("[PAPER] No open positions to close")
            return
        
        logger.info(f"[PAPER] Flattening {len(self.positions)} open position(s)...")
        
        # Close all positions (iterate over copy to avoid modification during iteration)
        for symbol in list(self.positions.keys()):
            position = self.positions[symbol]
            
            # Get latest market price
            try:
                close_price = market_price_provider(symbol)
            except Exception as e:
                logger.error(f"[PAPER] Failed to get price for {symbol}: {e}")
                logger.warning(f"[PAPER] Using last known price for {symbol}")
                close_price = position.current_price
            
            # Determine closing side
            if position.side in [OrderSide.LONG, OrderSide.BUY]:
                close_side = OrderSide.SELL
            else:
                close_side = OrderSide.BUY
            
            # Create a synthetic close order
            close_order = OrderRequest(
                symbol=symbol,
                side=close_side,
                order_type=OrderType.MARKET,
                quantity=position.quantity,
                order_id=f"PAPER_FLATTEN_{uuid.uuid4().hex[:8]}"
            )
            
            # Submit the close order (this will log the trade automatically)
            result = self.submit_order(close_order, close_price)
            
            if result.success:
                logger.info(f"[PAPER] Flattened {symbol}: {position.side.value} position closed at ${close_price:.2f}")
            else:
                logger.error(f"[PAPER] Failed to flatten {symbol}: {result.error}")
    
    def get_balance(self) -> float:
        """Get current balance."""
        return self.balance
    
    def get_equity(self) -> float:
        """Get total equity (balance + unrealized PnL)."""
        unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        return self.balance + unrealized_pnl
    
    def get_trade_history(self) -> List[OrderFill]:
        """Get all filled orders."""
        return self.trade_history.copy()
    
    def get_closed_trades(self) -> List[Dict[str, Any]]:
        """Get all closed trades with PnL."""
        return self.closed_trades.copy()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance statistics."""
        equity = self.get_equity()
        total_return = equity - self.starting_balance
        total_return_pct = (total_return / self.starting_balance) * 100
        
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        return {
            'starting_balance': self.starting_balance,
            'current_balance': self.balance,
            'equity': equity,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': sum(pos.unrealized_pnl for pos in self.positions.values()),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'open_positions': len(self.positions)
        }
    
    def _log_trade(self, fill: OrderFill):
        """Log trade to CSV file with comprehensive details for reporting."""
        try:
            # Assert symbol is valid before writing
            assert fill.symbol and fill.symbol != "UNKNOWN", \
                f"Attempted to log trade with UNKNOWN symbol: {fill.order_id}"
            
            # Determine if this is opening or closing a position
            action = "CLOSE" if fill.symbol not in self.positions else "OPEN"
            
            # Get position info if closing
            realized_pnl = None
            pnl_pct = None
            entry_price = None
            
            if action == "CLOSE" and self.closed_trades:
                # Most recent closed trade
                recent_trade = self.closed_trades[-1]
                if recent_trade['symbol'] == fill.symbol:
                    realized_pnl = recent_trade['realized_pnl']
                    pnl_pct = recent_trade['pnl_pct']
                    entry_price = recent_trade['entry_price']
            
            trade_data = {
                'timestamp': fill.fill_time.isoformat(),
                'session_start': self.session_start.isoformat(),
                'order_id': fill.order_id,
                'symbol': fill.symbol,
                'action': action,  # OPEN or CLOSE
                'side': fill.side.value if isinstance(fill.side, OrderSide) else fill.side,
                'quantity': fill.quantity,
                'entry_price': entry_price if entry_price else fill.fill_price,
                'fill_price': fill.fill_price,
                'fill_value': fill.fill_value,
                'commission': fill.commission,
                'slippage': fill.slippage,
                'realized_pnl': realized_pnl if realized_pnl is not None else 0.0,
                'pnl_pct': pnl_pct if pnl_pct is not None else 0.0,
                'balance': self.balance,
                'equity': self.get_equity(),
                'open_positions': len(self.positions)
            }
            
            # Append to CSV
            df = pd.DataFrame([trade_data])
            
            if self.log_file.exists():
                df.to_csv(self.log_file, mode='a', header=False, index=False)
            else:
                df.to_csv(self.log_file, index=False)
        
        except Exception as e:
            logger.warning(f"Failed to log trade: {e}")
    
    def reset(self):
        """Reset paper trader to initial state."""
        self.balance = self.starting_balance
        self.positions.clear()
        self.trade_history.clear()
        self.closed_trades.clear()
        self.realized_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        logger.info("PaperTrader reset to initial state")
