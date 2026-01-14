"""pytest configuration for adding project root to sys.path."""

import sys
import os

# Add project root to sys.path so local modules can be imported
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
