"""
Unit tests for nightly paper trading session.

Tests the NightlyPaperSession class to ensure:
- Metrics are always generated and saved to JSON
- Status flags (PASS/WARN) are set correctly
- All required fields are present in metrics
- Summary generation handles missing/malformed metrics gracefully
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
import sys
from io import StringIO

# Add parent directory to path for imports
import os
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_nightly_paper import NightlyPaperSession
from scripts.generate_summary import generate_summary


class TestNightlyPaperSession:
    """Tests for NightlyPaperSession class."""
    
    def test_session_initialization(self):
        """Test that session initializes with correct parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = NightlyPaperSession(
                output_dir=tmpdir,
                duration_minutes=5,
                starting_balance=1000.0
            )
            
            assert session.duration_minutes == 5
            assert session.starting_balance == 1000.0
            assert session.output_dir == Path(tmpdir)
            assert session.deterministic is True
    
    def test_metrics_computation_pass_status(self):
        """Test that metrics with no errors get PASS status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = NightlyPaperSession(
                output_dir=tmpdir,
                duration_minutes=1,
                starting_balance=1000.0
            )
            
            # Manually set counts (simulating execution)
            session.signals_count = 5
            session.trades_count = 3
            session.errors_count = 0
            session.trader.balance = 1050.0  # Profit
            
            metrics = session._compute_metrics()
            
            assert metrics["status"] == "PASS"
            assert metrics["errors"] == 0
            assert metrics["signals"] == 5
            assert metrics["trades"] == 3
            assert metrics["pnl"] == 50.0
            assert metrics["pnl_pct"] == 5.0
            assert metrics["win_rate"] == 60.0  # 3/5
    
    def test_metrics_computation_warn_status(self):
        """Test that metrics with errors get WARN status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = NightlyPaperSession(
                output_dir=tmpdir,
                duration_minutes=1,
                starting_balance=1000.0
            )
            
            session.signals_count = 5
            session.trades_count = 2
            session.errors_count = 2
            session.trader.balance = 1000.0
            
            metrics = session._compute_metrics()
            
            assert metrics["status"] == "WARN"
            assert metrics["errors"] == 2
            assert len(metrics["status_details"]) > 0
            assert any("Errors" in detail for detail in metrics["status_details"])
    
    def test_metrics_required_fields(self):
        """Test that all required fields are present in metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = NightlyPaperSession(
                output_dir=tmpdir,
                duration_minutes=1,
                starting_balance=1000.0
            )
            
            session.errors_count = 0
            session.trader.balance = 1100.0
            metrics = session._compute_metrics()
            
            required_fields = [
                "timestamp",
                "duration_minutes",
                "starting_balance",
                "final_balance",
                "pnl",
                "pnl_pct",
                "signals",
                "trades",
                "errors",
                "deterministic",
                "status",
                "status_details",
                "win_rate"
            ]
            
            for field in required_fields:
                assert field in metrics, f"Missing required field: {field}"
    
    def test_metrics_saved_to_json(self):
        """Test that metrics are saved to JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = NightlyPaperSession(
                output_dir=tmpdir,
                duration_minutes=1,
                starting_balance=1000.0
            )
            
            session.errors_count = 0
            session.trader.balance = 1050.0
            session._compute_metrics()
            session._save_metrics()
            
            metrics_file = Path(tmpdir) / "metrics.json"
            assert metrics_file.exists(), "metrics.json not created"
            
            # Verify it's valid JSON
            with open(metrics_file) as f:
                data = json.load(f)
            
            assert isinstance(data, dict)
            assert "status" in data
    
    def test_win_rate_calculation_zero_signals(self):
        """Test win rate calculation when no signals."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = NightlyPaperSession(output_dir=tmpdir)
            
            session.signals_count = 0
            session.trades_count = 0
            session.errors_count = 0
            
            metrics = session._compute_metrics()
            
            assert metrics["win_rate"] == 0.0
    
    def test_negative_pnl_status_detail(self):
        """Test that large drawdowns are flagged in status details."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = NightlyPaperSession(output_dir=tmpdir, starting_balance=1000.0)
            
            session.signals_count = 5
            session.trades_count = 5
            session.errors_count = 0
            session.trader.balance = 850.0  # 15% loss
            
            metrics = session._compute_metrics()
            
            assert any("drawdown" in detail.lower() for detail in metrics["status_details"])


