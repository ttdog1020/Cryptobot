"""
Health Check Aggregator for Multi-Session Trading

Monitors liveness of running sessions, detects hung processes, validates data integrity,
and provides health status for CI/CD integration.

Features:
- Scan log directory for recent activity
- Detect hung processes (no updates > threshold)
- Validate equity CSV integrity
- Summarize errors per session
- Return exit codes for CI
- JSON status output
"""

import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)


class HealthCheckResult:
    """Result of a health check on a session."""
    
    def __init__(self, session_name: str):
        """Initialize health check result."""
        self.session_name = session_name
        self.is_healthy = True
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.last_update: Optional[datetime] = None
        self.file_age_minutes: Optional[int] = None
        self.file_size_bytes: Optional[int] = None
        self.num_rows: Optional[int] = None
        self.row_count_stable = True
        self.csv_valid = True
    
    def add_issue(self, issue: str):
        """Add critical issue."""
        self.issues.append(issue)
        self.is_healthy = False
        logger.error(f"[HEALTH] {self.session_name}: {issue}")
    
    def add_warning(self, warning: str):
        """Add non-critical warning."""
        self.warnings.append(warning)
        logger.warning(f"[HEALTH] {self.session_name}: {warning}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'session_name': self.session_name,
            'is_healthy': self.is_healthy,
            'issues': self.issues,
            'warnings': self.warnings,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'file_age_minutes': self.file_age_minutes,
            'file_size_bytes': self.file_size_bytes,
            'num_rows': self.num_rows,
            'csv_valid': self.csv_valid
        }


class SessionHealthMonitor:
    """Monitor health of individual session."""
    
    def __init__(
        self,
        equity_file: Path,
        max_age_minutes: int = 10,
        min_expected_rows: int = 10
    ):
        """
        Initialize monitor.
        
        Args:
            equity_file: Path to equity CSV
            max_age_minutes: Max age before flagging as stale (default: 10 min)
            min_expected_rows: Min rows expected for validity (default: 10)
        """
        self.equity_file = equity_file
        self.max_age_minutes = max_age_minutes
        self.min_expected_rows = min_expected_rows
    
    def check(self) -> HealthCheckResult:
        """
        Check health of session.
        
        Returns:
            HealthCheckResult with detailed findings
        """
        session_name = self.equity_file.stem.replace("equity_", "")
        result = HealthCheckResult(session_name)
        
        # Check file exists
        if not self.equity_file.exists():
            result.add_issue(f"Equity file not found: {self.equity_file}")
            return result
        
        # Check file age
        try:
            file_stat = self.equity_file.stat()
            file_age = datetime.now() - datetime.fromtimestamp(file_stat.st_mtime)
            result.file_age_minutes = int(file_age.total_seconds() / 60)
            result.file_size_bytes = file_stat.st_size
            
            if result.file_age_minutes > self.max_age_minutes:
                result.add_issue(
                    f"Equity file stale: {result.file_age_minutes} min "
                    f"(threshold: {self.max_age_minutes} min)"
                )
            
            # Update timestamp
            result.last_update = datetime.fromtimestamp(file_stat.st_mtime)
        
        except Exception as e:
            result.add_issue(f"Error checking file age: {e}")
            return result
        
        # Check CSV validity
        result = self._validate_csv(result)
        
        return result
    
    def _validate_csv(self, result: HealthCheckResult) -> HealthCheckResult:
        """Validate CSV file format and content."""
        try:
            with open(self.equity_file, 'r') as f:
                lines = f.readlines()
            
            # Check minimum content
            if len(lines) < 2:
                result.add_issue(f"CSV has fewer than 2 lines (empty)")
                result.csv_valid = False
                return result
            
            # Parse header
            header = lines[0].strip().split(',')
            required_cols = ['timestamp', 'equity']
            
            if not all(col in header for col in required_cols):
                result.add_issue(
                    f"Missing required columns. Expected {required_cols}, "
                    f"got {header}"
                )
                result.csv_valid = False
                return result
            
            # Check row count
            num_data_rows = len(lines) - 1
            result.num_rows = num_data_rows
            
            if num_data_rows < self.min_expected_rows:
                result.add_warning(
                    f"Low row count: {num_data_rows} "
                    f"(expected minimum: {self.min_expected_rows})"
                )
            
            # Validate data rows (sample check)
            errors = []
            for i, line in enumerate(lines[1:min(len(lines), 11)], 1):  # Check first 10 rows
                cols = line.strip().split(',')
                if len(cols) != len(header):
                    errors.append(f"Row {i}: column count mismatch ({len(cols)} vs {len(header)})")
                
                # Check equity is numeric
                try:
                    equity_idx = header.index('equity')
                    float(cols[equity_idx])
                except (ValueError, IndexError) as e:
                    errors.append(f"Row {i}: invalid equity value")
            
            if errors:
                result.add_warning(f"CSV format issues: {errors[:3]}")  # Report first 3
        
        except Exception as e:
            result.add_issue(f"Error validating CSV: {e}")
            result.csv_valid = False
        
        return result


