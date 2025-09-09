# main.py

import ccxt
import pandas as pd
import time
from datetime import datetime

# =============================
# Fake API Keys (replace later with real ones if needed)
# =============================
API_KEY = "FAKE_API_KEY_123456"
API_SECRET = "FAKE_API_SECRET_ABCDEF"

# =============================
# Initialize MEXC exchange
# =============================
exchange = ccxt.mexc({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "enableRateLimit": True
})

# =============================
# Strategy: Liquidity Sweep → BOS → Order Block
# =============================
def fetch_ohlcv(symbol="BTC/USDT", timeframe="15m", limit=200):
    """Fetch OHLCV data from MEXC"""
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])  # type: ignore
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def check_strategy(df):
    """Simple example of your Liquidity Sweep → BOS → OB strategy"""

    last = df.iloc[-1]
    prev = df.iloc[-2]

    signals = []

    # ✅ Liquidity Sweep (price sweeps previous high/low but closes opposite)
    if last['high'] > prev['high'] and last['close'] < prev['high']:
        signals.append("Liquidity Sweep Down → Possible Short")
    elif last['low'] < prev['low'] and last['close'] > prev['low']:
        signals.append("Liquidity Sweep Up → Possible Long")

    # ✅ Break of Structure (close above/below recent swing)
    if last['close'] > df['high'].iloc[-5:-1].max():
        signals.append("Break of Structure Up → Bullish Bias")
    elif last['close'] < df['low'].iloc[-5:-1].min():
        signals.append("Break of Structure Down → Bearish Bias")

    # ✅ Order Block (basic: last opposite candle before move)
    # (This is simplified; in real version we’d mark OB zones)
    if "Long" in " ".join(signals):
        signals.append("Check Bullish Order Block for Entry")
    elif "Short" in " ".join(signals):
        signals.append("Check Bearish Order Block for Entry")

    return signals

def generate_alert(symbol, signals):
    """Format alert message like your Telegram signals"""
    if not signals:
        return None

    alert = f"""
📊 Signal for {symbol}

✅ Entry: Market Price
🎯 TP1: +0.5%
🎯 TP2: +1%
🎯 TP3: +2%
❌ SL: -0.5%

🧾 Confluences:
- {signals[0]}
- {signals[1] if len(signals) > 1 else ''}
    """.strip()
    return alert

def run_bot():
    pairs = ["BTC/USDT", "ETH/USDT", "ENA/USDT"]  # same as Replit setup
    timeframe = "15m"

    while True:
        for symbol in pairs:
            try:
                df = fetch_ohlcv(symbol, timeframe)
                signals = check_strategy(df)
                alert = generate_alert(symbol, signals)
                if alert:
                    print(f"[{datetime.now()}] {alert}\n")
            except Exception as e:
                print(f"Error fetching {symbol}: {e}")

        time.sleep(60)  # wait before next check


if __name__ == "__main__":
    run_bot()

