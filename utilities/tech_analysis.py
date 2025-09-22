import numpy as np
import pandas as pd
from typing import Dict, Optional
from .stock_candle import get_cached_stock_data


def compute_sma(series: pd.Series, window: int) -> pd.Series:
    return pd.to_numeric(series, errors='coerce').rolling(window=window, min_periods=1).mean()


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    return pd.to_numeric(series, errors='coerce').ewm(span=span, adjust=False, min_periods=1).mean()


def compute_rsi(series: pd.Series, length: int = 14) -> pd.Series:
    s = pd.to_numeric(series, errors='coerce')
    delta = s.diff()
    gain = (delta.clip(lower=0)).ewm(alpha=1/length, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/length, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = compute_ema(series, fast)
    ema_slow = compute_ema(series, slow)
    macd = ema_fast - ema_slow
    macd_signal = compute_ema(macd, signal)
    macd_hist = macd - macd_signal
    return macd, macd_signal, macd_hist


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    h = pd.to_numeric(high, errors='coerce').fillna(method='ffill')
    l = pd.to_numeric(low, errors='coerce').fillna(method='ffill')
    c = pd.to_numeric(close, errors='coerce').fillna(method='ffill')
    prev_close = c.shift(1)
    tr = np.maximum(h - l, np.maximum((h - prev_close).abs(), (l - prev_close).abs()))
    atr = tr.ewm(alpha=1/length, adjust=False, min_periods=1).mean()
    return atr


def _linreg_slope(series: pd.Series, lookback: int) -> float:
    s = pd.Series(series).dropna()
    if len(s) < max(3, lookback):
        return 0.0
    y = s.iloc[-lookback:]
    x = np.arange(len(y), dtype=float)
    x_mean = x.mean(); y_mean = y.mean()
    denom = ((x - x_mean) ** 2).sum()
    if denom == 0:
        return 0.0
    return float(((x - x_mean) * (y - y_mean)).sum() / denom)


def _scale_slope_to_weight(series: pd.Series, lookback: int, weight: float, threshold_ppm: float) -> float:
    slope = _linreg_slope(series, lookback)
    avg_price = float(pd.Series(series).iloc[-lookback:].mean()) if len(series) >= lookback else float(pd.Series(series).iloc[-1])
    if avg_price <= 0:
        return 0.0
    ppm = (slope / avg_price) * 10000.0
    ratio = ppm / max(1e-6, threshold_ppm)
    ratio = float(np.clip(ratio, -1.0, 1.0))
    return ratio * float(weight)


def _ema_rising(series: pd.Series, lookback: int = 3) -> bool:
    s = pd.Series(series).dropna()
    if len(s) < lookback:
        return False
    return bool(s.iloc[-1] > s.iloc[-lookback])


def compute_short_trend(df: pd.DataFrame) -> Dict:
    if df is None or df.empty:
        return {"score": 0.0, "regime": "n/a"}
    close = pd.to_numeric(df['close'], errors='coerce')
    high = pd.to_numeric(df.get('high', close), errors='coerce')
    low = pd.to_numeric(df.get('low', close), errors='coerce')
    ema20 = compute_ema(close, 20)
    ema50 = compute_ema(close, 50)
    ma_align = 30.0 if float(ema20.iloc[-1]) > float(ema50.iloc[-1]) else -30.0 if float(ema20.iloc[-1]) < float(ema50.iloc[-1]) else 0.0
    slope = _scale_slope_to_weight(ema20, lookback=min(20, len(ema20)), weight=25.0, threshold_ppm=8.0)
    if float(close.iloc[-1]) > float(ema20.iloc[-1]) and _ema_rising(ema20, 3):
        price_pos = 25.0
    elif float(close.iloc[-1]) < float(ema20.iloc[-1]) and not _ema_rising(ema20, 3):
        price_pos = -25.0
    else:
        price_pos = 0.0

    # Structure via simple 3-bar fractal swings: HH/HL -> +20; LH/LL -> -20; else 0
    def _detect_structure(high_s: pd.Series, low_s: pd.Series, window: int = 3, max_lookback: int = 80) -> int:
        h = pd.Series(high_s).astype(float)
        l = pd.Series(low_s).astype(float)
        if len(h) < window * 2 + 1:
            return 0
        start = max(0, len(h) - max_lookback)
        idx = range(start + window, len(h) - window)
        swing_highs = []
        swing_lows = []
        for i in idx:
            if h.iloc[i] == h.iloc[i - window:i + window + 1].max():
                swing_highs.append((i, h.iloc[i]))
            if l.iloc[i] == l.iloc[i - window:i + window + 1].min():
                swing_lows.append((i, l.iloc[i]))
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return 0
        h1, h2 = swing_highs[-1][1], swing_highs[-2][1]
        l1, l2 = swing_lows[-1][1], swing_lows[-2][1]
        if (h1 > h2) and (l1 > l2):
            return +1
        if (h1 < h2) and (l1 < l2):
            return -1
        return 0

    structure_flag = _detect_structure(high, low, window=3, max_lookback=80)
    structure = 20.0 if structure_flag > 0 else -20.0 if structure_flag < 0 else 0.0

    score = float(np.clip(ma_align + slope + price_pos + structure, -100.0, 100.0))
    regime = "Uptrend" if score >= 20 else "Downtrend" if score <= -20 else "Range"
    return {"score": round(score, 1), "regime": regime}


def compute_long_trend(df: pd.DataFrame) -> Dict:
    if df is None or df.empty:
        return {"score": 0.0, "regime": "n/a"}
    close = pd.to_numeric(df['close'], errors='coerce')
    ema50 = compute_ema(close, 50)
    sma200 = compute_sma(close, 200)
    ma_align = 30.0 if float(ema50.iloc[-1]) > float(sma200.iloc[-1]) else -30.0 if float(ema50.iloc[-1]) < float(sma200.iloc[-1]) else 0.0
    slope = _scale_slope_to_weight(sma200, lookback=min(100, len(sma200)), weight=25.0, threshold_ppm=1.5)
    price_pos = 35.0 if float(close.iloc[-1]) > float(sma200.iloc[-1]) else -35.0 if float(close.iloc[-1]) < float(sma200.iloc[-1]) else 0.0
    ema50_conf = 10.0 if _ema_rising(ema50, 5) else -10.0
    score = float(np.clip(ma_align + slope + price_pos + ema50_conf, -100.0, 100.0))
    regime = "Uptrend" if score >= 20 else "Downtrend" if score <= -20 else "Range"
    return {"score": round(score, 1), "regime": regime}


def _rsi_core_score(rsi_value: float) -> float:
    r = float(rsi_value)
    if r <= 20:
        return 60.0
    if r >= 80:
        return -60.0
    if 20 < r <= 40:
        return 60.0 - (r - 20.0) * (40.0 / 20.0)
    if 40 < r < 60:
        return 20.0 - (r - 40.0) * (40.0 / 20.0)
    if 60 <= r < 80:
        return -20.0 - (r - 60.0) * (40.0 / 20.0)
    return 0.0


def compute_obos(df: pd.DataFrame, rsi_len: int = 14, macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9,
                 lts_score: Optional[float] = None, pullback_enabled: bool = True, pull_mode: str = 'percent', pull_threshold: float = 5.0,
                 pull_atr_mult: float = 3.0, pull_scale: str = 'daily') -> Dict:
    """Mirror the Streamlit page OB/OS scoring so CLI utilities stay consistent."""
    if df is None or df.empty:
        return {"score": 0.0, "regime": "Neutral", "components": {}, "labels": []}

    close = pd.to_numeric(df['close'], errors='coerce')
    rsi = compute_rsi(close, rsi_len)
    rsi_last = float(rsi.iloc[-1]) if len(rsi) else 50.0
    macd_line, macd_sig, macd_hist = compute_macd(close, macd_fast, macd_slow, macd_signal)
    labels = []

    rsi_core = _rsi_core_score(rsi_last)
    macd_shift = 0.0
    hist_rising = len(macd_hist) >= 4 and all(macd_hist.iloc[-i] > macd_hist.iloc[-i-1] for i in range(1, 4))
    hist_falling = len(macd_hist) >= 4 and all(macd_hist.iloc[-i] < macd_hist.iloc[-i-1] for i in range(1, 4))
    recent_cross_up = any(macd_line.iloc[-i] > macd_sig.iloc[-i] and macd_line.iloc[-i-1] <= macd_sig.iloc[-i-1] for i in range(1, min(4, len(macd_line))))
    recent_cross_dn = any(macd_line.iloc[-i] < macd_sig.iloc[-i] and macd_line.iloc[-i-1] >= macd_sig.iloc[-i-1] for i in range(1, min(4, len(macd_line))))
    if (rsi_last < 40 and (hist_rising or recent_cross_up)):
        macd_shift = 20.0
        labels.append("MACD bullish shift")
    elif (rsi_last > 60 and (hist_falling or recent_cross_dn)):
        macd_shift = -20.0
        labels.append("MACD bearish shift")

    pull_score = 0.0
    pull_detail = None
    pull_overlay = None
    if pullback_enabled:
        pb = _pullback_component(
            df,
            lts_score if lts_score is not None else 0.0,
            mode=pull_mode,
            threshold=pull_threshold,
            atr_mult=pull_atr_mult,
            detect_scale=pull_scale
        )
        pull_score = float(pb.get('score', 0.0))
        pull_detail = pb.get('details')
        pull_overlay = pb.get('overlay')

    score = float(np.clip(rsi_core + macd_shift + pull_score, -100.0, 100.0))
    regime = "Bullish OS" if score >= 40 else "Bearish OB" if score <= -40 else "Neutral"
    components = {"rsi_core": round(rsi_core, 1), "macd_shift": macd_shift, "rsi": round(rsi_last, 1)}
    if pullback_enabled:
        components.update({"pullback": pull_score})
    return {
        "score": round(score, 1),
        "regime": regime,
        "components": components,
        "labels": labels,
        "pull_detail": pull_detail,
        "pull_overlay": pull_overlay,
    }


# --- Pullback/Extension logic (trimmed & aligned with page) ---
def _zigzag_swings(close: pd.Series, high: pd.Series, low: pd.Series, mode: str = 'percent', threshold: float = 5.0,
                   atr_series: Optional[pd.Series] = None, atr_mult: float = 3.0, max_lookback: int = 250,
                   min_swing_bars: int = 5):
    c = pd.Series(close)
    h = pd.Series(high)
    l = pd.Series(low)
    n = len(c)
    if n < 5:
        return []
    start = max(0, n - max_lookback)
    pivots = []
    idx0 = start
    last_pivot_idx = idx0
    curr_trend = 0
    extreme_idx = idx0
    extreme_high = h.iloc[idx0]
    extreme_low = l.iloc[idx0]

    def thresh_at(i_ref: int, price_ref: float) -> float:
        if mode == 'percent':
            return abs(price_ref) * (threshold / 100.0)
        a = atr_series.iloc[i_ref] if atr_series is not None else 0.0
        return a * atr_mult

    for i in range(start + 1, n):
        if curr_trend >= 0:
            if h.iloc[i] >= extreme_high:
                extreme_high = h.iloc[i]
                extreme_idx = i
            dd = extreme_high - l.iloc[i]
            if dd >= thresh_at(extreme_idx, extreme_high) and (i - last_pivot_idx) >= min_swing_bars:
                pivots.append({'idx': int(extreme_idx), 'price': float(extreme_high), 'type': 'H', 'confirmed': True})
                last_pivot_idx = extreme_idx
                curr_trend = -1
                extreme_idx = i
                extreme_low = l.iloc[i]
        if curr_trend <= 0:
            if l.iloc[i] <= extreme_low:
                extreme_low = l.iloc[i]
                extreme_idx = i
            bu = h.iloc[i] - extreme_low
            if bu >= thresh_at(extreme_idx, extreme_low) and (i - last_pivot_idx) >= min_swing_bars:
                pivots.append({'idx': int(extreme_idx), 'price': float(extreme_low), 'type': 'L', 'confirmed': True})
                last_pivot_idx = extreme_idx
                curr_trend = +1
                extreme_idx = i
                extreme_high = h.iloc[i]

    if curr_trend >= 0:
        pivots.append({'idx': int(extreme_idx), 'price': float(extreme_high), 'type': 'H', 'confirmed': False})
    else:
        pivots.append({'idx': int(extreme_idx), 'price': float(extreme_low), 'type': 'L', 'confirmed': False})

    pivots = sorted({p['idx']: p for p in pivots}.values(), key=lambda x: x['idx'])
    return pivots


def _auto_pull_params(df: pd.DataFrame, lts_score: float) -> dict:
    """Auto-select swing detection parameters (shared with Streamlit page)."""
    d = df.copy()
    d['date'] = pd.to_datetime(d['tradingDate'])
    close = pd.to_numeric(d['close'], errors='coerce')
    high = pd.to_numeric(d.get('high', close), errors='coerce')
    low = pd.to_numeric(d.get('low', close), errors='coerce')
    atr = compute_atr(high, low, close)
    atr_pct = (atr / close.replace(0, np.nan)).fillna(0) * 100.0
    atr_med = float(atr_pct.iloc[-60:].median()) if len(atr_pct) >= 10 else float(atr_pct.median())

    candidates = [4.0, 5.0, 6.0, 7.0]
    best = None
    best_score = -1

    def eval_params(scale: str, mode: str, thr: float, atrx: float) -> tuple:
        if scale == 'weekly':
            dw = d.set_index('date').sort_index().resample('W-FRI').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna(how='any').reset_index()
            c = pd.to_numeric(dw['close'], errors='coerce'); h = pd.to_numeric(dw['high'], errors='coerce'); l = pd.to_numeric(dw['low'], errors='coerce')
            a = compute_atr(h, l, c)
            piv = _zigzag_swings(c, h, l, mode=mode, threshold=thr, atr_series=a, atr_mult=atrx, max_lookback=250, min_swing_bars=2)
        else:
            c = close; h = high; l = low; a = atr
            piv = _zigzag_swings(c, h, l, mode=mode, threshold=thr, atr_series=a, atr_mult=atrx, max_lookback=250, min_swing_bars=5)
        up = dn = 0
        for i in range(len(piv) - 1):
            a_p, b_p = piv[i], piv[i + 1]
            if not (a_p.get('confirmed') and b_p.get('confirmed')):
                continue
            if a_p['type'] == 'L' and b_p['type'] == 'H':
                up += 1
            elif a_p['type'] == 'H' and b_p['type'] == 'L':
                dn += 1
        legs = up + dn
        return legs, up, dn

    base_mode = 'percent'
    atr_mult = 3.0
    if atr_med >= 3.0:
        base_mode = 'atrx'
        atr_mult = 3.0 if atr_med < 4.5 else 3.5

    for thr in candidates:
        legs, up, dn = eval_params('daily', 'percent' if base_mode == 'percent' else 'atrx', thr, atr_mult)
        if 3 <= legs <= 8:
            score = 10 - abs(5 - legs)
        else:
            score = max(0, 8 - abs(5 - legs))
        if score > best_score:
            best_score = score
            best = {'mode': 'percent' if base_mode == 'percent' else 'atrx', 'threshold': thr, 'atr_mult': atr_mult, 'scale': 'daily', 'legs': legs}

    if best is None or best['legs'] < 2 or best['legs'] > 12:
        for thr in candidates:
            legs, up, dn = eval_params('weekly', 'percent' if base_mode == 'percent' else 'atrx', thr, atr_mult)
            if 2 <= legs <= 8:
                score = 10 - abs(4 - legs)
            else:
                score = max(0, 8 - abs(4 - legs))
            if score > best_score:
                best_score = score
                best = {'mode': 'percent' if base_mode == 'percent' else 'atrx', 'threshold': thr, 'atr_mult': atr_mult, 'scale': 'weekly', 'legs': legs}

    if best is None:
        best = {'mode': 'percent', 'threshold': 5.0, 'atr_mult': 3.0, 'scale': 'daily', 'legs': 0}
    best['debug'] = {'atr_med_pct': atr_med, 'score': best_score}
    return best


def _pullback_component(df: pd.DataFrame, lts_score: float, mode: str = 'percent', threshold: float = 5.0,
                        atr_mult: float = 3.0, leg_mode: str = 'auto', detect_scale: str = 'daily') -> dict:
    if df is None or df.empty or len(df) < 20:
        return {"score": 0.0, "details": "Insufficient data", "overlay": None}

    d = df.copy()
    d['date'] = pd.to_datetime(d['tradingDate'])
    close = pd.to_numeric(d['close'], errors='coerce')
    high = pd.to_numeric(d.get('high', close), errors='coerce')
    low = pd.to_numeric(d.get('low', close), errors='coerce')
    ema20 = compute_ema(close, 20)
    ema50 = compute_ema(close, 50)
    atr = compute_atr(high, low, close)
    atr_pct = (atr / close.replace(0, np.nan)).fillna(0) * 100.0

    use_weekly = (detect_scale.lower() == 'weekly')
    if use_weekly:
        dw = d.set_index('date').sort_index().resample('W-FRI').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna(how='any').reset_index()
        wc = pd.to_numeric(dw['close'], errors='coerce')
        wh = pd.to_numeric(dw['high'], errors='coerce')
        wl = pd.to_numeric(dw['low'], errors='coerce')
        w_atr = compute_atr(wh, wl, wc)
        swings = _zigzag_swings(wc, wh, wl, mode=mode, threshold=threshold, atr_series=w_atr, atr_mult=atr_mult, max_lookback=250, min_swing_bars=2)
        date_index = dw['date']

        def map_idx(w_idx: int) -> int:
            wdt = date_index.iloc[w_idx]
            mask = d['date'] <= wdt
            if not mask.any():
                return 0
            return int(mask[mask].index[-1])
    else:
        swings = _zigzag_swings(close, high, low, mode=mode, threshold=threshold, atr_series=atr, atr_mult=atr_mult, max_lookback=250, min_swing_bars=5)

    if len(swings) < 2:
        return {"score": 0.0, "details": "Not enough swings to determine last leg", "overlay": None}

    up_legs = []
    dn_legs = []
    for i in range(len(swings) - 1):
        a, b = swings[i], swings[i + 1]
        if not (a.get('confirmed') and b.get('confirmed')):
            continue
        if a['type'] == 'L' and b['type'] == 'H':
            if use_weekly:
                L_idx = map_idx(a['idx'])
                H_idx = map_idx(b['idx'])
                Lp = float(close.iloc[L_idx]); Hp = float(close.iloc[H_idx])
            else:
                L_idx, Lp = a['idx'], float(a['price'])
                H_idx, Hp = b['idx'], float(b['price'])
            move_pct = (float(close.iloc[H_idx]) / max(1e-9, float(close.iloc[L_idx])) - 1.0) * 100.0
            bars = max(1, H_idx - L_idx)
            up_legs.append(('up', L_idx, Lp, H_idx, Hp, move_pct, bars))
        elif a['type'] == 'H' and b['type'] == 'L':
            if use_weekly:
                H_idx = map_idx(a['idx'])
                L_idx = map_idx(b['idx'])
                Hp = float(close.iloc[H_idx]); Lp = float(close.iloc[L_idx])
            else:
                H_idx, Hp = a['idx'], float(a['price'])
                L_idx, Lp = b['idx'], float(b['price'])
            move_pct = (1.0 - float(close.iloc[L_idx]) / max(1e-9, float(close.iloc[H_idx]))) * 100.0
            bars = max(1, L_idx - H_idx)
            dn_legs.append(('down', H_idx, Hp, L_idx, Lp, move_pct, bars))

    def last_up_leg():
        if not up_legs:
            return None
        leg = up_legs[-1]
        return (leg[0], leg[1], leg[2], leg[3], leg[4])

    def last_down_leg():
        if not dn_legs:
            return None
        leg = dn_legs[-1]
        return (leg[0], leg[1], leg[2], leg[3], leg[4])

    up_leg = last_up_leg()
    dn_leg = last_down_leg()
    if up_leg is None and dn_leg is None:
        return {"score": 0.0, "details": "No valid legs found", "overlay": None}

    leg_reason = "latest"
    chosen = None
    if leg_mode == 'up' and up_leg is not None:
        chosen = up_leg; leg_reason = 'forced_up'
    elif leg_mode == 'down' and dn_leg is not None:
        chosen = dn_leg; leg_reason = 'forced_down'
    elif leg_mode == 'auto':
        min_pct = 8.0
        min_bars = 6
        if lts_score >= 20 and up_legs:
            candidates = [leg for leg in up_legs if leg[5] >= min_pct and leg[6] >= min_bars]
            if candidates:
                leg = candidates[-1]
                chosen = ('up', leg[1], leg[2], leg[3], leg[4]); leg_reason = 'dominant_up'
            else:
                leg = max(up_legs, key=lambda x: x[5])
                chosen = ('up', leg[1], leg[2], leg[3], leg[4]); leg_reason = 'max_up'
        elif lts_score <= -20 and dn_legs:
            candidates = [leg for leg in dn_legs if leg[5] >= min_pct and leg[6] >= min_bars]
            if candidates:
                leg = candidates[-1]
                chosen = ('down', leg[1], leg[2], leg[3], leg[4]); leg_reason = 'dominant_down'
            else:
                leg = max(dn_legs, key=lambda x: x[5])
                chosen = ('down', leg[1], leg[2], leg[3], leg[4]); leg_reason = 'max_down'
        else:
            if up_legs and dn_legs:
                chosen = ('up', up_legs[-1][1], up_legs[-1][2], up_legs[-1][3], up_legs[-1][4]) if up_legs[-1][3] >= dn_legs[-1][3] else ('down', dn_legs[-1][1], dn_legs[-1][2], dn_legs[-1][3], dn_legs[-1][4])
            else:
                if up_legs:
                    leg = up_legs[-1]; chosen = ('up', leg[1], leg[2], leg[3], leg[4])
                else:
                    leg = dn_legs[-1]; chosen = ('down', leg[1], leg[2], leg[3], leg[4])
            leg_reason = 'latest_neutral'
        if chosen and leg_reason.startswith('regime'):
            recent = close.diff().iloc[-5:]
            ema20_last = float(ema20.iloc[-1])
            if lts_score >= 20:
                if (recent.lt(0).sum() >= 3) and (float(close.iloc[-1]) <= ema20_last) and up_leg is not None:
                    chosen = up_leg; leg_reason = 'override_pullback_up'
            elif lts_score <= -20:
                if (recent.gt(0).sum() >= 3) and (float(close.iloc[-1]) >= ema20_last) and dn_leg is not None:
                    chosen = dn_leg; leg_reason = 'override_bounce_down'
    else:
        if up_leg and dn_leg:
            chosen = up_leg if up_leg[3] >= dn_leg[3] else dn_leg
        else:
            chosen = up_leg or dn_leg

    direction, P0_idx, P0, P1_idx, P1 = chosen

    if direction == 'up':
        move_pct = (float(close.iloc[P1_idx]) / max(1e-9, float(close.iloc[P0_idx])) - 1.0) * 100.0
    else:
        move_pct = (1.0 - float(close.iloc[P1_idx]) / max(1e-9, float(close.iloc[P0_idx]))) * 100.0
    bars_in_leg = max(1, P1_idx - P0_idx)
    curr = float(close.iloc[-1])
    bars_since = max(0, len(close) - 1 - P1_idx)

    if direction == 'up':
        denom = max(1e-9, (P1 - P0))
        retr = float((P1 - curr) / denom)
        retr = float(np.clip(retr, 0.0, 1.5))
        base_points = (
            2 if retr < 0.236 else
            12 if retr < 0.382 else
            18 if retr < 0.5 else
            20 if retr < 0.618 else
            14 if retr < 0.786 else
            6
        )
        fib_prices = {
            '23.6%': P1 - 0.236 * (P1 - P0),
            '38.2%': P1 - 0.382 * (P1 - P0),
            '50%': P1 - 0.5 * (P1 - P0),
            '61.8%': P1 - 0.618 * (P1 - P0),
            '78.6%': P1 - 0.786 * (P1 - P0),
        }
    else:
        denom = max(1e-9, (P0 - P1))
        ext = float((curr - P1) / denom)
        ext = float(np.clip(ext, 0.0, 1.5))
        base_points = -(
            2 if ext < 0.236 else
            12 if ext < 0.382 else
            18 if ext < 0.5 else
            20 if ext < 0.618 else
            14 if ext < 0.786 else
            6
        )
        fib_prices = {
            '23.6%': P1 + 0.236 * (P0 - P1),
            '38.2%': P1 + 0.382 * (P0 - P1),
            '50%': P1 + 0.5 * (P0 - P1),
            '61.8%': P1 + 0.618 * (P0 - P1),
            '78.6%': P1 + 0.786 * (P0 - P1),
        }

    if lts_score >= 20:
        regime_scale = 1.0
    elif lts_score <= -20:
        regime_scale = 1.0
    else:
        regime_scale = 0.5

    ema50_rising = _ema_rising(ema50, 5)
    guard_scale = 1.0
    if direction == 'up':
        if (curr < float(ema50.iloc[-1])) and (not ema50_rising):
            guard_scale = 0.6
    else:
        if (curr > float(ema50.iloc[-1])) and ema50_rising:
            guard_scale = 0.6

    if bars_since <= 30:
        time_scale = 1.0
    elif bars_since >= 60:
        time_scale = 0.0
    else:
        time_scale = max(0.0, 1.0 - (bars_since - 30) / 30.0)

    dist_atr = 0.0
    if float(atr.iloc[-1]) > 0:
        dist_atr = abs((curr - float(ema20.iloc[-1])) / float(atr.iloc[-1]))
    stretch_pts = 0.0
    if direction == 'up' and curr < float(ema20.iloc[-1]) and dist_atr > 1.0:
        stretch_pts = min(6.0, 3.0 * min(2.0, dist_atr - 1.0))
    elif direction == 'down' and curr > float(ema20.iloc[-1]) and dist_atr > 1.0:
        stretch_pts = -min(6.0, 3.0 * min(2.0, dist_atr - 1.0))

    pullback_vol_adj = 0.0
    if bars_since >= 3:
        seg_vol = d['volume'].iloc[P1_idx + 1:]
        seg_mean = float(seg_vol.mean()) if len(seg_vol) else 0.0
        if direction == 'up':
            leg_df = d.iloc[P0_idx:P1_idx + 1]
            up_vol = leg_df.loc[leg_df['close'] > leg_df['close'].shift(1), 'volume']
            base = float(up_vol.mean()) if len(up_vol) else float(leg_df['volume'].mean())
            if base > 0:
                ratio = seg_mean / base
                if ratio < 0.9:
                    pullback_vol_adj = +4.0
                elif ratio > 1.1:
                    pullback_vol_adj = -6.0
        else:
            leg_df = d.iloc[P0_idx:P1_idx + 1]
            down_vol = leg_df.loc[leg_df['close'] < leg_df['close'].shift(1), 'volume']
            base = float(down_vol.mean()) if len(down_vol) else float(leg_df['volume'].mean())
            if base > 0:
                ratio = seg_mean / base
                if ratio < 0.9:
                    pullback_vol_adj = -4.0
                elif ratio > 1.1:
                    pullback_vol_adj = +6.0

    raw_component = base_points * regime_scale
    component = (raw_component * guard_scale * time_scale) + stretch_pts + pullback_vol_adj
    component = float(np.clip(component, -30.0, 30.0))

    overlay = {
        'direction': direction,
        'start_idx': int(P0_idx),
        'end_idx': int(P1_idx),
        'start_date': d['date'].iloc[P0_idx],
        'end_date': d['date'].iloc[P1_idx],
        'start_price': float(P0),
        'end_price': float(P1),
        'fib_prices': {k: float(v) for k, v in fib_prices.items()},
        'leg_mode': leg_mode,
        'leg_reason': leg_reason,
        'lts_score': float(lts_score),
        'atr_pct': float(atr_pct.iloc[-1]) if len(atr_pct) else 0.0,
    }

    if direction == 'up':
        retr = float(np.clip((P1 - curr) / max(1e-9, (P1 - P0)), 0.0, 1.5))
        retr_pct = retr * 100.0
        zone = '(<23.6%)' if retr < 0.236 else '(23.6–38.2%)' if retr < 0.382 else '(38.2–50%)' if retr < 0.5 else '(50–61.8%)' if retr < 0.618 else '(61.8–78.6%)' if retr < 0.786 else '(>78.6%)'
        detail = f"Regime-aware ({leg_reason}): Last up-leg +{move_pct:.1f}% over {bars_in_leg} bars. Retracement {retr_pct:.1f}% {zone} → base {base_points:+.0f}. Guard {guard_scale:.2f}, time {time_scale:.2f}, stretch {stretch_pts:+.1f}, volume {pullback_vol_adj:+.1f}."
    else:
        ext = float(np.clip((curr - P1) / max(1e-9, (P0 - P1)), 0.0, 1.5))
        ext_pct = ext * 100.0
        zone = '(<23.6%)' if ext < 0.236 else '(23.6–38.2%)' if ext < 0.382 else '(38.2–50%)' if ext < 0.5 else '(50–61.8%)' if ext < 0.618 else '(61.8–78.6%)' if ext < 0.786 else '(>78.6%)'
        detail = f"Regime-aware ({leg_reason}): Last down-leg -{move_pct:.1f}% over {bars_in_leg} bars. Bounce extension {ext_pct:.1f}% {zone} → base {base_points:+.0f}. Guard {guard_scale:.2f}, time {time_scale:.2f}, stretch {stretch_pts:+.1f}, volume {pullback_vol_adj:+.1f}."

    return {"score": round(component, 1), "details": detail, "overlay": overlay}


def compute_obos_with_pullback(df: pd.DataFrame, lts_score: float, rsi_len: int = 14,
                                macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9) -> Dict:
    params = _auto_pull_params(df, lts_score)
    return compute_obos(
        df,
        rsi_len=rsi_len,
        macd_fast=macd_fast,
        macd_slow=macd_slow,
        macd_signal=macd_signal,
        lts_score=lts_score,
        pullback_enabled=True,
        pull_mode=params['mode'],
        pull_threshold=params['threshold'],
        pull_atr_mult=params['atr_mult'],
        pull_scale=params['scale'],
    )


def analyze_tickers(tickers, days: int = 365) -> Dict:
    results = {}
    for t in tickers:
        try:
            df_calc = get_cached_stock_data(t, max(days, 330))
            if df_calc is None or df_calc.empty:
                results[t] = {"status": "failed", "error": "no_data"}
                continue
            sts = compute_short_trend(df_calc)
            lts = compute_long_trend(df_calc)
            obos = compute_obos_with_pullback(df_calc, lts_score=lts['score'])
            # Brief implications
            trend_note = (
                "Strong uptrend" if lts['score'] >= 60 else
                "Uptrend" if lts['score'] >= 20 else
                "Range" if lts['score'] > -20 else
                "Downtrend" if lts['score'] > -60 else
                "Strong downtrend"
            )
            obos_note = (
                "Bullish pullback" if obos['score'] >= 40 else
                "Neutral" if -40 < obos['score'] < 40 else
                "Bearish extension"
            )
            implication = f"{trend_note}; STS {sts['score']:+.0f}. OB/OS: {obos_note} ({obos['score']:+.0f})."
            results[t] = {
                "sts": sts['score'],
                "lts": lts['score'],
                "obos": obos['score'],
                "sts_regime": sts['regime'],
                "lts_regime": lts['regime'],
                "obos_regime": obos['regime'],
                "implication": implication,
                "status": "success"
            }
        except Exception as e:
            results[t] = {"status": "failed", "error": str(e)}
    return {"results": results, "requested": len(tickers), "status": "success"}
