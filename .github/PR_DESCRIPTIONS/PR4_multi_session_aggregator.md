# PR4: Live Multi-Session Aggregation & Reporting

**Branch:** `feat/multi-session-aggregator` → `staging`  
**Risk Level:** 🟡 MED  
**Impact:** 🟡 MED  
**Auto-Merge:** ✅ Conditional (after manual testing with equity files)

---

## 📋 Summary

This PR adds comprehensive **portfolio-level aggregation** for multi-session live trading. It solves the problem of managing multiple trading sessions (different symbols) without a unified view:

**Before:**
- 10 separate equity CSV files in logs/
- Manual aggregation required
- No correlation analysis
- No HTML reports
- Missing portfolio metrics (VaR, combined Sharpe)

**After:**
- Automatic discovery and loading of all equity files
- Single-command aggregation into portfolio-level metrics
- Correlation analysis between sessions
- Professional HTML reports with summary tables
- JSON export for CI integration
- Clear pass/fail status for operations

---

## 🏗️ Architecture

### New Module

#### `analytics/multi_session_aggregator.py` (~350 LOC)
Core aggregation engine:

```python
from analytics.multi_session_aggregator import run_aggregation, MultiSessionAggregator

# Simple usage
stats = run_aggregation(equity_dir=Path('logs'))
# Outputs:
#   - logs/aggregation.json (statistics)
#   - logs/aggregation_report.html (visual report)

# Advanced usage
agg = MultiSessionAggregator(Path('logs'))
agg.load_sessions(pattern="equity_*.csv")  # Load all equity files
stats = agg.compute_metrics()               # Aggregate statistics
corr = agg.compute_correlation()            # Session-to-session correlation
agg.export_json(Path('logs/agg.json'))      # Save metrics
agg.generate_html_report()                  # Generate report
```

**Key Methods:**
1. **`load_sessions(pattern)`** - Discover and load equity CSV files
2. **`compute_metrics()`** - Calculate aggregate stats
3. **`compute_correlation()`** - Session correlation matrix
4. **`export_json(path)`** - Export metrics as JSON
5. **`generate_html_report(path)`** - Create HTML summary

**Key Features:**
- **Automatic Discovery**: Finds all `equity_*.csv` files in directory
- **Aggregate Metrics**:
  - Total PnL across all sessions
  - Combined Sharpe ratio
  - Portfolio-level maximum drawdown
  - VaR (95%) and CVaR (95%)
  - Duration and time range
  
- **Per-Session Stats**: Individual metrics for each symbol
- **Correlation Analysis**: Returns correlation matrix between sessions
- **HTML Reporting**: Professional reports with tables and stats
- **JSON Export**: Machine-readable output for automation

#### `tests/test_multi_session_aggregator.py` (~450 LOC)
Comprehensive test coverage:

```python
# Test categories:
pytest tests/test_multi_session_aggregator.py

# Coverage:
- Session loading from CSVs
- Metric computation (PnL, Sharpe, drawdown, VaR)
- Correlation calculation
- JSON/HTML export
- Edge cases (empty dirs, invalid CSVs, single session)
- Negative returns, flat equity
```

**18+ Tests:**
- Load sessions from directory
- Handle invalid/missing CSV files
- Compute Sharpe ratio
- Calculate max drawdown
- Compute Value at Risk (VaR)
- Export to JSON
- Generate HTML reports
- Edge cases and error handling

---

## 📊 Usage Examples

### 1. Default Aggregation (Nightly Jobs)
```python
# Automatically aggregate after nightly run
from analytics.multi_session_aggregator import run_aggregation

stats = run_aggregation()  # Uses logs/ by default
print(f"Total PnL: ${stats['total_pnl']:.2f}")
print(f"Return: {stats['aggregate_return_pct']:.2f}%")
print(f"Sharpe: {stats['combined_sharpe']:.2f}")
```

