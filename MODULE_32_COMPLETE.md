# Module 32 Complete: Strategy Evolution Engine v1

**Status**: ✅ COMPLETE  
**Date**: December 8, 2025  
**Modules**: 30, 31, 32

---

## Overview

Module 32 adds the foundation for a **self-observing optimization system** that tracks performance over time, versions strategy profiles, and detects when profiles degrade. This builds on Modules 30-31's optimizer and auto-apply functionality.

### Key Features

1. **Performance History Tracking**: All optimizer runs are logged to `logs/performance_history/history.jsonl` with full context (params, metrics, timestamps, run IDs)

2. **Versioned Strategy Profiles**: Profiles now include `meta` and `metrics` sections for tracking:
   - Version number
   - Creation/update timestamps
   - Source (optimizer vs manual)
   - Run ID linkage
   - Performance metrics at creation time

3. **Decay Detector**: Analyzes profile health by comparing current metrics against historical optimizer runs
   - READ-ONLY: Only reports status, never modifies configs
   - Flags profiles as "healthy", "degraded", "no-data", or "error"
   - Configurable thresholds for win rate and drawdown degradation

---

## Components

### 1. Performance History (`optimizer/performance_history.py`)

**Purpose**: Persist detailed records of all optimizer runs for future analysis.

**Schema** (history.jsonl):
```json
{
  "run_id": "run_20251208_120000",
  "created_at": "2025-12-08T12:00:00Z",
  "strategy": "scalping_ema_rsi",
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "start": "2025-12-01",
  "end": "2025-12-08",
  "interval": "1m",
  "trailing_stop_enabled": true,
  "trailing_stop_pct": 2.0,
  "risk_config_snapshot": {
    "default_risk_per_trade_pct": 1.0,
    "max_exposure_pct": 20.0,
    "max_daily_loss_pct": 5.0,
    "max_open_trades": 3
  },
  "profiles": [
    {
      "symbol": "BTCUSDT",
      "params": {...},
      "profile_name": "BTCUSDT.json",
      "metrics": {
        "trades": 125,
        "win_rate_pct": 65.0,
        "total_return_pct": 12.3,
        "max_drawdown_pct": 2.5,
        "avg_R_multiple": 1.8
      },
      "ranked_position": 1,
      "selected_for_live": true
    }
  ]
}
```

**Functions**:
- `get_history_dir()` - Get/create history directory
- `log_run(run_summary)` - Append run to history.jsonl
- `load_history(symbol=None, limit=None, history_dir=None)` - Load runs
- `latest_profiles(symbol, max_runs=20)` - Get recent profile snapshots
- `generate_run_id()` - Generate unique run ID

**Usage**:
```python
from optimizer.performance_history import log_run, generate_run_id

run_summary = {
    "run_id": generate_run_id(),
    "created_at": datetime.now(timezone.utc).isoformat(),
    "strategy": "scalping_ema_rsi",
    "symbols": ["BTCUSDT"],
    # ... other fields
}

log_run(run_summary)
```

---

### 2. Strategy Profile Versioning (`strategies/profile_loader.py`)

**Purpose**: Track metadata and metrics for strategy profiles to enable evolution tracking.

**New Profile Schema**:
```json
{
  "symbol": "BTCUSDT",
  "strategy": "scalping_ema_rsi",
  "enabled": true,
  "params": {
    "ema_fast": 8,
    "ema_slow": 21,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    "rsi_period": 14,
    "volume_multiplier": 1.5,
    "timeframe": "15m"
  },
  "meta": {
    "version": 1,
    "created_at": "2025-12-08T12:00:00Z",
    "updated_at": "2025-12-08T12:00:00Z",
    "source": "optimizer",
    "run_id": "run_20251208_120000",
    "notes": ""
  },
  "metrics": {
    "trades": 125,
    "win_rate_pct": 65.0,
    "total_return_pct": 12.3,
    "max_drawdown_pct": 2.5,
    "avg_R_multiple": 1.8,
    "sample_period_days": 7
  }
}
```

**Backward Compatibility**: Profile loader automatically adds default `meta` and `metrics` sections to legacy profiles when loading them.

**Updated Methods**:
- `load_profile(symbol, strategy)` - Loads profile and adds defaults for missing meta/metrics
- `save_profile(symbol, strategy, params, metrics=None, source="optimizer", run_id=None)` - Saves with new schema

