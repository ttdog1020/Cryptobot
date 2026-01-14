# 🤖 AUTONOMOUS ROADMAP

## Vision

CryptoBot is an **autonomous, self-improving crypto trading system** designed for hands-off operation with human oversight only at critical decision points. The system evolves strategies safely, detects performance decay, and maintains strict safety boundaries to prevent accidental live trading.

### Dual-Purpose Design

While currently focused on **crypto trading**, the architecture maintains clean boundaries to support future migration to a **stock "signal-only" bot** for Discord alerts. This requires:
- Strategies output `TradeIntent` (symbol, direction, entry, SL, TP, metadata)
- Execution layer converts intents → orders (crypto) or alerts (stocks)
- Risk management operates on intents, not orders
- Data pipelines remain exchange-agnostic

---

## Current State (January 2026)

### ✅ Implemented Capabilities

**Safety & Risk Management:**
- Two-key live trading gate (mode + env var both required)
- Paper-only by default, zero live trading risk
- Strategy → TradeIntent → RiskEngine → ExecutionEngine pipeline
- SafetyMonitor with kill switches and invariant checks
- 256+ unit tests, safety suite validation

**Development Workflow:**
- Protected main branch (manual approval required)
- Auto-merge staging branch (CI passes → merge)
- PR template with test requirements
- GitHub Actions CI: pytest + safety suite + smoke backtest
- Nightly paper trading (deterministic, 03:00 UTC)

**Strategy Infrastructure:**
- ScalpingEMARSI rule-based strategy (12/26 EMA, 14 RSI)
- Profile-based configuration system
- Multi-symbol support with per-symbol profiles
- Synthetic data generator for deterministic testing

**Backtesting & Analysis:**
- Config-driven historical backtest runner
- Paper trade performance reports (PnL, drawdown, R-multiples)
- Accounting invariant validation (cash + equity = total)

**Optimization & Evolution:**
- Parameter search with grid/random/genetic algorithms
- Performance history tracking
- Decay detection (identifies degraded strategies)
- Evolution engine (auto-applies improved parameters)
- Optimizer runs on historical windows

**Data & Execution:**
- PaperTrader with realistic slippage (0.05%) and commission (0.05%)
- CCXT integration for exchange connectivity
- OHLCV caching for faster backtests
- Live data streaming support

---

## End-State Objectives

### 1. Crypto Side: Robust Self-Training System

**Safe Evolution:**
- Walk-forward validation prevents overfitting
- Rolling train/test windows (e.g., 30-day train, 7-day test)
- Overfit detection: parameter stability + train→test degradation
- Auto-apply only when out-of-sample metrics exceed thresholds
- Full audit trail of all parameter changes

**Multi-Strategy Coordination:**
- Portfolio-level risk management
- Strategy correlation analysis
- Ensemble signal voting/weighting
- Strategy health monitoring dashboard
- Auto-disable underperforming strategies

**Operational Resilience:**
- Deterministic nightly paper runs (no live keys)
- 60-second summary dashboard (pass/fail scorecard)
- Auto-rollback on metric failures
- Anomaly detection (volume spikes, fat-finger protection)
- Circuit breakers for cascade failures

**Live Trading Eligibility (Human-Gated):**
- 30+ days stable paper performance
- Walk-forward validation passed
- Max drawdown < 10%
- Win rate > 45%, expectancy > 0
- No safety violations
- Manual human approval required

### 2. Autonomy: Hands-Off Development

**Issue → PR → Deploy Loop:**
- Agent-ready issue templates (objectives, acceptance criteria, files)
- Auto-generated issue backlog from roadmap milestones
- CI gates prevent broken code from merging
- Nightly paper runs validate staging changes
- Human reviews only: summaries, promotion to main, live enablement

**Observable System:**
- Metrics scorecard (PnL, DD, win rate, expectancy, fees, errors)
- Pass/fail thresholds for nightly runs
- Artifact retention (7 days) for forensics
- GitHub Actions job summaries (no external dashboards)
- Alerts only on failures or threshold breaches

