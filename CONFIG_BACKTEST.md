# Configuration-Driven Historical Backtest Runner

## Overview

The `backtests.config_backtest` module provides a complete backtesting system that **reuses all live trading components** for historical testing. This ensures that backtest results accurately reflect what would happen in live trading.

## Key Features

### Component Reuse
- ✅ **Same configuration** - Uses `config/live.yaml` (symbols, timeframe, risk settings)
- ✅ **Same strategies** - Identical signal generation logic as live trading
- ✅ **Same risk management** - RiskEngine with position sizing and SL/TP
- ✅ **Same execution engine** - PaperTrader with cash+equity accounting
- ✅ **Same safety limits** - SafetyMonitor with kill switch and max exposure
- ✅ **Same order flow** - ExecutionEngine routing and validation

### Cash+Equity Accounting Model
- Balance (cash) changes **ONLY** on CLOSE trades
- Equity = balance + unrealized PnL of open positions
- Flatten-on-shutdown: All positions closed at end of backtest
- Trade logging matches live paper trading CSV format

### Data Management
- Fetches historical OHLCV data from Binance/Binance US via CCXT
- Automatic caching in `data/backtest_cache/` to avoid re-fetching
- Respects exchange rate limits
- Supports multiple symbols and timeframes

## Usage

### Basic Usage

Run a backtest for a specific date range:

```bash
# Backtest from Dec 1-8, 2025 with 1m candles
python -m backtests.config_backtest --start 2025-12-01 --end 2025-12-08 --interval 1m
```

### Quick Test

Run with default settings (last 24 hours):

```bash
# Uses last 24 hours and config defaults
python -m backtests.config_backtest
```

### Custom Timeframes

```bash
# 5-minute candles for November
python -m backtests.config_backtest --start 2025-11-01 --end 2025-11-30 --interval 5m

# 15-minute candles for last week
python -m backtests.config_backtest --start 2025-12-01 --end 2025-12-08 --interval 15m
```

### Programmatic Usage

```python
from backtests.config_backtest import run_config_backtest

results = run_config_backtest(
    start="2025-12-01",
    end="2025-12-08",
    interval="1m"
)

print(f"Total return: {results['performance']['total_return_pct']:.2f}%")
print(f"Win rate: {results['performance']['win_rate']:.1f}%")
```

## Command-Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--start` | Start date (YYYY-MM-DD) | 24 hours ago |
| `--end` | End date (YYYY-MM-DD) | Now |
| `--interval` | Candle interval (1m, 5m, 15m, etc.) | From config |
| `--config` | Path to config file | config/live.yaml |

## Output

### Console Report

The backtest prints a comprehensive report:

```
============================================================
BACKTEST RESULTS
============================================================
Period: 2025-12-01 00:00 to 2025-12-08 00:00
Candles processed: 10080
Signals generated: 42
Orders submitted: 38
------------------------------------------------------------
Starting balance:  $10000.00
Final balance:     $10234.56
Final equity:      $10234.56
Realized PnL:      +$234.56
Total return:      +2.35%
------------------------------------------------------------
Total trades:      38
Winning trades:    24
Losing trades:     14
Win rate:          63.2%
------------------------------------------------------------
Peak equity:       $10456.78
Max drawdown:      2.14%
------------------------------------------------------------
Trade log saved:   logs/backtests/config_backtest_20251201_20251208.csv
============================================================
```

### Trade Log CSV

All trades are logged to `logs/backtests/config_backtest_{start}_{end}.csv` with columns:

- `timestamp` - Trade execution time
- `symbol` - Trading pair (e.g., BTCUSDT)
- `action` - OPEN or CLOSE
- `side` - LONG or SHORT
- `price` - Execution price
- `quantity` - Position size
- `commission` - Trading fees
- `slippage` - Price slippage
- `balance` - Cash balance after trade
- `equity` - Total equity (balance + unrealized)
- `realized_pnl` - Realized profit/loss (0 for OPEN)
- `unrealized_pnl` - Unrealized P&L of position
- `strategy` - Strategy name
- `metadata` - Additional context (JSON)

### Results Dictionary

The `run_config_backtest()` function returns:

