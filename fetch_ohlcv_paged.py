import ccxt
import pandas as pd
import time


def fetch_ohlcv_paged(exchange, symbol: str, timeframe: str, limit: int, since=None, max_per_call: int = 300):
    """
    Fetch up to `limit` OHLCV candles using multiple ccxt.fetch_ohlcv calls.
    Fetches backwards in time to get the most recent candles.
    
    Args:
        exchange: ccxt exchange instance
        symbol: trading pair symbol
        timeframe: candle timeframe
        limit: total number of candles to fetch
        since: optional timestamp to start from (if None, starts from most recent)
        max_per_call: maximum candles per API call (default 300 for OKX compatibility)
    
    Returns:
        List of OHLCV candles [[timestamp, o, h, l, c, v], ...]
    """
    all_candles = []
    
    # Parse timeframe to milliseconds
    tf_map = {'1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800, 
              '1h': 3600, '4h': 14400, '1d': 86400}
    tf_seconds = tf_map.get(timeframe, 900)  # default to 15m
    tf_ms = tf_seconds * 1000
    
    # If since not provided, work backwards from now
    if since is None:
        since_ts = int(time.time() * 1000) - (limit * tf_ms)
    else:
        since_ts = since
    
    print(f"[FETCH] Starting pagination to fetch {limit} candles...")
    fetched_count = 0
    
    while fetched_count < limit:
        batch_limit = min(max_per_call, limit - fetched_count)
        
        try:
            candles = exchange.fetch_ohlcv(
                symbol, 
                timeframe=timeframe, 
                since=since_ts, 
                limit=batch_limit
            )
        except Exception as e:
            print(f"[BT][ERROR] fetch_ohlcv_paged failed: {type(e).__name__} {e}")
            break

        if not candles:
            print(f"[FETCH] No more candles available. Got {fetched_count} total.")
            break
        
        print(f"[FETCH] Batch {len(all_candles) // max_per_call + 1}: fetched {len(candles)} candles")
        all_candles.extend(candles)
        fetched_count = len(all_candles)

        # Advance `since` to just after the last candle to avoid duplicates
        last_ts = candles[-1][0]
        since_ts = last_ts + 1

        # If the exchange gave fewer than requested, we probably hit the end of history
        if len(candles) < batch_limit:
            print(f"[FETCH] Reached end of available history. Got {fetched_count} candles.")
            break
        
        # Small delay to respect rate limits
        time.sleep(0.1)

    print(f"[FETCH] Complete. Total candles fetched: {len(all_candles)}")
    
    # Keep only the most recent `limit` candles
    if len(all_candles) > limit:
        all_candles = all_candles[-limit:]

    return all_candles

