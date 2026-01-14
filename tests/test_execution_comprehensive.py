"""
Tests for Execution Module - Order Types, Paper Trader, and Safety (PR9)
"""

import pytest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from execution.order_types import (
    OrderSide, OrderType, OrderStatus, OrderRequest, OrderFill, ExecutionResult, Position
)
from execution.paper_trader import PaperTrader
from execution.safety import SafetyMonitor


class TestOrderSide:
    """Test OrderSide enum and conversions"""
    
    def test_order_side_values(self):
        assert OrderSide.LONG.value == "LONG"
        assert OrderSide.SHORT.value == "SHORT"
        assert OrderSide.BUY.value == "BUY"
        assert OrderSide.SELL.value == "SELL"
    
    def test_from_signal_upper(self):
        assert OrderSide.from_signal("LONG") == OrderSide.LONG
        assert OrderSide.from_signal("SHORT") == OrderSide.SHORT
        assert OrderSide.from_signal("BUY") == OrderSide.BUY
        assert OrderSide.from_signal("SELL") == OrderSide.SELL
    
    def test_from_signal_lower(self):
        assert OrderSide.from_signal("long") == OrderSide.LONG
        assert OrderSide.from_signal("short") == OrderSide.SHORT
    
    def test_from_signal_invalid_defaults_to_long(self):
        assert OrderSide.from_signal("INVALID") == OrderSide.LONG


class TestOrderType:
    """Test OrderType enum"""
    
    def test_order_type_values(self):
        assert OrderType.MARKET.value == "MARKET"
        assert OrderType.LIMIT.value == "LIMIT"
        assert OrderType.STOP_LOSS.value == "STOP_LOSS"
        assert OrderType.TAKE_PROFIT.value == "TAKE_PROFIT"


class TestOrderStatus:
    """Test OrderStatus enum"""
    
    def test_all_statuses_exist(self):
        statuses = [
            OrderStatus.NEW,
            OrderStatus.PENDING,
            OrderStatus.FILLED,
            OrderStatus.PARTIAL,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED
        ]
        assert len(statuses) == 7


class TestOrderRequest:
    """Test OrderRequest dataclass"""
    
    def test_basic_market_order(self):
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.5
        )
        assert order.symbol == "BTCUSDT"
        assert order.side == OrderSide.LONG
        assert order.quantity == 0.5
    
    def test_limit_order(self):
        order = OrderRequest(
            symbol="ETHUSDT",
            side=OrderSide.SHORT,
            order_type=OrderType.LIMIT,
            quantity=2.0,
            price=1800.0
        )
        assert order.price == 1800.0
    
    def test_order_with_stop_loss_take_profit(self):
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1,
            stop_loss=40000.0,
            take_profit=50000.0
        )
        assert order.stop_loss == 40000.0
        assert order.take_profit == 50000.0
    
    def test_quantity_validation_positive(self):
        with pytest.raises(ValueError):
            OrderRequest(
                symbol="BTCUSDT",
                side=OrderSide.LONG,
                order_type=OrderType.MARKET,
                quantity=-1.0  # Invalid
            )
    
    def test_quantity_validation_zero(self):
        with pytest.raises(ValueError):
            OrderRequest(
                symbol="BTCUSDT",
                side=OrderSide.LONG,
                order_type=OrderType.MARKET,
                quantity=0.0  # Invalid
            )
    
    def test_side_string_conversion(self):
        order = OrderRequest(
            symbol="BTCUSDT",
            side="long",  # String
            order_type=OrderType.MARKET,
            quantity=0.5
        )
        assert order.side == OrderSide.LONG
    
    def test_order_type_string_conversion(self):
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type="market",  # String
            quantity=0.5
        )
        assert order.order_type == OrderType.MARKET
    
    def test_to_dict_serialization(self):
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.5,
            strategy_name="scalping_ema_rsi"
        )
        d = order.to_dict()
        assert d['symbol'] == "BTCUSDT"
        assert d['side'] == "LONG"
        assert d['quantity'] == 0.5
        assert d['strategy_name'] == "scalping_ema_rsi"


