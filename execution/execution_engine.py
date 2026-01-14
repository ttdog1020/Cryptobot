"""
MODULE 18 + 24: Execution Engine

Central routing layer for all order execution.
Routes orders to PaperTrader or real exchange clients.

MODULE 24: Added SafetyMonitor integration and multi-mode support.
"""

import logging
from typing import Optional, Dict, Any, Union
from datetime import datetime

from .order_types import OrderRequest, OrderSide, OrderType, ExecutionResult, OrderStatus
from .paper_trader import PaperTrader
from .exchange_client_base import ExchangeClientBase
from .safety import SafetyMonitor, SafetyLimits, SafetyViolation

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    Execution engine for routing and managing orders.
    
    Central access point for all order execution in the system.
    Routes orders to appropriate execution venue (paper or real exchange).
    
    Integrates with:
    - RiskEngine (Module 14) output
    - Strategies (Module 15, 17)
    - Backtesting system
    - Live runtime (Module 16)
    """
    
    def __init__(
        self,
        execution_mode: str = "paper",
        paper_trader: Optional[PaperTrader] = None,
        exchange_client: Optional[ExchangeClientBase] = None,
        enable_validation: bool = True,
        safety_monitor: Optional[SafetyMonitor] = None
    ):
        """
        Initialize execution engine.
        
        Args:
            execution_mode: "paper", "dry_run", or "live"
            paper_trader: PaperTrader instance for paper trading
            exchange_client: Exchange client for dry_run/live trading
            enable_validation: Whether to validate orders before submission
            safety_monitor: SafetyMonitor for enforcing global safety limits
        """
        self.execution_mode = execution_mode
        self.enable_validation = enable_validation
        self.safety_monitor = safety_monitor
        
        # Set up execution venue
        if execution_mode == "paper":
            self.paper_trader = paper_trader or PaperTrader()
            self.exchange_client = None
            logger.info("ExecutionEngine initialized in PAPER mode")
        elif execution_mode in ["dry_run", "live"]:
            if exchange_client is None:
                raise ValueError(f"{execution_mode} mode requires exchange_client")
            self.exchange_client = exchange_client
            self.paper_trader = None
            logger.info(f"ExecutionEngine initialized in {execution_mode.upper()} mode "
                       f"(Exchange: {exchange_client.exchange_name})")
        else:
            raise ValueError(f"Invalid execution_mode: {execution_mode}. "
                           f"Must be 'paper', 'dry_run', or 'live'")
        
        # Statistics
        self.total_orders = 0
        self.successful_orders = 0
        self.rejected_orders = 0
        self.consecutive_failures = 0
    
    def submit_order(
        self,
        order: OrderRequest,
        current_price: Optional[float] = None,
        validate: bool = True
    ) -> ExecutionResult:
        """
        Submit an order for execution.
        
        This is the main entry point for order submission.
        
        Args:
            order: OrderRequest to execute
            current_price: Current market price (required for paper trading)
            validate: Whether to validate order
            
        Returns:
            ExecutionResult with execution details
        """
        # Validate symbol before processing
        if not order.symbol or order.symbol == "UNKNOWN":
            raise ValueError(f"Invalid symbol passed to execution engine: {order.symbol}")
        
        self.total_orders += 1
        
        logger.info(f"[ExecutionEngine] Submitting {order.order_type.value} "
                   f"{order.side.value} order: {order.quantity} {order.symbol}")
        
        # Check safety monitor kill switch first
        if self.safety_monitor and self.safety_monitor.kill_switch_engaged():
            logger.error(f"[ExecutionEngine] Order rejected: Kill switch engaged")
            self.rejected_orders += 1
            self.consecutive_failures += 1
            return ExecutionResult.failure_result(
                status=OrderStatus.REJECTED,
                error="Trading halted: Kill switch engaged"
            )
        
        # Pre-trade safety check
        if self.safety_monitor:
            try:
                # Calculate risk and position value for safety check
                risk_amount = order.metadata.get('risk_usd', 0.0) if order.metadata else 0.0
                position_value = order.metadata.get('position_value_usd', 0.0) if order.metadata else 0.0
                
                # If not in metadata, estimate from order
                if position_value == 0.0 and current_price:
                    position_value = order.quantity * current_price
                
                self.safety_monitor.check_pre_trade(order, risk_amount, position_value)
            except SafetyViolation as e:
                logger.warning(f"[ExecutionEngine] Order rejected by safety monitor: {e}")
                self.rejected_orders += 1
                self.consecutive_failures += 1
                return ExecutionResult.failure_result(
                    status=OrderStatus.REJECTED,
                    error=f"Safety violation: {str(e)}"
                )
        
        # Validate if enabled
        if validate and self.enable_validation:
            validation_error = self._validate_order(order)
            if validation_error:
                logger.warning(f"[ExecutionEngine] Order validation failed: {validation_error}")
                self.rejected_orders += 1
                return ExecutionResult.failure_result(
                    status=OrderStatus.REJECTED,
                    error=f"Validation failed: {validation_error}"
                )
        
        # Route to appropriate execution venue
        try:
            if self.execution_mode == "paper":
                if current_price is None:
                    raise ValueError("current_price required for paper trading")
                
                result = self.paper_trader.submit_order(order, current_price)
            
            elif self.execution_mode in ["dry_run", "live"]:
                # Use exchange client (async call, need to run in event loop)
                # For now, using sync wrapper - future versions should be fully async
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                result = loop.run_until_complete(self.exchange_client.submit_order(order))
            
            else:
                raise ValueError(f"Invalid execution mode: {self.execution_mode}")
            
            # Update stats
            if result.success:
                self.successful_orders += 1
                self.consecutive_failures = 0
                logger.info(f"[ExecutionEngine] Order executed successfully: {result.order_id}")
                
                # Post-trade safety check
                if self.safety_monitor:
                    current_equity = self.get_equity()
                    self.safety_monitor.check_post_trade(current_equity)
                    
                    # Record position for safety tracking
                    if order.side in [OrderSide.LONG, OrderSide.BUY]:
                        self.safety_monitor.record_position_open(
                            symbol=order.symbol,
                            quantity=result.filled_quantity,
                            entry_price=result.average_price,
                            side=order.side
                        )
            else:
                self.rejected_orders += 1
                self.consecutive_failures += 1
                logger.warning(f"[ExecutionEngine] Order failed: {result.error}")
            
            return result
        
        except Exception as e:
            logger.error(f"[ExecutionEngine] Error executing order: {e}", exc_info=True)
            self.rejected_orders += 1
            return ExecutionResult.failure_result(
                status=OrderStatus.REJECTED,
                error=f"Execution error: {str(e)}"
            )
    
    def _validate_order(self, order: OrderRequest) -> Optional[str]:
        """
        Validate order before submission.
        
        Args:
            order: OrderRequest to validate
            
        Returns:
            Error message if invalid, None if valid
        """
        # Basic validation
        if order.quantity <= 0:
            return "Quantity must be positive"
        
        if not order.symbol:
            return "Symbol is required"
        
        # Order type specific validation
        if order.order_type == OrderType.LIMIT:
            if order.price is None or order.price <= 0:
                return "Limit orders require a positive price"
        
        # Side validation
        if order.side not in [OrderSide.LONG, OrderSide.SHORT, OrderSide.BUY, OrderSide.SELL]:
            return f"Invalid order side: {order.side}"
        
        return None
    
    def create_order_from_signal(
        self,
        signal: str,
        symbol: str,
        quantity: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        strategy_name: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> OrderRequest:
        """
        Create an OrderRequest from strategy signal.
        
        Convenience method for converting strategy outputs to orders.
        
        Args:
            signal: Signal string ('LONG', 'SHORT', 'BUY', 'SELL')
            symbol: Trading pair symbol
            quantity: Order quantity
            stop_loss: Stop loss price
            take_profit: Take profit price
            strategy_name: Name of strategy generating signal
            confidence: Signal confidence (0-1)
            metadata: Additional metadata
            
        Returns:
            OrderRequest ready for submission
        """
        order = OrderRequest(
            symbol=symbol,
            side=OrderSide.from_signal(signal),
            order_type=OrderType.MARKET,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy_name=strategy_name,
            signal_confidence=confidence,
            metadata=metadata or {}
        )
        
        return order
    
    def create_order_from_risk_output(
        self,
        risk_output: Dict[str, Any],
        strategy_name: Optional[str] = None
    ) -> OrderRequest:
        """
        Create an OrderRequest from RiskEngine output.
        
        Compatible with Module 14 RiskEngine.apply_risk_to_signal() output.
        
        Args:
            risk_output: Output from RiskEngine
            strategy_name: Name of strategy
            
        Returns:
            OrderRequest ready for submission
        """
        # Symbol must be present in risk_output
        symbol = risk_output.get('symbol')
        if not symbol or symbol == 'UNKNOWN':
            raise ValueError(f"Risk output missing valid symbol: {risk_output}")
        
        order = OrderRequest(
            symbol=symbol,
            side=OrderSide.from_signal(risk_output['side']),
            order_type=OrderType.MARKET,
            quantity=risk_output['position_size'],
            stop_loss=risk_output.get('stop_loss'),
            take_profit=risk_output.get('take_profit'),
            strategy_name=strategy_name,
            metadata={
                'entry_price': risk_output.get('entry_price'),
                'position_value_usd': risk_output.get('position_value_usd'),
                'risk_usd': risk_output.get('risk_usd')
            }
        )
        
        return order
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics."""
        return {
            'execution_mode': self.execution_mode,
            'total_orders': self.total_orders,
            'successful_orders': self.successful_orders,
            'rejected_orders': self.rejected_orders,
            'success_rate': (self.successful_orders / self.total_orders * 100) 
                           if self.total_orders > 0 else 0
        }
    
    def get_balance(self) -> float:
        """Get current balance."""
        if self.execution_mode == "paper":
            return self.paper_trader.get_balance()
        else:
            raise NotImplementedError("Live balance not yet implemented")
    
    def get_equity(self) -> float:
        """Get total equity (balance + unrealized PnL)."""
        if self.execution_mode == "paper":
            return self.paper_trader.get_equity()
        else:
            raise NotImplementedError("Live equity not yet implemented")
    
    def get_open_positions(self) -> Dict:
        """Get all open positions."""
        if self.execution_mode == "paper":
            return self.paper_trader.get_open_positions()
        else:
            raise NotImplementedError("Live positions not yet implemented")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if self.execution_mode == "paper":
            perf = self.paper_trader.get_performance_summary()
            perf['execution_stats'] = self.get_statistics()
            return perf
        else:
            raise NotImplementedError("Live performance not yet implemented")
    
    def update_positions(self, prices: Dict[str, float]):
        """
        Update position prices for PnL calculation.
        
        Args:
            prices: Dict of {symbol: current_price}
        """
        if self.execution_mode == "paper":
            self.paper_trader.update_positions(prices)
    
    def reset(self):
        """Reset execution engine (paper mode only)."""
        if self.execution_mode == "paper":
            self.paper_trader.reset()
            self.total_orders = 0
            self.successful_orders = 0
            self.rejected_orders = 0
            logger.info("ExecutionEngine reset")
        else:
            logger.warning("Reset not supported in live mode")
