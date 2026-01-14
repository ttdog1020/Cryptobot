"""
CLI for auto-evolution engine (Module 33)

Usage:
    python -m optimizer.run_evolution --dry-run
    python -m optimizer.run_evolution --symbols BTCUSDT ETHUSDT
"""

import asyncio
import argparse
import json
import logging
from pathlib import Path

from optimizer.evolution_engine import EvolutionEngine
from strategies.profile_loader import StrategyProfileLoader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Auto-evolve strategy profiles based on decay + optimizer results"
    )
    parser.add_argument(
        "--symbols",
        nargs="*",
        help="Optional list of symbols to evolve (default: from config)"
    )
    parser.add_argument(
        "--config",
        default="config/evolution.json",
        help="Evolution config path (default: config/evolution.json)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force dry-run mode (override config)"
    )
    args = parser.parse_args()
    
    # Load config
    base_dir = Path(__file__).resolve().parents[1]
    cfg_path = base_dir / args.config
    
    if not cfg_path.exists():
        logger.error(f"Config file not found: {cfg_path}")
        return
    
    with cfg_path.open("r", encoding="utf-8") as f:
        evo_cfg = json.load(f)
    
    if args.dry_run:
        evo_cfg["dry_run"] = True
    
    # Initialize components
    profile_loader = StrategyProfileLoader(base_dir / "config" / "strategy_profiles")
    
    engine = EvolutionEngine(
        evolution_cfg=evo_cfg,
        profile_loader=profile_loader,
        base_dir=base_dir,
    )
    
    # Run evolution
    logger.info("=" * 70)
    logger.info("AUTO-EVOLUTION ENGINE")
    logger.info("=" * 70)
    logger.info(f"Mode: {'DRY-RUN' if evo_cfg.get('dry_run') else 'LIVE'}")
    logger.info(f"Symbols: {args.symbols or evo_cfg.get('symbols', 'all')}")
    logger.info("=" * 70)
    
    results = await engine.run_for_all_symbols(args.symbols)
    
    # Print summary
    print("\n" + "=" * 70)
    print("AUTO-EVOLUTION SUMMARY")
    print("=" * 70)
    
    if not results:
        print("No symbols processed")
    else:
        header = f"{'Symbol':<12} {'Status':<8} {'Reason':<48}"
        print(header)
        print("-" * len(header))
        
        for sym, dec in results.items():
            reason = (dec.reason or "")[:45] + ("..." if len(dec.reason or "") > 45 else "")
            print(f"{sym:<12} {dec.status:<8} {reason:<48}")
        
        # Counts
        print("-" * len(header))
        counts = {"SKIP": 0, "APPLY": 0, "REJECT": 0, "ERROR": 0}
        for dec in results.values():
            counts[dec.status] = counts.get(dec.status, 0) + 1
        
        print(f"SKIP: {counts['SKIP']}, APPLY: {counts['APPLY']}, REJECT: {counts['REJECT']}, ERROR: {counts['ERROR']}")
    
    print("=" * 70)
    
    if evo_cfg.get("dry_run"):
        print("\n⚠️  DRY-RUN MODE: No profiles were modified")
        print("Set 'dry_run': false in config to apply changes")
    
    print(f"\nLogs written to: {engine.log_dir}")


if __name__ == "__main__":
    asyncio.run(main())
