#!/usr/bin/env python3
"""
Issue Generator Script

Generates ready-to-paste GitHub issue bodies from AUTONOMOUS_ROADMAP.md milestones.
No GitHub API required - outputs markdown for manual issue creation.

Usage:
    python scripts/create_issues.py --milestone "Phase 1"
    python scripts/create_issues.py --all
    python scripts/create_issues.py --milestone "Phase 1" --output issues/

Outputs:
    - One markdown file per issue
    - Copy/paste into GitHub issue creation form
    - Pre-filled with objectives, acceptance criteria, files, tests
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Milestone definitions extracted from AUTONOMOUS_ROADMAP.md
MILESTONES = {
    "Phase 1: Overfitting Prevention": {
        "priority": "P1",
        "issues": [
            {
                "title": "[Feature] Walk-Forward Evaluation Framework",
                "objective": "Implement rolling window train/test validation to prevent overfitting",
                "description": """
Implement a walk-forward evaluation framework that validates strategy parameters on out-of-sample data.

**Requirements:**
- Split historical data into rolling train/test windows (e.g., 30-day train, 7-day test)
- Train optimizer on train windows ONLY (no peeking at test data)
- Validate parameters on out-of-sample test windows
- Compute overfit risk score (parameter stability + train→test degradation)
- Output artifacts/walk_forward/<date>/summary.json with all metrics
- Integrate with optimizer/evolution_engine.py for auto-apply decisions

**Why this matters:**
- Prevents strategies from being overfitted to historical data
- Ensures robustness on unseen market conditions
- Critical for safe autonomous evolution
""",
                "acceptance_criteria": [
                    "backtests/walk_forward.py exists with WalkForwardRunner class",
                    "Rolling window logic implemented (configurable train/test sizes)",
                    "Overfit risk score computed (parameter stability + degradation)",
                    "CLI interface: python -m backtests.walk_forward --config <yaml> --windows N",
                    "Integration with optimizer/evolution_engine.py complete",
                    "Unit tests pass using synthetic_data (deterministic)",
                    "artifacts/walk_forward/<date>/summary.json generated",
                    "Documentation: docs/WALKFORWARD_GUIDE.md created",
                    "All existing tests still pass"
                ],
                "validation_commands": [
                    "pytest tests/test_walk_forward.py -v",
                    "python -m backtests.walk_forward --config config/smoke_test.yaml --windows 3",
                    "python -c \"import json; print(json.load(open('artifacts/walk_forward/latest/summary.json')))\"",
                    "pytest",
                    "python -m validation.safety_suite"
                ],
                "files": {
                    "new": [
                        "backtests/walk_forward.py (main implementation, ~400 lines)",
                        "tests/test_walk_forward.py (unit tests)",
                        "docs/WALKFORWARD_GUIDE.md (usage documentation)"
                    ],
                    "modified": [
                        "optimizer/evolution_engine.py (add walk-forward integration)",
                        ".gitignore (add artifacts/walk_forward/)",
                        "docs/AUTONOMOUS_ROADMAP.md (update Phase 1 status)"
                    ]
                },
                "risk": "medium-risk",
                "module": "backtest",
                "labels": ["needs-walkforward"]
            },
            {
                "title": "[Feature] Overfit Penalty Scoring System",
                "objective": "Quantify overfitting risk to block unsafe parameter changes",
                "description": """
Create a scoring system that detects overfitting patterns and prevents evolution engine from applying risky parameter changes.

**Components:**
1. Parameter Stability Score: Measure consistency of optimal params across windows
2. Train→Test Degradation: Quantify performance drop on out-of-sample data
3. Composite Overfit Risk Score: Weighted combination of indicators
4. Threshold-based approval/rejection

**Scoring Logic:**
- Stability = 1 - avg(param_variance) / param_range
- Degradation = (train_pnl - test_pnl) / train_pnl * 100
- Overfit Risk = 0.5 * (1 - stability) + 0.5 * (degradation / 100)
- Reject if: risk > 0.5 OR degradation > 40% OR stability < 0.4
""",
                "acceptance_criteria": [
                    "optimizer/overfit_detector.py exists with scoring functions",
                    "Parameter stability score computed across windows",
                    "Train→test degradation percentage calculated",
                    "Composite overfit risk score (0-1 scale) generated",
                    "Thresholds configurable in config/evolution.json",
                    "Integration with evolution_engine.py approval logic",
                    "Unit tests with synthetic data",
                    "Documentation in MODULE_34_COMPLETE.md"
                ],
                "validation_commands": [
                    "pytest tests/test_overfit_detector.py -v",
                    "python -c \"from optimizer.overfit_detector import compute_overfit_risk; print(compute_overfit_risk([0.8, 0.85, 0.75]))\"",
                    "pytest",
                    "python -m validation.safety_suite"
                ],
                "files": {
                    "new": [
                        "optimizer/overfit_detector.py (scoring functions)",
                        "tests/test_overfit_detector.py (unit tests)"
                    ],
                    "modified": [
                        "optimizer/evolution_engine.py (integrate scoring)",
                        "config/evolution.json (add thresholds)",
                        "docs/METRICS_SCORECARD.md (add overfit metrics)"
                    ]
                },
                "risk": "medium-risk",
                "module": "optimizer"
            }
        ]
    },
    
    "Phase 2: Nightly Summary Dashboard": {
        "priority": "P1",
        "issues": [
            {
                "title": "[Feature] Enhanced Nightly Scorecard with Pass/Fail Thresholds",
                "objective": "Generate 60-second review dashboard with clear pass/fail status",
                "description": """
