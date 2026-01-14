# 📊 METRICS SCORECARD

## Purpose

This document defines **all metrics** collected from backtest runs and nightly paper trading sessions. These metrics are used to:

1. **Validate strategy performance** before evolution/deployment
2. **Monitor system health** in nightly paper runs
3. **Trigger alerts** when thresholds are breached
4. **Generate scorecard summaries** for human review (60 seconds)
5. **Provide audit trail** for parameter changes and rollbacks

---

## Metric Categories

### 1. Financial Performance

| Metric | Description | Formula | Good | Warning | Critical |
|--------|-------------|---------|------|---------|----------|
| **Total PnL ($)** | Absolute profit/loss | `final_balance - starting_balance` | > 0 | < 0 | < -5% of balance |
| **Total PnL (%)** | Percentage return | `(final_balance - starting_balance) / starting_balance * 100` | > 0% | -2% to 0% | < -5% |
| **Max Drawdown (%)** | Largest peak-to-trough decline | `max((peak - trough) / peak * 100)` | < 5% | 5-10% | > 15% |
| **Max Drawdown ($)** | Largest dollar decline | `max(peak - trough)` | < 2% balance | 2-5% | > 10% |
| **Final Balance ($)** | Ending cash balance | From last trade log entry | - | - | < starting * 0.8 |
| **Final Equity ($)** | Balance + open position value | `balance + sum(pos_value)` | - | - | < starting * 0.8 |

### 2. Trade Quality

| Metric | Description | Formula | Good | Warning | Critical |
|--------|-------------|---------|------|---------|----------|
| **Trade Count** | Total closed trades | Count of CLOSE actions | 10-100 | 5-10 or 100-200 | < 5 or > 200 |
| **Win Rate (%)** | Percentage of winning trades | `wins / total_trades * 100` | > 50% | 40-50% | < 35% |
| **Loss Rate (%)** | Percentage of losing trades | `losses / total_trades * 100` | < 50% | 50-60% | > 65% |
| **Avg Win ($)** | Average profit per winning trade | `sum(winning_pnl) / wins` | > avg_loss * 1.5 | > avg_loss | < avg_loss |
| **Avg Loss ($)** | Average loss per losing trade | `sum(losing_pnl) / losses` | Small | Medium | Large |
| **Largest Win ($)** | Single largest winning trade | `max(winning_pnl)` | - | - | Outlier (> 5x avg) |
| **Largest Loss ($)** | Single largest losing trade | `max(losing_pnl)` | Small | Medium | > 3x avg loss |
| **Expectancy** | Expected value per trade | `avg_win * win_rate - avg_loss * loss_rate` | > 0.5 | 0.1-0.5 | < 0 |
| **Risk-Reward Ratio** | Ratio of avg win to avg loss | `avg_win / abs(avg_loss)` | > 2.0 | 1.5-2.0 | < 1.0 |

### 3. R-Multiple Analysis (If Available)

| Metric | Description | Formula | Good | Warning | Critical |
|--------|-------------|---------|------|---------|----------|
| **Avg R-Multiple** | Average R achieved per trade | `avg(pnl / initial_risk)` | > 0.5 | 0-0.5 | < 0 |
| **R-Multiple Std Dev** | Consistency of R outcomes | `std(r_multiples)` | < 2.0 | 2.0-3.0 | > 3.0 |
| **Best R-Multiple** | Largest R achieved | `max(r_multiples)` | > 3R | 2-3R | - |
| **Worst R-Multiple** | Largest R lost | `min(r_multiples)` | > -1R | -1R to -2R | < -2R |

### 4. Execution Quality

