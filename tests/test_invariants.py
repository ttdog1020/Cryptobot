"""
Tests for Invariant Validation Functions (Module 20)

Tests accounting, risk, and position invariant checks.
"""

import unittest
import pandas as pd
import numpy as np
from validation.invariants import (
    check_accounting_invariants,
    check_risk_invariants,
    check_position_invariants,
    validate_trade_sequence
)


class TestAccountingInvariants(unittest.TestCase):
    """Test accounting invariant validation."""
    
    def test_happy_path_valid_accounting(self):
        """Test that valid accounting passes all checks."""
        # Create log with correct accounting including commissions
        # Starting: $1000
        # OPEN: buy $500 position, commission $0.50 -> balance = $499.50
        # CLOSE: sell for $515, commission $0.52, realized_pnl = $15 - $1.02 = $13.98
        # Final balance: $1000 + $13.98 = $1013.98
        log_data = [
            {
                'timestamp': '2024-01-01 00:00:00',
                'balance': 1000.0,
                'equity': 1000.0,
                'realized_pnl': 0.0,
                'action': 'INIT'
            },
            {
                'timestamp': '2024-01-01 01:00:00',
                'balance': 499.50,
                'equity': 1004.50,
                'realized_pnl': 0.0,
                'action': 'OPEN'
            },
            {
                'timestamp': '2024-01-01 02:00:00',
                'balance': 1013.98,
                'equity': 1013.98,
                'realized_pnl': 13.98,
                'action': 'CLOSE'
            },
        ]
        log_df = pd.DataFrame(log_data)
        
        # Should not raise
        try:
            check_accounting_invariants(log_df, starting_balance=1000.0)
        except AssertionError as e:
            self.fail(f"Valid accounting raised AssertionError: {e}")
    
    def test_final_balance_mismatch(self):
        """Test that mismatched final balance is detected."""
        log_data = [
            {'balance': 1000.0, 'equity': 1000.0, 'realized_pnl': 0.0, 'action': 'INIT'},
            {'balance': 990.0, 'equity': 1005.0, 'realized_pnl': 0.0, 'action': 'OPEN'},
            {'balance': 1100.0, 'equity': 1100.0, 'realized_pnl': 15.0, 'action': 'CLOSE'},  # Wrong!
        ]
        log_df = pd.DataFrame(log_data)
        
        # Should raise AssertionError
        with self.assertRaises(AssertionError) as context:
            check_accounting_invariants(log_df, starting_balance=1000.0)
        
        self.assertIn("Final balance mismatch", str(context.exception))
    
    def test_empty_log_raises(self):
        """Test that empty log raises error."""
        log_df = pd.DataFrame()
        
        with self.assertRaises(AssertionError):
            check_accounting_invariants(log_df, starting_balance=1000.0)
    
    def test_multiple_trades_accounting(self):
        """Test accounting with multiple trades."""
        log_data = [
            {'balance': 10000.0, 'equity': 10000.0, 'realized_pnl': 0.0, 'action': 'INIT'},
            {'balance': 9500.0, 'equity': 10050.0, 'realized_pnl': 0.0, 'action': 'OPEN'},
            {'balance': 10100.0, 'equity': 10100.0, 'realized_pnl': 100.0, 'action': 'CLOSE'},
            {'balance': 9600.0, 'equity': 9550.0, 'realized_pnl': 0.0, 'action': 'OPEN'},
            {'balance': 9050.0, 'equity': 9050.0, 'realized_pnl': -50.0, 'action': 'CLOSE'},
        ]
        log_df = pd.DataFrame(log_data)
        
        # Total realized PnL = 100 - 50 = 50
        # Final balance should be 10000 + 50 = 10050
        # But we have 9050, so this should fail
        with self.assertRaises(AssertionError):
            check_accounting_invariants(log_df, starting_balance=10000.0)
    
    def test_per_trade_sum_matches_total(self):
        """Test that sum of individual trade PnLs matches reported total."""
        log_data = [
            {'balance': 1000.0, 'equity': 1000.0, 'realized_pnl': 0.0, 'action': 'INIT'},
            {'balance': 995.0, 'equity': 1010.0, 'realized_pnl': 0.0, 'action': 'OPEN'},
            {'balance': 1020.0, 'equity': 1020.0, 'realized_pnl': 20.0, 'action': 'CLOSE'},
            {'balance': 1015.0, 'equity': 1005.0, 'realized_pnl': 0.0, 'action': 'OPEN'},
            {'balance': 1005.0, 'equity': 1005.0, 'realized_pnl': -10.0, 'action': 'CLOSE'},
        ]
        log_df = pd.DataFrame(log_data)
        
        # Sum of closed trades: 20 - 10 = 10
        # Final balance: 1000 + 10 = 1010, but we have 1005
        with self.assertRaises(AssertionError):
            check_accounting_invariants(log_df, starting_balance=1000.0)


