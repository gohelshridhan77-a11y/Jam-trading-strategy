def check_bearish_setup(bar2, bar1):
    upper_wick_bar2 = bar2['high'] - max(bar2['open'], bar2['close'])
    mid_upper_wick = bar2['high'] - (upper_wick_bar2 * 0.5)

    var_a = bar1['high'] > bar2['high']
    var_b = (upper_wick_bar2 > 0) and (bar1['high'] >= mid_upper_wick)
    condition1 = var_a or var_b

    bar1_bearish = bar1['close'] < bar1['open']
    body_closes_below = bar1['close'] < bar2['open']
    condition2 = bar1_bearish and body_closes_below

    return condition1 and condition2


def check_bullish_setup(bar2, bar1):
    lower_wick_bar2 = min(bar2['open'], bar2['close']) - bar2['low']
    mid_lower_wick = bar2['low'] + (lower_wick_bar2 * 0.5)

    var_a = bar1['low'] < bar2['low']
    var_b = (lower_wick_bar2 > 0) and (bar1['low'] <= mid_lower_wick)
    condition1 = var_a or var_b

    bar1_bullish = bar1['close'] > bar1['open']
    body_closes_above = bar1['close'] > bar2['open']
    condition2 = bar1_bullish and body_closes_above

    return condition1 and condition2
