"""
MODULE 18: Exchange Client Base

Abstract base class for exchange integrations.
Will be implemented in Module 19 for real exchange trading.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

from .order_types import OrderRequest, ExecutionResult, Position


class ExchangeClientBase(ABC):
    """
    Abstract base class for exchange clients.
    
    Defines the interface that all exchange implementations must follow.
    Future implementations: BinanceClient, CoinbaseClient, etc.
    """
    
    @abstractmethod
    async def submit_order(
        self,
        order: OrderRequest
    ) -> ExecutionResult:
        """
        Submit an order to the exchange.
        
        Args:
            order: OrderRequest to submit
            
        Returns:
            ExecutionResult with fill details or error
        """
        pass
    
    @abstractmethod
    async def cancel_order(
        self,
        order_id: str,
        symbol: str
    ) -> bool:
        """
        Cancel an open order.
        
        Args:
            order_id: Order ID to cancel
            symbol: Symbol of the order
            
        Returns:
            True if cancelled successfully
        """
        pass
    
    @abstractmethod
    async def get_balance(self) -> Dict[str, float]:
        """
        Get account balances.
        
        Returns:
            Dict of {currency: balance}
        """
        pass
    
    @abstractmethod
    async def get_open_positions(self) -> Dict[str, Position]:
        """
        Get all open positions.
        
        Returns:
            Dict of {symbol: Position}
        """
        pass
    
    @abstractmethod
    async def get_open_orders(self) -> List[Dict[str, Any]]:
        """
        Get all open orders.
        
        Returns:
            List of open order dicts
        """
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Get status of a specific order.
        
        Args:
            order_id: Order ID
            symbol: Symbol
            
        Returns:
            Order status dict
        """
        pass
    
    @abstractmethod
    async def get_current_price(self, symbol: str) -> float:
        """
        Get current market price for a symbol.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Current price
        """
        pass
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to exchange.
        
        Returns:
            True if connected successfully
        """
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from exchange."""
        pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to exchange."""
        pass
    
    @property
    @abstractmethod
    def exchange_name(self) -> str:
        """Get exchange name."""
        pass
