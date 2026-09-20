import requests
import time
import os
from jam_strategy import check_bearish_setup, check_bullish_setup

TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID         = os.environ.get("CHAT_ID")
TWELVE_API_KEY  = os.environ.get("TWELVE_API_KEY")
ALPHA_API_KEY   = os.environ.get("ALPHA_API_KEY")

# ════════════════════════════════════
# XAUUSD via Twelve Data
# ════════════════════════════════════
XAUUSD_TIMEFRAMES = ["5min", "15min", "1h", "4h"]

# ════════════════════════════════════
# US100 & US30 via Alpha Vantage
# Interval options: 5min, 15min, 60min
# ════════════════════════════════════
INDEX_WATCHLIST = [
    {"symbol": "NDX",  "name": "US100", "interval": "5min"},
    {"symbol": "NDX",  "name": "US100", "interval": "15min"},
    {"symbol": "NDX",  "name": "US100", "interval": "60min"},
    {"symbol": "DJI",  "name": "US30",  "interval": "5min"},
    {"symbol": "DJI",  "name": "US30",  "interval": "15min"},
    {"symbol": "DJI",  "name": "US30",  "interval": "60min"},
]

SL_TP = {
    "XAU/USD": {"5min": (80,160),  "15min": (150,300), "1h": (300,600),  "4h": (600,1200)},
    "US100":   {"5min": (30,60),   "15min": (50,100),  "60min": (100,200), "4h": (200,400)},
    "US30":    {"5min": (50,100),  "15min": (100,200), "60min": (200,400), "4h": (400,800)},
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

def get_index_candles(symbol, interval):
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol,
        "interval": interval,
        "outputsize": "compact",
        "apikey": ALPHA_API_KEY,
    }
    r = requests.get(url, params=params)
    data = r.json()
    key = f"Time Series ({interval})"
    if key not in data:
        raise Exception(f"AlphaVantage error: {data}")
    candles = []
    for ts in sorted(data[key].keys()):
        c = data[key][ts]
        try:
            candles.append({
                "open":  float(c["1. open"]),
                "high":  float(c["2. high"]),
                "low":   float(c["3. low"]),
                "close": float(c["4. close"]),
            })
        except (ValueError, KeyError):
            continue
    return candles[-5:]

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

def check_and_alert(symbol, display_name, interval, candles, last_signal_time):
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
                    "XAU/USD", "XAU/USD", interval, candles, last_signal_time
                )
            except Exception as e:
                send_message(f"⚠️ XAUUSD {interval}: {str(e)}")
            time.sleep(15)

        # ── US100 & US30 via Alpha Vantage ──
        for item in INDEX_WATCHLIST:
            try:
                candles = get_index_candles(item["symbol"], item["interval"])
                last_signal_time = check_and_alert(
                    item["symbol"], item["name"], item["interval"], candles, last_signal_time
                )
            except Exception as e:
                send_message(f"⚠️ {item['name']} {item['interval']}: {str(e)}")
            time.sleep(15)

        time.sleep(60)

if __name__ == "__main__":
    main()
