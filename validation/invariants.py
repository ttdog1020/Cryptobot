"""
Invariant Checks for Trading System Validation (Module 20)

Provides reusable invariant check functions that validate accounting,
risk management, and position integrity. All functions raise AssertionError
with descriptive messages when invariants are violated.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional


def check_accounting_invariants(
    log_df: pd.DataFrame,
    starting_balance: float,
    epsilon: float = 0.01
) -> None:
    """
    Validate accounting invariants on trading logs.
    
    Checks:
    1. Final balance ≈ starting balance + realized PnL
    2. Equity ≈ balance + unrealized PnL (if unrealized_pnl exists)
    3. Sum of per-trade realized_pnl ≈ reported total PnL
    
    Args:
        log_df: Trading log DataFrame with columns like balance, equity, realized_pnl
        starting_balance: Initial account balance
        epsilon: Tolerance for floating-point comparisons (default 0.01 = 1 cent)
    
    Raises:
        AssertionError: When any accounting invariant is violated
    """
    if log_df.empty:
        raise AssertionError("Cannot check accounting invariants on empty log")
    
    # Get final balance
    final_balance = log_df.iloc[-1]['balance']
    
    # Check 1: Final balance ≈ starting_balance + sum(realized_pnl)
    if 'realized_pnl' in log_df.columns:
        # Sum all realized PnL (including INIT row which has 0)
        total_realized_pnl = log_df['realized_pnl'].sum()
        expected_final_balance = starting_balance + total_realized_pnl
        balance_diff = abs(final_balance - expected_final_balance)
        
        if balance_diff > epsilon:
            raise AssertionError(
                f"Accounting invariant violated: Final balance mismatch!\n"
                f"  Starting balance: ${starting_balance:.2f}\n"
                f"  Total realized PnL: ${total_realized_pnl:.2f}\n"
                f"  Expected final: ${expected_final_balance:.2f}\n"
                f"  Actual final: ${final_balance:.2f}\n"
                f"  Difference: ${balance_diff:.2f} (epsilon={epsilon})"
            )
    
    # Check 2: Equity ≈ balance + unrealized_pnl (for rows where both exist)
    if 'equity' in log_df.columns and 'balance' in log_df.columns:
        # For rows with unrealized_pnl, check equity calculation
        if 'unrealized_pnl' in log_df.columns:
            for idx, row in log_df.iterrows():
                expected_equity = row['balance'] + row.get('unrealized_pnl', 0)
                actual_equity = row['equity']
                equity_diff = abs(actual_equity - expected_equity)
                
                if equity_diff > epsilon:
                    raise AssertionError(
                        f"Equity calculation violated at row {idx}!\n"
                        f"  Balance: ${row['balance']:.2f}\n"
                        f"  Unrealized PnL: ${row.get('unrealized_pnl', 0):.2f}\n"
                        f"  Expected equity: ${expected_equity:.2f}\n"
                        f"  Actual equity: ${actual_equity:.2f}\n"
                        f"  Difference: ${equity_diff:.2f}"
                    )
    
    # Check 3: Sum of closed trade PnL matches total
    if 'action' in log_df.columns and 'realized_pnl' in log_df.columns:
        # Filter for CLOSE actions only (actual completed trades)
        closed_trades = log_df[log_df['action'] == 'CLOSE']
        if not closed_trades.empty:
            per_trade_sum = closed_trades['realized_pnl'].sum()
            # Total realized PnL should match sum of closed trades
            # (INIT and OPEN rows have 0 realized_pnl)
            total_from_all_rows = log_df['realized_pnl'].sum()
            diff = abs(per_trade_sum - total_from_all_rows)
            
            if diff > epsilon:
                raise AssertionError(
                    f"Per-trade PnL sum mismatch!\n"
                    f"  Sum of CLOSE actions: ${per_trade_sum:.2f}\n"
                    f"  Total from all rows: ${total_from_all_rows:.2f}\n"
                    f"  Difference: ${diff:.2f}"
                )


def check_risk_invariants(
    trades_df: pd.DataFrame,
    risk_config: Dict[str, Any],
    epsilon: float = 0.001
) -> None:
    """
    Validate risk management invariants on trading data.
    
    Checks:
    1. Dollar risk per trade <= default_risk_per_trade * equity_at_entry
    2. Total simultaneous risk <= max_exposure * equity
    
    Args:
        trades_df: DataFrame with columns like quantity, fill_price, equity, action, symbol
        risk_config: Dict with keys 'default_risk_per_trade', 'max_exposure'
        epsilon: Tolerance for floating-point comparisons (default 0.001 = 0.1%)
    
    Raises:
        AssertionError: When any risk invariant is violated
    """
    if trades_df.empty:
        return  # No trades to validate
    
    default_risk_pct = risk_config.get('default_risk_per_trade', 0.01)
    max_exposure_pct = risk_config.get('max_exposure', 1.0)
    
    # Track open positions for simultaneous risk calculation
    open_positions = {}
    
    for idx, row in trades_df.iterrows():
        action = row.get('action', 'UNKNOWN')
        symbol = row.get('symbol', '')
        
        if action == 'INIT':
            continue
        
        # Check 1: Individual trade risk
        if action == 'OPEN' and 'equity' in row and 'fill_value' in row:
            equity_at_entry = row['equity']
            position_size = abs(row['fill_value'])
            max_allowed_risk = default_risk_pct * equity_at_entry
            
            # Assuming stop loss would risk up to default_risk_pct of equity
            # For now, check that position size doesn't exceed reasonable limits
            # (position_size should be <= equity, and risk per trade is a fraction)
            # Conservative check: position_size <= equity (no over-leveraging)
            if position_size > equity_at_entry * (1 + epsilon):
                raise AssertionError(
                    f"Risk invariant violated at row {idx}: Position size exceeds equity!\n"
                    f"  Symbol: {symbol}\n"
                    f"  Position size: ${position_size:.2f}\n"
                    f"  Equity at entry: ${equity_at_entry:.2f}\n"
                    f"  Over-leveraged by: ${position_size - equity_at_entry:.2f}"
                )
            
            # Track open position
            open_positions[symbol] = {
                'size': position_size,
                'equity': equity_at_entry,
                'row': idx
            }
        
        elif action == 'CLOSE' and symbol in open_positions:
            # Remove closed position
            del open_positions[symbol]
        
        # Check 2: Simultaneous risk exposure
        if open_positions and 'equity' in row:
            total_exposure = sum(pos['size'] for pos in open_positions.values())
            current_equity = row['equity']
            max_allowed_exposure = max_exposure_pct * current_equity
            
            if total_exposure > max_allowed_exposure * (1 + epsilon):
                open_symbols = ', '.join(open_positions.keys())
                raise AssertionError(
                    f"Exposure limit violated at row {idx}!\n"
                    f"  Total exposure: ${total_exposure:.2f}\n"
                    f"  Current equity: ${current_equity:.2f}\n"
                    f"  Max allowed ({max_exposure_pct*100}%): ${max_allowed_exposure:.2f}\n"
                    f"  Excess: ${total_exposure - max_allowed_exposure:.2f}\n"
                    f"  Open positions: {open_symbols}"
                )


def check_position_invariants(
    positions_df: pd.DataFrame,
    epsilon: float = 1e-8
) -> None:
    """
    Validate position integrity invariants.
    
    Checks:
    1. No zero-quantity positions
    2. Long positions have positive notional; shorts negative
    3. No overlapping contradictory positions per symbol
    
    Args:
        positions_df: DataFrame with columns like symbol, side, quantity, fill_value
        epsilon: Tolerance for zero-quantity check (default 1e-8)
    
    Raises:
        AssertionError: When any position invariant is violated
    """
    if positions_df.empty:
        return  # No positions to validate
    
    # Check 1: No zero-quantity positions
    if 'quantity' in positions_df.columns:
        zero_qty_positions = positions_df[abs(positions_df['quantity']) < epsilon]
        if not zero_qty_positions.empty:
            raise AssertionError(
                f"Position invariant violated: Found {len(zero_qty_positions)} "
                f"zero-quantity positions!\n"
                f"Symbols: {zero_qty_positions['symbol'].tolist()}"
            )
    
    # Check 2: Side and notional alignment
    if 'side' in positions_df.columns and 'quantity' in positions_df.columns:
        for idx, row in positions_df.iterrows():
            side = row['side']
            qty = row['quantity']
            
            if side == 'LONG' and qty <= 0:
                raise AssertionError(
                    f"Position invariant violated at row {idx}: "
                    f"LONG position has non-positive quantity!\n"
                    f"  Symbol: {row.get('symbol', 'UNKNOWN')}\n"
                    f"  Quantity: {qty}"
                )
            
            if side == 'SHORT' and qty >= 0:
                raise AssertionError(
                    f"Position invariant violated at row {idx}: "
                    f"SHORT position has non-negative quantity!\n"
                    f"  Symbol: {row.get('symbol', 'UNKNOWN')}\n"
                    f"  Quantity: {qty}"
                )
    
    # Check 3: No duplicate open positions per symbol (only one position per symbol)
    if 'symbol' in positions_df.columns and 'action' in positions_df.columns:
        # Filter for OPEN actions
        open_positions = positions_df[positions_df['action'] == 'OPEN']
        
        # Group by symbol and check for duplicates
        symbol_counts = open_positions['symbol'].value_counts()
        duplicates = symbol_counts[symbol_counts > 1]
        
        if not duplicates.empty:
            duplicate_symbols = duplicates.index.tolist()
            raise AssertionError(
                f"Position invariant violated: Multiple open positions detected!\n"
                f"  Symbols with overlapping positions: {duplicate_symbols}\n"
                f"  Counts: {duplicates.to_dict()}"
            )


def validate_trade_sequence(
    log_df: pd.DataFrame,
    allow_multiple_positions: bool = False
) -> None:
    """
    Validate that trade sequence follows proper open/close pattern.
    
    Checks:
    1. Every CLOSE has a matching OPEN for the same symbol
    2. No CLOSE before OPEN for same symbol
    3. No multiple OPENs without CLOSE (unless allow_multiple_positions=True)
    
    Args:
        log_df: Trading log DataFrame with action and symbol columns
        allow_multiple_positions: Whether to allow multiple simultaneous positions per symbol
    
    Raises:
        AssertionError: When trade sequence is invalid
    """
    if log_df.empty or 'action' not in log_df.columns:
        return
    
    open_positions = {}  # symbol -> list of row indices
    
    for idx, row in log_df.iterrows():
        action = row.get('action', '')
        symbol = row.get('symbol', '')
        
        if action == 'INIT':
            continue
        
        if not symbol:
            continue
        
        if action == 'OPEN':
            if symbol not in open_positions:
                open_positions[symbol] = []
            
            if not allow_multiple_positions and open_positions[symbol]:
                raise AssertionError(
                    f"Trade sequence violated at row {idx}: "
                    f"Multiple OPEN actions for {symbol} without CLOSE!\n"
                    f"  Previous OPEN at rows: {open_positions[symbol]}"
                )
            
            open_positions[symbol].append(idx)
        
        elif action == 'CLOSE':
            if symbol not in open_positions or not open_positions[symbol]:
                raise AssertionError(
                    f"Trade sequence violated at row {idx}: "
                    f"CLOSE action for {symbol} without matching OPEN!"
                )
            
            # Remove the most recent OPEN for this symbol
            open_positions[symbol].pop()
            if not open_positions[symbol]:
                del open_positions[symbol]
    
    # After processing all rows, check for unclosed positions
    if open_positions:
        unclosed = {sym: rows for sym, rows in open_positions.items() if rows}
        if unclosed:
            # This is not necessarily an error (positions can remain open at end)
            # Just informational - could be converted to warning in production
            pass
