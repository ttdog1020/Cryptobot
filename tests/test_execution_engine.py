"""
Module 18: Execution Engine Tests

Tests for paper trading, order execution, and execution engine functionality.
"""

import unittest
from pathlib import Path
from datetime import datetime
from execution import (
    OrderSide, OrderType, OrderStatus,
    OrderRequest, OrderFill, ExecutionResult, Position,
    PaperTrader, ExecutionEngine, ExchangeClientBase
)


class TestOrderTypes(unittest.TestCase):
    """Test order type enums and dataclasses."""
    
    def test_order_side_from_signal(self):
        """Test OrderSide.from_signal() conversion."""
        self.assertEqual(OrderSide.from_signal("LONG"), OrderSide.LONG)
        self.assertEqual(OrderSide.from_signal("SHORT"), OrderSide.SHORT)
        self.assertEqual(OrderSide.from_signal("BUY"), OrderSide.BUY)
        self.assertEqual(OrderSide.from_signal("SELL"), OrderSide.SELL)
        
        # Invalid signal defaults to LONG
        self.assertEqual(OrderSide.from_signal("INVALID"), OrderSide.LONG)
    
    def test_order_request_validation(self):
        """Test OrderRequest validation."""
        # Valid market order
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        self.assertEqual(order.symbol, "BTCUSDT")
        self.assertEqual(order.side, OrderSide.LONG)
        
        # Invalid quantity
        with self.assertRaises(ValueError):
            OrderRequest(
                symbol="BTCUSDT",
                side=OrderSide.LONG,
                order_type=OrderType.MARKET,
                quantity=-0.1
            )
    
    def test_execution_result_factory_methods(self):
        """Test ExecutionResult.success_result() and failure_result()."""
        # Success result
        fill = OrderFill(
            order_id="test_order",
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.1,
            fill_price=50000.0,
            commission=5.0,
            slippage=2.5
        )
        success = ExecutionResult.success_result(
            order_id="test_order",
            fill=fill
        )
        self.assertTrue(success.success)
        self.assertEqual(success.status, OrderStatus.FILLED)
        self.assertEqual(success.fill, fill)
        
        # Failure result
        failure = ExecutionResult.failure_result(
            status=OrderStatus.REJECTED,
            error="Insufficient balance"
        )
        self.assertFalse(failure.success)
        self.assertEqual(failure.status, OrderStatus.REJECTED)
        self.assertEqual(failure.error, "Insufficient balance")
    
    def test_position_pnl_calculation(self):
        """Test Position unrealized PnL calculation."""
        # Long position with profit
        position = Position(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.1,
            entry_price=50000.0,
            current_price=51000.0
        )
        self.assertAlmostEqual(position.unrealized_pnl, 100.0, places=2)  # (51000 - 50000) * 0.1
        self.assertAlmostEqual(position.unrealized_pnl_pct, 2.0, places=2)  # 2% gain
        
        # Short position with loss
        position_short = Position(
            symbol="BTCUSDT",
            side=OrderSide.SHORT,
            quantity=0.1,
            entry_price=50000.0,
            current_price=51000.0
        )
        self.assertAlmostEqual(position_short.unrealized_pnl, -100.0, places=2)  # (50000 - 51000) * 0.1
        self.assertAlmostEqual(position_short.unrealized_pnl_pct, -2.0, places=2)  # 2% loss