**Self-Diagnosis:**
- Automated test coverage reporting
- Performance regression detection
- Dependency vulnerability scanning
- Log analysis for error patterns

### 3. Strategy Quality: Anti-Overfitting Focus

**Walk-Forward Validation:**
- Rolling windows: 30-day train, 7-day test (configurable)
- Out-of-sample performance metrics
- Parameter stability scoring
- Train→test degradation penalty
- Require 3+ positive test windows before apply

**Decay Detection:**
- Compare recent vs historical performance
- Expectancy drift alerts
- Volume/volatility regime shifts
- Auto-trigger re-optimization when degraded

**Safe Retraining:**
- Optimizer locked to train windows only
- Never backtest on test data
- Candidate filtering (min trades, max DD, expectancy > 0)
- Dry-run mode for validation before apply
- Archive old profiles with full metadata

**Guardrails:**
- Reject param changes > 50% deviation from current
- Require human approval for high-risk modules
- Block optimization during high volatility
- Enforce cooldown periods between evolutions

### 4. Future Migration: Stock Signal Bot

**Clean Boundaries:**
- `TradeIntent` interface remains stable
- Strategies agnostic to crypto vs stocks
- Execution layer swappable (orders vs Discord alerts)
- Risk calculations work on price/volatility, not asset type

**Portable Components:**
- `strategies/` → signal generation (reusable)
- `risk_management/` → position sizing (reusable)
- `backtests/` → historical validation (reusable)
- `execution/` → crypto-specific (swap for alert sender)

**Signal-Only Mode:**
- `TradeIntent` → Discord webhook
- Include: symbol, direction, entry, SL, TP, reason, confidence
- No order placement, pure informational
- Rate limiting (max N alerts per day)

---

## Milestones & Timeline

### Phase 1: Overfitting Prevention (Current Priority)

**Goal:** Ensure strategies validated on out-of-sample data before deployment

**Tasks:**
- [x] Walk-forward evaluation framework (`backtests/walk_forward.py`)
- [x] Overfit penalty scoring
- [x] Integration with evolution engine
- [x] Deterministic tests using synthetic data
- [ ] Walk-forward required for evolution approval

**Success Criteria:**
- 3+ test windows pass before param apply
- Train→test performance degradation < 20%
- Parameter stability score > 0.7

**Estimated Completion:** Week 1, January 2026

### Phase 2: Nightly Summary Dashboard (Current Priority)

**Goal:** 60-second review of system health

**Tasks:**
- [x] Define metrics scorecard (PnL, DD, win rate, expectancy, fees, errors)
- [x] Update nightly workflow to generate scorecard
- [x] Add pass/fail thresholds (configurable)
- [x] Linkable artifacts in job summary
- [ ] Alert on failures (optional: email/Slack)

**Success Criteria:**
- Human can review nightly run in < 60 seconds
- Clear pass/fail status
- Actionable alerts on failures

**Estimated Completion:** Week 1, January 2026

### Phase 3: Issue Backlog Automation (Current Priority)

**Goal:** Agent can pick up issues and execute autonomously

**Tasks:**
- [x] Issue templates (feature.yml, bug.yml)
- [x] Labels schema (strategy, execution, risk, ml, ops, low-risk, high-risk)
- [x] Issue generator script (outputs markdown for manual paste)
- [ ] CI enforces issue template compliance

**Success Criteria:**
- All issues have: objective, acceptance criteria, tests, risk level
- Agent can execute without clarifying questions
- Issues link to files/modules

**Estimated Completion:** Week 1, January 2026

### Phase 4: Multi-Strategy Coordination

**Goal:** Portfolio-level optimization and ensemble signals

**Tasks:**
- [ ] Portfolio risk aggregator (cross-strategy exposure)
- [ ] Strategy correlation matrix
- [ ] Ensemble voting/weighting system
- [ ] Portfolio-level backtest runner
- [ ] Dashboard for strategy health

