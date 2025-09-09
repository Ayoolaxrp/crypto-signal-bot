import os
import ccxt
import pandas as pd
from dotenv import load_dotenv

# Load environment variables (Railway injects them automatically, but dotenv helps for local testing too)
load_dotenv()

# Get API keys from env
api_key = os.getenv("MEXC_API_KEY")
secret_key = os.getenv("MEXC_SECRET_KEY")

# Initialize MEXC client
exchange = ccxt.mexc({
    "apiKey": api_key,
    "secret": secret_key
})

def fetch_data(symbol="ETH/USDT", timeframe="1h", limit=100):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["timestamp","open","high","low","close","volume"])  # type: ignore
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

def analyze_strategy(df):
    if df is None or df.empty:
        return None

    last_close = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-2]

    # Simple example strategy (replace with your real one)
    if last_close > prev_close:
        return {
            "signal": "BUY",
            "entry": last_close,
            "tp1": round(last_close * 1.01, 4),
            "tp2": round(last_close * 1.02, 4),
            "tp3": round(last_close * 1.03, 4),
            "sl": round(last_close * 0.99, 4)
        }
    else:
        return {
            "signal": "SELL",
            "entry": last_close,
            "tp1": round(last_close * 0.99, 4),
            "tp2": round(last_close * 0.98, 4),
            "tp3": round(last_close * 0.97, 4),
            "sl": round(last_close * 1.01, 4)
        }

def main():
    symbols = ["ETH/USDT", "BTC/USDT", "ENA/USDT"]  # use your chosen pairs
    for symbol in symbols:
        df = fetch_data(symbol)
        signal = analyze_strategy(df)
        if signal:
            print(f"\n📊 {symbol} Signal:")
            print(signal)

if __name__ == "__main__":
    main()
