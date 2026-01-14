import os
import csv
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

import ccxt
import pandas as pd
from dotenv import load_dotenv

from strategies.macd_rsi_adx import (
    add_indicators_macd_rsi_adx as add_indicators,
    generate_signal_macd_rsi_adx as generate_signal,
)
from data_stream import start_ohlc_stream, get_latest_candles, stop_stream
from strategy_engine import load_strategy_profile
from risk_management import RiskConfig, RiskEngine

LOG_DIR = Path("logs")
TRADES_LOG = LOG_DIR / "trades.csv"
EQUITY_LOG = LOG_DIR / "equity.csv"
RISK_LOG = LOG_DIR / "risk_events.csv"


def ensure_logs_exist():
    LOG_DIR.mkdir(exist_ok=True)
    if not TRADES_LOG.exists():
        with TRADES_LOG.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "side", "price", "size", "pnl", "balance_after", "entry_price", "exit_price", "stop_loss", "take_profit", "atr"])
    if not EQUITY_LOG.exists():
        with EQUITY_LOG.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "equity"])
    if not RISK_LOG.exists():
        with RISK_LOG.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "event", "detail", "equity"])


def _fmt_usd(x):
    """Format USD values consistently with 2 decimals."""
    try:
        return f"{float(x):.2f}"
    except Exception:
        return str(x)


def _fmt_size(x):
    """Higher precision for position size (crypto units)."""
    try:
        return f"{float(x):.8f}"
    except Exception:
        return str(x)


def log_trade(ts, side, price, size, pnl, balance_after, entry_price=None, exit_price=None, stop_loss=None, take_profit=None, atr=None):
    """
    Log a single trade. PnL and balances are stored as 2-decimal USD strings
    to avoid mis-reading (e.g. 32.23 vs 322.3). Sizes use 8-decimal precision.
    """
    with TRADES_LOG.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            ts,
            side,
            _fmt_usd(price),
            _fmt_size(size),
            _fmt_usd(pnl),
            _fmt_usd(balance_after),
            _fmt_usd(entry_price) if entry_price is not None else "",
            _fmt_usd(exit_price) if exit_price is not None else "",
            _fmt_usd(stop_loss) if stop_loss is not None else "",
            _fmt_usd(take_profit) if take_profit is not None else "",
            _fmt_usd(atr) if atr is not None else ""
        ])


def log_equity(ts, equity):
    with EQUITY_LOG.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([ts, f"{equity:.8f}"])


def log_risk_event(ts, event, detail, equity):
    with RISK_LOG.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([ts, event, detail, equity])


load_dotenv()  # Load .env configuration


@dataclass
class BotConfig:
    # exchange fields (keep exchange_name for backwards compatibility)
    exchange: str = os.getenv("EXCHANGE", "kraken")
    exchange_name: str = os.getenv("EXCHANGE", os.getenv("EXCHANGE", "kraken"))
    symbol: str = os.getenv("SYMBOL", "BTC/USD")
    timeframe: str = os.getenv("TIMEFRAME", "1m")

    # Candle and loop settings
    candle_limit: int = int(os.getenv("CANDLE_LIMIT", "500"))
    loop_interval_sec: int = int(os.getenv("LOOP_INTERVAL_SEC", "15"))

    # Trading configuration wired from environment
    starting_balance: float = float(os.getenv("STARTING_BALANCE", "1000.0"))
    risk_per_trade_pct: float = float(os.getenv("RISK_PER_TRADE_PCT", "3.0"))
    max_trades_per_run: int = int(os.getenv("MAX_TRADES_PER_RUN", "1000"))
    max_drawdown_pct: float = float(os.getenv("MAX_DRAWDOWN_PCT", "10.0"))

    # Mode flags
    trader_mode: str = os.getenv("TRADER_MODE", "paper")
    test_mode: bool = os.getenv("TEST_MODE", "0") == "1"

