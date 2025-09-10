import ccxt
import pandas as pd
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# ================== CONFIG ==================
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "your_email@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "your_gmail_app_password")
EMAIL_TO = os.getenv("EMAIL_TO", "receiver_email@gmail.com")

SYMBOLS = ["BTC/USDT", "ETH/USDT", "ENA/USDT"]

# Timeframes for top-down analysis
BIAS_TFS = ["1h", "4h"]   # bias
CONFIRM_TF = "15m"        # confirmation
ENTRY_TFS = ["5m", "1m"]  # entries

LOOP_INTERVAL = 120   # 2 minutes
exchange = ccxt.mexc({"enableRateLimit": True})

# ================== HELPERS ==================
def get_ohlcv(symbol, timeframe, limit=200):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"]  # type: ignore
        )
        return df
    except Exception as e:
        print(f"❌ Error fetching {symbol} ({timeframe}): {e}")
        return None

def get_bias(symbol):
    """Check if bias agrees on 1h and 4h"""
    results = []
    for tf in BIAS_TFS:
        df = get_ohlcv(symbol, tf, limit=100)
        if df is None:
            return None
        close = df["close"].iloc[-1]
        prev_close = df["close"].iloc[-2]
        results.append("BULLISH" if close > prev_close else "BEARISH")
    return results[0] if results.count(results[0]) == len(results) else None

def analyze_pair(symbol):
    print(f"\n🔎 Checking {symbol}...")

    # 1. Get bias from 1h + 4h
    bias = get_bias(symbol)
    if bias is None:
        print("⚠️ Bias not aligned.")
        return None

    # 2. Confirmation on 15m
    confirm_df = get_ohlcv(symbol, CONFIRM_TF, limit=50)
    if confirm_df is None:
        return None
    confirm_close = confirm_df["close"].iloc[-1]
    confirm_prev = confirm_df["close"].iloc[-2]
    confirm_trend = "BULLISH" if confirm_close > confirm_prev else "BEARISH"
    if confirm_trend != bias:
        print("⚠️ 15m confirmation disagrees with bias.")
        return None

    # 3. Look for entry on 5m and 1m
    for tf in ENTRY_TFS:
        ltf = get_ohlcv(symbol, tf, limit=50)
        if ltf is None:
            continue
        last_high = ltf["high"].iloc[-2]
        last_low = ltf["low"].iloc[-2]
        current_close = ltf["close"].iloc[-1]

        signal = None
        if current_close > last_high and bias == "BULLISH":
            signal = f"✅ LONG {symbol} ({tf})"
        elif current_close < last_low and bias == "BEARISH":
            signal = f"❌ SHORT {symbol} ({tf})"

        if signal:
            send_email_alert(symbol, signal, bias, current_close, last_high, last_low, tf)
            return signal  # only send one signal per loop

    print("No valid entry found.")
    return None

# ================== ALERTS ==================
def send_email_alert(symbol, signal, bias, price, high, low, tf):
    try:
        subject = f"📊 Trade Signal for {symbol}"
        body = f"""
        Signal: {signal}
        Bias: {bias}
        Timeframe: {tf}
        Current Price: {price}
        Last High: {high}
        Last Low: {low}

        TP1: {round(price * (1.01 if "LONG" in signal else 0.99), 4)}
        TP2: {round(price * (1.02 if "LONG" in signal else 0.98), 4)}
        TP3: {round(price * (1.03 if "LONG" in signal else 0.97), 4)}
        SL:  {round(price * (0.99 if "LONG" in signal else 1.01), 4)}
        """

        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = EMAIL_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, EMAIL_TO, msg.as_string())
        server.quit()

        print(f"📧 Email sent for {symbol}: {signal}")

    except Exception as e:
        print(f"❌ Error sending email: {e}")

# ================== MAIN LOOP ==================
def main():
    while True:
        for symbol in SYMBOLS:
            analyze_pair(symbol)
        print(f"⏳ Sleeping {LOOP_INTERVAL}s before next cycle...\n")
        time.sleep(LOOP_INTERVAL)

if __name__ == "__main__":
    main()