```python
{
    "config": {
        "start_date": "2025-12-01T00:00:00",
        "end_date": "2025-12-08T00:00:00",
        "interval": "1m",
        "symbols": ["BTCUSDT", "ETHUSDT", ...],
        "starting_balance": 10000.0
    },
    "statistics": {
        "candles_processed": 10080,
        "signals_generated": 42,
        "orders_submitted": 38
    },
    "performance": {
        "starting_balance": 10000.0,
        "current_balance": 10234.56,
        "equity": 10234.56,
        "realized_pnl": 234.56,
        "total_return_pct": 2.35,
        "total_trades": 38,
        "winning_trades": 24,
        "losing_trades": 14,
        "win_rate": 63.2,
        "open_positions": []
    },
    "log_file": "logs/backtests/config_backtest_20251201_20251208.csv"
}
```

## Architecture

### Component Flow

```
ConfigBacktestRunner
  ├─> HistoricalDataProvider (fetch OHLCV via CCXT)
  │     └─> Cache in data/backtest_cache/
  │
  ├─> ScalpingEMARSI Strategy (same as live)
  │     ├─> add_indicators() (technical analysis)
  │     └─> generate_signal() (LONG/SHORT/FLAT)
  │
  ├─> RiskEngine (same as live)
  │     ├─> Position sizing based on equity
  │     ├─> Stop-loss and take-profit levels
  │     └─> Risk validation (max 1% per trade)
  │
  ├─> ExecutionEngine (same as live)
  │     ├─> Order validation (no UNKNOWN symbols)
  │     └─> Safety checks (kill switch, max positions)
  │
  ├─> PaperTrader (cash+equity model)
  │     ├─> Balance unchanged on OPEN
  │     ├─> Balance changes only on CLOSE
  │     ├─> Position tracking with unrealized PnL
  │     └─> Trade logging to CSV
  │
  └─> SafetyMonitor (same as live)
        ├─> Max drawdown tracking (equity-based)
        ├─> Max open positions limit
        ├─> Max exposure limit
        └─> Kill switch integration
```

### Data Caching

Historical data is cached to avoid repeated API calls:

```
data/backtest_cache/
  ├─ BTCUSDT_1m_20251201_20251208.csv
  ├─ ETHUSDT_1m_20251201_20251208.csv
  └─ SOLUSDT_5m_20251101_20251130.csv
```

Cache files are reused if they exist. Delete cache files to force re-fetch.

### Candle Processing

The backtest processes candles chronologically:

1. **Unified Timeline** - Merge timestamps from all symbols
2. **Sequential Processing** - Process each timestamp in order
3. **Historical Context** - Pass all candles up to current time to strategy
4. **Indicator Calculation** - Add technical indicators to historical data
5. **Signal Generation** - Strategy analyzes indicators and generates signal
6. **Risk Management** - Size position and set SL/TP based on equity
7. **Order Execution** - Submit to PaperTrader with slippage/commission
8. **Position Tracking** - Update unrealized PnL as prices change
9. **Safety Checks** - Monitor drawdown and enforce limits

### Flatten-on-Shutdown

At the end of the backtest:

1. Get all open positions
2. For each position, get latest price from historical data
3. Call `PaperTrader.close_all_positions()` with price lookup function
4. All positions closed and logged as CLOSE trades
5. Final equity = final balance (no unrealized PnL)

## Configuration

The backtest uses the same configuration as live trading:

### Live Config (`config/live.yaml`)

```yaml
exchange: binance_us
symbols:
  - BTCUSDT
  - ETHUSDT
  - SOLUSDT
  # ... more symbols
timeframe: "1m"
strategy:
  type: scalping_ema_rsi
  params: {}  # Uses defaults from strategy config
```

### Risk Config (`config/risk.json`)

```json
{
  "base_account_size": 10000.0,
  "default_risk_per_trade": 0.01,
  "max_exposure": 0.20,
  "default_slippage": 0.001,
  "min_position_size_usd": 10.0
}
```

### Trading Mode Config (`config/trading_mode.yaml`)

```yaml
mode: paper
max_daily_loss_pct: 0.05
max_risk_per_trade_pct: 0.01
max_exposure_pct: 0.20
max_open_trades: 5
```

## Testing

### Unit Tests

Run backtest unit tests:

```bash
python -m unittest tests.test_backtest_basic -v
```