### 2. Custom Output Paths
```python
stats = run_aggregation(
    equity_dir=Path('logs/2025_01_13'),
    output_json=Path('reports/monthly_agg.json'),
    output_html=Path('reports/monthly_report.html')
)
```

### 3. Advanced Usage
```python
agg = MultiSessionAggregator(Path('logs'))

# Load specific pattern
num_loaded = agg.load_sessions(pattern="equity_LIVE_*.csv")
print(f"Loaded {num_loaded} sessions")

# Compute everything
stats = agg.compute_metrics()
corr = agg.compute_correlation()

# Per-session breakdown
for symbol, metrics in stats['per_session_stats'].items():
    print(f"{symbol}: PnL ${metrics['pnl']:.2f}, Return {metrics['return_pct']:.2f}%")

# Correlation insights
print("\nSession Correlations:")
print(corr)

# Export
agg.export_json(Path('logs/agg.json'))
agg.generate_html_report(Path('logs/report.html'))
```

### 4. Integration with run_live_multi.py
```python
# At end of run_live_multi.py session
from analytics.multi_session_aggregator import run_aggregation

# ... existing trading code ...

# Generate portfolio report
stats = run_aggregation()
if stats['combined_sharpe'] < 1.0:
    print("[WARN] Portfolio Sharpe below threshold")
    exit_code = 1
else:
    print("[OK] Portfolio health check passed")
    exit_code = 0

sys.exit(exit_code)
```

---

## 📈 Output Examples

### JSON Export (`aggregation.json`)
```json
{
  "num_sessions": 3,
  "session_names": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  "total_pnl": 1250.50,
  "aggregate_return_pct": 4.17,
  "combined_sharpe": 1.45,
  "max_drawdown_pct": 8.3,
  "var_95": -0.025,
  "cvar_95": -0.035,
  "per_session_stats": {
    "BTCUSDT": {
      "starting_balance": 10000,
      "final_equity": 10450,
      "pnl": 450,
      "return_pct": 4.5,
      "sharpe_ratio": 1.62,
      "max_drawdown_pct": 5.2
    },
    "ETHUSDT": { ... },
    "SOLUSDT": { ... }
  },
  "generated_at": "2025-01-13T14:30:00"
}
```

### HTML Report
Professional HTML page with:
- Aggregate statistics table
- Per-session breakdown table
- Correlation matrix
- Generated timestamp
- Responsive design

---

## ✅ Acceptance Criteria

- [x] `analytics/multi_session_aggregator.py` implements aggregation
- [x] `MultiSessionAggregator` loads equity CSV files
- [x] Per-session metrics computed correctly
- [x] Aggregate metrics (PnL, Sharpe, DD, VaR) calculated
- [x] Correlation matrix computed for 2+ sessions
- [x] JSON export works
- [x] HTML report generation works
- [x] `tests/test_multi_session_aggregator.py` has 18+ tests
- [x] All tests pass
- [x] Edge cases handled (empty dirs, invalid CSVs)
- [x] CLI interface works (`python analytics/multi_session_aggregator.py <dir>`)

---

## 🚨 Risk Assessment

**Risk Level:** 🟡 **MED**

**Why MED (not LOW):**
- ✅ Does not touch trading logic (read-only aggregation)
- ✅ No changes to live trading execution
- ⚠️ Depends on CSV format staying consistent
- ⚠️ Statistical calculations (Sharpe, VaR) have edge cases

**Failure Modes:**
1. CSV format changes → parsing fails → skip files gracefully
2. Missing sessions → report fewer sessions (not critical)
3. Statistical edge cases → handled with fallbacks

**Mitigation:**
- Comprehensive error handling for CSV parsing
- Graceful degradation when files missing
- Unit tests for all edge cases
- Logs warnings/errors clearly

**Rollback Plan:**
- Simply don't call aggregator in run_live_multi.py
- No state changes, read-only module

---

## 📈 Impact

