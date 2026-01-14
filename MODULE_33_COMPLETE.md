# MODULE 33 COMPLETE ✅

**Auto-Evolution / Self-Training Engine v1**

## 📋 Overview

Module 33 implements an **automated evolution system** that:
1. Continuously monitors strategy profile health using the decay detector (Module 32)
2. Automatically searches performance history for better parameter sets when profiles degrade
3. Applies strict safety filters and improvement thresholds before making changes
4. Archives old profiles and updates to new parameters with full audit trail
5. **READ-ONLY for risk configs** - never modifies `risk.json`, `trading_mode.yaml`, or safety limits

## 🎯 What Got Built

### 1. Evolution Configuration (`config/evolution.json`)

Centralized config for auto-evolution behavior:

```json
{
  "enable_auto_evolution": true,
  "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT", ...],
  "decay_health_thresholds": ["degraded"],
  "optimizer_window": {
    "start_days_ago": 30,
    "end_days_ago": 0
  },
  "min_trades": 5,
  "min_return_pct": 1.0,
  "max_dd_pct": 5.0,
  "min_improvement_return_pct": 0.5,
  "max_allowed_dd_increase_pct": 0.5,
  "archive_dir": "config/strategy_profiles/archive",
  "log_dir": "logs/evolution",
  "dry_run": true,
  "require_confirmation": false
}
```

**Key Parameters:**
- **`decay_health_thresholds`**: Which health statuses trigger evolution (e.g., `["degraded"]`)
- **`optimizer_window`**: Time range to search for better parameters
- **Safety Filters**: Minimum trades, return, maximum drawdown
- **Improvement Thresholds**: Require meaningful improvement (0.5% return, max 0.5% dd increase)
- **`dry_run`**: Safe default - logs what would happen without modifying files

### 2. Evolution Engine (`optimizer/evolution_engine.py`)

Core decision-making engine with 5-step process:

#### Step 1: Load Current Profile
```python
profile = profile_loader.load_profile(symbol, strategy)
old_metrics = profile.get("metrics", {})
```

#### Step 2: Check Health Status
```python
health_status = await analyze_profile_decay(symbol, strategy, min_trades)
if health_status.status not in decay_health_thresholds:
    return EvolutionDecision("SKIP", "Profile is healthy")
```

#### Step 3: Search Performance History
```python
history = load_history(history_dir=base_dir / "logs/performance_history")
candidates = extract_candidates_from_history(symbol, history, start_dt, end_dt)
```

#### Step 4: Filter & Rank Candidates
```python
# Apply global safety filters
viable = [c for c in candidates if 
    c.trades >= min_trades and
    c.return >= min_return_pct and
    c.drawdown <= max_dd_pct
]

# Rank: maximize return, minimize drawdown
viable.sort(key=lambda c: (-c.return, c.drawdown))
best = viable[0]
```

#### Step 5: Compare & Decide
```python
improvement = best.return - old_return
dd_increase = best.drawdown - old_drawdown

if improvement < min_improvement_return_pct:
    return EvolutionDecision("REJECT", "Insufficient improvement")
if dd_increase > max_allowed_dd_increase_pct:
    return EvolutionDecision("REJECT", "Drawdown increase too high")

return EvolutionDecision("APPLY", "Candidate approved", 
                        new_params=best.params, new_metrics=best.metrics)
```

#### Application (if not dry-run)
```python
def apply_update(symbol, decision):
    if decision.status != "APPLY" or cfg["dry_run"]:
        return log_decision_only()
    
    # Archive old profile
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    archive_path = f"archive/{symbol}_profile_{timestamp}.json"
    shutil.copy2(current_profile, archive_path)
    
    # Update profile with new params/metrics
    profile["params"] = decision.new_params
    profile["metrics"] = decision.new_metrics
    profile["meta"]["version"] += 1
    profile["meta"]["source"] = "auto_evolution"
    profile["meta"]["updated_at"] = timestamp
    
    # Write new profile
    write_json(profile_path, profile)
    
    # Log decision to audit trail
    write_evolution_log(symbol, decision, applied=True)
```

**Decision Statuses:**
- **`SKIP`**: Profile doesn't need evolution (healthy, no data, etc.)
- **`APPLY`**: New candidate approved and should be applied
- **`REJECT`**: Candidates found but don't meet requirements
- **`ERROR`**: Something went wrong during evaluation

### 3. CLI Wrapper (`optimizer/run_evolution.py`)

