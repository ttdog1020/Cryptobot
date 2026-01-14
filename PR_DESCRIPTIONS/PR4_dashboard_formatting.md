# PR#4: Dashboard Formatting Utilities

## Overview
Adds formatting utilities to Trade Intelligence for integrating signals with dashboards, webhooks, and terminal displays.

## Changes

### New Module: `dashboard.py`
Added `DashboardFormatter` class with static methods for formatting TradeSignal objects:

1. **Table Formatting**
   - `format_table_row()`: Single signal as dict (pandas-ready)
   - `format_table()`: Multiple signals as list of dicts
   - Columns: Symbol, Timeframe, Direction, Conviction, Bucket, Regime, Agreement, Age, TF Align, Risk Flags

2. **Terminal Display**
   - `format_terminal()`: ANSI-colored console output
   - Color-coded conviction (green/yellow/red)
   - Optional explanation section
   - Emoji-free for accessibility

3. **Discord Integration**
   - `format_discord()`: Embed payload ready for webhook POST
   - Direction-based colors (green LONG, red SHORT, gray FLAT)
   - Inline fields for metrics
   - Optional timeframe alignment and risk flags

4. **Slack Integration**
   - `format_slack()`: Block kit payload
   - Emoji indicators (📈📉➖)
   - Markdown formatting for emphasis
   - Risk warnings highlighted

5. **Summary Statistics**
   - `format_summary()`: Aggregate metrics for signal lists
   - Counts by direction
   - Average conviction
   - High-confidence percentage

6. **Signal Filtering**
   - `filter_actionable()`: Filter signals by criteria
   - Min conviction threshold
   - Exclude/include FLAT signals
   - Max risk flags limit

### Public API Updates
- Added `DashboardFormatter` and `filter_actionable` to `__init__.py` exports
- Updated README with dashboard integration examples

## Testing
- Added 14 new tests covering all formatters and filtering
- All tests pass (335 total)
- Safety suite validated

## Usage Examples

```python
from trade_intelligence import DashboardFormatter, filter_actionable

# Terminal display
print(DashboardFormatter.format_terminal(signal))

# Discord webhook
import requests
embed = DashboardFormatter.format_discord(signal)
requests.post(webhook_url, json={'embeds': [embed]})

# Slack webhook
payload = DashboardFormatter.format_slack(signal)
requests.post(webhook_url, json=payload)

# Pandas DataFrame
import pandas as pd
rows = DashboardFormatter.format_table(signals)
df = pd.DataFrame(rows)
print(df.to_string())

# Filter high-confidence signals with low risk
actionable = filter_actionable(
    signals,
    min_conviction=0.6,
    exclude_flat=True,
    max_risk_flags=1,
)
```

## Backward Compatibility
- New module, no changes to existing code
- Zero impact on signal generation or execution paths
- Purely formatting/display logic

## Risk Assessment
**Risk Level:** Low

- Analysis-only utilities
- Read-only operations
- No execution or trading logic
- No external dependencies (uses stdlib only)
- All safety gates intact

## Documentation
- Updated trade_intelligence/README.md with dashboard section
- Added CHANGELOG.md entry
- Inline docstrings with examples

## Checklist
- [x] Tests pass (14/14 new, 335 total)
- [x] Safety suite passes
- [x] Backward compatible
- [x] No execution paths
- [x] Documentation updated
- [x] Analysis-only (no trading logic)
- [x] JSON-serializable outputs
