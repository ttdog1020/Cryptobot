"""
MODULE 8: Live Multi-Symbol Paper-Trading Harness

Runs ETH/USDT, BTC/USDT, SOL/USDT simultaneously on 15m in paper-trading mode.
Suitable for 24/7 operation with robust error handling and consistent USD formatting.

SAFETY: Paper trading mode is enforced. Live trading disabled by default.
"""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

from orchestrator import Orchestrator, ensure_multi_trades_log, ensure_multi_equity_log, log_multi_equity
from bot import BotConfig, create_exchange
from strategy_engine import load_strategy_profile
from execution.live_trading_gate import check_live_trading_gate, log_trading_mode_status


# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Error logging (separate from trade logging)
error_log_file = log_dir / "live_errors.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(error_log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_env():
    """Load environment configuration."""
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)
    elif Path("config.example.env").exists():
        load_dotenv("config.example.env")
    
    # CRITICAL: Check live trading gate
    is_live_enabled, actual_mode, reason = check_live_trading_gate()
    log_trading_mode_status(is_live_enabled, actual_mode, reason)
    
    # Enforce safe mode for run_live_multi.py
    if actual_mode not in ["paper", "monitor"]:
        logger.warning(
            f"run_live_multi.py only supports paper/monitor modes. "
            f"Overriding to paper mode for safety."
        )
        os.environ["TRADING_MODE"] = "paper"


class LiveOrchestrator(Orchestrator):
    """Extended Orchestrator with live trading loop capabilities."""
    
    def __init__(self, starting_balance_per_symbol: float = 5000.0):
        super().__init__(starting_balance_per_symbol)
        # Auto-optimization settings
        self.auto_opt_enabled = os.getenv("AUTO_OPT_ENABLED", "0") == "1"
        self.auto_opt_every_iters = int(os.getenv("AUTO_OPT_CHECK_EVERY_ITERS", "20"))
        self.iteration_counter = 0
        self.last_profiles_mtime = None
        
        if self.auto_opt_enabled:
            logger.info(f"[AUTO_OPT] Auto-optimization enabled, check every {self.auto_opt_every_iters} iterations")
    
    def run_live(self, loop_interval_sec: int = 60, max_iterations: int = None):
        """
        Execute live multi-symbol trading loop.
        
        Args:
            loop_interval_sec: Sleep duration between iterations (default 60s)
            max_iterations: Optional max iterations for testing (default infinite)
        """
        ensure_multi_trades_log()
        ensure_multi_equity_log()
        
        logger.info(f"[LIVE] Starting multi-symbol live loop with {len(self.controllers)} symbols")
        logger.info(f"[LIVE] Loop interval: {loop_interval_sec}s, Max iterations: {max_iterations or 'unlimited'}")
        
        iteration = 0
        while True:
            iteration += 1
            
            if max_iterations is not None and iteration > max_iterations:
                logger.info(f"[LIVE] Reached max_iterations={max_iterations}, exiting")
                break
            
            ts = datetime.now(timezone.utc).isoformat()
            logger.info(f"\n[LIVE] === Iteration {iteration} at {ts} ===")
            
            for controller in self.controllers:
                try:
                    self._tick_symbol(controller)
                    # Log equity after each symbol is processed
                    log_multi_equity(ts, controller.symbol, controller.timeframe, controller.trader.balance)
                except Exception as e:
                    logger.error(
                        f"[LIVE] Error processing {controller.symbol} {controller.timeframe}: {e}",
                        exc_info=True
                    )
                    # Continue with next symbol instead of crashing
                    continue
            
            # Log current balances
            for controller in self.controllers:
                logger.info(
                    f"[LIVE] {controller.symbol:10} | Balance: ${controller.trader.balance:10.2f} | "
                    f"Position: {controller.trader.position_side or 'NONE':5} | "
                    f"Trades: {len(controller.trader.closed_trade_pnls)}"
                )
            
            # Check for auto-optimization trigger
            self.iteration_counter += 1
            if self.auto_opt_enabled and self.iteration_counter % self.auto_opt_every_iters == 0:
                logger.info(f"[AUTO_OPT] Triggering optimization cycle at iteration {self.iteration_counter}")
                self.run_auto_opt_cycle()
            
            logger.info(f"[LIVE] Sleeping for {loop_interval_sec}s...")
            time.sleep(loop_interval_sec)
    
    def _tick_symbol(self, controller):
        """Execute one trading cycle for a symbol."""
        # Fetch latest candles (use last 100 for efficiency)
        df = controller.fetch_data(limit=100)
        if df is None or len(df) < 50:
            logger.warning(
                f"[LIVE] {controller.symbol} {controller.timeframe}: Insufficient data ({len(df) if df is not None else 0} candles)"
            )
            return
        
        # Apply indicators
        from bot import _apply_indicators_with_profile
        df = _apply_indicators_with_profile(df, controller.trader)
        
        # Process the latest bar
        bar_index = len(df) - 1
        if bar_index < 30:
            logger.debug(f"[LIVE] {controller.symbol}: Still in warmup period")
            return
        
        # Execute one cycle
        trades = controller.run_cycle(df, bar_index)
        
        if trades:
            for trade in trades:
                logger.info(
                    f"[LIVE] {controller.symbol} {trade.get('side', '?')}: "
                    f"price={trade.get('price', 0):.2f}, pnl={trade.get('pnl', 0):.2f}"
                )
    
    def run_auto_opt_cycle(self):
        """Run performance snapshot + auto-optimizer, then reload updated profiles."""
        import subprocess
        
        # 1) Generate fresh performance snapshot (quiet mode)
        logger.info("[AUTO_OPT] Running performance report...")
        result_perf = subprocess.run(
            [sys.executable, "-u", "performance_report.py", "--quiet"],
            capture_output=True,
            text=True
        )
        
        if result_perf.returncode != 0:
            logger.error(f"[AUTO_OPT] performance_report failed: {result_perf.stderr.strip()}")
            return
        
        # 2) Run auto_optimizer (uses snapshot + env thresholds)
        logger.info("[AUTO_OPT] Running auto-optimizer...")
        result_opt = subprocess.run(
            [sys.executable, "-u", "auto_optimizer.py"],
            capture_output=True,
            text=True
        )
        
        if result_opt.returncode != 0:
            logger.error(f"[AUTO_OPT] auto_optimizer failed: {result_opt.stderr.strip()}")
            return
        
        logger.info(f"[AUTO_OPT] Optimizer output: {result_opt.stdout.strip()}")
        
        # 3) Reload strategy profiles if changed
        self.reload_strategy_profiles_if_changed()
    
    def reload_strategy_profiles_if_changed(self):
        """Check if strategy_profiles.json changed; if so, reload for all controllers."""
        profiles_file = Path("strategy_profiles.json")
        if not profiles_file.exists():
            logger.warning("[AUTO_OPT] strategy_profiles.json not found, skipping reload")
            return
        
        current_mtime = os.path.getmtime(profiles_file)
        
        if self.last_profiles_mtime is not None and current_mtime == self.last_profiles_mtime:
            logger.info("[AUTO_OPT] No profile changes detected")
            self.last_profiles_mtime = current_mtime
            return
        
        # File changed or first check - reload
        if self.last_profiles_mtime is None:
            logger.info("[AUTO_OPT] First profile check, loading current profiles...")
        else:
            logger.info("[AUTO_OPT] strategy_profiles.json changed, reloading all controllers...")
        
        self.last_profiles_mtime = current_mtime
        
        # Load updated profiles
        import json
        with profiles_file.open("r", encoding="utf-8") as f:
            all_profiles = json.load(f)
        
        # Update each controller
        for controller in self.controllers:
            symbol = controller.symbol
            timeframe = controller.timeframe
            
            if symbol in all_profiles and timeframe in all_profiles[symbol]:
                new_profile = all_profiles[symbol][timeframe]
                controller.update_strategy_profile(new_profile)
                logger.info(f"[AUTO_OPT] Reloaded profile for {symbol} {timeframe} (reason: optimizer update)")
            else:
                logger.warning(f"[AUTO_OPT] No profile found for {symbol} {timeframe} in updated file")


