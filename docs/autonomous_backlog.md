# Autonomous Development Backlog

**Last Updated:** January 13, 2026  
**Target Completion:** Ongoing (prioritized weekly)  
**Branch:** `staging` (all PRs target staging, merged to main only after manual review)

---

## Triage Summary

Current status of high-value improvements sorted by risk/impact ratio:

| Priority | Category | Item | Risk | Impact | Est. LOC |
|----------|----------|------|------|--------|----------|
| 1 | Reporting | Nightly paper job summary clarity | LOW | HIGH | 100-150 |
| 2 | Risk Modeling | Walk-forward validation harness | LOW | HIGH | 200-300 |
| 3 | Execution | Fee/slippage realism modeling | LOW | MED | 150-200 |
| 4 | Reporting | Live multi-session aggregation | MED | MED | 200-250 |
| 5 | Overfitting | Parameter drift constraint system | MED | HIGH | 250-350 |
| 6 | Ops | Health check aggregator for multi-run | LOW | MED | 100-150 |
| 7 | Evolution | Rollback safeguards for bad parameters | MED | HIGH | 150-250 |
| 8 | Code Cleanup | Remove sweep_v2, exit_sweep, patch scripts | LOW | LOW | 300 lines removed |
| 9 | Testing | Expand core module coverage (>80%) | MED | MED | 400-500 |
| 10 | Config | Consolidate strategy profile management | MED | MED | 150-200 |
| 11 | Validation | Integration test suite for backtest→live pipeline | MED | HIGH | 300-400 |
| 12 | Reporting | Trade journal with regime/confidence tracking | MED | MED | 250-300 |
| 13 | Execution | Partial fill & order rejection handling | MED | HIGH | 200-300 |
| 14 | Safety | Environment variable audit & hardening | LOW | MED | 50-100 |
| 15 | Docs | Runbook for emergency shutdown & recovery | LOW | MED | 100-150 |

---

## Backlog Items (Detailed)

### 1. **Nightly Paper Job Summary Clarity** ✅ [PR1]
**Category:** Reporting  
**Priority:** 1 (HIGH impact, LOW risk)  
**Status:** READY  
**Branch:** `feat/nightly-paper-summary`

**Problem:**
- Current `nightly_paper.yml` generates artifacts but job summary is minimal
- `generate_summary.py` expects `metrics.json` but `run_nightly_paper.py` may not create it consistently
- No clear PASS/FAIL indication in GitHub Actions UI
- Missing key metrics: starting balance, final balance, PnL, return%, win rate, max drawdown

**Acceptance Criteria:**
- [ ] `run_nightly_paper.py` always generates `metrics.json` with complete metrics
- [ ] `generate_summary.py` produces markdown with:
  - Status badge (✅ PASS or ⚠️ FAIL)
  - Key metrics table (balance, PnL, return%, trades, signals, errors)
  - System info (deterministic mode, run duration, timestamp)
  - Link to full artifacts
- [ ] GitHub Actions workflow step publishes summary to `$GITHUB_STEP_SUMMARY`
- [ ] All existing tests pass
- [ ] Ran locally: `pytest` + `python -m validation.safety_suite`

**Files to Touch:**
- `scripts/run_nightly_paper.py` - Ensure metrics.json is always written
- `scripts/generate_summary.py` - Enhance markdown generation
- `.github/workflows/nightly_paper.yml` - Add job summary step
- `tests/test_nightly_session.py` - Add tests for metrics generation

**Estimated LOC:** 100-150 net additions

---

### 2. **Walk-Forward Validation Harness** ✅ [PR2]
**Category:** Risk Modeling / Overfitting Resistance  
**Priority:** 2 (HIGH impact, LOW risk)  
**Status:** READY  
**Branch:** `feat/walk-forward-validation`

**Problem:**
- Current optimizer (`auto_optimizer.py`) trains on full historical period
- No resistance to overfitting; parameters may be tuned to past noise
- No way to test parameter stability across overlapping windows
- Manual walk-forward testing needed; no integrated harness

**Acceptance Criteria:**
- [ ] New module `backtests/walk_forward.py` with:
  - `WalkForwardValidator` class that:
    - Splits data into `train_window` + `test_window` pairs
    - Supports rolling, anchored (expanding), and fixed-gap windows
    - Tracks parameter evolution across windows (drift detection)
    - Detects overfitting (train Sharpe >> test Sharpe)
  - Config support: `walk_forward.yaml` with window sizes, overlap, gap
