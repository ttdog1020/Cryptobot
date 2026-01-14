"""
MODULE 16: Live Stream Mock Tests

Tests for WebSocket streaming components using mock data.
Validates async behavior, data normalization, and callback execution.
"""

import asyncio
import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any, List

from data_feed.live import BinanceWebSocketClient, StreamRouter


class TestBinanceWebSocketClient(unittest.TestCase):
    """Test BinanceWebSocketClient with mocked WebSocket connections."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = BinanceWebSocketClient(
            symbols=["BTCUSDT"],
            timeframe="1m"
        )
        self.received_candles: List[Dict[str, Any]] = []
    
    def test_build_stream_url_single_symbol(self):
        """Test URL building for single symbol."""
        client = BinanceWebSocketClient(symbols=["BTCUSDT"], timeframe="1m")
        url = client._build_stream_url()
        
        # Single symbol uses direct stream
        self.assertIn("btcusdt@kline_1m", url.lower())
    
    def test_build_stream_url_multiple_symbols(self):
        """Test URL building for multiple symbols."""
        client = BinanceWebSocketClient(symbols=["BTCUSDT", "ETHUSDT"], timeframe="1m")
        url = client._build_stream_url()
        
        # Multiple symbols use combined stream
        self.assertIn("/stream?streams=", url)
        self.assertIn("btcusdt@kline_1m", url.lower())
        self.assertIn("ethusdt@kline_1m", url.lower())
    
    def test_normalize_candle(self):
        """Test Binance candle normalization."""
        # Binance kline format
        binance_msg = {
            "e": "kline",
            "s": "BTCUSDT",
            "k": {
                "t": 1638360000000,  # Open time
                "o": "50000.00",
                "h": "50100.00",
                "l": "49900.00",
                "c": "50050.00",
                "v": "100.5",
                "x": True,           # Is closed
                "n": 1000            # Number of trades
            }
        }
        
        normalized = self.client._normalize_candle(binance_msg)
        
        self.assertEqual(normalized["symbol"], "BTCUSDT")
        self.assertEqual(normalized["open"], 50000.00)
        self.assertEqual(normalized["high"], 50100.00)
        self.assertEqual(normalized["low"], 49900.00)
        self.assertEqual(normalized["close"], 50050.00)
        self.assertEqual(normalized["volume"], 100.5)
        self.assertEqual(normalized["is_closed"], True)
        self.assertEqual(normalized["trades"], 1000)
        self.assertEqual(normalized["timeframe"], "1m")
    
    def test_normalize_combined_stream(self):
        """Test normalization of combined stream message."""
        # Combined stream wraps data in 'data' field
        combined_msg = {
            "stream": "btcusdt@kline_1m",
            "data": {
                "e": "kline",
                "s": "BTCUSDT",
                "k": {
                    "t": 1638360000000,
                    "o": "50000.00",
                    "h": "50100.00",
                    "l": "49900.00",
                    "c": "50050.00",
                    "v": "100.5",
                    "x": True,
                    "n": 1000
                }
            }
        }
        
        normalized = self.client._normalize_candle(combined_msg)
        
        self.assertEqual(normalized["symbol"], "BTCUSDT")
        self.assertEqual(normalized["close"], 50050.00)
    
    async def _async_test_callback_execution(self):
        """Async test for callback execution."""
        callback_executed = asyncio.Event()
        received_candle = {}
        
        async def test_callback(candle):
            received_candle.update(candle)
            callback_executed.set()
        
        client = BinanceWebSocketClient(
            symbols=["BTCUSDT"],
            timeframe="1m",
            on_candle=test_callback
        )
        
        # Simulate receiving a message (must be JSON string)
        import json
        test_msg = json.dumps({
            "e": "kline",
            "s": "BTCUSDT",
            "k": {
                "t": 1638360000000,
                "o": "50000.00",
                "h": "50100.00",
                "l": "49900.00",
                "c": "50050.00",
                "v": "100.5",
                "x": True,
                "n": 1000
            }
        })
        
        await client._handle_message(test_msg)
        
        # Wait for callback
        await asyncio.wait_for(callback_executed.wait(), timeout=1.0)
        
        self.assertEqual(received_candle["symbol"], "BTCUSDT")
        self.assertEqual(received_candle["close"], 50050.00)
    
    def test_callback_execution(self):
        """Test that callbacks are executed on message."""
        asyncio.run(self._async_test_callback_execution())


class TestStreamRouter(unittest.TestCase):
    """Test StreamRouter with mocked WebSocket client."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.router = StreamRouter(
            exchange="binance",
            symbols=["BTCUSDT", "ETHUSDT"],
            timeframe="1m"
        )
        self.received_candles: List[Dict[str, Any]] = []
    
    async def _async_test_callback_registration(self):
        """Async test for callback registration."""
        callback_executed = asyncio.Event()
        received_candles = []
        
        async def test_callback(candle):
            received_candles.append(candle)
            callback_executed.set()
        
        self.router.register_callback(test_callback)
        
        # Simulate candle update
        test_candle = {
            "symbol": "BTCUSDT",
            "timestamp": 1638360000000,
            "open": 50000.0,
            "high": 50100.0,
            "low": 49900.0,
            "close": 50050.0,
            "volume": 100.5,
            "is_closed": True,
            "trades": 1000,
            "timeframe": "1m"
        }
        
        await self.router._on_candle_update(test_candle)
        
        # Wait for callback
        await asyncio.wait_for(callback_executed.wait(), timeout=1.0)
        
        self.assertEqual(len(received_candles), 1)
        self.assertEqual(received_candles[0]["symbol"], "BTCUSDT")
    
    def test_callback_registration(self):
        """Test callback registration and execution."""
        asyncio.run(self._async_test_callback_registration())
    
    async def _async_test_candle_buffering(self):
        """Async test for candle buffering."""
        # Add multiple candles
        for i in range(10):
            candle = {
                "symbol": "BTCUSDT",
                "timestamp": 1638360000000 + (i * 60000),
                "open": 50000.0 + i,
                "high": 50100.0 + i,
                "low": 49900.0 + i,
                "close": 50050.0 + i,
                "volume": 100.5,
                "is_closed": True,
                "trades": 1000,
                "timeframe": "1m"
            }
            await self.router._on_candle_update(candle)
        
        # Get latest candle
        latest = self.router.get_latest_candle("BTCUSDT")
        self.assertIsNotNone(latest)
        self.assertEqual(latest["close"], 50059.0)  # Last candle
        
        # Get buffer
        buffer = self.router.get_candle_buffer("BTCUSDT", n=5)
        self.assertEqual(len(buffer), 5)
        self.assertEqual(buffer[-1]["close"], 50059.0)  # Most recent
        
        # Get all
        all_candles = self.router.get_candle_buffer("BTCUSDT")
        self.assertEqual(len(all_candles), 10)
    
    def test_candle_buffering(self):
        """Test candle buffering functionality."""
        asyncio.run(self._async_test_candle_buffering())
    
    async def _async_test_dataframe_conversion(self):
        """Async test for DataFrame conversion."""
        # Add candles
        for i in range(5):
            candle = {
                "symbol": "ETHUSDT",
                "timestamp": 1638360000000 + (i * 60000),
                "open": 4000.0 + i,
                "high": 4010.0 + i,
                "low": 3990.0 + i,
                "close": 4005.0 + i,
                "volume": 50.0,
                "is_closed": True,
                "trades": 500,
                "timeframe": "1m"
            }
            await self.router._on_candle_update(candle)
        
        # Get DataFrame
        df = self.router.get_dataframe("ETHUSDT", n=3)
        
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 3)
        self.assertIn("open", df.columns)
        self.assertIn("close", df.columns)
        self.assertIn("volume", df.columns)
        
        # Check values
        self.assertEqual(df.iloc[-1]["close"], 4009.0)  # Last candle
        self.assertEqual(df.iloc[0]["close"], 4007.0)   # First of 3
    
    def test_dataframe_conversion(self):
        """Test DataFrame conversion from candle buffer."""
        asyncio.run(self._async_test_dataframe_conversion())
    
    async def _async_test_multiple_symbols(self):
        """Async test for multiple symbol handling."""
        # Add candles for different symbols
        btc_candle = {
            "symbol": "BTCUSDT",
            "timestamp": 1638360000000,
            "open": 50000.0,
            "high": 50100.0,
            "low": 49900.0,
            "close": 50050.0,
            "volume": 100.5,
            "is_closed": True,
            "trades": 1000,
            "timeframe": "1m"
        }
        
        eth_candle = {
            "symbol": "ETHUSDT",
            "timestamp": 1638360000000,
            "open": 4000.0,
            "high": 4010.0,
            "low": 3990.0,
            "close": 4005.0,
            "volume": 50.0,
            "is_closed": True,
            "trades": 500,
            "timeframe": "1m"
        }
        
        await self.router._on_candle_update(btc_candle)
        await self.router._on_candle_update(eth_candle)
        
        # Check both symbols have data
        btc_latest = self.router.get_latest_candle("BTCUSDT")
        eth_latest = self.router.get_latest_candle("ETHUSDT")
        
        self.assertIsNotNone(btc_latest)
        self.assertIsNotNone(eth_latest)
        self.assertEqual(btc_latest["close"], 50050.0)
        self.assertEqual(eth_latest["close"], 4005.0)
    
    def test_multiple_symbols(self):
        """Test handling multiple symbols independently."""
        asyncio.run(self._async_test_multiple_symbols())
    
    def test_get_status(self):
        """Test status reporting."""
        status = self.router.get_status()
        
        self.assertIn("exchange", status)
        self.assertIn("symbols", status)
        self.assertIn("timeframe", status)
        self.assertIn("running", status)
        self.assertIn("buffer_sizes", status)
        
        self.assertEqual(status["exchange"], "binance")
        self.assertEqual(status["timeframe"], "1m")
        self.assertFalse(status["running"])


