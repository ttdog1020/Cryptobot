"""
MODULE 18: Order Types

Standardized order types, statuses, and data structures.
Used across backtesting, paper trading, and live execution.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime


class OrderSide(Enum):
    """Order side/direction."""
    LONG = "LONG"
    SHORT = "SHORT"
    BUY = "BUY"    # Alias for LONG
    SELL = "SELL"  # Alias for SHORT
    
    @classmethod
    def from_signal(cls, signal: str) -> 'OrderSide':
        """Convert signal string to OrderSide."""
        signal_map = {
            'LONG': cls.LONG,
            'SHORT': cls.SHORT,
            'BUY': cls.BUY,
            'SELL': cls.SELL
        }
        return signal_map.get(signal.upper(), cls.LONG)


class OrderType(Enum):
    """Order type."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class OrderStatus(Enum):
    """Order execution status."""
    NEW = "NEW"              # Order created but not submitted
    PENDING = "PENDING"      # Submitted, awaiting fill
    FILLED = "FILLED"        # Fully executed
    PARTIAL = "PARTIAL"      # Partially filled
    CANCELLED = "CANCELLED"  # Cancelled by user
    REJECTED = "REJECTED"    # Rejected by exchange/risk engine
    EXPIRED = "EXPIRED"      # Expired (limit orders)


@dataclass
class OrderRequest:
    """
    Order request from strategy to execution engine.
    
    This is the standard format for all order submissions.
    """
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    
    # Prices
    price: Optional[float] = None              # For limit orders
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # Metadata
    strategy_name: Optional[str] = None
    signal_confidence: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Internal tracking
    order_id: Optional[str] = None
    
    def __post_init__(self):
        """Validate order request."""
        if self.quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {self.quantity}")
        
        if isinstance(self.side, str):
            self.side = OrderSide.from_signal(self.side)
        
        if isinstance(self.order_type, str):
            self.order_type = OrderType[self.order_type.upper()]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'order_type': self.order_type.value,
            'quantity': self.quantity,
            'price': self.price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'strategy_name': self.strategy_name,
            'signal_confidence': self.signal_confidence,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'metadata': self.metadata
        }


@dataclass
class OrderFill:
    """
    Order fill/execution details.
    
    Represents a completed or partial order execution.
    """
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    fill_price: float
    fill_time: datetime = field(default_factory=datetime.now)
    
    # Fees and costs
    commission: float = 0.0
    slippage: float = 0.0
    
    # Additional info
    fill_type: str = "COMPLETE"  # COMPLETE, PARTIAL
    execution_venue: str = "PAPER"  # PAPER, BINANCE, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def fill_value(self) -> float:
        """Total value of fill (price * quantity)."""
        return self.fill_price * self.quantity
    
    @property
    def total_cost(self) -> float:
        """Total cost including fees."""
        return self.fill_value + self.commission
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side.value if isinstance(self.side, OrderSide) else self.side,
            'quantity': self.quantity,
            'fill_price': self.fill_price,
            'fill_value': self.fill_value,
            'fill_time': self.fill_time.isoformat() if self.fill_time else None,
            'commission': self.commission,
            'slippage': self.slippage,
            'total_cost': self.total_cost,
            'fill_type': self.fill_type,
            'execution_venue': self.execution_venue,
            'metadata': self.metadata
        }


@dataclass
class ExecutionResult:
    """
    Result of order execution attempt.
    
    Returned by ExecutionEngine after submitting an order.
    Module 27: Added filled_quantity to prevent AttributeError.
    """
    success: bool
    status: OrderStatus
    order_id: Optional[str] = None
    fill: Optional[OrderFill] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def filled_quantity(self) -> float:
        """Get filled quantity from fill object or return 0."""
        if self.fill:
            return self.fill.quantity
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'success': self.success,
            'status': self.status.value if isinstance(self.status, OrderStatus) else self.status,
            'order_id': self.order_id,
            'fill': self.fill.to_dict() if self.fill else None,
            'error': self.error,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'metadata': self.metadata
        }
    
    @classmethod
    def success_result(
        cls,
        order_id: str,
        fill: OrderFill,
        metadata: Optional[Dict[str, Any]] = None
    ) -> 'ExecutionResult':
        """Create a successful execution result."""
        return cls(
            success=True,
            status=OrderStatus.FILLED,
            order_id=order_id,
            fill=fill,
            metadata=metadata or {}
        )
    
    @classmethod
    def failure_result(
        cls,
        status: OrderStatus,
        error: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> 'ExecutionResult':
        """Create a failed execution result."""
        return cls(
            success=False,
            status=status,
            error=error,
            metadata=metadata or {}
        )


@dataclass
class Position:
    """
    Open trading position.
    
    Tracks entry, current state, and PnL.
    """
    symbol: str
    side: OrderSide
    quantity: float
    entry_price: float
    entry_time: datetime = field(default_factory=datetime.now)
    
    # Risk management
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # Current state
    current_price: float = 0.0
    
    # Trailing stop tracking (for long positions)
    highest_price: float = 0.0  # Highest price seen since entry
    
    # Metadata
    strategy_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized profit/loss."""
        if self.current_price == 0:
            return 0.0
        
        if self.side in [OrderSide.LONG, OrderSide.BUY]:
            return (self.current_price - self.entry_price) * self.quantity
        else:  # SHORT/SELL
            return (self.entry_price - self.current_price) * self.quantity
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """Calculate unrealized PnL as percentage."""
        if self.entry_price == 0:
            return 0.0
        return (self.unrealized_pnl / (self.entry_price * self.quantity)) * 100
    
    @property
    def position_value(self) -> float:
        """Current position value."""
        return self.current_price * self.quantity
    
    def update_price(self, new_price: float):
        """Update current price for PnL calculation."""
        self.current_price = new_price
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'side': self.side.value if isinstance(self.side, OrderSide) else self.side,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'current_price': self.current_price,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_pct': self.unrealized_pnl_pct,
            'position_value': self.position_value,
            'strategy_name': self.strategy_name,
            'metadata': self.metadata
        }