Upgrade nightly paper trading workflow to generate a comprehensive scorecard with pass/fail thresholds.

**Requirements:**
- Extend analytics/paper_report.py or create analytics/nightly_summary.py
- Compute all metrics from METRICS_SCORECARD.md
- Apply pass/fail thresholds (configurable)
- Generate markdown table for GitHub Actions summary
- Include status indicators (✅ PASS, ⚠️ WARNING, ❌ FAIL)
- Link to artifacts (trades.csv, metrics.json)

**Output Format:**
```markdown
## 📊 Nightly Paper Trading Scorecard

**Status:** ✅ PASS
**Date:** 2026-01-13 03:00 UTC

### Financial Performance
| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Total PnL | $45.23 (0.45%) | > -2% | ✅ |
...
```
""",
                "acceptance_criteria": [
                    "analytics/nightly_summary.py exists (or paper_report.py extended)",
                    "All metrics from METRICS_SCORECARD.md computed",
                    "Pass/fail thresholds applied (configurable in config)",
                    "Markdown output generated with tables and status icons",
                    "CLI: python analytics/nightly_summary.py --metrics <json> --output <md>",
                    ".github/workflows/nightly_paper.yml updated to use new summary",
                    "Deterministic output (same input → same summary)",
                    "Unit tests with mock data"
                ],
                "validation_commands": [
                    "pytest tests/test_nightly_summary.py -v",
                    "python analytics/nightly_summary.py --metrics artifacts/nightly/metrics.json --output test_summary.md",
                    "cat test_summary.md  # Verify format",
                    "pytest",
                    "python -m validation.safety_suite"
                ],
                "files": {
                    "new": [
                        "analytics/nightly_summary.py (scorecard generator)",
                        "tests/test_nightly_summary.py (unit tests)",
                        "config/nightly_thresholds.json (pass/fail thresholds)"
                    ],
                    "modified": [
                        ".github/workflows/nightly_paper.yml (use new summary)",
                        "scripts/run_nightly_paper.py (output more metrics)",
                        "docs/AUTONOMOUS_ROADMAP.md (update Phase 2 status)"
                    ]
                },
                "risk": "low-risk",
                "module": "analytics"
            }
        ]
    },
    
    "Phase 4: Multi-Strategy Coordination": {
        "priority": "P2",
        "issues": [
            {
                "title": "[Feature] Portfolio Risk Aggregator",
                "objective": "Track and limit total exposure across all active strategies",
                "description": """
Implement portfolio-level risk management to prevent over-exposure when multiple strategies run simultaneously.

**Requirements:**
- Aggregate open positions across all strategies
- Compute total exposure (sum of position values)
- Enforce portfolio-level limits (max leverage, max symbols)
- Veto new trades if portfolio limits exceeded
- Track correlation between strategies