- [ ] Optionally integrate into `auto_optimizer.py` as post-check
- [ ] `validation/overfitting_check.py` with penalty function:
  - `penalty = max(0, train_sharpe - test_sharpe - tolerance)`
- [ ] Tests in `tests/test_walk_forward.py`:
  - Window splitting correctness
  - Drift detection accuracy
  - Penalty calculation
- [ ] All existing tests pass

**Files to Touch:**
- `backtests/walk_forward.py` (NEW)
- `validation/overfitting_check.py` (NEW)
- `config/walk_forward.yaml` (NEW)
- `tests/test_walk_forward.py` (NEW)
- `auto_optimizer.py` (optional hook)

**Estimated LOC:** 200-300 net additions

---

### 3. **Fee & Slippage Realism Modeling**
**Category:** Execution Modeling  
**Priority:** 3 (MED impact, LOW risk)  
**Status:** READY  
**Branch:** `feat/realistic-fees-slippage`

**Problem:**
- Current `PaperTrader` uses flat commission (0.05%) and fixed slippage (0.05%)
- Real Binance fees vary by volume tier (0.1%, 0.075%, etc.)
- Slippage depends on order size, market depth, volatility
- Spread modeling missing; all fills at mid-price

**Acceptance Criteria:**
- [ ] `execution/fee_schedule.py` with:
  - Binance fee tier lookup (volume-based)
  - Configurable commission structure
  - Dynamic slippage model based on order size % of volume
  - Bid-ask spread simulation
- [ ] `PaperTrader` updated to use fee schedule
- [ ] Config file `config/fees.yaml` for easy tuning
- [ ] Backtests show realistic PnL (~2-5% lower than idealized)
- [ ] All tests pass

**Files to Touch:**
- `execution/fee_schedule.py` (NEW)
- `execution/paper_trader.py` (modify)
- `config/fees.yaml` (NEW)
- `tests/test_fee_schedule.py` (NEW)

**Estimated LOC:** 150-200

---

### 4. **Live Multi-Session Aggregation Report**
**Category:** Reporting  
**Priority:** 4 (MED impact, MED risk)  
**Status:** READY  
**Branch:** `feat/multi-session-aggregator`

**Problem:**
- Current `run_live_multi.py` runs multiple sessions but no unified report
- Hard to see aggregate PnL, correlation, tail risk across sessions
- No dashboard or HTML report; only log files
- Need clear PASS/FAIL on portfolio-level health

**Acceptance Criteria:**
- [ ] `analytics/multi_session_aggregator.py` with:
  - Loads all `equity_*.csv` from logs/ or specified dir
  - Computes aggregate stats: total PnL, combined Sharpe, max DD, VaR
  - Per-session breakdown table
  - Correlation matrix between sessions
  - HTML report with charts (equity curve, drawdown, per-symbol heatmap)
- [ ] Invoked by `run_live_multi.py` automatically at end
- [ ] Config support in `config/live.yaml`
- [ ] All tests pass

**Files to Touch:**
- `analytics/multi_session_aggregator.py` (NEW)
- `run_live_multi.py` (integrate call)
- `tests/test_multi_session_aggregator.py` (NEW)

**Estimated LOC:** 200-250

---

### 5. **Parameter Drift Constraint System**
**Category:** Overfitting Resistance / Evolution  
**Priority:** 5 (HIGH impact, MED risk)  
**Status:** READY  
**Branch:** `feat/parameter-drift-limits`

**Problem:**
- Optimizer may evolve parameters far from human-readable ranges
- No safeguards against absurd values (EMA periods > 200, RSI thresholds outside 0-100)
- No soft constraint to penalize large jumps between generations
- Risk of "unrealistic" optimal parameters that won't hold OOS

**Acceptance Criteria:**
- [ ] `optimizer/drift_monitor.py` with:
  - Parameter bounds definition (hard limits + soft bounds)
  - Drift penalty function: `penalty = sum(abs(p - prev_p) / max_drift)`
  - Tracking of parameter history across generations
  - Health check: flag if >3 params exceed soft bounds
- [ ] Config `config/evolution.json` extended with:
  - `parameter_bounds` section with min/max for each param
  - `max_drift_per_generation` threshold
  - `enable_drift_penalty` flag (default: true)
- [ ] Integrated into `auto_optimizer.py` fitness function
- [ ] Tests for drift calculation and bounds enforcement