class HealthAggregator:
    """Aggregate health status across all sessions."""
    
    def __init__(
        self,
        log_dir: Optional[Path] = None,
        max_age_minutes: int = 10
    ):
        """
        Initialize aggregator.
        
        Args:
            log_dir: Directory containing equity files (default: logs/)
            max_age_minutes: Max file age before flagging (default: 10)
        """
        self.log_dir = Path(log_dir) if log_dir else Path("logs")
        self.max_age_minutes = max_age_minutes
        self.results: Dict[str, HealthCheckResult] = {}
    
    def run(self, pattern: str = "equity_*.csv") -> Dict[str, Any]:
        """
        Run health check across all sessions.
        
        Args:
            pattern: Glob pattern for equity files
        
        Returns:
            Aggregated health status
        """
        self.results.clear()
        
        if not self.log_dir.exists():
            logger.error(f"Log directory not found: {self.log_dir}")
            return self._build_summary(healthy=False)
        
        # Find all equity files
        equity_files = list(self.log_dir.glob(pattern))
        
        if not equity_files:
            logger.warning(f"No equity files found matching {pattern}")
            return self._build_summary(healthy=False)
        
        logger.info(f"[HEALTH] Checking {len(equity_files)} sessions")
        
        # Check each session
        for equity_file in equity_files:
            monitor = SessionHealthMonitor(equity_file, self.max_age_minutes)
            result = monitor.check()
            self.results[result.session_name] = result
        
        # Build summary
        return self._build_summary()
    
    def _build_summary(self, healthy: Optional[bool] = None) -> Dict[str, Any]:
        """Build aggregated health summary."""
        # If healthy explicitly set, use that
        if healthy is not None:
            return {
                'timestamp': datetime.now().isoformat(),
                'overall_status': 'HEALTHY' if healthy else 'UNHEALTHY',
                'num_sessions': 0,
                'healthy_sessions': 0,
                'unhealthy_sessions': 0,
                'sessions_with_warnings': 0,
                'sessions': {},
                'errors': [],
                'warnings': [],
                'exit_code': 0 if healthy else 1
            }
        
        # Aggregate results
        num_healthy = sum(1 for r in self.results.values() if r.is_healthy)
        num_warnings = sum(1 for r in self.results.values() if r.warnings and r.is_healthy)
        num_unhealthy = len(self.results) - num_healthy
        
        # Overall status
        if num_unhealthy > 0:
            overall = 'UNHEALTHY'
            exit_code = 1
        elif num_warnings > 0:
            overall = 'HEALTHY_WITH_WARNINGS'
            exit_code = 0
        else:
            overall = 'HEALTHY'
            exit_code = 0
        
        # Collect all issues and warnings
        all_issues = []
        all_warnings = []
        
        for result in self.results.values():
            all_issues.extend(result.issues)
            all_warnings.extend(result.warnings)
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': overall,
            'num_sessions': len(self.results),
            'healthy_sessions': num_healthy,
            'unhealthy_sessions': num_unhealthy,
            'sessions_with_warnings': num_warnings,
            'sessions': {
                name: result.to_dict()
                for name, result in self.results.items()
            },
            'issues': all_issues,
            'warnings': all_warnings,
            'exit_code': exit_code
        }
        
        return summary
    
    def export_json(self, output_path: Optional[Path] = None) -> Path:
        """
        Export health status to JSON.
        
        Args:
            output_path: Path to save JSON (default: logs/health.json)
        
        Returns:
            Path to output file
        """
        if output_path is None:
            output_path = self.log_dir / "health.json"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get current summary
        summary = self._build_summary()
        
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"[HEALTH] Exported health status to {output_path}")
        return output_path
    
    def export_status_file(self, output_path: Optional[Path] = None) -> Path:
        """
        Export simple status file (0 = healthy, 1 = unhealthy).
        
        For shell integration.
        
        Args:
            output_path: Path to status file (default: logs/health.status)
        
        Returns:
            Path to output file
        """
        if output_path is None:
            output_path = self.log_dir / "health.status"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        summary = self._build_summary()
        exit_code = summary['exit_code']
        
        with open(output_path, 'w') as f:
            f.write(str(exit_code))
        
        logger.info(f"[HEALTH] Wrote exit code {exit_code} to {output_path}")
        return output_path


def check_multi_session_health(
    log_dir: Optional[Path] = None,
    max_age_minutes: int = 10,
    output_json: Optional[Path] = None
) -> Tuple[int, Dict[str, Any]]:
    """
    Convenience function to run health check.
    
    Args:
        log_dir: Log directory (default: logs/)
        max_age_minutes: Max file age (default: 10)
        output_json: Export path (optional)
    
    Returns:
        (exit_code, status_dict)
    """
    aggregator = HealthAggregator(log_dir, max_age_minutes)
    status = aggregator.run()
    
    if output_json:
        aggregator.export_json(output_json)
    
    exit_code = status['exit_code']
    
    # Log summary
    logger.info(
        f"[HEALTH] Status: {status['overall_status']} | "
        f"Sessions: {status['healthy_sessions']}/{status['num_sessions']} healthy"
    )
    
    return exit_code, status


if __name__ == "__main__":
    import sys
    
    # CLI interface
    log_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("logs")
    
    exit_code, status = check_multi_session_health(
        log_dir=log_dir,
        output_json=log_dir / "health.json"
    )
    
    print(json.dumps(status, indent=2))
    sys.exit(exit_code)
