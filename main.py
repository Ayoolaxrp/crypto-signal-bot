# main.py
import os
import time
import ccxt
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

# Load .env locally (Railway injects env vars automatically)
load_dotenv()

# === Config ===
SYMBOLS = ["ETH/USDT", "BTC/USDT", "ENA/USDT", "SOL/USDT"]  # edit list as needed
TIMEFRAMES = {"bias": "1h", "confirm": "15m", "entry": "5m"}
LOOP_INTERVAL_SECONDS = 120  # bot loop runs every 2 minutes

# Email env vars (set these in Railway Variables)
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")   # use Gmail App Password
EMAIL_TO = os.getenv("EMAIL_TO")
SEND_TEST_EMAIL = os.getenv("SEND_TEST_EMAIL", "0") == "1"

# Exchange (public OHLCV data; no API keys needed for analysis)
exchange = ccxt.mexc({"enableRateLimit": True})

# Keep last sent signal per symbol to avoid spamming identical signals
last_sent = {}  # symbol -> (signature, timestamp)

# === Utilities / Fetch ===
def fetch_ohlcv(symbol, timeframe, limit=200):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["ts","open","high","low","close","volume"])  # type: ignore
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        return df
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching {symbol} {timeframe}: {e}")
        return None

# === Strategy pieces ===
def detect_bias(df):
    # Robust bias: compare last close vs 20-period MA (returns "BULLISH"/"BEARISH")
    if df is None or len(df) < 30:
        return None
    ma20 = df["close"].rolling(20).mean().iloc[-1]
    last = df["close"].iloc[-1]
    return "BULLISH" if last > ma20 else "BEARISH"

def detect_bos(df):
    # Break of structure compared to recent swing (10 candles)
    if df is None or len(df) < 12:
        return None
    prev_high = df["high"].iloc[-12:-2].max()
    prev_low  = df["low"].iloc[-12:-2].min()
    last_close = df["close"].iloc[-1]
    if last_close > prev_high:
        return "BOS_UP"
    if last_close < prev_low:
        return "BOS_DOWN"
    return None

def detect_liquidity_sweep(df):
    # Sweep if last candle's wick takes out recent high/low then closes back inside
    if df is None or len(df) < 6:
        return None
    recent_high = df["high"].iloc[-6:-1].max()
    recent_low  = df["low"].iloc[-6:-1].min()
    last = df.iloc[-1]
    # bearish sweep: wick above recent high but close is bearish (failed high)
    if last["high"] > recent_high and last["close"] < last["open"]:
        return "SWEEP_HIGH"
    # bullish sweep: wick below recent low but close is bullish (failed low)
    if last["low"] < recent_low and last["close"] > last["open"]:
        return "SWEEP_LOW"
    return None

def detect_order_block(df, sweep, bos):
    # very simple OB: take the candle before last as OB level
    if df is None or len(df) < 3:
        return (None, None)
    prev = df.iloc[-2]
    if sweep == "SWEEP_LOW" and bos == "BOS_UP":
        return ("BULLISH_OB", float(prev["low"]))
    if sweep == "SWEEP_HIGH" and bos == "BOS_DOWN":
        return ("BEARISH_OB", float(prev["high"]))
    return (None, None)

def build_signal_text(symbol, bias, sweep, bos, ob_label, ob_price, entry_df):
    # SL = recent extreme (10 candles), risk = abs(entry - sl)
    recent_low = entry_df["low"].iloc[-11:-1].min()
    recent_high = entry_df["high"].iloc[-11:-1].max()
    if ob_label == "BULLISH_OB":
        entry = ob_price
        sl = recent_low
        risk = abs(entry - sl)
        tp1 = entry + risk * 2
        tp2 = entry + risk * 3
        tp3 = entry + risk * 4
    else:  # BEARISH_OB
        entry = ob_price
        sl = recent_high
        risk = abs(entry - sl)
        tp1 = entry - risk * 2
        tp2 = entry - risk * 3
        tp3 = entry - risk * 4

    text = (
        f"Signal for {symbol}\n"
        f"Bias (1H): {bias}\n"
        f"Setup: {ob_label}  (from {sweep} + {bos})\n\n"
        f"Entry: {entry:.6f}\n"
        f"TP1: {tp1:.6f}\n"
        f"TP2: {tp2:.6f}\n"
        f"TP3: {tp3:.6f}\n"
        f"SL: {sl:.6f}\n"
    )
    return text