| Metric | Description | Formula | Good | Warning | Critical |
|--------|-------------|---------|------|---------|----------|
| **Avg Slippage (%)** | Average slippage per trade | `avg((fill_price - intended_price) / intended_price * 100)` | < 0.05% | 0.05-0.1% | > 0.2% |
| **Total Slippage ($)** | Total slippage cost | `sum(slippage_per_trade)` | < 1% PnL | 1-3% | > 5% |
| **Avg Commission ($)** | Average fee per trade | `total_fees / trade_count` | Low | Medium | > 0.5% per trade |
| **Fee Burn (% of PnL)** | Fees as % of gross profit | `total_fees / gross_profit * 100` | < 10% | 10-20% | > 30% |
| **Fill Rate (%)** | Orders filled vs attempted | `fills / attempts * 100` | 100% | 95-100% | < 90% |

### 5. Risk Management

| Metric | Description | Formula | Good | Warning | Critical |
|--------|-------------|---------|------|---------|----------|
| **Max Position Size (%)** | Largest position as % of equity | `max(position_value / equity * 100)` | < 10% | 10-20% | > 30% |
| **Avg Position Size (%)** | Average position sizing | `avg(position_value / equity * 100)` | 5-10% | 3-5% or 10-15% | < 2% or > 20% |
| **Leverage Used** | Max leverage employed | `max(total_exposure / equity)` | 1.0 (none) | 1.0-2.0 | > 2.0 |
| **Max Concurrent Positions** | Most positions held at once | `max(count(open_positions))` | 1-3 | 3-5 | > 5 |
| **Stop Loss Hit Rate (%)** | % trades stopped out | `stops / total_trades * 100` | 20-40% | 40-60% | > 70% |
| **Take Profit Hit Rate (%)** | % trades hit profit target | `tps / total_trades * 100` | > 40% | 20-40% | < 10% |

### 6. Timing & Duration

| Metric | Description | Formula | Good | Warning | Critical |
|--------|-------------|---------|------|---------|----------|
| **Avg Trade Duration** | Average holding time | `avg(close_time - open_time)` | Matches strategy | - | Outliers |
| **Longest Trade** | Longest held position | `max(close_time - open_time)` | - | - | > 7 days (for scalping) |
| **Shortest Trade** | Quickest closed position | `min(close_time - open_time)` | - | < 1 minute | - |
| **Trades Per Day** | Average daily trade frequency | `total_trades / days` | 5-20 | 20-50 | < 2 or > 100 |
| **Inactive Days** | Days with zero trades | Count | 0 | 1-2 | > 3 |

### 7. System Health

| Metric | Description | Formula | Good | Warning | Critical |
|--------|-------------|---------|------|---------|----------|
| **Error Count** | Total errors logged | Count from logs | 0 | 1-3 | > 5 |
| **Signal Count** | Total signals generated | Count | 20-200 | 10-20 or 200-500 | < 10 or > 500 |
| **Signal→Trade Rate (%)** | Signals converted to trades | `trades / signals * 100` | 20-80% | 10-20% or 80-95% | < 5% or > 95% |
| **Risk Vetoes** | Trades blocked by RiskEngine | Count | 0-5% signals | 5-10% | > 20% |
| **Safety Violations** | Kill switch or safety triggers | Count | **0** | **0** | **> 0** |
| **Execution Time (s)** | Avg time from signal to order | `avg(order_time - signal_time)` | < 1s | 1-5s | > 10s |
| **Session Duration (min)** | Length of backtest/paper run | From start to end timestamp | - | - | - |

### 8. Walk-Forward Validation (Optimizer Only)

| Metric | Description | Formula | Good | Warning | Critical |
|--------|-------------|---------|------|---------|----------|
| **Train Window PnL (%)** | Performance on train data | From train backtest | > 0% | - | - |
| **Test Window PnL (%)** | Performance on test data | From test backtest | > 0% | 0% to -2% | < -5% |
| **Train→Test Degradation (%)** | Performance drop train→test | `(train_pnl - test_pnl) / train_pnl * 100` | < 10% | 10-30% | > 40% |
| **Parameter Stability Score** | Consistency of params across windows | Custom scoring | > 0.7 | 0.5-0.7 | < 0.4 |
| **Test Windows Passing** | Number of OOS windows profitable | Count | 3+ | 2 | < 2 |
| **Overfit Risk Score** | Combined overfit indicators | Composite | < 0.3 | 0.3-0.5 | > 0.5 |