def main(max_iterations: int = None):
    """Main entry point for live trading."""
    load_env()
    
    # Configuration
    config = BotConfig()
    loop_interval = int(os.getenv("LOOP_INTERVAL_SEC", "60"))
    
    logger.info("[LIVE] === CryptoBot Live Multi-Symbol Paper Trading ===")
    logger.info(f"[LIVE] Exchange: {config.exchange_name}")
    logger.info(f"[LIVE] Starting Balance per Symbol: ${config.starting_balance:.2f}")
    logger.info(f"[LIVE] Risk per Trade: {config.risk_per_trade_pct}%")
    
    # Create exchange
    exchange = create_exchange(config)
    
    # Initialize orchestrator
    orchestrator = LiveOrchestrator(starting_balance_per_symbol=config.starting_balance)
    symbols = orchestrator.load_symbols(Path("symbols.json"))
    
    if not symbols:
        logger.error("[LIVE] No symbols loaded from symbols.json, exiting")
        return
    
    orchestrator.initialize_controllers(exchange, symbols)
    
    # Run live loop
    try:
        orchestrator.run_live(loop_interval_sec=loop_interval, max_iterations=max_iterations)
    except KeyboardInterrupt:
        logger.info("[LIVE] Keyboard interrupt received, shutting down gracefully...")
    except Exception as e:
        logger.error(f"[LIVE] Fatal error in live loop: {e}", exc_info=True)
        sys.exit(1)
    
    logger.info("[LIVE] === Live Trading Session Ended ===")
    
    # Print final summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    for controller in orchestrator.controllers:
        summary = controller.get_summary()
        print(f"{controller.symbol:12} | Trades: {summary['total_trades']:3} | "
              f"WR: {summary['win_rate']:5.1f}% | "
              f"PnL: ${summary['total_pnl']:10.2f} | "
              f"Equity: ${summary['final_equity']:10.2f}")
    
    # Overall totals
    total_trades = sum(c.get_summary()['total_trades'] for c in orchestrator.controllers)
    total_pnl = sum(c.get_summary()['total_pnl'] for c in orchestrator.controllers)
    total_equity = sum(c.get_summary()['final_equity'] for c in orchestrator.controllers)
    starting_total = config.starting_balance * len(orchestrator.controllers)
    
    print(f"\nTOTAL: {total_trades} trades | PnL: ${total_pnl:.2f} | "
          f"Equity: ${total_equity:.2f} ({((total_equity/starting_total - 1)*100):.2f}%)")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Allow passing max_iterations as command-line argument for testing
    max_iter = None
    if len(sys.argv) > 1:
        try:
            max_iter = int(sys.argv[1])
        except ValueError:
            logger.error(f"Invalid max_iterations: {sys.argv[1]}")
            sys.exit(1)
    
    main(max_iterations=max_iter)
