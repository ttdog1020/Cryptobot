"""
Tests for multi-session aggregation and reporting.

Tests:
- Session loading from CSV files
- Metric computation (PnL, Sharpe, drawdown, VaR)
- Correlation calculation
- JSON/HTML export
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

from analytics.multi_session_aggregator import MultiSessionAggregator, run_aggregation


class TestMultiSessionAggregator:
    """Tests for MultiSessionAggregator."""
    
    @pytest.fixture
    def temp_equity_dir(self):
        """Create temporary directory with sample equity CSVs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create sample equity files for 2 sessions
            base_time = datetime(2025, 1, 1, 9, 0, 0)
            
            # Session 1: BTCUSDT (profitable)
            data1 = {
                'timestamp': [base_time + timedelta(hours=i) for i in range(24)],
                'equity': np.linspace(10000, 11000, 24).tolist(),
            }
            df1 = pd.DataFrame(data1)
            df1.to_csv(tmpdir / "equity_BTCUSDT.csv", index=False)
            
            # Session 2: ETHUSDT (less profitable)
            data2 = {
                'timestamp': [base_time + timedelta(hours=i) for i in range(24)],
                'equity': np.linspace(10000, 10500, 24).tolist(),
            }
            df2 = pd.DataFrame(data2)
            df2.to_csv(tmpdir / "equity_ETHUSDT.csv", index=False)
            
            yield tmpdir
    
    def test_initialization(self):
        """Test aggregator initialization."""
        agg = MultiSessionAggregator(Path("logs"))
        
        assert agg.equity_dir == Path("logs")
        assert len(agg.sessions) == 0
    
    def test_load_sessions(self, temp_equity_dir):
        """Test loading equity CSV files."""
        agg = MultiSessionAggregator(temp_equity_dir)
        
        num_loaded = agg.load_sessions()
        
        assert num_loaded == 2
        assert "BTCUSDT" in agg.sessions
        assert "ETHUSDT" in agg.sessions
        assert len(agg.sessions["BTCUSDT"]) == 24
        assert len(agg.sessions["ETHUSDT"]) == 24
    
    def test_load_sessions_empty_dir(self):
        """Test loading from empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agg = MultiSessionAggregator(Path(tmpdir))
            num_loaded = agg.load_sessions()
            
            assert num_loaded == 0
    
    def test_load_sessions_invalid_csv(self):
        """Test loading CSV with missing required columns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create CSV missing 'equity' column
            data = {'timestamp': ['2025-01-01'], 'other_col': [100]}
            df = pd.DataFrame(data)
            df.to_csv(tmpdir / "equity_BTCUSDT.csv", index=False)
            
            agg = MultiSessionAggregator(tmpdir)
            num_loaded = agg.load_sessions()
            
            # Should skip invalid file
            assert num_loaded == 0
    
    def test_compute_metrics(self, temp_equity_dir):
        """Test metric computation."""
        agg = MultiSessionAggregator(temp_equity_dir)
        agg.load_sessions()
        
        stats = agg.compute_metrics()
        
        assert stats['num_sessions'] == 2
        assert 'BTCUSDT' in stats['per_session_stats']
        assert 'ETHUSDT' in stats['per_session_stats']
        
        # Check BTCUSDT metrics
        btc_stats = stats['per_session_stats']['BTCUSDT']
        assert btc_stats['starting_balance'] == pytest.approx(10000, rel=0.01)
        assert btc_stats['final_equity'] == pytest.approx(11000, rel=0.01)
        assert btc_stats['pnl'] == pytest.approx(1000, rel=0.01)
        assert btc_stats['return_pct'] == pytest.approx(10.0, rel=0.01)
        assert btc_stats['sharpe_ratio'] > 0
    
    def test_aggregate_metrics(self, temp_equity_dir):
        """Test aggregate calculation across sessions."""
        agg = MultiSessionAggregator(temp_equity_dir)
        agg.load_sessions()
        
        stats = agg.compute_metrics()
        
        # Both sessions: 10k starting each = 20k total
        assert stats['total_starting_balance'] == pytest.approx(20000, rel=0.01)
        
        # Total PnL: 1000 + 500 = 1500
        assert stats['total_pnl'] == pytest.approx(1500, rel=0.01)
        
        # Aggregate return: 21500 / 20000 - 1 = 7.5%
        assert stats['aggregate_return_pct'] == pytest.approx(7.5, rel=0.01)
    
    def test_compute_sharpe(self, temp_equity_dir):
        """Test Sharpe ratio computation."""
        agg = MultiSessionAggregator(temp_equity_dir)
        agg.load_sessions()
        
        stats = agg.compute_metrics()
        
        # Sharpe should be positive for profitable session
        btc_sharpe = stats['per_session_stats']['BTCUSDT']['sharpe_ratio']
        assert btc_sharpe > 0
    
    def test_compute_max_drawdown(self):
        """Test max drawdown computation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create equity with drawdown: 100 -> 50 -> 80
            base_time = datetime(2025, 1, 1, 9, 0, 0)
            data = {
                'timestamp': [base_time + timedelta(hours=i) for i in range(3)],
                'equity': [100, 50, 80],
            }
            df = pd.DataFrame(data)
            df.to_csv(tmpdir / "equity_TEST.csv", index=False)
            
            agg = MultiSessionAggregator(tmpdir)
            agg.load_sessions()
            
            stats = agg.compute_metrics()
            
            # Max DD: (50 - 100) / 100 = -50%
            test_dd = stats['per_session_stats']['TEST']['max_drawdown_pct']
            assert test_dd == pytest.approx(50.0, rel=0.01)
    
    def test_compute_correlation(self, temp_equity_dir):
        """Test correlation computation."""
        agg = MultiSessionAggregator(temp_equity_dir)
        agg.load_sessions()
        
        corr = agg.compute_correlation()
        
        assert corr is not None
        assert corr.shape == (2, 2)
        assert 'BTCUSDT' in corr.index
        assert 'ETHUSDT' in corr.index
    
    def test_compute_correlation_single_session(self):
        """Test correlation with single session (should return None)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create single equity file
            base_time = datetime(2025, 1, 1, 9, 0, 0)
            data = {
                'timestamp': [base_time + timedelta(hours=i) for i in range(10)],
                'equity': np.linspace(10000, 11000, 10).tolist(),
            }
            df = pd.DataFrame(data)
            df.to_csv(tmpdir / "equity_BTCUSDT.csv", index=False)
            
            agg = MultiSessionAggregator(tmpdir)
            agg.load_sessions()
            
            corr = agg.compute_correlation()
            
            # Should return None for single session
            assert corr is None
    
    def test_export_json(self, temp_equity_dir):
        """Test JSON export."""
        agg = MultiSessionAggregator(temp_equity_dir)
        agg.load_sessions()
        agg.compute_metrics()
        
        output_path = temp_equity_dir / "test_aggregation.json"
        exported_path = agg.export_json(output_path)
        
        assert exported_path.exists()
        
        # Verify JSON content
        with open(exported_path, 'r') as f:
            data = json.load(f)
        
        assert 'num_sessions' in data
        assert data['num_sessions'] == 2
        assert 'per_session_stats' in data
    
    def test_export_html(self, temp_equity_dir):
        """Test HTML export."""
        agg = MultiSessionAggregator(temp_equity_dir)
        agg.load_sessions()
        agg.compute_metrics()
        
        output_path = temp_equity_dir / "test_report.html"
        exported_path = agg.generate_html_report(output_path)
        
        assert exported_path.exists()
        
        # Verify HTML content
        with open(exported_path, 'r') as f:
            html_content = f.read()
        
        assert 'Multi-Session Aggregation Report' in html_content
        assert 'BTCUSDT' in html_content
        assert 'ETHUSDT' in html_content
    
    def test_var_95_calculation(self):
        """Test Value at Risk calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create equity with known returns
            base_time = datetime(2025, 1, 1, 9, 0, 0)
            equity_values = [10000]
            
            # Simulate returns
            for i in range(100):
                next_equity = equity_values[-1] * (1 + np.random.normal(0.001, 0.02))
                equity_values.append(next_equity)
            
            data = {
                'timestamp': [base_time + timedelta(hours=i) for i in range(101)],
                'equity': equity_values,
            }
            df = pd.DataFrame(data)
            df.to_csv(tmpdir / "equity_TEST.csv", index=False)
            
            agg = MultiSessionAggregator(tmpdir)
            agg.load_sessions()
            
            stats = agg.compute_metrics()
            
            # VaR should be negative (loss scenario)
            assert stats['var_95'] < 0
            assert stats['cvar_95'] < stats['var_95']
    
    def test_run_aggregation_function(self, temp_equity_dir):
        """Test run_aggregation convenience function."""
        stats = run_aggregation(
            equity_dir=temp_equity_dir,
            output_json=temp_equity_dir / "agg.json",
            output_html=temp_equity_dir / "report.html"
        )
        
        assert stats['num_sessions'] == 2
        assert (temp_equity_dir / "agg.json").exists()
        assert (temp_equity_dir / "report.html").exists()


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_sessions_dict(self):
        """Test metrics with no sessions loaded."""
        agg = MultiSessionAggregator(Path("logs"))
        stats = agg.compute_metrics()
        
        assert stats == {}
    
    def test_single_row_session(self):
        """Test with session having only 1 row."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Single row
            data = {'timestamp': ['2025-01-01'], 'equity': [10000]}
            df = pd.DataFrame(data)
            df.to_csv(tmpdir / "equity_TEST.csv", index=False)
            
            agg = MultiSessionAggregator(tmpdir)
            agg.load_sessions()
            
            stats = agg.compute_metrics()
            
            # Should handle gracefully
            assert stats['num_sessions'] == 0  # Single row skipped
    
    def test_negative_returns(self):
        """Test with losing session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            base_time = datetime(2025, 1, 1, 9, 0, 0)
            data = {
                'timestamp': [base_time + timedelta(hours=i) for i in range(10)],
                'equity': np.linspace(10000, 9000, 10).tolist(),
            }
            df = pd.DataFrame(data)
            df.to_csv(tmpdir / "equity_LOSER.csv", index=False)
            
            agg = MultiSessionAggregator(tmpdir)
            agg.load_sessions()
            
            stats = agg.compute_metrics()
            
            loser_stats = stats['per_session_stats']['LOSER']
            assert loser_stats['return_pct'] == pytest.approx(-10.0, rel=0.01)
            assert loser_stats['pnl'] == pytest.approx(-1000, rel=0.01)
    
    def test_flat_equity(self):
        """Test with flat equity (no movement)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            base_time = datetime(2025, 1, 1, 9, 0, 0)
            data = {
                'timestamp': [base_time + timedelta(hours=i) for i in range(10)],
                'equity': [10000] * 10,
            }
            df = pd.DataFrame(data)
            df.to_csv(tmpdir / "equity_FLAT.csv", index=False)
            
            agg = MultiSessionAggregator(tmpdir)
            agg.load_sessions()
            
            stats = agg.compute_metrics()
            
            flat_stats = stats['per_session_stats']['FLAT']
            assert flat_stats['return_pct'] == pytest.approx(0.0, abs=0.001)
            assert flat_stats['sharpe_ratio'] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