### 9. Per-Symbol Breakdown (Multi-Symbol Only)

For each symbol, track:
- Total PnL ($, %)
- Trade count
- Win rate (%)
- Max drawdown (%)
- Avg trade duration
- Error count

This allows identifying:
- Best/worst performing symbols
- Symbols causing errors
- Symbol-specific parameter drift

---

## Thresholds & Alerts

### Pass/Fail Criteria (Nightly Paper Runs)

A nightly run **PASSES** if ALL of:
- Total PnL % > -2%
- Max Drawdown < 15%
- Win Rate > 35%
- Expectancy > 0
- Error Count = 0
- Safety Violations = 0

A nightly run **FAILS** if ANY of:
- Total PnL % < -5%
- Max Drawdown > 20%
- Win Rate < 30%
- Expectancy < -0.5
- Error Count > 5
- Safety Violations > 0

**Warning Status:** Metrics in warning range but no critical failures.

### Evolution Approval Criteria (Walk-Forward)

New parameters can be auto-applied ONLY if ALL of:
- Test windows passing ≥ 3
- Train→Test degradation < 30%
- Parameter stability > 0.5
- Test PnL % > 0%
- Overfit risk score < 0.5
- Max drawdown (test) < 15%

If ANY threshold fails → **Reject candidate, keep current parameters**.

### Production Eligibility (Staging → Live)

System eligible for live trading ONLY if ALL of (last 30 days):
- Nightly pass rate > 90%
- Avg PnL % > 0%
- Max drawdown < 10%
- Win rate > 45%
- Expectancy > 0.5
- Error count = 0
- Safety violations = 0
- Walk-forward validation passed
- **Human approval obtained**

---

## Data Sources

### Backtest Runs

Metrics computed from:
- Trade log CSV (`logs/trades_*.csv`)
- Columns: timestamp, symbol, action, side, quantity, fill_price, balance, equity, pnl, r_multiple (optional)

### Nightly Paper Runs

Metrics computed from:
- `artifacts/nightly/<date>/trades.csv`
- `artifacts/nightly/<date>/metrics.json`
- Generated by `scripts/run_nightly_paper.py`

### Walk-Forward Runs

Metrics computed from:
- `artifacts/walk_forward/<date>/summary.json`
- Per-window results stored in `artifacts/walk_forward/<date>/windows/`
- Generated by `backtests/walk_forward.py`

---

## Metric Computation Examples

### Python Implementation