**Files to Touch:**
- `optimizer/drift_monitor.py` (NEW)
- `config/evolution.json` (modify)
- `auto_optimizer.py` (integrate)
- `tests/test_drift_monitor.py` (NEW)

**Estimated LOC:** 250-350

---

### 6. **Health Check Aggregator for Multi-Run**
**Category:** Ops & Observability  
**Priority:** 6 (MED impact, LOW risk)  
**Status:** READY  
**Branch:** `feat/health-check-aggregator`

**Problem:**
- No centralized health check for running sessions
- Multi-run scenarios (10+ symbols) hard to monitor for hung processes
- Need clear error surfacing without manual log parsing
- Missing exit code/status propagation for CI

**Acceptance Criteria:**
- [ ] `validation/health_aggregator.py` with:
  - Scans log directory for recent updates
  - Checks for hung processes (no log update > 10 min)
  - Validates equity CSV integrity
  - Summarizes errors per session
  - Returns exit code (0 = healthy, 1 = issues detected)
- [ ] Invoked by `run_live_multi.py` at intervals
- [ ] JSON output for CI consumption
- [ ] Tests for all checks

**Files to Touch:**
- `validation/health_aggregator.py` (NEW)
- `run_live_multi.py` (integrate)
- `tests/test_health_aggregator.py` (NEW)

**Estimated LOC:** 100-150

---

### 7. **Rollback Safeguards for Bad Parameters**
**Category:** Evolution Safety  
**Priority:** 7 (HIGH impact, MED risk)  
**Status:** READY  
**Branch:** `feat/rollback-safeguards`

**Problem:**
- Optimizer may converge on locally-optimal but risky parameters
- No automatic rejection of parameters that violate risk rules
- No rollback to previous best generation if new generation degrades
- Loss of generalizability not caught

**Acceptance Criteria:**
- [ ] `optimizer/rollback_manager.py` with:
  - Track fitness history per generation
  - Detect degradation: `fitness_new < fitness_old - tolerance`
  - Automatic rollback if degradation > threshold
  - Veto rules: reject params if:
    - Max position size > limit
    - Drawdown % > acceptable
    - Sharpe < min threshold
- [ ] Config `config/evolution.json` extended:
  - `enable_rollback` (default: true)
  - `max_generation_degradation` (e.g., 0.05)
  - `veto_rules` section
- [ ] Logging of all rollback decisions
- [ ] Tests

**Files to Touch:**
- `optimizer/rollback_manager.py` (NEW)
- `config/evolution.json` (modify)
- `auto_optimizer.py` (integrate)
- `tests/test_rollback_manager.py` (NEW)

**Estimated LOC:** 150-250

---

### 8. **Code Cleanup: Remove Orphan Scripts**
**Category:** Maintainability  
**Priority:** 8 (LOW impact, LOW risk)  
**Status:** READY  
**Branch:** `chore/cleanup-orphan-scripts`

**Problem:**
- `sweep_v2_params.py`, `sweep_macd_params.py`, `exit_sweep_eth15m.py` not used
- `patch_bot.py`, `patch_strategy_engine.py` one-time migrations
- `add_indicators.py`, `clean_equity.py` redundant utilities
- Clutters root directory and confuses new contributors

**Acceptance Criteria:**
- [ ] Safe removal (backed up in git history):
  - `sweep_v2_params.py`
  - `sweep_macd_params.py`
  - `exit_sweep_eth15m.py`
  - `patch_bot.py`
  - `patch_strategy_engine.py`
  - `add_indicators.py`
  - `clean_equity.py`
- [ ] Move educational demos to `examples/`:
  - `demo_fixed_accounting.py` → `examples/demo_fixed_accounting.py`
  - `demo_scalping_strategy.py` → `examples/demo_scalping_strategy.py`
  - `demo_ml_pipeline.py` → `examples/demo_ml_pipeline.py`
- [ ] All tests still pass
- [ ] README updated if demos referenced

**Files to Remove/Move:** ~1000 LOC removed, 600 LOC moved

---

### 9. **Expand Core Module Testing (>80% coverage)**
**Category:** Quality / Safety  
**Priority:** 9 (MED impact, MED risk)  
**Status:** READY  
**Branch:** `feat/expand-test-coverage`

**Problem:**
- Current coverage ~60% in some core modules
- `risk_management/`, `execution/`, `validation/` have gaps
- Missing integration tests for backtest→live pipeline
- New features require test-first approach

