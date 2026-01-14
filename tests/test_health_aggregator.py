"""
Tests for health check aggregator.

Tests:
- Session liveness monitoring
- File age detection
- CSV validation
- Error aggregation
- Exit code generation
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

from validation.health_aggregator import (
    HealthAggregator, SessionHealthMonitor, HealthCheckResult,
    check_multi_session_health
)


class TestHealthCheckResult:
    """Tests for HealthCheckResult."""
    
    def test_initialization(self):
        """Test result initialization."""
        result = HealthCheckResult("BTCUSDT")
        
        assert result.session_name == "BTCUSDT"
        assert result.is_healthy == True
        assert len(result.issues) == 0
        assert len(result.warnings) == 0
    
    def test_add_issue(self):
        """Test adding issue."""
        result = HealthCheckResult("BTCUSDT")
        
        result.add_issue("Test issue")
        
        assert not result.is_healthy
        assert len(result.issues) == 1
        assert result.issues[0] == "Test issue"
    
    def test_add_warning(self):
        """Test adding warning."""
        result = HealthCheckResult("BTCUSDT")
        
        result.add_warning("Test warning")
        
        assert result.is_healthy  # Warning doesn't mark unhealthy
        assert len(result.warnings) == 1
    
    def test_to_dict(self):
        """Test converting to dictionary."""
        result = HealthCheckResult("BTCUSDT")
        result.add_issue("Test issue")
        result.file_age_minutes = 5
        result.num_rows = 100
        
        result_dict = result.to_dict()
        
        assert result_dict['session_name'] == "BTCUSDT"
        assert not result_dict['is_healthy']
        assert result_dict['file_age_minutes'] == 5
        assert result_dict['num_rows'] == 100


class TestSessionHealthMonitor:
    """Tests for SessionHealthMonitor."""
    
    @pytest.fixture
    def temp_equity_csv(self):
        """Create temporary equity CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create valid equity CSV
            data = {
                'timestamp': [
                    datetime.now() - timedelta(minutes=i) for i in range(10)
                ],
                'equity': [10000 + i*100 for i in range(10)]
            }
            df = pd.DataFrame(data)
            equity_file = tmpdir / "equity_BTCUSDT.csv"
            df.to_csv(equity_file, index=False)
            
            yield equity_file
    
    def test_check_healthy_file(self, temp_equity_csv):
        """Test checking healthy equity file."""
        monitor = SessionHealthMonitor(temp_equity_csv, max_age_minutes=10)
        
        result = monitor.check()
        
        assert result.is_healthy
        assert result.csv_valid
        assert result.num_rows == 10
        assert result.file_size_bytes > 0
    
    def test_check_missing_file(self):
        """Test checking missing file."""
        monitor = SessionHealthMonitor(Path("nonexistent.csv"))
        
        result = monitor.check()
        
        assert not result.is_healthy
        assert len(result.issues) > 0
    
    def test_check_stale_file(self):
        """Test detecting stale file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create CSV
            data = {
                'timestamp': [datetime.now()],
                'equity': [10000]
            }
            df = pd.DataFrame(data)
            equity_file = tmpdir / "equity_TEST.csv"
            df.to_csv(equity_file, index=False)
            
            # Check with very strict age threshold
            monitor = SessionHealthMonitor(equity_file, max_age_minutes=0)
            
            result = monitor.check()
            
            # Should be flagged as stale
            assert not result.is_healthy
            assert any('stale' in issue.lower() for issue in result.issues)
    
    def test_check_invalid_csv_missing_columns(self):
        """Test detecting invalid CSV (missing columns)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create CSV with wrong columns
            data = {'timestamp': [datetime.now()], 'price': [50000]}
            df = pd.DataFrame(data)
            equity_file = tmpdir / "equity_TEST.csv"
            df.to_csv(equity_file, index=False)
            
            monitor = SessionHealthMonitor(equity_file)
            result = monitor.check()
            
            assert not result.is_healthy
            assert not result.csv_valid
    
    def test_check_empty_csv(self):
        """Test detecting empty CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create empty file
            equity_file = tmpdir / "equity_TEST.csv"
            equity_file.write_text("")
            
            monitor = SessionHealthMonitor(equity_file)
            result = monitor.check()
            
            assert not result.is_healthy
            assert not result.csv_valid
    
    def test_check_low_row_count_warning(self):
        """Test warning for low row count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create CSV with few rows
            data = {
                'timestamp': [datetime.now()],
                'equity': [10000]
            }
            df = pd.DataFrame(data)
            equity_file = tmpdir / "equity_TEST.csv"
            df.to_csv(equity_file, index=False)
            
            # High minimum expected rows
            monitor = SessionHealthMonitor(equity_file, min_expected_rows=100)
            result = monitor.check()
            
            assert result.is_healthy  # Warning, not issue
            assert len(result.warnings) > 0


