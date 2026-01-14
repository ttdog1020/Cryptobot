# 🏷️ ISSUE LABELS SCHEMA

## Purpose

This document defines the **label taxonomy** for GitHub issues to enable:

1. **Autonomous agent filtering** - Find issues matching capabilities
2. **Risk assessment** - Identify high-risk changes requiring human review
3. **Module organization** - Route issues to appropriate codebase areas
4. **Priority management** - Surface critical work first
5. **Status tracking** - Monitor issue lifecycle

---

## Label Categories

### 1. Type Labels (Mandatory)

Every issue must have exactly **one** type label:

| Label | Description | Color | Usage |
|-------|-------------|-------|-------|
| `feature` | New feature or enhancement | `#0e8a16` (green) | New capabilities, improvements |
| `bug` | Something isn't working | `#d73a4a` (red) | Crashes, errors, incorrect behavior |
| `refactor` | Code restructuring (no behavior change) | `#fbca04` (yellow) | Cleanup, optimization, tech debt |
| `docs` | Documentation only | `#0075ca` (blue) | README, MODULE_*.md, guides |
| `tests` | Test additions or fixes | `#1d76db` (dark blue) | Unit tests, integration tests |
| `ops` | DevOps, CI/CD, infrastructure | `#5319e7` (purple) | Workflows, scripts, deployment |

---

### 2. Module Labels (Recommended)

Identify the primary module affected (one or more allowed):

| Label | Description | Color | Files |
|-------|-------------|-------|-------|
| `strategy` | Signal generation logic | `#bfdadc` (teal) | `strategies/`, `strategy_profiles/` |
| `execution` | Order placement and management | `#c5def5` (light blue) | `execution/`, `order_types.py` |
| `risk` | Position sizing and vetoes | `#f9d0c4` (peach) | `risk_management/`, `risk.json` |
| `data` | Data feeds, cache, synthetic | `#d4c5f9` (lavender) | `data_feed/`, `validation/synthetic_data.py` |
| `ml` | Machine learning pipelines | `#c2e0c6` (mint) | `ml_pipeline/`, `models/` |
| `optimizer` | Parameter search and evolution | `#fef2c0` (cream) | `optimizer/`, `evolution_engine.py` |
| `backtest` | Historical validation | `#bfd4f2` (sky blue) | `backtests/`, `config_backtest.py` |
| `analytics` | Reporting and metrics | `#d1bcf9` (periwinkle) | `analytics/`, `performance_report.py` |
| `validation` | Safety checks and invariants | `#ffdce5` (pink) | `validation/`, `safety_suite.py` |

---

### 3. Risk Labels (Mandatory for code changes)

Assess safety impact (exactly **one** required for feature/bug):

| Label | Description | Color | Criteria |
|-------|-------------|-------|----------|
| `low-risk` | Safe, isolated change | `#c2e0c6` (mint) | New feature, no changes to safety/risk/execution |
| `medium-risk` | Strategy or optimizer change | `#fbca04` (yellow) | Modifies signal logic, param search, backtest |
| `high-risk` | Risk/execution/safety change | `#d93f0b` (orange-red) | Touches risk management, order placement, gates |
| `critical-risk` | Live trading safety affected | `#b60205` (dark red) | Changes live trading gates, safety monitors |

**Human review required for:** `high-risk`, `critical-risk`

---

### 4. Priority Labels (Optional)

Urgency for implementation:

| Label | Description | Color | SLA |
|-------|-------------|-------|-----|
| `P0` | Critical (blocks other work) | `#b60205` (dark red) | < 24 hours |
| `P1` | High (end-state milestone) | `#d93f0b` (orange-red) | < 1 week |
| `P2` | Medium (nice-to-have) | `#fbca04` (yellow) | < 1 month |
| `P3` | Low (future enhancement) | `#c2e0c6` (mint) | Backlog |

---

### 5. Status Labels (Lifecycle)

Track issue progress:

| Label | Description | Color | When Applied |
|-------|-------------|-------|--------------|
| `needs-triage` | Requires review and labeling | `#d4c5f9` (lavender) | Auto-added by template |
| `ready` | Agent-ready (all fields complete) | `#0e8a16` (green) | After triage |
| `blocked` | Waiting on external dependency | `#d93f0b` (orange-red) | Dependency not resolved |
| `in-progress` | Agent or human actively working | `#0075ca` (blue) | PR opened |
| `needs-review` | Human review required | `#fbca04` (yellow) | High-risk changes |
| `wontfix` | Not planned or out of scope | `#ffffff` (white) | Rejected or deferred |
| `duplicate` | Already exists elsewhere | `#cfd3d7` (gray) | Link to original |

