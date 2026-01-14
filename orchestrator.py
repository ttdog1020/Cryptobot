"""
MODULE 6: Multi-Symbol Orchestration Engine

Manages multiple trading strategies across different symbols and timeframes simultaneously.
Each symbol maintains its own state, profile, and position independently.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import csv

import pandas as pd

from bot import PaperTrader, create_exchange, _apply_indicators_with_profile, _generate_signal_with_profile, _fmt_usd, _fmt_size
from strategy_engine import load_strategy_profile
from fetch_ohlcv_paged import fetch_ohlcv_paged
from regime_engine import classify_regime
from risk_management import RiskConfig, RiskEngine


SYMBOLS_CONFIG = Path("symbols.json")
MULTI_TRADES_LOG = Path("logs") / "trades_multi.csv"
MULTI_EQUITY_LOG = Path("logs") / "equity_multi.csv"


def ensure_multi_trades_log():
    """Create trades_multi.csv with extended schema including symbol and regime."""
    MULTI_TRADES_LOG.parent.mkdir(exist_ok=True)
    if not MULTI_TRADES_LOG.exists():
        with MULTI_TRADES_LOG.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "symbol", "timeframe", "regime", "side", "price", "size", "pnl", 
                "balance_after", "entry_price", "exit_price", "stop_loss", "take_profit", "atr"
            ])


def ensure_multi_equity_log():
    """Create equity_multi.csv for per-symbol equity tracking."""
    MULTI_EQUITY_LOG.parent.mkdir(exist_ok=True)
    if not MULTI_EQUITY_LOG.exists():
        with MULTI_EQUITY_LOG.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "symbol", "timeframe", "equity"])


def log_multi_trade(ts, symbol, timeframe, regime, side, price, size, pnl, balance_after, 
                    entry_price=None, exit_price=None, stop_loss=None, take_profit=None, atr=None):
    """
    Log trade to multi-symbol trades CSV with USD precision formatting and regime tracking.
    PnL and balances use 2-decimal precision; sizes use 8-decimal precision.
    """
    with MULTI_TRADES_LOG.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            ts,
            symbol,
            timeframe,
            regime if regime else "UNKNOWN",
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


def log_multi_equity(ts, symbol, timeframe, equity):
    """Log per-symbol equity with 2-decimal USD formatting."""
    with MULTI_EQUITY_LOG.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([ts, symbol, timeframe, _fmt_usd(equity)])


class SymbolController:
    """
    Handles trading logic for a single symbol/timeframe pair.
    Maintains isolated state, profile, and trader instance.
    """
    
    def __init__(self, symbol: str, timeframe: str, starting_balance: float, exchange=None):
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = exchange
        
        # Load strategy profile for this symbol/timeframe
        self.profile = load_strategy_profile(symbol, timeframe)
        if self.profile is None:
            print(f"[{symbol} {timeframe}] WARNING: No profile found, using defaults")
            self.profile = {}
        
        # Regime tracking
        self.base_profile = dict(self.profile)  # Original profile
        self.regime_profiles = self.profile.get("regimes", {})  # Regime overrides
        self.current_regime = "DEFAULT"
        self.active_profile = dict(self.profile)  # Currently applied profile
        
        # Remove regimes from active_profile to avoid confusion
        if "regimes" in self.active_profile:
            del self.active_profile["regimes"]
        
        # Create dedicated trader instance for this symbol
        self.trader = PaperTrader(
            balance=starting_balance,
            strategy_profile=self.active_profile
        )
        
        # Track last processed timestamp to avoid duplicate processing
        self.last_processed_ts = None
        
        has_regimes = "(regime-aware)" if self.regime_profiles else ""
        print(f"[{symbol} {timeframe}] Controller initialized with balance ${starting_balance:.2f} {has_regimes}")
    
    def update_strategy_profile(self, profile_dict: Dict[str, Any]):
        """
        Update strategy profile and refresh trader parameters.
        
        Args:
            profile_dict: New profile configuration
        """
        self.profile = profile_dict
        self.base_profile = dict(profile_dict)
        self.regime_profiles = profile_dict.get("regimes", {})
        
        # Remove regimes from active profile
        self.active_profile = dict(profile_dict)
        if "regimes" in self.active_profile:
            del self.active_profile["regimes"]
        
        # Update trader profile and refresh cached parameters
        self.trader.strategy_profile = self.active_profile
        
        # Refresh risk parameters
        self.trader.risk_pct = float(self.active_profile.get("risk_per_trade_pct", 1.0))
        self.trader.sl_mult = float(self.active_profile.get("sl_atr_mult", 1.5))
        self.trader.tp_mult = float(self.active_profile.get("tp_atr_mult", 3.0))
        self.trader.min_pos_size = float(self.active_profile.get("min_position_size_usd", 10.0))
        
        print(f"[{self.symbol} {self.timeframe}] Profile updated: "
              f"MACD({self.active_profile.get('fast', 12)},{self.active_profile.get('slow', 26)},{self.active_profile.get('signal', 9)}), "
              f"RSI({self.active_profile.get('rsi_buy', 30)}/{self.active_profile.get('rsi_exit', 70)}), "
              f"ADX({self.active_profile.get('adx_min', 25)})")
    
    def select_profile_for_regime(self, regime: str) -> None:
        """
        Switch to regime-specific profile if available.
        
        Args:
            regime: Regime name (TRENDING, RANGING, BREAKOUT, etc.)
        """
        # If regime is DEFAULT or no regime overrides exist, use base profile
        if regime == "DEFAULT" or not self.regime_profiles:
            if self.current_regime != "DEFAULT":
                self.active_profile = dict(self.base_profile)
                if "regimes" in self.active_profile:
                    del self.active_profile["regimes"]
                self._apply_active_profile()
                print(f"[REGIME] {self.symbol}/{self.timeframe} switched {self.current_regime} -> DEFAULT")
                self.current_regime = "DEFAULT"
            return
        
        # Check if this regime has overrides
        if regime not in self.regime_profiles:
            return  # No overrides for this regime, keep current profile
        
        # Already in this regime
        if self.current_regime == regime:
            return
        
        # Build merged profile: base + regime overrides
        old_regime = self.current_regime
        self.current_regime = regime
        
        # Start with base profile
        self.active_profile = dict(self.base_profile)
        if "regimes" in self.active_profile:
            del self.active_profile["regimes"]
        
        # Apply regime overrides
        regime_overrides = self.regime_profiles[regime]
        self.active_profile.update(regime_overrides)
        
        # Apply to trader
        self._apply_active_profile()
        
        print(f"[REGIME] {self.symbol}/{self.timeframe} switched {old_regime} -> {regime} | "
              f"ADX:{self.active_profile.get('adx_min', 0):.0f} "
              f"RSI:{self.active_profile.get('rsi_buy', 0):.0f}/{self.active_profile.get('rsi_exit', 0):.0f} "
              f"TP:{self.active_profile.get('tp_atr_mult', 0):.1f}x")
    
    def _apply_active_profile(self):
        """Apply active_profile to trader instance."""
        self.trader.strategy_profile = self.active_profile
        
        # Refresh risk parameters
        self.trader.risk_pct = float(self.active_profile.get("risk_per_trade_pct", 1.0))
        self.trader.sl_mult = float(self.active_profile.get("sl_atr_mult", 1.5))
        self.trader.tp_mult = float(self.active_profile.get("tp_atr_mult", 3.0))
        self.trader.min_pos_size = float(self.active_profile.get("min_position_size_usd", 10.0))
    
    def fetch_data(self, limit: int = 500) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data for this symbol."""
        if self.exchange is None:
            return None
        
        try:
            ohlcv = fetch_ohlcv_paged(self.exchange, self.symbol, self.timeframe, limit)
            if not ohlcv or len(ohlcv) < 50:
                print(f"[{self.symbol} {self.timeframe}] Not enough data ({len(ohlcv) if ohlcv else 0} candles)")
                return None
            
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df
        except Exception as e:
            print(f"[{self.symbol} {self.timeframe}] Error fetching data: {e}")
            return None
    
    def run_cycle(self, df: pd.DataFrame, bar_index: int) -> List[Dict[str, Any]]:
        """
        Execute one trading cycle at the given bar index.
        Returns list of trades executed (if any).
        """
        trades = []
        
        if bar_index < 30:  # Need warmup period
            return trades
        
        # Detect market regime and switch profile if needed
        if self.regime_profiles:  # Only if regime overrides exist
            regime = classify_regime(df.iloc[:bar_index + 1])
            self.select_profile_for_regime(regime)
        
        row = df.iloc[bar_index]
        price = float(row["close"])
        high = float(row["high"])
        low = float(row["low"])
        
        # Extract ATR
        atr_val = float(row.get("atr", float("nan")))
        if pd.isna(atr_val):
            atr_val = None
        
        # Check SL/TP using high/low
        if self.trader.position_side == "LONG":
            if self.trader.stop_loss is not None and self.trader.take_profit is not None:
                if low <= self.trader.stop_loss:
                    # SL hit - save values before clearing
                    entry_price = self.trader.entry_price
                    sl = self.trader.stop_loss
                    tp = self.trader.take_profit
                    atr = self.trader.current_atr
                    size = self.trader.position_size
                    exit_price = sl
                    
                    pnl = (exit_price - entry_price) * size
                    self.trader.balance += pnl
                    
                    ts = datetime.now(timezone.utc).isoformat()
                    log_multi_trade(ts, self.symbol, self.timeframe, self.current_regime, "CLOSE_LONG", 
                                   exit_price, size, pnl, self.trader.balance,
                                   entry_price, exit_price, sl, tp, atr)
                    
                    trades.append({
                        "timestamp": ts, "symbol": self.symbol, "side": "CLOSE_LONG", 
                        "price": exit_price, "pnl": pnl
                    })
                    
                    # Clear position
                    self.trader.closed_trade_pnls.append(pnl)
                    self.trader.position_side = None
                    self.trader.position_size = 0.0
                    self.trader.entry_price = 0.0
                    self.trader.stop_loss = None
                    self.trader.take_profit = None
                    self.trader.current_atr = None
                    
                    print(f"[{self.symbol} {self.timeframe}] RISK: SL hit at {exit_price:.2f}, PnL={pnl:.4f}")
                    
                elif high >= self.trader.take_profit:
                    # TP hit - save values before clearing
                    entry_price = self.trader.entry_price
                    sl = self.trader.stop_loss
                    tp = self.trader.take_profit
                    atr = self.trader.current_atr
                    size = self.trader.position_size
                    exit_price = tp
                    
                    pnl = (exit_price - entry_price) * size
                    self.trader.balance += pnl
                    
                    ts = datetime.now(timezone.utc).isoformat()
                    log_multi_trade(ts, self.symbol, self.timeframe, self.current_regime, "CLOSE_LONG", 
                                   exit_price, size, pnl, self.trader.balance,
                                   entry_price, exit_price, sl, tp, atr)
                    
                    trades.append({
                        "timestamp": ts, "symbol": self.symbol, "side": "CLOSE_LONG", 
                        "price": exit_price, "pnl": pnl
                    })
                    
                    # Clear position
                    self.trader.closed_trade_pnls.append(pnl)
                    self.trader.position_side = None
                    self.trader.position_size = 0.0
                    self.trader.entry_price = 0.0
                    self.trader.stop_loss = None
                    self.trader.take_profit = None
                    self.trader.current_atr = None
                    
                    print(f"[{self.symbol} {self.timeframe}] RISK: TP hit at {exit_price:.2f}, PnL={pnl:.4f}")
        
        # Generate signal
        window = df.iloc[:bar_index + 1].copy()
        signal = _generate_signal_with_profile(window, self.trader)
        
        # Handle signals
        if signal == "BUY" and self.trader.position_side is None:
            if atr_val is None or atr_val <= 0:
                # Can't size position without ATR
                pass
            else:
                # MODULE 14: Use centralized risk engine for position sizing
                try:
                    order = self.trader.risk_engine.apply_risk_to_signal(
                        signal="LONG",
                        equity=self.trader.balance,
                        entry_price=price,
                        atr=atr_val,
                        risk_per_trade=self.trader.risk_pct,
                        sl_mult=self.trader.sl_mult,
                        tp_mult=self.trader.tp_mult
                    )
                    
                    if order is not None:
                        # Open position using risk engine results
                        self.trader.position_size = order["position_size"]
                        self.trader.entry_price = price
                        self.trader.position_side = "LONG"
                        self.trader.current_atr = atr_val
                        self.trader.stop_loss = order["stop_loss"]
                        self.trader.take_profit = order["take_profit"]
                        
                        ts = datetime.now(timezone.utc).isoformat()
                        log_multi_trade(ts, self.symbol, self.timeframe, self.current_regime, "OPEN_LONG", 
                                       price, order["position_size"], 0.0, self.trader.balance,
                                       price, None, order["stop_loss"], order["take_profit"], atr_val)
                        
                        trades.append({
                            "timestamp": ts, "symbol": self.symbol, "side": "OPEN_LONG", 
                            "price": price, "pnl": 0.0
                        })
                        
                        print(f"[{self.symbol} {self.timeframe}] OPEN LONG at {price:.2f}, "
                              f"size={order['position_size']:.6f}, SL={order['stop_loss']:.2f}, "
                              f"TP={order['take_profit']:.2f}, Risk=${order['risk_usd']:.2f}")
                except ValueError as e:
                    print(f"[{self.symbol} {self.timeframe}] RISK: Cannot open position: {e}")
        
        elif signal == "SELL" and self.trader.position_side == "LONG":
            # Exit signal
            entry_price = self.trader.entry_price
            sl = self.trader.stop_loss
            tp = self.trader.take_profit
            atr = self.trader.current_atr
            size = self.trader.position_size
            
            pnl = (price - entry_price) * size
            self.trader.balance += pnl
            
            ts = datetime.now(timezone.utc).isoformat()
            log_multi_trade(ts, self.symbol, self.timeframe, self.current_regime, "CLOSE_LONG", 
                           price, size, pnl, self.trader.balance,
                           entry_price, price, sl, tp, atr)
            
            trades.append({
                "timestamp": ts, "symbol": self.symbol, "side": "CLOSE_LONG",
                "price": price, "pnl": pnl
            })
            
            # Clear position
            self.trader.closed_trade_pnls.append(pnl)
            self.trader.position_side = None
            self.trader.position_size = 0.0
            self.trader.entry_price = 0.0
            self.trader.stop_loss = None
            self.trader.take_profit = None
            self.trader.current_atr = None
            
            print(f"[{self.symbol} {self.timeframe}] CLOSE LONG at {price:.2f}, PnL={pnl:.4f}")
        
        # Mark to market
        self.trader.mark_to_market(price)
        
        return trades
    
    def get_summary(self) -> Dict[str, Any]:
        """Get trading summary for this symbol."""
        summary = self.trader.get_summary()
        summary["symbol"] = self.symbol
        summary["timeframe"] = self.timeframe
        
        wins = sum(1 for pnl in self.trader.closed_trade_pnls if pnl > 0)
        losses = sum(1 for pnl in self.trader.closed_trade_pnls if pnl < 0)
        win_rate = (wins / summary["total_trades"] * 100) if summary["total_trades"] > 0 else 0.0
        
        summary["wins"] = wins
        summary["losses"] = losses
        summary["win_rate"] = win_rate
        
        return summary


