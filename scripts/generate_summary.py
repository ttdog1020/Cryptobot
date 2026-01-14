"""
Generate markdown summary for GitHub Actions job summary.

Usage:
    python scripts/generate_summary.py artifacts/nightly >> $GITHUB_STEP_SUMMARY
"""

import json
import sys
from pathlib import Path

def generate_summary(nightly_dir: str) -> str:
    """Generate markdown summary from nightly run artifacts."""
    
    nightly_path = Path(nightly_dir)
    metrics_file = nightly_path / "metrics.json"
    
    if not metrics_file.exists():
        return "⚠️ No metrics found in nightly run"
    
    with open(metrics_file) as f:
        metrics = json.load(f)
    
    # Build markdown summary
    lines = [
        "# 📊 Nightly Paper Trading Report",
        "",
        f"**Run Time:** {metrics['timestamp']}",
        f"**Duration:** {metrics['duration_minutes']} minutes (simulated)",
        "",
        "## Performance Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Starting Balance | ${metrics['starting_balance']:.2f} |",
        f"| Final Balance | ${metrics['final_balance']:.2f} |",
        f"| PnL | ${metrics['pnl']:.2f} |",
        f"| Return | {metrics['pnl_pct']:.2f}% |",
        "",
        "## Trading Activity",
        "",
        "| Item | Count |",
        "|------|-------|",
        f"| Signals Generated | {metrics['signals']} |",
        f"| Trades Executed | {metrics['trades']} |",
        f"| Errors | {metrics['errors']} |",
        "",
        "## System Info",
        "",
        f"- **Mode:** Deterministic Paper Trading" if metrics['deterministic'] else "- **Mode:** Live Paper Trading",
        f"- **Artifacts Location:** `artifacts/nightly/`",
        "",
    ]
    
    # Add status indicator
    if metrics['errors'] == 0 and metrics['trades'] >= 0:
        lines.append("✅ **Status:** All checks passed")
    else:
        lines.append(f"⚠️ **Status:** {metrics['errors']} error(s) detected")
    
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_summary.py <nightly_dir>")
        sys.exit(1)
    
    summary = generate_summary(sys.argv[1])
    print(summary)
