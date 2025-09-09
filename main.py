import os
import time
import ccxt
import pandas as pd
from flask import Flask

# ============ API KEYS (Fake for Testing) ============
API_KEY = "mx0vglPbQhO0NZ5DYx"       # fake api key
API_SECRET = "601fce1027f44fd2b49e056adf76359d"  # fake secret

# ============ MEXC Client ============
exchange = ccxt.mexc({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "enableRateLimit": True
})

# ============ Flask Server ============
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running smoothly ✅"

# ============ Pairs to Scan ============
pairs = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT"
]  # ✅ replace/expand with the exact pairs you had in Replit

# ============ Signal Generator ============
def generate_signal(symbol, direction, price):
    if direction == "long":
        entry_low = round(price * 0.995, 4)
        entry_high = round(price * 1.005, 4)
        tp1 = round(price * 1.01, 4)
        tp2 = round(price * 1.02, 4)
        tp3 = round(price * 1.03, 4)
        sl = round(price * 0.985, 4)

        print(f"""
💥 Futures (Free Signal)

✅ Long

#{symbol.replace("/", "")}

Entry zone : {entry_low} - {entry_high}
Take Profits :
{tp1}
{tp2}
{tp3}
Stop loss : {sl}
        """)

    elif direction == "short":
        entry_low = round(price * 0.995, 4)
        entry_high = round(price * 1.005, 4)
        tp1 = round(price * 0.99, 4)
        tp2 = round(price * 0.98, 4)
        tp3 = round(price * 0.97, 4)
        sl = round(price * 1.015, 4)

        print(f"""
💥 Futures (Free Signal)

❌ Short

#{symbol.replace("/", "")}

Entry zone : {entry_low} - {entry_high}
Take Profits :
{tp1}
{tp2}
{tp3}
Stop loss : {sl}
        """)

# ============ ICT Strategy (Alerts + Signals) ============
def analyze_market(symbol="BTC/USDT", timeframe="1h", limit=100):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )  # type: ignore

        last_close = df["close"].iloc[-1]
        prev_high = df["high"].iloc[-2]
        prev_low = df["low"].iloc[-2]
        prev_close = df["close"].iloc[-2]

        # Conditions
        if last_close > prev_high and last_close > prev_close:
            generate_signal(symbol, "long", last_close)
        elif last_close < prev_low and last_close < prev_close:
            generate_signal(symbol, "short", last_close)
        else:
            print(f"{symbol} | No clear setup | Last Close: {last_close}")

    except Exception as e:
        print(f"Error analyzing {symbol}: {str(e)}")

# ============ Main Loop ============
def run_bot():
    while True:
        for pair in pairs:
            analyze_market(pair, "1h")
            time.sleep(2)  # small delay to avoid rate limits
        time.sleep(60)  # wait 1 min before next full cycle

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=run_bot)
    t.start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