class TestPaperTrader(unittest.TestCase):
    """Test paper trading functionality."""
    
    def setUp(self):
        """Create a paper trader for testing."""
        self.trader = PaperTrader(
            starting_balance=10000.0,
            slippage=0.001,  # 0.1%
            commission_rate=0.001,  # 0.1%
            allow_shorting=True,
            log_trades=False  # Disable logging for tests
        )
    
    def test_initial_balance(self):
        """Test initial balance setup."""
        self.assertEqual(self.trader.get_balance(), 10000.0)
        self.assertEqual(self.trader.get_equity(), 10000.0)
        self.assertEqual(len(self.trader.get_open_positions()), 0)
    
    def test_long_order_fill(self):
        """Test filling a LONG market order."""
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        
        result = self.trader.submit_order(order, current_price=50000.0)
        
        self.assertTrue(result.success)
        self.assertEqual(result.status, OrderStatus.FILLED)
        
        # Check fill price (should include slippage)
        # LONG pays more: 50000 * (1 + 0.001) = 50050
        self.assertAlmostEqual(result.fill.fill_price, 50050.0, places=2)
        
        # Check commission: 50050 * 0.1 * 0.001 = 5.005
        self.assertAlmostEqual(result.fill.commission, 5.005, places=2)
        
        # CASH+EQUITY MODEL: Balance unchanged on OPEN
        self.assertEqual(self.trader.get_balance(), 10000.0)
        
        # Check position opened
        positions = self.trader.get_open_positions()
        self.assertEqual(len(positions), 1)
        self.assertIn("BTCUSDT", positions)
        pos = positions["BTCUSDT"]
        self.assertEqual(pos.side, OrderSide.LONG)
        self.assertAlmostEqual(pos.quantity, 0.1, places=6)
    
    def test_short_order_fill(self):
        """Test filling a SHORT market order."""
        order = OrderRequest(
            symbol="ETHUSDT",
            side=OrderSide.SHORT,
            order_type=OrderType.MARKET,
            quantity=1.0
        )
        
        result = self.trader.submit_order(order, current_price=3000.0)
        
        self.assertTrue(result.success)
        
        # SHORT receives less: 3000 * (1 - 0.001) = 2997
        self.assertAlmostEqual(result.fill.fill_price, 2997.0, places=2)
        
        # Commission: 2997 * 1.0 * 0.001 = 2.997
        self.assertAlmostEqual(result.fill.commission, 2.997, places=2)
        
        # CASH+EQUITY MODEL: Balance unchanged on OPEN
        self.assertEqual(self.trader.get_balance(), 10000.0)
        
        # Check SHORT position opened
        positions = self.trader.get_open_positions()
        self.assertEqual(len(positions), 1)
        self.assertIn("ETHUSDT", positions)
        pos = positions["ETHUSDT"]
        self.assertEqual(pos.side, OrderSide.SHORT)
    
    def test_insufficient_balance(self):
        """Test order rejection when balance is insufficient."""
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=1.0  # Requires ~50000 USD, but only have 10000
        )
        
        result = self.trader.submit_order(order, current_price=50000.0)
        
        self.assertFalse(result.success)
        self.assertEqual(result.status, OrderStatus.REJECTED)
        self.assertIn("Insufficient balance", result.error)
    
    def test_position_close_with_profit(self):
        """Test closing a position with profit."""
        # Open LONG position
        open_order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        self.trader.submit_order(open_order, current_price=50000.0)
        
        # Close position at higher price
        close_order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        result = self.trader.submit_order(close_order, current_price=51000.0)
        
        self.assertTrue(result.success)
        
        # Check position closed
        self.assertEqual(len(self.trader.get_open_positions()), 0)
        
        # Check balance increased (CASH+EQUITY MODEL: only changes on CLOSE)
        # Starting: 10000
        # Open: balance unchanged = 10000
        # Close: realized PnL = (50949 - 50050) * 0.1 = 89.9 minus fees
        # Final balance > 10000
        self.assertGreater(self.trader.get_balance(), 10000.0)
        
        # Check performance stats - only 1 trade (close counts realized PnL)
        performance = self.trader.get_performance_summary()
        self.assertEqual(performance["total_trades"], 1)
        self.assertGreater(performance["realized_pnl"], 0.0)
    
    def test_position_close_with_loss(self):
        """Test closing a position with loss."""
        # Open LONG position
        open_order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        self.trader.submit_order(open_order, current_price=50000.0)
        
        initial_balance = self.trader.get_balance()
        
        # Close at lower price
        close_order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        self.trader.submit_order(close_order, current_price=49000.0)
        
        # Check position closed
        self.assertEqual(len(self.trader.get_open_positions()), 0)
        
        # Check balance decreased
        self.assertLess(self.trader.get_balance(), 10000.0)
        
        # Check performance stats
        performance = self.trader.get_performance_summary()
        self.assertEqual(performance["losing_trades"], 1)
        self.assertLess(performance["realized_pnl"], 0.0)
    
    def test_multiple_positions(self):
        """Test managing multiple positions across symbols."""
        # Open LONG on BTC
        order1 = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.05
        )
        self.trader.submit_order(order1, current_price=50000.0)
        
        # Open SHORT on ETH
        order2 = OrderRequest(
            symbol="ETHUSDT",
            side=OrderSide.SHORT,
            order_type=OrderType.MARKET,
            quantity=0.5
        )
        self.trader.submit_order(order2, current_price=3000.0)
        
        # Check both positions exist
        positions = self.trader.get_open_positions()
        self.assertEqual(len(positions), 2)
        
        symbols = list(positions.keys())
        self.assertIn("BTCUSDT", symbols)
        self.assertIn("ETHUSDT", symbols)
    
    def test_equity_calculation_with_positions(self):
        """Test equity calculation includes unrealized PnL."""
        # Open LONG position
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        self.trader.submit_order(order, current_price=50000.0)
        
        # Update position prices (price increased)
        self.trader.update_positions({"BTCUSDT": 51000.0})
        
        # Equity should be balance + unrealized PnL
        balance = self.trader.get_balance()
        equity = self.trader.get_equity()
        
        # Unrealized PnL ≈ (51000 - 50050) * 0.1 = 95
        # Equity ≈ balance + 95
        self.assertGreater(equity, balance)
        self.assertAlmostEqual(equity - balance, 95.0, delta=5.0)