class TestRiskInvariants(unittest.TestCase):
    """Test risk management invariant validation."""
    
    def test_valid_risk_limits(self):
        """Test that valid risk levels pass."""
        trades_data = [
            {'action': 'INIT', 'symbol': '', 'equity': 10000.0, 'fill_value': 0.0},
            {'action': 'OPEN', 'symbol': 'BTCUSDT', 'equity': 10000.0, 'fill_value': 1000.0},
            {'action': 'CLOSE', 'symbol': 'BTCUSDT', 'equity': 10050.0, 'fill_value': 1005.0},
        ]
        trades_df = pd.DataFrame(trades_data)
        
        risk_config = {
            'default_risk_per_trade': 0.01,
            'max_exposure': 0.20
        }
        
        # Should not raise
        try:
            check_risk_invariants(trades_df, risk_config)
        except AssertionError as e:
            self.fail(f"Valid risk levels raised AssertionError: {e}")
    
    def test_over_leveraged_position(self):
        """Test detection of over-leveraged positions."""
        trades_data = [
            {'action': 'INIT', 'symbol': '', 'equity': 10000.0, 'fill_value': 0.0},
            {'action': 'OPEN', 'symbol': 'BTCUSDT', 'equity': 10000.0, 'fill_value': 50000.0},  # 5x leverage!
        ]
        trades_df = pd.DataFrame(trades_data)
        
        risk_config = {
            'default_risk_per_trade': 0.01,
            'max_exposure': 0.20
        }
        
        with self.assertRaises(AssertionError) as context:
            check_risk_invariants(trades_df, risk_config)
        
        self.assertIn("Position size exceeds equity", str(context.exception))
    
    def test_exposure_limit_violation(self):
        """Test detection of exposure limit violations."""
        trades_data = [
            {'action': 'INIT', 'symbol': '', 'equity': 10000.0, 'fill_value': 0.0},
            {'action': 'OPEN', 'symbol': 'BTCUSDT', 'equity': 10000.0, 'fill_value': 1500.0},
            {'action': 'OPEN', 'symbol': 'ETHUSDT', 'equity': 10000.0, 'fill_value': 1500.0},  # Total: 30% > 20%
        ]
        trades_df = pd.DataFrame(trades_data)
        
        risk_config = {
            'default_risk_per_trade': 0.01,
            'max_exposure': 0.20
        }
        
        with self.assertRaises(AssertionError) as context:
            check_risk_invariants(trades_df, risk_config)
        
        self.assertIn("Exposure limit violated", str(context.exception))
    
    def test_empty_trades_passes(self):
        """Test that empty trades DataFrame doesn't raise."""
        trades_df = pd.DataFrame()
        
        risk_config = {
            'default_risk_per_trade': 0.01,
            'max_exposure': 0.20
        }
        
        # Should not raise
        check_risk_invariants(trades_df, risk_config)