**Acceptance Criteria:**
- [ ] Coverage report: `coverage run -m pytest && coverage html`
- [ ] Target >80% for: `risk_management/`, `execution/`, `validation/`
- [ ] Add regression tests for past bugs
- [ ] Add integration tests:
  - Backtest load → signal gen → position sizing → order placement
  - Paper trader accounting invariants
- [ ] All new code requires tests before PR merge

**Files to Touch:** `tests/` comprehensive expansion

**Estimated LOC:** 400-500

---

### 10. **Consolidate Strategy Profile Management**
**Category:** Config / DevOps  
**Priority:** 10 (MED impact, MED risk)  
**Status:** READY  
**Branch:** `feat/strategy-profile-consolidation`

**Problem:**
- Profiles in both `config/strategy_profiles/` and `strategy_profiles.json` root
- Inconsistent YAML/JSON mixing
- No validation of profile integrity
- Hard to discover available profiles

**Acceptance Criteria:**
- [ ] Unified profile system:
  - Single source of truth: `config/strategy_profiles/` (all YAML)
  - Loader validates each profile against schema
  - Discovery command: `python -m scripts.list_profiles`
- [ ] Migrate root `strategy_profiles.json` → `config/strategy_profiles/default.yaml`
- [ ] Profile schema validation in `validation/config_validator.py`
- [ ] All tests pass, migration tested

**Files to Touch:**
- `config/strategy_profiles/` reorganized
- `validation/config_validator.py` enhanced
- `orchestrator.py` updated loader

**Estimated LOC:** 150-200

---

### 11. **Integration Test Suite for Backtest→Live Pipeline**
**Category:** Safety / Quality  
**Priority:** 11 (HIGH impact, MED risk)  
**Status:** READY  
**Branch:** `feat/backtest-to-live-integration-tests`

**Problem:**
- Backtest and live trading paths diverge; no end-to-end test
- Paper trader ≠ live trader behavior (fees, fills, rejections)
- No validation that backtest results match live runs
- Hard to catch slippage/fee assumptions before live

**Acceptance Criteria:**
- [ ] `tests/integration/test_backtest_to_live.py` with:
  - Run backtest on historical data (1 week)
  - Replay same period with paper trader
  - Compare PnL within tolerance (±5%)
  - Verify trade counts match
  - Check invariants hold end-to-end
- [ ] Synthetic data generator in `validation/synthetic_data.py` enhanced for replay
- [ ] CI runs these tests on every PR

**Files to Touch:**
- `tests/integration/test_backtest_to_live.py` (NEW)
- `validation/synthetic_data.py` (enhance)

**Estimated LOC:** 300-400

---

### 12. **Trade Journal with Regime & Confidence Tracking**
**Category:** Analytics / Reporting  
**Priority:** 12 (MED impact, MED risk)  
**Status:** READY  
**Branch:** `feat/trade-journal-regime-confidence`

**Problem:**
- Current logs only timestamp, side, price, quantity
- No regime context (bull/bear/chop) at trade time
- No confidence level (strong signal vs weak)
- Hard to analyze which markets/regimes trade best

**Acceptance Criteria:**
- [ ] Extended trade log columns:
  - `regime` (BULL/BEAR/CHOP based on regime engine)
  - `confidence` (0.0-1.0, from strategy)
  - `indicator_values` (EMA, RSI, etc.)
  - `equity_drawdown_pct` at trade time
- [ ] `analytics/trade_journal.py` generates detailed report:
  - Win rate by regime
  - Avg profit by confidence level
  - Heatmap: regime × confidence
- [ ] HTML report with sortable table + charts

**Files to Touch:**
- `analytics/trade_journal.py` (NEW)
- `execution/paper_trader.py` (add regime/confidence logging)
- `tests/test_trade_journal.py` (NEW)

**Estimated LOC:** 250-300

---

### 13. **Partial Fill & Order Rejection Handling**
**Category:** Execution / Realism  
**Priority:** 13 (HIGH impact, MED risk)  
**Status:** READY  
**Branch:** `feat/partial-fills-rejections`

**Problem:**
- Paper trader assumes 100% fill; live exchanges reject orders
- No simulation of partial fills (qty < requested)
- No modeling of insufficient balance rejections
- Live trading may experience order cancellations; backtest doesn't

