"""
MODULE 16: Stream Router

Manages multiple WebSocket connections and routes data to strategies.
Maintains latest candle state for each symbol and provides async interfaces.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from collections import defaultdict
import inspect
import pandas as pd

from .websocket_client import BinanceWebSocketClient

logger = logging.getLogger(__name__)


class StreamRouter:
    """
    Async manager for WebSocket data streams.
    
    Responsibilities:
    - Start/stop WebSocket clients for multiple symbols
    - Maintain latest candle data for each symbol
    - Route data to registered strategies/callbacks
    - Provide access to current market state
    """
    
    def __init__(
        self,
        exchange: str = "binance",
        symbols: List[str] = None,
        timeframe: str = "1m",
        ws_base_url: Optional[str] = None,
        reconnect_delay: int = 3,
        max_retries: int = 5,
        heartbeat_interval: int = 30
    ):
        """
        Initialize stream router.
        
        Args:
            exchange: Exchange name ("binance" or "binance_us")
            symbols: List of trading pairs to subscribe to
            timeframe: Candlestick timeframe
            ws_base_url: WebSocket base URL (None = auto-select based on exchange)
            reconnect_delay: WebSocket reconnection delay
            max_retries: Max reconnection attempts
            heartbeat_interval: Heartbeat check interval
        """
        self.exchange = exchange.lower()
        self.symbols = symbols or []
        self.timeframe = timeframe
        self.ws_base_url = ws_base_url
        self.reconnect_delay = reconnect_delay
        self.max_retries = max_retries
        self.heartbeat_interval = heartbeat_interval
        
        # WebSocket client
        self.ws_client: Optional[BinanceWebSocketClient] = None
        
        # Latest candle for each symbol
        self.latest_candles: Dict[str, Dict[str, Any]] = {}
        
        # Candle history buffer (last N candles per symbol)
        self.candle_buffers: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.max_buffer_size = 500  # Keep last 500 candles
        
        # Registered callbacks
        self.callbacks: List[Callable[[Dict[str, Any]], Any]] = []
        
        # Running state
        self.running = False
        self.tasks: List[asyncio.Task] = []
        
        logger.info(f"Initialized StreamRouter: {exchange}, {symbols}, {timeframe}")
    
    def register_callback(self, callback: Callable[[Dict[str, Any]], Any]):
        """
        Register a callback to receive candle updates.
        
        Args:
            callback: Async or sync function that takes candle dict
        """
        self.callbacks.append(callback)
        logger.info(f"Registered callback: {callback.__name__}")
    
    def get_latest_candle(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent candle for a symbol.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            
        Returns:
            Latest candle dict or None
        """
        return self.latest_candles.get(symbol.upper())
    
    def get_candle_buffer(self, symbol: str, n: int = None) -> List[Dict[str, Any]]:
        """
        Get candle history buffer for a symbol.
        
        Args:
            symbol: Trading pair
            n: Number of recent candles to return (None = all)
            
        Returns:
            List of candle dicts (oldest to newest)
        """
        buffer = self.candle_buffers.get(symbol.upper(), [])
        if n is not None:
            return buffer[-n:]
        return buffer
    
    def get_dataframe(self, symbol: str, n: int = None) -> Optional[pd.DataFrame]:
        """
        Get candle history as a pandas DataFrame.
        
        Args:
            symbol: Trading pair
            n: Number of recent candles (None = all)
            
        Returns:
            DataFrame with OHLCV data or None if no data
        """
        candles = self.get_candle_buffer(symbol, n)
        
        if not candles:
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        
        # Ensure proper column order
        columns = ["timestamp", "open", "high", "low", "close", "volume"]
        df = df[columns]
        
        return df
    
    async def _on_candle_update(self, candle: Dict[str, Any]):
        """
        Handle incoming candle data from WebSocket.
        
        Args:
            candle: Normalized candle dict
        """
        symbol = candle["symbol"]
        is_closed = candle.get("is_closed", False)
        
        # Update latest candle
        self.latest_candles[symbol] = candle
        
        # Add to buffer only when candle closes (finalized)
        if is_closed:
            buffer = self.candle_buffers[symbol]
            buffer.append(candle)
            
            # Trim buffer to max size
            if len(buffer) > self.max_buffer_size:
                self.candle_buffers[symbol] = buffer[-self.max_buffer_size:]
            
            logger.debug(f"[{symbol}] Candle closed: {candle['close']:.2f} @ {candle['timestamp']}")
        
        # Call registered callbacks
        for callback in self.callbacks:
            try:
                if inspect.iscoroutinefunction(callback):
                    await callback(candle)
                else:
                    callback(candle)
            except Exception as e:
                logger.error(f"Error in callback {callback.__name__}: {e}", exc_info=True)
    
    async def start(self):
        """Start the stream router and WebSocket client."""
        if self.running:
            logger.warning("StreamRouter already running")
            return
        
        if not self.symbols:
            logger.error("No symbols configured for streaming")
            return
        
        logger.info(f"Starting StreamRouter for {len(self.symbols)} symbols...")
        self.running = True
        
        # Determine base URL for WebSocket connection
        if self.ws_base_url:
            # Use explicitly configured base URL
            base_url = self.ws_base_url
            logger.info(f"Using configured WebSocket base URL: {base_url}")
        elif self.exchange == "binance":
            base_url = BinanceWebSocketClient.DEFAULT_BASE_URL
            logger.info(f"Using Binance WebSocket: {base_url}")
        elif self.exchange == "binance_us":
            base_url = BinanceWebSocketClient.BINANCE_US_BASE_URL
            logger.info(f"Using Binance US WebSocket: {base_url}")
        else:
            logger.error(f"Unsupported exchange: {self.exchange}")
            raise ValueError(f"Unsupported exchange for WebSocket: {self.exchange}")
        
        # Initialize WebSocket client based on exchange
        if self.exchange in ["binance", "binance_us"]:
            self.ws_client = BinanceWebSocketClient(
                symbols=self.symbols,
                timeframe=self.timeframe,
                on_candle=self._on_candle_update,
                base_url=base_url,
                reconnect_delay=self.reconnect_delay,
                max_retries=self.max_retries,
                heartbeat_interval=self.heartbeat_interval
            )
        else:
            logger.error(f"Unsupported exchange: {self.exchange}")
            return
        
        # Start WebSocket client
        ws_task = asyncio.create_task(self.ws_client.start())
        self.tasks.append(ws_task)
        
        logger.info(f"[OK] StreamRouter started")
    
    async def stop(self):
        """Stop the stream router and all connections."""
        logger.info("Stopping StreamRouter...")
        self.running = False
        
        # Stop WebSocket client
        if self.ws_client:
            await self.ws_client.stop()
        
        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self.tasks.clear()
        logger.info("[OK] StreamRouter stopped")
    
    async def wait_for_data(self, symbol: str, timeout: float = 30.0) -> bool:
        """
        Wait until data is available for a symbol.
        
        Args:
            symbol: Trading pair to wait for
            timeout: Maximum wait time in seconds
            
        Returns:
            True if data received, False if timeout
        """
        symbol = symbol.upper()
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            if symbol in self.latest_candles:
                return True
            await asyncio.sleep(0.1)
        
        logger.warning(f"Timeout waiting for {symbol} data")
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current router status.
        
        Returns:
            Status dict with connection info and data stats
        """
        return {
            "running": self.running,
            "exchange": self.exchange,
            "symbols": self.symbols,
            "timeframe": self.timeframe,
            "connected_symbols": list(self.latest_candles.keys()),
            "buffer_sizes": {
                symbol: len(buffer)
                for symbol, buffer in self.candle_buffers.items()
            },
            "ws_connected": self.ws_client and self.ws_client.ws and not self.ws_client.ws.closed if self.ws_client else False
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