---

### 6. Special Labels

Meta-labels for specific workflows:

| Label | Description | Color | Usage |
|-------|-------------|-------|-------|
| `good-first-issue` | Beginner-friendly | `#7057ff` (violet) | Simple, well-defined tasks |
| `help-wanted` | Community contribution welcome | `#008672` (teal) | Non-critical enhancements |
| `breaking-change` | Requires migration or config update | `#d93f0b` (orange-red) | API changes, config format changes |
| `needs-walkforward` | Requires out-of-sample validation | `#fef2c0` (cream) | Strategy or optimizer changes |
| `security` | Security vulnerability or concern | `#b60205` (dark red) | Secrets, live trading gates |

---

## Labeling Workflow

### Issue Creation (Auto-Applied by Template)

```
New Issue Created
    ↓
Template auto-applies:
- Type label (feature/bug)
- needs-triage
    ↓
Human or Bot Triage:
- Add module label(s)
- Add risk label
- Add priority label
- Change needs-triage → ready
    ↓
Agent picks up issue
```

### Issue Lifecycle

```
ready → in-progress (PR opened) → needs-review (if high-risk) → closed (PR merged)
                                ↓
                          blocked (dependency issue)
```

---

## Examples

### Example 1: Low-Risk Feature

```yaml
Title: "[Feature] Add CSV export to nightly reports"
Labels:
  - feature
  - analytics
  - low-risk
  - P2
  - ready
```

**Rationale:**
- Type: feature (new capability)
- Module: analytics (reporting system)
- Risk: low-risk (no safety impact)
- Priority: P2 (nice-to-have)
- Status: ready (all fields complete)

---

### Example 2: High-Risk Bug

```yaml
Title: "[Bug] RiskEngine allows oversized positions"
Labels:
  - bug
  - risk
  - high-risk
  - P0
  - needs-review
```

**Rationale:**
- Type: bug (broken behavior)
- Module: risk (position sizing)
- Risk: high-risk (affects money management)
- Priority: P0 (critical safety issue)
- Status: needs-review (human approval required)

---

### Example 3: Medium-Risk Refactor

```yaml
Title: "[Refactor] Optimize walk-forward window splitting"
Labels:
  - refactor
  - optimizer
  - backtest
  - medium-risk
  - P2
  - ready
```

**Rationale:**
- Type: refactor (performance improvement)
- Modules: optimizer, backtest (multi-module)
- Risk: medium-risk (optimizer logic changed)
- Priority: P2 (not urgent)
- Status: ready (agent can execute)

---

### Example 4: Critical Security Issue

```yaml
Title: "[Bug] API keys logged in plaintext"
Labels:
  - bug
  - security
  - ops
  - critical-risk
  - P0
  - needs-review
```

**Rationale:**
- Type: bug (security vulnerability)
- Special: security (sensitive)
- Module: ops (logging system)
- Risk: critical-risk (live trading keys exposed)
- Priority: P0 (immediate fix required)
- Status: needs-review (human oversight mandatory)

---

## Label Application Rules

### Mandatory Combinations

| Scenario | Required Labels |
|----------|----------------|
| Feature | `feature`, module, risk, priority |
| Bug | `bug`, module, risk, priority |
| High-risk change | `high-risk` or `critical-risk` + `needs-review` |
| Strategy change | module = `strategy` + `needs-walkforward` |
| Security issue | `security` + `critical-risk` + `P0` |

### Prohibited Combinations

| Invalid | Why |
|---------|-----|
| `feature` + `bug` | Mutually exclusive (choose one) |
| `low-risk` + `needs-review` | Low-risk changes don't need review |
| `P0` + `wontfix` | Critical items shouldn't be rejected |
| `ready` + `needs-triage` | Choose one status |

---

## Automation Rules

### Auto-Applied by Bots

1. **Issue templates** → Auto-add `needs-triage`
2. **PR opened** → Change to `in-progress`
3. **PR merged** → Remove `in-progress`, close issue
4. **Stale (30 days)** → Add `blocked`, comment for update