Command-line interface for running evolution:

```bash
# Run evolution in dry-run mode (default - safe)
python -m optimizer.run_evolution

# Run for specific symbols
python -m optimizer.run_evolution --symbols BTCUSDT ETHUSDT

# Live mode (actually applies changes)
python -m optimizer.run_evolution --config config/evolution.json

# Override config file
python -m optimizer.run_evolution --config custom_evolution.json --dry-run
```

**Output Example:**
```
=== Auto-Evolution Report ===

Symbol     | Status  | Reason
-----------|---------|------------------------------------------
BTCUSDT    | APPLY   | ✓ Candidate approved: +2.5% return, +0.2% dd
ETHUSDT    | SKIP    | Health=healthy not in thresholds
SOLUSDT    | REJECT  | Insufficient improvement (0.3% < 0.5%)
BNBUSDT    | REJECT  | All candidates failed global safety filters

Summary:
  SKIP:   1
  APPLY:  1
  REJECT: 2
  ERROR:  0

⚠️  DRY-RUN MODE: No profiles were modified
📁 Logs written to: logs/evolution/
```

### 4. Unit Tests (`tests/test_evolution_engine.py`)

Comprehensive test coverage with 8 test cases:

1. **✅ test_evolution_accepts_better_profile**
   - Degraded profile + better candidate → APPLY

2. **✅ test_evolution_rejects_if_not_degraded**
   - Healthy profile → SKIP (not in thresholds)

3. **✅ test_evolution_rejects_if_insufficient_improvement**
   - Improvement only 0.1% (needs 0.5%) → REJECT

4. **✅ test_evolution_rejects_if_drawdown_too_high**
   - Good return but excessive drawdown increase → REJECT

5. **✅ test_evolution_rejects_if_insufficient_trades**
   - Candidate has only 2 trades (needs 5) → REJECT

6. **✅ test_apply_update_in_dry_run_does_not_modify**
   - Dry-run mode logs but doesn't change files

7. **✅ test_apply_update_archives_and_increments_version**
   - Live mode archives old profile and increments version

8. **✅ test_evolution_log_is_created**
   - Audit logs are written to `logs/evolution/`

**All tests use AsyncMock to control decay detector behavior:**
```python
mock_status = DecayStatus(symbol, strategy, status="degraded", reason="Test", stats={})
with patch('optimizer.evolution_engine.analyze_profile_decay', new_callable=AsyncMock) as mock:
    mock.return_value = mock_status
    decision = await engine.evaluate_symbol(symbol)
```

## 🔒 Safety Features

### 1. Dry-Run Mode (Default)
- **Enabled by default** in `config/evolution.json`
- Logs all decisions without modifying files
- Safe for testing and monitoring

### 2. Profile Archiving
- Every replaced profile is archived with timestamp
- Archive path: `config/strategy_profiles/archive/{symbol}_profile_{timestamp}.json`
- Full history preserved for rollback

### 3. Audit Logs
- Every decision logged to `logs/evolution/{symbol}_{timestamp}.json`
- Contains: status, reason, old/new params, old/new metrics, run_id
- Full transparency for all evolution actions

### 4. Strict Safety Filters
- **Global filters** (min_trades, min_return, max_dd)
- **Improvement thresholds** (min improvement, max dd increase)
- **Health-based triggers** (only evolve if status in thresholds)

### 5. READ-ONLY for Risk Configs
- **NEVER** modifies `config/risk.json`
- **NEVER** modifies `config/trading_mode.yaml`
- **NEVER** changes safety limits or position sizing
- **ONLY** updates strategy profile parameters

### 6. Version Tracking
- Increments `meta.version` on every update
- Sets `meta.source = "auto_evolution"`
- Tracks `meta.updated_at` timestamp
- Full versioning for rollback capability

## 📊 Integration with Modules 30-32

### Module 30: Optimizer
- **Uses**: Performance history entries created by optimizer
- **Searches**: `logs/performance_history/history.jsonl` for better parameters
- **Filters**: Candidates based on safety constraints from optimizer runs

### Module 31: Profile Loader
- **Uses**: `StrategyProfileLoader` to read/write profiles
- **Loads**: Current profile to compare against candidates
- **Writes**: Updated profile with new parameters

### Module 32: Decay Detector
- **Uses**: `analyze_profile_decay()` to check profile health
- **Triggers**: Evolution only when status is in `decay_health_thresholds`
- **Monitors**: Performance degradation over time