class TestAsyncBehavior(unittest.TestCase):
    """Test async behavior and edge cases."""
    
    async def _async_test_sync_callback(self):
        """Test that sync callbacks work in async context."""
        callback_executed = asyncio.Event()
        received_candles = []
        
        def sync_callback(candle):
            """Synchronous callback."""
            received_candles.append(candle)
            callback_executed.set()
        
        router = StreamRouter(
            exchange="binance",
            symbols=["BTCUSDT"],
            timeframe="1m"
        )
        
        router.register_callback(sync_callback)
        
        test_candle = {
            "symbol": "BTCUSDT",
            "timestamp": 1638360000000,
            "open": 50000.0,
            "high": 50100.0,
            "low": 49900.0,
            "close": 50050.0,
            "volume": 100.5,
            "is_closed": True,
            "trades": 1000,
            "timeframe": "1m"
        }
        
        await router._on_candle_update(test_candle)
        
        # Wait for callback (should be immediate for sync)
        await asyncio.wait_for(callback_executed.wait(), timeout=1.0)
        
        self.assertEqual(len(received_candles), 1)
    
    def test_sync_callback_in_async_context(self):
        """Test that synchronous callbacks work correctly."""
        asyncio.run(self._async_test_sync_callback())
    
    async def _async_test_wait_for_data_timeout(self):
        """Test wait_for_data timeout behavior."""
        router = StreamRouter(
            exchange="binance",
            symbols=["BTCUSDT"],
            timeframe="1m"
        )
        
        # Should timeout since no data
        result = await router.wait_for_data("BTCUSDT", timeout=0.1)
        self.assertFalse(result)
    
    def test_wait_for_data_timeout(self):
        """Test wait_for_data timeout."""
        asyncio.run(self._async_test_wait_for_data_timeout())
    
    async def _async_test_wait_for_data_success(self):
        """Test wait_for_data success case."""
        router = StreamRouter(
            exchange="binance",
            symbols=["BTCUSDT"],
            timeframe="1m"
        )
        
        # Add data in background
        async def add_data():
            await asyncio.sleep(0.1)
            test_candle = {
                "symbol": "BTCUSDT",
                "timestamp": 1638360000000,
                "open": 50000.0,
                "high": 50100.0,
                "low": 49900.0,
                "close": 50050.0,
                "volume": 100.5,
                "is_closed": True,
                "trades": 1000,
                "timeframe": "1m"
            }
            await router._on_candle_update(test_candle)
        
        # Start adding data
        asyncio.create_task(add_data())
        
        # Wait for data
        result = await router.wait_for_data("BTCUSDT", timeout=1.0)
        self.assertTrue(result)
    
    def test_wait_for_data_success(self):
        """Test wait_for_data success."""
        asyncio.run(self._async_test_wait_for_data_success())


if __name__ == "__main__":
    unittest.main()
