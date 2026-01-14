"""
Configuration-Driven Historical Backtest Runner

Reuses the current live trading setup for historical backtesting:
- Same configuration (symbols, risk, timeframe, strategies)
- Same components (PaperTrader, SafetyMonitor, ExecutionEngine, RiskEngine)
- Cash+equity accounting model
- Kill switch and safety limits
- Flatten-on-shutdown behavior

Usage examples:

    # Run backtest for last week
    python -m backtests.config_backtest --start 2025-12-01 --end 2025-12-08 --interval 1m

    # Run quick test with last 24 hours
    python -m backtests.config_backtest

    # Custom date range with 5m candles
    python -m backtests.config_backtest --start 2025-11-01 --end 2025-11-30 --interval 5m

Output:
    - Backtest performance report printed to console
    - Trade log CSV saved to logs/backtests/config_backtest_{start}_{end}.csv
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import yaml
import pandas as pd
import ccxt
import time

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategies.rule_based.scalping import ScalpingEMARSI, add_indicators
from strategies.profile_loader import StrategyProfileLoader
from risk_management import RiskEngine, RiskConfig
from execution import (
    ExecutionEngine, PaperTrader, OrderType, OrderSide, OrderRequest,
    SafetyMonitor, SafetyLimits
)
from validation.config_validator import validate_all_configs, ConfigValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


class HistoricalDataProvider:
    """
    Historical data provider using CCXT.
    
    Fetches and caches OHLCV data for backtesting.
    """
    
    def __init__(self, exchange_name: str = "binance_us", cache_dir: str = "data/backtest_cache"):
        """
        Initialize historical data provider.
        
        Args:
            exchange_name: Exchange to fetch data from
            cache_dir: Directory for caching historical data
        """
        self.exchange_name = exchange_name
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize CCXT exchange
        exchange_class = getattr(ccxt, exchange_name.replace("_", ""))
        self.exchange = exchange_class({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        
        logger.info(f"HistoricalDataProvider initialized: {exchange_name}")
    
    def _get_cache_path(self, symbol: str, interval: str, start: str, end: str) -> Path:
        """Get cache file path for given parameters."""
        # Convert symbol to filesystem-safe name
        safe_symbol = symbol.replace("/", "")
        filename = f"{safe_symbol}_{interval}_{start}_{end}.csv"
        return self.cache_dir / filename
    
    def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        start_date: datetime,
        end_date: datetime,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candles for given date range.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            interval: Timeframe (e.g., "1m", "5m", "15m")
            start_date: Start datetime
            end_date: End datetime
            use_cache: Whether to use cached data if available
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        # Format dates for cache filename
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        
        cache_path = self._get_cache_path(symbol, interval, start_str, end_str)
        
        # Check cache
        if use_cache and cache_path.exists():
            logger.info(f"[CACHE] Loading cached data: {cache_path.name}")
            df = pd.read_csv(cache_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        
        logger.info(f"[FETCH] Fetching {symbol} {interval} from {start_str} to {end_str}")
        
        # Convert dates to timestamps
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)
        
        # Fetch data in batches
        all_candles = []
        current_ts = start_ts
        batch_size = 1000  # Most exchanges support 1000 candles per request
        
        while current_ts < end_ts:
            try:
                candles = self.exchange.fetch_ohlcv(
                    symbol,
                    timeframe=interval,
                    since=current_ts,
                    limit=batch_size
                )
                
                if not candles:
                    break
                
                # Filter candles within our date range
                filtered = [c for c in candles if start_ts <= c[0] <= end_ts]
                all_candles.extend(filtered)
                
                logger.info(f"[FETCH] Fetched {len(filtered)} candles "
                          f"(total: {len(all_candles)}, "
                          f"date: {datetime.fromtimestamp(candles[-1][0]/1000).strftime('%Y-%m-%d %H:%M')})")
                
                # If we got fewer candles than requested, we've reached the end
                if len(candles) < batch_size:
                    break
                
                # Move to next batch (start from last timestamp + 1ms)
                current_ts = candles[-1][0] + 1
                
                # Respect rate limits
                time.sleep(self.exchange.rateLimit / 1000)
                
            except Exception as e:
                logger.error(f"[FETCH] Error fetching data: {e}")
                break
        
        if not all_candles:
            raise ValueError(f"No data fetched for {symbol} {interval}")
        
        # Convert to DataFrame
        df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Save to cache
        df.to_csv(cache_path, index=False)
        logger.info(f"[CACHE] Saved to cache: {cache_path.name} ({len(df)} candles)")
        
        return df


class ConfigBacktestRunner:
    """
    Configuration-driven backtest runner.
    
    Reuses all live trading components for historical backtesting.
    """
    
    def __init__(
        self,
        config_path: str = "config/live.yaml",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        interval: Optional[str] = None,
        symbols: Optional[List[str]] = None,
        log_suffix: Optional[str] = None,
        use_profiles: bool = False
    ):
        """
        Initialize backtest runner.
        
        Args:
            config_path: Path to live configuration file
            start_date: Backtest start date (defaults to 24h ago)
            end_date: Backtest end date (defaults to now)
            interval: Candle interval (overrides config, optional)
            symbols: Symbol list (overrides config, optional)
            log_suffix: Optional suffix for log filename (for optimization runs)
            use_profiles: If True, load per-symbol strategy profiles (Module 31)
        """
        # Validate all configs
        try:
            self.all_configs = validate_all_configs()
        except ConfigValidationError as e:
            logger.critical(f"Configuration validation failed: {e}")
            raise
        
        # Load config
        self.config = self._load_config(config_path)
        self.trading_mode_config = self.all_configs["trading_mode"]
        
        # Set date range (default to last 24 hours for quick testing)
        self.end_date = end_date or datetime.now()
        self.start_date = start_date or (self.end_date - timedelta(days=1))
        
        # Set interval (from arg or config)
        self.interval = interval or self.config.get("timeframe", "1m")
        
        # Get symbols from config or override
        self.symbols = symbols or self.config.get("symbols", ["BTCUSDT"])
        
        # Store log suffix for optimizer runs
        self.log_suffix = log_suffix
        
        # Store profile usage flag
        self.use_profiles = use_profiles
        
        # Initialize components (will be set up in run())
        self.data_provider: Optional[HistoricalDataProvider] = None
        self.strategy: Optional[ScalpingEMARSI] = None
        self.risk_engine: Optional[RiskEngine] = None
        self.execution_engine: Optional[ExecutionEngine] = None
        self.safety_monitor: Optional[SafetyMonitor] = None
        self.paper_trader: Optional[PaperTrader] = None
        
        # Statistics
        self.candles_processed = 0
        self.signals_generated = 0
        self.orders_submitted = 0
        
        logger.info(f"ConfigBacktestRunner initialized")
        logger.info(f"  Date range: {self.start_date.strftime('%Y-%m-%d %H:%M')} to "
                   f"{self.end_date.strftime('%Y-%m-%d %H:%M')}")
        logger.info(f"  Symbols: {self.symbols}")
        logger.info(f"  Interval: {self.interval}")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        config_file = Path(config_path)
        
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"Loaded config from {config_path}")
        return config
    
    def _get_latest_price(self, symbol: str, price_data: Dict[str, float]) -> float:
        """
        Get the latest market price for a symbol.
        
        Used for closing positions at end of backtest.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            price_data: Dictionary of symbol -> latest price
            
        Returns:
            Latest close price
        """
        if symbol not in price_data:
            raise ValueError(f"No price data available for {symbol}")
        return price_data[symbol]
    
    def _process_candle(
        self,
        symbol: str,
        candle: Dict[str, Any],
        df_history: pd.DataFrame
    ):
        """
        Process a single candle through the strategy pipeline.
        
        Args:
            symbol: Trading pair
            candle: Current candle data
            df_history: Historical data up to current candle (for indicators)
        """
        self.candles_processed += 1
        
        # Add indicators to historical data
        try:
            df_with_indicators = add_indicators(
                df_history,
                self.strategy.config if hasattr(self.strategy, 'config') else None
            )
        except Exception as e:
            logger.error(f"[{symbol}] Error adding indicators: {e}")
            return
        
        # Generate signal
        try:
            signal_result = self.strategy.generate_signal(df_with_indicators)
            signal = signal_result["signal"]
            metadata = signal_result["metadata"]
            
            if signal == "FLAT":
                return
            
            # We have a LONG or SHORT signal!
            self.signals_generated += 1
            
            logger.debug(f"[{symbol}] [{signal}] SIGNAL at {candle['timestamp']}")
            
            # Apply risk management
            if signal in ["LONG", "SHORT"]:
                entry_price = metadata.get("entry_price")
                sl_distance = metadata.get("sl_distance")
                tp_distance = metadata.get("tp_distance")
                
                if entry_price and sl_distance and tp_distance:
                    # Calculate SL/TP prices
                    if signal == "LONG":
                        sl_price = entry_price - sl_distance
                        tp_price = entry_price + tp_distance
                    else:  # SHORT
                        sl_price = entry_price + sl_distance
                        tp_price = entry_price - tp_distance
                    
                    # Apply risk engine
                    try:
                        current_equity = self.execution_engine.get_equity()
                        
                        order = self.risk_engine.apply_risk_to_signal(
                            signal=signal,
                            equity=current_equity,
                            entry_price=entry_price,
                            stop_loss_price=sl_price,
                            take_profit_price=tp_price
                        )
                        
                        if order:
                            # Add symbol to order (critical)
                            order['symbol'] = symbol
                            
                            # Check kill switch
                            if self.safety_monitor and self.safety_monitor.kill_switch_engaged():
                                logger.warning(f"[{symbol}] KILL SWITCH - Order blocked")
                                return
                            
                            # Create and submit order
                            order_request = self.execution_engine.create_order_from_risk_output(
                                risk_output=order,
                                strategy_name=self.config['strategy']['type']
                            )
                            
                            # Add metadata
                            order_request.metadata = order_request.metadata or {}
                            order_request.metadata['risk_usd'] = order['risk_usd']
                            order_request.metadata['position_value_usd'] = order['position_value_usd']
                            
                            result = self.execution_engine.submit_order(
                                order=order_request,
                                current_price=candle['close']
                            )
                            
                            if result.success:
                                self.orders_submitted += 1
                                logger.debug(f"[{symbol}] Order filled: {signal} @ ${entry_price:.2f}")
                        
                    except Exception as e:
                        logger.error(f"[{symbol}] Execution error: {e}")
        
        except Exception as e:
            logger.error(f"[{symbol}] Error generating signal: {e}")
    
    def run(self) -> Dict[str, Any]:
        """
        Run the backtest.
        
        Returns:
            Dictionary with backtest results and performance summary
        """
        logger.info("="*60)
        logger.info("STARTING CONFIGURATION-DRIVEN BACKTEST")
        logger.info("="*60)
        logger.info(f"Period: {self.start_date.strftime('%Y-%m-%d %H:%M')} to "
                   f"{self.end_date.strftime('%Y-%m-%d %H:%M')}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Interval: {self.interval}")
        logger.info("="*60)
        
        # Initialize historical data provider
        exchange_name = self.config.get("exchange", "binance_us")
        self.data_provider = HistoricalDataProvider(exchange_name=exchange_name)
        
        # Initialize strategy with profile support (Module 31)
        symbol = self.symbols[0]  # Use first symbol for strategy params
        strategy_type = self.config['strategy']['type']
        
        if self.use_profiles:
            # Try to load profile
            profile_loader = StrategyProfileLoader()
            profile_params = profile_loader.load_profile(symbol, strategy_type)
            
            if profile_params:
                logger.info(f"[OK] Using strategy profile for {symbol}")
                logger.info(f"     Profile params: {profile_params}")
                self.strategy = ScalpingEMARSI(config=profile_params)
            else:
                # Fall back to config
                strategy_params = self.config.get("strategy", {}).get("params", {})
                logger.info(f"[INFO] No profile for {symbol}, using config params")
                if strategy_params:
                    logger.info(f"       Config params: {strategy_params}")
                self.strategy = ScalpingEMARSI(config=strategy_params)
        else:
            # Use config params (default behavior)
            strategy_params = self.config.get("strategy", {}).get("params", {})
            self.strategy = ScalpingEMARSI(config=strategy_params)
        
        logger.info(f"[OK] Strategy: {strategy_type}")
        
        # Initialize risk engine
        risk_config_file = self.config.get("risk", {}).get("config_file", "config/risk.json")
        risk_config = RiskConfig.from_file(Path(risk_config_file))
        self.risk_engine = RiskEngine(risk_config)
        logger.info(f"[OK] Risk engine: {risk_config_file}")
        
        # Load raw risk config for trailing stop settings
        with open(risk_config_file, 'r') as f:
            import json
            self.risk_config_raw = json.load(f)
        
        # Initialize execution engine with paper trader
        execution_config = self.config.get("execution", {})
        starting_balance = execution_config.get("starting_balance", 10000.0)
        
        # Create log file path
        start_str = self.start_date.strftime("%Y%m%d")
        end_str = self.end_date.strftime("%Y%m%d")
        
        # Add optional suffix for optimizer runs
        if self.log_suffix:
            log_file = f"logs/backtests/config_backtest_{start_str}_{end_str}_{self.log_suffix}.csv"
        else:
            log_file = f"logs/backtests/config_backtest_{start_str}_{end_str}.csv"
        
        self.paper_trader = PaperTrader(
            starting_balance=starting_balance,
            slippage=execution_config.get("slippage", 0.0005),
            commission_rate=execution_config.get("commission_rate", 0.0005),
            allow_shorting=execution_config.get("allow_shorting", True),
            log_trades=True,
            log_file=log_file
        )
        
        # Configure trailing stop from risk config
        self.paper_trader.set_risk_config(self.risk_config_raw)
        
        # Initialize safety monitor
        kill_switch_var = self.trading_mode_config.get("kill_switch_env_var", "CRYPTOBOT_KILL_SWITCH")
        safety_limits = SafetyLimits(
            max_daily_loss_pct=self.trading_mode_config["max_daily_loss_pct"],
            max_risk_per_trade_pct=self.trading_mode_config["max_risk_per_trade_pct"],
            max_exposure_pct=self.trading_mode_config["max_exposure_pct"],
            max_open_trades=self.trading_mode_config["max_open_trades"],
            kill_switch_env_var=kill_switch_var
        )
        
        self.safety_monitor = SafetyMonitor(
            limits=safety_limits,
            starting_equity=starting_balance
        )
        
        self.execution_engine = ExecutionEngine(
            execution_mode="paper",
            paper_trader=self.paper_trader,
            safety_monitor=self.safety_monitor
        )
        
        logger.info(f"[OK] Execution: Paper trading (balance: ${starting_balance:.2f})")
        logger.info(f"[OK] Safety: Max loss {safety_limits.max_daily_loss_pct*100:.1f}%, "
                   f"Max positions {safety_limits.max_open_trades}")
        logger.info(f"[OK] Trade log: {log_file}")
        logger.info("="*60)
        
        # Fetch historical data for all symbols
        symbol_data: Dict[str, pd.DataFrame] = {}
        
        for symbol in self.symbols:
            # Convert symbol format (BTCUSDT -> BTC/USDT for CCXT)
            ccxt_symbol = f"{symbol[:-4]}/{symbol[-4:]}" if "/" not in symbol else symbol
            
            try:
                df = self.data_provider.fetch_ohlcv(
                    symbol=ccxt_symbol,
                    interval=self.interval,
                    start_date=self.start_date,
                    end_date=self.end_date
                )
                
                # Store with original symbol format (for consistency with live trading)
                symbol_data[symbol] = df
                logger.info(f"[OK] {symbol}: {len(df)} candles loaded")
                
            except Exception as e:
                logger.error(f"[ERROR] Failed to fetch data for {symbol}: {e}")
        
        if not symbol_data:
            raise ValueError("No data fetched for any symbol")
        
        logger.info("="*60)
        logger.info("RUNNING BACKTEST")
        logger.info("="*60)
        
        # Create unified timeline (all timestamps across all symbols)
        all_timestamps = set()
        for df in symbol_data.values():
            all_timestamps.update(df['timestamp'].tolist())
        
        sorted_timestamps = sorted(all_timestamps)
        logger.info(f"Processing {len(sorted_timestamps)} unique timestamps...")
        
        # Track latest prices for position closing
        latest_prices: Dict[str, float] = {}
        
        # Process candles chronologically
        for i, timestamp in enumerate(sorted_timestamps):
            # Process each symbol's candle at this timestamp
            for symbol, df in symbol_data.items():
                # Get candle at this timestamp
                candle_rows = df[df['timestamp'] == timestamp]
                
                if candle_rows.empty:
                    continue
                
                candle_row = candle_rows.iloc[0]
                
                # Update latest price
                latest_prices[symbol] = float(candle_row['close'])
                
                # Build candle dict
                candle = {
                    'symbol': symbol,
                    'timestamp': timestamp,
                    'open': float(candle_row['open']),
                    'high': float(candle_row['high']),
                    'low': float(candle_row['low']),
                    'close': float(candle_row['close']),
                    'volume': float(candle_row['volume'])
                }
                
                # Get historical data up to this point (for indicators)
                df_history = df[df['timestamp'] <= timestamp].copy()
                
                # Need at least 30 candles for indicators
                if len(df_history) < 30:
                    continue
                
                # Process through strategy pipeline
                self._process_candle(symbol, candle, df_history)
                
                # Update position prices (also applies trailing stop if enabled)
                self.paper_trader.update_positions(latest_prices)
                
                # Check for exit conditions (SL/TP)
                symbols_to_close = self.paper_trader.check_exit_conditions(latest_prices)
                for close_symbol in symbols_to_close:
                    # Close position at current price
                    close_price = latest_prices.get(close_symbol)
                    if close_price:
                        # Determine close side (opposite of position side)
                        position = self.paper_trader.positions.get(close_symbol)
                        if position:
                            if position.side in [OrderSide.LONG, OrderSide.BUY]:
                                close_side = OrderSide.SELL
                            else:
                                close_side = OrderSide.BUY
                            
                            # Create close order
                            close_order = OrderRequest(
                                symbol=close_symbol,
                                side=close_side,
                                quantity=position.quantity,
                                order_type=OrderType.MARKET,
                                strategy_name="EXIT_SL_TP"
                            )
                            
                            # Submit close order
                            self.execution_engine.submit_order(
                                order=close_order,
                                current_price=close_price
                            )
            
            # Periodic progress update
            if (i + 1) % 100 == 0:
                progress = (i + 1) / len(sorted_timestamps) * 100
                logger.info(f"Progress: {progress:.1f}% ({i+1}/{len(sorted_timestamps)} timestamps)")
        
        logger.info("="*60)
        logger.info("BACKTEST COMPLETE - FLATTENING POSITIONS")
        logger.info("="*60)
        
        # Flatten all open positions at end of backtest
        open_positions = self.paper_trader.get_open_positions()
        if open_positions:
            logger.info(f"Closing {len(open_positions)} open positions...")
            try:
                self.paper_trader.close_all_positions(
                    lambda symbol: self._get_latest_price(symbol, latest_prices)
                )
                logger.info("[OK] All positions flattened")
            except Exception as e:
                logger.error(f"[ERROR] Error flattening positions: {e}")
        
        # Get performance summary
        performance = self.execution_engine.get_performance_summary()
        
        logger.info("="*60)
        logger.info("BACKTEST RESULTS")
        logger.info("="*60)
        logger.info(f"Period: {self.start_date.strftime('%Y-%m-%d %H:%M')} to "
                   f"{self.end_date.strftime('%Y-%m-%d %H:%M')}")
        logger.info(f"Candles processed: {self.candles_processed}")
        logger.info(f"Signals generated: {self.signals_generated}")
        logger.info(f"Orders submitted: {self.orders_submitted}")
        logger.info("-"*60)
        logger.info(f"Starting balance:  ${performance['starting_balance']:.2f}")
        logger.info(f"Final balance:     ${performance['current_balance']:.2f}")
        logger.info(f"Final equity:      ${performance['equity']:.2f}")
        logger.info(f"Realized PnL:      ${performance['realized_pnl']:+.2f}")
        logger.info(f"Total return:      {performance['total_return_pct']:+.2f}%")
        logger.info("-"*60)
        logger.info(f"Total trades:      {performance['total_trades']}")
        logger.info(f"Winning trades:    {performance['winning_trades']}")
        logger.info(f"Losing trades:     {performance['losing_trades']}")
        logger.info(f"Win rate:          {performance['win_rate']:.1f}%")
        logger.info("-"*60)
        
        # Max drawdown from safety monitor
        if self.safety_monitor:
            status = self.safety_monitor.get_status()
            peak_equity = status.get('peak_equity', 0)  # Use .get() to avoid KeyError
            if peak_equity > 0:
                max_dd_pct = (peak_equity - performance['equity']) / peak_equity * 100
                logger.info(f"Peak equity:       ${peak_equity:.2f}")
                logger.info(f"Max drawdown:      {max_dd_pct:.2f}%")
                logger.info("-"*60)
        
        logger.info(f"Trade log saved:   {log_file}")
        logger.info("="*60)
        
        # Return results
        results = {
            "config": {
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat(),
                "interval": self.interval,
                "symbols": self.symbols,
                "starting_balance": starting_balance
            },
            "statistics": {
                "candles_processed": self.candles_processed,
                "signals_generated": self.signals_generated,
                "orders_submitted": self.orders_submitted
            },
            "performance": performance,
            "log_file": log_file
        }
        
        return results


def run_config_backtest(
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: Optional[str] = None,
    config_path: str = "config/live.yaml",
    symbols: Optional[List[str]] = None,
    log_suffix: Optional[str] = None,
    use_profiles: bool = False
) -> Path:
    """
    Run configuration-driven backtest (programmatic API).
    
    Args:
        start: Start date (YYYY-MM-DD format, defaults to 24h ago)
        end: End date (YYYY-MM-DD format, defaults to now)
        interval: Candle interval (defaults to config value)
        config_path: Path to configuration file
        symbols: Optional list of symbols (overrides config)
        log_suffix: Optional suffix for log filename (for optimization runs)
        use_profiles: If True, load per-symbol strategy profiles (Module 31)
        
    Returns:
        Path to the generated trade log CSV file
    """
    # Parse dates
    start_date = datetime.strptime(start, "%Y-%m-%d") if start else None
    end_date = datetime.strptime(end, "%Y-%m-%d") if end else None
    
    # Create and run backtest
    runner = ConfigBacktestRunner(
        config_path=config_path,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        symbols=symbols,
        log_suffix=log_suffix,
        use_profiles=use_profiles
    )
    
    results = runner.run()
    
    # Return log file path
    return Path(results["log_file"])


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Configuration-driven historical backtest runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run backtest for specific date range
  python -m backtests.config_backtest --start 2025-12-01 --end 2025-12-08 --interval 1m

  # Run quick test with last 24 hours (default)
  python -m backtests.config_backtest

  # Custom interval
  python -m backtests.config_backtest --start 2025-11-01 --end 2025-11-30 --interval 5m
        """
    )
    
    parser.add_argument(
        "--start",
        type=str,
        help="Start date (YYYY-MM-DD format, default: 24h ago)"
    )
    
    parser.add_argument(
        "--end",
        type=str,
        help="End date (YYYY-MM-DD format, default: now)"
    )
    
    parser.add_argument(
        "--interval",
        type=str,
        help="Candle interval (e.g., 1m, 5m, 15m, default: from config)"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config/live.yaml",
        help="Path to configuration file (default: config/live.yaml)"
    )
    
    parser.add_argument(
        "--use-profiles",
        action="store_true",
        help="Load per-symbol strategy profiles from config/strategy_profiles/ (Module 31)"
    )
    
    args = parser.parse_args()
    
    try:
        run_config_backtest(
            start=args.start,
            end=args.end,
            interval=args.interval,
            config_path=args.config,
            use_profiles=args.use_profiles
        )
    except KeyboardInterrupt:
        logger.info("\nBacktest interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
