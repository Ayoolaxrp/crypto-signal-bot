import os
import ccxt
import pandas as pd
import time
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

# MEXC API (not strictly needed if you only fetch candles)
api_key = os.getenv("MEXC_API_KEY")
secret_key = os.getenv("MEXC_SECRET_KEY")

exchange = ccxt.mexc({
    "apiKey": api_key,
    "secret": secret_key
})

# Email settings
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

def send_email(subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = EMAIL_RECEIVER

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.ehlo()                # handshake
            server.starttls()            # secure connection
            server.ehlo()                # handshake again
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, EMAIL_RECEIVER, msg.as_string())
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Error sending email: {e}")

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
    symbols = ["ETH/USDT", "BTC/USDT", "ENA/USDT"]
    while True:
        for symbol in symbols:
            df = fetch_data(symbol)
            signal = analyze_strategy(df)
            if signal:
                body = f"""
📊 {symbol} Signal:
Direction: {signal['signal']}
Entry: {signal['entry']}
TP1: {signal['tp1']}
TP2: {signal['tp2']}
TP3: {signal['tp3']}
SL: {signal['sl']}
"""
                print(body)
                send_email(f"Trading Signal: {symbol}", body)
        print("\n--- Waiting 5 minutes before next check ---\n")
        time.sleep(300)

if __name__ == "__main__":
    main()
