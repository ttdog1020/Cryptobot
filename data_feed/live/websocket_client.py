"""
MODULE 16: Binance WebSocket Client

Async WebSocket client for live market data streaming.
Supports kline (candlestick) and trade streams with auto-reconnection.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timezone
import inspect
import aiohttp

logger = logging.getLogger(__name__)


class BinanceWebSocketClient:
    """
    Async WebSocket client for Binance market data.
    
    Supports:
    - Kline (candlestick) streams for various timeframes
    - Trade tick streams
    - Auto-reconnection with exponential backoff
    - Heartbeat monitoring
    - Graceful shutdown
    - Module 26: Configurable base URL for Binance US support
    """
    
    # Default base URLs for different exchanges
    # Module 26 Patch: Use /stream endpoint directly (not /ws)
    DEFAULT_BASE_URL = "wss://stream.binance.com:9443/stream"
    BINANCE_US_BASE_URL = "wss://stream.binance.us:9443/stream"
    
    def __init__(
        self,
        symbols: List[str],
        timeframe: str = "1m",
        on_candle: Optional[Callable[[Dict[str, Any]], None]] = None,
        base_url: Optional[str] = None,
        reconnect_delay: int = 3,
        max_retries: int = 5,
        heartbeat_interval: int = 30
    ):
        """
        Initialize Binance WebSocket client.
        
        Args:
            symbols: List of trading pairs (e.g., ["BTCUSDT", "ETHUSDT"])
            timeframe: Kline interval (1m, 3m, 5m, 15m, 1h, etc.)
            on_candle: Callback function for new candle data
            base_url: WebSocket base URL (None = use DEFAULT_BASE_URL)
            reconnect_delay: Initial reconnection delay in seconds
            max_retries: Maximum reconnection attempts (0 = infinite)
            heartbeat_interval: Heartbeat check interval in seconds
        """
        self.symbols = [s.lower() for s in symbols]  # Binance uses lowercase
        self.timeframe = timeframe
        self.on_candle = on_candle
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.reconnect_delay = reconnect_delay
        self.max_retries = max_retries
        self.heartbeat_interval = heartbeat_interval
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.running = False
        self.retry_count = 0
        
        logger.info(f"Initialized Binance WS client for {symbols} @ {timeframe}")
        logger.info(f"WebSocket base URL: {self.base_url}")
    
    def _build_stream_url(self) -> str:
        """
        Build combined stream URL for multiple symbols.
        
        Assumes self.base_url already points to the '/stream' endpoint,
        e.g. 'wss://stream.binance.us:9443/stream'.
        
        Returns:
            WebSocket URL for combined streams
        """
        # Create stream names: btcusdt@kline_1m/ethusdt@kline_1m
        streams = [f"{symbol}@kline_{self.timeframe}" for symbol in self.symbols]
        combined = "/".join(streams)
        
        # Append query parameters directly to base_url
        # For single symbol, still use combined stream format for consistency
        url = f"{self.base_url}?streams={combined}"
        
        return url
    
    def _normalize_candle(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normalize Binance kline data to standard format.
        
        Args:
            raw_data: Raw WebSocket message from Binance
            
        Returns:
            Normalized candle dict or None if invalid
        """
        try:
            # Handle combined stream format vs single stream format
            if "stream" in raw_data:
                # Combined stream: {"stream":"btcusdt@kline_1m", "data":{...}}
                stream_name = raw_data["stream"]
                symbol = stream_name.split("@")[0].upper()
                kline_data = raw_data["data"]
            else:
                # Single stream: {"e":"kline", "s":"BTCUSDT", "k":{...}}
                symbol = raw_data.get("s", "").upper()
                kline_data = raw_data
            
            # Extract kline object
            if "k" not in kline_data:
                logger.warning(f"No kline data in message: {raw_data}")
                return None
            
            k = kline_data["k"]
            
            # Normalize to standard OHLCV format
            normalized = {
                "symbol": symbol,
                "timestamp": datetime.fromtimestamp(k["t"] / 1000, tz=timezone.utc),
                "open": float(k["o"]),
                "high": float(k["h"]),
                "low": float(k["l"]),
                "close": float(k["c"]),
                "volume": float(k["v"]),
                "is_closed": k["x"],  # True when candle is finalized
                "trades": int(k["n"]),
                "timeframe": self.timeframe
            }
            
            return normalized
        
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error normalizing candle data: {e}")
            logger.debug(f"Raw data: {raw_data}")
            return None
    
    async def _handle_message(self, msg_data: str):
        """
        Process incoming WebSocket message.
        
        Args:
            msg_data: Raw WebSocket message string
        """
        try:
            data = json.loads(msg_data)
            
            # Normalize candle data
            candle = self._normalize_candle(data)
            
            if candle and self.on_candle:
                # Call user's callback
                if inspect.iscoroutinefunction(self.on_candle):
                    await self.on_candle(candle)
                else:
                    self.on_candle(candle)
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
    
    async def _heartbeat_task(self):
        """Monitor connection health and send pings."""
        while self.running and self.ws:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                if self.ws and not self.ws.closed:
                    await self.ws.ping()
                    logger.debug("Sent WebSocket ping")
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Heartbeat error: {e}")
    
    async def connect(self):
        """
        Establish WebSocket connection with auto-reconnect logic.
        """
        url = self._build_stream_url()
        
        while self.running:
            try:
                logger.info(f"Connecting to Binance WebSocket: {url}")
                
                if not self.session:
                    self.session = aiohttp.ClientSession()
                
                self.ws = await self.session.ws_connect(
                    url,
                    heartbeat=self.heartbeat_interval,
                    autoping=True
                )
                
                logger.info(f"[OK] Connected to Binance WebSocket")
                self.retry_count = 0  # Reset retry counter on successful connection
                
                # Start heartbeat monitoring
                heartbeat_task = asyncio.create_task(self._heartbeat_task())
                
                # Message loop
                async for msg in self.ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self._handle_message(msg.data)
                    
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        logger.warning("WebSocket closed by server")
                        break
                    
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"WebSocket error: {self.ws.exception()}")
                        break
                
                # Cancel heartbeat task
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            except aiohttp.ClientError as e:
                logger.error(f"Connection error: {e}")
            
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
            
            finally:
                # Clean up WebSocket
                if self.ws and not self.ws.closed:
                    await self.ws.close()
                    self.ws = None
            
            # Reconnection logic
            if not self.running:
                break
            
            self.retry_count += 1
            
            if self.max_retries > 0 and self.retry_count > self.max_retries:
                logger.error(f"Max retries ({self.max_retries}) reached. Giving up.")
                break
            
            # Exponential backoff
            delay = min(self.reconnect_delay * (2 ** (self.retry_count - 1)), 60)
            logger.info(f"Reconnecting in {delay}s (attempt {self.retry_count})...")
            await asyncio.sleep(delay)
    
    async def start(self):
        """Start the WebSocket client."""
        if self.running:
            logger.warning("WebSocket client already running")
            return
        
        self.running = True
        await self.connect()
    
    async def stop(self):
        """Stop the WebSocket client gracefully."""
        logger.info("Stopping WebSocket client...")
        self.running = False
        
        if self.ws and not self.ws.closed:
            await self.ws.close()
        
        if self.session and not self.session.closed:
            await self.session.close()
        
        logger.info("[OK] WebSocket client stopped")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
