"""
MODULE 24: Tests for Safety Limits and SafetyMonitor

Tests global safety limits and kill switch functionality.
"""

import unittest
import os
from datetime import datetime

from execution.safety import SafetyLimits, SafetyMonitor, SafetyViolation
from execution.order_types import OrderRequest, OrderSide, OrderType


class TestSafetyLimits(unittest.TestCase):
    """Test SafetyLimits dataclass."""
    
    def test_valid_limits(self):
        """Test creating valid safety limits."""
        limits = SafetyLimits(
            max_daily_loss_pct=0.02,
            max_risk_per_trade_pct=0.01,
            max_exposure_pct=0.20,
            max_open_trades=5
        )
        
        self.assertEqual(limits.max_daily_loss_pct, 0.02)
        self.assertEqual(limits.max_risk_per_trade_pct, 0.01)
        self.assertEqual(limits.max_exposure_pct, 0.20)
        self.assertEqual(limits.max_open_trades, 5)
        self.assertEqual(limits.kill_switch_env_var, "CRYPTOBOT_KILL_SWITCH")
    
    def test_custom_kill_switch_var(self):
        """Test custom kill switch variable name."""
        limits = SafetyLimits(
            max_daily_loss_pct=0.02,
            max_risk_per_trade_pct=0.01,
            max_exposure_pct=0.20,
            max_open_trades=5,
            kill_switch_env_var="MY_KILL_SWITCH"
        )
        
        self.assertEqual(limits.kill_switch_env_var, "MY_KILL_SWITCH")
    
    def test_negative_daily_loss_limit(self):
        """Test negative daily loss limit raises error."""
        with self.assertRaises(ValueError):
            SafetyLimits(
                max_daily_loss_pct=-0.02,  # Invalid
                max_risk_per_trade_pct=0.01,
                max_exposure_pct=0.20,
                max_open_trades=5
            )
    
    def test_zero_max_open_trades(self):
        """Test zero max open trades raises error."""
        with self.assertRaises(ValueError):
            SafetyLimits(
                max_daily_loss_pct=0.02,
                max_risk_per_trade_pct=0.01,
                max_exposure_pct=0.20,
                max_open_trades=0  # Invalid
            )