**Usage**:
```python
from strategies.profile_loader import StrategyProfileLoader

loader = StrategyProfileLoader()

# Save with versioning
loader.save_profile(
    symbol="BTCUSDT",
    strategy="scalping_ema_rsi",
    params={"ema_fast": 8, ...},
    metrics={"trades": 125, "win_rate_pct": 65.0, ...},
    source="optimizer",
    run_id="run_20251208_120000"
)

# Load (gets meta/metrics even from legacy profiles)
profile = loader.load_profile("BTCUSDT", "scalping_ema_rsi")
print(profile["meta"]["version"])  # 1
print(profile["metrics"]["trades"])  # 125 or 0 if legacy
```

---

### 3. Decay Detector (`optimizer/decay_detector.py`)

**Purpose**: Analyze strategy profile health by comparing current metrics against historical best performance.

**Status Types**:
- `healthy`: Current metrics within acceptable thresholds of historical best
- `degraded`: Win rate dropped too much or drawdown increased too much
- `no-data`: No profile, insufficient trades, or no historical data
- `error`: Analysis failed

**Key Function**:
```python
async def analyze_profile_decay(
    symbol: str,
    strategy: str,
    profile_dir: Optional[Path] = None,
    history_dir: Optional[Path] = None,
    min_trades: int = 50,
    max_lookback_days: int = 30,
    winrate_threshold_pct: float = 15.0,
    drawdown_threshold_pct: float = 10.0
) -> DecayStatus
```

**DecayStatus**:
```python
@dataclass
class DecayStatus:
    symbol: str
    strategy: str
    status: Literal["healthy", "degraded", "no-data", "error"]
    reason: str
    stats: Dict[str, Any]  # current/best metrics, degradation amounts, thresholds
```

**CLI** (`optimizer/run_decay_check.py`):
```bash
# Check single symbol
python -m optimizer.run_decay_check --symbol BTCUSDT

# Check all symbols
python -m optimizer.run_decay_check --all

# Custom thresholds
python -m optimizer.run_decay_check --symbol ETHUSDT --min-trades 100 --winrate-threshold 20.0

# Options:
#   --symbol            Symbol to check
#   --all               Check all symbols
#   --strategy          Strategy name (default: scalping_ema_rsi)
#   --min-trades        Minimum trades required (default: 50)
#   --max-lookback-days Lookback window in days (default: 30)
#   --winrate-threshold Max win rate drop in % points (default: 15.0)
#   --drawdown-threshold Max drawdown increase in % points (default: 10.0)
```

**Example Output**:
```
======================================================================
Symbol: BTCUSDT
Strategy: scalping_ema_rsi
Status: HEALTHY
Reason: Metrics within thresholds (checked 5 historical runs)

Metrics:
  Current Trades: 120
  Current Win Rate: 58.50%
  Current Total Return: 10.20%
  Current Max Drawdown: 5.20%

Historical Best:
  Best Win Rate: 62.00%
  Best Total Return: 12.50%
  Best Max Drawdown: 4.80%

Degradation:
  Win Rate Drop: 3.50%
  Drawdown Increase: 0.40%

Analysis Context:
  Historical Runs: 5
  Lookback Days: 30

Thresholds:
  Min Trades: 50
  Win Rate Threshold: 15.0%
  Drawdown Threshold: 10.0%
======================================================================
```

---

## Usage Examples

### 1. Run Optimizer with History Logging

```bash
# Optimizer automatically logs to history.jsonl
python -m optimizer.run_optimizer \
  --symbol BTCUSDT ETHUSDT \
  --start 2025-12-01 \
  --end 2025-12-08 \
  --interval 1m \
  --auto-apply \
  --safety-check

# Disable history logging (not recommended)
python -m optimizer.run_optimizer \
  --symbol BTCUSDT \
  --start 2025-12-01 \
  --end 2025-12-08 \
  --interval 1m \
  --no-log-history
```

### 2. Check Profile Health

```bash
# Check if BTCUSDT profile is still performing well
python -m optimizer.run_decay_check --symbol BTCUSDT

# Check all profiles
python -m optimizer.run_decay_check --all

# Exit code 0 = healthy, 1 = degraded
python -m optimizer.run_decay_check --symbol ETHUSDT && echo "Profile is healthy"
```

