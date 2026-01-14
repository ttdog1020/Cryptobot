"""
Multi-Strategy Signal Aggregation

Combines outputs from multiple strategies via thin wrapper adapters
without refactoring strategy code.
"""

from typing import List, Dict, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class StrategyOutputFormat(str, Enum):
    """Supported strategy output formats."""
    TRADE_INTENT = "TradeIntent"  # Our standard internal format
    SIGNAL_DICT = "SignalDict"    # Simple dict with 'signal' key
    BOOLEAN = "Boolean"           # True = BUY, False = SELL


class StrategyAdapter:
    """Thin wrapper to normalize strategy outputs."""
    
    def __init__(self, format_type: StrategyOutputFormat):
        """
        Initialize adapter.
        
        Args:
            format_type: Expected output format
        """
        self.format_type = format_type
    
    def normalize(self, output: Any) -> Dict[str, Any]:
        """
        Normalize strategy output to standard format.
        
        Returns:
            {
                'signal': 'LONG'|'SHORT'|'FLAT',
                'confidence': float 0-1 (optional),
                'metadata': {...}
            }
        """
        if self.format_type == StrategyOutputFormat.TRADE_INTENT:
            # Already normalized
            if isinstance(output, dict) and 'signal' in output:
                return {
                    'signal': output.get('signal', 'FLAT'),
                    'confidence': output.get('confidence', 0.5),
                    'metadata': output.get('metadata', {}),
                }
        
        elif self.format_type == StrategyOutputFormat.SIGNAL_DICT:
            # Simple dict with 'signal' key
            if isinstance(output, dict) and 'signal' in output:
                return {
                    'signal': output.get('signal', 'FLAT'),
                    'confidence': output.get('confidence', 0.5),
                    'metadata': output.get('metadata', {}),
                }
        
        elif self.format_type == StrategyOutputFormat.BOOLEAN:
            # True=LONG, False=FLAT/SHORT
            if isinstance(output, bool):
                return {
                    'signal': 'LONG' if output else 'FLAT',
                    'confidence': 0.6 if output else 0.0,
                    'metadata': {},
                }
        
        # Fallback
        logger.warning(f"Could not normalize output: {output}")
        return {
            'signal': 'FLAT',
            'confidence': 0.0,
            'metadata': {},
        }


class SignalAggregator:
    """Aggregate signals from multiple strategies."""
    
    def __init__(self):
        """Initialize aggregator."""
        self.adapters: Dict[str, StrategyAdapter] = {}
    
    def register_strategy(
        self,
        name: str,
        format_type: StrategyOutputFormat = StrategyOutputFormat.TRADE_INTENT,
    ):
        """Register a strategy with expected output format."""
        self.adapters[name] = StrategyAdapter(format_type)
        logger.info(f"Registered strategy '{name}' with format {format_type}")
    
    def aggregate(
        self,
        strategy_outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Aggregate multiple strategy outputs.
        
        Args:
            strategy_outputs: {strategy_name: output_value, ...}
        
        Returns:
            {
                'direction': 'LONG'|'SHORT'|'FLAT',
                'num_strategies': int,
                'agreeing': int,
                'agreement_ratio': float,
                'per_strategy': {name: normalized_output, ...}
            }
        """
        if not strategy_outputs:
            return {
                'direction': 'FLAT',
                'num_strategies': 0,
                'agreeing': 0,
                'agreement_ratio': 0.0,
                'per_strategy': {},
            }
        
        normalized = {}
        long_count = 0
        short_count = 0
        flat_count = 0
        
        for name, output in strategy_outputs.items():
            adapter = self.adapters.get(name)
            if adapter is None:
                # Use default adapter
                adapter = StrategyAdapter(StrategyOutputFormat.TRADE_INTENT)
            
            try:
                norm = adapter.normalize(output)
                normalized[name] = norm
                
                signal = norm.get('signal', 'FLAT')
                if signal == 'LONG':
                    long_count += 1
                elif signal == 'SHORT':
                    short_count += 1
                else:
                    flat_count += 1
            
            except Exception as e:
                logger.error(f"Error normalizing {name}: {e}")
                normalized[name] = {
                    'signal': 'FLAT',
                    'confidence': 0.0,
                    'metadata': {'error': str(e)},
                }
                flat_count += 1
        
        # Determine dominant direction
        total = long_count + short_count + flat_count
        if long_count > short_count and long_count > flat_count:
            direction = 'LONG'
            agreeing = long_count
        elif short_count > long_count and short_count > flat_count:
            direction = 'SHORT'
            agreeing = short_count
        else:
            direction = 'FLAT'
            agreeing = flat_count
        
        return {
            'direction': direction,
            'num_strategies': total,
            'agreeing': agreeing,
            'agreement_ratio': agreeing / total if total > 0 else 0.0,
            'per_strategy': normalized,
        }