class TestHealthAggregator:
    """Tests for HealthAggregator."""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory with equity files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create 2 healthy CSVs
            for symbol in ['BTCUSDT', 'ETHUSDT']:
                data = {
                    'timestamp': [datetime.now() - timedelta(minutes=i) for i in range(10)],
                    'equity': [10000 + i*100 for i in range(10)]
                }
                df = pd.DataFrame(data)
                df.to_csv(tmpdir / f"equity_{symbol}.csv", index=False)
            
            yield tmpdir
    
    def test_initialization(self):
        """Test aggregator initialization."""
        agg = HealthAggregator(Path("logs"), max_age_minutes=10)
        
        assert agg.log_dir == Path("logs")
        assert agg.max_age_minutes == 10
    
    def test_run_with_files(self, temp_log_dir):
        """Test running aggregator with equity files."""
        agg = HealthAggregator(temp_log_dir)
        
        status = agg.run()
        
        assert status['num_sessions'] == 2
        assert status['healthy_sessions'] == 2
        assert status['overall_status'] == 'HEALTHY'
        assert status['exit_code'] == 0
    
    def test_run_missing_directory(self):
        """Test running with missing directory."""
        agg = HealthAggregator(Path("/nonexistent/dir"))
        
        status = agg.run()
        
        assert status['overall_status'] == 'UNHEALTHY'
        assert status['exit_code'] == 1
    
    def test_run_no_files(self):
        """Test running with no equity files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agg = HealthAggregator(Path(tmpdir))
            
            status = agg.run()
            
            assert status['num_sessions'] == 0
            assert status['overall_status'] == 'UNHEALTHY'
    
    def test_unhealthy_detection(self):
        """Test detecting unhealthy sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create unhealthy CSV (missing column)
            data = {'timestamp': [datetime.now()], 'price': [50000]}
            df = pd.DataFrame(data)
            df.to_csv(tmpdir / "equity_BAD.csv", index=False)
            
            agg = HealthAggregator(tmpdir)
            status = agg.run()
            
            assert status['unhealthy_sessions'] == 1
            assert status['overall_status'] == 'UNHEALTHY'
            assert status['exit_code'] == 1
    
    def test_mixed_healthy_unhealthy(self):
        """Test with mix of healthy and unhealthy sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Healthy
            data = {
                'timestamp': [datetime.now() - timedelta(minutes=i) for i in range(10)],
                'equity': [10000 + i*100 for i in range(10)]
            }
            df = pd.DataFrame(data)
            df.to_csv(tmpdir / "equity_GOOD.csv", index=False)
            
            # Unhealthy
            bad_data = {'timestamp': [datetime.now()], 'price': [50000]}
            bad_df = pd.DataFrame(bad_data)
            bad_df.to_csv(tmpdir / "equity_BAD.csv", index=False)
            
            agg = HealthAggregator(tmpdir)
            status = agg.run()
            
            assert status['healthy_sessions'] == 1
            assert status['unhealthy_sessions'] == 1
            assert status['overall_status'] == 'UNHEALTHY'
    
    def test_warnings_only(self):
        """Test sessions with warnings only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Few rows (warning, not issue)
            data = {
                'timestamp': [datetime.now()],
                'equity': [10000]
            }
            df = pd.DataFrame(data)
            df.to_csv(tmpdir / "equity_TEST.csv", index=False)
            
            agg = HealthAggregator(tmpdir)
            agg.run()
            
            status = agg._build_summary()
            
            # Healthy but with warnings
            assert status['healthy_sessions'] == 1
            assert status['sessions_with_warnings'] == 1
            assert status['overall_status'] == 'HEALTHY_WITH_WARNINGS'
            assert status['exit_code'] == 0
    
    def test_export_json(self, temp_log_dir):
        """Test JSON export."""
        agg = HealthAggregator(temp_log_dir)
        agg.run()
        
        output_path = temp_log_dir / "health.json"
        exported = agg.export_json(output_path)
        
        assert exported.exists()
        
        with open(exported, 'r') as f:
            data = json.load(f)
        
        assert 'overall_status' in data
        assert 'num_sessions' in data
        assert 'sessions' in data
    
    def test_export_status_file(self, temp_log_dir):
        """Test status file export."""
        agg = HealthAggregator(temp_log_dir)
        agg.run()
        
        output_path = temp_log_dir / "health.status"
        exported = agg.export_status_file(output_path)
        
        assert exported.exists()
        
        exit_code = int(exported.read_text().strip())
        assert exit_code == 0  # Healthy


class TestConvenienceFunction:
    """Tests for convenience functions."""
    
    def test_check_multi_session_health(self):
        """Test convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create valid CSV
            data = {
                'timestamp': [datetime.now() - timedelta(minutes=i) for i in range(10)],
                'equity': [10000 + i*100 for i in range(10)]
            }
            df = pd.DataFrame(data)
            df.to_csv(tmpdir / "equity_TEST.csv", index=False)
            
            exit_code, status = check_multi_session_health(log_dir=tmpdir)
            
            assert exit_code == 0
            assert status['overall_status'] == 'HEALTHY'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
