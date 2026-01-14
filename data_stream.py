import asyncio
import json
import threading
import time
from collections import deque
from typing import Deque, Dict, Tuple, Optional

import pandas as pd
import websockets

# In-memory buffers keyed by (pair, timeframe)
_buffers: Dict[Tuple[str, str], Deque[dict]] = {}
_lock = threading.Lock()
_ws_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


def _timeframe_to_interval(timeframe: str) -> int:
    if timeframe == "1m":
        return 1
    if timeframe == "5m":
        return 5
    if timeframe == "15m":
        return 15
    return 5


async def _ws_ohlc_loop(pair: str, timeframe: str, max_candles: int):
    url = "wss://ws.kraken.com/"
    interval = _timeframe_to_interval(timeframe)
    key = (pair, timeframe)

    while not _stop_event.is_set():
        try:
            async with websockets.connect(url) as ws:
                # subscribe
                msg = {
                    "event": "subscribe",
                    "pair": [pair],
                    "subscription": {"name": "ohlc", "interval": interval},
                }
                await ws.send(json.dumps(msg))

                # ensure buffer exists
                with _lock:
                    if key not in _buffers:
                        _buffers[key] = deque(maxlen=max_candles)
                    buf = _buffers[key]

                async for raw in ws:
                    if _stop_event.is_set():
                        break

                    try:
                        data = json.loads(raw)
                    except Exception:
                        continue

                    # skip non-list messages
                    if not isinstance(data, list) or len(data) < 2:
                        continue

                    payload = data[1]
                    if not isinstance(payload, list) or len(payload) < 6:
                        continue

                    try:
                        o_time = float(payload[0])
                        open_ = float(payload[2])
                        high_ = float(payload[3])
                        low_ = float(payload[4])
                        close_ = float(payload[5])
                    except (ValueError, TypeError):
                        continue

                    candle = {
                        "timestamp": pd.to_datetime(o_time, unit="s"),
                        "open": open_,
                        "high": high_,
                        "low": low_,
                        "close": close_,
                    }

                    with _lock:
                        buf.append(candle)

        except Exception as exc:
            print(f"[WS] WebSocket error: {exc}. Reconnecting in 2s...")
            await asyncio.sleep(2)


def _start_loop_in_thread(pair: str, timeframe: str, max_candles: int):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def runner():
        while not _stop_event.is_set():
            await _ws_ohlc_loop(pair, timeframe, max_candles)
            if not _stop_event.is_set():
                await asyncio.sleep(1)

    try:
        loop.run_until_complete(runner())
    finally:
        loop.close()


def start_ohlc_stream(pair: str, timeframe: str, max_candles: int = 500):
    """Start a background thread to populate OHLC buffers from Kraken WebSocket.

    If already started, this is a no-op.
    """
    global _ws_thread
    if _ws_thread and _ws_thread.is_alive():
        return

    _stop_event.clear()
    _ws_thread = threading.Thread(
        target=_start_loop_in_thread, args=(pair, timeframe, max_candles), daemon=True
    )
    _ws_thread.start()


def stop_stream():
    _stop_event.set()
    global _ws_thread
    if _ws_thread:
        _ws_thread.join(timeout=2)
    _ws_thread = None
    with _lock:
        _buffers.clear()


def get_latest_candles(pair: str, timeframe: str, limit: int) -> pd.DataFrame:
    key = (pair, timeframe)
    with _lock:
        buf = _buffers.get(key)
        if not buf or len(buf) == 0:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close"])

        items = list(buf)[-limit:]

    df = pd.DataFrame(items)
    # ensure columns and ordering
    df = df[["timestamp", "open", "high", "low", "close"]]
    return df
