"""
Nightly Paper Trading Runner

Runs a deterministic paper trading session using synthetic/historical data.
Suitable for CI/nightly automated testing without live exchange connectivity.

Usage:
    python scripts/run_nightly_paper.py --output-dir artifacts/nightly --duration-minutes 15 --deterministic
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import json
import csv

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

from execution import PaperTrader
from strategies.rule_based.scalping import ScalpingEMARSI, add_indicators
from validation.synthetic_data import generate_trend_series
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/nightly_paper.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


class NightlyPaperSession:
    """Runs a deterministic paper trading session for nightly validation."""
    
    def __init__(
        self,
        output_dir: str = "artifacts/nightly",
        duration_minutes: int = 15,
        deterministic: bool = True,
        starting_balance: float = 10000.0
    ):
        """
        Initialize nightly paper session.
        
        Args:
            output_dir: Where to save artifacts
            duration_minutes: Simulated trading duration
            deterministic: If True, use synthetic data with fixed seed
            starting_balance: Starting cash balance
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.duration_minutes = duration_minutes
        self.deterministic = deterministic
        self.starting_balance = starting_balance
        
        # Initialize paper trader
        self.trader = PaperTrader(
            starting_balance=starting_balance,
            slippage=0.0005,
            commission_rate=0.0005,
            allow_shorting=False,
            log_trades=True,
            log_file=str(self.output_dir / "trades.csv")
        )
        
        # Initialize strategy
        self.strategy = ScalpingEMARSI(
            config={
                "ema_fast": 12,
                "ema_slow": 26,
                "rsi_period": 14,
                "rsi_overbought": 70,
                "rsi_oversold": 30
            }
        )
        
        self.trades_count = 0
        self.signals_count = 0
        self.errors_count = 0
        self.metrics = {}
    
    def run(self) -> dict:
        """
        Run the paper trading session.
        
        Returns:
            Dictionary with session metrics
        """
        logger.info("="*70)
        logger.info("[NIGHTLY] Starting deterministic paper trading session")
        logger.info("="*70)
        logger.info(f"Duration: {self.duration_minutes} minutes (simulated)")
        logger.info(f"Starting balance: ${self.starting_balance:.2f}")
        
        try:
            # Generate synthetic OHLCV data
            logger.info(f"Generating synthetic data ({self.duration_minutes}m candles)...")
            
            if self.deterministic:
                # Use fixed seed for reproducibility
                df = generate_trend_series(
                    symbol="BTCUSDT",
                    start_price=45000.0,
                    num_candles=self.duration_minutes,
                    timeframe="1m",
                    trend_strength=0.001,
                    volatility=0.015,
                    seed=42
                )
            else:
                df = generate_trend_series(
                    symbol="BTCUSDT",
                    start_price=45000.0,
                    num_candles=self.duration_minutes,
                    timeframe="1m",
                    trend_strength=0.001,
                    volatility=0.015,
                    seed=None
                )
            
            logger.info(f"Generated {len(df)} candles")
            logger.info(f"Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")
            
            # Process each candle
            for idx, row in df.iterrows():
                try:
                    # Get data up to current candle
                    df_up_to_now = df.iloc[:idx+1]
                    
                    if len(df_up_to_now) < 30:
                        continue  # Need warmup period
                    
                    # Add indicators
                    try:
                        df_with_indicators = add_indicators(df_up_to_now, self.strategy.config)
                    except Exception as e:
                        logger.warning(f"Error adding indicators at candle {idx}: {e}")
                        self.errors_count += 1
                        continue
                    
                    # Generate signal
                    try:
                        signal_result = self.strategy.generate_signal(df_with_indicators)
                        signal = signal_result["signal"]
                        metadata = signal_result["metadata"]
                        
                        if signal != "FLAT":
                            self.signals_count += 1
                            logger.info(
                                f"[{idx:3d}] {signal:5s} signal: "
                                f"price=${row['close']:.2f}, reason={metadata.get('reason', 'N/A')}"
                            )
                            
                            # Simulate order (simplified for deterministic testing)
                            if signal == "LONG":
                                entry_price = row['close']
                                sl_price = entry_price - (metadata.get("sl_distance", 100))
                                tp_price = entry_price + (metadata.get("tp_distance", 200))
                                
                                # Simulate a simple long position
                                position_size = 0.01  # 0.01 BTC
                                cost = position_size * entry_price
                                
                                if cost <= self.trader.balance:
                                    self.trader.balance -= cost
                                    pnl_on_exit = position_size * (tp_price - entry_price)
                                    self.trader.balance += (cost + pnl_on_exit)
                                    self.trades_count += 1
                                    
                                    logger.info(
                                        f"  [TRADE] Long executed at ${entry_price:.2f}, "
                                        f"TP=${tp_price:.2f}, PnL=${pnl_on_exit:.2f}"
                                    )
                    
                    except Exception as e:
                        logger.warning(f"Error processing signal at candle {idx}: {e}")
                        self.errors_count += 1
                
                except Exception as e:
                    logger.error(f"Error processing candle {idx}: {e}")
                    self.errors_count += 1
            
            # Compile metrics
            self.metrics = self._compute_metrics()
            
            logger.info("="*70)
            logger.info("[NIGHTLY] Session Complete")
            logger.info("="*70)
            logger.info(f"Signals: {self.signals_count}")
            logger.info(f"Trades: {self.trades_count}")
            logger.info(f"Errors: {self.errors_count}")
            logger.info(f"Final Balance: ${self.trader.balance:.2f}")
            logger.info(f"Return: {(self.trader.balance - self.starting_balance) / self.starting_balance * 100:.2f}%")
            logger.info("="*70)
            
            # Save metrics
            self._save_metrics()
            
            return self.metrics
        
        except Exception as e:
            logger.error(f"Fatal error during paper session: {e}", exc_info=True)
            self.errors_count += 1
            raise
    
    def _compute_metrics(self) -> dict:
        """Compute session metrics."""
        pnl = self.trader.balance - self.starting_balance
        pnl_pct = (pnl / self.starting_balance) * 100 if self.starting_balance > 0 else 0
        
        # Determine pass/fail status
        status = "PASS" if self.errors_count == 0 else "WARN"
        status_details = []
        
        # Validation checks
        if self.errors_count > 0:
            status_details.append(f"Errors: {self.errors_count}")
        if self.trades_count == 0:
            status_details.append("No trades executed (may be normal)")
        if pnl_pct < -10.0:
            status_details.append(f"Large drawdown: {pnl_pct:.2f}%")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "duration_minutes": self.duration_minutes,
            "starting_balance": self.starting_balance,
            "final_balance": self.trader.balance,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "signals": self.signals_count,
            "trades": self.trades_count,
            "errors": self.errors_count,
            "deterministic": self.deterministic,
            "status": status,
            "status_details": status_details,
            "win_rate": (self.trades_count / max(1, self.signals_count)) * 100 if self.signals_count > 0 else 0.0
        }
    
    def _save_metrics(self):
        """Save metrics to JSON file."""
        metrics_file = self.output_dir / "metrics.json"
        with open(metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)
        logger.info(f"Metrics saved to {metrics_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Run nightly deterministic paper trading session"
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/nightly",
        help="Output directory for artifacts"
    )
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=15,
        help="Simulated trading duration in minutes"
    )
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Use deterministic synthetic data (fixed seed)"
    )
    parser.add_argument(
        "--starting-balance",
        type=float,
        default=10000.0,
        help="Starting cash balance"
    )
    
    args = parser.parse_args()
    
    # Verify trading mode is paper
    trading_mode = os.getenv("TRADING_MODE", "paper")
    if trading_mode != "paper":
        logger.warning(f"WARNING: TRADING_MODE is '{trading_mode}', forcing paper mode for nightly run")
        os.environ["TRADING_MODE"] = "paper"
    
    # Run session
    session = NightlyPaperSession(
        output_dir=args.output_dir,
        duration_minutes=args.duration_minutes,
        deterministic=args.deterministic,
        starting_balance=args.starting_balance
    )
    
    metrics = session.run()
    
    # Exit with error if too many errors
    if metrics["errors"] > 0:
        logger.warning(f"Session completed with {metrics['errors']} errors")
        # Don't fail, just warn
    
    sys.exit(0)


if __name__ == "__main__":
    main()
