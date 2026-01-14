"""
Auto-Evolution / Self-Training Engine (Module 33)

Automatically improves strategy profiles by:
1. Detecting degraded profiles using decay detector
2. Running optimizer over recent history window
3. Applying best candidate that passes safety filters
4. Archiving old profiles with full audit trail

READ-ONLY for risk.json, trading_mode.yaml, and safety limits.
Only updates strategy profile parameters.
"""

import json
import logging
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from optimizer.decay_detector import analyze_profile_decay
from optimizer.performance_history import load_history
from strategies.profile_loader import StrategyProfileLoader

logger = logging.getLogger(__name__)


@dataclass
class EvolutionDecision:
    """Decision about whether to evolve a strategy profile"""
    symbol: str
    status: str  # "SKIP" | "APPLY" | "REJECT" | "ERROR"
    reason: str
    old_params: Optional[Dict[str, Any]] = None
    new_params: Optional[Dict[str, Any]] = None
    old_metrics: Optional[Dict[str, Any]] = None
    new_metrics: Optional[Dict[str, Any]] = None
    optimizer_run_id: Optional[str] = None
    archive_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class EvolutionEngine:
    """
    Phase-1 self-training engine.
    
    Responsibilities:
    1. Check symbol health via decay detector
    2. Run optimizer if health is degraded
    3. Filter candidates by safety constraints
    4. Compare best candidate vs current profile
    5. Archive old profile and apply new one (if not dry-run)
    """
    
    def __init__(
        self,
        evolution_cfg: Dict[str, Any],
        profile_loader: StrategyProfileLoader,
        base_dir: Path,
    ) -> None:
        self.cfg = evolution_cfg
        self.profile_loader = profile_loader
        self.base_dir = base_dir
        
        # Setup directories
        self.archive_dir = (base_dir / self.cfg.get("archive_dir", "config/strategy_profiles/archive")).resolve()
        self.log_dir = (base_dir / self.cfg.get("log_dir", "logs/evolution")).resolve()
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def _now(self) -> datetime:
        """Get current UTC time"""
        return datetime.now(timezone.utc)
    
    def _window_to_dates(self) -> tuple[datetime, datetime]:
        """Convert configured window to start/end dates"""
        window = self.cfg.get("optimizer_window", {})
        end_days_ago = int(window.get("end_days_ago", 0))
        start_days_ago = int(window.get("start_days_ago", 30))
        end = self._now() - timedelta(days=end_days_ago)
        start = self._now() - timedelta(days=start_days_ago)
        return start, end
    
    async def evaluate_symbol(self, symbol: str) -> EvolutionDecision:
        """
        Evaluate whether a symbol should be evolved.
        
        Returns decision with status:
        - SKIP: Profile doesn't need evolution
        - APPLY: New candidate is better and should be applied
        - REJECT: Candidates don't meet requirements
        - ERROR: Something went wrong
        """
        try:
            # 1) Load current profile
            profile = self.profile_loader.load_profile(symbol=symbol, strategy="scalping_ema_rsi", require_enabled=False)
            if profile is None:
                return EvolutionDecision(symbol, "SKIP", "No existing profile found")
            
            old_params = {k: v for k, v in profile.items() if k not in ["symbol", "meta", "metrics"]}
            old_metrics = profile.get("metrics", {}) or {}
            old_return = float(old_metrics.get("total_return_pct", 0.0))
            old_dd = float(old_metrics.get("max_drawdown_pct", 0.0))
            old_trades = int(old_metrics.get("trades", 0))
            
            logger.info(f"[{symbol}] Current profile: return={old_return:.2f}%, dd={old_dd:.2f}%, trades={old_trades}")
            
            # 2) Query decay detector
            health_status = await analyze_profile_decay(
                symbol=symbol,
                strategy="scalping_ema_rsi",
                min_trades=self.cfg.get("min_trades", 5),
            )
            
            # Check if health status triggers evolution
            thresholds = set(t.lower() for t in self.cfg.get("decay_health_thresholds", ["degraded"]))
            if health_status.status.lower() not in thresholds:
                return EvolutionDecision(
                    symbol,
                    "SKIP",
                    f"Health={health_status.status} not in thresholds {sorted(thresholds)}",
                    old_params=old_params,
                    old_metrics=old_metrics,
                )
            
            logger.info(f"[{symbol}] Health status: {health_status.status} - {health_status.reason}")
            
            # 3) Find best candidate from performance history
            start_dt, end_dt = self._window_to_dates()
            logger.info(f"[{symbol}] Searching history from {start_dt.date()} to {end_dt.date()}")
            
            # Load history from base_dir/logs/performance_history
            history_dir = self.base_dir / "logs" / "performance_history"
            history = load_history(history_dir=history_dir)
            candidates = self._extract_candidates_from_history(symbol, history, start_dt, end_dt)
            
            if not candidates:
                return EvolutionDecision(
                    symbol,
                    "REJECT",
                    "No optimizer candidates found in history",
                    old_params=old_params,
                    old_metrics=old_metrics,
                )
            
            logger.info(f"[{symbol}] Found {len(candidates)} candidates in history")
            
            # 4) Filter by global safety constraints
            viable = self._filter_candidates(candidates)
            
            if not viable:
                return EvolutionDecision(
                    symbol,
                    "REJECT",
                    "All candidates failed global safety filters",
                    old_params=old_params,
                    old_metrics=old_metrics,
                )
            
            logger.info(f"[{symbol}] {len(viable)} candidates passed safety filters")
            
            # 5) Rank and pick best
            viable.sort(
                key=lambda c: (
                    -float(c["metrics"].get("total_return_pct", 0.0)),
                    float(c["metrics"].get("max_drawdown_pct", 0.0)),
                )
            )
            best = viable[0]
            new_params = best.get("params", {})
            new_metrics = best.get("metrics", {}) or {}
            new_return = float(new_metrics.get("total_return_pct", 0.0))
            new_dd = float(new_metrics.get("max_drawdown_pct", 0.0))
            
            logger.info(f"[{symbol}] Best candidate: return={new_return:.2f}%, dd={new_dd:.2f}%")
            
            # 6) Compare vs old profile
            improvement = new_return - old_return
            dd_increase = new_dd - old_dd
            
            min_imp = float(self.cfg.get("min_improvement_return_pct", 0.0))
            max_dd_inc = float(self.cfg.get("max_allowed_dd_increase_pct", 100.0))
            
            if improvement < min_imp:
                return EvolutionDecision(
                    symbol,
                    "REJECT",
                    f"Return improvement {improvement:.2f}% < required {min_imp:.2f}%",
                    old_params=old_params,
                    new_params=new_params,
                    old_metrics=old_metrics,
                    new_metrics=new_metrics,
                    optimizer_run_id=best.get("run_id"),
                )
            
            if dd_increase > max_dd_inc:
                return EvolutionDecision(
                    symbol,
                    "REJECT",
                    f"Drawdown increase {dd_increase:.2f}% > allowed {max_dd_inc:.2f}%",
                    old_params=old_params,
                    new_params=new_params,
                    old_metrics=old_metrics,
                    new_metrics=new_metrics,
                    optimizer_run_id=best.get("run_id"),
                )
            
            logger.info(f"[{symbol}] ✓ Candidate approved: +{improvement:.2f}% return, +{dd_increase:.2f}% dd")
            
            return EvolutionDecision(
                symbol,
                "APPLY",
                f"Candidate passed all filters: +{improvement:.2f}% return",
                old_params=old_params,
                new_params=new_params,
                old_metrics=old_metrics,
                new_metrics=new_metrics,
                optimizer_run_id=best.get("run_id"),
            )
        
        except Exception as e:
            logger.exception(f"[{symbol}] Error evaluating symbol: {e}")
            return EvolutionDecision(
                symbol,
                "ERROR",
                f"Evaluation failed: {str(e)}",
            )
    
    def _extract_candidates_from_history(
        self,
        symbol: str,
        history: List[Dict[str, Any]],
        start_dt: datetime,
        end_dt: datetime,
    ) -> List[Dict[str, Any]]:
        """Extract candidate profiles for symbol from performance history"""
        candidates = []
        
        for run in history:
            # Parse timestamp
            created_at_str = run.get("created_at", "")
            try:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                continue
            
            # Check if within window
            if not (start_dt <= created_at <= end_dt):
                continue
            
            # Extract profiles for this symbol
            for profile_entry in run.get("profiles", []):
                if profile_entry.get("symbol") == symbol:
                    candidates.append({
                        "params": profile_entry.get("params", {}),
                        "metrics": profile_entry.get("metrics", {}),
                        "run_id": run.get("run_id"),
                    })
        
        return candidates
    
    def _filter_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter candidates by global safety constraints"""
        min_trades = int(self.cfg.get("min_trades", 5))
        min_ret = float(self.cfg.get("min_return_pct", 0.0))
        max_dd = float(self.cfg.get("max_dd_pct", 100.0))
        
        viable = []
        for c in candidates:
            m = c.get("metrics", {})
            trades = int(m.get("trades", 0))
            ret = float(m.get("total_return_pct", 0.0))
            dd = float(m.get("max_drawdown_pct", 0.0))
            
            if trades < min_trades:
                continue
            if ret < min_ret:
                continue
            if dd > max_dd:
                continue
            
            viable.append(c)
        
        return viable
    
    def apply_update(self, symbol: str, decision: EvolutionDecision) -> EvolutionDecision:
        """
        Apply evolution decision.
        
        If status == "APPLY" and not dry_run:
        - Archive old profile
        - Write updated profile with new params/metrics
        - Write evolution log
        """
        if decision.status != "APPLY":
            self._write_evolution_log(symbol, decision, applied=False)
            return decision
        
        if self.cfg.get("dry_run", False):
            logger.info(f"[{symbol}] DRY-RUN: Would apply new profile")
            self._write_evolution_log(symbol, decision, applied=False)
            return decision
        
        try:
            profile_path = self.profile_loader.profile_dir / f"{symbol}.json"
            if not profile_path.exists():
                decision.reason = "APPLY requested but profile path is missing"
                decision.status = "ERROR"
                self._write_evolution_log(symbol, decision, applied=False)
                return decision
            
            # Archive old profile
            ts = self._now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"{symbol}_profile_{ts}.json"
            archive_path = self.archive_dir / archive_name
            shutil.copy2(profile_path, archive_path)
            decision.archive_path = str(archive_path)
            
            logger.info(f"[{symbol}] Archived old profile to {archive_path}")
            
            # Load and update profile
            with profile_path.open("r", encoding="utf-8") as f:
                profile = json.load(f)
            
            meta = profile.setdefault("meta", {})
            
            # Increment version
            meta["version"] = int(meta.get("version", 0)) + 1
            meta["source"] = "auto_evolution"
            if decision.optimizer_run_id:
                meta["parent_run_id"] = decision.optimizer_run_id
            meta["updated_at"] = self._now().isoformat().replace('+00:00', 'Z')
            meta["previous_profile"] = archive_name
            
            # Update params and metrics
            profile["params"] = decision.new_params or profile.get("params", {})
            profile["metrics"] = decision.new_metrics or profile.get("metrics", {})
            
            # Write updated profile
            with profile_path.open("w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2)
            
            logger.info(f"[{symbol}] ✓ Applied new profile (version {meta['version']})")
            
            self._write_evolution_log(symbol, decision, applied=True)
            return decision
        
        except Exception as e:
            logger.exception(f"[{symbol}] Error applying update: {e}")
            decision.status = "ERROR"
            decision.reason = f"Apply failed: {str(e)}"
            self._write_evolution_log(symbol, decision, applied=False)
            return decision
    
    def _write_evolution_log(self, symbol: str, decision: EvolutionDecision, applied: bool) -> None:
        """Write evolution decision to audit log"""
        log = {
            "timestamp": self._now().isoformat().replace('+00:00', 'Z'),
            "symbol": symbol,
            "status": decision.status,
            "reason": decision.reason,
            "applied": applied,
            "old_params": decision.old_params,
            "new_params": decision.new_params,
            "old_metrics": decision.old_metrics,
            "new_metrics": decision.new_metrics,
            "optimizer_run_id": decision.optimizer_run_id,
            "archive_path": decision.archive_path,
            "config_snapshot": {
                "min_trades": self.cfg.get("min_trades"),
                "min_return_pct": self.cfg.get("min_return_pct"),
                "max_dd_pct": self.cfg.get("max_dd_pct"),
                "min_improvement_return_pct": self.cfg.get("min_improvement_return_pct"),
                "max_allowed_dd_increase_pct": self.cfg.get("max_allowed_dd_increase_pct"),
                "optimizer_window": self.cfg.get("optimizer_window"),
                "decay_health_thresholds": self.cfg.get("decay_health_thresholds"),
                "dry_run": self.cfg.get("dry_run"),
            },
        }
        
        ts = self._now().strftime("%Y%m%d_%H%M%S_%f")
        path = self.log_dir / f"evolution_run_{symbol}_{ts}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(log, f, indent=2)
    
    async def run_for_all_symbols(self, symbols: Optional[List[str]] = None) -> Dict[str, EvolutionDecision]:
        """
        Run evolution engine for all configured symbols.
        
        Returns dictionary mapping symbol -> decision
        """
        if not self.cfg.get("enable_auto_evolution", False):
            logger.warning("Auto-evolution is disabled in config")
            return {}
        
        if symbols is None or len(symbols) == 0:
            symbols = self.cfg.get("symbols") or []
        
        if not symbols:
            logger.warning("No symbols configured for evolution")
            return {}
        
        logger.info(f"Running evolution for {len(symbols)} symbols...")
        
        results: Dict[str, EvolutionDecision] = {}
        
        for sym in symbols:
            decision = await self.evaluate_symbol(sym)
            decision = self.apply_update(sym, decision)
            results[sym] = decision
        
        # Summary
        counts = {"SKIP": 0, "APPLY": 0, "REJECT": 0, "ERROR": 0}
        for dec in results.values():
            counts[dec.status] = counts.get(dec.status, 0) + 1
        
        logger.info(f"Evolution complete: {counts}")
        
        return results
