import requests
import time
import os
from jam_strategy import check_bearish_setup, check_bullish_setup

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SYMBOL = "BTCUSDT"
INTERVAL = "15m"

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

def get_candles():
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": SYMBOL, "interval": INTERVAL, "limit": 3}
    r = requests.get(url, params=params)
    data = r.json()
    candles = []
    for c in data:
        candles.append({
            "open":  float(c[1]),
            "high":  float(c[2]),
            "low":   float(c[3]),
            "close": float(c[4]),
        })
    return candles

def main():
    send_message("✅ JAM Trading Bot is now running!")
    last_signal_time = 0

    while True:
        try:
            candles = get_candles()
            if len(candles) < 3:
                time.sleep(10)
                continue

            bar2 = candles[-3]
            bar1 = candles[-2]

            current_time = time.time()
            if current_time - last_signal_time > 60:
                if check_bearish_setup(bar2, bar1):
                    msg = (
                        f"🔴 BEARISH JAM SIGNAL\n"
                        f"Symbol: {SYMBOL}\n"
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
                        f"Symbol: {SYMBOL}\n"
                        f"Timeframe: {INTERVAL}\n"
                        f"➡️ BUY at next candle open\n"
                        f"Bar2 Open: {bar2['open']}\n"
                        f"Bar1 Close: {bar1['close']}"
                    )
                    send_message(msg)
                    last_signal_time = current_time

        except Exception as e:
            send_message(f"⚠️ Error: {str(e)}")

        time.sleep(30)

if __name__ == "__main__":
    main()