class PaperTrader:
    def __init__(
        self,
        balance: float,
        strategy_profile: Optional[Dict[str, Any]] = None,
        risk_config: Optional[RiskConfig] = None,
    ):
        self.balance = balance
        self.strategy_profile = strategy_profile
        self.position_size = 0.0
        self.entry_price = 0.0
        self.position_side: Optional[str] = None
        self.equity_curve = []
        self.closed_trade_pnls = []
        self.stop_loss: float | None = None
        self.take_profit: float | None = None
        self.current_atr: float | None = None  # Track ATR for current position
        # Track last candle timestamp where a trade (open/close) actually occurred
        self.last_trade_candle_time = None
        # NEW: track last equity value that was written to equity.csv
        self.last_logged_equity: Optional[float] = None
        
        # MODULE 14: Initialize risk engine
        if risk_config is None:
            # Try to load from config/risk.json
            risk_config_path = Path("config") / "risk.json"
            risk_config = RiskConfig.from_file(risk_config_path)
        
        self.risk_engine = RiskEngine(risk_config)
        
        # MODULE 5: Load risk parameters from profile (can override risk_config)
        if strategy_profile:
            self.risk_pct = float(strategy_profile.get("risk_per_trade_pct", risk_config.default_risk_per_trade * 100)) / 100.0
            self.sl_mult = float(strategy_profile.get("sl_atr_mult", risk_config.default_sl_atr_mult))
            self.tp_mult = float(strategy_profile.get("tp_atr_mult", risk_config.default_tp_atr_mult))
            self.min_pos_size = float(strategy_profile.get("min_position_size_usd", risk_config.min_position_size_usd))
        else:
            self.risk_pct = risk_config.default_risk_per_trade
            self.sl_mult = risk_config.default_sl_atr_mult
            self.tp_mult = risk_config.default_tp_atr_mult
            self.min_pos_size = risk_config.min_position_size_usd
            self.min_pos_size = 50.0

    def open_long(self, price: float, risk_pct: float = None, atr: float | None = None):
        if self.position_side == "LONG":
            print("[WARN] Already in LONG position; ignoring new BUY signal.")
            return

        # MODULE 14: Use centralized risk engine for position sizing
        if atr is None or atr <= 0:
            print("[WARN] Invalid ATR, cannot calculate position size. Skipping trade.")
            return
        
        # Get current equity for position sizing
        current_equity = self.balance
        
        # Use risk_pct if provided, otherwise use trader's default
        trade_risk_pct = (risk_pct / 100.0) if risk_pct is not None else self.risk_pct
        
        try:
            # Apply risk management to generate trade order
            order = self.risk_engine.apply_risk_to_signal(
                signal="LONG",
                equity=current_equity,
                entry_price=price,
                atr=atr,
                risk_per_trade=trade_risk_pct,
                sl_mult=self.sl_mult,
                tp_mult=self.tp_mult
            )
            
            if order is None:
                print("[RISK] Trade rejected by risk engine.")
                return
            
            # Extract order details
            self.position_size = order["position_size"]
            self.entry_price = price
            self.position_side = "LONG"
            self.current_atr = atr
            self.stop_loss = order["stop_loss"]
            self.take_profit = order["take_profit"]
            
            print(f"[TRADE] OPEN LONG at {price:.2f}, size={self.position_size:.6f}, "
                  f"SL={self.stop_loss:.2f}, TP={self.take_profit:.2f}, "
                  f"Risk=${order['risk_usd']:.2f}")
            
            ts = datetime.now(timezone.utc).isoformat()
            log_trade(ts, "OPEN_LONG", price, self.position_size, 0.0, self.balance, 
                      entry_price=price, exit_price=None, stop_loss=self.stop_loss, 
                      take_profit=self.take_profit, atr=atr)
        
        except ValueError as e:
            print(f"[RISK] Cannot open position: {e}")
            return

    def close_position(self, price: float):
        if self.position_side is None:
            print("[WARN] No position to close.")
            return

        if self.position_side == "LONG":
            pnl = (price - self.entry_price) * self.position_size
        else:
            pnl = 0.0
        
        # Store exit info before clearing
        entry_price = self.entry_price
        sl = self.stop_loss
        tp = self.take_profit
        atr = self.current_atr
        
        self.balance += pnl
        print(f"[TRADE] CLOSE {self.position_side} at {price:.2f}, "
              f"PnL={pnl:.4f}, balance={self.balance:.4f}")

        ts = datetime.now(timezone.utc).isoformat()
        log_trade(ts, "CLOSE_LONG", price, self.position_size, pnl, self.balance,
                  entry_price=entry_price, exit_price=price, stop_loss=sl, take_profit=tp, atr=atr)

        # record closed trade pnl for summary
        try:
            self.closed_trade_pnls.append(pnl)
        except Exception:
            pass

        # Clear SL/TP
        self.stop_loss = None
        self.take_profit = None
        self.current_atr = None

        self.position_size = 0.0
        self.entry_price = 0.0
        self.position_side = None

    def check_risk_exit(self, price: float) -> bool:
        """
        Check ATR-based stop-loss / take-profit. If hit, close the position and
        return True; otherwise return False.
        """
        if self.position_side != "LONG":
            return False
        if self.stop_loss is None or self.take_profit is None:
            return False

        if price <= self.stop_loss:
            print(f"[RISK] Stop-loss hit at {price:.2f} (SL={self.stop_loss:.2f}).")
            self.close_position(price)
            return True

        if price >= self.take_profit:
            print(f"[RISK] Take-profit hit at {price:.2f} (TP={self.take_profit:.2f}).")
            self.close_position(price)
            return True

        return False

    def mark_to_market(self, price: float):
        if self.position_side == "LONG":
            unrealized = (price - self.entry_price) * self.position_size
        else:
            unrealized = 0.0
        equity = self.balance + unrealized
        self.equity_curve.append(equity)
        return equity

    def get_summary(self):
        total_trades = len(self.closed_trade_pnls)
        total_pnl = sum(self.closed_trade_pnls) if self.closed_trade_pnls else 0.0
        max_equity = max(self.equity_curve) if self.equity_curve else self.balance
        min_equity = min(self.equity_curve) if self.equity_curve else self.balance
        final_equity = self.equity_curve[-1] if self.equity_curve else self.balance
        return {
            "total_trades": total_trades,
            "total_pnl": total_pnl,
            "final_equity": final_equity,
            "max_equity": max_equity,
            "min_equity": min_equity,
        }