**Data Flow:**
```
1. Optimizer (M30) runs → creates performance history entries
2. Decay Detector (M32) analyzes profile health
3. Evolution Engine (M33) detects degradation
4. Evolution searches history for better params
5. Filters & ranks candidates by safety constraints
6. Archives old profile & applies new one
7. Logs decision to audit trail
```

## 📖 Usage Examples

### Example 1: Initial Setup (Dry-Run)

```bash
# Review default configuration
cat config/evolution.json

# Run evolution in dry-run mode (safe)
python -m optimizer.run_evolution

# Check what would have been applied
cat logs/evolution/BTCUSDT_*.json
```

**Expected Output:**
```json
{
  "timestamp": "2025-12-09T10:30:00Z",
  "symbol": "BTCUSDT",
  "status": "APPLY",
  "reason": "✓ Candidate approved: +2.0% return, +0.1% dd",
  "old_params": {"ema_fast": 8, "ema_slow": 21, ...},
  "new_params": {"ema_fast": 10, "ema_slow": 20, ...},
  "old_metrics": {"total_return_pct": 1.5, "max_drawdown_pct": 1.2, ...},
  "new_metrics": {"total_return_pct": 3.5, "max_drawdown_pct": 1.3, ...},
  "optimizer_run_id": "opt_20251208_103000",
  "archive_path": null,
  "dry_run": true,
  "applied": false
}
```

### Example 2: Enable Live Mode (After Testing)

```bash
# Edit config to disable dry-run
# Change: "dry_run": false in config/evolution.json

# Run evolution in live mode
python -m optimizer.run_evolution

# Verify profiles were updated
ls -l config/strategy_profiles/archive/

# Check version incremented
cat config/strategy_profiles/BTCUSDT.json | grep version
```

**Profile Changes:**
```json
{
  "symbol": "BTCUSDT",
  "strategy": "scalping_ema_rsi",
  "params": {
    "ema_fast": 10,      // ← UPDATED
    "ema_slow": 20,      // ← UPDATED
    ...
  },
  "metrics": {
    "total_return_pct": 3.5,    // ← UPDATED
    "max_drawdown_pct": 1.3,    // ← UPDATED
    ...
  },
  "meta": {
    "version": 2,                      // ← INCREMENTED
    "source": "auto_evolution",        // ← CHANGED
    "updated_at": "2025-12-09T10:35:00Z",  // ← UPDATED
    ...
  }
}
```

**Archive Created:**
```
config/strategy_profiles/archive/BTCUSDT_profile_20251209_103500.json
```

### Example 3: Scheduled Evolution (Cron/Task Scheduler)

```bash
# Add to crontab (Linux/Mac) - run daily at 2 AM
0 2 * * * cd /path/to/CryptoBot && python -m optimizer.run_evolution

# Or Windows Task Scheduler
schtasks /create /tn "CryptoBot Evolution" /tr "python -m optimizer.run_evolution" /sc daily /st 02:00
```

### Example 4: Custom Evolution Config

```json
// custom_evolution.json
{
  "enable_auto_evolution": true,
  "symbols": ["BTCUSDT"],  // Only evolve BTC
  "decay_health_thresholds": ["degraded", "concerning"],  // More aggressive
  "optimizer_window": {"start_days_ago": 7, "end_days_ago": 0},  // Recent data only
  "min_trades": 10,  // Higher confidence
  "min_return_pct": 2.0,  // Stricter filters
  "max_dd_pct": 3.0,
  "min_improvement_return_pct": 1.0,  // Require 1% improvement
  "max_allowed_dd_increase_pct": 0.3,  // Very conservative
  "dry_run": false,
  "require_confirmation": false
}
```

```bash
python -m optimizer.run_evolution --config custom_evolution.json
```

## 🧪 Testing

### Run Evolution Engine Tests
```bash
# Run Module 33 tests only
python -m unittest tests.test_evolution_engine -v

# Expected: 8/8 tests passing
# ✅ test_evolution_accepts_better_profile
# ✅ test_evolution_rejects_if_not_degraded
# ✅ test_evolution_rejects_if_insufficient_improvement
# ✅ test_evolution_rejects_if_drawdown_too_high
# ✅ test_evolution_rejects_if_insufficient_trades
# ✅ test_apply_update_in_dry_run_does_not_modify
# ✅ test_apply_update_archives_and_increments_version
# ✅ test_evolution_log_is_created
```

