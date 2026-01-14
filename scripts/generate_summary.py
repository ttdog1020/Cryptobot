"""
Generate markdown summary for GitHub Actions job summary.

Reads metrics.json from nightly artifacts and produces a formatted
markdown summary with status badge, key metrics, and links to artifacts.

Usage:
    python scripts/generate_summary.py artifacts/nightly >> $GITHUB_STEP_SUMMARY
    python scripts/generate_summary.py artifacts/nightly --output summary.md
"""

import json
import sys
from pathlib import Path
from typing import Optional


def generate_summary(nightly_dir: str) -> str:
    """
    Generate markdown summary from nightly run artifacts.
    
    Args:
        nightly_dir: Path to artifacts directory containing metrics.json
        
    Returns:
        Formatted markdown string suitable for GitHub Actions job summary
    """
    
    nightly_path = Path(nightly_dir)
    metrics_file = nightly_path / "metrics.json"
    
    if not metrics_file.exists():
        return "⚠️ **Status:** No metrics found in nightly run - check job logs for errors"
    
    try:
        with open(metrics_file) as f:
            metrics = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return f"⚠️ **Status:** Failed to read metrics: {e}"
    
    # Status badge
    status = metrics.get("status", "UNKNOWN")
    if status == "PASS":
        status_badge = "✅ PASS"
        emoji = "✅"
    else:
        status_badge = "⚠️ WARN"
        emoji = "⚠️"
    
    # Build markdown summary
    lines = [
        f"## {emoji} Nightly Paper Trading Report",
        "",
        f"**Status:** {status_badge}",
        f"**Run Time:** {metrics.get('timestamp', 'N/A')}",
        f"**Duration:** {metrics.get('duration_minutes', 'N/A')} minutes (simulated)",
        f"**Mode:** {'Deterministic' if metrics.get('deterministic') else 'Stochastic'}",
        "",
    ]
    
    # Performance Metrics
    lines.extend([
        "### 📊 Performance Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Starting Balance | ${metrics.get('starting_balance', 0):.2f} |",
        f"| Final Balance | ${metrics.get('final_balance', 0):.2f} |",
        f"| PnL | ${metrics.get('pnl', 0):.2f} |",
        f"| Return % | {metrics.get('pnl_pct', 0):.2f}% |",
        "",
    ])
    
    # Trading Activity
    lines.extend([
        "### 📈 Trading Activity",
        "",
        "| Item | Count |",
        "|------|-------|",
        f"| Signals Generated | {metrics.get('signals', 0)} |",
        f"| Trades Executed | {metrics.get('trades', 0)} |",
        f"| Win Rate | {metrics.get('win_rate', 0):.1f}% |",
        f"| Errors | {metrics.get('errors', 0)} |",
        "",
    ])
    
    # Status Details
    status_details = metrics.get("status_details", [])
    if status_details:
        lines.extend([
            "### ⚠️ Status Details",
            "",
        ])
        for detail in status_details:
            lines.append(f"- {detail}")
        lines.append("")
    
    # System Info
    lines.extend([
        "### 🔧 System Info",
        "",
        f"- **Artifact Location:** `artifacts/nightly/`",
        f"- **Logs:** Check job logs for detailed execution trace",
        "",
    ])
    
    # Artifacts note
    lines.extend([
        "### 📦 Artifacts",
        "",
        "The following artifacts are available for download:",
        "- `metrics.json` - This metrics summary",
        "- `nightly_paper.log` - Detailed execution log",
        "- `trades.csv` - Trade log (if trades executed)",
        "",
    ])
    
    return "\n".join(lines)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate GitHub Actions job summary from nightly metrics"
    )
    parser.add_argument(
        "nightly_dir",
        help="Path to nightly artifacts directory"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Optional: write to file instead of stdout"
    )
    
    args = parser.parse_args()
    
    summary = generate_summary(args.nightly_dir)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(summary)
        print(f"Summary written to {args.output}")
    else:
        print(summary)


if __name__ == "__main__":
    main()
