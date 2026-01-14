"""
Test Cash+Equity Accounting Model

Verifies that the refactored paper trading accounting correctly implements:
- Balance (cash) changes ONLY on CLOSED trades
- Equity = balance + unrealized PnL
- OPEN trades don't modify balance
- CLOSE trades use apply_trade_result() to update balance
"""

import unittest
from pathlib import Path
import tempfile

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from execution import PaperTrader, OrderRequest, OrderSide, OrderType


class TestCashEquityModel(unittest.TestCase):
    """Test the cash+equity accounting model."""
    
    def setUp(self):
        """Create a paper trader for testing."""
        # Use temp file for logging
        self.temp_log = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        self.temp_log.close()
        
        self.trader = PaperTrader(
            starting_balance=10000.0,
            slippage=0.001,
            commission_rate=0.001,
            log_trades=True,
            log_file=self.temp_log.name
        )
    
    def tearDown(self):
        """Clean up temp file."""
        Path(self.temp_log.name).unlink(missing_ok=True)
    
    def test_open_long_no_balance_change(self):
        """Test that opening a LONG position does NOT change balance."""
        initial_balance = self.trader.get_balance()
        
        # Open LONG position
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        result = self.trader.submit_order(order, current_price=50000.0)
        
        self.assertTrue(result.success)
        
        # CRITICAL: Balance should NOT change on OPEN
        self.assertEqual(self.trader.get_balance(), initial_balance)
        self.assertEqual(self.trader.get_balance(), 10000.0)
        
        # Position should be open
        positions = self.trader.get_open_positions()
        self.assertEqual(len(positions), 1)
        
        # Equity equals balance when price hasn't moved
        self.assertEqual(self.trader.get_equity(), initial_balance)
    
    def test_open_short_no_balance_change(self):
        """Test that opening a SHORT position does NOT change balance."""
        initial_balance = self.trader.get_balance()
        
        # Open SHORT position
        order = OrderRequest(
            symbol="ETHUSDT",
            side=OrderSide.SHORT,
            order_type=OrderType.MARKET,
            quantity=1.0
        )
        result = self.trader.submit_order(order, current_price=3000.0)
        
        self.assertTrue(result.success)
        
        # CRITICAL: Balance should NOT change on OPEN
        self.assertEqual(self.trader.get_balance(), initial_balance)
        self.assertEqual(self.trader.get_balance(), 10000.0)
        
        # Position should be open
        positions = self.trader.get_open_positions()
        self.assertEqual(len(positions), 1)
    
    def test_equity_reflects_unrealized_pnl(self):
        """Test that equity = balance + unrealized PnL."""
        # Open LONG at 50000
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        self.trader.submit_order(order, current_price=50000.0)
        
        # Balance unchanged
        self.assertEqual(self.trader.get_balance(), 10000.0)
        
        # Price moves up to 51000
        self.trader.update_positions({"BTCUSDT": 51000.0})
        
        # Unrealized PnL = (51000 - 50050) * 0.1 = 95
        positions = self.trader.get_open_positions()
        unrealized = positions["BTCUSDT"].unrealized_pnl
        self.assertAlmostEqual(unrealized, 95.0, places=2)
        
        # Equity = balance + unrealized
        equity = self.trader.get_equity()
        self.assertAlmostEqual(equity, 10095.0, places=2)
        
        # Balance still unchanged
        self.assertEqual(self.trader.get_balance(), 10000.0)
    
    def test_close_long_profit_updates_balance(self):
        """Test that closing a LONG with profit updates balance correctly."""
        initial_balance = 10000.0
        
        # Open LONG at 50000
        open_order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        self.trader.submit_order(open_order, current_price=50000.0)
        
        # Balance unchanged after OPEN
        self.assertEqual(self.trader.get_balance(), initial_balance)
        
        # Close at 51000 (profit)
        close_order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        self.trader.submit_order(close_order, current_price=51000.0)
        
        # Position closed
        self.assertEqual(len(self.trader.get_open_positions()), 0)
        
        # Balance should NOW change (only on CLOSE)
        # Realized PnL = (50949 - 50050) * 0.1 = 89.9
        # Balance = 10000 + 89.9 - commission - slippage
        final_balance = self.trader.get_balance()
        self.assertGreater(final_balance, initial_balance)
        self.assertAlmostEqual(final_balance, 10079.4, delta=1.0)
        
        # Equity = balance (no open positions)
        self.assertEqual(self.trader.get_equity(), final_balance)
    
    def test_close_long_loss_updates_balance(self):
        """Test that closing a LONG with loss updates balance correctly."""
        initial_balance = 10000.0
        
        # Open LONG at 50000
        open_order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        self.trader.submit_order(open_order, current_price=50000.0)
        
        # Balance unchanged after OPEN
        self.assertEqual(self.trader.get_balance(), initial_balance)
        
        # Close at 49000 (loss)
        close_order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        self.trader.submit_order(close_order, current_price=49000.0)
        
        # Position closed
        self.assertEqual(len(self.trader.get_open_positions()), 0)
        
        # Balance should decrease (loss)
        final_balance = self.trader.get_balance()
        self.assertLess(final_balance, initial_balance)
        
        # Equity = balance (no open positions)
        self.assertEqual(self.trader.get_equity(), final_balance)
    
    def test_close_short_profit_updates_balance(self):
        """Test that closing a SHORT with profit updates balance correctly."""
        initial_balance = 10000.0
        
        # Open SHORT at 3000
        open_order = OrderRequest(
            symbol="ETHUSDT",
            side=OrderSide.SHORT,
            order_type=OrderType.MARKET,
            quantity=1.0
        )
        self.trader.submit_order(open_order, current_price=3000.0)
        
        # Balance unchanged after OPEN
        self.assertEqual(self.trader.get_balance(), initial_balance)
        
        # Close at 2900 (profit for SHORT)
        close_order = OrderRequest(
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0
        )
        self.trader.submit_order(close_order, current_price=2900.0)
        
        # Position closed
        self.assertEqual(len(self.trader.get_open_positions()), 0)
        
        # Balance should increase (profit)
        final_balance = self.trader.get_balance()
        self.assertGreater(final_balance, initial_balance)
        
        # Equity = balance (no open positions)
        self.assertEqual(self.trader.get_equity(), final_balance)
    
    def test_multiple_positions_balance_unchanged_until_close(self):
        """Test that opening multiple positions doesn't change balance until closing."""
        initial_balance = 10000.0
        
        # Open 3 positions
        orders = [
            OrderRequest(symbol="BTCUSDT", side=OrderSide.LONG, order_type=OrderType.MARKET, quantity=0.05),
            OrderRequest(symbol="ETHUSDT", side=OrderSide.SHORT, order_type=OrderType.MARKET, quantity=0.5),
            OrderRequest(symbol="BNBUSDT", side=OrderSide.LONG, order_type=OrderType.MARKET, quantity=2.0),
        ]
        
        prices = {"BTCUSDT": 50000.0, "ETHUSDT": 3000.0, "BNBUSDT": 600.0}
        
        for order in orders:
            self.trader.submit_order(order, current_price=prices[order.symbol])
        
        # Balance should STILL be initial (no CLOSE yet)
        self.assertEqual(self.trader.get_balance(), initial_balance)
        self.assertEqual(len(self.trader.get_open_positions()), 3)
        
        # Now close one position
        close_order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=0.05
        )
        self.trader.submit_order(close_order, current_price=51000.0)
        
        # NOW balance should change (only for this one CLOSE)
        self.assertNotEqual(self.trader.get_balance(), initial_balance)
        self.assertEqual(len(self.trader.get_open_positions()), 2)
    
    def test_equity_vs_balance_with_open_positions(self):
        """Test that equity differs from balance when positions are open."""
        # Open LONG at 50000
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        self.trader.submit_order(order, current_price=50000.0)
        
        # Balance unchanged
        balance = self.trader.get_balance()
        self.assertEqual(balance, 10000.0)
        
        # Price moves to 52000 (big profit)
        self.trader.update_positions({"BTCUSDT": 52000.0})
        
        equity = self.trader.get_equity()
        
        # Equity should be > balance (unrealized profit)
        self.assertGreater(equity, balance)
        
        # Unrealized PnL = (52000 - 50050) * 0.1 = 195
        self.assertAlmostEqual(equity, 10195.0, places=1)
        
        # Price moves down to 48000 (loss)
        self.trader.update_positions({"BTCUSDT": 48000.0})
        
        equity = self.trader.get_equity()
        
        # Equity should be < balance (unrealized loss)
        self.assertLess(equity, balance)
        
        # Unrealized PnL = (48000 - 50050) * 0.1 = -205
        self.assertAlmostEqual(equity, 9795.0, places=1)


if __name__ == "__main__":
    unittest.main()
