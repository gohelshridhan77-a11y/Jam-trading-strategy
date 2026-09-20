import requests
import time
import os
from jam_strategy import check_bearish_setup, check_bullish_setup

TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID         = os.environ.get("CHAT_ID")
TWELVE_API_KEY  = os.environ.get("TWELVE_API_KEY")

# ════════════════════════════════════
# XAUUSD via Twelve Data
# ════════════════════════════════════
XAUUSD_TIMEFRAMES = ["5min", "15min", "1h", "4h"]

# ════════════════════════════════════
# US100 & US30 via Yahoo Finance
# ════════════════════════════════════
INDEX_WATCHLIST = [
    {"symbol": "NQ=F",  "name": "US100", "interval": "5m"},
    {"symbol": "NQ=F",  "name": "US100", "interval": "15m"},
    {"symbol": "NQ=F",  "name": "US100", "interval": "1h"},
    {"symbol": "YM=F",  "name": "US30",  "interval": "5m"},
    {"symbol": "YM=F",  "name": "US30",  "interval": "15m"},
    {"symbol": "YM=F",  "name": "US30",  "interval": "1h"},
]

SL_TP = {
    "XAU/USD": {"5min": (80,160),  "15min": (150,300), "1h": (300,600),  "4h": (600,1200)},
    "US100":   {"5m":   (30,60),   "15m":   (50,100),  "1h": (100,200)},
    "US30":    {"5m":   (50,100),  "15m":   (100,200), "1h": (200,400)},
}

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

def get_xauusd_candles(interval):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": "XAU/USD",
        "interval": interval,
        "outputsize": 5,
        "apikey": TWELVE_API_KEY,
    }
    r = requests.get(url, params=params)
    data = r.json()
    if "values" not in data:
        raise Exception(f"TwelveData error: {data}")
    candles = []
    for c in reversed(data["values"]):
        try:
            candles.append({
                "open":  float(c["open"]),
                "high":  float(c["high"]),
                "low":   float(c["low"]),
                "close": float(c["close"]),
            })
        except (ValueError, KeyError):
            continue
    return candles

def get_yahoo_candles(symbol, interval):
    # Map interval to Yahoo Finance range
    range_map = {
        "5m":  "2d",
        "15m": "5d",
        "1h":  "1mo",
    }
    period = range_map.get(interval, "5d")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        "interval": interval,
        "range": period,
    }
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    r = requests.get(url, params=params, headers=headers)
    data = r.json()

    try:
        timestamps = data["chart"]["result"][0]["timestamp"]
        ohlc = data["chart"]["result"][0]["indicators"]["quote"][0]
        candles = []
        for i in range(len(timestamps)):
            try:
                candles.append({
                    "open":  float(ohlc["open"][i]),
                    "high":  float(ohlc["high"][i]),
                    "low":   float(ohlc["low"][i]),
                    "close": float(ohlc["close"][i]),
                })
            except (TypeError, ValueError):
                continue
        return candles[-5:]
    except (KeyError, IndexError, TypeError) as e:
        raise Exception(f"Yahoo error for {symbol}: {e}")

def build_message(direction, symbol, interval, entry, sl, tp, bar2, bar1):
    emoji = "🔴 BEARISH" if direction == "SELL" else "🟢 BULLISH"
    action = "SELL" if direction == "SELL" else "BUY"
    return (
        f"{emoji} JAM SIGNAL\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 Symbol: {symbol}\n"
        f"⏱ Timeframe: {interval}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"➡️ {action} at: {entry}\n"
        f"🛑 Stop Loss: {sl}\n"
        f"✅ Take Profit: {tp}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Bar2 Open: {bar2['open']}\n"
        f"Bar1 Close: {bar1['close']}"
    )

def check_and_alert(display_name, interval, candles, last_signal_time):
    closed = candles[:-1]
    if len(closed) < 2:
        return last_signal_time

    bar2 = closed[-2]
    bar1 = closed[-1]
    key  = f"{display_name}_{interval}"
    current_time = time.time()
    sl_val, tp_val = SL_TP.get(display_name, {}).get(interval, (100, 200))

    if current_time - last_signal_time.get(key, 0) > 300:
        if check_bearish_setup(bar2, bar1):
            entry = bar1["close"]
            sl    = round(entry + sl_val, 3)
            tp    = round(entry - tp_val, 3)
            send_message(build_message("SELL", display_name, interval, entry, sl, tp, bar2, bar1))
            last_signal_time[key] = current_time

        elif check_bullish_setup(bar2, bar1):
            entry = bar1["close"]
            sl    = round(entry - sl_val, 3)
            tp    = round(entry + tp_val, 3)
            send_message(build_message("BUY", display_name, interval, entry, sl, tp, bar2, bar1))
            last_signal_time[key] = current_time

    return last_signal_time

def main():
    send_message(
        "✅ JAM Trading Bot is now running!\n"
        "━━━━━━━━━━━━━━━\n"
        "📊 Monitoring:\n"
        "🥇 XAUUSD → 5m | 15m | 1h | 4h\n"
        "📈 US100  → 5m | 15m | 1h\n"
        "📈 US30   → 5m | 15m | 1h\n"
        "━━━━━━━━━━━━━━━"
    )

    last_signal_time = {}

    while True:
        # ── XAUUSD via Twelve Data ──
        for interval in XAUUSD_TIMEFRAMES:
            try:
                candles = get_xauusd_candles(interval)
                last_signal_time = check_and_alert(
                    "XAU/USD", interval, candles, last_signal_time
                )
            except Exception as e:
                send_message(f"⚠️ XAUUSD {interval}: {str(e)}")
            time.sleep(15)

        # ── US100 & US30 via Yahoo Finance ──
        for item in INDEX_WATCHLIST:
            try:
                candles = get_yahoo_candles(item["symbol"], item["interval"])
                last_signal_time = check_and_alert(
                    item["name"], item["interval"], candles, last_signal_time
                )
            except Exception as e:
                send_message(f"⚠️ {item['name']} {item['interval']}: {str(e)}")
            time.sleep(15)

        time.sleep(60)

if __name__ == "__main__":
    main()
