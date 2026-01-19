"""
Fee Schedule and Dynamic Slippage Modeling

Provides realistic commission and slippage calculation based on:
- Exchange fee tiers (volume-based)
- Order size relative to market depth
- Bid-ask spread simulation
- Market volatility adjustment

Compatible with Binance spot trading fee structure.
"""

import logging
from typing import Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class BinanceTier(Enum):
    """Binance VIP tier levels based on 30-day trading volume."""
    REGULAR = "Regular"      # < 50 BTC
    VIP0 = "VIP 0"          # >= 50 BTC
    VIP1 = "VIP 1"          # >= 500 BTC
    VIP2 = "VIP 2"          # >= 1,500 BTC
    VIP3 = "VIP 3"          # >= 4,500 BTC
    VIP4 = "VIP 4"          # >= 10,000 BTC


@dataclass
class FeeStructure:
    """Fee structure for a specific tier."""
    tier: BinanceTier
    maker_fee: float  # Maker fee as fraction (e.g., 0.001 = 0.1%)
    taker_fee: float  # Taker fee as fraction
    min_volume_btc: float  # Minimum 30-day volume in BTC


# Binance spot trading fee schedule (as of 2024)
BINANCE_FEE_SCHEDULE = {
    BinanceTier.REGULAR: FeeStructure(BinanceTier.REGULAR, 0.001, 0.001, 0),      # 0.1% / 0.1%
    BinanceTier.VIP0: FeeStructure(BinanceTier.VIP0, 0.0009, 0.001, 50),          # 0.09% / 0.1%
    BinanceTier.VIP1: FeeStructure(BinanceTier.VIP1, 0.0008, 0.00095, 500),       # 0.08% / 0.095%
    BinanceTier.VIP2: FeeStructure(BinanceTier.VIP2, 0.0007, 0.0009, 1500),       # 0.07% / 0.09%
    BinanceTier.VIP3: FeeStructure(BinanceTier.VIP3, 0.0006, 0.00085, 4500),      # 0.06% / 0.085%
    BinanceTier.VIP4: FeeStructure(BinanceTier.VIP4, 0.0005, 0.0008, 10000),      # 0.05% / 0.08%
}


class FeeSchedule:
    """
    Manages fee calculation based on exchange tier and order characteristics.
    
    Features:
    - Volume-based tier lookup
    - Maker/taker fee distinction
    - BNB discount simulation (optional)
    - Custom fee override support
    """
    
    def __init__(
        self,
        exchange: str = "binance",
        tier: BinanceTier = BinanceTier.REGULAR,
        use_bnb_discount: bool = False,
        custom_fee_schedule: Optional[Dict[BinanceTier, FeeStructure]] = None
    ):
        """
        Initialize fee schedule.
        
        Args:
            exchange: Exchange name (currently only 'binance' supported)
            tier: Starting fee tier
            use_bnb_discount: Apply 25% BNB discount (Binance feature)
            custom_fee_schedule: Optional custom fee structure
        """
        self.exchange = exchange.lower()
        self.tier = tier
        self.use_bnb_discount = use_bnb_discount
        self.bnb_discount = 0.75 if use_bnb_discount else 1.0  # 25% discount = 0.75 multiplier
        
        if custom_fee_schedule:
            self.fee_schedule = custom_fee_schedule
        elif self.exchange == "binance":
            self.fee_schedule = BINANCE_FEE_SCHEDULE
        else:
            # Default to regular tier
            self.fee_schedule = {
                BinanceTier.REGULAR: FeeStructure(BinanceTier.REGULAR, 0.001, 0.001, 0)
            }
        
        logger.info(f"FeeSchedule initialized: {self.exchange}, tier={tier.value}, BNB discount={use_bnb_discount}")
    
    def update_tier(self, monthly_volume_btc: float):
        """
        Update fee tier based on 30-day trading volume.
        
        Args:
            monthly_volume_btc: 30-day trading volume in BTC equivalent
        """
        # Find appropriate tier
        for tier in [BinanceTier.VIP4, BinanceTier.VIP3, BinanceTier.VIP2, 
                     BinanceTier.VIP1, BinanceTier.VIP0]:
            fee_structure = self.fee_schedule.get(tier)
            if fee_structure and monthly_volume_btc >= fee_structure.min_volume_btc:
                self.tier = tier
                logger.info(f"Fee tier updated to {tier.value} (volume: {monthly_volume_btc:.2f} BTC)")
                return
        
        self.tier = BinanceTier.REGULAR
    
    def get_commission(
        self,
        order_value: float,
        is_maker: bool = False
    ) -> float:
        """
        Calculate commission for an order.
        
        Args:
            order_value: Total order value in quote currency (e.g., USDT)
            is_maker: True if maker order, False if taker
            
        Returns:
            Commission amount in quote currency
        """
        fee_structure = self.fee_schedule.get(self.tier, self.fee_schedule[BinanceTier.REGULAR])
        
        if is_maker:
            base_fee = order_value * fee_structure.maker_fee
        else:
            base_fee = order_value * fee_structure.taker_fee
        
        # Apply BNB discount if enabled
        commission = base_fee * self.bnb_discount
        
        return commission
    
    def get_fee_rate(self, is_maker: bool = False) -> float:
        """
        Get fee rate as fraction for current tier.
        
        Args:
            is_maker: True for maker rate, False for taker rate
            
        Returns:
            Fee rate as fraction (e.g., 0.001 = 0.1%)
        """
        fee_structure = self.fee_schedule.get(self.tier, self.fee_schedule[BinanceTier.REGULAR])
        
        if is_maker:
            rate = fee_structure.maker_fee
        else:
            rate = fee_structure.taker_fee
        
        return rate * self.bnb_discount