**Acceptance Criteria:**
- [ ] `execution/paper_trader.py` enhanced:
  - Config: `allow_partial_fills` (bool, default: true)
  - Config: `fill_rate` (0.0-1.0, probability of full fill)
  - Reject orders if: balance < cost, position > limit
  - Log all rejections with reason
- [ ] `execution/order_types.py` extended:
  - `PartialFill` status tracking
  - Rejection reason enum
- [ ] Risk engine updated to handle rejections
- [ ] Tests for all rejection scenarios
- [ ] Backtest results should degrade slightly (more realistic)

**Files to Touch:**
- `execution/paper_trader.py` (enhance)
- `execution/order_types.py` (extend)
- `risk_management/risk_engine.py` (handle rejections)
- `tests/test_partial_fills.py` (NEW)

**Estimated LOC:** 200-300

---

### 14. **Environment Variable Audit & Hardening**
**Category:** Safety / Security  
**Priority:** 14 (MED impact, LOW risk)  
**Status:** READY  
**Branch:** `chore/env-var-audit`

**Problem:**
- No centralized env var validation at startup
- Risk of missing required vars (TRADING_MODE, LIVE_TRADING_ENABLED)
- API keys may be passed insecurely
- No audit trail of what env vars were loaded

**Acceptance Criteria:**
- [ ] `validation/env_validator.py` with:
  - Schema defining all required/optional env vars
  - Validation at startup (hard-fail if required missing)
  - Masking of secrets in logs
  - Warning if LIVE_TRADING_ENABLED present
- [ ] All entrypoints (bot.py, orchestrator.py, etc.) call validator
- [ ] Tests for all validation rules
- [ ] Documentation: `.env.example` fully populated

**Files to Touch:**
- `validation/env_validator.py` (NEW)
- `bot.py`, `orchestrator.py` (call validator)
- `.env.example` (update)
- `tests/test_env_validator.py` (NEW)

**Estimated LOC:** 50-100

---

### 15. **Runbook for Emergency Shutdown & Recovery**
**Category:** Ops / Documentation  
**Priority:** 15 (MED impact, LOW risk)  
**Status:** READY  
**Branch:** `docs/emergency-shutdown-runbook`

**Problem:**
- No documented procedure for graceful shutdown
- No recovery steps if bot crashes
- Missing monitoring/alerting setup instructions
- Hard to know what to check if something goes wrong

**Acceptance Criteria:**
- [ ] Create `docs/EMERGENCY_RUNBOOK.md` with:
  - Shutdown procedures (clean stop, forced stop, recovery)
  - Log locations and how to read them
  - Equity/balance validation steps
  - Health check commands
  - Recovery from corrupted state (re-initialize)
  - Escalation procedures (when to alert)
- [ ] Add monitoring setup guide (optional: Prometheus, alerts)
- [ ] Quick reference card (1-page PDF)

**Files to Touch:** `docs/EMERGENCY_RUNBOOK.md` (NEW)

**Estimated LOC:** 100-150 lines of doc

---

## Development Workflow for Agents

### For Each Backlog Item:

1. **Plan (5 min):**
   - Read acceptance criteria
   - Check files to touch
   - Identify dependencies

2. **Implement (30-60 min):**
   - Add/modify code
   - Keep PRs ≤300 LOC net changes
   - Follow existing patterns
   - Add docstrings & type hints

3. **Test (10-20 min):**
   - Write unit tests (new functionality)
   - Run: `pytest` (all tests pass)
   - Run: `python -m validation.safety_suite` (safety checks pass)
   - Run: `python -m backtests.config_backtest --config config/smoke_test.yaml` (backtest works)

4. **PR Submission (5 min):**
   - Branch name: `feat/`, `chore/`, `docs/`, `fix/` as appropriate
   - Title: Descriptive, links to backlog item
   - Description includes:
     - What changed
     - How to validate
     - Risk level (LOW/MED/HIGH)
     - Files changed summary
   - Enable auto-merge if LOW risk and CI passes
   - Flag for manual review if MED/HIGH risk

5. **Monitor & Iterate:**
   - Wait for CI feedback
   - Address any failures
   - Move to next item once PR merged (or after 24h if open)

---

## Notes

- **No PRs to main.** All changes go to `staging` first.
- **Safety first.** If in doubt, keep defaults safe and add config flags.
- **Test coverage matters.** New code requires tests.
- **Config > Code.** Prefer config-driven changes for quick tuning.
- **Documentation.** Update RUNBOOK.md, README, and docstrings as you go.

---

End of Backlog
