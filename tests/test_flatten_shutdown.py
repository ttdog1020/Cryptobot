"""
Test flatten-on-shutdown functionality for PaperTrader.

This test verifies that close_all_positions() properly:
1. Closes all open positions
2. Calculates realized PnL correctly
3. Updates balance using apply_trade_result()
4. Logs CLOSE trades to CSV
"""

import unittest
from pathlib import Path
from datetime import datetime
import pandas as pd
import tempfile

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from execution import PaperTrader, OrderRequest, OrderSide, OrderType


class TestFlattenOnShutdown(unittest.TestCase):
    """Test PaperTrader.close_all_positions() functionality."""
    
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
    
    def test_close_all_positions_empty(self):
        """Test closing when no positions are open."""
        # Should not raise an error
        self.trader.close_all_positions(lambda symbol: 50000.0)
        
        # Balance should be unchanged
        self.assertEqual(self.trader.get_balance(), 10000.0)
    
    def test_close_all_positions_single_long(self):
        """Test closing a single LONG position."""
        # Open a LONG position
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        self.trader.submit_order(order, current_price=50000.0)
        
        # Verify position opened
        positions = self.trader.get_open_positions()
        self.assertEqual(len(positions), 1)
        self.assertIn("BTCUSDT", positions)
        
        # Close all positions at a higher price (profit)
        def price_provider(symbol):
            return 51000.0
        
        initial_balance = self.trader.get_balance()
        self.trader.close_all_positions(price_provider)
        
        # Verify all positions closed
        positions = self.trader.get_open_positions()
        self.assertEqual(len(positions), 0)
        
        # Verify balance increased (we made a profit)
        final_balance = self.trader.get_balance()
        self.assertGreater(final_balance, initial_balance)
        
        # Verify CSV contains both OPEN and CLOSE trades
        df = pd.read_csv(self.temp_log.name)
        trade_df = df[df['action'] != 'INIT']
        self.assertEqual(len(trade_df), 2)  # OPEN and CLOSE
        self.assertEqual(trade_df.iloc[0]['action'], 'OPEN')
        self.assertEqual(trade_df.iloc[1]['action'], 'CLOSE')
        self.assertEqual(trade_df.iloc[0]['symbol'], 'BTCUSDT')
        self.assertEqual(trade_df.iloc[1]['symbol'], 'BTCUSDT')
        
        # Verify realized PnL is recorded
        realized_pnl = trade_df.iloc[1]['realized_pnl']
        self.assertGreater(realized_pnl, 0)  # Should be profitable
    
    def test_close_all_positions_single_short(self):
        """Test closing a single SHORT position."""
        initial_balance = self.trader.get_balance()
        
        # Open a SHORT position
        order = OrderRequest(
            symbol="ETHUSDT",
            side=OrderSide.SHORT,
            order_type=OrderType.MARKET,
            quantity=1.0
        )
        self.trader.submit_order(order, current_price=3000.0)
        
        # Close at lower price (profit for SHORT)
        def price_provider(symbol):
            return 2900.0
        
        self.trader.close_all_positions(price_provider)
        
        # Verify all positions closed
        self.assertEqual(len(self.trader.get_open_positions()), 0)
        
        # Verify balance increased (profit on SHORT)
        self.assertGreater(self.trader.get_balance(), initial_balance)
    
    def test_close_all_positions_multiple(self):
        """Test closing multiple positions at once."""
        # Open 3 positions
        orders = [
            OrderRequest(symbol="BTCUSDT", side=OrderSide.LONG, order_type=OrderType.MARKET, quantity=0.1),
            OrderRequest(symbol="ETHUSDT", side=OrderSide.SHORT, order_type=OrderType.MARKET, quantity=1.0),
            OrderRequest(symbol="BNBUSDT", side=OrderSide.LONG, order_type=OrderType.MARKET, quantity=5.0),
        ]
        
        prices = {"BTCUSDT": 50000.0, "ETHUSDT": 3000.0, "BNBUSDT": 600.0}
        
        for order in orders:
            self.trader.submit_order(order, current_price=prices[order.symbol])
        
        # Verify 3 positions opened
        self.assertEqual(len(self.trader.get_open_positions()), 3)
        
        # Close all with updated prices
        def price_provider(symbol):
            # All positions lose money
            if symbol == "BTCUSDT":
                return 49000.0  # LONG loss
            elif symbol == "ETHUSDT":
                return 3100.0   # SHORT loss
            else:
                return 590.0    # LONG loss
        
        self.trader.close_all_positions(price_provider)
        
        # Verify all positions closed
        self.assertEqual(len(self.trader.get_open_positions()), 0)
        
        # Verify CSV contains INIT + 3 OPEN + 3 CLOSE = 7 rows
        df = pd.read_csv(self.temp_log.name)
        self.assertEqual(len(df), 7)
        
        # Verify we have 3 OPEN and 3 CLOSE trades
        opens = df[df['action'] == 'OPEN']
        closes = df[df['action'] == 'CLOSE']
        self.assertEqual(len(opens), 3)
        self.assertEqual(len(closes), 3)
        
        # Verify each symbol has matching OPEN and CLOSE
        for symbol in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]:
            symbol_opens = opens[opens['symbol'] == symbol]
            symbol_closes = closes[closes['symbol'] == symbol]
            self.assertEqual(len(symbol_opens), 1)
            self.assertEqual(len(symbol_closes), 1)
    
    def test_close_all_positions_with_loss(self):
        """Test that losses are properly recorded."""
        initial_balance = self.trader.get_balance()
        
        # Open LONG
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        self.trader.submit_order(order, current_price=50000.0)
        
        # Close at lower price (loss)
        def price_provider(symbol):
            return 49000.0
        
        self.trader.close_all_positions(price_provider)
        
        # Verify balance decreased (loss)
        final_balance = self.trader.get_balance()
        self.assertLess(final_balance, initial_balance)
        
        # Verify negative realized PnL in CSV
        df = pd.read_csv(self.temp_log.name)
        close_row = df[df['action'] == 'CLOSE'].iloc[0]
        self.assertLess(close_row['realized_pnl'], 0)
    
    def test_price_provider_error_handling(self):
        """Test that price provider errors are handled gracefully."""
        # Open position
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        result = self.trader.submit_order(order, current_price=50000.0)
        
        # Price provider that raises an error
        def failing_price_provider(symbol):
            raise ValueError("Market data unavailable")
        
        # Should use last known price instead of crashing
        self.trader.close_all_positions(failing_price_provider)
        
        # Position should still be closed
        self.assertEqual(len(self.trader.get_open_positions()), 0)


class TestApplyTradeResult(unittest.TestCase):
    """Test the apply_trade_result helper function."""
    
    def test_profitable_trade(self):
        """Test applying a profitable trade."""
        balance = 10000.0
        realized_pnl = 100.0
        commission = 5.0
        slippage = 2.0
        
        new_balance = PaperTrader.apply_trade_result(
            balance, realized_pnl, commission, slippage
        )
        
        # New balance = 10000 + 100 - 5 - 2 = 10093
        self.assertAlmostEqual(new_balance, 10093.0, places=2)
    
    def test_losing_trade(self):
        """Test applying a losing trade."""
        balance = 10000.0
        realized_pnl = -100.0
        commission = 5.0
        slippage = 2.0
        
        new_balance = PaperTrader.apply_trade_result(
            balance, realized_pnl, commission, slippage
        )
        
        # New balance = 10000 - 100 - 5 - 2 = 9893
        self.assertAlmostEqual(new_balance, 9893.0, places=2)


if __name__ == "__main__":
    unittest.main()