Tests verify:
- ✅ Initialization with default and custom dates
- ✅ Configuration loading
- ✅ Latest price lookup
- ✅ No exceptions during execution
- ✅ Cash+equity accounting model
- ✅ Trade logging to CSV
- ✅ Position flattening at end
- ✅ Safety limits enforcement

### Integration Tests

Run with synthetic data:

```bash
python -m unittest tests.test_config_backtest -v
```

### Demo

Run quick demo (2 hours of recent data):

```bash
python examples/demo_config_backtest.py
```

## Comparison: Live vs Backtest

| Aspect | Live Trading | Backtest |
|--------|-------------|----------|
| Data source | WebSocket streams | Historical OHLCV |
| Execution | Real-time (async) | Sequential (sync) |
| Slippage | Real market impact | Simulated (0.05%) |
| Commission | Actual exchange fees | Simulated (0.05%) |
| Configuration | config/live.yaml | **Same file** |
| Strategy | ScalpingEMARSI | **Same class** |
| Risk engine | RiskEngine | **Same class** |
| Execution engine | ExecutionEngine | **Same class** |
| Paper trader | PaperTrader | **Same class** |
| Safety monitor | SafetyMonitor | **Same class** |
| Accounting | Cash+equity | **Same model** |
| Trade logging | CSV format | **Same format** |

## Examples

### Example 1: Week-long Backtest

```bash
python -m backtests.config_backtest \
  --start 2025-12-01 \
  --end 2025-12-08 \
  --interval 1m
```

Output:
```
Candles processed: 10080
Signals generated: 42
Orders submitted: 38
Starting balance: $10000.00
Final equity: $10234.56
Return: +2.35%
Win rate: 63.2%
```

### Example 2: Month-long with 5m Candles

```bash
python -m backtests.config_backtest \
  --start 2025-11-01 \
  --end 2025-11-30 \
  --interval 5m
```

Benefits:
- Faster execution (fewer candles)
- Different strategy behavior (5m vs 1m)
- Reduced API calls (cached data)

### Example 3: Python API

```python
from backtests.config_backtest import ConfigBacktestRunner
from datetime import datetime

runner = ConfigBacktestRunner(
    config_path="config/live.yaml",
    start_date=datetime(2025, 12, 1),
    end_date=datetime(2025, 12, 8),
    interval="1m"
)

results = runner.run()

# Analyze results
perf = results['performance']
if perf['win_rate'] > 60 and perf['total_return_pct'] > 2:
    print("✅ Strategy performs well!")
else:
    print("⚠️  Strategy needs optimization")
```

## Troubleshooting

### Rate Limit Errors

If you see `ccxt.RateLimitExceeded`:

- Wait a few minutes before retrying
- Use cached data (don't delete cache files)
- Reduce date range (fewer candles to fetch)

### Missing Data

If no data is returned:

- Check symbol format (use BTCUSDT not BTC/USDT in config)
- Verify exchange supports the symbol
- Try a more recent date range
- Check network connectivity

### Memory Issues

For very long backtests:

- Use larger interval (5m instead of 1m)
- Reduce number of symbols
- Process date range in chunks
- Clear cache after each run

## Performance Tips

1. **Use Cache** - Don't delete cache files between runs
2. **Larger Intervals** - 5m or 15m instead of 1m for faster tests
3. **Limit Symbols** - Test with 1-3 symbols first
4. **Shorter Ranges** - Start with 1 week, then expand
5. **Parallel Testing** - Run multiple backtests with different params

## Future Enhancements

Potential additions:

- [ ] Walk-forward optimization
- [ ] Monte Carlo simulation
- [ ] Portfolio-level backtesting (multiple strategies)
- [ ] Slippage modeling based on volume
- [ ] Real commission tiers (maker/taker)
- [ ] Benchmark comparison (buy-and-hold)
- [ ] Sharpe ratio and other metrics
- [ ] Equity curve visualization
- [ ] Parameter sensitivity analysis

## See Also

- `run_live.py` - Live trading runtime
- `execution/paper_trader.py` - Cash+equity accounting
- `risk_management/risk_engine.py` - Position sizing
- `strategies/rule_based/scalping.py` - Strategy implementation
- `FLATTEN_ON_SHUTDOWN.md` - Position closing behavior
- `ACCOUNTING_FIX.md` - Cash+equity model documentation

---

**Last Updated**: December 8, 2025
**Module Version**: 1.0
**Status**: Production Ready ✅