# === Email ===
def send_email(subject, body):
    if not (EMAIL_USER and EMAIL_PASS and EMAIL_TO):
        print(f"[{datetime.now()}] Email not sent: missing EMAIL_USER/EMAIL_PASS/EMAIL_TO")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
        print(f"[{datetime.now()}] Email sent: {subject}")
        return True
    except Exception as e:
        print(f"[{datetime.now()}] Error sending email: {e}")
        return False

# === Main loop ===
def run_bot():
    print(f"[{datetime.now()}] Bot started. Timeframe: bias={TIMEFRAMES['bias']} confirm={TIMEFRAMES['confirm']} entry={TIMEFRAMES['entry']}")
    # optional startup test email
    if SEND_TEST_EMAIL:
        send_email("Signal Bot — Test Email", f"Test sent at {datetime.now()}")
    while True:
        for symbol in SYMBOLS:
            try:
                # 1) fetch bias (1H), confirmation (15m) and entry (5m)
                bias_df = fetch_ohlcv(symbol, TIMEFRAMES["bias"], limit=200)
                confirm_df = fetch_ohlcv(symbol, TIMEFRAMES["confirm"], limit=200)
                entry_df = fetch_ohlcv(symbol, TIMEFRAMES["entry"], limit=200)
                # small pacing between fetches
                time.sleep(0.5)

                bias = detect_bias(bias_df)
                bias_confirm = detect_bias(confirm_df)

                # require bias alignment: 1H bias must match 15m bias
                if bias is None or bias_confirm is None:
                    print(f"[{datetime.now()}] {symbol}: insufficient data for bias or confirmation.")
                    continue
                if bias != bias_confirm:
                    print(f"[{datetime.now()}] {symbol}: bias mismatch (1H={bias} vs 15m={bias_confirm}) — skipping.")
                    continue

                # now check entry-level confluences on entry_df (5m)
                sweep = detect_liquidity_sweep(entry_df)
                bos = detect_bos(entry_df)
                ob_label, ob_price = detect_order_block(entry_df, sweep, bos)

                if ob_label and ob_price is not None:
                    # ensure OB direction matches bias (safe check)
                    if (bias == "BULLISH" and ob_label != "BULLISH_OB") or (bias == "BEARISH" and ob_label != "BEARISH_OB"):
                        print(f"[{datetime.now()}] {symbol}: OB direction {ob_label} does not match bias {bias} — skipping.")
                        continue

                    text = build_signal_text(symbol, bias, sweep, bos, ob_label, ob_price, entry_df)

                    # dedupe similar signals per symbol (cooldown 10 minutes)
                    signature = f"{ob_label}_{round(ob_price,6)}"
                    now_ts = time.time()
                    prev = last_sent.get(symbol)
                    if prev and prev[0] == signature and now_ts - prev[1] < 600:
                        print(f"[{datetime.now()}] {symbol}: duplicate signal recently sent -> skip email.")
                    else:
                        print(f"[{datetime.now()}] SIGNAL: {symbol}\n{text}")
                        send_email(f"{symbol} Trade Signal", text)
                        last_sent[symbol] = (signature, now_ts)
                else:
                    print(f"[{datetime.now()}] {symbol}: no valid entry confluence (sweep={sweep}, bos={bos}, ob={ob_label}).")

            except Exception as e:
                print(f"[{datetime.now()}] Error processing {symbol}: {e}")

        # loop interval (2 minutes)
        print(f"[{datetime.now()}] Cycle complete — sleeping {LOOP_INTERVAL_SECONDS} seconds.\n")
        time.sleep(LOOP_INTERVAL_SECONDS)

if __name__ == "__main__":
    run_bot()