def create_exchange(config: BotConfig):
    cls = getattr(ccxt, config.exchange_name)
    exchange = cls({"enableRateLimit": True})
    return exchange


def fetch_ohlcv(exchange, symbol: str, timeframe: str, limit: int):
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    except Exception as e:
        print(f"[ERROR] Fetching OHLCV failed: {e}")
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame(
        data, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


def _apply_indicators_with_profile(df: pd.DataFrame, trader: PaperTrader) -> pd.DataFrame:
    """
    Call add_indicators, passing the strategy profile if the function supports it.
    Falls back gracefully to the legacy (df-only) signature if needed.
    """
    params = getattr(trader, "strategy_profile", None)
    if params is None:
        # No profile loaded, use legacy call
        return add_indicators(df)

    # Try calling with (df, params); if the function doesn't accept it, fall back to legacy
    try:
        return add_indicators(df, params)  # type: ignore[arg-type]
    except TypeError:
        return add_indicators(df)


def _generate_signal_with_profile(df: pd.DataFrame, trader: PaperTrader) -> str:
    """
    Call generate_signal, passing the strategy profile if supported.
    Falls back to legacy (df-only) signature if needed.
    """
    params = getattr(trader, "strategy_profile", None)
    if params is None:
        return generate_signal(df)

    try:
        return generate_signal(df, params)  # type: ignore[arg-type]
    except TypeError:
        return generate_signal(df)


def run_once(config: BotConfig, exchange, trader: PaperTrader, iteration: int):
    print("\n--- Bot Tick ---")
    print(f"Exchange: {config.exchange_name} | Symbol: {config.symbol} | TF: {config.timeframe}")

    # First try WebSocket buffer
    df = get_latest_candles(config.symbol, config.timeframe, config.candle_limit)

    if df.empty or len(df) < 20:
        print("[WS] Not enough candles from WebSocket yet, falling back to REST fetch_ohlcv.")
        df = fetch_ohlcv(exchange, config.symbol, config.timeframe, config.candle_limit)
    else:
        print(f"[WS] Using {len(df)} candles from WebSocket stream.")

    if df.empty or len(df) < 20:
        print("[WARN] Not enough candles from either WebSocket or REST. Skipping tick.")
        return

    # Ensure candles are time-sorted and compute indicators on closed candles
    df = df.sort_values("timestamp")
    df = _apply_indicators_with_profile(df, trader).dropna()
    if df.empty or len(df) < 20:
        print("[WARN] Not enough data after indicators, skipping.")
        return

    # Use the last closed candle
    last = df.iloc[-1]
    price = float(last["close"])
    # Get ATR value from last row if available
    atr_val = float(last.get("atr", float("nan")))
    if pd.isna(atr_val):
        atr_val = None

    # Candle time for per-candle guard
    candle_time = last["timestamp"]

    # First, check ATR-based SL/TP exits; if triggered, record the candle time
    if trader.check_risk_exit(price):
        trader.last_trade_candle_time = candle_time
        print("[INFO] Exited via SL/TP; skipping further actions this tick.")
        return

    signal = _generate_signal_with_profile(df, trader)

    print(f"Latest candle time: {last['timestamp']}")
    print(f"Price: {price:.2f}")
    print(f"Signal: {signal}")

    # Per-candle trade guard: only allow one trade (open or close) per candle
    if trader.last_trade_candle_time is not None and trader.last_trade_candle_time == candle_time:
        print("[RISK] Trade already executed on this candle; skipping trade logic.")
        # We can still mark to market equity, but do not open/close again
        equity = trader.mark_to_market(price)
        print(f"Equity: {equity:.8f}")
        return

    # Optional test mode: force a BUY on iteration 1 if flat, and a SELL on iteration 3 if long.
    # First, check ATR-based SL/TP exits
    if trader.check_risk_exit(price):
        print("[INFO] Exited via SL/TP; skipping further actions this tick.")
        return

    if config.test_mode:
        if trader.position_side is None and iteration == 1:
            print("[TEST_MODE] Forcing BUY on iteration 1.")
            trader.open_long(price, config.risk_per_trade_pct, atr_val)
            trader.last_trade_candle_time = candle_time
        elif trader.position_side == "LONG" and iteration == 3:
            print("[TEST_MODE] Forcing SELL on iteration 3.")
            trader.close_position(price)
            trader.last_trade_candle_time = candle_time
        else:
            print("[TEST_MODE] No forced action this iteration.")
    else:
        if signal == "BUY":
            if trader.position_side is None:
                trader.open_long(price, config.risk_per_trade_pct, atr_val)
                trader.last_trade_candle_time = candle_time
            else:
                print("[INFO] Already in position; skipping BUY.")
        elif signal == "SELL":
            if trader.position_side == "LONG":
                trader.close_position(price)
                trader.last_trade_candle_time = candle_time
            else:
                print("[INFO] No open position to close; skipping SELL.")
        else:
            print("[INFO] HOLD: no action taken.")

    equity = trader.mark_to_market(price)
    print(f"Equity: {equity:.8f}")

    # Only log to CSV when equity actually changes
    if getattr(trader, "last_logged_equity", None) is None or equity != trader.last_logged_equity:
        ts = datetime.now(timezone.utc).isoformat()
        log_equity(ts, equity)
        trader.last_logged_equity = equity
    else:
        print("[LOG] Equity unchanged; not logging to CSV.")
    if trader.position_side:
        print(f"[POSITION] {trader.position_side} @ {trader.entry_price:.2f}, size={trader.position_size:.6f}")
    else:
        print("[POSITION] Flat (no open trades)")
    print("--- End Tick ---\n")


def run_loop(max_iterations: int = 5):
    """
    Run the bot for a fixed number of iterations.
    You can change max_iterations or later swap this to an infinite loop.
    """
    config = BotConfig()
    exchange = create_exchange(config)
    
    trader = PaperTrader(
        balance=config.starting_balance,
        strategy_profile=None,
    )

    # Load per-symbol/timeframe strategy profile (if available)
    profile = load_strategy_profile(config.symbol, config.timeframe)
    if profile is not None:
        print(f"[STRATEGY] Loaded profile for {config.symbol} {config.timeframe}: {profile}")
        trader.strategy_profile = profile
    else:
        print(f"[STRATEGY] No profile found for {config.symbol} {config.timeframe}; using internal defaults.")

    # Start WebSocket OHLC stream (non-blocking background thread)
    pair = config.symbol
    start_ohlc_stream(pair, config.timeframe, max_candles=config.candle_limit)

    ensure_logs_exist()

    print(f"Starting loop for {max_iterations} iterations; interval={config.loop_interval_sec}s")

    # Starting equity for drawdown calculations
    initial_equity = trader.balance

    for i in range(1, max_iterations + 1):
        print(f"== Iteration {i}/{max_iterations} ==")
        run_once(config, exchange, trader, i)

        # Risk checks after each tick
        summary = trader.get_summary()

        # 1) Max trades per run
        if summary["total_trades"] >= config.max_trades_per_run:
            msg = f"Max trades per run reached ({summary['total_trades']} >= {config.max_trades_per_run})"
            print(f"[RISK] {msg}. Stopping loop.")
            ts = datetime.now(timezone.utc).isoformat()
            log_risk_event(ts, "MAX_TRADES_PER_RUN", msg, summary["final_equity"])
            break

        # 2) Max drawdown based on starting equity
        current_equity = summary["final_equity"]
        drawdown_pct = (initial_equity - current_equity) / initial_equity * 100 if initial_equity > 0 else 0.0
        if drawdown_pct >= config.max_drawdown_pct:
            msg = f"Max drawdown exceeded ({drawdown_pct:.2f}% >= {config.max_drawdown_pct}%)"
            print(f"[RISK] {msg}. Stopping loop.")
            ts = datetime.now(timezone.utc).isoformat()
            log_risk_event(ts, "MAX_DRAWDOWN", msg, current_equity)
            break

        if i < max_iterations:
            time.sleep(config.loop_interval_sec)

    print("Loop finished.")
    summary = trader.get_summary()
    print("\n=== Run Summary ===")
    print(f"Total closed trades: {summary['total_trades']}")
    print(f"Total PnL: {summary['total_pnl']:.2f}")
    print(f"Final equity: {summary['final_equity']:.2f}")
    print(f"Max equity: {summary['max_equity']:.2f}")
    print(f"Min equity: {summary['min_equity']:.2f}")
    print("=== End Summary ===\n")

if __name__ == "__main__":
    # MODULE 6: Multi-symbol orchestration support
    if os.getenv("MULTI_SYMBOL", "0") == "1":
        from orchestrator import Orchestrator
        from pathlib import Path
        
        config = BotConfig()
        exchange = create_exchange(config)
        
        orchestrator = Orchestrator(starting_balance_per_symbol=config.starting_balance)
        symbols = orchestrator.load_symbols(Path("symbols.json"))
        orchestrator.initialize_controllers(exchange, symbols)
        
        print("[BOT] Starting multi-symbol live mode")
        orchestrator.start_live()
    else:
        # For now, run a finite loop so it doesn't run forever.
        run_loop(max_iterations=5)
