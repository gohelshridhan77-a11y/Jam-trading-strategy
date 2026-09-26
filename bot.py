import time
import os
import requests
from datetime import datetime, timezone, timedelta, date
from jam_strategy import check_bearish_setup, check_bullish_setup

TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID         = os.environ.get("CHAT_ID")
POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")

# Polygon.io symbols
WATCHLIST = [
    {"symbol": "C:XAUUSD", "name": "XAUUSD", "interval": "3"},
    {"symbol": "C:XAUUSD", "name": "XAUUSD", "interval": "5"},
    {"symbol": "C:XAUUSD", "name": "XAUUSD", "interval": "15"},
    {"symbol": "I:NDX",    "name": "US100",  "interval": "3"},
    {"symbol": "I:NDX",    "name": "US100",  "interval": "5"},
    {"symbol": "I:NDX",    "name": "US100",  "interval": "15"},
    {"symbol": "I:DJI",    "name": "US30",   "interval": "3"},
    {"symbol": "I:DJI",    "name": "US30",   "interval": "5"},
    {"symbol": "I:DJI",    "name": "US30",   "interval": "15"},
]

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except:
        pass

def get_ist_time():
    utc_now = datetime.now(timezone.utc)
    return utc_now + timedelta(hours=5, minutes=30)

def is_market_open():
    ist = get_ist_time()
    if ist.weekday() > 4:
        return False
    market_open  = ist.replace(hour=8,  minute=0,  second=0)
    market_close = ist.replace(hour=23, minute=59, second=0)
    return market_open <= ist <= market_close

def get_timestamp():
    ist = get_ist_time()
    return ist.strftime("%Y-%m-%d %H:%M IST")

def get_candles(symbol, interval):
    # Get date range
    today = date.today()
    from_date = (today - timedelta(days=5)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range"
        f"/{interval}/minute/{from_date}/{to_date}"
    )
    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": 10,
        "apiKey": POLYGON_API_KEY,
    }
    r = requests.get(url, params=params, timeout=15)
    data = r.json()

    if data.get("status") == "ERROR" or "results" not in data:
        raise Exception(f"Polygon error: {data.get('error', data)}")

    candles = []
    for c in data["results"]:
        try:
            candles.append({
                "open":  float(c["o"]),
                "high":  float(c["h"]),
                "low":   float(c["l"]),
                "close": float(c["c"]),
            })
        except (ValueError, KeyError):
            continue
    return candles

def build_message(direction, name, interval, entry, sl, tp, bar1):
    emoji  = "🔴 BEARISH" if direction == "SELL" else "🟢 BULLISH"
    action = "SELL" if direction == "SELL" else "BUY"
    risk   = abs(entry - sl)
    reward = abs(tp - entry)
    rr     = round(reward / risk, 2) if risk > 0 else 0
    timestamp = get_timestamp()
    return (
        f"{emoji} JAM SIGNAL\n"
        f"---------------\n"
        f"Symbol : {name}\n"
        f"TF     : {interval}min\n"
        f"Time   : {timestamp}\n"
        f"---------------\n"
        f"Action : {action}\n"
        f"Entry  : {entry}\n"
        f"SL     : {sl}\n"
        f"TP     : {tp}\n"
        f"RR     : 1:{rr}\n"
        f"---------------\n"
        f"Bar1 H : {bar1['high']}\n"
        f"Bar1 L : {bar1['low']}\n"
        f"Bar1 C : {bar1['close']}"
    )

def check_and_alert(name, interval, candles, last_signal_time):
    closed = candles[:-1]
    if len(closed) < 2:
        return last_signal_time

    bar2 = closed[-2]
    bar1 = closed[-1]
    key  = f"{name}_{interval}"
    current_time = time.time()

    if current_time - last_signal_time.get(key, 0) > 300:
        try:
            if check_bearish_setup(bar2, bar1):
                entry   = bar1["close"]
                sl      = round(bar1["high"], 5)
                sl_pips = abs(entry - sl)
                tp      = round(entry - sl_pips, 5)
                send_message(build_message(
                    "SELL", name, interval,
                    entry, sl, tp, bar1
                ))
                last_signal_time[key] = current_time

            elif check_bullish_setup(bar2, bar1):
                entry   = bar1["close"]
                sl      = round(bar1["low"], 5)
                sl_pips = abs(entry - sl)
                tp      = round(entry + sl_pips, 5)
                send_message(build_message(
                    "BUY", name, interval,
                    entry, sl, tp, bar1
                ))
                last_signal_time[key] = current_time

        except Exception as e:
            send_message(f"Error {name} {interval}: {str(e)}")

    return last_signal_time

def main():
    send_message(
        "JAM Trading Bot Running!\n"
        "---------------\n"
        "XAUUSD: 3m 5m 15m\n"
        "US100 : 3m 5m 15m\n"
        "US30  : 3m 5m 15m\n"
        "---------------\n"
        "Strategy : 75% Wick\n"
        "SL       : Bar1 High/Low\n"
        "TP       : 1:1 RR\n"
        "Data     : Real-Time\n"
        "Hours    : Mon-Fri 8AM-12AM IST"
    )

    last_signal_time = {}
    market_was_open = False

    while True:
        if not is_market_open():
            ist = get_ist_time()
            if market_was_open:
                send_message(
                    "Market Closed!\nResume Monday 8AM IST"
                    if ist.weekday() == 4
                    else "Market Closed!\nResume Tomorrow 8AM IST"
                )
                market_was_open = False
            time.sleep(60)
            continue

        if not market_was_open:
            send_message("Market Open!\nJAM Bot Scanning...")
            market_was_open = True

        for item in WATCHLIST:
            try:
                candles = get_candles(
                    item["symbol"],
                    item["interval"]
                )
                last_signal_time = check_and_alert(
                    item["name"],
                    item["interval"],
                    candles,
                    last_signal_time
                )
            except Exception as e:
                send_message(f"Error {item['name']} {item['interval']}m: {str(e)}")
            time.sleep(15)

        time.sleep(180)

if __name__ == "__main__":
    main()