class TestSafetyMonitor(unittest.TestCase):
    """Test SafetyMonitor functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.limits = SafetyLimits(
            max_daily_loss_pct=0.02,  # 2%
            max_risk_per_trade_pct=0.01,  # 1%
            max_exposure_pct=0.20,  # 20%
            max_open_trades=3,
            kill_switch_env_var="TEST_KILL_SWITCH"
        )
        
        self.starting_equity = 1000.0
        self.monitor = SafetyMonitor(
            limits=self.limits,
            starting_equity=self.starting_equity
        )
        
        # Clean up environment
        if "TEST_KILL_SWITCH" in os.environ:
            del os.environ["TEST_KILL_SWITCH"]
    
    def tearDown(self):
        """Clean up environment variables."""
        if "TEST_KILL_SWITCH" in os.environ:
            del os.environ["TEST_KILL_SWITCH"]
    
    def create_test_order(self, symbol="BTCUSDT", side=OrderSide.LONG, quantity=0.1):
        """Helper to create test order."""
        return OrderRequest(
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            stop_loss=None,
            take_profit=None
        )
    
    def test_initial_state(self):
        """Test initial safety monitor state."""
        self.assertEqual(self.monitor.starting_equity, 1000.0)
        self.assertEqual(self.monitor.current_equity, 1000.0)
        self.assertEqual(self.monitor.daily_pnl, 0.0)
        self.assertFalse(self.monitor.trading_halted)
        self.assertFalse(self.monitor.kill_switch_engaged())
    
    def test_pre_trade_check_passes(self):
        """Test pre-trade check with valid order."""
        order = self.create_test_order()
        
        # Risk: $5 (0.5% of $1000 equity)
        # Position value: $100 (10% of equity)
        # Both within limits
        
        # Should not raise
        self.monitor.check_pre_trade(
            order=order,
            risk_amount=5.0,
            position_value=100.0
        )
    
    def test_pre_trade_risk_too_high(self):
        """Test pre-trade check rejects excessive risk."""
        order = self.create_test_order()
        
        # Risk: $15 (1.5% of $1000 equity)
        # Exceeds max_risk_per_trade_pct of 1%
        
        with self.assertRaises(SafetyViolation) as ctx:
            self.monitor.check_pre_trade(
                order=order,
                risk_amount=15.0,
                position_value=100.0
            )
        
        self.assertIn("exceeds max risk per trade", str(ctx.exception))
    
    def test_pre_trade_exposure_too_high(self):
        """Test pre-trade check rejects excessive exposure."""
        order = self.create_test_order()
        
        # Risk: $5 (within limit)
        # Position value: $250 (25% of $1000 equity)
        # Exceeds max_exposure_pct of 20%
        
        with self.assertRaises(SafetyViolation) as ctx:
            self.monitor.check_pre_trade(
                order=order,
                risk_amount=5.0,
                position_value=250.0
            )
        
        self.assertIn("would exceed max exposure", str(ctx.exception))
    
    def test_pre_trade_too_many_positions(self):
        """Test pre-trade check rejects when max positions reached."""
        # Open 3 positions (max_open_trades = 3)
        self.monitor.record_position_open("BTCUSDT", 0.1, 50000.0, OrderSide.LONG)
        self.monitor.record_position_open("ETHUSDT", 1.0, 3000.0, OrderSide.LONG)
        self.monitor.record_position_open("SOLUSDT", 10.0, 100.0, OrderSide.LONG)
        
        # Try to open 4th position
        order = self.create_test_order(symbol="BNBUSDT")
        
        with self.assertRaises(SafetyViolation) as ctx:
            self.monitor.check_pre_trade(
                order=order,
                risk_amount=5.0,
                position_value=100.0
            )
        
        self.assertIn("Maximum open trades", str(ctx.exception))
    
    def test_post_trade_within_limits(self):
        """Test post-trade check with equity within limits."""
        # Lose $10 (1% of $1000)
        # Within max_daily_loss_pct of 2%
        
        new_equity = 990.0
        self.monitor.check_post_trade(new_equity)
        
        self.assertEqual(self.monitor.current_equity, 990.0)
        self.assertEqual(self.monitor.daily_pnl, -10.0)
        self.assertFalse(self.monitor.trading_halted)
    
    def test_post_trade_exceeds_daily_loss_limit(self):
        """Test post-trade check trips kill switch on excessive loss."""
        # Lose $25 (2.5% of $1000)
        # Exceeds max_daily_loss_pct of 2%
        
        new_equity = 975.0
        self.monitor.check_post_trade(new_equity)
        
        self.assertEqual(self.monitor.current_equity, 975.0)
        self.assertTrue(self.monitor.trading_halted)
        self.assertTrue(self.monitor.kill_switch_engaged())
        # Module 27: Message changed from "Daily loss limit" to "Drawdown limit"
        self.assertIn("Drawdown limit exceeded", self.monitor.halt_reason)
    
    def test_post_trade_profit(self):
        """Test post-trade check with profit."""
        # Gain $50
        new_equity = 1050.0
        self.monitor.check_post_trade(new_equity)
        
        self.assertEqual(self.monitor.current_equity, 1050.0)
        self.assertEqual(self.monitor.daily_pnl, 50.0)
        self.assertFalse(self.monitor.trading_halted)
    
    def test_kill_switch_env_var_engaged(self):
        """Test kill switch via environment variable."""
        self.assertFalse(self.monitor.kill_switch_engaged())
        
        # Set environment variable
        os.environ["TEST_KILL_SWITCH"] = "1"
        
        self.assertTrue(self.monitor.kill_switch_engaged())
        self.assertTrue(self.monitor.trading_halted)
    
    def test_kill_switch_various_truthy_values(self):
        """Test kill switch with various truthy values."""
        for value in ["1", "true", "yes", "on", "TRUE", "YES"]:
            os.environ["TEST_KILL_SWITCH"] = value
            self.assertTrue(self.monitor.kill_switch_engaged())
            del os.environ["TEST_KILL_SWITCH"]
    
    def test_kill_switch_falsy_values(self):
        """Test kill switch with falsy values."""
        for value in ["0", "false", "no", "off", ""]:
            os.environ["TEST_KILL_SWITCH"] = value
            self.assertFalse(self.monitor.kill_switch_engaged())
            del os.environ["TEST_KILL_SWITCH"]
    
    def test_position_tracking(self):
        """Test position open/close tracking."""
        # Open position
        self.monitor.record_position_open("BTCUSDT", 0.1, 50000.0, OrderSide.LONG)
        
        self.assertEqual(len(self.monitor.open_positions), 1)
        self.assertIn("BTCUSDT", self.monitor.open_positions)
        
        # Close position
        self.monitor.record_position_close("BTCUSDT", 51000.0, 100.0)
        
        self.assertEqual(len(self.monitor.open_positions), 0)
        self.assertNotIn("BTCUSDT", self.monitor.open_positions)
    
    def test_exposure_calculation(self):
        """Test total exposure calculation."""
        # Open 2 positions
        self.monitor.record_position_open("BTCUSDT", 0.1, 50000.0, OrderSide.LONG)  # $5000
        self.monitor.record_position_open("ETHUSDT", 1.0, 3000.0, OrderSide.LONG)   # $3000
        
        exposure = self.monitor._calculate_total_exposure()
        
        self.assertEqual(exposure, 8000.0)  # $5000 + $3000
    
    def test_reset_daily_limits(self):
        """Test resetting daily limits."""
        # Simulate some trading
        self.monitor.check_post_trade(950.0)  # Lost $50
        self.monitor.daily_pnl = -50.0
        
        # Reset with new starting equity
        self.monitor.reset_daily_limits(new_starting_equity=950.0)
        
        self.assertEqual(self.monitor.starting_equity, 950.0)
        self.assertEqual(self.monitor.daily_pnl, 0.0)
        self.assertFalse(self.monitor.trading_halted)
        self.assertIsNone(self.monitor.halt_reason)
    
    def test_get_status(self):
        """Test get_status returns complete state."""
        # Open a position and simulate loss
        self.monitor.record_position_open("BTCUSDT", 0.1, 50000.0, OrderSide.LONG)
        self.monitor.check_post_trade(990.0)
        
        status = self.monitor.get_status()
        
        self.assertEqual(status["starting_equity"], 1000.0)
        self.assertEqual(status["current_equity"], 990.0)
        self.assertEqual(status["daily_pnl"], -10.0)
        self.assertEqual(status["open_positions"], 1)
        self.assertEqual(status["total_exposure"], 5000.0)
        self.assertAlmostEqual(status["exposure_pct"], 5000.0 / 990.0)
        self.assertIn("limits", status)
    
    def test_kill_switch_blocks_pre_trade(self):
        """Test kill switch blocks new orders."""
        # Trigger kill switch
        self.monitor._halt_trading("Test halt")
        
        order = self.create_test_order()
        
        with self.assertRaises(SafetyViolation) as ctx:
            self.monitor.check_pre_trade(
                order=order,
                risk_amount=5.0,
                position_value=100.0
            )
        
        self.assertIn("Trading halted", str(ctx.exception))


class TestSafetyMonitorIntegration(unittest.TestCase):
    """Integration tests for SafetyMonitor in trading scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.limits = SafetyLimits(
            max_daily_loss_pct=0.05,  # 5% max loss
            max_risk_per_trade_pct=0.02,  # 2% risk per trade
            max_exposure_pct=0.30,  # 30% max exposure
            max_open_trades=5
        )
        
        self.monitor = SafetyMonitor(
            limits=self.limits,
            starting_equity=10000.0
        )
    
    def test_successful_trading_day(self):
        """Test a successful trading day scenario."""
        # Trade 1: Win
        self.monitor.check_pre_trade(
            OrderRequest("BTCUSDT", OrderSide.LONG, OrderType.MARKET, 0.1),
            risk_amount=100.0,
            position_value=1000.0  # Changed from 5000 to stay within 30% limit
        )
        self.monitor.record_position_open("BTCUSDT", 0.1, 10000.0, OrderSide.LONG)  # Adjusted
        self.monitor.check_post_trade(10100.0)
        self.monitor.record_position_close("BTCUSDT", 10100.0, 100.0)
        
        # Trade 2: Win
        self.monitor.check_pre_trade(
            OrderRequest("ETHUSDT", OrderSide.LONG, OrderType.MARKET, 1.0),
            risk_amount=150.0,
            position_value=3000.0
        )
        self.monitor.record_position_open("ETHUSDT", 1.0, 3000.0, OrderSide.LONG)
        self.monitor.check_post_trade(10250.0)
        self.monitor.record_position_close("ETHUSDT", 3150.0, 150.0)
        
        # Final status
        status = self.monitor.get_status()
        
        self.assertEqual(status["current_equity"], 10250.0)
        self.assertEqual(status["daily_pnl"], 250.0)
        self.assertFalse(status["trading_halted"])
    
    def test_losing_day_hits_stop_loss(self):
        """Test trading day that hits daily loss limit."""
        # Simulate several losing trades totaling more than 5%
        # Each trade loses $200, need to lose $500+ to exceed 5% of $10000
        
        # Trade 1: Lose $200
        self.monitor.record_position_open("SYM1", 1.0, 1000.0, OrderSide.LONG)
        self.monitor.check_post_trade(9800.0)  # Down $200
        self.monitor.record_position_close("SYM1", 800.0, -200.0)
        
        # After first loss, should not be halted yet (2% < 5%)
        self.assertFalse(self.monitor.trading_halted)
        
        # Trade 2: Lose another $200
        self.monitor.record_position_open("SYM2", 1.0, 1000.0, OrderSide.LONG)
        self.monitor.check_post_trade(9600.0)  # Down $400 total
        self.monitor.record_position_close("SYM2", 800.0, -200.0)
        
        # After second loss, should not be halted yet (4% < 5%)
        self.assertFalse(self.monitor.trading_halted)
        
        # Trade 3: Lose another $200 - this should trip the kill switch
        self.monitor.record_position_open("SYM3", 1.0, 1000.0, OrderSide.LONG)
        self.monitor.check_post_trade(9400.0)  # Down $600 total = 6% > 5%
        self.monitor.record_position_close("SYM3", 800.0, -200.0)
        
        # Now should be halted (6% > 5% limit)
        self.assertTrue(self.monitor.trading_halted)
        self.assertTrue(self.monitor.kill_switch_engaged())


if __name__ == "__main__":
    unittest.main()
