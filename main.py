import ccxt
import pandas as pd
import time

# ==============================
#  Fake API Keys (for testing only)
# ==============================
API_KEY = "601fce1027f44fd2b49e056adf76359d"
API_SECRET = "mx0vglPbQhO0NZ5DYx"

exchange = ccxt.mexc({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "enableRateLimit": True
})

# Pairs we monitor
pairs = ["BTC/USDT", "ETH/USDT", "ENA/USDT", "SOL/USDT", "XRP/USDT"]

# ==============================
#  Strategy Functions
# ==============================

def fetch_ohlcv(symbol, timeframe="5m", limit=100):
    """Fetch OHLCV data from MEXC and return DataFrame"""
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["timestamp","open","high","low","close","volume"])  # type: ignore
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

def detect_liquidity_sweep(df):
    """Check if last candle sweeps previous high/low"""
    if len(df) < 3:
        return None
    last = df.iloc[-1]
    prev = df.iloc[-2]

    if last["high"] > prev["high"] and last["close"] < prev["close"]:
        return "sweep_high"
    if last["low"] < prev["low"] and last["close"] > prev["close"]:
        return "sweep_low"
    return None

def detect_bos(df):
    """Check Break of Structure"""
    if len(df) < 10:
        return None
    recent_high = df["high"].iloc[-10:-1].max()
    recent_low = df["low"].iloc[-10:-1].min()
    close = df["close"].iloc[-1]

    if close > recent_high:
        return "bos_up"
    if close < recent_low:
        return "bos_down"
    return None

def detect_order_block(df, sweep, bos):
    """Detect valid Order Block (very simplified)"""
    if sweep == "sweep_high" and bos == "bos_down":
        return "bearish_order_block"
    if sweep == "sweep_low" and bos == "bos_up":
        return "bullish_order_block"
    return None

def generate_signal(symbol):
    """Run strategy and generate plain text signal"""
    df = fetch_ohlcv(symbol)

    sweep = detect_liquidity_sweep(df)
    bos = detect_bos(df)
    ob = detect_order_block(df, sweep, bos)

    if sweep and bos and ob:
        direction = "LONG" if ob == "bullish_order_block" else "SHORT"
        entry = df["close"].iloc[-1]
        tp1 = entry * (1.005 if direction == "LONG" else 0.995)
        tp2 = entry * (1.010 if direction == "LONG" else 0.990)
        tp3 = entry * (1.020 if direction == "LONG" else 0.980)
        sl = entry * (0.995 if direction == "LONG" else 1.005)

        return f"""
Signal for {symbol}
Direction: {direction}
Entry: {entry:.2f}
TP1: {tp1:.2f}
TP2: {tp2:.2f}
TP3: {tp3:.2f}
SL: {sl:.2f}
Confluences: {sweep}, {bos}, {ob}
"""
    return None

# ==============================
#  Main Loop
# ==============================
if __name__ == "__main__":
    print("🚀 Bot started with fake keys:", API_KEY, API_SECRET)
    while True:
        for pair in pairs:
            try:
                signal = generate_signal(pair)
                if signal:
                    print(signal)
            except Exception as e:
                print(f"Error on {pair}: {e}")
        time.sleep(60)  # run every 1 min