class TestPosition:
    """Test Position tracking"""
    
    def test_position_basic_creation(self):
        position = Position(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.5,
            entry_price=45000.0
        )
        assert position.symbol == "BTCUSDT"
        assert position.quantity == 0.5
    
    def test_position_unrealized_pnl_long(self):
        position = Position(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=1.0,
            entry_price=45000.0
        )
        position.update_price(46000.0)
        
        assert position.unrealized_pnl == 1000.0
        assert position.unrealized_pnl_pct == pytest.approx(2.22, rel=1e-2)
    
    def test_position_unrealized_pnl_short(self):
        position = Position(
            symbol="BTCUSDT",
            side=OrderSide.SHORT,
            quantity=1.0,
            entry_price=45000.0
        )
        position.update_price(44000.0)
        
        assert position.unrealized_pnl == 1000.0  # Profit on short
    
    def test_position_with_stop_loss(self):
        position = Position(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.1,
            entry_price=45000.0,
            stop_loss=44000.0
        )
        assert position.stop_loss == 44000.0
    
    def test_position_with_take_profit(self):
        position = Position(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.1,
            entry_price=45000.0,
            take_profit=47000.0
        )
        assert position.take_profit == 47000.0
    
    def test_position_value_calculation(self):
        position = Position(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.5,
            entry_price=45000.0
        )
        position.update_price(45000.0)
        
        assert position.position_value == 22500.0  # 0.5 * 45000


class TestExecutionResult:
    """Test ExecutionResult status tracking"""
    
    def test_execution_result_filled(self):
        fill = OrderFill(
            order_id="order_123",
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.5,
            fill_price=45000.0,
            fill_time=datetime.now()
        )
        result = ExecutionResult(
            success=True,
            status=OrderStatus.FILLED,
            order_id="order_123",
            fill=fill
        )
        assert result.status == OrderStatus.FILLED
        assert result.success
    
    def test_execution_result_partial_fill(self):
        fill = OrderFill(
            order_id="order_456",
            symbol="ETHUSDT",
            side=OrderSide.SHORT,
            quantity=0.3,
            fill_price=1800.0,
            fill_time=datetime.now()
        )
        result = ExecutionResult(
            success=False,
            status=OrderStatus.PARTIAL,
            order_id="order_456",
            fill=fill
        )
        assert result.status == OrderStatus.PARTIAL
    
    def test_execution_result_rejected(self):
        result = ExecutionResult(
            success=False,
            status=OrderStatus.REJECTED,
            error="Insufficient balance"
        )
        assert result.status == OrderStatus.REJECTED
        assert "Insufficient balance" in result.error
    
    def test_execution_result_success_factory(self):
        fill = OrderFill(
            order_id="order_789",
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=1.0,
            fill_price=45000.0,
            fill_time=datetime.now()
        )
        result = ExecutionResult.success_result("order_789", fill)
        
        assert result.success
        assert result.status == OrderStatus.FILLED
    
    def test_execution_result_failure_factory(self):
        result = ExecutionResult.failure_result(
            OrderStatus.REJECTED,
            "Order rejected by exchange"
        )
        
        assert not result.success
        assert result.status == OrderStatus.REJECTED
        assert "rejected" in result.error.lower()


class TestEdgeCases:
    """Edge case and error handling"""
    
    def test_order_with_extreme_quantities(self):
        """Test handling of very small and very large quantities"""
        # Small quantity
        order_small = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.0001  # 0.0001 BTC
        )
        assert order_small.quantity == 0.0001
        
        # Large quantity
        order_large = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=1000.0  # 1000 BTC
        )
        assert order_large.quantity == 1000.0
    
    def test_position_with_zero_price(self):
        """Test position with zero current price"""
        position = Position(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.1,
            entry_price=45000.0,
            current_price=0.0
        )
        # Should not crash, unrealized PnL should be 0
        assert position.unrealized_pnl == 0.0
    
    def test_order_fill_serialization(self):
        """Test OrderFill serialization"""
        fill = OrderFill(
            order_id="order_123",
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.5,
            fill_price=45000.0,
            fill_time=datetime.now()
        )
        d = fill.to_dict()
        assert d['order_id'] == "order_123"
        assert d['quantity'] == 0.5