class TestPositionInvariants(unittest.TestCase):
    """Test position integrity invariant validation."""
    
    def test_zero_quantity_detection(self):
        """Test detection of zero-quantity positions."""
        positions_data = [
            {'symbol': 'BTCUSDT', 'side': 'LONG', 'quantity': 0.01, 'action': 'OPEN'},
            {'symbol': 'ETHUSDT', 'side': 'LONG', 'quantity': 0.0, 'action': 'OPEN'},  # Zero qty!
        ]
        positions_df = pd.DataFrame(positions_data)
        
        with self.assertRaises(AssertionError) as context:
            check_position_invariants(positions_df)
        
        self.assertIn("zero-quantity", str(context.exception))
    
    def test_long_with_negative_quantity(self):
        """Test detection of LONG position with negative quantity."""
        positions_data = [
            {'symbol': 'BTCUSDT', 'side': 'LONG', 'quantity': -0.01, 'action': 'OPEN'},
        ]
        positions_df = pd.DataFrame(positions_data)
        
        with self.assertRaises(AssertionError) as context:
            check_position_invariants(positions_df)
        
        self.assertIn("non-positive quantity", str(context.exception))
    
    def test_short_with_positive_quantity(self):
        """Test detection of SHORT position with positive quantity."""
        positions_data = [
            {'symbol': 'BTCUSDT', 'side': 'SHORT', 'quantity': 0.01, 'action': 'OPEN'},
        ]
        positions_df = pd.DataFrame(positions_data)
        
        with self.assertRaises(AssertionError) as context:
            check_position_invariants(positions_df)
        
        self.assertIn("non-negative quantity", str(context.exception))
    
    def test_duplicate_open_positions(self):
        """Test detection of multiple open positions for same symbol."""
        positions_data = [
            {'symbol': 'BTCUSDT', 'side': 'LONG', 'quantity': 0.01, 'action': 'OPEN'},
            {'symbol': 'BTCUSDT', 'side': 'LONG', 'quantity': 0.02, 'action': 'OPEN'},  # Duplicate!
        ]
        positions_df = pd.DataFrame(positions_data)
        
        with self.assertRaises(AssertionError) as context:
            check_position_invariants(positions_df)
        
        self.assertIn("Multiple open positions", str(context.exception))
    
    def test_empty_positions_passes(self):
        """Test that empty positions DataFrame doesn't raise."""
        positions_df = pd.DataFrame()
        
        # Should not raise
        check_position_invariants(positions_df)


class TestTradeSequence(unittest.TestCase):
    """Test trade sequence validation."""
    
    def test_valid_sequence(self):
        """Test valid OPEN->CLOSE sequence."""
        log_data = [
            {'action': 'INIT', 'symbol': ''},
            {'action': 'OPEN', 'symbol': 'BTCUSDT'},
            {'action': 'CLOSE', 'symbol': 'BTCUSDT'},
        ]
        log_df = pd.DataFrame(log_data)
        
        # Should not raise
        validate_trade_sequence(log_df)
    
    def test_close_without_open(self):
        """Test detection of CLOSE without OPEN."""
        log_data = [
            {'action': 'INIT', 'symbol': ''},
            {'action': 'CLOSE', 'symbol': 'BTCUSDT'},  # No prior OPEN!
        ]
        log_df = pd.DataFrame(log_data)
        
        with self.assertRaises(AssertionError) as context:
            validate_trade_sequence(log_df)
        
        self.assertIn("without matching OPEN", str(context.exception))
    
    def test_multiple_opens_without_close(self):
        """Test detection of multiple OPENs without CLOSE."""
        log_data = [
            {'action': 'INIT', 'symbol': ''},
            {'action': 'OPEN', 'symbol': 'BTCUSDT'},
            {'action': 'OPEN', 'symbol': 'BTCUSDT'},  # Second OPEN!
        ]
        log_df = pd.DataFrame(log_data)
        
        with self.assertRaises(AssertionError) as context:
            validate_trade_sequence(log_df, allow_multiple_positions=False)
        
        self.assertIn("Multiple OPEN actions", str(context.exception))


if __name__ == '__main__':
    unittest.main()