**Integration Points:**
- risk_management/risk_engine.py (add portfolio checks)
- orchestrator.py (coordinate multi-strategy execution)
""",
                "acceptance_criteria": [
                    "risk_management/portfolio_risk.py exists",
                    "Total exposure computed across strategies",
                    "Portfolio limits enforced (configurable in config/risk.json)",
                    "Vetoes new trades if limits breached",
                    "Integration with orchestrator.py",
                    "Unit tests with multi-strategy scenarios",
                    "Documentation in MODULE_35_COMPLETE.md"
                ],
                "validation_commands": [
                    "pytest tests/test_portfolio_risk.py -v",
                    "pytest",
                    "python -m validation.safety_suite"
                ],
                "files": {
                    "new": [
                        "risk_management/portfolio_risk.py",
                        "tests/test_portfolio_risk.py"
                    ],
                    "modified": [
                        "risk_management/risk_engine.py (integrate portfolio checks)",
                        "orchestrator.py (pass portfolio state)",
                        "config/risk.json (add portfolio limits)"
                    ]
                },
                "risk": "high-risk",
                "module": "risk"
            }
        ]
    }
}


def generate_issue_markdown(issue: Dict[str, Any], milestone: str, priority: str) -> str:
    """Generate markdown for a GitHub issue."""
    
    md = f"# {issue['title']}\n\n"
    md += f"**Milestone:** {milestone}  \n"
    md += f"**Priority:** {priority}  \n"
    md += f"**Module:** {issue['module']}  \n"
    md += f"**Risk:** {issue['risk']}  \n"
    md += "\n---\n\n"
    
    md += "## Objective\n\n"
    md += f"{issue['objective']}\n\n"
    
    md += "## Detailed Description\n\n"
    md += f"{issue['description'].strip()}\n\n"
    
    md += "## Acceptance Criteria\n\n"
    for criterion in issue['acceptance_criteria']:
        md += f"- [ ] {criterion}\n"
    md += "\n"
    
    md += "## Tests & Validation Commands\n\n"
    md += "```bash\n"
    for cmd in issue['validation_commands']:
        md += f"{cmd}\n"
    md += "```\n\n"
    
    md += "## Files/Modules to Touch\n\n"
    md += "**New files:**\n"
    for f in issue['files']['new']:
        md += f"- {f}\n"
    md += "\n**Modified files:**\n"
    for f in issue['files']['modified']:
        md += f"- {f}\n"
    md += "\n"
    
    md += "## Labels\n\n"
    labels = ["feature", issue['module'], issue['risk'], priority, "ready"]
    if 'labels' in issue:
        labels.extend(issue['labels'])
    md += f"`{' | '.join(labels)}`\n\n"
    
    md += "## Additional Context\n\n"
    md += f"Generated from AUTONOMOUS_ROADMAP.md milestone: **{milestone}**\n\n"
    md += "**References:**\n"
    md += "- docs/AUTONOMOUS_ROADMAP.md\n"
    md += "- docs/METRICS_SCORECARD.md\n"
    md += "- AGENTS.md (safety rules)\n\n"
    
    md += "---\n\n"
    md += f"*Generated by scripts/create_issues.py on {datetime.now().strftime('%Y-%m-%d')}*\n"
    
    return md


def main():
    parser = argparse.ArgumentParser(description="Generate GitHub issues from roadmap milestones")
    parser.add_argument("--milestone", help="Generate issues for specific milestone (e.g., 'Phase 1')")
    parser.add_argument("--all", action="store_true", help="Generate issues for all milestones")
    parser.add_argument("--output", default="issues_generated", help="Output directory for markdown files")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format")
    
    args = parser.parse_args()
    
    if not args.milestone and not args.all:
        print("Error: Must specify --milestone or --all")
        sys.exit(1)
    
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)
    
    milestones_to_process = []
    if args.all:
        milestones_to_process = list(MILESTONES.keys())
    else:
        # Find matching milestone
        for key in MILESTONES.keys():
            if args.milestone.lower() in key.lower():
                milestones_to_process.append(key)
                break
        
        if not milestones_to_process:
            print(f"Error: Milestone '{args.milestone}' not found")
            print(f"Available milestones: {', '.join(MILESTONES.keys())}")
            sys.exit(1)
    
    generated_count = 0
    
    for milestone_name in milestones_to_process:
        milestone_data = MILESTONES[milestone_name]
        priority = milestone_data['priority']
        
        print(f"\n📋 Generating issues for: {milestone_name}")
        print(f"   Priority: {priority}")
        print(f"   Issue count: {len(milestone_data['issues'])}")
        
        for idx, issue in enumerate(milestone_data['issues'], 1):
            # Generate safe filename
            safe_title = issue['title'].replace("[", "").replace("]", "").replace(":", "").replace(" ", "_")
            filename = f"{milestone_name.split(':')[0].replace(' ', '_')}_{idx:02d}_{safe_title[:50]}"
            
            if args.format == "markdown":
                filepath = output_dir / f"{filename}.md"
                content = generate_issue_markdown(issue, milestone_name, priority)
                filepath.write_text(content, encoding='utf-8')
            else:  # json
                filepath = output_dir / f"{filename}.json"
                issue_json = {
                    "title": issue['title'],
                    "milestone": milestone_name,
                    "priority": priority,
                    "body": generate_issue_markdown(issue, milestone_name, priority)
                }
                filepath.write_text(json.dumps(issue_json, indent=2), encoding='utf-8')
            
            print(f"   ✅ {issue['title']}")
            print(f"      → {filepath}")
            generated_count += 1
    
    print(f"\n✨ Generated {generated_count} issues in: {output_dir}/")
    print(f"\nNext steps:")
    print(f"1. Review generated files in {output_dir}/")
    print(f"2. Copy/paste markdown into GitHub issue creation form")
    print(f"3. Apply labels as specified at bottom of each file")
    print(f"4. Agents can now pick up 'ready' issues!")


if __name__ == "__main__":
    main()
