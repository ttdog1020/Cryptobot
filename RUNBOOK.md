# RUNBOOK: Hands-Off Workflow

## Overview

This repository uses a **hands-off autonomous workflow** with:
- ✅ **Protected main branch** - requires PR + approval + status checks
- ✅ **Staging branch** - auto-merges when CI passes
- ✅ **Nightly paper trading** - automated runs from staging with reports
- ✅ **Paper-only safety** - live trading impossible by default (dual-key gate)

---

## Branches & Flow

```
feature branch → PR (against staging) → CI checks → Merge to staging → Nightly run
                                              ↓
                                        (manual approval)
                                              ↓
                                        Merge to main (protected)
```

### Main Branch
- **Protected:** Yes (requires 1 approval + CI)
- **Purpose:** Production-ready code
- **Access:** Manual PRs with review (not auto-merged)
- **Trigger:** `release/*` tags or manual promotion

### Staging Branch
- **Protected:** Partial (requires CI only)
- **Purpose:** Integration testing + nightly runs
- **Access:** Auto-merge from feature branches when CI passes
- **Trigger:** Nightly paper trading at 03:00 UTC daily

### Feature Branches
- **Naming:** `feature/issue-name`, `fix/issue-name`, `docs/issue-name`
- **Base:** Always branch from `staging`
- **PR Target:** Always create PR against `staging`
- **Delete After Merge:** Yes (auto-cleaned)

---

## Setup (One-Time)

### 1. Create Staging Branch Locally

```bash
cd c:\Projects\CryptoBot
git checkout -b staging main
git push -u origin staging
```

### 2. GitHub UI Configuration

#### Protection for `main` branch:
1. Go to Settings → Branches → Add rule
2. Branch pattern: `main`
3. Check:
   - ✅ Require pull request reviews before merging (1+ reviewer)
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - ✅ Dismiss stale pull request approvals when new commits are pushed
4. Status checks: `CI` (from `.github/workflows/ci.yml`)

#### Protection for `staging` branch:
1. Branch pattern: `staging`
2. Check:
   - ✅ Require status checks to pass
   - ✅ Allow auto-merge (Squash + merge)
   - ✅ Automatically delete head branches
3. Status checks: `CI`

#### Repository Settings:
1. Go to Settings → General → Pull Requests
2. Check: ✅ Allow auto-merge
3. Select: Squash and merge (default)

---

## Creating a PR (Agent/Developer Workflow)

### Step 1: Create Feature Branch

```bash
# Fetch latest from staging
git fetch origin staging
git checkout -b feature/my-feature origin/staging

# Make changes
git add .
git commit -m "Feature: description of changes"
```

### Step 2: Push & Open PR

```bash
git push -u origin feature/my-feature
```

Then in GitHub UI:
1. Click "Create Pull Request"
2. **Target branch:** `staging` (not main)
3. Title: `[FEATURE] Description`
4. Description: Include what changed, how to test, risk level
5. Click "Create Pull Request"

### Step 3: CI Runs Automatically

- Tests run (pytest)
- Safety suite runs
- Smoke backtest runs
- If all pass → PR is eligible to merge

### Step 4: Review & Merge

- **For staging:** Auto-merge enabled (once CI passes)
- **For main:** Manual review required

---

## Nightly Paper Trading

### What Happens

Every night at **03:00 UTC**:

1. Workflow checks out `staging` branch
2. Runs deterministic paper trading session (15 minutes simulated)
3. Uses synthetic data (reproducible, no live keys needed)
4. Generates performance report
5. Uploads artifacts to workflow run
6. Posts summary to GitHub Actions job

### View Results

1. Go to GitHub repo → Actions
2. Find "Nightly Paper Trading" workflow
3. Click latest run
4. Scroll to "paper trading artifacts" artifact
5. Download `nightly-paper-trading.zip`
6. Contents:
   - `trades.csv` - All trades executed
   - `metrics.json` - Session summary
   - `report.md` - Performance markdown report

### Manual Trigger

To run nightly job on-demand:

1. Go to Actions → Nightly Paper Trading
2. Click "Run workflow"
3. (Optional) Set duration and options
4. Click "Run workflow"
5. Wait ~30 seconds for run to start

---

## Safety: Live Trading Gate

### Hard Requirements

Live trading is **disabled by default** and requires:

```yaml
# 1. In config/trading_mode.yaml:
mode: "live"
allow_live_trading: true

# 2. Environment variable (not in config):
export LIVE_TRADING_ENABLED="true"  # Linux/Mac
$env:LIVE_TRADING_ENABLED="true"    # PowerShell
```

