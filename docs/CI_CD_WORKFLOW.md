# CI/CD Workflow Documentation

## Overview

This repository now has a comprehensive CI/CD pipeline that automatically validates code quality, runs tests, and checks security before merging changes to main or staging branches.

## Workflow Jobs

### 1. **ci-test** - Main Testing Suite

Runs on every pull request and push to `main` or `staging` branches.

**Steps:**
- **Code Formatting (Black)**: Checks Python code formatting consistency
  - Currently set to warning mode (non-blocking)
  - Run `black .` locally to auto-format code
  
- **Linting (Flake8)**: Checks for code quality issues
  - Fails on syntax errors and undefined names
  - Provides complexity and style warnings
  
- **Unit Tests (Pytest)**: Runs all test files in `tests/` directory
  - Generates code coverage reports
  - Uploads coverage to Codecov
  
- **Coverage Reporting**: Tracks test coverage over time

### 2. **security-scan** - Security Validation

Validates security and safety parameters.

**Steps:**
- **Risk Parameter Validation**: Runs `scripts/validate_risk_params.py`
  - Checks position sizes are within safe limits
  - Validates stop-loss requirements
  - Ensures leverage limits are not exceeded
  - Verifies max exposure and daily loss limits
  
- **Safety Suite**: Runs the comprehensive safety validation suite
  - Validates accounting invariants
  - Checks for execution discrepancies
  - Tests paper trading consistency
  
- **Secret Scanning**: Checks for hardcoded secrets
  - Searches for API keys, tokens, passwords in code
  - Fails if potential secrets are detected
  
- **Live Trading Gate Check**: Verifies live trading is disabled
  - Ensures `allow_live_trading` is false by default
  - Warns if live trading is enabled

### 3. **integration-test** - Integration Testing

Runs only on PRs to `main` branch (conditional).

**Steps:**
- **Integration Tests**: Runs tests marked with `@pytest.mark.integration`
- **Smoke Backtest**: Runs a quick backtest with `config/smoke_test.yaml`

### 4. **validation-summary** - Results Summary

Summarizes all validation results and provides clear pass/fail status.

## Local Development

### Running Tests Locally

```bash
# Install dependencies
pip install -r requirements.txt
pip install black flake8 pytest pytest-cov

# Run all tests
pytest

# Run specific test file
pytest tests/test_basic.py -v

# Run with coverage
pytest --cov=. --cov-report=html
```

### Code Formatting

```bash
# Check formatting
black --check --diff .

# Auto-format code
black .
```

### Linting

```bash
# Check for critical errors
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Full lint check
flake8 . --count --max-complexity=10 --max-line-length=127 --statistics
```

### Risk Validation

```bash
# Validate risk parameters
python scripts/validate_risk_params.py
```

## Configuration Files

### config/trading_config.example.json

Example configuration with safe default parameters:
- Risk per trade: 1% (conservative)
- Max exposure: 15% of account
- Stop-loss: 1.5 ATR minimum
- Daily loss limit: 2%
- Live trading: disabled by default
- Trailing stops: enabled

Copy this file to customize your own configuration:
```bash
cp config/trading_config.example.json config/my_strategy_config.json
```

## Safety Checks

The CI pipeline enforces these safety requirements:

✅ **Position Sizing**
- Maximum risk per trade: 2%
- Maximum total exposure: 30%
- Minimum position size: $5 USD

✅ **Stop-Loss Requirements**
- Minimum stop-loss distance: 0.5 ATR
- Stop-loss required on all trades

✅ **Leverage Limits**
- Maximum leverage: 3x
- Conservative default: 1x (no leverage)

✅ **Daily Loss Limits**
- Maximum daily loss: 5%
- Trading halts if limit exceeded

✅ **Live Trading Gates**
- Two-factor authentication required
- `allow_live_trading: true` in config
- `LIVE_TRADING_ENABLED=true` environment variable
- Both gates must pass

## Troubleshooting

### Black Formatting Failures

```bash
# Auto-fix formatting issues
black .

# Check which files would be changed
black --check --diff .
```

### Test Failures

```bash
# Run tests with more verbose output
pytest -vv --tb=long

# Run specific failing test
pytest tests/test_specific.py::test_function_name -vv
```

### Risk Validation Failures

If `scripts/validate_risk_params.py` fails:
1. Review error messages for specific parameter violations
2. Check `config/risk.json` and `config/trading_mode.yaml`
3. Ensure values are within safe limits (see safety checks above)
4. Never disable safety checks to make CI pass

### Secret Detection False Positives

If the secret scanner flags false positives:
1. Ensure test files use `test_` prefix
2. Use `.example` suffix for example configs
3. Add `_comment` fields for documentation in JSON/YAML
4. Never commit real secrets - use environment variables

## Best Practices

1. **Run tests locally before pushing**
   ```bash
   pytest && python scripts/validate_risk_params.py
   ```

2. **Format code before committing**
   ```bash
   black .
   ```

3. **Check for critical linting errors**
   ```bash
   flake8 . --select=E9,F63,F7,F82
   ```

4. **Never bypass safety checks**
   - Don't modify risk limits just to pass CI
   - Don't disable security validation
   - Safety checks exist for a reason

5. **Use paper trading first**
   - Always test in paper mode before live
   - Validate strategies with historical data
   - Review safety suite results

## CI Status Badge

Add this to README.md to show CI status:

```markdown
![CI Status](https://github.com/ttdog1020/Cryptobot/workflows/CI%2FCD%20Pipeline/badge.svg)
```

## Support

For issues with the CI/CD pipeline:
1. Check the Actions tab in GitHub for detailed logs
2. Review this documentation
3. Ensure all dependencies are installed locally
4. Verify Python 3.11+ is being used
