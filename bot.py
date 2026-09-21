import requests
import time
import os
import json
import asyncio
import websockets
from datetime import datetime, timezone, timedelta
from jam_strategy import check_bearish_setup, check_bullish_setup

TELEGRAM_TOKEN        = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID               = os.environ.get("CHAT_ID")
TWELVE_API_KEY        = os.environ.get("TWELVE_API_KEY")
CTRADER_CLIENT_ID     = os.environ.get("CTRADER_CLIENT_ID")
CTRADER_CLIENT_SECRET = os.environ.get("CTRADER_CLIENT_SECRET")
CTRADER_ACCOUNT_ID    = int(os.environ.get("CTRADER_ACCOUNT_ID", "0"))

XAUUSD_TIMEFRAMES = ["5min", "15min", "1h", "4h"]

INDEX_WATCHLIST = [
    {"symbol": "NQ=F", "name": "US100", "interval": "5m"},
    {"symbol": "NQ=F", "name": "US100", "interval": "15m"},
    {"symbol": "NQ=F", "name": "US100", "interval": "1h"},
    {"symbol": "YM=F", "name": "US30",  "interval": "5m"},
    {"symbol": "YM=F", "name": "US30",  "interval": "15m"},
    {"symbol": "YM=F", "name": "US30",  "interval": "1h"},
]

SL_TP = {
    "XAU/USD": {"5min": (80,80),   "15min": (150,150), "1h": (300,300), "4h": (600,600)},
    "US100":   {"5m":   (30,30),   "15m":   (50,50),   "1h": (100,100)},
    "US30":    {"5m":   (50,50),   "15m":   (100,100), "1h": (200,200)},
}

# cTrader symbol mapping
CTRADER_SYMBOLS = {
    "XAU/USD": "XAUUSD",
    "US100":   "NAS100",
    "US30":    "DJ30",
}

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

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
    range_map = {"5m": "2d", "15m": "5d", "1h": "1mo"}
    period = range_map.get(interval, "5d")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"interval": interval, "range": period}
    headers = {"User-Agent": "Mozilla/5.0"}
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

async def get_ctrader_token():
    url = "https://connect.spotware.com/apps/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": CTRADER_CLIENT_ID,
        "client_secret": CTRADER_CLIENT_SECRET,
    }
    r = requests.post(url, data=params)
    data = r.json()
    if "accessToken" not in data:
        raise Exception(f"Token error: {data}")
    return data["accessToken"]

async def ctrader_place_trade(symbol, direction, volume_lots=0.01):
    try:
        token = await get_ctrader_token()
        uri = "wss://live.ctraderapi.com:5036"

        async with websockets.connect(uri) as ws:
            # Authenticate
            auth_msg = {
                "clientMsgId": "auth",
                "payloadType": 2100,
                "payload": {
                    "clientId": CTRADER_CLIENT_ID,
                    "clientSecret": CTRADER_CLIENT_SECRET,
                }
            }
            await ws.send(json.dumps(auth_msg))
            await asyncio.sleep(1)
            await ws.recv()

            # Authorize account
            account_auth = {
                "clientMsgId": "account_auth",
                "payloadType": 2102,
                "payload": {
                    "ctidTraderAccountId": CTRADER_ACCOUNT_ID,
                    "accessToken": token,
                }
            }
            await ws.send(json.dumps(account_auth))
            await asyncio.sleep(1)
            await ws.recv()

            # Place trade
            trade_side = 1 if direction == "BUY" else 2
            ctrade_symbol = CTRADER_SYMBOLS.get(symbol, "XAUUSD")

            order_msg = {
                "clientMsgId": "new_order",
                "payloadType": 2106,
                "payload": {
                    "ctidTraderAccountId": CTRADER_ACCOUNT_ID,
                    "symbolName": ctrade_symbol,
                    "orderType": 1,
                    "tradeSide": trade_side,
                    "volume": int(volume_lots * 100000),
                    "timeInForce": 1,
                }
            }
            await ws.send(json.dumps(order_msg))
            await asyncio.sleep(1)
            result = await ws.recv()
            data = json.loads(result)
            return data

    except Exception as e:
        raise Exception(f"cTrader trade failed: {str(e)}")

