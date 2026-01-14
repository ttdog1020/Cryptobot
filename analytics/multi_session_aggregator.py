"""
Multi-Session Aggregation & Reporting

Aggregates metrics across multiple trading sessions (equity runs)
to provide portfolio-level insights and HTML reporting.

Features:
- Loads equity CSV files from live trading sessions
- Computes aggregate statistics (PnL, Sharpe, drawdown, VaR)
- Per-session breakdown and correlation analysis
- HTML report generation with charts
- JSON export for CI integration
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Minimum rows required for a session to be considered valid
# Sessions with fewer rows are skipped during load_sessions()
MIN_SESSION_ROWS = 2


class MultiSessionAggregator:
    """Aggregate metrics across multiple trading sessions."""
    
    def __init__(self, equity_dir: Optional[Path] = None):
        """
        Initialize aggregator.
        
        Args:
            equity_dir: Directory containing equity_*.csv files (default: logs/)
        """
        self.equity_dir = Path(equity_dir) if equity_dir else Path("logs")
        self.sessions: Dict[str, pd.DataFrame] = {}
        self.aggregate_stats: Optional[Dict[str, Any]] = None
        self.correlation_matrix: Optional[pd.DataFrame] = None
    
    def load_sessions(self, pattern: str = "equity_*.csv") -> int:
        """
        Load all equity CSV files matching pattern.
        
        Args:
            pattern: Glob pattern for equity files (default: equity_*.csv)
        
        Returns:
            Number of sessions loaded
        """
        self.sessions.clear()
        
        if not self.equity_dir.exists():
            logger.warning(f"Equity directory not found: {self.equity_dir}")
            return 0
        
        equity_files = list(self.equity_dir.glob(pattern))
        
        for file_path in equity_files:
            try:
                df = pd.read_csv(file_path)
                
                # Validate required columns
                required_cols = ['timestamp', 'equity']
                if not all(col in df.columns for col in required_cols):
                    logger.warning(f"[AGG] Skipping {file_path.name}: missing required columns")
                    continue
                
                # Skip sessions with insufficient data for analysis
                if len(df) < MIN_SESSION_ROWS:
                    logger.info(f"[AGG] Skipping {file_path.name}: insufficient data ({len(df)} rows, need >={MIN_SESSION_ROWS})")
                    continue
                
                # Parse timestamp
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp').reset_index(drop=True)
                
                # Extract session name (e.g., "BTCUSDT" from "equity_BTCUSDT.csv")
                session_name = file_path.stem.replace("equity_", "")
                self.sessions[session_name] = df
                
                logger.info(f"[AGG] Loaded session {session_name}: {len(df)} rows")
            
            except Exception as e:
                logger.error(f"[AGG] Error loading {file_path.name}: {e}")
        
        return len(self.sessions)
    
    def compute_metrics(self, returns_col: str = 'returns') -> Dict[str, Any]:
        """
        Compute aggregate statistics across all sessions.
        
        Args:
            returns_col: Column name for returns (computed if not present)
        
        Returns:
            Dictionary of aggregate metrics
        """
        if not self.sessions:
            logger.warning("[AGG] No sessions loaded")
            return {
                'num_sessions': 0,
                'session_names': [],
                'start_time': None,
                'end_time': None,
                'duration_days': None,
                'total_pnl': 0.0,
                'total_starting_balance': 0.0,
                'total_final_equity': 0.0,
                'aggregate_return_pct': 0.0,
                'combined_sharpe': 0.0,
                'max_drawdown_pct': 0.0,
                'var_95': 0.0,
                'cvar_95': 0.0,
                'per_session_stats': {},
                'correlation_matrix': None
            }
        
        # Compute returns if not present
        for session_name, df in self.sessions.items():
            if returns_col not in df.columns:
                df[returns_col] = df['equity'].pct_change().fillna(0)
        
        # Aggregate metrics
        stats = {
            'num_sessions': len(self.sessions),
            'session_names': sorted(self.sessions.keys()),
            'start_time': None,
            'end_time': None,
            'duration_days': None,
            'total_pnl': 0.0,
            'total_starting_balance': 0.0,
            'total_final_equity': 0.0,
            'aggregate_return_pct': 0.0,
            'combined_sharpe': 0.0,
            'max_drawdown_pct': 0.0,
            'var_95': 0.0,
            'cvar_95': 0.0,
            'per_session_stats': {},
            'correlation_matrix': None
        }
        
        # Compute per-session stats
        all_returns = []
        
        for session_name, df in self.sessions.items():
            if len(df) < MIN_SESSION_ROWS:
                continue
            
            starting_balance = df.iloc[0]['equity']
            final_equity = df.iloc[-1]['equity']
            returns = df[returns_col].values
            
            pnl = final_equity - starting_balance
            return_pct = (final_equity / starting_balance - 1) * 100
            sharpe = self._compute_sharpe(returns)
            max_dd = self._compute_max_drawdown(df['equity'].values)
            
            stats['per_session_stats'][session_name] = {
                'starting_balance': starting_balance,
                'final_equity': final_equity,
                'pnl': pnl,
                'return_pct': return_pct,
                'sharpe_ratio': sharpe,
                'max_drawdown_pct': max_dd,
                'num_trades': len(df) - 1,  # Approximation
                'duration_days': (df.iloc[-1]['timestamp'] - df.iloc[0]['timestamp']).days
            }
            
            stats['total_pnl'] += pnl
            stats['total_starting_balance'] += starting_balance
            stats['total_final_equity'] += final_equity
            
            all_returns.extend(returns)
        
        # Aggregate calculations
        if all_returns:
            all_returns = np.array(all_returns)
            
            stats['aggregate_return_pct'] = (
                stats['total_final_equity'] / stats['total_starting_balance'] - 1
            ) * 100 if stats['total_starting_balance'] > 0 else 0.0
            
            stats['combined_sharpe'] = self._compute_sharpe(all_returns)
            stats['var_95'] = np.percentile(all_returns, 5)
            stats['cvar_95'] = np.mean(all_returns[all_returns <= stats['var_95']])
        
        # Time range
        if self.sessions:
            all_timestamps = [
                df['timestamp'].min() for df in self.sessions.values() if len(df) > 0
            ]
            all_timestamps.extend([
                df['timestamp'].max() for df in self.sessions.values() if len(df) > 0
            ])
            
            if all_timestamps:
                stats['start_time'] = min(all_timestamps).isoformat()
                stats['end_time'] = max(all_timestamps).isoformat()
                
                start = datetime.fromisoformat(stats['start_time'])
                end = datetime.fromisoformat(stats['end_time'])
                stats['duration_days'] = (end - start).days
        
        # Compute max drawdown across all sessions
        if self.sessions:
            max_dds = []
            for df in self.sessions.values():
                if len(df) > 0:
                    dd = self._compute_max_drawdown(df['equity'].values)
                    max_dds.append(dd)
            
            if max_dds:
                stats['max_drawdown_pct'] = max(max_dds)
        
        self.aggregate_stats = stats
        return stats
    
    def compute_correlation(self) -> Optional[pd.DataFrame]:
        """
        Compute correlation matrix between session returns.
        
        Returns:
            Correlation matrix DataFrame
        """
        if not self.sessions or len(self.sessions) < 2:
            logger.warning("[AGG] Need at least 2 sessions for correlation")
            return None
        
        # Align all returns to common timestamps
        all_timestamps = set()
        for df in self.sessions.values():
            all_timestamps.update(df['timestamp'].unique())
        
        all_timestamps = sorted(all_timestamps)
        
        # Create aligned returns matrix
        returns_dict = {}
        
        for session_name, df in self.sessions.items():
            df_indexed = df.set_index('timestamp')
            
            # Forward fill to align timestamps
            returns = []
            for ts in all_timestamps:
                if ts in df_indexed.index:
                    idx = df_indexed.index.get_loc(ts)
                    if idx > 0:
                        returns.append(df_indexed.iloc[idx]['equity'] / df_indexed.iloc[idx-1]['equity'] - 1)
                    else:
                        returns.append(0.0)
                else:
                    # Use most recent value
                    mask = df_indexed.index < ts
                    if mask.any():
                        idx = np.where(mask)[0][-1]
                        if idx > 0:
                            returns.append(df_indexed.iloc[idx]['equity'] / df_indexed.iloc[idx-1]['equity'] - 1)
                        else:
                            returns.append(0.0)
                    else:
                        returns.append(0.0)
            
            returns_dict[session_name] = returns
        
        # Create correlation matrix
        returns_df = pd.DataFrame(returns_dict)
        self.correlation_matrix = returns_df.corr()
        
        return self.correlation_matrix
    
    def export_json(self, output_path: Optional[Path] = None) -> Path:
        """
        Export aggregated stats to JSON.
        
        Args:
            output_path: Path to save JSON (default: logs/aggregation.json)
        
        Returns:
            Path to output file
        """
        if output_path is None:
            output_path = self.equity_dir / "aggregation.json"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare JSON-serializable data
        export_data = self.aggregate_stats.copy() if self.aggregate_stats else {}
        export_data['generated_at'] = datetime.now().isoformat()
        
        # Convert numpy types
        export_data = self._make_serializable(export_data)
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"[AGG] Exported aggregation stats to {output_path}")
        return output_path
    
    def generate_html_report(self, output_path: Optional[Path] = None) -> Path:
        """
        Generate HTML report with charts.
        
        Args:
            output_path: Path to save HTML (default: logs/aggregation_report.html)
        
        Returns:
            Path to output file
        """
        if output_path is None:
            output_path = self.equity_dir / "aggregation_report.html"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build HTML
        html = self._build_html_report()
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        logger.info(f"[AGG] Generated HTML report: {output_path}")
        return output_path
    
    def _compute_sharpe(self, returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        """Compute Sharpe ratio."""
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / 252)
        std = np.std(excess_returns)
        
        if std == 0:
            return 0.0
        
        sharpe = np.mean(excess_returns) / std * np.sqrt(252)
        return float(sharpe)
    
    def _compute_max_drawdown(self, equity: np.ndarray) -> float:
        """Compute maximum drawdown percentage."""
        if len(equity) < 2:
            return 0.0
        
        cummax = np.maximum.accumulate(equity)
        drawdown = (equity - cummax) / cummax
        max_dd = np.min(drawdown)
        
        return float(abs(max_dd) * 100)
    
    def _make_serializable(self, obj: Any) -> Any:
        """Convert numpy types to Python native types for JSON."""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(v) for v in obj]
        elif isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        elif isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        elif pd.isna(obj):
            return None
        else:
            return obj
    
    def _build_html_report(self) -> str:
        """Build HTML report string."""
        stats = self.aggregate_stats or {}
        
        # Aggregate stats table
        stats_rows = f"""
        <tr><td>Sessions</td><td>{stats.get('num_sessions', 0)}</td></tr>
        <tr><td>Total PnL</td><td>${stats.get('total_pnl', 0):.2f}</td></tr>
        <tr><td>Return</td><td>{stats.get('aggregate_return_pct', 0):.2f}%</td></tr>
        <tr><td>Sharpe Ratio</td><td>{stats.get('combined_sharpe', 0):.2f}</td></tr>
        <tr><td>Max Drawdown</td><td>{stats.get('max_drawdown_pct', 0):.2f}%</td></tr>
        <tr><td>VaR (95%)</td><td>{stats.get('var_95', 0):.4f}</td></tr>
        <tr><td>CVaR (95%)</td><td>{stats.get('cvar_95', 0):.4f}</td></tr>
        """
        
        # Per-session stats table
        per_session_html = "<tr><th>Session</th><th>PnL</th><th>Return %</th><th>Sharpe</th><th>Max DD %</th></tr>"
        
        for session_name, session_stats in stats.get('per_session_stats', {}).items():
            per_session_html += f"""
            <tr>
                <td>{session_name}</td>
                <td>${session_stats.get('pnl', 0):.2f}</td>
                <td>{session_stats.get('return_pct', 0):.2f}%</td>
                <td>{session_stats.get('sharpe_ratio', 0):.2f}</td>
                <td>{session_stats.get('max_drawdown_pct', 0):.2f}%</td>
            </tr>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Multi-Session Aggregation Report</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                h1 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; background: white; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .metric {{ font-weight: bold; color: #2196F3; }}
                .warning {{ color: #ff9800; }}
                .error {{ color: #f44336; }}
            </style>
        </head>
        <body>
            <h1>Multi-Session Aggregation Report</h1>
            <p>Generated: {datetime.now().isoformat()}</p>
            
            <h2>Aggregate Statistics</h2>
            <table>
                {stats_rows}
            </table>
            
            <h2>Per-Session Breakdown</h2>
            <table>
                {per_session_html}
            </table>
            
            <h2>Correlation Matrix</h2>
            <p>Session-to-session return correlation (if 2+ sessions):</p>
            <pre>{self.correlation_matrix.to_string() if self.correlation_matrix is not None else "N/A"}</pre>
        </body>
        </html>
        """
        
        return html


def run_aggregation(
    equity_dir: Optional[Path] = None,
    pattern: str = "equity_*.csv",
    output_json: Optional[Path] = None,
    output_html: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Run aggregation pipeline.
    
    Args:
        equity_dir: Directory with equity files
        pattern: File pattern to match
        output_json: Path for JSON export
        output_html: Path for HTML export
    
    Returns:
        Aggregate statistics dictionary
    """
    aggregator = MultiSessionAggregator(equity_dir)
    
    # Load sessions
    num_loaded = aggregator.load_sessions(pattern)
    
    if num_loaded == 0:
        logger.warning("[AGG] No sessions loaded, aborting")
        return {}
    
    logger.info(f"[AGG] Loaded {num_loaded} sessions")
    
    # Compute metrics
    stats = aggregator.compute_metrics()
    
    # Compute correlation
    if num_loaded > 1:
        aggregator.compute_correlation()
    
    # Export
    if output_json:
        aggregator.export_json(output_json)
    else:
        aggregator.export_json()
    
    if output_html:
        aggregator.generate_html_report(output_html)
    else:
        aggregator.generate_html_report()
    
    logger.info("[AGG] Aggregation complete")
    return stats


if __name__ == "__main__":
    import sys
    
    # CLI interface
    if len(sys.argv) > 1:
        equity_dir = Path(sys.argv[1])
    else:
        equity_dir = Path("logs")
    
    stats = run_aggregation(equity_dir)
    print(json.dumps(stats, indent=2, default=str))