**Success Criteria:**
- Multiple strategies run simultaneously
- Risk allocated across strategies (not duplicated)
- Ensemble signals improve Sharpe vs single strategies

**Estimated Completion:** Week 3-4, January 2026

### Phase 5: Advanced ML Integration

**Goal:** Feature engineering, model training, and prediction pipelines

**Tasks:**
- [ ] Feature pipeline (technical indicators → features)
- [ ] Model training workflow (sklearn/xgboost)
- [ ] Walk-forward validation for ML models
- [ ] Hyperparameter tuning integration
- [ ] Model registry and versioning

**Success Criteria:**
- ML models validated on out-of-sample data
- Feature drift detection
- Model retraining triggered by decay
- A/B testing rule-based vs ML strategies

**Estimated Completion:** Week 5-8, January 2026

### Phase 6: Production Hardening

**Goal:** Live trading readiness (still requires human approval)

**Tasks:**
- [ ] 30-day stable paper performance requirement
- [ ] Live trading checklist enforcement
- [ ] Real-time monitoring dashboard
- [ ] Alerting system (Slack/email)
- [ ] Circuit breakers for cascade failures
- [ ] Order execution optimizations (TWAP, iceberg)

**Success Criteria:**
- System passes all live trading gates
- Human can approve live trading with confidence
- Zero safety violations in 30-day window

**Estimated Completion:** February-March 2026

### Phase 7: Stock Signal Bot Migration

**Goal:** Reuse strategies for Discord stock alerts

**Tasks:**
- [ ] Discord webhook integration
- [ ] Alert formatting (embed with charts)
- [ ] Rate limiting (max N per day)
- [ ] Signal-only execution mode
- [ ] Stock data providers (Polygon, Alpha Vantage)

**Success Criteria:**
- Strategies portable to stock symbols
- Discord alerts sent in real-time
- No code changes required for strategy logic

**Estimated Completion:** Q2 2026

---

## Key Metrics & Targets

### System Health (Nightly Scorecard)

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| Total PnL % | > 0% | < -5% |
| Max Drawdown | < 10% | < 15% |
| Win Rate | > 45% | < 35% |
| Expectancy (avg win / avg loss) | > 1.5 | < 1.0 |
| Trade Count | 10-100/day | < 5 or > 200 |
| Error Count | 0 | > 5 |
| Slippage Impact | < 0.1% per trade | > 0.5% |
| Fee Burn | < 0.2% per day | > 1.0% |

### Walk-Forward Validation

| Metric | Target | Fail Threshold |
|--------|--------|---------------|
| Test Windows Passing | 3+ | < 2 |
| Train→Test Degradation | < 20% | > 40% |
| Parameter Stability | > 0.7 | < 0.4 |
| Out-of-Sample Sharpe | > 1.0 | < 0.5 |

### Development Velocity

| Metric | Target |
|--------|--------|
| PR → Merge Time | < 5 minutes (auto-merge) |
| Issue → PR Time | < 24 hours (for agent) |
| Test Coverage | > 80% |
| CI Pass Rate | > 95% |
| Nightly Pass Rate | > 90% |

---

## Risk Management Philosophy

### Never Compromise Safety

1. **Live trading impossible by default** - Two keys required (config + env var)
2. **Strategies output intents only** - No direct order placement
3. **Risk engine can veto** - But cannot place orders
4. **Test all changes in paper** - 30-day minimum before live consideration
5. **Human approval for live** - No auto-enable of real money

### Fail-Safe Defaults

- Unknown mode → Paper trading
- Missing config → Conservative defaults
- API failure → Flatten positions and stop
- Safety violation → Kill switch activated
- Evolution uncertainty → Keep current parameters

### Audit Everything

- All parameter changes logged with rationale
- Trade history immutable (append-only)
- Performance metrics timestamped
- Walk-forward results archived
- Git commits link to issues

---

## Autonomous Development Workflow

