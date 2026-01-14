# Archived Deprecated Scripts

This directory contains deprecated scripts that are no longer actively used but are kept for historical reference and potential debugging.

## Contents

### `sweep_macd_params.py` (269 LOC)
**Status:** Archived during PR8 (Code Cleanup)
**Purpose:** Standalone MACD parameter sweep utility for BTC/USDT analysis
**Why Archived:** 
- Not integrated into active codebase
- Superseded by generic `auto_optimizer.py` (Module 10)
- No imports from active code
- One-time experimental tool

**How to Use:** If needed, run directly:
```bash
python archive/deprecated_scripts/sweep_macd_params.py
```

**Dependencies:** pandas, ccxt, backtest.py, strategies/macd_only.py

---

## Restoration

To restore a deprecated script to the main directory:
```bash
mv archive/deprecated_scripts/<script>.py ./<script>.py
git add archive/deprecated_scripts/ <script>.py
git commit -m "restore: Re-activate <script> for <reason>"
```

## Future Cleanup

Additional candidates for archival:
- `fetch_ohlcv_paged.py` (if ccxt handles pagination natively)
- One-off forensic validators (FORENSIC_VALIDATOR*.py)
- Patch scripts (already deleted in MODULE_22)
