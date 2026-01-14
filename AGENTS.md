# 🤖 AGENT DEVELOPMENT GUIDELINES

## Overview

This repository is designed for **autonomous agent development** via PR-based workflows. Follow these rules to ensure safe, high-quality contributions.

All PRs should target the **`staging` branch** (not main). Main is protected and requires manual approval.

---

## ⚠️ CRITICAL SAFETY RULES

### 1. **Strategies Output TradeIntent Only**

**NEVER** allow strategies to directly place orders. All strategy code must:
- Return `TradeIntent` objects (signal + metadata)
- Pass through `RiskEngine` for position sizing
- Route through `ExecutionEngine` for order submission
- Be testable without market connections

**Example (CORRECT):**
```python
def generate_signal(self, df):
    if self._is_buy_setup(df):
        return {
            "signal": "LONG",
            "metadata": {
                "entry_price": df.iloc[-1]['close'],
                "sl_distance": 10.0,
                "tp_distance": 30.0,
                "reason": "EMA crossover + RSI oversold"
            }
        }
    return {"signal": "FLAT", "metadata": {}}
```

**Example (WRONG - DO NOT DO THIS):**
```python
def generate_signal(self, df):
    if self._is_buy_setup(df):
        # ❌ WRONG: Direct order placement
        exchange.create_market_order('BTC/USDT', 'buy', 0.01)
```

---

### 2. **Do NOT Enable Live Trading Paths**

Live trading is **DISABLED BY DEFAULT** and requires explicit unlocking:
- `config/trading_mode.yaml` must have `mode: "live"` AND `allow_live_trading: true`
- Environment variable `LIVE_TRADING_ENABLED` must equal `"true"`
- Both gates must pass before `BinanceClient` initializes

**What agents SHOULD do:**
- Develop and test in `paper` or `monitor` mode
- Add features that work in paper trading first
- Document how to enable live trading (but don't enable it)

**What agents MUST NOT do:**
- Modify the two-key safety gate logic
- Auto-enable live trading in configs
- Bypass safety checks
- Initialize exchange clients without gate checks

---

### 3. **All Changes Require Tests**

Before finalizing any PR:
```bash
# Run unit tests
pytest

# Run safety validation
python -m validation.safety_suite

# Run smoke backtest (CI does this automatically)
python -m backtests.config_backtest --config config/smoke_test.yaml
```

**Test Requirements:**
- New strategies: Add strategy-specific tests in `tests/`
- New modules: Add unit tests with >80% coverage
- Bug fixes: Add regression tests
- Refactors: Ensure all existing tests pass

---

### 4. **Never Edit Safety Limits Unless Explicitly Requested**

The following files control safety and should **ONLY** be modified when the issue explicitly requests it:

- `config/risk.json` - Risk management limits
- `config/trading_mode.yaml` - Trading mode and safety thresholds
- `execution/safety.py` - Safety monitor logic
- `risk_management/risk_engine.py` - Position sizing logic

**When in doubt:** Create a new config file instead of modifying safety files.

---

## 📋 Development Workflow

### Step 1: Understand the Issue
- Read the issue description carefully
- Check existing module documentation (`MODULE_*_COMPLETE.md`)
- Review related code in the repo

### Step 2: Implement Changes
- Follow existing code patterns and naming conventions
- Add docstrings to all functions/classes
- Use type hints wherever possible
- Keep functions small and testable

### Step 3: Write Tests
```python
# tests/test_your_feature.py
import pytest
from your_module import YourClass

def test_your_feature():
    obj = YourClass()
    result = obj.your_method(input_data)
    assert result == expected_output
```

### Step 4: Run Validation
```bash
# Full validation sequence
pytest                                  # All unit tests
python -m validation.safety_suite       # Safety checks
python -m backtests.config_backtest --config config/smoke_test.yaml  # Smoke test
```

### Step 5: Create PR
Use the PR template to document:
- What changed
- How to run/test
- Risk impact
- Relevant artifacts (logs, reports)

---

## 🧪 Testing Standards

### Unit Tests (Required)
- Test all public methods
- Test edge cases (None, empty, invalid inputs)
- Use mocks for external dependencies (exchange APIs, file I/O)

### Integration Tests (For Major Features)
- Test end-to-end workflows
- Use synthetic data generators from `validation/synthetic_data.py`
- Verify accounting invariants

### Backtest Validation (For Strategy Changes)
```bash
python -m backtests.config_backtest \
  --config config/your_strategy.yaml \
  --start 2025-01-01 \
  --end 2025-01-31 \
  --symbols BTCUSDT
```

---

## 📁 Repository Structure

```
CryptoBot/
├── strategies/          # Strategy implementations (TradeIntent only!)
├── execution/           # Order routing (DO NOT bypass safety gates)
├── risk_management/     # Position sizing (DO NOT weaken limits)
├── backtests/           # Historical backtesting
├── validation/          # Safety suite and invariants
├── tests/               # Unit and integration tests
├── config/              # Configuration files
│   ├── risk.json        # ⚠️ Safety limits - rarely modify
│   └── trading_mode.yaml # ⚠️ Trading mode gates - rarely modify
└── logs/                # Ignored by git
```

---

## 🚫 Common Mistakes to Avoid

1. **Hardcoding symbols/timeframes** → Use config files
2. **Ignoring test failures** → All tests must pass before PR
3. **Bypassing RiskEngine** → Always use apply_risk_to_signal()
4. **Modifying safety thresholds** → Only if issue explicitly requests it
5. **Committing .env or API keys** → Use .env.example with placeholders
6. **Creating network calls in tests** → Mock external dependencies
7. **Adding print() statements** → Use logger instead

---

## ✅ Checklist Before Submitting PR

- [ ] All tests pass (`pytest`)
- [ ] Safety suite passes (`python -m validation.safety_suite`)
- [ ] Smoke backtest runs successfully
- [ ] No secrets committed (check with `git diff`)
- [ ] PR template filled out completely
- [ ] Code follows existing patterns
- [ ] Docstrings added to new functions/classes
- [ ] No live trading paths enabled
- [ ] Strategy only returns TradeIntent (never places orders directly)

---

## 📚 Documentation

For implementation details, see:
- `MODULE_*_COMPLETE.md` - Module-specific documentation
- `TECH_DEBT_REPORT.md` - Known issues and improvement areas
- `PROJECT_MEMORY.md` - High-level architecture and design decisions

---

## 🆘 Getting Help

If blocked or unsure:
1. Check existing module documentation
2. Review similar implementations in the codebase
3. Ask clarifying questions in the issue thread
4. Run validation tools to catch issues early

---

**Remember: Safety first. Paper trading by default. Real money requires explicit unlocking.**
