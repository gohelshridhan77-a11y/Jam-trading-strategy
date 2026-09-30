import time
import os
import requests
from datetime import datetime, timezone, timedelta
from jam_strategy import check_bearish_setup, check_bullish_setup

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID        = os.environ.get("CHAT_ID")

XAUUSD_INTERVALS = [
    {"interval": "15",  "name": "15min"},
    {"interval": "60",  "name": "1h"},
    {"interval": "240", "name": "4h"},
]

INDEX_WATCHLIST = [
    {"yahoo": "NQ=F", "name": "US100", "interval": "15m"},
    {"yahoo": "NQ=F", "name": "US100", "interval": "1h"},
    {"yahoo": "YM=F", "name": "US30",  "interval": "15m"},
    {"yahoo": "YM=F", "name": "US30",  "interval": "1h"},
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

def get_kraken_candles(interval):
    """Real-time XAUUSD from Kraken - no API key needed!"""
    url = "https://api.kraken.com/0/public/OHLC"
    params = {
        "pair": "XAUUSD",
        "interval": interval,
    }
    r    = requests.get(url, params=params, timeout=15)
    data = r.json()

    if data.get("error"):
        raise Exception(f"Kraken error: {data['error']}")

    result  = data["result"]
    key     = [k for k in result.keys() if k != "last"][0]
    candles = []
    for c in result[key]:
        try:
            candles.append({
                "open":  float(c[1]),
                "high":  float(c[2]),
                "low":   float(c[3]),
                "close": float(c[4]),
            })
        except (ValueError, IndexError):
            continue
    return candles[-6:]

def get_yahoo_candles(symbol, interval):
    """US100 and US30 from Yahoo Finance"""
    range_map = {
        "15m": "5d",
        "1h":  "1mo",
    }
    period  = range_map.get(interval, "5d")
    url     = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params  = {"interval": interval, "range": period}
    headers = {"User-Agent": "Mozilla/5.0"}
    r       = requests.get(url, params=params, headers=headers, timeout=15)
    data    = r.json()
    try:
        ohlc    = data["chart"]["result"][0]["indicators"]["quote"][0]
        candles = []
        for i in range(len(ohlc["open"])):
            try:
                o = ohlc["open"][i]
                h = ohlc["high"][i]
                l = ohlc["low"][i]
                c = ohlc["close"][i]
                if None not in (o, h, l, c):
                    candles.append({
                        "open":  float(o),
                        "high":  float(h),
                        "low":   float(l),
                        "close": float(c),
                    })
            except (TypeError, ValueError):
                continue
        return candles[-6:]
    except Exception as e:
        raise Exception(f"Yahoo error {symbol}: {str(e)}")

def build_message(direction, name, tf_name, entry, sl, tp, bar1):
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
        f"TF     : {tf_name}\n"
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

def check_and_alert(name, tf_key, tf_name, candles, last_signal_time):
    closed = candles[:-1]
    if len(closed) < 2:
        return last_signal_time

    bar2 = closed[-2]
    bar1 = closed[-1]
    key  = f"{name}_{tf_key}"
    current_time = time.time()

    if current_time - last_signal_time.get(key, 0) > 300:
        try:
            if check_bearish_setup(bar2, bar1):
                entry   = bar1["close"]
                sl      = round(bar1["high"], 5)
                sl_pips = abs(entry - sl)
                tp      = round(entry - sl_pips, 5)
                send_message(build_message(
                    "SELL", name, tf_name,
                    entry, sl, tp, bar1
                ))
                last_signal_time[key] = current_time

            elif check_bullish_setup(bar2, bar1):
                entry   = bar1["close"]
                sl      = round(bar1["low"], 5)
                sl_pips = abs(entry - sl)
                tp      = round(entry + sl_pips, 5)
                send_message(build_message(
                    "BUY", name, tf_name,
                    entry, sl, tp, bar1
                ))
                last_signal_time[key] = current_time

        except Exception as e:
            send_message(f"Error {name} {tf_name}: {str(e)}")

    return last_signal_time

def main():
    send_message(
        "JAM Trading Bot Running!\n"
        "---------------\n"
        "XAUUSD: 15m 1h 4h (Kraken)\n"
        "US100 : 15m 1h (Yahoo)\n"
        "US30  : 15m 1h (Yahoo)\n"
        "---------------\n"
        "Strategy: 75% Wick\n"
        "SL     : Bar1 High/Low\n"
        "TP     : 1:1 RR\n"
        "Hours  : Mon-Fri 8AM-12AM IST"
    )

    last_signal_time = {}
    market_was_open  = False

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

        # XAUUSD via Kraken
        tf_labels = {"15": "15min", "60": "1h", "240": "4h"}
        for item in XAUUSD_INTERVALS:
            try:
                candles = get_kraken_candles(item["interval"])
                last_signal_time = check_and_alert(
                    "XAUUSD", item["interval"],
                    item["name"], candles,
                    last_signal_time
                )
            except Exception as e:
                send_message(f"Error XAUUSD {item['name']}: {str(e)}")
            time.sleep(10)

        # US100 & US30 via Yahoo
        for item in INDEX_WATCHLIST:
            try:
                candles = get_yahoo_candles(item["yahoo"], item["interval"])
                last_signal_time = check_and_alert(
                    item["name"], item["interval"],
                    item["interval"], candles,
                    last_signal_time
                )
            except Exception as e:
                send_message(f"Error {item['name']} {item['interval']}: {str(e)}")
            time.sleep(10)

        time.sleep(300)

if __name__ == "__main__":
    main()