def place_trade(symbol, direction):
    try:
        result = asyncio.run(
            ctrader_place_trade(symbol, direction)
        )
        return f"✅ Placed! {result}"
    except Exception as e:
        send_message(f"⚠️ Trade failed: {str(e)}")
        return None

def build_message(direction, symbol, interval, entry, sl, tp, bar2, bar1, trade_result=None):
    emoji  = "🔴 BEARISH" if direction == "SELL" else "🟢 BULLISH"
    action = "SELL" if direction == "SELL" else "BUY"
    risk   = abs(entry - sl)
    reward = abs(tp - entry)
    rr     = round(reward / risk, 2) if risk > 0 else 0
    timestamp = get_timestamp()

    msg = (
        f"{emoji} JAM SIGNAL\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 Symbol: {symbol}\n"
        f"⏱ Timeframe: {interval}\n"
        f"🕐 Time: {timestamp}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"➡️ {action} at: {entry}\n"
        f"🛑 Stop Loss: {sl}\n"
        f"✅ Take Profit: {tp}\n"
        f"⚖️ Risk/Reward: 1:{rr}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Bar2 Open: {bar2['open']}\n"
        f"Bar1 Close: {bar1['close']}\n"
        f"━━━━━━━━━━━━━━━\n"
    )
    if trade_result:
        msg += f"🤖 Auto Trade: {trade_result}"
    else:
        msg += f"🤖 Auto Trade: ❌ Failed"
    return msg

def check_and_alert(display_name, interval, candles, last_signal_time):
    closed = candles[:-1]
    if len(closed) < 2:
        return last_signal_time

    bar2 = closed[-2]
    bar1 = closed[-1]
    key  = f"{display_name}_{interval}"
    current_time = time.time()
    sl_val, tp_val = SL_TP.get(display_name, {}).get(interval, (100, 100))

    if current_time - last_signal_time.get(key, 0) > 300:
        try:
            if check_bearish_setup(bar2, bar1):
                entry = bar1["close"]
                sl    = round(bar1["high"] + sl_val, 3)
                tp    = round(entry - sl_val, 3)
                trade_result = place_trade(display_name, "SELL")
                send_message(build_message(
                    "SELL", display_name, interval,
                    entry, sl, tp, bar2, bar1, trade_result
                ))
                last_signal_time[key] = current_time

            elif check_bullish_setup(bar2, bar1):
                entry = bar1["close"]
                sl    = round(bar1["low"] - sl_val, 3)
                tp    = round(entry + sl_val, 3)
                trade_result = place_trade(display_name, "BUY")
                send_message(build_message(
                    "BUY", display_name, interval,
                    entry, sl, tp, bar2, bar1, trade_result
                ))
                last_signal_time[key] = current_time

        except Exception as e:
            send_message(f"⚠️ Error {display_name} {interval}: {str(e)}")

    return last_signal_time

def main():
    send_message(
        "✅ JAM Auto Trading Bot is now running!\n"
        "━━━━━━━━━━━━━━━\n"
        "📊 Monitoring:\n"
        "🥇 XAUUSD → 5m | 15m | 1h | 4h\n"
        "📈 US100  → 5m | 15m | 1h\n"
        "📈 US30   → 5m | 15m | 1h\n"
        "━━━━━━━━━━━━━━━\n"
        "🤖 Auto Trading: cTrader ENABLED\n"
        "💰 Account: DEMO\n"
        "🕐 Market Hours: Mon-Fri 8AM-12AM IST"
    )

    last_signal_time = {}
    market_was_open = False

    while True:
        if not is_market_open():
            ist = get_ist_time()
            if market_was_open:
                send_message(
                    "🔕 Market is now closed!\n"
                    "Bot will resume Monday 8:00AM IST"
                    if ist.weekday() == 4
                    else "🔕 Market is now closed!\n"
                    "Bot will resume tomorrow 8:00AM IST"
                )
                market_was_open = False
            time.sleep(60)
            continue

        if not market_was_open:
            send_message(
                "🔔 Market is now open!\n"
                "JAM Bot scanning for signals..."
            )
            market_was_open = True

        for interval in XAUUSD_TIMEFRAMES:
            try:
                candles = get_xauusd_candles(interval)
                last_signal_time = check_and_alert(
                    "XAU/USD", interval, candles, last_signal_time
                )
            except Exception as e:
                send_message(f"⚠️ XAUUSD {interval}: {str(e)}")
            time.sleep(15)

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
