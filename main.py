import ccxt
import time
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os
from datetime import datetime

# Load .env variables
load_dotenv()
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

# Setup MEXC client
exchange = ccxt.mexc({
    "enableRateLimit": True
})

# === Logging ===
def log_message(message):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open("signals.log", "a") as f:
        f.write(f"[{timestamp}] {message}\n")

# === Strategy Functions ===
def detect_liquidity_sweep(candles):
    last_close = candles[-1][4]
    prev_high = max([c[2] for c in candles[-5:-1]])
    prev_low = min([c[3] for c in candles[-5:-1]])
    if last_close > prev_high:
        return "bullish"
    elif last_close < prev_low:
        return "bearish"
    return None

def detect_bos(candles, direction):
    last_close = candles[-1][4]
    if direction == "bullish":
        return last_close > candles[-2][2]
    elif direction == "bearish":
        return last_close < candles[-2][3]
    return False

def detect_order_block(candles, direction):
    last_open, last_close = candles[-1][1], candles[-1][4]
    if direction == "bullish" and last_close > last_open:
        return True
    if direction == "bearish" and last_close < last_open:
        return True
    return False

def analyze_strategy(candles, direction):
    sweep = detect_liquidity_sweep(candles)
    if sweep == direction:
        if detect_bos(candles, direction):
            if detect_order_block(candles, direction):
                return True
    return False

# === Email Alerts ===
def send_email(subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = EMAIL_ADDRESS

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, EMAIL_ADDRESS, msg.as_string())

        print(f"📧 Email sent: {subject}")
        log_message(f"Email sent: {subject} - {body}")
    except Exception as e:
        error_msg = f"❌ Error sending email: {e}"
        print(error_msg)
        log_message(error_msg)

# === Main Bot Loop ===
symbols = ["BTC/USDT", "ETH/USDT", "ENA/USDT"]
timeframes = ["4h", "1h", "15m", "5m", "1m"]

def fetch_candles(symbol, timeframe, limit=100):
    try:
        return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    except Exception as e:
        msg = f"❌ Error fetching {symbol} {timeframe}: {e}"
        print(msg)
        log_message(msg)
        return None

def run_bot():
    while True:
        for symbol in symbols:
            log_message(f"🔎 Checking {symbol}...")
            candles = {}

            # Fetch all timeframes
            for tf in timeframes:
                data = fetch_candles(symbol, tf)
                if data:
                    candles[tf] = data

            if "4h" not in candles or "1h" not in candles:
                continue

            # Step 1: Higher timeframe bias (4H → 1H)
            ht_bias = detect_liquidity_sweep(candles["4h"]) or detect_liquidity_sweep(candles["1h"])
            if not ht_bias:
                msg = f"{symbol}: No clear higher timeframe bias"
                print(msg)
                log_message(msg)
                continue

            # Step 2: Lower timeframe entries (15m, 5m, 1m)
            for tf in ["15m", "5m", "1m"]:
                if tf not in candles:
                    continue
                if analyze_strategy(candles[tf], ht_bias):
                    signal = f"{symbol} {tf} ENTRY ({ht_bias.upper()}) ✅"
                    print(signal)
                    log_message(signal)
                    send_email("Trading Signal", signal)
                else:
                    msg = f"{symbol} {tf}: No valid entry"
                    print(msg)
                    log_message(msg)

        # Wait before next scan (default 2 minutes)
        time.sleep(120)

# Run bot
if __name__ == "__main__":
    run_bot()
