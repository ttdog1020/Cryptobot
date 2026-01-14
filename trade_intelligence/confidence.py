"""
Confidence Score Calculation

Computes conviction scores using configurable weighting:
- Strategy agreement (primary)
- Volatility normalization (secondary)
- Optional historical stats
"""

from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


# Default configuration (can be overridden at initialization)
DEFAULT_CONFIDENCE_CONFIG = {
    'weight_agreement': 0.6,           # How much strategy agreement matters
    'weight_volatility': 0.2,          # How much volatility normalization matters
    'weight_historical': 0.2,          # Historical edge (if available)
    'min_base_conviction': 0.3,        # Floor for conviction
    'agreement_decay': 0.05,           # Penalty per missing strategy
}


class ConfidenceCalculator:
    """Compute conviction scores for aggregated signals."""
    
    def __init__(self, config: Optional[Dict[str, float]] = None):
        """
        Initialize confidence calculator.
        
        Args:
            config: Optional override of DEFAULT_CONFIDENCE_CONFIG
        """
        self.config = {**DEFAULT_CONFIDENCE_CONFIG}
        if config:
            self.config.update(config)
        
        # Validate weights sum to 1.0
        weight_sum = (
            self.config['weight_agreement'] +
            self.config['weight_volatility'] +
            self.config['weight_historical']
        )
        if abs(weight_sum - 1.0) > 0.01:
            logger.warning(
                f"Confidence weights sum to {weight_sum:.2f}, not 1.0. "
                f"Normalizing weights."
            )
            # Normalize
            factor = 1.0 / weight_sum
            self.config['weight_agreement'] *= factor
            self.config['weight_volatility'] *= factor
            self.config['weight_historical'] *= factor
    
    def compute_agreement_score(
        self,
        num_strategies: int,
        agreeing_count: int,
    ) -> float:
        """
        Compute agreement confidence component.
        
        Args:
            num_strategies: Total number of strategies
            agreeing_count: How many agree
        
        Returns:
            Score 0.0-1.0
        """
        if num_strategies == 0:
            return 0.0
        
        # Base agreement ratio
        agreement_ratio = agreeing_count / num_strategies
        
        # Apply decay penalty for missing strategies
        # (i.e., single strategy has lower confidence than 3-strategy consensus)
        decay_penalty = (num_strategies - 1) * self.config['agreement_decay']
        decay_penalty = min(decay_penalty, 0.4)  # Cap penalty at 40%
        
        agreement_score = agreement_ratio * (1.0 - decay_penalty)
        return max(agreement_score, 0.0)
    
    def compute_volatility_normalization(
        self,
        volatility_percentile: Optional[float],
    ) -> float:
        """
        Compute volatility normalization component.
        
        Higher volatility → lower confidence (more noise).
        Volatility percentile: 0 (very low vol) - 100 (very high vol).
        
        Args:
            volatility_percentile: Current volatility percentile (0-100), or None
        
        Returns:
            Score 0.0-1.0
        """
        if volatility_percentile is None:
            # If no data, assume neutral
            return 0.5
        
        # Clamp to [0, 100]
        vp = max(0.0, min(100.0, volatility_percentile))
        
        # High vol (80+) → score 0.4
        # Mid vol (40-60) → score 0.9
        # Low vol (0-20) → score 0.7 (too quiet, fewer opportunities)
        
        if vp < 20:
            return 0.7
        elif vp < 40:
            return 0.8
        elif vp <= 60:
            return 0.9  # Optimal zone
        elif vp < 80:
            return 0.7
        else:
            return 0.4  # Too volatile
    
    def compute_historical_score(
        self,
        win_rate: Optional[float] = None,
    ) -> float:
        """
        Compute historical component.
        
        Args:
            win_rate: Historical win rate of strategy (0.0-1.0), or None
        
        Returns:
            Score 0.0-1.0
        """
        if win_rate is None:
            # Default to neutral
            return 0.5
        
        # Win rate directly translates to confidence
        # (clamped to [0.2, 1.0] to avoid extremes)
        return max(0.2, min(1.0, win_rate))
    
    def compute_conviction(
        self,
        num_strategies: int,
        agreeing_count: int,
        volatility_percentile: Optional[float] = None,
        win_rate: Optional[float] = None,
    ) -> float:
        """
        Compute overall conviction score.
        
        Args:
            num_strategies: Total strategies
            agreeing_count: Agreeing strategies
            volatility_percentile: Current vol percentile (0-100)
            win_rate: Historical win rate (0-1)
        
        Returns:
            Conviction score 0.0-1.0
        """
        # Compute components
        agreement = self.compute_agreement_score(num_strategies, agreeing_count)
        volatility = self.compute_volatility_normalization(volatility_percentile)
        historical = self.compute_historical_score(win_rate)
        
        # Weighted combination
        conviction = (
            agreement * self.config['weight_agreement'] +
            volatility * self.config['weight_volatility'] +
            historical * self.config['weight_historical']
        )
        
        # Apply floor
        conviction = max(conviction, self.config['min_base_conviction'])
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, conviction))
    
    def get_config(self) -> Dict[str, float]:
        """Get current configuration."""
        return self.config.copy()
