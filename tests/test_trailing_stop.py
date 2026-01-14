"""
Tests for trailing stop loss feature.

Tests the percentage-based trailing stop functionality in both
PaperTrader and backtest environments.
"""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

from execution.paper_trader import PaperTrader
from execution.order_types import OrderRequest, OrderSide, OrderType, Position


class TestTrailingStopBasic(unittest.TestCase):
    """Basic trailing stop functionality tests."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.paper_trader = PaperTrader(
            starting_balance=10000.0,
            slippage=0.001,
            commission_rate=0.001,
            allow_shorting=True,
            log_trades=False
        )
        
        # Enable trailing stop with 2% trail
        self.paper_trader.set_risk_config({
            "enable_trailing_stop": True,
            "trailing_stop_pct": 0.02
        })
    
    def test_trailing_stop_disabled_no_effect(self):
        """
        Test that trailing stop has no effect when disabled.
        """
        # Disable trailing stop
        self.paper_trader.set_risk_config({
            "enable_trailing_stop": False,
            "trailing_stop_pct": 0.02
        })
        
        # Open long position at 100 with 5% SL
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.1,
            order_type=OrderType.MARKET,
            stop_loss=95.0,  # 5% below entry
            strategy_name="test"
        )
        
        result = self.paper_trader.submit_order(order, current_price=100.0)
        self.assertTrue(result.success)
        
        # Price moves to 110
        self.paper_trader.update_positions({"BTCUSDT": 110.0})
        
        # Check that stop loss hasn't moved (trailing disabled)
        position = self.paper_trader.positions["BTCUSDT"]
        self.assertEqual(position.stop_loss, 95.0)
        # highest_price is initialized to entry_price (which includes slippage)
        self.assertAlmostEqual(position.highest_price, position.entry_price, places=1)
    
    def test_trailing_stop_tightens_on_favorable_move(self):
        """
        Test that trailing stop tightens as price moves favorably.
        """
        # Open long position at 100 with 5% SL (95.0)
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.1,
            order_type=OrderType.MARKET,
            stop_loss=95.0,
            strategy_name="test"
        )
        
        result = self.paper_trader.submit_order(order, current_price=100.0)
        self.assertTrue(result.success)
        
        position = self.paper_trader.positions["BTCUSDT"]
        # highest_price is initialized to entry_price (with slippage ~100.1)
        self.assertAlmostEqual(position.highest_price, position.entry_price, places=1)
        self.assertEqual(position.stop_loss, 95.0)
        
        # Price moves to 105
        self.paper_trader.update_positions({"BTCUSDT": 105.0})
        self.assertEqual(position.highest_price, 105.0)
        # Trailing stop: 105 * (1 - 0.02) = 102.9
        # Should tighten: max(95.0, 102.9) = 102.9
        self.assertAlmostEqual(position.stop_loss, 102.9, places=2)
        
        # Price moves to 110
        self.paper_trader.update_positions({"BTCUSDT": 110.0})
        self.assertEqual(position.highest_price, 110.0)
        # Trailing stop: 110 * (1 - 0.02) = 107.8
        # Should tighten: max(102.9, 107.8) = 107.8
        self.assertAlmostEqual(position.stop_loss, 107.8, places=2)
    
    def test_trailing_stop_does_not_loosen(self):
        """
        Test that trailing stop never loosens (only tightens).
        """
        # Open long position at 100 with 5% SL (95.0)
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.1,
            order_type=OrderType.MARKET,
            stop_loss=95.0,
            strategy_name="test"
        )
        
        result = self.paper_trader.submit_order(order, current_price=100.0)
        self.assertTrue(result.success)
        
        # Price moves to 110
        self.paper_trader.update_positions({"BTCUSDT": 110.0})
        position = self.paper_trader.positions["BTCUSDT"]
        
        # Stop tightened to 107.8
        self.assertAlmostEqual(position.stop_loss, 107.8, places=2)
        initial_stop = position.stop_loss
        
        # Price falls back to 103
        self.paper_trader.update_positions({"BTCUSDT": 103.0})
        
        # Highest price should stay at 110
        self.assertEqual(position.highest_price, 110.0)
        
        # Stop should NOT loosen (stays at 107.8)
        self.assertEqual(position.stop_loss, initial_stop)
    
    def test_trailing_stop_triggers_exit(self):
        """
        Test that position is closed when price hits trailing stop.
        """
        # Open long position at 100 with 5% SL (95.0)
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.1,
            order_type=OrderType.MARKET,
            stop_loss=95.0,
            strategy_name="test"
        )
        
        result = self.paper_trader.submit_order(order, current_price=100.0)
        self.assertTrue(result.success)
        
        # Price moves to 110 (tightens stop to 107.8)
        self.paper_trader.update_positions({"BTCUSDT": 110.0})
        position = self.paper_trader.positions["BTCUSDT"]
        self.assertAlmostEqual(position.stop_loss, 107.8, places=2)
        
        # Price falls to 107.5 (below stop of 107.8)
        self.paper_trader.update_positions({"BTCUSDT": 107.5})
        
        # Check that exit condition is triggered
        symbols_to_close = self.paper_trader.check_exit_conditions({"BTCUSDT": 107.5})
        self.assertIn("BTCUSDT", symbols_to_close)
        
        # Close the position
        close_order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            quantity=0.1,
            order_type=OrderType.MARKET,
            strategy_name="exit"
        )
        
        close_result = self.paper_trader.submit_order(close_order, current_price=107.5)
        self.assertTrue(close_result.success)
        
        # Position should be closed
        self.assertNotIn("BTCUSDT", self.paper_trader.positions)
        
        # Should have profit (entered at ~100, exited at ~107.5)
        self.assertGreater(self.paper_trader.balance, 10000.0)
    
    def test_trailing_stop_initializes_when_no_initial_stop(self):
        """
        Test that trailing stop is set even if no initial SL was provided.
        """
        # Open position without stop loss
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.1,
            order_type=OrderType.MARKET,
            stop_loss=None,  # No initial stop
            strategy_name="test"
        )
        
        result = self.paper_trader.submit_order(order, current_price=100.0)
        self.assertTrue(result.success)
        
        position = self.paper_trader.positions["BTCUSDT"]
        self.assertIsNone(position.stop_loss)
        
        # Price moves to 110
        self.paper_trader.update_positions({"BTCUSDT": 110.0})
        
        # Trailing stop should be initialized: 110 * 0.98 = 107.8
        self.assertIsNotNone(position.stop_loss)
        self.assertAlmostEqual(position.stop_loss, 107.8, places=2)
    
    def test_trailing_stop_works_with_take_profit(self):
        """
        Test that trailing stop works alongside take profit.
        """
        # Open long position with both SL and TP
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.1,
            order_type=OrderType.MARKET,
            stop_loss=95.0,
            take_profit=120.0,  # 20% profit target
            strategy_name="test"
        )
        
        result = self.paper_trader.submit_order(order, current_price=100.0)
        self.assertTrue(result.success)
        
        # Price moves to 110 (tightens stop)
        self.paper_trader.update_positions({"BTCUSDT": 110.0})
        position = self.paper_trader.positions["BTCUSDT"]
        self.assertAlmostEqual(position.stop_loss, 107.8, places=2)
        
        # TP should still be at 120
        self.assertEqual(position.take_profit, 120.0)
        
        # Price reaches TP
        symbols_to_close = self.paper_trader.check_exit_conditions({"BTCUSDT": 120.0})
        self.assertIn("BTCUSDT", symbols_to_close)
    
    def test_trailing_stop_only_for_long_positions(self):
        """
        Test that trailing stop only applies to LONG positions (not SHORT).
        """
        # Open short position
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.SHORT,
            quantity=0.1,
            order_type=OrderType.MARKET,
            stop_loss=105.0,  # 5% above entry for short
            strategy_name="test"
        )
        
        result = self.paper_trader.submit_order(order, current_price=100.0)
        self.assertTrue(result.success)
        
        position = self.paper_trader.positions["BTCUSDT"]
        initial_stop = position.stop_loss
        initial_highest = position.highest_price  # Entry price with slippage
        
        # Price moves down (favorable for short)
        self.paper_trader.update_positions({"BTCUSDT": 90.0})
        
        # Stop should NOT change (trailing only for LONG)
        self.assertEqual(position.stop_loss, initial_stop)
        self.assertEqual(position.highest_price, initial_highest)  # Not updated for shorts


class TestTrailingStopConfiguration(unittest.TestCase):
    """Test trailing stop configuration and validation."""
    
    def test_set_risk_config_enables_trailing_stop(self):
        """Test that set_risk_config properly enables trailing stop."""
        paper_trader = PaperTrader(starting_balance=10000.0, log_trades=False)
        
        # Initially disabled
        self.assertFalse(paper_trader.enable_trailing_stop)
        
        # Enable with config
        paper_trader.set_risk_config({
            "enable_trailing_stop": True,
            "trailing_stop_pct": 0.03  # 3%
        })
        
        self.assertTrue(paper_trader.enable_trailing_stop)
        self.assertEqual(paper_trader.trailing_stop_pct, 0.03)
    
    def test_set_risk_config_disables_trailing_stop(self):
        """Test that set_risk_config can disable trailing stop."""
        paper_trader = PaperTrader(starting_balance=10000.0, log_trades=False)
        
        # Enable first
        paper_trader.set_risk_config({
            "enable_trailing_stop": True,
            "trailing_stop_pct": 0.02
        })
        self.assertTrue(paper_trader.enable_trailing_stop)
        
        # Disable
        paper_trader.set_risk_config({
            "enable_trailing_stop": False,
            "trailing_stop_pct": 0.02
        })
        
        self.assertFalse(paper_trader.enable_trailing_stop)
    
    def test_trailing_stop_with_different_percentages(self):
        """Test trailing stop with various trail percentages."""
        paper_trader = PaperTrader(starting_balance=10000.0, log_trades=False)
        
        # Test with 1% trail
        paper_trader.set_risk_config({
            "enable_trailing_stop": True,
            "trailing_stop_pct": 0.01
        })
        
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            quantity=0.1,
            order_type=OrderType.MARKET,
            stop_loss=95.0,
            strategy_name="test"
        )
        
        paper_trader.submit_order(order, current_price=100.0)
        paper_trader.update_positions({"BTCUSDT": 110.0})
        
        position = paper_trader.positions["BTCUSDT"]
        # 110 * (1 - 0.01) = 108.9
        self.assertAlmostEqual(position.stop_loss, 108.9, places=2)


if __name__ == "__main__":
    unittest.main()
