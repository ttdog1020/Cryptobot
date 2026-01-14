# PR6: Health Check Aggregator for Multi-Session Monitoring

## Problem
Running multiple concurrent trading sessions with no centralized health monitoring. No way to detect stale sessions, hung processes, or CSV corruption without manual inspection.

## Solution
Implement `HealthAggregator` to scan log directories, validate equity files, detect stale updates, and report overall system health with actionable exit codes.

## Architecture

### Core Classes
- **HealthCheckResult**: Tracks individual session health (status, issues, warnings)
- **SessionHealthMonitor**: Validates single equity file (age, CSV format, row count)
- **HealthAggregator**: Aggregates across all sessions, exports status, returns CI-friendly exit codes

### Key Features
1. **File Liveness Detection**: Warns if equity file >N minutes old (default 30min)
2. **CSV Validation**: Checks required columns, data types, numeric integrity
3. **Row Count Monitoring**: Flags sessions with <10 rows as warnings
4. **Error Aggregation**: Rolls up issues across all sessions
5. **Exit Codes**: 0=healthy, 1=unhealthy (for CI/CD automation)
6. **JSON Export**: Machine-readable status for dashboards

### Integration Points
- **CI/CD**: Use exit code to fail nightly jobs if any session unhealthy
- **Monitoring**: Import HealthAggregator, call check_multi_session_health(), parse JSON status
- **Automation**: Trigger alerts, log rotations, or recovery procedures

## Testing
- 20+ tests covering normal sessions, stale files, CSV corruption, mixed health
- Edge cases: missing files, invalid columns, empty CSVs, low row counts
- 100% function/class coverage

## Risk Assessment
- **Risk Level**: LOW
- **Impact**: HIGH (enables operational visibility)
- **Backward Compatibility**: ✅ No breaking changes
- **Safety**: ✅ No live trading modifications
- **Testing**: ✅ 20+ tests pass

## Example Usage
```python
from validation.health_aggregator import check_multi_session_health

status, report = check_multi_session_health('logs/', max_age_minutes=30)
if status != 0:
    print(f"Session health issues: {report}")
    sys.exit(1)
```

## Files
- `validation/health_aggregator.py` - 600+ LOC
- `tests/test_health_aggregator.py` - 160+ LOC
- No config changes required
