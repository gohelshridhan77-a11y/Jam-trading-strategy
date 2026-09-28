import time
import os
import requests
from datetime import datetime, timezone, timedelta
from jam_strategy import check_bearish_setup, check_bullish_setup

TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID         = os.environ.get("CHAT_ID")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY")

WATCHLIST = [
    {"symbol": "OANDA:XAU_USD", "name": "XAUUSD", "interval": "15"},
    {"symbol": "OANDA:XAU_USD", "name": "XAUUSD", "interval": "60"},
    {"symbol": "OANDA:XAU_USD", "name": "XAUUSD", "interval": "240"},
    {"symbol": "OANDA:NAS100_USD", "name": "US100", "interval": "15"},
    {"symbol": "OANDA:NAS100_USD", "name": "US100", "interval": "60"},
    {"symbol": "OANDA:US30_USD",   "name": "US30",  "interval": "15"},
    {"symbol": "OANDA:US30_USD",   "name": "US30",  "interval": "60"},
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
    import time as t
    now = int(t.time())
    # Get enough history based on interval
    if interval == "15":
        from_time = now - (15 * 60 * 20)  # 20 candles back
    elif interval == "60":
        from_time = now - (60 * 60 * 20)
    else:
        from_time = now - (240 * 60 * 20)

    url = "https://finnhub.io/api/v1/forex/candle"
    params = {
        "symbol": symbol,
        "resolution": interval,
        "from": from_time,
        "to": now,
        "token": FINNHUB_API_KEY,
    }
    r = requests.get(url, params=params, timeout=15)
    data = r.json()

    if data.get("s") == "no_data" or "o" not in data:
        raise Exception(f"No data for {symbol}")

    candles = []
    for i in range(len(data["o"])):
        try:
            candles.append({
                "open":  float(data["o"][i]),
                "high":  float(data["h"][i]),
                "low":   float(data["l"][i]),
                "close": float(data["c"][i]),
            })
        except (ValueError, KeyError):
            continue
    return candles[-6:]

def build_message(direction, name, interval, entry, sl, tp, bar1):
    emoji  = "🔴 BEARISH" if direction == "SELL" else "🟢 BULLISH"
    action = "SELL" if direction == "SELL" else "BUY"
    risk   = abs(entry - sl)
    reward = abs(tp - entry)
    rr     = round(reward / risk, 2) if risk > 0 else 0
    tf_map = {"15": "15min", "60": "1h", "240": "4h"}
    tf     = tf_map.get(interval, interval)
    timestamp = get_timestamp()
    return (
        f"{emoji} JAM SIGNAL\n"
        f"---------------\n"
        f"Symbol : {name}\n"
        f"TF     : {tf}\n"
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
        "XAUUSD: 15m 1h 4h\n"
        "US100 : 15m 1h\n"
        "US30  : 15m 1h\n"
        "---------------\n"
        "Data   : Finnhub Real-Time\n"
        "Strategy: 75% Wick\n"
        "SL     : Bar1 High/Low\n"
        "TP     : 1:1 RR\n"
        "Hours  : Mon-Fri 8AM-12AM IST"
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
                candles = get_candles(item["symbol"], item["interval"])
                last_signal_time = check_and_alert(
                    item["name"], item["interval"],
                    candles, last_signal_time
                )
            except Exception as e:
                send_message(f"Error {item['name']} {item['interval']}m: {str(e)}")
            time.sleep(15)

        time.sleep(300)

if __name__ == "__main__":
    main()