**Impact:** 🟡 **MED**

**Why MED (valuable but incremental):**

1. **Improved Observability**
   - Portfolio-level metrics previously unavailable
   - Clear pass/fail on combined performance
   - Correlation insights between strategies

2. **Better Ops**
   - Single aggregation step replaces manual work
   - JSON output enables automation
   - HTML reports for stakeholders

3. **Foundation for Future**
   - Enables portfolio-level health checks
   - Supports multi-strategy optimization
   - Basis for auto-stop if portfolio health degrades

4. **Minimal Risk**
   - Pure analysis, no trading changes
   - Read-only aggregation
   - Can be disabled with single line

**Not HIGH Impact Because:**
- Doesn't change strategy execution
- Doesn't affect single-session performance
- Optional feature (non-blocking if fails)

---

## 🧪 Testing

### Run Tests
```bash
# All aggregation tests
pytest tests/test_multi_session_aggregator.py -v

# Expected output:
# test_initialization PASSED
# test_load_sessions PASSED
# test_compute_metrics PASSED
# test_compute_sharpe PASSED
# test_export_json PASSED
# test_export_html PASSED
# ... (18+ tests total)
# ===== 18 passed in 0.45s =====
```

### Manual Testing
```bash
# Create sample equity files
cd logs
echo "timestamp,equity" > equity_TEST1.csv
echo "2025-01-13 09:00:00,10000" >> equity_TEST1.csv
echo "2025-01-13 10:00:00,10100" >> equity_TEST1.csv

# Run aggregation
python -m analytics.multi_session_aggregator logs/

# Check outputs
cat logs/aggregation.json
open logs/aggregation_report.html
```

---

## 🔄 Integration Points

### 1. With run_live_multi.py
```python
# At end of trading loop
from analytics.multi_session_aggregator import run_aggregation

stats = run_aggregation()
logger.info(f"[PORTFOLIO] PnL: ${stats['total_pnl']:.2f}}, Sharpe: {stats['combined_sharpe']:.2f}")

# Optional: check health
if stats['max_drawdown_pct'] > 15:
    logger.warning("[ALERT] Portfolio drawdown exceeded threshold")
```

### 2. With GitHub Actions
```yaml
# nightly_multi_session.yml
- name: Aggregate Results
  if: always()
  run: python -m analytics.multi_session_aggregator logs/

- name: Upload Artifacts
  uses: actions/upload-artifact@v3
  with:
    name: aggregation-report
    path: logs/aggregation_report.html
```

### 3. With CI/CD
```python
# verify_multi_session_health.py
from analytics.multi_session_aggregator import run_aggregation

stats = run_aggregation()

if stats['combined_sharpe'] < 1.0:
    sys.exit(1)  # Fail CI
else:
    sys.exit(0)  # Pass CI
```

---

## 📝 Checklist

Before merging:
- [x] All tests pass
- [x] Edge cases handled
- [x] No breaking changes
- [x] CSV format assumptions documented
- [x] Error handling comprehensive
- [ ] Manual test with real equity files (recommended before merge)
- [ ] Integration with run_live_multi.py documented

---

## 🏷️ Labels

- `enhancement`
- `reporting`
- `analytics`
- `observability`
- `risk:med`
- `impact:med`

---

## 📚 References

- Backlog Item: `docs/autonomous_backlog.md` #4
- Related: PR3 (Realistic Fees), useful for accurate session metrics
- Related: PR2 (Walk-Forward), aggregate metrics can validate strategies

---

## 🎯 Next Steps

After this PR merges:
1. **PR5: Parameter Drift Constraints** - Protect optimizer from unrealistic params
2. **PR6: Health Check Aggregator** - Monitor multi-run liveness
3. **Integration**: Call aggregator from run_live_multi.py
4. **Monitoring**: Add to nightly CI for portfolio health tracking

---

**🤖 Generated by autonomous agent | January 13, 2026**
