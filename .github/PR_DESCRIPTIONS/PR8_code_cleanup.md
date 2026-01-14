# PR8: Code Cleanup - Archive Deprecated Scripts

## Problem
Root directory cluttered with deprecated one-time experimental scripts (sweep_macd_params.py). No clear organization for "keep but don't use" code.

## Solution
Move deprecated scripts to `archive/deprecated_scripts/` with metadata. This preserves history while reducing visual clutter.

## Changes

### Moved
- `sweep_macd_params.py` → `archive/deprecated_scripts/sweep_macd_params.py` (269 LOC)
  * Standalone MACD parameter sweep
  * No imports from active code
  * Superseded by generic `auto_optimizer.py`

### Added
- `archive/deprecated_scripts/README.md`
  * Explains each archived script
  * Retention rationale
  * Restoration instructions for future developers
  * Candidates for next cleanup cycle

## Rationale

**Why Archive (not Delete)?**
1. Preserves git history if needed for reference
2. Allows easy restoration if experimental approach is revisited
3. Provides learning reference for parameter sweeping
4. Avoids permanent loss of working code

**Why Now?**
1. Reduces visual clutter in root directory (less mental overhead)
2. Pairs well with PR7 (organization-focused cycle)
3. Sets precedent for handling future experimental code
4. No runtime impact, safe to do early

## Impact
- **LOC Removed from Root:** 269
- **Files Moved:** 1
- **Files Added:** 1 (README.md)
- **Runtime Impact:** Zero
- **Test Impact:** Zero
- **Safety:** ✅ Low (archive only)

## Restoration
If needed later, restore with:
```bash
mv archive/deprecated_scripts/sweep_macd_params.py ./
git add archive/ sweep_macd_params.py
git commit -m "restore: Re-activate sweep_macd_params"
```

## Risk Assessment
- **Risk Level**: LOW
- **Impact**: LOW (code organization only)
- **Backward Compatibility**: ✅ No breaking changes
- **Safety**: ✅ Archive structure allows easy restoration
- **Testing**: ✅ No tests affected
