import requests
import time
import os
from jam_strategy import check_bearish_setup, check_bullish_setup

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TWELVE_API_KEY = os.environ.get("TWELVE_API_KEY")

SYMBOL = "XAU/USD"
INTERVAL = "15min"

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

def get_candles():
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "outputsize": 5,
        "apikey": TWELVE_API_KEY,
    }
    r = requests.get(url, params=params)
    data = r.json()

    if "values" not in data:
        raise Exception(f"API error: {data}")

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
    send_message("✅ JAM Trading Bot (XAUUSD) is now running!")
    last_signal_time = 0

    while True:
        try:
            candles = get_candles()

            closed = candles[:-1]

            if len(closed) < 2:
                time.sleep(10)
                continue

            bar2 = closed[-2]
            bar1 = closed[-1]

            current_time = time.time()
            if current_time - last_signal_time > 60:
                if check_bearish_setup(bar2, bar1):
                    msg = (
                        f"🔴 BEARISH JAM SIGNAL\n"
                        f"Symbol: XAUUSD (Gold)\n"
                        f"Timeframe: {INTERVAL}\n"
                        f"➡️ SELL at next candle open\n"
                        f"Bar2 Open: {bar2['open']}\n"
                        f"Bar1 Close: {bar1['close']}"
                    )
                    send_message(msg)
                    last_signal_time = current_time

                elif check_bullish_setup(bar2, bar1):
                    msg = (
                        f"🟢 BULLISH JAM SIGNAL\n"
                        f"Symbol: XAUUSD (Gold)\n"
                        f"Timeframe: {INTERVAL}\n"
                        f"➡️ BUY at next candle open\n"
                        f"Bar2 Open: {bar2['open']}\n"
                        f"Bar1 Close: {bar1['close']}"
                    )
                    send_message(msg)
                    last_signal_time = current_time

        except Exception as e:
            send_message(f"⚠️ Error: {str(e)}")

        time.sleep(60)

if __name__ == "__main__":
    main()
