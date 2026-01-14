"""
Safety Suite - Comprehensive Validation System (Module 20 + 24)

Provides differential testing, invariant validation, and a unified
safety check runner for detecting accounting, risk, and execution
discrepancies before enabling real trading.

MODULE 24: Added safety monitor and kill switch tests.
"""

import pandas as pd
import numpy as np
import os
from pathlib import Path
from typing import Dict, Any, Tuple
import sys

# Import validation components
from . import invariants
from . import synthetic_data

# Import trading system components
from strategies.ema_rsi import add_indicators, generate_signal
from execution.paper_trader import PaperTrader
from execution.execution_engine import ExecutionEngine
from execution.order_types import OrderRequest, OrderSide, OrderType
from execution.safety import SafetyMonitor, SafetyLimits, SafetyViolation


def run_backtest_vs_paper_consistency_test(
    num_candles: int = 200,
    starting_balance: float = 10000.0,
    tolerance_pct: float = 0.5,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Run differential test comparing backtest engine vs live paper trading.
    
    Uses synthetic data to drive both:
    1. Simplified backtest simulation
    2. ExecutionEngine + PaperTrader pipeline
    
    Validates that both produce similar results (PnL, trade count, positions).
    
    Args:
        num_candles: Number of candles in synthetic series
        starting_balance: Starting capital for both tests
        tolerance_pct: Acceptable PnL difference percentage
        verbose: Print detailed progress
    
    Returns:
        Dictionary with test results and metrics
    
    Raises:
        AssertionError: When consistency checks fail
    """
    if verbose:
        print("\n" + "="*70)
        print("DIFFERENTIAL TEST: Backtest vs Paper Trading Consistency")
        print("="*70)
    
    # Step 1: Generate synthetic data
    if verbose:
        print(f"\n[1/4] Generating {num_candles} synthetic candles...")
    
    df = synthetic_data.generate_trend_series(
        symbol="BTCUSDT",
        start_price=50000.0,
        num_candles=num_candles,
        timeframe="1h",
        trend_strength=0.015,  # Moderate trend
        volatility=0.008,
        seed=42
    )
    
    if verbose:
        print(f"      Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
        print(f"      Total return: {((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100:.2f}%")
    
    # Step 2: Run simplified backtest
    if verbose:
        print("\n[2/4] Running simplified backtest...")
    
    backtest_result = _run_simplified_backtest(df, starting_balance, verbose)
    
    # Step 3: Run paper trading simulation
    if verbose:
        print("\n[3/4] Running paper trading simulation...")
    
    paper_result = _run_paper_simulation(df, starting_balance, verbose)
    
    # Step 4: Compare results
    if verbose:
        print("\n[4/4] Comparing results...")
        print("\n" + "-"*70)
        print("COMPARISON SUMMARY")
        print("-"*70)
        print(f"{'Metric':<30} {'Backtest':<20} {'Paper':<20}")
        print("-"*70)
    
    # Extract metrics
    bt_pnl = backtest_result['final_balance'] - starting_balance
    paper_pnl = paper_result['final_balance'] - starting_balance
    pnl_diff_pct = abs(bt_pnl - paper_pnl) / starting_balance * 100 if starting_balance > 0 else 0
    
    bt_trades = backtest_result['total_trades']
    paper_trades = paper_result['total_trades']
    
    if verbose:
        print(f"{'Total PnL':<30} ${bt_pnl:<19.2f} ${paper_pnl:<19.2f}")
        print(f"{'Final Balance':<30} ${backtest_result['final_balance']:<19.2f} ${paper_result['final_balance']:<19.2f}")
        print(f"{'Trade Count':<30} {bt_trades:<20} {paper_trades:<20}")
        print(f"{'Win Rate':<30} {backtest_result['win_rate']:<19.1f}% {paper_result['win_rate']:<19.1f}%")
        print("-"*70)
        print(f"\nPnL Difference: {pnl_diff_pct:.3f}% (tolerance: {tolerance_pct}%)")
    
    # Step 5: Run invariant checks
    if verbose:
        print("\n" + "-"*70)
        print("INVARIANT CHECKS")
        print("-"*70)
    
    # Check accounting invariants on backtest log
    if verbose:
        print("  Checking backtest accounting...")
    try:
        invariants.check_accounting_invariants(
            backtest_result['log_df'],
            starting_balance,
            epsilon=0.01
        )
        if verbose:
            print("    [OK] Backtest accounting valid")
    except AssertionError as e:
        if verbose:
            print(f"    ✗ Backtest accounting FAILED: {e}")
        raise
    
    # Check accounting invariants on paper log
    if verbose:
        print("  Checking paper trading accounting...")
    try:
        invariants.check_accounting_invariants(
            paper_result['log_df'],
            starting_balance,
            epsilon=0.01
        )
        if verbose:
            print("    [OK] Paper trading accounting valid")
    except AssertionError as e:
        if verbose:
            print(f"    ✗ Paper trading accounting FAILED: {e}")
        raise
    
    # Check risk invariants
    risk_config = {
        'default_risk_per_trade': 0.01,
        'max_exposure': 0.20
    }
    
    if verbose:
        print("  Checking paper trading risk limits...")
    try:
        invariants.check_risk_invariants(
            paper_result['log_df'],
            risk_config,
            epsilon=0.001
        )
        if verbose:
            print("    [OK] Risk limits respected")
    except AssertionError as e:
        if verbose:
            print(f"    ✗ Risk limits VIOLATED: {e}")
        raise
    
    # Step 6: Assert consistency
    if verbose:
        print("\n" + "-"*70)
        print("CONSISTENCY VALIDATION")
        print("-"*70)
    
    # PnL should be within tolerance
    if pnl_diff_pct > tolerance_pct:
        raise AssertionError(
            f"PnL consistency check FAILED!\n"
            f"  Backtest PnL: ${bt_pnl:.2f}\n"
            f"  Paper PnL: ${paper_pnl:.2f}\n"
            f"  Difference: {pnl_diff_pct:.3f}% (tolerance: {tolerance_pct}%)"
        )
    
    if verbose:
        print(f"  [OK] PnL within tolerance ({pnl_diff_pct:.3f}% < {tolerance_pct}%)")
    
    # Trade counts should be reasonably close (within 20%)
    if bt_trades > 0:
        trade_diff_pct = abs(bt_trades - paper_trades) / bt_trades * 100
        if trade_diff_pct > 20:
            raise AssertionError(
                f"Trade count consistency check FAILED!\n"
                f"  Backtest trades: {bt_trades}\n"
                f"  Paper trades: {paper_trades}\n"
                f"  Difference: {trade_diff_pct:.1f}% (max: 20%)"
            )
        
        if verbose:
            print(f"  [OK] Trade count reasonably close ({trade_diff_pct:.1f}% difference)")
    else:
        if verbose:
            print("  ⚠ No trades executed (not enough signals)")
    
    if verbose:
        print("\n" + "="*70)
        print("[OK] DIFFERENTIAL TEST PASSED")
        print("="*70)
    
    return {
        'passed': True,
        'backtest': backtest_result,
        'paper': paper_result,
        'pnl_diff_pct': pnl_diff_pct
    }


def _run_simplified_backtest(
    df: pd.DataFrame,
    starting_balance: float,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Run simplified backtest simulation on synthetic data.
    
    Returns dictionary with final_balance, total_trades, win_rate, log_df.
    """
    # Add indicators
    df = add_indicators(df.copy())
    
    # Track trades
    balance = starting_balance
    position = None
    entry_price = 0
    trades = []
    log_rows = []
    
    # INIT row
    log_rows.append({
        'timestamp': df.iloc[0]['timestamp'],
        'symbol': 'BTCUSDT',
        'action': 'INIT',
        'side': '',
        'quantity': 0,
        'fill_price': 0,
        'fill_value': 0,
        'commission': 0,
        'slippage': 0,
        'realized_pnl': 0,
        'pnl_pct': 0,
        'balance': balance,
        'equity': balance,
        'open_positions': 0
    })
    
    # Walk through candles
    for i in range(50, len(df)):
        window = df.iloc[:i+1].copy()
        signal = generate_signal(window)
        current_price = df.iloc[i]['close']
        
        # Position management
        if position is None and signal == "BUY":
            # Open LONG
            quantity = 0.01  # Fixed quantity for testing
            position_value = current_price * quantity
            commission = position_value * 0.001
            
            if balance >= position_value + commission:
                position = 'LONG'
                entry_price = current_price
                balance -= (position_value + commission)
                
                log_rows.append({
                    'timestamp': df.iloc[i]['timestamp'],
                    'symbol': 'BTCUSDT',
                    'action': 'OPEN',
                    'side': 'LONG',
                    'quantity': quantity,
                    'fill_price': current_price,
                    'fill_value': position_value,
                    'commission': commission,
                    'slippage': 0,
                    'realized_pnl': 0,
                    'pnl_pct': 0,
                    'balance': balance,
                    'equity': balance + position_value,
                    'open_positions': 1
                })
        
        elif position == 'LONG' and signal == "SELL":
            # Close LONG
            quantity = 0.01
            position_value = current_price * quantity
            commission = position_value * 0.001
            
            realized_pnl = (current_price - entry_price) * quantity - commission * 2
            balance += (position_value - commission)
            
            trades.append({
                'entry': entry_price,
                'exit': current_price,
                'pnl': realized_pnl
            })
            
            log_rows.append({
                'timestamp': df.iloc[i]['timestamp'],
                'symbol': 'BTCUSDT',
                'action': 'CLOSE',
                'side': 'SHORT',
                'quantity': quantity,
                'fill_price': current_price,
                'fill_value': position_value,
                'commission': commission,
                'slippage': 0,
                'realized_pnl': realized_pnl,
                'pnl_pct': (realized_pnl / (entry_price * quantity)) * 100,
                'balance': balance,
                'equity': balance,
                'open_positions': 0
            })
            
            position = None
            entry_price = 0
    
    # Calculate metrics
    total_trades = len(trades)
    winning_trades = sum(1 for t in trades if t['pnl'] > 0)
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    log_df = pd.DataFrame(log_rows)
    
    if verbose:
        print(f"      Final balance: ${balance:.2f}")
        print(f"      Trades: {total_trades}, Win rate: {win_rate:.1f}%")
    
    return {
        'final_balance': balance,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'trades': trades,
        'log_df': log_df
    }


def _run_paper_simulation(
    df: pd.DataFrame,
    starting_balance: float,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Run paper trading simulation using ExecutionEngine + PaperTrader.
    
    Returns dictionary with final_balance, total_trades, win_rate, log_df.
    """
    # Add indicators
    df = add_indicators(df.copy())
    
    # Initialize paper trader (no logging to file)
    paper_trader = PaperTrader(
        starting_balance=starting_balance,
        commission_rate=0.001,
        slippage=0.0,
        log_trades=False
    )
    
    # Initialize execution engine
    exec_engine = ExecutionEngine(
        execution_mode='paper',
        paper_trader=paper_trader
    )
    
    # Track log manually
    log_rows = []
    
    # INIT row
    log_rows.append({
        'timestamp': df.iloc[0]['timestamp'],
        'symbol': 'BTCUSDT',
        'action': 'INIT',
        'side': '',
        'quantity': 0,
        'fill_price': 0,
        'fill_value': 0,
        'commission': 0,
        'slippage': 0,
        'realized_pnl': 0,
        'pnl_pct': 0,
        'balance': starting_balance,
        'equity': starting_balance,
        'open_positions': 0
    })
    
    position_open = False
    entry_info = None
    
    # Walk through candles
    for i in range(50, len(df)):
        window = df.iloc[:i+1].copy()
        signal = generate_signal(window)
        current_price = df.iloc[i]['close']
        
        if not position_open and signal == "BUY":
            # Generate order
            order_req = OrderRequest(
                symbol="BTCUSDT",
                side=OrderSide.LONG,
                order_type=OrderType.MARKET,
                quantity=0.01  # Fixed for testing
            )
            
            # Submit order
            result = exec_engine.submit_order(order_req, current_price)
            
            if result.success:
                position_open = True
                entry_info = {
                    'price': current_price,
                    'quantity': 0.01
                }
                
                # Log OPEN
                log_rows.append({
                    'timestamp': df.iloc[i]['timestamp'],
                    'symbol': 'BTCUSDT',
                    'action': 'OPEN',
                    'side': 'LONG',
                    'quantity': result.fill.quantity,
                    'fill_price': result.fill.fill_price,
                    'fill_value': result.fill.fill_value,
                    'commission': result.fill.commission,
                    'slippage': result.fill.slippage,
                    'realized_pnl': 0,
                    'pnl_pct': 0,
                    'balance': paper_trader.balance,
                    'equity': paper_trader.get_equity(),
                    'open_positions': len(paper_trader.positions)
                })
        
        elif position_open and signal == "SELL":
            # Close position
            order_req = OrderRequest(
                symbol="BTCUSDT",
                side=OrderSide.SHORT,
                order_type=OrderType.MARKET,
                quantity=0.01
            )
            
            result = exec_engine.submit_order(order_req, current_price)
            
            if result.success:
                # Get realized PnL from most recent closed trade
                realized_pnl = 0
                if paper_trader.closed_trades:
                    realized_pnl = paper_trader.closed_trades[-1]['realized_pnl']
                
                log_rows.append({
                    'timestamp': df.iloc[i]['timestamp'],
                    'symbol': 'BTCUSDT',
                    'action': 'CLOSE',
                    'side': 'SHORT',
                    'quantity': result.fill.quantity,
                    'fill_price': result.fill.fill_price,
                    'fill_value': result.fill.fill_value,
                    'commission': result.fill.commission,
                    'slippage': result.fill.slippage,
                    'realized_pnl': realized_pnl,
                    'pnl_pct': (realized_pnl / (entry_info['price'] * entry_info['quantity'])) * 100 if entry_info else 0,
                    'balance': paper_trader.balance,
                    'equity': paper_trader.get_equity(),
                    'open_positions': len(paper_trader.positions)
                })
                
                position_open = False
                entry_info = None
    
    # Get final metrics
    perf = paper_trader.get_performance_summary()
    log_df = pd.DataFrame(log_rows)
    
    if verbose:
        print(f"      Final balance: ${perf['current_balance']:.2f}")
        print(f"      Trades: {perf['total_trades']}, Win rate: {perf['win_rate']:.1f}%")
    
    return {
        'final_balance': perf['current_balance'],
        'total_trades': perf['total_trades'],
        'win_rate': perf['win_rate'],
        'log_df': log_df
    }


def run_safety_suite():
    """
    Run complete safety suite with all validation checks.
    
    Includes:
    1. Invariant unit tests on synthetic logs
    2. Differential backtest vs paper consistency test
    3. Comprehensive summary report
    
    Exits with status code 0 if all checks pass, 1 if any fail.
    """
    print("\n" + "="*70)
    print(" "*20 + "SAFETY SUITE - Module 20")
    print("="*70)
    print("\nRunning comprehensive validation checks before live trading...\n")
    
    failed_checks = []
    passed_checks = []
    
    # Test 1: Invariant checks on happy path
    print("[TEST 1] Invariant checks on valid data...")
    try:
        _test_happy_path_invariants()
        passed_checks.append("Happy path invariants")
        print("  PASSED\n")
    except Exception as e:
        failed_checks.append(("Happy path invariants", str(e)))
        print(f"  FAILED: {e}\n")
    
    # Test 2: Invariant checks on broken data
    print("[TEST 2] Invariant detection of broken accounting...")
    try:
        _test_broken_accounting_detection()
        passed_checks.append("Broken accounting detection")
        print("  PASSED\n")
    except Exception as e:
        failed_checks.append(("Broken accounting detection", str(e)))
        print(f"  FAILED: {e}\n")
    
    # Test 3: Risk invariant checks
    print("[TEST 3] Risk limit validation...")
    try:
        _test_risk_invariants()
        passed_checks.append("Risk limit validation")
        print("  PASSED\n")
    except Exception as e:
        failed_checks.append(("Risk limit validation", str(e)))
        print(f"  FAILED: {e}\n")
    
    # Test 4: Differential consistency test
    print("[TEST 4] Differential backtest vs paper consistency...")
    try:
        run_backtest_vs_paper_consistency_test(
            num_candles=150,
            starting_balance=10000.0,
            tolerance_pct=1.0,
            verbose=True
        )
        passed_checks.append("Differential consistency")
        print()
    except Exception as e:
        failed_checks.append(("Differential consistency", str(e)))
        print(f"\n✗ FAILED: {e}\n")
    
    # Test 5: Safety monitor and kill switch (MODULE 24)
    print("[TEST 5] Safety monitor and kill switch...")
    try:
        _test_safety_monitor()
        passed_checks.append("Safety monitor and kill switch")
        print("  PASSED\n")
    except Exception as e:
        failed_checks.append(("Safety monitor and kill switch", str(e)))
        print(f"  FAILED: {e}\n")
    
    # Final summary
    print("\n" + "="*70)
    print("SAFETY SUITE SUMMARY")
    print("="*70)
    print(f"\nPassed: {len(passed_checks)}/{len(passed_checks) + len(failed_checks)} checks")
    
    if passed_checks:
        print("\nPassed checks:")
        for check in passed_checks:
            print(f"  - {check}")
    
    if failed_checks:
        print("\nFailed checks:")
        for check, error in failed_checks:
            print(f"  - {check}")
            print(f"    Error: {error[:100]}...")
        
        print("\n" + "="*70)
        print("SAFETY SUITE FAILED - DO NOT ENABLE LIVE TRADING")
        print("="*70)
        sys.exit(1)
    else:
        print("\n" + "="*70)
        print("ALL SAFETY CHECKS PASSED")
        print("="*70)
        print("\nSystem validation complete. Accounting, risk, and execution")
        print("systems are operating within expected parameters.")
        sys.exit(0)


def _test_happy_path_invariants():
    """Test invariants on correctly formatted data."""
    # Create valid log
    log_data = [
        {'balance': 1000.0, 'equity': 1000.0, 'realized_pnl': 0.0, 'action': 'INIT'},
        {'balance': 990.0, 'equity': 1005.0, 'realized_pnl': 0.0, 'action': 'OPEN'},
        {'balance': 1015.0, 'equity': 1015.0, 'realized_pnl': 15.0, 'action': 'CLOSE'},
    ]
    log_df = pd.DataFrame(log_data)
    
    # Should not raise
    invariants.check_accounting_invariants(log_df, starting_balance=1000.0)


def _test_broken_accounting_detection():
    """Test that broken accounting is detected."""
    # Create invalid log (final balance doesn't match starting + PnL)
    log_data = [
        {'balance': 1000.0, 'equity': 1000.0, 'realized_pnl': 0.0, 'action': 'INIT'},
        {'balance': 990.0, 'equity': 1005.0, 'realized_pnl': 0.0, 'action': 'OPEN'},
        {'balance': 1100.0, 'equity': 1100.0, 'realized_pnl': 15.0, 'action': 'CLOSE'},  # Wrong!
    ]
    log_df = pd.DataFrame(log_data)
    
    # Should raise AssertionError
    try:
        invariants.check_accounting_invariants(log_df, starting_balance=1000.0)
        raise RuntimeError("Should have detected broken accounting!")
    except AssertionError:
        pass  # Expected


def _test_risk_invariants():
    """Test risk limit validation."""
    # Create log with valid risk levels
    trades_data = [
        {'action': 'INIT', 'symbol': '', 'equity': 10000.0, 'fill_value': 0.0},
        {'action': 'OPEN', 'symbol': 'BTC', 'equity': 10000.0, 'fill_value': 1000.0},  # 10% of equity
        {'action': 'CLOSE', 'symbol': 'BTC', 'equity': 10050.0, 'fill_value': 1005.0},
    ]
    trades_df = pd.DataFrame(trades_data)
    
    risk_config = {
        'default_risk_per_trade': 0.01,
        'max_exposure': 0.20
    }
    
    # Should not raise
    invariants.check_risk_invariants(trades_df, risk_config)


def _test_safety_monitor():
    """
    Test SafetyMonitor functionality and kill switch.
    
    MODULE 24: Tests global safety limits and emergency shutdown.
    """
    print("\n  Testing safety monitor limits...")
    
    # Create safety limits
    limits = SafetyLimits(
        max_daily_loss_pct=0.05,  # 5%
        max_risk_per_trade_pct=0.02,  # 2%
        max_exposure_pct=0.30,  # 30%
        max_open_trades=3,
        kill_switch_env_var="TEST_KILL_SWITCH_SAFETY_SUITE"
    )
    
    starting_equity = 1000.0
    monitor = SafetyMonitor(limits=limits, starting_equity=starting_equity)
    
    # Test 1: Normal order should pass
    print("    - Testing normal order (should pass)...")
    order = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.LONG,
        order_type=OrderType.MARKET,
        quantity=0.1
    )
    
    try:
        monitor.check_pre_trade(order, risk_amount=10.0, position_value=100.0)
        print("      [OK] Normal order accepted")
    except SafetyViolation:
        raise AssertionError("Normal order should have been accepted")
    
    # Test 2: Excessive risk should be rejected
    print("    - Testing excessive risk (should reject)...")
    try:
        monitor.check_pre_trade(order, risk_amount=50.0, position_value=100.0)  # 5% risk
        raise AssertionError("Excessive risk should have been rejected")
    except SafetyViolation:
        print("      [OK] Excessive risk rejected")
    
    # Test 3: Excessive exposure should be rejected
    print("    - Testing excessive exposure (should reject)...")
    try:
        monitor.check_pre_trade(order, risk_amount=10.0, position_value=500.0)  # 50% exposure
        raise AssertionError("Excessive exposure should have been rejected")
    except SafetyViolation:
        print("      [OK] Excessive exposure rejected")
    
    # Test 4: Too many positions should be rejected
    print("    - Testing max open trades limit...")
    monitor.record_position_open("BTCUSDT", 0.1, 50000.0, OrderSide.LONG)
    monitor.record_position_open("ETHUSDT", 1.0, 3000.0, OrderSide.LONG)
    monitor.record_position_open("SOLUSDT", 10.0, 100.0, OrderSide.LONG)
    
    try:
        monitor.check_pre_trade(
            OrderRequest("BNBUSDT", OrderSide.LONG, OrderType.MARKET, 1.0),
            risk_amount=10.0,
            position_value=100.0
        )
        raise AssertionError("Should have rejected order (max trades reached)")
    except SafetyViolation:
        print("      [OK] Max open trades limit enforced")
    
    # Clear positions for next test
    monitor.record_position_close("BTCUSDT", 50000.0, 0.0)
    monitor.record_position_close("ETHUSDT", 3000.0, 0.0)
    monitor.record_position_close("SOLUSDT", 100.0, 0.0)
    
    # Test 5: Daily loss limit should trip kill switch
    print("    - Testing daily loss limit...")
    # Simulate losing more than 5%
    new_equity = 900.0  # Lost $100 = 10%
    monitor.check_post_trade(new_equity)
    
    if not monitor.kill_switch_engaged():
        raise AssertionError("Daily loss limit should have tripped kill switch")
    print("      [OK] Daily loss limit tripped kill switch")
    
    # Test 6: Kill switch via environment variable
    print("    - Testing environment kill switch...")
    
    # Reset monitor
    monitor2 = SafetyMonitor(limits=limits, starting_equity=starting_equity)
    
    # Set environment variable
    os.environ["TEST_KILL_SWITCH_SAFETY_SUITE"] = "1"
    
    if not monitor2.kill_switch_engaged():
        raise AssertionError("Environment kill switch should be engaged")
    print("      [OK] Environment kill switch detected")
    
    # Clean up
    del os.environ["TEST_KILL_SWITCH_SAFETY_SUITE"]
    
    # Test 7: Kill switch blocks orders
    print("    - Testing kill switch blocks orders...")
    try:
        monitor.check_pre_trade(order, risk_amount=10.0, position_value=100.0)
        raise AssertionError("Kill switch should block all orders")
    except SafetyViolation:
        print("      [OK] Kill switch blocks new orders")
    
    print("\n  All safety monitor tests passed!")


if __name__ == "__main__":
    run_safety_suite()
