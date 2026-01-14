"""
MODULE 16 + 18 + 19 + 24: Live Trading Runtime

Async entrypoint for live market data streaming and strategy execution.

MODULE 16: WebSocket data streaming with async runtime
MODULE 18: ExecutionEngine with PaperTrader for virtual order execution
MODULE 19: Session-based logging and paper-trading defaults
MODULE 24: Multi-mode support (monitor/paper/dry_run/live) with safety limits

Usage:
    python run_live.py

    After session ends, generate report with:
    python analytics/paper_report.py --log-file <path_to_log> --group-by-symbol
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import yaml

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

from data_feed.live import StreamRouter
from strategies.rule_based.scalping import ScalpingEMARSI, add_indicators
from strategies.profile_loader import StrategyProfileLoader
from risk_management import RiskEngine, RiskConfig
from execution import (
    ExecutionEngine, PaperTrader, OrderType,
    BinanceClient, SafetyMonitor, SafetyLimits
)
from execution.live_trading_gate import (
    check_live_trading_gate, log_trading_mode_status,
    LiveTradingGateError
)
from validation.config_validator import validate_all_configs, ConfigValidationError


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/live_runtime.log', mode='a')
    ]
)

logger = logging.getLogger(__name__)


class LiveTradingRuntime:
    """
    Live trading runtime coordinator.
    
    Manages:
    - WebSocket data streams
    - Strategy execution
    - Risk management
    - Multi-mode execution (monitor/paper/dry_run/live) (Module 24)
    - Safety monitoring and kill switch (Module 24)
    """
    
    def __init__(self, config_path: str = "config/live.yaml"):
        """
        Initialize live trading runtime.
        
        Args:
            config_path: Path to live configuration file
        """
        # CRITICAL: Check live trading gate FIRST
        is_live_enabled, actual_mode, reason = check_live_trading_gate()
        log_trading_mode_status(is_live_enabled, actual_mode, reason)
        
        # Validate all configs before starting
        try:
            self.all_configs = validate_all_configs()
        except ConfigValidationError as e:
            logger.critical(f"Configuration validation failed: {e}")
            raise
        
        self.config = self._load_config(config_path)
        self.trading_mode_config = self.all_configs["trading_mode"]
        
        # OVERRIDE trading mode with gate-checked mode for safety
        config_requested_mode = self.trading_mode_config["mode"]
        if config_requested_mode != actual_mode:
            logger.warning(
                f"Trading mode override: config requested '{config_requested_mode}' "
                f"but safety gate enforcing '{actual_mode}'"
            )
        self.trading_mode = actual_mode
        
        # Initialize components
        self.router: Optional[StreamRouter] = None
        self.strategy: Optional[ScalpingEMARSI] = None
        self.risk_engine: Optional[RiskEngine] = None
        self.execution_engine: Optional[ExecutionEngine] = None
        self.safety_monitor: Optional[SafetyMonitor] = None
        
        # Trading state
        self.running = False
        self.signals_generated = 0
        self.candles_processed = 0
        self.orders_submitted = 0
        
        logger.info(f"Initialized LiveTradingRuntime with config from {config_path}")
        logger.info(f"Trading mode (gate-enforced): {self.trading_mode.upper()}")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        config_file = Path(config_path)
        
        if not config_file.exists():
            logger.warning(f"Config file {config_path} not found, using defaults")
            return self._get_default_config()
        
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded config from {config_path}")
            return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "exchange": "binance",
            "symbols": ["BTCUSDT", "SOLUSDT"],
            "timeframe": "1m",
            "reconnect_delay": 3,
            "max_retries": 5,
            "heartbeat": 30,
            "strategy": {
                "type": "scalping_ema_rsi",
                "params": {}
            },
            "risk": {
                "config_file": "config/risk.json"
            }
        }
    
    def _get_latest_price(self, symbol: str) -> float:
        """
        Get the latest market price for a symbol.
        
        Used for closing positions on shutdown.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            
        Returns:
            Latest close price from the most recent candle
            
        Raises:
            ValueError: If no price data is available
        """
        if not self.router:
            raise ValueError(f"StreamRouter not initialized, cannot get price for {symbol}")
        
        candle = self.router.get_latest_candle(symbol)
        if not candle:
            raise ValueError(f"No candle data available for {symbol}")
        
        return candle['close']
    
    async def _on_candle_update(self, candle: Dict[str, Any]):
        """
        Handle incoming candle data.
        
        Args:
            candle: Normalized candle dict from StreamRouter
        """
        symbol = candle["symbol"]
        is_closed = candle.get("is_closed", False)
        
        # Only process closed candles for strategy signals
        if not is_closed:
            return
        
        self.candles_processed += 1
        
        logger.info(f"[{symbol}] New candle closed: "
                   f"O={candle['open']:.2f} H={candle['high']:.2f} "
                   f"L={candle['low']:.2f} C={candle['close']:.2f} "
                   f"V={candle['volume']:.0f}")
        
        # Get historical data for strategy
        df = self.router.get_dataframe(symbol, n=100)
        
        if df is None or len(df) < 30:
            logger.debug(f"[{symbol}] Insufficient data for strategy ({len(df) if df is not None else 0} candles)")
            return
        
        # Add indicators
        try:
            df_with_indicators = add_indicators(df, self.strategy.config if hasattr(self.strategy, 'config') else None)
        except Exception as e:
            logger.error(f"[{symbol}] Error adding indicators: {e}")
            return
        
        # Generate signal
        try:
            signal_result = self.strategy.generate_signal(df_with_indicators)
            signal = signal_result["signal"]
            metadata = signal_result["metadata"]
            
            if signal == "FLAT":
                logger.debug(f"[{symbol}] FLAT - {metadata.get('reason', 'no setup')}")
                return
            
            # We have a LONG or SHORT signal!
            self.signals_generated += 1
            
            logger.info(f"[{symbol}] [{signal}] SIGNAL DETECTED!")
            logger.info(f"  Metadata: {metadata}")
            
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
                        # Get current equity from execution engine
                        if self.execution_engine:
                            current_equity = self.execution_engine.get_equity()
                        else:
                            # Monitor mode: use starting balance
                            current_equity = self.config.get("execution", {}).get("starting_balance", 1000.0)
                        
                        order = self.risk_engine.apply_risk_to_signal(
                            signal=signal,
                            equity=current_equity,
                            entry_price=entry_price,
                            stop_loss_price=sl_price,
                            take_profit_price=tp_price
                        )
                        
                        if order:
                            # Add symbol to order dict (critical - never leave as UNKNOWN)
                            order['symbol'] = symbol
                            
                            logger.info(f"[{symbol}] [OK] Risk-managed order:")
                            logger.info(f"    Side: {order['side']}")
                            logger.info(f"    Entry: ${order['entry_price']:.2f}")
                            logger.info(f"    Position size: {order['position_size']:.6f} units")
                            logger.info(f"    Position value: ${order['position_value_usd']:.2f}")
                            logger.info(f"    Stop-loss: ${order['stop_loss']:.2f}")
                            logger.info(f"    Take-profit: ${order['take_profit']:.2f}")
                            logger.info(f"    Risk (USD): ${order['risk_usd']:.2f}")
                            
                            # Submit order via execution engine (if not in monitor mode)
                            if self.execution_engine:
                                # Check kill switch before submitting
                                if self.safety_monitor and self.safety_monitor.kill_switch_engaged():
                                    logger.critical(f"[{symbol}] [KILL SWITCH] KILL SWITCH ENGAGED - Order blocked!")
                                    return
                                
                                order_request = self.execution_engine.create_order_from_risk_output(
                                    risk_output=order,
                                    strategy_name=self.config['strategy']['type']
                                )
                                
                                # Add metadata for safety checks
                                order_request.metadata = order_request.metadata or {}
                                order_request.metadata['risk_usd'] = order['risk_usd']
                                order_request.metadata['position_value_usd'] = order['position_value_usd']
                                
                                result = self.execution_engine.submit_order(
                                    order=order_request,
                                    current_price=candle['close']
                                )
                                
                                if result.success:
                                    self.orders_submitted += 1
                                    
                                    mode_str = "paper trading" if self.trading_mode == "paper" else "dry-run"
                                    logger.info(f"[{symbol}] [FILLED] ORDER FILLED ({mode_str}):")
                                    
                                    if hasattr(result, 'fill') and result.fill:
                                        logger.info(f"    Fill price: ${result.fill.fill_price:.2f}")
                                        logger.info(f"    Commission: ${result.fill.commission:.4f}")
                                        logger.info(f"    Slippage: ${result.fill.slippage:.4f}")
                                    
                                    if self.trading_mode == "paper":
                                        logger.info(f"    New balance: ${self.execution_engine.get_balance():.2f}")
                                        logger.info(f"    New equity: ${self.execution_engine.get_equity():.2f}")
                                    
                                    # Log safety status
                                    if self.safety_monitor:
                                        status = self.safety_monitor.get_status()
                                        logger.info(f"    Safety: {status['open_positions']}/{status['limits']['max_open_trades']} positions, "
                                                  f"{status['exposure_pct']*100:.1f}% exposure")
                                else:
                                    logger.warning(f"[{symbol}] [REJECTED] ORDER REJECTED: {result.error}")
                            else:
                                # Monitor mode: just log the signal
                                logger.info(f"[{symbol}] [MONITOR] MONITOR MODE - Order not submitted (signal only)")
                        else:
                            logger.warning(f"[{symbol}] Risk engine rejected order")
                    
                    except Exception as e:
                        logger.error(f"[{symbol}] Execution error: {e}", exc_info=True)
        
        except Exception as e:
            logger.error(f"[{symbol}] Error generating signal: {e}", exc_info=True)
    
    async def start(self):
        """Start the live trading runtime."""
        if self.running:
            logger.warning("Runtime already running")
            return
        
        logger.info("="*60)
        logger.info(f"STARTING LIVE TRADING RUNTIME - {self.trading_mode.upper()} MODE")
        logger.info("="*60)
        logger.info(f"Exchange: {self.config['exchange']}")
        logger.info(f"Symbols: {self.config['symbols']}")
        logger.info(f"Timeframe: {self.config['timeframe']}")
        logger.info(f"Strategy: {self.config['strategy']['type']}")
        logger.info("="*60)
        
        # Check kill switch at startup
        kill_switch_var = self.trading_mode_config.get("kill_switch_env_var", "CRYPTOBOT_KILL_SWITCH")
        if os.environ.get(kill_switch_var, "").lower() in ["1", "true", "yes", "on"]:
            logger.critical(f"[KILL SWITCH] KILL SWITCH ENGAGED: {kill_switch_var}={os.environ[kill_switch_var]}")
            logger.critical("Cannot start runtime with kill switch engaged!")
            raise RuntimeError("Kill switch is engaged")
        
        # Warn if in live mode
        if self.trading_mode == "live":
            logger.warning("="*60)
            logger.warning("[WARNING] LIVE MODE ENABLED (DRY-RUN ONLY)")
            logger.warning("="*60)
            logger.warning("Live mode is not yet fully implemented.")
            logger.warning("All orders will be logged but NOT submitted to exchange.")
            logger.warning("This is a DRY-RUN mode for testing purposes only.")
            logger.warning("="*60)
            
            if self.trading_mode_config.get("require_live_confirmation", True):
                logger.warning("Live mode requires manual confirmation.")
                logger.warning("Remove this check when ready for real trading.")
        
        self.running = True
        
        # Initialize strategy with profile support
        symbol = self.config.get("symbols", ["BTCUSDT"])[0]  # Use first symbol for now
        strategy_type = self.config['strategy']['type']
        
        # Try to load profile for this symbol
        profile_loader = StrategyProfileLoader()
        profile_params = profile_loader.load_profile(symbol, strategy_type)
        
        if profile_params:
            logger.info(f"[OK] Using strategy profile for {symbol}")
            logger.info(f"     Profile params: {profile_params}")
            self.strategy = ScalpingEMARSI(config=profile_params)
        else:
            # Fall back to config params
            strategy_params = self.config.get("strategy", {}).get("params", {})
            logger.info(f"[INFO] No profile found for {symbol}, using config params")
            if strategy_params:
                logger.info(f"       Config params: {strategy_params}")
            self.strategy = ScalpingEMARSI(config=strategy_params)
        
        logger.info(f"[OK] Strategy initialized: {strategy_type}")

        
        # Initialize risk engine
        risk_config_file = self.config.get("risk", {}).get("config_file", "config/risk.json")
        risk_config = RiskConfig.from_file(Path(risk_config_file))
        self.risk_engine = RiskEngine(risk_config)
        logger.info(f"[OK] Risk engine initialized from {risk_config_file}")
        
        # Initialize execution based on trading mode
        execution_config = self.config.get("execution", {})
        starting_balance = execution_config.get("starting_balance", 1000.0)
        
        # Initialize safety monitor (for all modes except monitor)
        if self.trading_mode != "monitor":
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
            
            logger.info("="*60)
            logger.info("[SAFETY] SAFETY MONITOR ACTIVE")
            logger.info(f"  Max daily loss: {safety_limits.max_daily_loss_pct*100:.1f}%")
            logger.info(f"  Max risk/trade: {safety_limits.max_risk_per_trade_pct*100:.1f}%")
            logger.info(f"  Max exposure: {safety_limits.max_exposure_pct*100:.1f}%")
            logger.info(f"  Max open trades: {safety_limits.max_open_trades}")
            logger.info(f"  Kill switch var: {kill_switch_var}")
            logger.info("="*60)
        
        if self.trading_mode == "monitor":
            # Monitor mode: No execution engine, only signal generation
            logger.info("="*60)
            logger.info("[MONITOR] MONITOR MODE - Signal generation only")
            logger.info("  No orders will be submitted (monitoring only)")
            logger.info("="*60)
            self.execution_engine = None
        
        elif self.trading_mode == "paper":
            # Paper mode: Use PaperTrader for simulation
            log_file_path = execution_config.get("log_file")
            
            paper_trader = PaperTrader(
                starting_balance=starting_balance,
                slippage=execution_config.get("slippage", 0.0005),
                commission_rate=execution_config.get("commission_rate", 0.0005),
                allow_shorting=execution_config.get("allow_shorting", True),
                log_trades=execution_config.get("log_trades", True),
                log_file=log_file_path
            )
            
            self.execution_engine = ExecutionEngine(
                execution_mode="paper",
                paper_trader=paper_trader,
                safety_monitor=self.safety_monitor
            )
            
            logger.info("="*60)
            logger.info("[PAPER] PAPER TRADING SESSION")
            logger.info(f"  Starting balance: ${starting_balance:.2f}")
            logger.info(f"  Slippage: {paper_trader.slippage*100:.3f}%")
            logger.info(f"  Commission: {paper_trader.commission_rate*100:.3f}%")
            logger.info(f"  Trade log: {paper_trader.log_file}")
            logger.info("="*60)
        
        elif self.trading_mode in ["dry_run", "live"]:
            # Dry-run or live mode: Use BinanceClient (stub for now)
            # Get API keys from environment (should be None for paper/monitor)
            api_key = os.getenv("BINANCE_API_KEY")
            api_secret = os.getenv("BINANCE_API_SECRET")
            
            binance_client = BinanceClient(
                api_key=api_key,
                api_secret=api_secret,
                testnet=True,
                dry_run=True,  # Always dry-run until real API integration
                trading_mode=self.trading_mode  # Pass for safety validation
            )
            
            self.execution_engine = ExecutionEngine(
                execution_mode=self.trading_mode,
                exchange_client=binance_client,
                safety_monitor=self.safety_monitor
            )
            
            logger.info("="*60)
            logger.info(f"[{self.trading_mode.upper()}] {self.trading_mode.upper()} MODE (Binance Client - DRY-RUN)")
            logger.info(f"  Starting equity: ${starting_balance:.2f}")
            logger.info("  [WARNING] No real orders will be submitted (stub implementation)")
            logger.info("="*60)
        
        # Initialize stream router (Module 26: with WebSocket base URL support)
        self.router = StreamRouter(
            exchange=self.config["exchange"],
            symbols=self.config["symbols"],
            timeframe=self.config["timeframe"],
            ws_base_url=self.config.get("ws_base_url"),
            reconnect_delay=self.config.get("reconnect_delay", 3),
            max_retries=self.config.get("max_retries", 5),
            heartbeat_interval=self.config.get("heartbeat", 30)
        )
        
        # Register callback
        self.router.register_callback(self._on_candle_update)
        
        # Start router
        await self.router.start()
        logger.info("[OK] Stream router started")
        
        # Wait for initial data
        logger.info("Waiting for initial market data...")
        for symbol in self.config["symbols"]:
            if await self.router.wait_for_data(symbol, timeout=30.0):
                logger.info(f"[OK] Received data for {symbol}")
            else:
                logger.warning(f"[WARN] No data received for {symbol}")
        
        logger.info("="*60)
        logger.info(f"[OK] LIVE RUNTIME READY ({self.trading_mode.upper()} MODE)")
        logger.info("="*60)
    
    async def stop(self):
        """Stop the live trading runtime."""
        logger.info("Stopping live trading runtime...")
        self.running = False
        
        if self.router:
            await self.router.stop()
        
        # FLATTEN ALL OPEN POSITIONS FOR PAPER TRADING
        if self.execution_engine and hasattr(self.execution_engine, 'paper_trader'):
            paper_trader = self.execution_engine.paper_trader
            if paper_trader and hasattr(paper_trader, 'close_all_positions'):
                open_positions = paper_trader.get_open_positions()
                if open_positions:
                    logger.info("="*60)
                    logger.info("[PAPER] FLATTENING OPEN POSITIONS ON SHUTDOWN")
                    logger.info("="*60)
                    try:
                        paper_trader.close_all_positions(self._get_latest_price)
                        logger.info("[PAPER] All positions successfully flattened")
                    except Exception as e:
                        logger.error(f"[PAPER] Error flattening positions: {e}", exc_info=True)
                    logger.info("="*60)
        
        # Print final performance summary
        if self.execution_engine and self.trading_mode == "paper":
            performance = self.execution_engine.get_performance_summary()
            paper_trader = self.execution_engine.paper_trader
            
            logger.info("="*60)
            logger.info("[REPORT] PAPER TRADING PERFORMANCE SUMMARY")
            logger.info("="*60)
            logger.info(f"  Starting balance: ${performance['starting_balance']:.2f}")
            logger.info(f"  Current balance: ${performance['current_balance']:.2f}")
            logger.info(f"  Equity (balance + positions): ${performance['equity']:.2f}")
            logger.info(f"  Realized PnL: ${performance['realized_pnl']:.2f}")
            logger.info(f"  Total return: {performance['total_return_pct']:.2f}%")
            logger.info(f"  Total trades: {performance['total_trades']}")
            logger.info(f"  Winning trades: {performance['winning_trades']}")
            logger.info(f"  Losing trades: {performance['losing_trades']}")
            logger.info(f"  Win rate: {performance['win_rate']:.1f}%")
            logger.info(f"  Open positions: {len(performance['open_positions'])}")
            logger.info("="*60)
            logger.info("")
            logger.info("[INFO] Generate detailed report with:")
            logger.info(f"   python analytics/paper_report.py --log-file {paper_trader.log_file} --group-by-symbol")
            logger.info("")
        
        # Print safety monitor summary
        if self.safety_monitor:
            status = self.safety_monitor.get_status()
            
            logger.info("="*60)
            logger.info("[SAFETY] SAFETY MONITOR SUMMARY")
            logger.info("="*60)
            logger.info(f"  Kill switch engaged: {status['kill_switch_engaged']}")
            logger.info(f"  Trading halted: {status['trading_halted']}")
            if status['halt_reason']:
                logger.info(f"  Halt reason: {status['halt_reason']}")
            logger.info(f"  Starting equity: ${status['starting_equity']:.2f}")
            logger.info(f"  Current equity: ${status['current_equity']:.2f}")
            logger.info(f"  Daily PnL: ${status['daily_pnl']:+.2f}")
            logger.info(f"  Daily loss: {status['daily_loss_pct']*100:.2f}%")
            logger.info(f"  Open positions: {status['open_positions']}/{status['limits']['max_open_trades']}")
            logger.info(f"  Total exposure: ${status['total_exposure']:.2f} ({status['exposure_pct']*100:.1f}%)")
            logger.info("="*60)
        
        logger.info("="*60)
        logger.info(f"LIVE RUNTIME STOPPED ({self.trading_mode.upper()} MODE)")
        logger.info(f"  Candles processed: {self.candles_processed}")
        logger.info(f"  Signals generated: {self.signals_generated}")
        logger.info(f"  Orders submitted: {self.orders_submitted}")
        logger.info("="*60)
    
    async def run(self):
        """Run the live trading runtime until interrupted."""
        try:
            await self.start()
            
            # Keep running until interrupted
            while self.running:
                await asyncio.sleep(1)
                
                # Periodic status update
                if self.candles_processed > 0 and self.candles_processed % 10 == 0:
                    status = self.router.get_status()
                    logger.debug(f"Status: {status}")
        
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        
        except Exception as e:
            logger.error(f"Runtime error: {e}", exc_info=True)
        
        finally:
            await self.stop()


async def main():
    """Main entry point for live trading runtime."""
    runtime = LiveTradingRuntime()
    await runtime.run()


if __name__ == "__main__":
    asyncio.run(main())