```python
import pandas as pd
import numpy as np

def compute_metrics(trades_df: pd.DataFrame) -> dict:
    """
    Compute all metrics from a trades DataFrame.
    
    Args:
        trades_df: DataFrame with columns [timestamp, symbol, action, side, 
                   quantity, fill_price, balance, equity, pnl, r_multiple]
    
    Returns:
        Dictionary with all metrics
    """
    metrics = {}
    
    # Filter for closed trades
    closes = trades_df[trades_df['action'] == 'CLOSE']
    
    if len(closes) == 0:
        return {"error": "No closed trades"}
    
    # Financial performance
    starting_balance = trades_df.iloc[0]['equity']
    final_balance = trades_df.iloc[-1]['balance']
    final_equity = trades_df.iloc[-1]['equity']
    
    metrics['starting_balance'] = starting_balance
    metrics['final_balance'] = final_balance
    metrics['final_equity'] = final_equity
    metrics['total_pnl'] = final_balance - starting_balance
    metrics['total_pnl_pct'] = (final_balance - starting_balance) / starting_balance * 100
    
    # Max drawdown
    equity_series = trades_df['equity']
    cummax = equity_series.cummax()
    drawdown_series = (equity_series - cummax) / cummax * 100
    metrics['max_drawdown_pct'] = abs(drawdown_series.min())
    metrics['max_drawdown_dollars'] = (equity_series - cummax).min()
    
    # Trade quality
    metrics['trade_count'] = len(closes)
    wins = closes[closes['pnl'] > 0]
    losses = closes[closes['pnl'] <= 0]
    
    metrics['wins'] = len(wins)
    metrics['losses'] = len(losses)
    metrics['win_rate'] = len(wins) / len(closes) * 100 if len(closes) > 0 else 0
    metrics['loss_rate'] = len(losses) / len(closes) * 100 if len(closes) > 0 else 0
    
    metrics['avg_win'] = wins['pnl'].mean() if len(wins) > 0 else 0
    metrics['avg_loss'] = losses['pnl'].mean() if len(losses) > 0 else 0
    metrics['largest_win'] = wins['pnl'].max() if len(wins) > 0 else 0
    metrics['largest_loss'] = losses['pnl'].min() if len(losses) > 0 else 0
    
    # Expectancy
    if len(closes) > 0:
        win_rate = len(wins) / len(closes)
        loss_rate = len(losses) / len(closes)
        avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
        avg_loss = abs(losses['pnl'].mean()) if len(losses) > 0 else 0
        metrics['expectancy'] = avg_win * win_rate - avg_loss * loss_rate
        metrics['risk_reward_ratio'] = avg_win / avg_loss if avg_loss > 0 else 0
    else:
        metrics['expectancy'] = 0
        metrics['risk_reward_ratio'] = 0
    
    # R-multiples (if available)
    if 'r_multiple' in closes.columns:
        metrics['avg_r_multiple'] = closes['r_multiple'].mean()
        metrics['r_multiple_std'] = closes['r_multiple'].std()
        metrics['best_r'] = closes['r_multiple'].max()
        metrics['worst_r'] = closes['r_multiple'].min()
    
    # Timing
    if 'timestamp' in closes.columns:
        trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
        duration = (trades_df['timestamp'].max() - trades_df['timestamp'].min()).total_seconds() / 60
        metrics['session_duration_minutes'] = duration
        
        days = duration / 1440  # minutes to days
        metrics['trades_per_day'] = len(closes) / days if days > 0 else 0
    
    return metrics


def check_thresholds(metrics: dict) -> dict:
    """
    Check metrics against thresholds.
    
    Returns:
        Dictionary with status: "PASS" | "WARNING" | "FAIL"
    """
    status = "PASS"
    issues = []
    
    # Critical failures
    if metrics.get('total_pnl_pct', 0) < -5:
        status = "FAIL"
        issues.append("PnL < -5%")
    
    if metrics.get('max_drawdown_pct', 0) > 20:
        status = "FAIL"
        issues.append("Drawdown > 20%")
    
    if metrics.get('win_rate', 100) < 30:
        status = "FAIL"
        issues.append("Win rate < 30%")
    
    if metrics.get('expectancy', 0) < -0.5:
        status = "FAIL"
        issues.append("Expectancy < -0.5")
    
    if metrics.get('error_count', 0) > 5:
        status = "FAIL"
        issues.append("Errors > 5")
    
    # Warnings
    if status == "PASS":
        if -5 <= metrics.get('total_pnl_pct', 0) < -2:
            status = "WARNING"
            issues.append("PnL between -2% and -5%")
        
        if 15 <= metrics.get('max_drawdown_pct', 0) <= 20:
            status = "WARNING"
            issues.append("Drawdown between 15% and 20%")
        
        if 30 <= metrics.get('win_rate', 100) <= 35:
            status = "WARNING"
            issues.append("Win rate between 30% and 35%")
    
    return {
        "status": status,
        "issues": issues,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
```

---

## Scorecard Output Format

### JSON (for programmatic use)

