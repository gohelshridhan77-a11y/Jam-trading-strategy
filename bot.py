import requests
import time
import os
from jam_strategy import check_bearish_setup, check_bullish_setup

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TWELVE_API_KEY = os.environ.get("TWELVE_API_KEY")

# ════════════════════════════════════
# ALL SYMBOLS & TIMEFRAMES
# ════════════════════════════════════
WATCHLIST = [
    # XAUUSD - 4 timeframes
    {"symbol": "XAU/USD", "interval": "5min",  "sl_pips": 80,  "tp_pips": 160},
    {"symbol": "XAU/USD", "interval": "15min", "sl_pips": 150, "tp_pips": 300},
    {"symbol": "XAU/USD", "interval": "1h",    "sl_pips": 300, "tp_pips": 600},
    {"symbol": "XAU/USD", "interval": "4h",    "sl_pips": 600, "tp_pips": 1200},

    # US100 - 4 timeframes
    {"symbol": "US100",   "interval": "5min",  "sl_pips": 30,  "tp_pips": 60},
    {"symbol": "US100",   "interval": "15min", "sl_pips": 50,  "tp_pips": 100},
    {"symbol": "US100",   "interval": "1h",    "sl_pips": 100, "tp_pips": 200},
    {"symbol": "US100",   "interval": "4h",    "sl_pips": 200, "tp_pips": 400},

    # US30 - 4 timeframes
    {"symbol": "US30",    "interval": "5min",  "sl_pips": 50,  "tp_pips": 100},
    {"symbol": "US30",    "interval": "15min", "sl_pips": 100, "tp_pips": 200},
    {"symbol": "US30",    "interval": "1h",    "sl_pips": 200, "tp_pips": 400},
    {"symbol": "US30",    "interval": "4h",    "sl_pips": 400, "tp_pips": 800},
]

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

def get_candles(symbol, interval):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": 5,
        "apikey": TWELVE_API_KEY,
    }
    r = requests.get(url, params=params)
    data = r.json()

    if "values" not in data:
        raise Exception(f"API error for {symbol} {interval}: {data}")

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

def main():
    send_message(
        "✅ JAM Trading Bot is now running!\n"
        "━━━━━━━━━━━━━━━\n"
        "📊 Monitoring:\n"
        "🥇 XAUUSD → 5m | 15m | 1h | 4h\n"
        "📈 US100  → 5m | 15m | 1h | 4h\n"
        "📈 US30   → 5m | 15m | 1h | 4h\n"
        "━━━━━━━━━━━━━━━"
    )

    last_signal_time = {}
    for item in WATCHLIST:
        key = f"{item['symbol']}_{item['interval']}"
        last_signal_time[key] = 0

    while True:
        for item in WATCHLIST:
            symbol   = item["symbol"]
            interval = item["interval"]
            sl_pips  = item["sl_pips"]
            tp_pips  = item["tp_pips"]
            key      = f"{symbol}_{interval}"

            try:
                candles = get_candles(symbol, interval)
                closed  = candles[:-1]

                if len(closed) < 2:
                    time.sleep(15)
                    continue

                bar2 = closed[-2]
                bar1 = closed[-1]
                current_time = time.time()

                if current_time - last_signal_time[key] > 300:

                    if check_bearish_setup(bar2, bar1):
                        entry = bar1["close"]
                        sl    = round(entry + sl_pips, 3)
                        tp    = round(entry - tp_pips, 3)
                        msg = (
                            f"🔴 BEARISH JAM SIGNAL\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"📊 Symbol: {symbol}\n"
                            f"⏱ Timeframe: {interval}\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"➡️ SELL at: {entry}\n"
                            f"🛑 Stop Loss: {sl}\n"
                            f"✅ Take Profit: {tp}\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"Bar2 Open: {bar2['open']}\n"
                            f"Bar1 Close: {bar1['close']}"
                        )
                        send_message(msg)
                        last_signal_time[key] = current_time

                    elif check_bullish_setup(bar2, bar1):
                        entry = bar1["close"]
                        sl    = round(entry - sl_pips, 3)
                        tp    = round(entry + tp_pips, 3)
                        msg = (
                            f"🟢 BULLISH JAM SIGNAL\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"📊 Symbol: {symbol}\n"
                            f"⏱ Timeframe: {interval}\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"➡️ BUY at: {entry}\n"
                            f"🛑 Stop Loss: {sl}\n"
                            f"✅ Take Profit: {tp}\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"Bar2 Open: {bar2['open']}\n"
                            f"Bar1 Close: {bar1['close']}"
                        )
                        send_message(msg)
                        last_signal_time[key] = current_time

            except Exception as e:
                send_message(f"⚠️ Error {symbol} {interval}: {str(e)}")

            # Wait between calls to respect API limit
            time.sleep(15)

        time.sleep(60)

if __name__ == "__main__":
    main()