class TestExecutionEngine(unittest.TestCase):
    """Test execution engine order routing."""
    
    def setUp(self):
        """Create execution engine for testing."""
        self.paper_trader = PaperTrader(
            starting_balance=10000.0,
            slippage=0.001,
            commission_rate=0.001,
            log_trades=False
        )
        self.engine = ExecutionEngine(
            execution_mode="paper",
            paper_trader=self.paper_trader
        )
    
    def test_order_submission_paper_mode(self):
        """Test order submission routes to paper trader."""
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        
        result = self.engine.submit_order(order, current_price=50000.0)
        
        self.assertTrue(result.success)
        self.assertEqual(result.status, OrderStatus.FILLED)
        
        # Check statistics updated
        stats = self.engine.get_statistics()
        self.assertEqual(stats["total_orders"], 1)
        self.assertEqual(stats["successful_orders"], 1)
    
    def test_order_validation(self):
        """Test order validation before submission."""
        # Create an order that bypasses __post_init__ validation
        # by creating it with valid quantity first, then testing validation
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1  # Valid quantity
        )
        
        # Now test validation logic in ExecutionEngine
        # We'll submit with validate=True but modify quantity to 0 through dict
        order.quantity = -0.1  # Negative quantity
        
        result = self.engine.submit_order(order, current_price=50000.0, validate=True)
        
        self.assertFalse(result.success)
        self.assertEqual(result.status, OrderStatus.REJECTED)
        
        # Check statistics
        stats = self.engine.get_statistics()
        self.assertEqual(stats["rejected_orders"], 1)
    
    def test_create_order_from_signal(self):
        """Test order creation from strategy signal."""
        order = self.engine.create_order_from_signal(
            signal="LONG",
            symbol="BTCUSDT",
            quantity=0.1,
            stop_loss=49000.0,
            take_profit=52000.0
        )
        
        self.assertEqual(order.symbol, "BTCUSDT")
        self.assertEqual(order.side, OrderSide.LONG)
        self.assertEqual(order.quantity, 0.1)
        self.assertEqual(order.stop_loss, 49000.0)
        self.assertEqual(order.take_profit, 52000.0)
    
    def test_create_order_from_risk_output(self):
        """Test order creation from RiskEngine output."""
        risk_output = {
            "side": "LONG",
            "entry_price": 50000.0,
            "position_size": 0.1,
            "stop_loss": 49000.0,
            "take_profit": 52000.0,
            "risk_usd": 100.0
        }
        
        # create_order_from_risk_output requires symbol in risk_output or as param
        risk_output["symbol"] = "BTCUSDT"  # Add symbol to risk output
        order = self.engine.create_order_from_risk_output(
            risk_output=risk_output
        )
        
        self.assertEqual(order.symbol, "BTCUSDT")
        self.assertEqual(order.side, OrderSide.LONG)
        self.assertAlmostEqual(order.quantity, 0.1, places=6)
        self.assertEqual(order.stop_loss, 49000.0)
        self.assertEqual(order.take_profit, 52000.0)
    
    def test_get_balance(self):
        """Test balance retrieval from paper trader."""
        balance = self.engine.get_balance()
        self.assertEqual(balance, 10000.0)
    
    def test_get_performance_summary(self):
        """Test performance summary retrieval."""
        # Submit a LONG order
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        self.engine.submit_order(order, current_price=50000.0)
        
        # Close the position to generate a trade
        close_order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        self.engine.submit_order(close_order, current_price=51000.0)
        
        performance = self.engine.get_performance_summary()
        
        self.assertIn("starting_balance", performance)
        self.assertIn("current_balance", performance)
        self.assertIn("total_trades", performance)
        self.assertEqual(performance["total_trades"], 1)  # Only close counts as completed trade
    
    def test_live_mode_not_implemented(self):
        """Test that live mode requires exchange_client."""
        with self.assertRaises(ValueError):
            ExecutionEngine(execution_mode="live")


class TestExchangeClientBase(unittest.TestCase):
    """Test exchange client abstract base class."""
    
    def test_cannot_instantiate_abstract_class(self):
        """Test that ExchangeClientBase cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            ExchangeClientBase()
    
    def test_subclass_must_implement_methods(self):
        """Test that subclasses must implement all abstract methods."""
        class IncompleteClient(ExchangeClientBase):
            pass
        
        with self.assertRaises(TypeError):
            IncompleteClient()
    
    def test_unknown_symbol_rejected(self):
        """Test that orders with UNKNOWN symbol are rejected."""
        engine = ExecutionEngine(
            execution_mode="paper",
            paper_trader=PaperTrader(starting_balance=10000.0, log_trades=False)
        )
        
        # Test with UNKNOWN symbol
        order = OrderRequest(
            symbol="UNKNOWN",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        
        with self.assertRaises(ValueError) as context:
            engine.submit_order(order, current_price=50000.0)
        
        self.assertIn("Invalid symbol", str(context.exception))
        self.assertIn("UNKNOWN", str(context.exception))
        
        # Test with empty symbol
        order_empty = OrderRequest(
            symbol="",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        
        with self.assertRaises(ValueError) as context:
            engine.submit_order(order_empty, current_price=50000.0)
        
        self.assertIn("Invalid symbol", str(context.exception))


if __name__ == "__main__":
    unittest.main()