```json
{
  "timestamp": "2026-01-13T03:00:00Z",
  "session_duration_minutes": 15,
  "status": "PASS",
  "issues": [],
  "financial": {
    "starting_balance": 10000.0,
    "final_balance": 10045.23,
    "final_equity": 10045.23,
    "total_pnl": 45.23,
    "total_pnl_pct": 0.45,
    "max_drawdown_pct": 2.3,
    "max_drawdown_dollars": 230.0
  },
  "trades": {
    "trade_count": 12,
    "wins": 8,
    "losses": 4,
    "win_rate": 66.67,
    "loss_rate": 33.33,
    "avg_win": 15.5,
    "avg_loss": -8.2,
    "largest_win": 28.3,
    "largest_loss": -12.1,
    "expectancy": 0.64,
    "risk_reward_ratio": 1.89
  },
  "execution": {
    "avg_slippage_pct": 0.04,
    "total_slippage": 2.1,
    "avg_commission": 0.5,
    "fee_burn_pct": 13.2
  },
  "system": {
    "error_count": 0,
    "signal_count": 45,
    "signal_to_trade_rate": 26.67,
    "risk_vetoes": 2,
    "safety_violations": 0
  }
}
```

### Markdown (for GitHub Actions summary)

```markdown
## 📊 Nightly Paper Trading Scorecard

**Status:** ✅ PASS  
**Date:** 2026-01-13 03:00 UTC  
**Duration:** 15 minutes  

### Financial Performance

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Total PnL | $45.23 (0.45%) | > -2% | ✅ |
| Max Drawdown | 2.3% | < 15% | ✅ |
| Final Equity | $10,045.23 | - | - |

### Trade Quality

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Trade Count | 12 | 10-100 | ✅ |
| Win Rate | 66.67% | > 35% | ✅ |
| Expectancy | 0.64 | > 0 | ✅ |
| Risk-Reward | 1.89 | > 1.0 | ✅ |

### System Health

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Error Count | 0 | 0 | ✅ |
| Safety Violations | 0 | 0 | ✅ |
| Signal→Trade Rate | 26.67% | 10-80% | ✅ |

### Artifacts

- [Trade Log CSV](artifacts/nightly/2026-01-13/trades.csv)
- [Full Metrics JSON](artifacts/nightly/2026-01-13/metrics.json)
- [Performance Report](artifacts/nightly/2026-01-13/report.md)
```

---

## Integration Points

### 1. Nightly Paper Workflow

File: `.github/workflows/nightly_paper.yml`

Updates needed:
```yaml
- name: Generate Scorecard
  run: |
    python analytics/nightly_summary.py \
      --metrics artifacts/nightly/metrics.json \
      --output artifacts/nightly/scorecard.md
    cat artifacts/nightly/scorecard.md >> $GITHUB_STEP_SUMMARY
```

### 2. Walk-Forward Runner

File: `backtests/walk_forward.py`

Compute metrics for each train/test window, then aggregate:
```python
def compute_window_metrics(train_df, test_df):
    train_metrics = compute_metrics(train_df)
    test_metrics = compute_metrics(test_df)
    
    degradation = (train_metrics['total_pnl_pct'] - test_metrics['total_pnl_pct']) / train_metrics['total_pnl_pct'] * 100
    
    return {
        "train": train_metrics,
        "test": test_metrics,
        "degradation_pct": degradation
    }
```

### 3. Evolution Engine

File: `optimizer/evolution_engine.py`

Use metrics to approve/reject candidates:
```python
def approve_candidate(old_metrics, new_metrics, walk_forward_results):
    # Check walk-forward metrics
    if walk_forward_results['test_windows_passing'] < 3:
        return False, "Insufficient test windows"
    
    if walk_forward_results['degradation_pct'] > 30:
        return False, "Excessive train→test degradation"
    
    # Check improvement vs current
    if new_metrics['expectancy'] <= old_metrics['expectancy']:
        return False, "No expectancy improvement"
    
    return True, "Candidate approved"
```

---

## References

- **AUTONOMOUS_ROADMAP.md** - End-state objectives and milestones
- **AGENTS.md** - Safety rules for development
- **MODULE_19_COMPLETE.md** - Paper trade reporting implementation
- **MODULE_20_COMPLETE.md** - Accounting invariants
- **MODULE_33_COMPLETE.md** - Evolution engine implementation

---

**Last Updated:** January 13, 2026  
**Owner:** Autonomous System + Human Oversight