class TestGenerateSummary:
    """Tests for generate_summary function."""
    
    def test_summary_with_valid_metrics(self):
        """Test summary generation with valid metrics file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create metrics file
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "duration_minutes": 15,
                "starting_balance": 10000.0,
                "final_balance": 10500.0,
                "pnl": 500.0,
                "pnl_pct": 5.0,
                "signals": 10,
                "trades": 8,
                "errors": 0,
                "deterministic": True,
                "status": "PASS",
                "status_details": [],
                "win_rate": 80.0
            }
            
            metrics_file = Path(tmpdir) / "metrics.json"
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f)
            
            summary = generate_summary(tmpdir)
            
            assert "✅ PASS" in summary
            assert "Performance Metrics" in summary
            assert "Trading Activity" in summary
            assert "$10000.00" in summary
            assert "$500.00" in summary
            assert "5.00%" in summary
    
    def test_summary_with_missing_metrics_file(self):
        """Test summary generation when metrics.json is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = generate_summary(tmpdir)
            
            assert "⚠️" in summary
            assert "No metrics found" in summary
    
    def test_summary_with_malformed_json(self):
        """Test summary generation with invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_file = Path(tmpdir) / "metrics.json"
            with open(metrics_file, 'w') as f:
                f.write("{invalid json}")
            
            summary = generate_summary(tmpdir)
            
            assert "⚠️" in summary
            assert "Failed to read metrics" in summary
    
    def test_summary_with_warn_status(self):
        """Test summary generation with WARN status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "duration_minutes": 15,
                "starting_balance": 10000.0,
                "final_balance": 9500.0,
                "pnl": -500.0,
                "pnl_pct": -5.0,
                "signals": 10,
                "trades": 5,
                "errors": 2,
                "deterministic": True,
                "status": "WARN",
                "status_details": ["Errors: 2", "Win rate below 50%"],
                "win_rate": 50.0
            }
            
            metrics_file = Path(tmpdir) / "metrics.json"
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f)
            
            summary = generate_summary(tmpdir)
            
            assert "⚠️ WARN" in summary
            assert "Status Details" in summary
            assert "Errors: 2" in summary
    
    def test_summary_contains_artifacts_section(self):
        """Test that summary includes artifacts information."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "duration_minutes": 15,
                "starting_balance": 10000.0,
                "final_balance": 10000.0,
                "pnl": 0.0,
                "pnl_pct": 0.0,
                "signals": 0,
                "trades": 0,
                "errors": 0,
                "deterministic": True,
                "status": "PASS",
                "status_details": [],
                "win_rate": 0.0
            }
            
            metrics_file = Path(tmpdir) / "metrics.json"
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f)
            
            summary = generate_summary(tmpdir)
            
            assert "Artifacts" in summary
            assert "metrics.json" in summary
            assert "nightly_paper.log" in summary
    
    def test_summary_markdown_formatting(self):
        """Test that summary contains proper markdown formatting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "duration_minutes": 15,
                "starting_balance": 10000.0,
                "final_balance": 10100.0,
                "pnl": 100.0,
                "pnl_pct": 1.0,
                "signals": 5,
                "trades": 4,
                "errors": 0,
                "deterministic": True,
                "status": "PASS",
                "status_details": [],
                "win_rate": 80.0
            }
            
            metrics_file = Path(tmpdir) / "metrics.json"
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f)
            
            summary = generate_summary(tmpdir)
            
            # Check for markdown headers
            assert "## " in summary
            assert "### " in summary
            
            # Check for tables
            assert "| Metric |" in summary
            assert "|--------|" in summary
            
            # Check for bullet points
            assert "- " in summary


class TestNightlySessionIntegration:
    """Integration tests for nightly session."""
    
    def test_session_run_with_deterministic_data(self):
        """Test that session can run with deterministic synthetic data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = NightlyPaperSession(
                output_dir=tmpdir,
                duration_minutes=5,
                deterministic=True,
                starting_balance=5000.0
            )
            
            metrics = session.run()
            
            # Verify metrics are returned
            assert isinstance(metrics, dict)
            assert metrics["starting_balance"] == 5000.0
            assert "status" in metrics
            
            # Verify metrics file was saved
            metrics_file = Path(tmpdir) / "metrics.json"
            assert metrics_file.exists()
    
    def test_metrics_json_readable_after_run(self):
        """Test that metrics JSON is valid and readable after session run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = NightlyPaperSession(
                output_dir=tmpdir,
                duration_minutes=3,
                deterministic=True
            )
            
            session.run()
            
            metrics_file = Path(tmpdir) / "metrics.json"
            with open(metrics_file) as f:
                metrics = json.load(f)
            
            # Verify all required fields
            assert metrics["status"] in ["PASS", "WARN"]
            assert isinstance(metrics["pnl"], float)
            assert isinstance(metrics["trades"], int)
            assert isinstance(metrics["errors"], int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