### Run Full Test Suite
```bash
# Verify no regressions
python -m unittest discover -s tests -p "test_*.py"

# Expected: 224/224 tests passing
```

## 🎓 Key Learnings

### 1. AsyncMock for Testing Async Functions
**Problem**: Tests calling real `analyze_profile_decay()` returned unexpected statuses  
**Solution**: Mock the async function with controlled return values
```python
from unittest.mock import patch, AsyncMock
from optimizer.decay_detector import DecayStatus

mock_status = DecayStatus(symbol, strategy, status="degraded", reason="Test", stats={})
with patch('optimizer.evolution_engine.analyze_profile_decay', new_callable=AsyncMock) as mock:
    mock.return_value = mock_status
    decision = await engine.evaluate_symbol(symbol)
```

### 2. History Directory Path
**Problem**: Tests created history files but engine couldn't find them  
**Solution**: Pass `history_dir` parameter to `load_history()`
```python
# Before (wrong - uses default path)
history = load_history()

# After (correct - uses test directory)
history_dir = self.base_dir / "logs/performance_history"
history = load_history(history_dir=history_dir)
```

### 3. Threshold Logic
**Problem**: Test with `status="healthy"` and `threshold=["healthy"]` didn't skip  
**Solution**: Thresholds define what TRIGGERS evolution, not what prevents it
```python
# Correct: threshold should be "degraded" to trigger evolution
# Test: mock status="healthy" (not in threshold) → expect SKIP
```

## 📁 Files Added/Modified

### New Files Created
- ✅ `config/evolution.json` - Evolution configuration
- ✅ `optimizer/evolution_engine.py` - Core evolution logic (424 lines)
- ✅ `optimizer/run_evolution.py` - CLI wrapper
- ✅ `tests/test_evolution_engine.py` - Unit tests (401 lines)
- ✅ `MODULE_33_COMPLETE.md` - This documentation

### Modified Files
- ✅ `optimizer/evolution_engine.py` - Fixed history_dir parameter in load_history call

## ✅ Completion Checklist

- [x] Step 1: Created `config/evolution.json` with all required parameters
- [x] Step 2: Created `optimizer/evolution_engine.py` with EvolutionEngine class
- [x] Step 3: Created `optimizer/run_evolution.py` CLI wrapper
- [x] Step 4: Wired into optimizer package (imports work correctly)
- [x] Step 5: Created `tests/test_evolution_engine.py` with 8 test cases
- [x] Step 6: All tests passing (8/8 Module 33, 224/224 full suite)
- [x] Step 7: Documentation complete (this file)
- [x] Verified dry-run mode works correctly
- [x] Verified archiving system works
- [x] Verified audit logging works
- [x] Verified integration with Modules 30-32

## 🚀 Next Steps

### Immediate (Recommended)
1. **Test in dry-run mode**: Run `python -m optimizer.run_evolution` and review logs
2. **Adjust thresholds**: Fine-tune safety filters and improvement thresholds in `config/evolution.json`
3. **Monitor audit logs**: Review `logs/evolution/*.json` for decision patterns

### Future Enhancements (Module 34+)
1. **Multi-strategy support**: Extend beyond `scalping_ema_rsi`
2. **Rollback mechanism**: Restore archived profiles if new ones underperform
3. **Performance monitoring**: Track evolution success rate over time
4. **Notification system**: Alert on profile changes (email, Slack, Discord)
5. **A/B testing**: Run old vs new profile in parallel for validation
6. **Ensemble strategies**: Combine multiple parameter sets
7. **Hyperparameter tuning**: Auto-tune evolution config itself

---

## 📊 Test Results

```
test_evolution_accepts_better_profile .......................... ok
test_evolution_rejects_if_not_degraded ........................ ok
test_evolution_rejects_if_insufficient_improvement ............ ok
test_evolution_rejects_if_drawdown_too_high ................... ok
test_evolution_rejects_if_insufficient_trades ................. ok
test_apply_update_in_dry_run_does_not_modify .................. ok
test_apply_update_archives_and_increments_version ............. ok
test_evolution_log_is_created ................................. ok

----------------------------------------------------------------------
Ran 8 tests in 0.225s

OK
```

**Full Test Suite:**
```
Ran 224 tests in 4.135s

OK (skipped=2)
```

---

**MODULE 33 STATUS: ✅ COMPLETE**

All components implemented, tested, and documented. Evolution engine ready for dry-run testing and gradual rollout to live mode.
