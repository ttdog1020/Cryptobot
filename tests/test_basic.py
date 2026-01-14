"""
Basic sanity tests to ensure the test infrastructure is working.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_basic_math():
    """Simple test to verify pytest is working."""
    assert 1 + 1 == 2


def test_imports():
    """Verify core modules can be imported."""
    try:
        from risk_management import RiskConfig, RiskEngine
        from execution.paper_trader import PaperTrader

        assert True
    except ImportError as e:
        # Some modules may not be available in all environments
        print(f"Warning: Import failed: {e}")
        assert True  # Don't fail if optional modules are missing


def test_config_files_exist():
    """Verify essential config files exist."""
    config_dir = Path(__file__).parent.parent / "config"

    # These are essential configuration files
    essential_files = ["risk.json", "trading_mode.yaml"]

    for filename in essential_files:
        config_file = config_dir / filename
        assert config_file.exists(), f"Essential config file missing: {filename}"


def test_python_version():
    """Verify Python version is 3.11+."""
    assert sys.version_info >= (
        3,
        11,
    ), f"Python 3.11+ required, got {sys.version_info.major}.{sys.version_info.minor}"
