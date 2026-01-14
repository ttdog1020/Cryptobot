## Description

<!-- Briefly describe what this PR changes and why -->

**What changed:**
- 
- 
- 

**Why these changes were needed:**


---

## How to Run/Test

<!-- Provide exact commands to test this PR -->

```bash
# Example commands
python -m pytest tests/test_your_feature.py
python -m backtests.config_backtest --config config/your_config.yaml
```

---

## Tests Run/Added

<!-- Check all that apply -->

- [ ] All existing tests pass (`pytest`)
- [ ] Added new unit tests for this feature
- [ ] Safety suite passes (`python -m validation.safety_suite`)
- [ ] Smoke backtest runs successfully
- [ ] Manual testing completed

**New test files:**
- 

---

## Risk Impact

<!-- Select ONE -->

- [ ] **LOW** - Documentation, tests, or monitoring-only changes
- [ ] **MEDIUM** - Strategy logic, config changes, or refactoring with test coverage
- [ ] **HIGH** - Safety limits, execution engine, or risk management changes

**Risk justification:**


---

## Artifacts

<!-- Attach relevant logs, reports, or screenshots -->

**Paper trading report:**
```
# Paste output from analytics/paper_report.py if relevant
```

**Backtest results:**
```
# Paste key metrics if relevant
```

**Other evidence:**


---

## Safety Checklist

<!-- Verify all items before submitting -->

- [ ] No secrets committed (.env, API keys, .pem files)
- [ ] Strategies only return TradeIntent (never place orders directly)
- [ ] No live trading paths enabled (unless explicitly requested in issue)
- [ ] Safety limits unchanged (unless explicitly requested in issue)
- [ ] Code follows existing patterns and conventions
- [ ] Docstrings added to new functions/classes
- [ ] No `print()` statements (using `logger` instead)

---

## Related Issues

<!-- Link to issue(s) this PR addresses -->

Closes #