### 3. Programmatic Access

```python
from optimizer.decay_detector import analyze_profile_decay
import asyncio

async def check_health():
    status = await analyze_profile_decay(
        symbol="BTCUSDT",
        strategy="scalping_ema_rsi",
        min_trades=50,
        winrate_threshold_pct=15.0
    )
    
    if status.status == "degraded":
        print(f"⚠️  DEGRADED: {status.reason}")
        print(f"Win rate drop: {status.stats['winrate_drop_pct']:.1f}%")
    elif status.status == "healthy":
        print(f"✅ Healthy (checked {status.stats['num_historical_runs']} runs)")
    else:
        print(f"ℹ️  {status.status.upper()}: {status.reason}")

asyncio.run(check_health())
```

---

## Testing

### Unit Tests

**Profile Versioning** (`tests/test_strategy_profile_versioning.py`):
- ✅ `test_profile_loader_populates_default_meta_and_metrics_when_missing`
- ✅ `test_profile_loader_reads_meta_and_metrics_when_present`
- ✅ `test_profile_loader_schema_validation_rejects_bad_meta_types`
- ✅ `test_save_profile_writes_new_versioned_schema`

**Decay Detector** (`tests/test_decay_detector.py`):
- ✅ `test_decay_detector_no_data_returns_no_data`
- ✅ `test_decay_detector_not_enough_trades_returns_no_data`
- ✅ `test_decay_detector_healthy_when_within_thresholds`
- ✅ `test_decay_detector_degraded_when_winrate_drops_too_much`
- ✅ `test_decay_detector_degraded_when_drawdown_worsens`

**Run Tests**:
```bash
# Run all Module 32 tests
python -m unittest tests.test_strategy_profile_versioning -v
python -m unittest tests.test_decay_detector -v

# Or all tests
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## Important Notes

### READ-ONLY Guarantee

**Module 32 components are 100% READ-ONLY**:
- Performance history only logs data, never modifies configs
- Decay detector only reports status, never changes profiles
- Profile versioning preserves backward compatibility

**No automatic changes** are made to:
- Strategy profiles
- Live trading configs
- Risk management settings

### Data Storage

**Performance History**:
- Location: `logs/performance_history/history.jsonl`
- Format: JSONL (one JSON object per line)
- Retention: Manual (no automatic cleanup)
- Size: ~1-5KB per optimizer run

**Strategy Profiles**:
- Location: `config/strategy_profiles/<SYMBOL>.json`
- Format: Pretty-printed JSON
- Versioning: Embedded in `meta.version` field

---

## Architecture

```
Module 30: Offline Optimizer
    ↓
Module 31: Auto-Apply with Safety
    ↓
Module 32: Performance Tracking + Decay Detection
    ↓
    ├── Performance History (logs/performance_history/history.jsonl)
    │   - Tracks all optimizer runs
    │   - Full parameter/metric snapshots
    │   - Run ID linkage
    │
    ├── Versioned Profiles (config/strategy_profiles/*.json)
    │   - Meta section (version, timestamps, source, run_id)
    │   - Metrics section (trades, win rate, return, drawdown)
    │   - Backward compatible with legacy profiles
    │
    └── Decay Detector (optimizer/decay_detector.py)
        - Compares current vs historical
        - Flags degraded profiles
        - READ-ONLY reporting
```

---

## Future Extensions

Module 32 provides the foundation for:

1. **Auto-Reoptimization**: When decay detected, trigger new optimization run
2. **Profile Rotation**: Swap degraded profiles with historical best performers
3. **A/B Testing**: Compare multiple profile versions simultaneously
4. **Metric Dashboards**: Visualize profile evolution over time
5. **Alerting**: Notify when profiles degrade
6. **Confidence Scoring**: Weight profiles by historical performance stability

---

## Success Criteria

✅ All tests passing (9 new tests)  
✅ Optimizer logs to history.jsonl automatically  
✅ Profiles use versioned schema with meta/metrics  
✅ Backward compatibility for legacy profiles  
✅ Decay detector correctly identifies healthy/degraded/no-data  
✅ CLI tools working (run_optimizer.py, run_decay_check.py)  
✅ Documentation complete  
✅ READ-ONLY guarantee maintained  

---

**Module 32 Complete** ✅  
Ready for Module 33: Advanced self-training features