class DynamicSlippageModel:
    """
    Calculates realistic slippage based on order characteristics.
    
    Factors:
    - Order size relative to average volume
    - Market volatility
    - Bid-ask spread
    - Time of day (optional)
    """
    
    def __init__(
        self,
        base_slippage: float = 0.0005,  # 0.05% base
        volatility_multiplier: float = 1.0,
        max_slippage: float = 0.01  # 1% cap
    ):
        """
        Initialize slippage model.
        
        Args:
            base_slippage: Minimum slippage for small orders
            volatility_multiplier: Adjustment for market volatility
            max_slippage: Maximum slippage cap
        """
        self.base_slippage = base_slippage
        self.volatility_multiplier = volatility_multiplier
        self.max_slippage = max_slippage
        
        logger.info(f"DynamicSlippageModel initialized: base={base_slippage*100:.3f}%, max={max_slippage*100:.2f}%")
    
    def calculate_slippage(
        self,
        order_value: float,
        market_volume_24h: float,
        volatility: Optional[float] = None,
        spread_pct: Optional[float] = None
    ) -> float:
        """
        Calculate slippage for an order.
        
        Args:
            order_value: Order value in quote currency
            market_volume_24h: 24h market volume in quote currency
            volatility: Optional volatility measure (e.g., ATR / price)
            spread_pct: Optional bid-ask spread as percentage
            
        Returns:
            Slippage as fraction of order value
        """
        # Base slippage
        slippage = self.base_slippage
        
        # Volume impact: larger orders relative to volume have more slippage
        if market_volume_24h > 0:
            volume_ratio = order_value / market_volume_24h
            volume_impact = volume_ratio * 100  # Scale factor
            slippage += volume_impact
        
        # Volatility adjustment
        if volatility is not None:
            volatility_impact = volatility * self.volatility_multiplier
            slippage += volatility_impact
        
        # Spread component (half the spread is typical slippage cost)
        if spread_pct is not None:
            spread_impact = spread_pct / 2
            slippage += spread_impact
        
        # Cap at max slippage
        slippage = min(slippage, self.max_slippage)
        
        return slippage
    
    def calculate_slippage_simple(
        self,
        order_size_ratio: float,
        volatility: float = 0.0
    ) -> float:
        """
        Simplified slippage calculation based on order size ratio.
        
        Args:
            order_size_ratio: Order size as fraction of avg volume (e.g., 0.01 = 1%)
            volatility: Volatility adjustment (0.0 - 1.0)
            
        Returns:
            Slippage as fraction
        """
        slippage = self.base_slippage + (order_size_ratio * 0.5) + (volatility * 0.002)
        return min(slippage, self.max_slippage)


class SpreadModel:
    """
    Simulates bid-ask spread behavior.
    
    Features:
    - Base spread by liquidity tier
    - Volatility-adjusted spread
    - Volume-dependent tightening
    """
    
    def __init__(
        self,
        base_spread_bps: float = 5.0,  # 5 basis points = 0.05%
        volatility_multiplier: float = 10.0,
        min_spread_bps: float = 1.0,
        max_spread_bps: float = 50.0
    ):
        """
        Initialize spread model.
        
        Args:
            base_spread_bps: Base spread in basis points (1 bps = 0.01%)
            volatility_multiplier: How much volatility widens spread
            min_spread_bps: Minimum spread
            max_spread_bps: Maximum spread
        """
        self.base_spread_bps = base_spread_bps
        self.volatility_multiplier = volatility_multiplier
        self.min_spread_bps = min_spread_bps
        self.max_spread_bps = max_spread_bps
    
    def calculate_spread(
        self,
        price: float,
        volatility: float = 0.0,
        volume_ratio: float = 1.0
    ) -> Tuple[float, float]:
        """
        Calculate bid and ask prices with spread.
        
        Args:
            price: Mid price
            volatility: Current volatility (as fraction, e.g., 0.02 = 2%)
            volume_ratio: Volume relative to average (1.0 = normal, >1 = high volume)
            
        Returns:
            (bid_price, ask_price) tuple
        """
        # Calculate spread in bps
        spread_bps = self.base_spread_bps
        
        # Volatility widens spread
        spread_bps += volatility * self.volatility_multiplier * 100
        
        # High volume tightens spread
        if volume_ratio > 1.0:
            spread_bps *= (1.0 / volume_ratio)
        
        # Clamp to limits
        spread_bps = max(self.min_spread_bps, min(spread_bps, self.max_spread_bps))
        
        # Convert to fraction
        spread_fraction = spread_bps / 10000  # bps to fraction
        
        # Calculate bid/ask
        half_spread = price * spread_fraction / 2
        bid = price - half_spread
        ask = price + half_spread
        
        return bid, ask