### If Live Keys Are Detected in Paper Mode

Program **hard-fails** with clear error:

```
========================================================================
CRITICAL SAFETY ERROR: Live API keys detected in PAPER mode!
========================================================================

Live API keys were found but trading mode is 'paper'.
This is a safety violation - keys should only be present in live mode.

Actions:
  1. Remove API keys from environment/config files
  2. Ensure .env files are in .gitignore
  3. Use paper trading for development and testing

If you need live trading:
  1. Set mode: 'live' in config/trading_mode.yaml
  2. Set allow_live_trading: true in config/trading_mode.yaml
  3. Set environment: export LIVE_TRADING_ENABLED=true

Program will now exit for safety.
========================================================================
```

### Test the Gate Locally

```bash
# Verify paper mode (should succeed)
python run_live.py

# Verify live mode blocked without env var (should force paper)
python run_live.py

# Verify live mode with both gates (uncomment in config if testing)
# export LIVE_TRADING_ENABLED=true
# python run_live.py  # (still needs mode=live in config)
```

---

## Adding Tests

### For New Features

```python
# tests/test_my_feature.py
import pytest
from my_module import MyClass

def test_basic_functionality():
    obj = MyClass()
    result = obj.do_something()
    assert result == expected

def test_edge_case():
    obj = MyClass()
    with pytest.raises(ValueError):
        obj.invalid_input(None)
```

### Running Tests Locally

```bash
# All tests
pytest

# Specific file
pytest tests/test_my_feature.py -v

# With coverage
pytest --cov=my_module tests/

# Safety suite
python -m validation.safety_suite
```

### Before Committing

```bash
# Run full test + safety + backtest
pytest --tb=short
python -m validation.safety_suite
python -m backtests.config_backtest --config config/smoke_test.yaml
```

---

## Monitoring & Debugging

### GitHub Actions

1. Go to Actions tab
2. View workflow runs for:
   - `CI` (on every PR push)
   - `Nightly Paper Trading` (daily at 03:00 UTC)

### View Logs

Each workflow run shows:
- ✅ Passed steps (green)
- ❌ Failed steps (red)
- 📊 Step output (click to expand)

### Artifacts

Click "Artifacts" section on a workflow run to download:
- `nightly-paper-trading.zip` - Paper trading results
- `*-artifact` - Any other artifacts from jobs

---

## Common Tasks

### Push a Hotfix to Main

```bash
# Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/issue-name

# Make fix, test locally
git add .
git commit -m "Hotfix: issue description"
git push -u origin hotfix/issue-name

# In GitHub: Create PR against main (not staging)
# Add label: [HOTFIX]
# Requires manual review + approval
# After merge: backport to staging if needed
```

### Revert a Commit

```bash
# Find commit hash from main branch
git log --oneline

# Create revert PR against main
git checkout -b revert/commit-hash main
git revert commit-hash
git push -u origin revert/commit-hash

# Open PR against main
# Describe reason for revert in description
```

### Sync Staging with Main

```bash
git checkout staging
git pull origin main
git push origin staging
```

---

## CI/CD Checklist

- [ ] All tests pass locally: `pytest`
- [ ] Safety suite passes: `python -m validation.safety_suite`
- [ ] Smoke backtest passes: `python -m backtests.config_backtest --config config/smoke_test.yaml`
- [ ] No new warnings in logs
- [ ] No secrets in diff: `git diff --cached`
- [ ] Commit message is clear and descriptive
- [ ] PR description includes: What changed, How to test, Risk level
- [ ] Tests added for new features

---

## Troubleshooting

### PR Not Auto-Merging to Staging

**Cause:** Status checks not passing
- Check CI job output in Actions
- Fix failing tests locally
- Push fix to PR branch
- CI will re-run automatically

### Nightly Paper Run Fails

**Cause:** Synthetic data generation or missing deps
- Check workflow logs in Actions
- Verify all dependencies in `requirements.txt`
- Run locally: `python scripts/run_nightly_paper.py --duration-minutes 5`

### Live Trading Accidentally Enabled

**Danger:** Immediate manual action required
1. Kill any running processes: `Ctrl+C`
2. Revert config changes: `git checkout config/trading_mode.yaml`
3. Unset env var: `unset LIVE_TRADING_ENABLED` (Linux/Mac) or `Remove-Item env:LIVE_TRADING_ENABLED` (PowerShell)
4. Contact team

---

## Support

For issues or questions:
1. Check AGENTS.md for development guidelines
2. Review module documentation (MODULE_*_COMPLETE.md)
3. Check existing GitHub issues
4. Create new issue with: What, Expected, Actual, Steps to reproduce