### GitHub Actions Integration

`.github/workflows/issue_labeler.yml` (future):
```yaml
name: Auto-Label Issues
on:
  issues:
    types: [opened, edited]

jobs:
  label:
    runs-on: ubuntu-latest
    steps:
      - name: Check required fields
        run: |
          # If all required fields present → add "ready"
          # If high-risk → add "needs-review"
          # If touches execution/ or risk/ → add "high-risk"
```

---

## Agent Filter Queries

### Ready Low-Risk Features

```
is:issue is:open label:feature label:low-risk label:ready -label:blocked
```

### High-Risk Items Needing Review

```
is:issue is:open label:high-risk label:needs-review
```

### P0 Critical Issues

```
is:issue is:open label:P0 -label:in-progress
```

### Strategy Changes Requiring Walk-Forward

```
is:issue is:open label:strategy label:needs-walkforward
```

---

## Creating Labels in GitHub

### Bulk Creation Script

```bash
# Create all labels (run in repo root)
# Requires GitHub CLI: https://cli.github.com/

# Type labels
gh label create "feature" --color 0e8a16 --description "New feature or enhancement"
gh label create "bug" --color d73a4a --description "Something isn't working"
gh label create "refactor" --color fbca04 --description "Code restructuring"
gh label create "docs" --color 0075ca --description "Documentation only"
gh label create "tests" --color 1d76db --description "Test additions or fixes"
gh label create "ops" --color 5319e7 --description "DevOps, CI/CD, infrastructure"

# Module labels
gh label create "strategy" --color bfdadc --description "Signal generation logic"
gh label create "execution" --color c5def5 --description "Order placement"
gh label create "risk" --color f9d0c4 --description "Position sizing and vetoes"
gh label create "data" --color d4c5f9 --description "Data feeds, cache, synthetic"
gh label create "ml" --color c2e0c6 --description "Machine learning pipelines"
gh label create "optimizer" --color fef2c0 --description "Parameter search and evolution"
gh label create "backtest" --color bfd4f2 --description "Historical validation"
gh label create "analytics" --color d1bcf9 --description "Reporting and metrics"
gh label create "validation" --color ffdce5 --description "Safety checks and invariants"

# Risk labels
gh label create "low-risk" --color c2e0c6 --description "Safe, isolated change"
gh label create "medium-risk" --color fbca04 --description "Strategy or optimizer change"
gh label create "high-risk" --color d93f0b --description "Risk/execution/safety change"
gh label create "critical-risk" --color b60205 --description "Live trading safety affected"

# Priority labels
gh label create "P0" --color b60205 --description "Critical (blocks other work)"
gh label create "P1" --color d93f0b --description "High (end-state milestone)"
gh label create "P2" --color fbca04 --description "Medium (nice-to-have)"
gh label create "P3" --color c2e0c6 --description "Low (future enhancement)"

# Status labels
gh label create "needs-triage" --color d4c5f9 --description "Requires review and labeling"
gh label create "ready" --color 0e8a16 --description "Agent-ready (all fields complete)"
gh label create "blocked" --color d93f0b --description "Waiting on external dependency"
gh label create "in-progress" --color 0075ca --description "Agent or human actively working"
gh label create "needs-review" --color fbca04 --description "Human review required"
gh label create "wontfix" --color ffffff --description "Not planned or out of scope"
gh label create "duplicate" --color cfd3d7 --description "Already exists elsewhere"

# Special labels
gh label create "good-first-issue" --color 7057ff --description "Beginner-friendly"
gh label create "help-wanted" --color 008672 --description "Community contribution welcome"
gh label create "breaking-change" --color d93f0b --description "Requires migration"
gh label create "needs-walkforward" --color fef2c0 --description "Requires out-of-sample validation"
gh label create "security" --color b60205 --description "Security vulnerability"
```

---

## References

- **Feature Template:** `.github/ISSUE_TEMPLATE/feature.yml`
- **Bug Template:** `.github/ISSUE_TEMPLATE/bug.yml`
- **Autonomous Roadmap:** `docs/AUTONOMOUS_ROADMAP.md`
- **Agent Guidelines:** `AGENTS.md`

---

**Last Updated:** January 13, 2026  
**Maintained By:** Human + Bots