class RealisticExecutionModel:
    """
    Combined model for realistic execution costs.
    
    Integrates:
    - Fee schedule (tier-based)
    - Dynamic slippage
    - Bid-ask spread
    - Partial fill simulation (optional)
    """
    
    def __init__(
        self,
        fee_schedule: Optional[FeeSchedule] = None,
        slippage_model: Optional[DynamicSlippageModel] = None,
        spread_model: Optional[SpreadModel] = None
    ):
        """
        Initialize execution model.
        
        Args:
            fee_schedule: FeeSchedule instance (default: Regular tier)
            slippage_model: DynamicSlippageModel instance
            spread_model: SpreadModel instance
        """
        self.fee_schedule = fee_schedule or FeeSchedule()
        self.slippage_model = slippage_model or DynamicSlippageModel()
        self.spread_model = spread_model or SpreadModel()
        
        logger.info("RealisticExecutionModel initialized with all components")
    
    def calculate_execution_costs(
        self,
        order_value: float,
        price: float,
        is_buy: bool,
        is_maker: bool = False,
        market_volume_24h: Optional[float] = None,
        volatility: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate all execution costs for an order.
        
        Args:
            order_value: Order value in quote currency
            price: Execution price
            is_buy: True if buy order
            is_maker: True if maker order
            market_volume_24h: Optional 24h volume for slippage calc
            volatility: Optional volatility for adjustments
            
        Returns:
            Dict with: commission, slippage_cost, spread_cost, total_cost, effective_price
        """
        # Commission
        commission = self.fee_schedule.get_commission(order_value, is_maker=is_maker)
        
        # Slippage
        if market_volume_24h:
            slippage_fraction = self.slippage_model.calculate_slippage(
                order_value, market_volume_24h, volatility
            )
        else:
            # Use simplified model if no volume data
            order_size_ratio = 0.001  # Assume 0.1% of daily volume
            slippage_fraction = self.slippage_model.calculate_slippage_simple(
                order_size_ratio, volatility or 0.0
            )
        
        slippage_cost = order_value * slippage_fraction
        
        # Spread cost
        bid, ask = self.spread_model.calculate_spread(
            price, volatility or 0.0, 1.0
        )
        
        if is_buy:
            effective_price = ask
            spread_cost = (ask - price) * (order_value / price)  # Extra cost from spread
        else:
            effective_price = bid
            spread_cost = (price - bid) * (order_value / price)  # Lost value from spread
        
        # Total cost
        total_cost = commission + slippage_cost + spread_cost
        
        return {
            "commission": commission,
            "slippage_cost": slippage_cost,
            "spread_cost": spread_cost,
            "total_cost": total_cost,
            "effective_price": effective_price,
            "slippage_fraction": slippage_fraction,
            "commission_rate": self.fee_schedule.get_fee_rate(is_maker)
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test fee schedule
    print("=== Fee Schedule Test ===")
    fees = FeeSchedule(tier=BinanceTier.REGULAR)
    order_value = 1000.0
    commission = fees.get_commission(order_value, is_maker=False)
    print(f"Order value: ${order_value}")
    print(f"Taker commission (Regular tier): ${commission:.4f} ({commission/order_value*100:.3f}%)")
    
    # Test slippage
    print("\n=== Slippage Model Test ===")
    slippage_model = DynamicSlippageModel()
    slippage = slippage_model.calculate_slippage_simple(order_size_ratio=0.01, volatility=0.02)
    print(f"Slippage for 1% order size, 2% volatility: {slippage*100:.4f}%")
    
    # Test spread
    print("\n=== Spread Model Test ===")
    spread_model = SpreadModel()
    bid, ask = spread_model.calculate_spread(price=50000, volatility=0.01)
    print(f"Mid: $50000, Bid: ${bid:.2f}, Ask: ${ask:.2f}, Spread: ${ask-bid:.2f}")
    
    # Test combined model
    print("\n=== Realistic Execution Model Test ===")
    exec_model = RealisticExecutionModel()
    costs = exec_model.calculate_execution_costs(
        order_value=1000.0,
        price=50000,
        is_buy=True,
        is_maker=False,
        market_volume_24h=1000000,
        volatility=0.015
    )
    print(f"Order: $1000 @ $50000 (BUY, TAKER)")
    for key, value in costs.items():
        if 'price' in key or 'rate' in key or 'fraction' in key:
            print(f"  {key}: {value:.6f}")
        else:
            print(f"  {key}: ${value:.4f}")
