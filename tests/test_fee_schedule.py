"""
Unit tests for fee schedule and realistic execution modeling.

Tests:
- Fee schedule (tier-based commissions)
- Dynamic slippage model
- Bid-ask spread simulation
- Realistic execution model integration
- Configuration loading
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from execution.fee_schedule import (
    FeeSchedule, BinanceTier, FeeStructure,
    DynamicSlippageModel, SpreadModel, RealisticExecutionModel
)


class TestFeeSchedule:
    """Tests for FeeSchedule class."""
    
    def test_regular_tier_initialization(self):
        """Test initialization with regular tier."""
        fees = FeeSchedule(tier=BinanceTier.REGULAR)
        
        assert fees.tier == BinanceTier.REGULAR
        assert fees.exchange == "binance"
        assert not fees.use_bnb_discount
    
    def test_bnb_discount(self):
        """Test BNB discount application."""
        fees_no_discount = FeeSchedule(use_bnb_discount=False)
        fees_with_discount = FeeSchedule(use_bnb_discount=True)
        
        order_value = 1000.0
        comm_no_discount = fees_no_discount.get_commission(order_value, is_maker=False)
        comm_with_discount = fees_with_discount.get_commission(order_value, is_maker=False)
        
        # With discount should be 75% of without (25% discount)
        assert comm_with_discount == pytest.approx(comm_no_discount * 0.75, rel=0.01)
    
    def test_maker_vs_taker_fees(self):
        """Test maker fees are lower than taker fees."""
        fees = FeeSchedule(tier=BinanceTier.REGULAR)
        
        order_value = 1000.0
        maker_comm = fees.get_commission(order_value, is_maker=True)
        taker_comm = fees.get_commission(order_value, is_maker=False)
        
        # For most tiers, maker <= taker
        assert maker_comm <= taker_comm
    
    def test_tier_upgrade(self):
        """Test tier upgrade based on volume."""
        fees = FeeSchedule(tier=BinanceTier.REGULAR)
        
        # Upgrade to VIP0 (requires 50 BTC volume)
        fees.update_tier(monthly_volume_btc=50)
        assert fees.tier == BinanceTier.VIP0
        
        # Upgrade to VIP2 (requires 1500 BTC volume)
        fees.update_tier(monthly_volume_btc=1500)
        assert fees.tier == BinanceTier.VIP2
    
    def test_vip_tiers_lower_fees(self):
        """Test that VIP tiers have lower fees than regular."""
        regular_fees = FeeSchedule(tier=BinanceTier.REGULAR)
        vip_fees = FeeSchedule(tier=BinanceTier.VIP2)
        
        order_value = 1000.0
        regular_rate = regular_fees.get_fee_rate(is_maker=False)
        vip_rate = vip_fees.get_fee_rate(is_maker=False)
        
        assert vip_rate < regular_rate
    
    def test_get_fee_rate(self):
        """Test fee rate retrieval."""
        fees = FeeSchedule(tier=BinanceTier.REGULAR)
        
        taker_rate = fees.get_fee_rate(is_maker=False)
        maker_rate = fees.get_fee_rate(is_maker=True)
        
        # Regular tier: 0.1% for both
        assert taker_rate == pytest.approx(0.001, abs=0.0001)
        assert maker_rate == pytest.approx(0.001, abs=0.0001)


class TestDynamicSlippageModel:
    """Tests for DynamicSlippageModel class."""
    
    def test_base_slippage(self):
        """Test base slippage for small orders."""
        model = DynamicSlippageModel(base_slippage=0.0005)
        
        # Small order, low volume impact
        slippage = model.calculate_slippage_simple(
            order_size_ratio=0.0001,
            volatility=0.0
        )
        
        # Should be close to base slippage
        assert slippage >= 0.0005
        assert slippage < 0.001
    
    def test_volume_impact(self):
        """Test that larger orders have more slippage."""
        model = DynamicSlippageModel(base_slippage=0.0005)
        
        small_order = model.calculate_slippage_simple(order_size_ratio=0.001, volatility=0.0)
        large_order = model.calculate_slippage_simple(order_size_ratio=0.05, volatility=0.0)
        
        assert large_order > small_order
    
    def test_volatility_impact(self):
        """Test that volatility increases slippage."""
        model = DynamicSlippageModel(base_slippage=0.0005)
        
        low_vol = model.calculate_slippage_simple(order_size_ratio=0.01, volatility=0.0)
        high_vol = model.calculate_slippage_simple(order_size_ratio=0.01, volatility=0.05)
        
        assert high_vol > low_vol
    
    def test_max_slippage_cap(self):
        """Test that slippage is capped at max_slippage."""
        model = DynamicSlippageModel(base_slippage=0.0005, max_slippage=0.01)
        
        # Extreme conditions
        slippage = model.calculate_slippage_simple(order_size_ratio=1.0, volatility=1.0)
        
        assert slippage <= 0.01
    
    def test_full_slippage_calculation(self):
        """Test full slippage calculation with market data."""
        model = DynamicSlippageModel(base_slippage=0.0005, max_slippage=0.01)
        
        slippage = model.calculate_slippage(
            order_value=1000,
            market_volume_24h=1000000,
            volatility=0.02,
            spread_pct=0.001
        )
        
        assert slippage > 0
        assert slippage <= 0.01


class TestSpreadModel:
    """Tests for SpreadModel class."""
    
    def test_basic_spread(self):
        """Test basic bid/ask spread calculation."""
        model = SpreadModel(base_spread_bps=5.0)
        
        mid_price = 50000
        bid, ask = model.calculate_spread(mid_price)
        
        assert bid < mid_price
        assert ask > mid_price
        assert ask - bid > 0
    
    def test_volatility_widens_spread(self):
        """Test that volatility widens the spread."""
        model = SpreadModel(base_spread_bps=5.0)
        
        bid_low, ask_low = model.calculate_spread(50000, volatility=0.0)
        bid_high, ask_high = model.calculate_spread(50000, volatility=0.05)
        
        spread_low = ask_low - bid_low
        spread_high = ask_high - bid_high
        
        assert spread_high > spread_low
    
    def test_volume_tightens_spread(self):
        """Test that high volume tightens the spread."""
        model = SpreadModel(base_spread_bps=5.0)
        
        bid_normal, ask_normal = model.calculate_spread(50000, volume_ratio=1.0)
        bid_high_vol, ask_high_vol = model.calculate_spread(50000, volume_ratio=2.0)
        
        spread_normal = ask_normal - bid_normal
        spread_high_vol = ask_high_vol - bid_high_vol
        
        assert spread_high_vol < spread_normal
    
    def test_spread_limits(self):
        """Test spread min/max limits."""
        model = SpreadModel(
            base_spread_bps=5.0,
            min_spread_bps=1.0,
            max_spread_bps=50.0
        )
        
        # Test max limit with extreme volatility
        bid_extreme, ask_extreme = model.calculate_spread(50000, volatility=10.0)
        spread_extreme = ask_extreme - bid_extreme
        
        # Spread should be capped
        max_spread_value = 50000 * (50.0 / 10000)
        assert spread_extreme <= max_spread_value * 1.01  # Allow small rounding


class TestRealisticExecutionModel:
    """Tests for RealisticExecutionModel integration."""
    
    def test_initialization(self):
        """Test model initialization with defaults."""
        model = RealisticExecutionModel()
        
        assert model.fee_schedule is not None
        assert model.slippage_model is not None
        assert model.spread_model is not None
    
    def test_custom_components(self):
        """Test initialization with custom components."""
        custom_fees = FeeSchedule(tier=BinanceTier.VIP2)
        custom_slippage = DynamicSlippageModel(base_slippage=0.0003)
        custom_spread = SpreadModel(base_spread_bps=3.0)
        
        model = RealisticExecutionModel(
            fee_schedule=custom_fees,
            slippage_model=custom_slippage,
            spread_model=custom_spread
        )
        
        assert model.fee_schedule.tier == BinanceTier.VIP2
    
    def test_buy_order_costs(self):
        """Test execution cost calculation for buy order."""
        model = RealisticExecutionModel()
        
        price = 50000
        costs = model.calculate_execution_costs(
            order_value=1000.0,
            price=price,
            is_buy=True,
            is_maker=False,
            market_volume_24h=1000000,
            volatility=0.01
        )
        
        assert "commission" in costs
        assert "slippage_cost" in costs
        assert "spread_cost" in costs
        assert "total_cost" in costs
        assert "effective_price" in costs
        
        # All costs should be positive
        assert costs["commission"] > 0
        assert costs["slippage_cost"] >= 0
        assert costs["spread_cost"] >= 0
        assert costs["total_cost"] > 0
        
        # Effective price should be higher for buy (pay ask)
        assert costs["effective_price"] >= price
    
    def test_sell_order_costs(self):
        """Test execution cost calculation for sell order."""
        model = RealisticExecutionModel()
        
        price = 50000
        costs = model.calculate_execution_costs(
            order_value=1000.0,
            price=price,
            is_buy=False,
            is_maker=False,
            market_volume_24h=1000000,
            volatility=0.01
        )
        
        # Effective price should be lower for sell (receive bid)
        assert costs["effective_price"] <= price
    
    def test_maker_vs_taker_costs(self):
        """Test that maker orders have lower commission."""
        model = RealisticExecutionModel()
        
        maker_costs = model.calculate_execution_costs(
            order_value=1000.0,
            price=50000,
            is_buy=True,
            is_maker=True
        )
        
        taker_costs = model.calculate_execution_costs(
            order_value=1000.0,
            price=50000,
            is_buy=True,
            is_maker=False
        )
        
        assert maker_costs["commission"] <= taker_costs["commission"]
    
    def test_costs_scale_with_order_size(self):
        """Test that costs scale with order size."""
        model = RealisticExecutionModel()
        
        small_costs = model.calculate_execution_costs(
            order_value=100.0,
            price=50000,
            is_buy=True
        )
        
        large_costs = model.calculate_execution_costs(
            order_value=10000.0,
            price=50000,
            is_buy=True
        )
        
        # Larger orders should have higher absolute costs
        assert large_costs["total_cost"] > small_costs["total_cost"]
    
    def test_high_volatility_increases_costs(self):
        """Test that volatility increases execution costs."""
        model = RealisticExecutionModel()
        
        low_vol_costs = model.calculate_execution_costs(
            order_value=1000.0,
            price=50000,
            is_buy=True,
            volatility=0.005
        )
        
        high_vol_costs = model.calculate_execution_costs(
            order_value=1000.0,
            price=50000,
            is_buy=True,
            volatility=0.05
        )
        
        # Higher volatility should increase slippage and spread costs
        assert high_vol_costs["slippage_cost"] > low_vol_costs["slippage_cost"]
        assert high_vol_costs["spread_cost"] > low_vol_costs["spread_cost"]


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_zero_order_value(self):
        """Test handling of zero order value."""
        fees = FeeSchedule()
        commission = fees.get_commission(0.0, is_maker=False)
        
        assert commission == 0.0
    
    def test_negative_volume(self):
        """Test handling of invalid volume."""
        model = DynamicSlippageModel()
        
        # Should handle gracefully (use base slippage)
        slippage = model.calculate_slippage(
            order_value=1000,
            market_volume_24h=-1000,
            volatility=0.01
        )
        
        assert slippage > 0
    
    def test_extreme_volatility(self):
        """Test handling of extreme volatility."""
        model = DynamicSlippageModel(max_slippage=0.05)
        
        slippage = model.calculate_slippage_simple(
            order_size_ratio=0.1,
            volatility=100.0  # Extreme
        )
        
        # Should be capped
        assert slippage <= 0.05
    
    def test_zero_price_spread(self):
        """Test spread calculation with zero price."""
        model = SpreadModel()
        
        bid, ask = model.calculate_spread(0.0)
        
        assert bid == 0.0
        assert ask == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