```
┌─────────────────┐
│ Roadmap         │
│ Milestone       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Issue Created   │ ← Auto-generated or manual
│ (Objectives,    │
│  Acceptance,    │
│  Files, Tests)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Agent Picks Up  │ ← Copilot or autonomous agent
│ Issue, Creates  │
│ Feature Branch  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Implements Code │ ← No human intervention
│ + Tests         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Opens PR to     │ ← Auto-targets staging
│ Staging         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ CI Runs         │ ← pytest + safety + backtest
│ (pytest, safety │
│  suite, smoke)  │
└────────┬────────┘
         │
    Pass │ Fail
         ▼         ▼
┌─────────────────┐  ┌──────────┐
│ Auto-Merge      │  │ Agent    │
│ to Staging      │  │ Fixes    │
└────────┬────────┘  └────┬─────┘
         │                │
         ▼                │
┌─────────────────┐       │
│ Nightly Paper   │◄──────┘
│ Run (03:00 UTC) │
└────────┬────────┘
         │
    Pass │ Fail
         ▼         ▼
┌─────────────────┐  ┌──────────┐
│ Human Reviews   │  │ Alert +  │
│ Summary         │  │ Rollback │
│ (60 seconds)    │  └──────────┘
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Manual PR:      │ ← Human approval
│ Staging → Main  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Production      │
│ Deployed        │
└─────────────────┘
```

---

## Documentation Structure

```
docs/
├── AUTONOMOUS_ROADMAP.md     ← This file (vision, milestones, workflow)
├── METRICS_SCORECARD.md      ← Metric definitions and thresholds
├── LABELS.md                 ← Issue label schema
├── PROMOTION_CHECKLIST.md    ← Staging → main requirements
├── WALKFORWARD_GUIDE.md      ← Walk-forward validation details
└── SIGNAL_BOT_SPEC.md        ← Future stock signal bot specification
```

---

## Guardrails for Agents

When working on this repo, autonomous agents must:

1. **Read AGENTS.md first** - Safety rules are non-negotiable
2. **Never enable live trading** - Paper-only unless explicitly requested
3. **All strategies return TradeIntent** - No direct order placement
4. **Add tests for all changes** - Unit + integration + smoke
5. **Run validation suite before PR** - pytest + safety + backtest
6. **Target staging branch** - Not main (auto-merge handles this)
7. **Fill PR template completely** - Objectives, tests, risk, artifacts
8. **Keep changes small** - Max 500 lines per PR for reviewability
9. **Preserve existing tests** - No deletions without justification
10. **Document breaking changes** - Update relevant MODULE_*_COMPLETE.md

---

## Success Indicators

**Month 1 (Current):**
- ✅ Two-key live trading gate enforced
- ✅ CI + nightly paper workflow operational
- ✅ Walk-forward validation framework exists
- ✅ Issue templates ready for agent pickup

**Month 2:**
- [ ] 30+ consecutive nightly paper runs passing
- [ ] Walk-forward validation integrated in evolution
- [ ] Multi-strategy portfolio running
- [ ] Agent has completed 10+ issues autonomously

**Month 3:**
- [ ] Live trading eligibility criteria met (paper performance)
- [ ] Human approves live trading with small capital
- [ ] Zero safety violations in production
- [ ] System self-diagnoses and auto-recovers from failures

**Month 6:**
- [ ] Stock signal bot deployed to Discord
- [ ] Ensemble strategies outperform individual strategies
- [ ] ML models integrated and validated
- [ ] Full autonomous operation (human reviews summaries only)

---

## Contact & Escalation

**For autonomous agents:**
- Stuck on issue? Check existing MODULE_*_COMPLETE.md docs
- Safety question? Refer to AGENTS.md
- Test failure? Run `pytest -vv` and check logs
- Uncertain about change? Create draft PR and tag for human review

**For humans:**
- Review nightly summaries daily (60 seconds)
- Approve staging → main PRs weekly (or on-demand)
- Monitor alerting channels (if configured)
- Approve live trading only after 30-day stable paper run

---

**Last Updated:** January 13, 2026  
**Next Review:** February 1, 2026  
**Owner:** Human + Autonomous Agents
