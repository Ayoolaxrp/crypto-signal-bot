import ccxt
import pandas as pd
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# ============ CONFIG ============
SYMBOLS = ["ETH/USDT", "BTC/USDT", "ENA/USDT", "SOL/USDT"]
TIMEFRAMES = {"bias": "1h", "confirm": "15m", "entry": "5m"}

# Email credentials (from Railway/ENV)
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

# Exchange
exchange = ccxt.mexc()

# ============ FETCH DATA ============
def fetch_data(symbol, timeframe="5m", limit=100):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(
            ohlcv,
            columns=['timestamp','open','high','low','close','volume']  # type: ignore
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"❌ Error fetching {symbol} ({timeframe}): {e}")
        return None

# ============ STRATEGY UTILS ============
def detect_bias(df):
    """Simple bias: higher highs/lows = bullish, lower lows/highs = bearish"""
    if df is None or len(df) < 3:
        return None
    last = df['close'].iloc[-1]
    prev = df['close'].iloc[-3]
    return "BULLISH" if last > prev else "BEARISH"

def detect_bos(df):
    """Break of Structure: last close breaks past high/low"""
    if df is None or len(df) < 10:
        return None
    last_close = df['close'].iloc[-1]
    prev_high = df['high'].iloc[-10:-1].max()
    prev_low = df['low'].iloc[-10:-1].min()
    if last_close > prev_high:
        return "BOS_UP"
    elif last_close < prev_low:
        return "BOS_DOWN"
    return None

def detect_liquidity_sweep(df):
    """Liquidity Sweep: wick takes liquidity above/below but closes opposite"""
    if df is None or len(df) < 3:
        return None
    last = df.iloc[-1]
    prev_high = df['high'].iloc[-3:-1].max()
    prev_low = df['low'].iloc[-3:-1].min()
    if last['high'] > prev_high and last['close'] < last['open']:
        return "SWEEP_HIGH"
    elif last['low'] < prev_low and last['close'] > last['open']:
        return "SWEEP_LOW"
    return None

def detect_order_block(df, sweep, bos):
    """Order Block after sweep + BOS"""
    if sweep == "SWEEP_HIGH" and bos == "BOS_DOWN":
        return "BEARISH_OB"
    if sweep == "SWEEP_LOW" and bos == "BOS_UP":
        return "BULLISH_OB"
    return None

def generate_signal(symbol, bias, sweep, bos, ob, df):
    if ob is None:
        return None
    entry = df['close'].iloc[-1]
    stop_loss = df['low'].iloc[-10:-1].min() if ob == "BULLISH_OB" else df['high'].iloc[-10:-1].max()
    risk = abs(entry - stop_loss)
    tp1 = entry + (risk * 2) if ob == "BULLISH_OB" else entry - (risk * 2)
    tp2 = entry + (risk * 3) if ob == "BULLISH_OB" else entry - (risk * 3)
    tp3 = entry + (risk * 4) if ob == "BULLISH_OB" else entry - (risk * 4)

    return f"""
📊 {symbol} SIGNAL
Bias: {bias}
Setup: {ob} (after {sweep} + {bos})

Entry: {entry:.4f}
TP1: {tp1:.4f}
TP2: {tp2:.4f}
TP3: {tp3:.4f}
SL: {stop_loss:.4f}
"""

# ============ EMAIL ============
def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
        server.quit()
        print(f"📧 Email sent: {subject}")
    except Exception as e:
        print(f"❌ Error sending email: {e}")

# ============ MAIN LOOP ============
def run_bot():
    while True:
        for symbol in SYMBOLS:
            bias_df = fetch_data(symbol, TIMEFRAMES["bias"])
            confirm_df = fetch_data(symbol, TIMEFRAMES["confirm"])
            entry_df = fetch_data(symbol, TIMEFRAMES["entry"])

            bias = detect_bias(bias_df)
            sweep = detect_liquidity_sweep(entry_df)
            bos = detect_bos(entry_df)
            ob = detect_order_block(entry_df, sweep, bos)

            signal = generate_signal(symbol, bias, sweep, bos, ob, entry_df)
            if signal:
                send_email(f"{symbol} Trade Signal", signal)

        time.sleep(120)  # 2 minutes

if __name__ == "__main__":
    run_bot()