class Orchestrator:
    """
    Manages multiple SymbolController instances for multi-symbol trading.
    """
    
    def __init__(self, starting_balance_per_symbol: float = 5000.0):
        self.starting_balance = starting_balance_per_symbol
        self.controllers: List[SymbolController] = []
        self.exchange = None
    
    def load_symbols(self, symbols_file: Path = SYMBOLS_CONFIG) -> List[Dict[str, str]]:
        """Load symbol configurations from JSON file."""
        if not symbols_file.exists():
            print(f"[ORCHESTRATOR] Symbols config not found: {symbols_file}")
            return []
        
        with symbols_file.open("r", encoding="utf-8") as f:
            config = json.load(f)
        
        symbols = config.get("symbols", [])
        print(f"[ORCHESTRATOR] Loaded {len(symbols)} symbols from {symbols_file}")
        return symbols
    
    def initialize_controllers(self, exchange, symbols: List[Dict[str, str]]):
        """Create SymbolController for each symbol/timeframe pair."""
        self.exchange = exchange
        
        for sym_config in symbols:
            symbol = sym_config.get("symbol")
            timeframe = sym_config.get("timeframe")
            
            if not symbol or not timeframe:
                print(f"[ORCHESTRATOR] Invalid symbol config: {sym_config}")
                continue
            
            controller = SymbolController(
                symbol=symbol,
                timeframe=timeframe,
                starting_balance=self.starting_balance,
                exchange=exchange
            )
            self.controllers.append(controller)
        
        print(f"[ORCHESTRATOR] Initialized {len(self.controllers)} controllers")
    
    def run_backtest(self, limit: int = 20000):
        """Run backtest for all symbols."""
        ensure_multi_trades_log()
        
        print(f"\n[ORCHESTRATOR] Starting multi-symbol backtest with {len(self.controllers)} symbols")
        print(f"[ORCHESTRATOR] Candle limit: {limit}")
        
        all_summaries = []
        
        for controller in self.controllers:
            print(f"\n{'='*60}")
            print(f"Processing {controller.symbol} {controller.timeframe}")
            print(f"{'='*60}")
            
            # Fetch data
            df = controller.fetch_data(limit)
            if df is None or len(df) < 50:
                print(f"[{controller.symbol}] Insufficient data, skipping")
                continue
            
            # Apply indicators
            df = _apply_indicators_with_profile(df, controller.trader)
            
            # Run backtest bar by bar
            for i in range(30, len(df)):
                controller.run_cycle(df, i)
            
            # Close any open positions
            if controller.trader.position_side == "LONG":
                last_price = float(df.iloc[-1]["close"])
                entry_price = controller.trader.entry_price
                size = controller.trader.position_size
                pnl = (last_price - entry_price) * size
                controller.trader.balance += pnl
                
                ts = datetime.now(timezone.utc).isoformat()
                log_multi_trade(ts, controller.symbol, controller.timeframe, controller.current_regime, "CLOSE_LONG", 
                               last_price, size, pnl, controller.trader.balance,
                               entry_price, last_price, controller.trader.stop_loss, 
                               controller.trader.take_profit, controller.trader.current_atr)
                
                controller.trader.closed_trade_pnls.append(pnl)
                controller.trader.position_side = None
            
            # Get summary
            summary = controller.get_summary()
            all_summaries.append(summary)
            
            print(f"\n[{controller.symbol} {controller.timeframe}] Summary:")
            print(f"  Trades: {summary['total_trades']}")
            print(f"  Wins: {summary['wins']}, Losses: {summary['losses']}, Win Rate: {summary['win_rate']:.1f}%")
            print(f"  PnL: {summary['total_pnl']:.4f}")
            print(f"  Final Equity: {summary['final_equity']:.4f}")
        
        # Overall summary
        print(f"\n{'='*60}")
        print("OVERALL MULTI-SYMBOL SUMMARY")
        print(f"{'='*60}")
        
        total_trades = sum(s['total_trades'] for s in all_summaries)
        total_wins = sum(s['wins'] for s in all_summaries)
        total_losses = sum(s['losses'] for s in all_summaries)
        total_pnl = sum(s['total_pnl'] for s in all_summaries)
        total_equity = sum(s['final_equity'] for s in all_summaries)
        
        overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0.0
        
        print(f"Total symbols processed: {len(all_summaries)}")
        print(f"Total trades: {total_trades}")
        print(f"Total wins: {total_wins}, Total losses: {total_losses}")
        print(f"Overall win rate: {overall_win_rate:.1f}%")
        print(f"Combined PnL: {total_pnl:.4f}")
        print(f"Combined equity: {total_equity:.4f}")
        print(f"Starting capital: {self.starting_balance * len(all_summaries):.4f}")
        print(f"Return: {((total_equity / (self.starting_balance * len(all_summaries))) - 1) * 100:.2f}%")
        
        return all_summaries
    
    def start_live(self):
        """Start live trading mode (round-robin execution)."""
        print("[ORCHESTRATOR] Live mode not yet implemented")
        # TODO: Implement live trading loop
        pass
