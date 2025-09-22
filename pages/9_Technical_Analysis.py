#%%
"""
Technical Analysis Dashboard
User selects a banking stock; renders candlestick with MAs, volume, RSI, and a simple rating score.

Design:
- Flexible time horizons (no hardcoded dates)
- Vectorized pandas ops for indicators
- Reuses TCBS data fetcher from utilities.stock_candle
"""

import os
import sys
from typing import List
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Streamlit config
st.set_page_config(page_title="Technical Analysis", page_icon="📉", layout="wide")

# Project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

try:
    from utilities.style_utils import apply_google_font
    from utilities.sidebar_style import apply_sidebar_style
    apply_google_font()
    apply_sidebar_style()
except Exception:
    pass

from utilities.stock_candle import get_cached_stock_data


# -------- Trend & OB/OS scoring per spec --------
def _linreg_slope(series: pd.Series, lookback: int) -> float:
    """Return least-squares slope per bar over the last N points (float)."""
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
    """
    Map slope to [-weight, weight] using a per-bar slope normalized by price level.
    threshold_ppm defines how many basis points per bar correspond to full weight.
    """
    slope = _linreg_slope(series, lookback)
    avg_price = float(pd.Series(series).iloc[-lookback:].mean()) if len(series) >= lookback else float(pd.Series(series).iloc[-1])
    if avg_price <= 0:
        return 0.0
    # per-bar change as parts-per-10k (basis points) to be scale-invariant
    ppm = (slope / avg_price) * 10000.0
    ratio = ppm / max(1e-6, threshold_ppm)
    ratio = float(np.clip(ratio, -1.0, 1.0))
    return ratio * float(weight)


def _ema_rising(series: pd.Series, lookback: int = 3) -> bool:
    s = pd.Series(series).dropna()
    if len(s) < lookback:
        return False
    return bool(s.iloc[-1] > s.iloc[-lookback])


def _auto_pull_params(df: pd.DataFrame, lts_score: float) -> dict:
    """Auto-select swing detection parameters based on volatility and pivot density.
    Returns dict(mode, threshold, atr_mult, scale, debug)
    """
    d = df.copy()
    d['date'] = pd.to_datetime(d['tradingDate'])
    close = pd.to_numeric(d['close'], errors='coerce')
    high = pd.to_numeric(d.get('high', close), errors='coerce')
    low = pd.to_numeric(d.get('low', close), errors='coerce')
    atr = compute_atr(high, low, close)
    atr_pct = (atr / close.replace(0, np.nan)).fillna(0) * 100.0
    atr_med = float(atr_pct.iloc[-60:].median()) if len(atr_pct) >= 10 else float(atr_pct.median())

    # Candidate thresholds to target 3-10 legs window
    candidates = [4.0, 5.0, 6.0, 7.0]
    best = None
    best_score = -1

    def eval_params(scale: str, mode: str, thr: float, atrx: float) -> tuple:
        # Build series for the given scale
        if scale == 'weekly':
            dw = d.set_index('date').sort_index().resample('W-FRI').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna(how='any').reset_index()
            c = pd.to_numeric(dw['close'], errors='coerce'); h = pd.to_numeric(dw['high'], errors='coerce'); l = pd.to_numeric(dw['low'], errors='coerce')
            a = compute_atr(h, l, c)
            piv = _zigzag_swings(c, h, l, mode=mode, threshold=thr, atr_series=a, atr_mult=atrx, max_lookback=250, min_swing_bars=2)
        else:
            c = close; h = high; l = low; a = atr
            piv = _zigzag_swings(c, h, l, mode=mode, threshold=thr, atr_series=a, atr_mult=atrx, max_lookback=250, min_swing_bars=5)
        # Count confirmed legs
        up = dn = 0
        for i in range(len(piv)-1):
            a, b = piv[i], piv[i+1]
            if not (a.get('confirmed') and b.get('confirmed')):
                continue
            if a['type']=='L' and b['type']=='H':
                # quick size/duration checks could be added
                up += 1
            elif a['type']=='H' and b['type']=='L':
                dn += 1
        legs = up + dn
        return legs, up, dn

    # Decide base mode by volatility
    base_mode = 'percent'
    atr_mult = 3.0
    if atr_med >= 3.0:
        base_mode = 'atrx'
        # more volatile -> slightly higher multiple to avoid noise
        atr_mult = 3.0 if atr_med < 4.5 else 3.5

    # Evaluate daily first
    for thr in candidates:
        legs, up, dn = eval_params('daily', 'percent' if base_mode=='percent' else 'atrx', thr, atr_mult)
        # Score: prefer 3-8 legs, light bias to 4-6
        if 3 <= legs <= 8:
            score = 10 - abs(5 - legs)
        else:
            score = max(0, 8 - abs(5 - legs))
        if score > best_score:
            best_score = score
            best = {'mode': 'percent' if base_mode=='percent' else 'atrx', 'threshold': thr, 'atr_mult': atr_mult, 'scale': 'daily', 'legs': legs}

    # If too noisy or too few legs, try weekly
    if best is None or best['legs'] < 2 or best['legs'] > 12:
        for thr in candidates:
            legs, up, dn = eval_params('weekly', 'percent' if base_mode=='percent' else 'atrx', thr, atr_mult)
            if 2 <= legs <= 8:
                score = 10 - abs(4 - legs)
            else:
                score = max(0, 8 - abs(4 - legs))
            if score > best_score:
                best_score = score
                best = {'mode': 'percent' if base_mode=='percent' else 'atrx', 'threshold': thr, 'atr_mult': atr_mult, 'scale': 'weekly', 'legs': legs}

    if best is None:
        best = {'mode': 'percent', 'threshold': 5.0, 'atr_mult': 3.0, 'scale': 'daily', 'legs': 0}
    best['debug'] = {'atr_med_pct': atr_med, 'score': best_score}
    return best


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    h = pd.to_numeric(high, errors='coerce').fillna(method='ffill')
    l = pd.to_numeric(low, errors='coerce').fillna(method='ffill')
    c = pd.to_numeric(close, errors='coerce').fillna(method='ffill')
    prev_close = c.shift(1)
    tr = np.maximum(h - l, np.maximum((h - prev_close).abs(), (l - prev_close).abs()))
    atr = tr.ewm(alpha=1/length, adjust=False, min_periods=1).mean()
    return atr


def _zigzag_swings(close: pd.Series, high: pd.Series, low: pd.Series, mode: str = 'percent', threshold: float = 5.0,
                   atr_series: pd.Series | None = None, atr_mult: float = 3.0, max_lookback: int = 250,
                   min_swing_bars: int = 5):
    """
    Lightweight ZigZag swing detection by percent or ATR multiple.
    Returns list of dicts: {idx, price, type: 'H'/'L'} limited to last max_lookback bars.
    """
    c = pd.to_numeric(close, errors='coerce')
    h = pd.to_numeric(high, errors='coerce')
    l = pd.to_numeric(low, errors='coerce')
    n = len(c)
    if n < 5:
        return []
    start = max(0, n - max_lookback)
    pivots = []
    # Initialize using first bar in window
    idx0 = start
    last_pivot_idx = idx0
    curr_trend = 0  # 0 unknown, +1 up, -1 down
    extreme_idx = idx0
    extreme_price_high = h.iloc[idx0]
    extreme_price_low = l.iloc[idx0]

    def thresh_at(i_ref: int, price_ref: float) -> float:
        if mode == 'percent':
            return abs(price_ref) * (threshold / 100.0)
        a = atr_series.iloc[i_ref] if atr_series is not None else 0.0
        return a * atr_mult

    for i in range(start + 1, n):
        # Update extremes within current trend
        if curr_trend >= 0:  # tracking upswing candidate
            if h.iloc[i] >= extreme_price_high:
                extreme_price_high = h.iloc[i]
                extreme_idx = i
            # Check reversal: drawdown from high exceeds threshold and min bars since last pivot
            dd = extreme_price_high - l.iloc[i]
            if dd >= thresh_at(extreme_idx, extreme_price_high) and (i - last_pivot_idx) >= min_swing_bars:
                # Confirm swing high at extreme_idx
                pivots.append({'idx': int(extreme_idx), 'price': float(extreme_price_high), 'type': 'H', 'confirmed': True})
                last_pivot_idx = extreme_idx
                curr_trend = -1
                # Reset extreme for downswing
                extreme_idx = i
                extreme_price_low = l.iloc[i]
        if curr_trend <= 0:  # tracking downswing candidate
            if l.iloc[i] <= extreme_price_low:
                extreme_price_low = l.iloc[i]
                extreme_idx = i
            # Check reversal: bounce from low exceeds threshold and min bars since last pivot
            bu = h.iloc[i] - extreme_price_low
            if bu >= thresh_at(extreme_idx, extreme_price_low) and (i - last_pivot_idx) >= min_swing_bars:
                # Confirm swing low at extreme_idx
                pivots.append({'idx': int(extreme_idx), 'price': float(extreme_price_low), 'type': 'L', 'confirmed': True})
                last_pivot_idx = extreme_idx
                curr_trend = +1
                # Reset extreme for upswing
                extreme_idx = i
                extreme_price_high = h.iloc[i]

    # Append the last tracked extreme as current running pivot for context
    if curr_trend >= 0:
        pivots.append({'idx': int(extreme_idx), 'price': float(extreme_price_high), 'type': 'H', 'confirmed': False})
    else:
        pivots.append({'idx': int(extreme_idx), 'price': float(extreme_price_low), 'type': 'L', 'confirmed': False})

    # Deduplicate by idx and sort
    pivots = sorted({p['idx']: p for p in pivots}.values(), key=lambda x: x['idx'])
    return pivots


def _pullback_component(df: pd.DataFrame, lts_score: float, mode: str = 'percent', threshold: float = 5.0,
                        atr_mult: float = 3.0, leg_mode: str = 'auto', detect_scale: str = 'daily') -> dict:
    """
    Compute pullback/extension score and details based on last leg using ZigZag swings.
    Returns {score, details, overlay}.
    overlay includes leg info and fib levels for charting.
    """
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
    # Optionally detect swings on weekly-aggregated data for robustness
    use_weekly = (detect_scale.lower() == 'weekly')
    if use_weekly:
        dw = d.set_index('date').sort_index().resample('W-FRI').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna(how='any').reset_index()
        wc = pd.to_numeric(dw['close'], errors='coerce')
        wh = pd.to_numeric(dw['high'], errors='coerce')
        wl = pd.to_numeric(dw['low'], errors='coerce')
        w_atr = compute_atr(wh, wl, wc)
        swings = _zigzag_swings(wc, wh, wl, mode=mode, threshold=threshold, atr_series=w_atr, atr_mult=atr_mult, max_lookback=250, min_swing_bars=2)
        date_index = dw['date']
        # helper to map weekly idx to nearest daily idx
        def map_idx(w_idx: int) -> int:
            wdt = date_index.iloc[w_idx]
            # nearest daily index <= wdt
            mask = d['date'] <= wdt
            if not mask.any():
                return 0
            return int(mask[mask].index[-1])
    else:
        swings = _zigzag_swings(close, high, low, mode=mode, threshold=threshold, atr_series=atr, atr_mult=atr_mult, max_lookback=250, min_swing_bars=5)
    if len(swings) < 2:
        return {"score": 0.0, "details": "Not enough swings to determine last leg", "overlay": None}

    # Build sequential legs from swings
    up_legs = []  # tuples: (dir, L_idx, L_price, H_idx, H_price, move_pct_close, bars)
    dn_legs = []  # tuples: (dir, H_idx, H_price, L_idx, L_price, move_pct_close, bars)
    for i in range(len(swings) - 1):
        a, b = swings[i], swings[i+1]
        # Only use confirmed pivot pairs
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
            # Use close-to-close for explanatory move percentage
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

    # Decide which leg to use
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
            # Prefer dominant up-leg: last up-leg meeting thresholds, else max pct up-leg
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
            # neutral: choose the most recent leg end
            if up_legs and dn_legs:
                chosen = ('up', up_legs[-1][1], up_legs[-1][2], up_legs[-1][3], up_legs[-1][4]) if up_legs[-1][3] >= dn_legs[-1][3] else ('down', dn_legs[-1][1], dn_legs[-1][2], dn_legs[-1][3], dn_legs[-1][4])
            else:
                if up_legs:
                    leg = up_legs[-1]; chosen = ('up', leg[1], leg[2], leg[3], leg[4])
                else:
                    leg = dn_legs[-1]; chosen = ('down', leg[1], leg[2], leg[3], leg[4])
            leg_reason = 'latest_neutral'
        # Sanity guard: override based on most recent bar behavior vs EMA20
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
        # latest
        if up_leg and dn_leg:
            chosen = up_leg if up_leg[3] >= dn_leg[3] else dn_leg
        else:
            chosen = up_leg or dn_leg

    direction, P0_idx, P0, P1_idx, P1 = chosen

    # Leg metrics (use closes for explanatory move percentage)
    if direction == 'up':
        move_pct = (float(close.iloc[P1_idx]) / max(1e-9, float(close.iloc[P0_idx])) - 1.0) * 100.0
    else:
        move_pct = (1.0 - float(close.iloc[P1_idx]) / max(1e-9, float(close.iloc[P0_idx]))) * 100.0
    bars_in_leg = max(1, P1_idx - P0_idx)
    curr = float(close.iloc[-1])
    bars_since = max(0, len(close) - 1 - P1_idx)

    # Retracement/Extension ratios
    if direction == 'up':
        denom = max(1e-9, (P1 - P0))
        retr = float((P1 - curr) / denom)
        retr = float(np.clip(retr, 0.0, 1.5))
        # Tuned weights: reward 23.6–38.2% more, reduce reward beyond 61.8%
        base_points = (
            2 if retr < 0.236 else
            12 if retr < 0.382 else
            18 if retr < 0.5 else
            20 if retr < 0.618 else
            14 if retr < 0.786 else
            6
        )
        component_sign = +1
        fib_prices = {
            '23.6%': P1 - 0.236 * (P1 - P0),
            '38.2%': P1 - 0.382 * (P1 - P0),
            '50%':   P1 - 0.5   * (P1 - P0),
            '61.8%': P1 - 0.618 * (P1 - P0),
            '78.6%': P1 - 0.786 * (P1 - P0),
        }
    else:
        denom = max(1e-9, (P0 - P1))
        ext = float((curr - P1) / denom)
        ext = float(np.clip(ext, 0.0, 1.5))
        # Mirror tuning for bounce extensions in down legs
        base_points = -(
            2 if ext < 0.236 else
            12 if ext < 0.382 else
            18 if ext < 0.5 else
            20 if ext < 0.618 else
            14 if ext < 0.786 else
            6
        )
        component_sign = -1
        fib_prices = {
            '23.6%': P1 + 0.236 * (P0 - P1),
            '38.2%': P1 + 0.382 * (P0 - P1),
            '50%':   P1 + 0.5   * (P0 - P1),
            '61.8%': P1 + 0.618 * (P0 - P1),
            '78.6%': P1 + 0.786 * (P0 - P1),
        }

    # Regime scaling
    if lts_score >= 20:
        regime_scale = 1.0
    elif lts_score <= -20:
        regime_scale = 1.0
    else:
        regime_scale = 0.5

    # Structure guard
    ema50_rising = _ema_rising(ema50, 5)
    guard_scale = 1.0
    if direction == 'up':
        if (curr < float(ema50.iloc[-1])) and (not ema50_rising):
            guard_scale = 0.6  # reduce reward
    else:
        if (curr > float(ema50.iloc[-1])) and ema50_rising:
            guard_scale = 0.6  # reduce penalty magnitude

    # Time decay: full until 30 bars, then linear to 0 by 60
    if bars_since <= 30:
        time_scale = 1.0
    elif bars_since >= 60:
        time_scale = 0.0
    else:
        time_scale = max(0.0, 1.0 - (bars_since - 30) / 30.0)

    # ATR stretch adjustment
    dist_atr = 0.0
    if float(atr.iloc[-1]) > 0:
        dist_atr = abs((curr - float(ema20.iloc[-1])) / float(atr.iloc[-1]))
    stretch_pts = 0.0
    if direction == 'up' and curr < float(ema20.iloc[-1]) and dist_atr > 1.0:
        stretch_pts = min(6.0, 3.0 * min(2.0, dist_atr - 1.0))
    elif direction == 'down' and curr > float(ema20.iloc[-1]) and dist_atr > 1.0:
        stretch_pts = -min(6.0, 3.0 * min(2.0, dist_atr - 1.0))

    # Volume context on pullback segment
    pullback_vol_adj = 0.0
    if bars_since >= 3:
        seg_vol = d['volume'].iloc[P1_idx + 1:]
        seg_mean = float(seg_vol.mean()) if len(seg_vol) else 0.0
        if direction == 'up':
            # Compare vs up-days volume during leg
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
            # Compare vs down-days volume during leg
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
    }

    # Build explanation string
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

def _detect_structure(high: pd.Series, low: pd.Series, window: int = 3, max_lookback: int = 80) -> int:
    """
    Very simple swing structure via 3-bar fractals.
    Returns +1 for HH/HL, -1 for LH/LL, 0 otherwise.
    """
    h = pd.Series(high).astype(float)
    l = pd.Series(low).astype(float)
    if len(h) < window * 2 + 1:
        return 0
    # Find fractal swing highs/lows in the last max_lookback bars
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
    # last two swings (most recent at end)
    h1, h2 = swing_highs[-1][1], swing_highs[-2][1]
    l1, l2 = swing_lows[-1][1], swing_lows[-2][1]
    if (h1 > h2) and (l1 > l2):
        return +1
    if (h1 < h2) and (l1 < l2):
        return -1
    return 0


def compute_short_trend(df: pd.DataFrame) -> dict:
    """
    Short-term trend score [-100, 100]
    Components: MA alignment (EMA20 vs EMA50), slope(EMA20), price position vs EMA20, structure(HH/HL vs LH/LL).
    Weights: +40, +30, +20, +10 respectively.
    """
    if df is None or df.empty:
        return {"score": 0, "components": {}, "regime": "n/a"}
    close = pd.to_numeric(df['close'], errors='coerce')
    high = pd.to_numeric(df.get('high', close), errors='coerce')
    low = pd.to_numeric(df.get('low', close), errors='coerce')
    ema20 = compute_ema(close, 20)
    ema50 = compute_ema(close, 50)

    # Tuned weights for VN short-term behavior (reduce MA dominance, increase structure)
    # MA alignment
    ma_align = 30.0 if float(ema20.iloc[-1]) > float(ema50.iloc[-1]) else -30.0 if float(ema20.iloc[-1]) < float(ema50.iloc[-1]) else 0.0
    # Slope of EMA20 -> tighter threshold 8 ppm per bar => full score 25
    slope = _scale_slope_to_weight(ema20, lookback=min(20, len(ema20)), weight=25.0, threshold_ppm=8.0)
    # Price position vs EMA20 and EMA20 rising/falling
    price_pos = 0.0
    if float(close.iloc[-1]) > float(ema20.iloc[-1]) and _ema_rising(ema20, 3):
        price_pos = 25.0
    elif float(close.iloc[-1]) < float(ema20.iloc[-1]) and not _ema_rising(ema20, 3):
        price_pos = -25.0
    # Structure
    structure_flag = _detect_structure(high, low, window=3, max_lookback=80)
    structure = 20.0 if structure_flag > 0 else -20.0 if structure_flag < 0 else 0.0

    score = float(np.clip(ma_align + slope + price_pos + structure, -100.0, 100.0))
    regime = "Uptrend" if score >= 20 else "Downtrend" if score <= -20 else "Range"
    return {
        "score": round(score, 1),
        "regime": regime,
        "components": {
            "ma_align": ma_align,
            "slope": round(float(slope), 1),
            "price_pos": price_pos,
            "structure": structure,
        }
    }


def compute_long_trend(df: pd.DataFrame) -> dict:
    """
    Long-term trend score [-100, 100]
    Components: MA alignment (EMA50 vs SMA200), slope(SMA200), price vs SMA200, EMA50 slope confirmation.
    Weights: +40, +30, +30, +10 respectively.
    """
    if df is None or df.empty:
        return {"score": 0, "components": {}, "regime": "n/a"}
    close = pd.to_numeric(df['close'], errors='coerce')
    ema50 = compute_ema(close, 50)
    sma200 = compute_sma(close, 200)

    # Tuned weights for VN long-term: emphasize price relative to SMA200
    # MA alignment
    ma_align = 30.0 if float(ema50.iloc[-1]) > float(sma200.iloc[-1]) else -30.0 if float(ema50.iloc[-1]) < float(sma200.iloc[-1]) else 0.0
    # Slope of SMA200 -> slightly looser threshold 1.5 ppm per bar => full 25
    slope = _scale_slope_to_weight(sma200, lookback=min(100, len(sma200)), weight=25.0, threshold_ppm=1.5)
    # Price vs SMA200
    price_pos = 35.0 if float(close.iloc[-1]) > float(sma200.iloc[-1]) else -35.0 if float(close.iloc[-1]) < float(sma200.iloc[-1]) else 0.0
    # EMA50 slope confirmation
    ema50_conf = 10.0 if _ema_rising(ema50, 5) else -10.0

    score = float(np.clip(ma_align + slope + price_pos + ema50_conf, -100.0, 100.0))
    regime = "Uptrend" if score >= 20 else "Downtrend" if score <= -20 else "Range"
    return {
        "score": round(score, 1),
        "regime": regime,
        "components": {
            "ma_align": ma_align,
            "slope": round(float(slope), 1),
            "price_pos": price_pos,
            "ema50_slope": ema50_conf,
        }
    }


def _rsi_core_score(rsi_value: float) -> float:
    """Piecewise map RSI to [-60, +60] emphasizing <20 and >80 as extremes."""
    r = float(rsi_value)
    if r <= 20:
        return 60.0
    if r >= 80:
        return -60.0
    if 20 < r <= 40:
        # 20->60 down to 40->20 (linear)
        return 60.0 - (r - 20.0) * (40.0 / 20.0)
    if 40 < r < 60:
        # 40->20 down to 60->-20
        return 20.0 - (r - 40.0) * (40.0 / 20.0)
    if 60 <= r < 80:
        # 60->-20 down to 80->-60
        return -20.0 - (r - 60.0) * (40.0 / 20.0)
    # Fallback neutral
    return 0.0


def compute_obos(df: pd.DataFrame, rsi_len: int = 14, macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9,
                 lts_score: float | None = None, pullback_enabled: bool = True, pull_mode: str = 'percent', pull_threshold: float = 5.0,
                 pull_atr_mult: float = 3.0, pull_scale: str = 'daily') -> dict:
    """
    Overbought/Oversold score [-100, 100]
    - RSI core mapped to [-70, +70]
    - MACD shift adds +/-30 when confirming turns (rising hist or recent cross)
    """
    if df is None or df.empty:
        return {"score": 0, "components": {}, "labels": []}
    close = pd.to_numeric(df['close'], errors='coerce')
    rsi = compute_rsi(close, rsi_len)
    rsi_last = float(rsi.iloc[-1]) if len(rsi) else 50.0
    macd_line, macd_sig, macd_hist = compute_macd(close, macd_fast, macd_slow, macd_signal)
    labels = []

    rsi_core = _rsi_core_score(rsi_last)
    macd_shift = 0.0
    # MACD conditions
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

    # Pullback/Extension component
    pull_score = 0.0
    pull_detail = None
    pull_overlay = None
    if pullback_enabled:
        pb = _pullback_component(df, lts_score if lts_score is not None else 0.0, mode=pull_mode, threshold=pull_threshold, atr_mult=pull_atr_mult, detect_scale=pull_scale)
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


@st.cache_data(ttl=1800)
def load_bank_tickers() -> List[str]:
    """Load bank tickers from reference file (exclude aggregate sector tickers)."""
    try:
        xls = pd.read_excel(os.path.join(project_root, 'Data', 'Bank_Type.xlsx'))
        tickers = sorted([t for t in xls['TICKER'].dropna().astype(str).unique().tolist() if len(t) == 3])
        return tickers
    except Exception:
        return []


@st.cache_data(ttl=1800)
def load_bank_groups() -> dict[str, List[str]]:
    """Return mapping of bank type/sector to constituent tickers."""
    try:
        xls = pd.read_excel(os.path.join(project_root, 'Data', 'Bank_Type.xlsx'))
        df = xls[['Type', 'TICKER']].dropna()
        df['TICKER'] = df['TICKER'].astype(str).str.strip()
        df['Type'] = df['Type'].astype(str).str.strip()
        df = df[df['TICKER'].str.len() == 3]
        groups: dict[str, List[str]] = {}
        for grp, sub in df.groupby('Type'):
            tickers = sorted(sub['TICKER'].unique().tolist())
            if tickers:
                groups[grp] = tickers
        return groups
    except Exception:
        return {}


def compute_sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=1).mean()


def compute_rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.clip(lower=0)).ewm(alpha=1/length, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/length, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_bollinger(series: pd.Series, window: int = 20, n_std: float = 2.0):
    ma = series.rolling(window=window, min_periods=1).mean()
    std = series.rolling(window=window, min_periods=1).std(ddof=0)
    upper = ma + n_std * std
    lower = ma - n_std * std
    return ma, upper, lower


def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = compute_ema(series, fast)
    ema_slow = compute_ema(series, slow)
    macd = ema_fast - ema_slow
    macd_signal = compute_ema(macd, signal)
    macd_hist = macd - macd_signal
    return macd, macd_signal, macd_hist


def compute_stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k_len: int = 14, d_len: int = 3):
    lowest_low = low.rolling(window=k_len, min_periods=1).min()
    highest_high = high.rolling(window=k_len, min_periods=1).max()
    denom = (highest_high - lowest_low).replace(0, np.nan)
    k = ((close - lowest_low) / denom) * 100
    k = k.fillna(method='bfill').fillna(50)
    d = k.rolling(window=d_len, min_periods=1).mean()
    return k.clip(0, 100), d.clip(0, 100)


# Legacy technical score functions removed in favor of STS/LTS/OBOS scoring


def render_chart(df_display: pd.DataFrame, ticker: str, ma_type: str, ma_windows: List[int], rsi_len: int,
                 show_bbands: bool, show_macd: bool, macd_fast: int, macd_slow: int, macd_signal: int,
                 show_stoch: bool, stoch_k: int, stoch_d: int, df_calc=None, pull_overlay=None, show_fib=False):
    """Render chart using display window but compute indicators on a longer calc window if provided."""
    # Prepare display frame
    dfd = df_display.copy()
    dfd['date'] = pd.to_datetime(dfd['tradingDate'])
    dfd['date_str'] = dfd['date'].dt.strftime('%Y-%m-%d')
    for c in ['open', 'high', 'low', 'close', 'volume']:
        if c in dfd.columns:
            dfd[c] = pd.to_numeric(dfd[c], errors='coerce')
    dfd = dfd.dropna(subset=['open', 'high', 'low', 'close']).reset_index(drop=True)
    dfd['x'] = dfd['date_str']

    # Choose calc frame (longer history) for indicators
    dfc = df_calc.copy() if df_calc is not None else dfd.copy()
    dfc['date'] = pd.to_datetime(dfc['tradingDate'])
    for c in ['open', 'high', 'low', 'close', 'volume']:
        if c in dfc.columns:
            dfc[c] = pd.to_numeric(dfc[c], errors='coerce')
    dfc = dfc.dropna(subset=['open', 'high', 'low', 'close']).reset_index(drop=True)

    # Compute indicators on calc frame
    ma_func = compute_sma if ma_type == 'SMA' else compute_ema
    ind_cols = {}
    for w in ma_windows:
        col = f'{ma_type}{w}'
        dfc[col] = ma_func(dfc['close'], w)
        ind_cols[col] = col
    dfc['RSI'] = compute_rsi(dfc['close'], rsi_len)
    if show_macd:
        macd_line, macd_sig, macd_hist = compute_macd(dfc['close'], macd_fast, macd_slow, macd_signal)
        dfc['MACD'] = macd_line; dfc['MACD_SIG'] = macd_sig; dfc['MACD_HIST'] = macd_hist
    if show_stoch:
        k, d = compute_stochastic(dfc['high'], dfc['low'], dfc['close'], stoch_k, stoch_d)
        dfc['STO_K'] = k; dfc['STO_D'] = d
    if show_bbands:
        bb_ma, bb_up, bb_lo = compute_bollinger(dfc['close'])
        dfc['BB_MA'] = bb_ma; dfc['BB_UP'] = bb_up; dfc['BB_LO'] = bb_lo

    # Merge indicators from calc frame to display frame on date
    merge_cols = ['date'] + list(ind_cols.keys()) + ['RSI']
    if show_macd:
        merge_cols += ['MACD', 'MACD_SIG', 'MACD_HIST']
    if show_stoch:
        merge_cols += ['STO_K', 'STO_D']
    if show_bbands:
        merge_cols += ['BB_MA', 'BB_UP', 'BB_LO']
    dfx = dfd.merge(dfc[merge_cols], on='date', how='left')
    dfx['x'] = dfx['date_str']

    # Subplots: price, volume, RSI, optional MACD, optional Stochastic
    rows = 3 + int(show_macd) + int(show_stoch)
    row_heights = [0.55, 0.2, 0.15]
    titles = [f"{ticker} Price", "Volume", "RSI"]
    if show_macd:
        row_heights.append(0.1); titles.append("MACD")
    if show_stoch:
        row_heights.append(0.1); titles.append("Stochastic")
    # Normalize heights
    total = sum(row_heights)
    row_heights = [h/total for h in row_heights]
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=row_heights, subplot_titles=tuple(titles))

    # Candle
    fig.add_trace(go.Candlestick(x=dfx['x'].tolist(), open=dfx['open'].tolist(), high=dfx['high'].tolist(), low=dfx['low'].tolist(), close=dfx['close'].tolist(), name='Price'), row=1, col=1)

    # MAs
    palette = ['#5A8A7F', '#e6a085', '#2D5E52', '#b5694f', '#619BF7']
    for idx, w in enumerate(ma_windows):
        fig.add_trace(go.Scatter(x=dfx['x'].tolist(), y=dfx[f'{ma_type}{w}'].tolist(), name=f'{ma_type}{w}', line=dict(color=palette[idx % len(palette)], width=1.5)), row=1, col=1)

    # Bollinger
    if show_bbands:
        fig.add_trace(go.Scatter(x=dfx['x'].tolist(), y=dfx['BB_UP'].tolist(), name='BB Upper', line=dict(color='rgba(97,155,247,0.6)', width=1), hoverinfo='skip'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dfx['x'].tolist(), y=dfx['BB_MA'].tolist(), name='BB MA', line=dict(color='rgba(97,155,247,0.8)', width=1), hoverinfo='skip'), row=1, col=1)
        fig.add_trace(go.Scatter(x=dfx['x'].tolist(), y=dfx['BB_LO'].tolist(), name='BB Lower', line=dict(color='rgba(97,155,247,0.6)', width=1), hoverinfo='skip'), row=1, col=1)

    # Pullback Fib overlay
    if show_fib and pull_overlay:
        try:
            start_dt = pd.to_datetime(pull_overlay['start_date']).strftime('%Y-%m-%d')
            end_dt = pd.to_datetime(pull_overlay['end_date']).strftime('%Y-%m-%d')
            # Draw leg line
            fig.add_trace(go.Scatter(x=[start_dt, end_dt], y=[pull_overlay['start_price'], pull_overlay['end_price']],
                                     name='Last Leg', mode='lines', line=dict(color='#888', width=1, dash='dot')), row=1, col=1)
            # Horizontal fib levels across display range
            for label, py in pull_overlay.get('fib_prices', {}).items():
                fig.add_trace(go.Scatter(x=[dfx['x'].iloc[0], dfx['x'].iloc[-1]], y=[py, py], name=f'Fib {label}',
                                         line=dict(width=1, dash='dash', color='rgba(0,0,0,0.25)'), hoverinfo='skip', showlegend=False), row=1, col=1)
        except Exception:
            pass

    # Volume
    colors = np.where(dfx['close'] >= dfx['open'], '#398278', '#cc7c5e')
    fig.add_trace(go.Bar(x=dfx['x'].tolist(), y=dfx['volume'].tolist(), name='Volume', marker_color=colors, showlegend=False), row=2, col=1)

    # RSI lines
    rsi_row = 3
    fig.add_trace(go.Scatter(x=dfx['x'].tolist(), y=dfx['RSI'].tolist(), name=f'RSI{rsi_len}', line=dict(color='#619BF7', width=1.5)), row=rsi_row, col=1)
    for lvl, col in [(30, 'rgba(204,124,94,0.25)'), (50, 'rgba(90,138,127,0.2)'), (70, 'rgba(204,124,94,0.25)')]:
        fig.add_hrect(y0=lvl-1, y1=lvl+1, line_width=0, fillcolor=col, row=rsi_row, col=1)

    next_row = rsi_row
    # MACD panel
    if show_macd:
        next_row += 1
        fig.add_trace(go.Scatter(x=dfx['x'].tolist(), y=dfx['MACD'].tolist(), name='MACD', line=dict(color='#5A8A7F', width=1.3)), row=next_row, col=1)
        fig.add_trace(go.Scatter(x=dfx['x'].tolist(), y=dfx['MACD_SIG'].tolist(), name='Signal', line=dict(color='#cc7c5e', width=1)), row=next_row, col=1)
        fig.add_trace(go.Bar(x=dfx['x'].tolist(), y=dfx['MACD_HIST'].tolist(), name='Hist', marker_color=np.where(dfx['MACD_HIST']>=0, 'rgba(57,130,120,0.6)', 'rgba(204,124,94,0.6)'), showlegend=False), row=next_row, col=1)
        fig.update_yaxes(title_text='MACD', row=next_row, col=1)
    # Stochastic panel
    if show_stoch:
        next_row += 1
        fig.add_trace(go.Scatter(x=dfx['x'].tolist(), y=dfx['STO_K'].tolist(), name=f'%K{stoch_k}', line=dict(color='#398278', width=1.2)), row=next_row, col=1)
        fig.add_trace(go.Scatter(x=dfx['x'].tolist(), y=dfx['STO_D'].tolist(), name=f'%D{stoch_d}', line=dict(color='#619BF7', width=1.2)), row=next_row, col=1)
        for lvl, col in [(20, 'rgba(57,130,120,0.15)'), (80, 'rgba(204,124,94,0.15)')]:
            fig.add_hrect(y0=lvl-1, y1=lvl+1, line_width=0, fillcolor=col, row=next_row, col=1)
        fig.update_yaxes(title_text='Stoch', row=next_row, col=1, range=[0, 100])

    # Layout
    tick_interval = max(1, len(dfx)//20)
    tickvals = [dfx['x'].iloc[i] for i in range(0, len(dfx), tick_interval)]
    ticktext = tickvals

    # Slightly smaller overall chart height
    fig.update_layout(height=780 if (show_macd or show_stoch) else 620, showlegend=True, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1), hovermode='x unified', xaxis_rangeslider_visible=False)
    fig.update_yaxes(title_text='Price (VND)', row=1, col=1, tickformat=',.0f')
    fig.update_yaxes(title_text='Volume', row=2, col=1, tickformat=',.0f')
    fig.update_yaxes(title_text='RSI', row=3, col=1, range=[0, 100])
    # Use categorical x-axes to remove gaps for weekends/holidays
    fig.update_xaxes(title_text='Date', row=3, col=1, tickmode='array', tickvals=tickvals, ticktext=ticktext, tickangle=-45, type='category', categoryorder='category ascending')
    fig.update_xaxes(showticklabels=False, row=1, col=1, type='category', categoryorder='category ascending')
    fig.update_xaxes(showticklabels=False, row=2, col=1, type='category', categoryorder='category ascending')
    if show_macd:
        fig.update_xaxes(row=4 if not show_stoch else 4, col=1, type='category', categoryorder='category ascending')
    if show_stoch:
        fig.update_xaxes(row=5 if show_macd else 4, col=1, type='category', categoryorder='category ascending')

    st.plotly_chart(fig, use_container_width=True)


def main():
    st.title("Technical Analysis")
    st.markdown("Analyze banking stocks with moving averages, volume, RSI, and a simple score")

    with st.sidebar:
        st.subheader("Inputs")
        bank_tickers = load_bank_tickers()
        ticker = st.selectbox("Bank Ticker", options=bank_tickers or ["VCB", "ACB", "BID"], index=st.session_state.get('ta_idx', 0))
        period_map = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "2Y": 730}
        period_label = st.selectbox("Period", options=list(period_map.keys()), index=st.session_state.get('ta_period_idx', 2))
        days = period_map[period_label]
        st.markdown("---")
        ma_type = st.radio("MA Type", options=["SMA", "EMA"], index=st.session_state.get('ta_ma_type_idx', 1), horizontal=True)
        available_windows = [10, 20, 50, 100, 200]
        default_windows = st.session_state.get('ta_ma_windows', [20, 50, 200])
        ma_windows = st.multiselect("MA Windows", options=available_windows, default=default_windows)
        rsi_len = st.slider("RSI Length", min_value=5, max_value=30, value=st.session_state.get('ta_rsi_len', 14))
        show_bbands = st.checkbox("Bollinger Bands (20, 2σ)", value=st.session_state.get('ta_bbands', False))
        st.markdown("---")
        use_weekly_lts = st.checkbox("Use weekly data for LTS (API)", value=st.session_state.get('ta_use_weekly_lts', False), help="Fetch weekly bars from API for long-term trend. Falls back to aggregated weekly if unavailable.")
        show_macd = st.checkbox("Show MACD", value=st.session_state.get('ta_show_macd', True))
        macd_fast = st.number_input("MACD Fast EMA", min_value=5, max_value=30, value=st.session_state.get('ta_macd_fast', 12))
        macd_slow = st.number_input("MACD Slow EMA", min_value=10, max_value=60, value=st.session_state.get('ta_macd_slow', 26))
        macd_signal = st.number_input("MACD Signal", min_value=5, max_value=20, value=st.session_state.get('ta_macd_signal', 9))
        st.markdown("---")
        st.caption("OB/OS Pullback Component")
        enable_pullback = st.checkbox("Enable Pullback/Extension", value=st.session_state.get('ta_enable_pullback', True))
        auto_pull = st.checkbox("Auto pullback detection (recommended)", value=st.session_state.get('ta_auto_pull', True))
        with st.expander("Advanced pullback settings"):
            pull_mode = st.selectbox("Swing Threshold Mode", options=["percent", "atrx"], index=0 if st.session_state.get('ta_pull_mode', 'percent')=='percent' else 1, help="Use % change or ATR multiple to detect swings")
            pull_threshold = st.number_input("Threshold % (if percent)", min_value=1.0, max_value=15.0, value=float(st.session_state.get('ta_pull_threshold', 5.0)), step=0.5)
            pull_atr_mult = st.number_input("ATR multiple (if ATRx)", min_value=1.0, max_value=6.0, value=float(st.session_state.get('ta_pull_atr_mult', 3.0)), step=0.5)
            pull_scale = st.selectbox("Swing detection scale", options=["daily","weekly"], index=0 if st.session_state.get('ta_pull_scale','daily')=='daily' else 1, help="Detect swings on daily or weekly-aggregated data")
            show_fib = st.checkbox("Show Fib overlay", value=st.session_state.get('ta_show_fib', False))
        st.markdown("---")
        show_stoch = st.checkbox("Show Stochastic", value=st.session_state.get('ta_show_stoch', False))
        stoch_k = st.number_input("Stoch %K Length", min_value=5, max_value=30, value=st.session_state.get('ta_stoch_k', 14))
        stoch_d = st.number_input("Stoch %D Smoothing", min_value=2, max_value=10, value=st.session_state.get('ta_stoch_d', 3))
        if st.button("Refresh Data"):
            st.cache_data.clear()
            st.rerun()
        # Persist settings
        st.session_state['ta_idx'] = bank_tickers.index(ticker) if ticker in bank_tickers else 0
        st.session_state['ta_period_idx'] = list(period_map.keys()).index(period_label)
        st.session_state['ta_ma_type_idx'] = 0 if ma_type == 'SMA' else 1
        st.session_state['ta_ma_windows'] = ma_windows
        st.session_state['ta_rsi_len'] = rsi_len
        st.session_state['ta_bbands'] = show_bbands
        st.session_state['ta_use_weekly_lts'] = use_weekly_lts
        st.session_state['ta_show_macd'] = show_macd
        st.session_state['ta_macd_fast'] = macd_fast
        st.session_state['ta_macd_slow'] = macd_slow
        st.session_state['ta_macd_signal'] = macd_signal
        st.session_state['ta_enable_pullback'] = enable_pullback
        st.session_state['ta_auto_pull'] = auto_pull
        st.session_state['ta_pull_mode'] = pull_mode
        st.session_state['ta_pull_threshold'] = pull_threshold
        st.session_state['ta_pull_atr_mult'] = pull_atr_mult
        st.session_state['ta_pull_scale'] = pull_scale
        st.session_state['ta_show_fib'] = show_fib
        st.session_state['ta_show_stoch'] = show_stoch
        st.session_state['ta_stoch_k'] = stoch_k
        st.session_state['ta_stoch_d'] = stoch_d

    # Determine extended history needed (calendar days) to stabilize longest MA
    longest_ma = max([200] + (ma_windows or []))
    calendar_factor = 1.5  # ~365/252 trading-to-calendar approximation
    buffer_days = 30
    calc_days = max(days, int(longest_ma * calendar_factor) + buffer_days)  # e.g., 200 -> ~330 days

    with st.spinner(f"Fetching {ticker} data..."):
        # Display window data
        df = get_cached_stock_data(ticker, days)
        # Extended window for indicator calculations
        df_calc = get_cached_stock_data(ticker, calc_days)

    if df is None or df.empty:
        st.error("No price data found.")
        return

    # New scoring: Short-term trend, Long-term trend, Overbought/Oversold
    sts = compute_short_trend(df_calc)
    # Long-term trend: optionally compute on weekly data from API (if selected)
    lts_df = df_calc
    if use_weekly_lts:
        try:
            # Try API weekly first (use a longer day window to ensure enough weeks)
            weekly_api = get_cached_stock_data(ticker, days=int(calc_days * 2), resolution="W")
            if weekly_api is not None and not weekly_api.empty and len(weekly_api) >= 50:
                lts_df = weekly_api
            else:
                # Fallback: aggregate daily to weekly
                d = df.copy()
                d['tradingDate'] = pd.to_datetime(d['tradingDate'])
                d = d.set_index('tradingDate').sort_index()
                agg = d.resample('W-FRI').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna(how='any').reset_index().rename(columns={'tradingDate': 'tradingDate'})
                if len(agg) >= 50:
                    lts_df = agg
        except Exception:
            pass
    lts = compute_long_trend(lts_df)
    # Auto or manual pullback params
    pullback_enabled = bool(enable_pullback)
    auto_pull_enabled = bool(auto_pull)
    if auto_pull_enabled:
        auto = _auto_pull_params(df_calc, float(lts.get('score', 0.0)))
        pull_mode_eff = auto['mode']
        pull_threshold_eff = auto['threshold']
        pull_atr_mult_eff = auto['atr_mult']
        pull_scale_eff = auto['scale']
        pull_debug = auto.get('debug', {})
    else:
        pull_mode_eff = 'percent' if pull_mode == 'percent' else 'atrx'
        pull_threshold_eff = float(pull_threshold)
        pull_atr_mult_eff = float(pull_atr_mult)
        pull_scale_eff = str(pull_scale)
        pull_debug = {}

    obos = compute_obos(
        df_calc,
        rsi_len=rsi_len,
        macd_fast=macd_fast,
        macd_slow=macd_slow,
        macd_signal=macd_signal,
        lts_score=float(lts.get('score', 0.0)),
        pullback_enabled=pullback_enabled,
        pull_mode=pull_mode_eff,
        pull_threshold=pull_threshold_eff,
        pull_atr_mult=pull_atr_mult_eff,
        pull_scale=pull_scale_eff,
    )

    # Render chart and indicators (compute indicators on extended history). Add optional fib overlay.
    render_chart(
        df,
        ticker,
        ma_type,
        ma_windows,
        rsi_len,
        show_bbands,
        show_macd,
        macd_fast,
        macd_slow,
        macd_signal,
        show_stoch,
        stoch_k,
        stoch_d,
        df_calc=df_calc,
        pull_overlay=obos.get('pull_overlay'),
        show_fib=bool(st.session_state.get('ta_show_fib', False))
    )

    st.markdown("---")
    st.subheader("Trend & Overbought/Oversold Scores")

    def make_gauge(title: str, value: float, subtitle: str):
        rng = [-100, 100]
        # Dynamic bar color by regime/sign
        def bar_color(val: float, sub: str) -> str:
            sub = (sub or '').lower()
            if 'range' in sub or 'neutral' in sub:
                return '#D4A017'  # warm yellow for neutral
            if val >= 0:
                return '#398278'  # green
            return '#cc7c5e'      # terracotta red
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=value,
            number={'suffix': ''},
            title={'text': f"{subtitle}", 'font': {'size': 16}},
            gauge={
                'axis': {'range': rng},
                'bar': {'color': bar_color(value, subtitle)},
                'steps': [
                    {'range': [-100, -40], 'color': 'rgba(204,124,94,0.25)'},
                    {'range': [-40, 40], 'color': 'rgba(128,128,128,0.15)'},
                    {'range': [40, 100], 'color': 'rgba(57,130,120,0.25)'}
                ],
            }
        ))
        # Slightly increase height and top margin so text never collides
        fig.update_layout(height=220, margin=dict(l=10, r=10, t=44, b=10))
        return fig

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("#### Short-Term Trend")
        st.plotly_chart(
            make_gauge("Short-Term Trend", float(sts['score']), sts['regime']),
            use_container_width=True,
            config={"displayModeBar": False, "displaylogo": False},
            key=f"gauge_sts_{ticker}"
        )
    with c2:
        st.markdown("#### Long-Term Trend")
        st.plotly_chart(
            make_gauge("Long-Term Trend", float(lts['score']), lts['regime']),
            use_container_width=True,
            config={"displayModeBar": False, "displaylogo": False},
            key=f"gauge_lts_{ticker}"
        )
    with c3:
        st.markdown("#### Overbought/Oversold")
        st.plotly_chart(
            make_gauge("Overbought/Oversold", float(obos['score']), obos['regime']),
            use_container_width=True,
            config={"displayModeBar": False, "displaylogo": False},
            key=f"gauge_obos_{ticker}"
        )
    if bool(st.session_state.get('ta_enable_pullback', True)) and bool(st.session_state.get('ta_auto_pull', True)):
        suffix = '%' if (pull_mode_eff == 'percent') else 'x ATR'
        st.caption(f"Auto pullback: mode={pull_mode_eff}, threshold={pull_threshold_eff:.1f}{suffix}, scale={pull_scale_eff}.")

    # Component breakdowns
    def explain_sts(e: dict) -> str:
        lines = []
        ma = e.get('ma_align', 0.0)
        slope = e.get('slope', 0.0)
        price_pos = e.get('price_pos', 0.0)
        structure = e.get('structure', 0.0)
        lines.append(f"- MA alignment: EMA20 {'above' if ma>0 else 'below' if ma<0 else '≈'} EMA50 → {ma:+.0f} points.")
        lines.append(f"- EMA20 slope: momentum over ~20 bars scaled to ±25 → {slope:+.1f} points.")
        lines.append(f"- Price vs EMA20: close {'>' if price_pos>0 else '<' if price_pos<0 else '≈'} EMA20 with trend {'rising' if price_pos>0 else 'falling' if price_pos<0 else 'mixed'} → {price_pos:+.0f} points.")
        lines.append(f"- Structure: recent swings show {'HH/HL' if structure>0 else 'LH/LL' if structure<0 else 'mixed'} → {structure:+.0f} points.")
        total = ma + float(slope) + price_pos + structure
        lines.append(f"= Short-term trend score: {total:+.1f} (clipped to [-100,100]).")
        return "\n".join(lines)

    def explain_lts(e: dict) -> str:
        lines = []
        ma = e.get('ma_align', 0.0)
        slope = e.get('slope', 0.0)
        price_pos = e.get('price_pos', 0.0)
        ema50_slope = e.get('ema50_slope', 0.0)
        lines.append(f"- MA alignment: EMA50 {'above' if ma>0 else 'below' if ma<0 else '≈'} SMA200 → {ma:+.0f} points.")
        lines.append(f"- SMA200 slope: long-term drift scaled to ±25 → {slope:+.1f} points.")
        lines.append(f"- Price vs SMA200: close {'>' if price_pos>0 else '<' if price_pos<0 else '≈'} SMA200 → {price_pos:+.0f} points.")
        lines.append(f"- EMA50 slope: confirmation of baseline direction → {ema50_slope:+.0f} points.")
        total = ma + float(slope) + price_pos + ema50_slope
        lines.append(f"= Long-term trend score: {total:+.1f} (clipped to [-100,100]).")
        return "\n".join(lines)

    def explain_obos(e: dict, labels: list, pull_detail: str | None) -> str:
        lines = []
        rsi = e.get('rsi', 50.0)
        rsi_core = e.get('rsi_core', 0.0)
        macd = e.get('macd_shift', 0.0)
        lines.append(f"- RSI: {rsi:.1f}. Deep oversold (<20) is rewarded; extreme overbought (>80) is penalized → core {rsi_core:+.1f} points.")
        if macd != 0:
            reason = ', '.join(labels) if labels else 'MACD shift'
            lines.append(f"- MACD shift: {reason} → {macd:+.0f} points.")
        else:
            lines.append("- MACD shift: no recent confirmation → +0 points.")
        if 'pullback' in e:
            lines.append(f"- Pullback/Extension: {pull_detail or 'computed'} → {e['pullback']:+.1f} points.")
        total = float(rsi_core) + float(macd)
        if 'pullback' in e:
            total += float(e.get('pullback', 0.0))
        lines.append(f"= OB/OS score: {total:+.1f} (clipped to [-100,100]).")
        return "\n".join(lines)

    with st.expander("Details: Short-Term Trend components"):
        st.markdown(explain_sts(sts['components']))
    with st.expander("Details: Long-Term Trend components"):
        st.markdown(explain_lts(lts['components']))
    with st.expander("Details: OB/OS components"):
        st.markdown(explain_obos(obos['components'], obos.get('labels', []), obos.get('pull_detail')))

    # Watchlist comparison
    st.markdown("---")
    st.subheader("Watchlist Scores")
    bank_tickers = load_bank_tickers()
    watchlist = st.multiselect(
        "Select tickers",
        options=bank_tickers,
        default=[],
        help="Choose individual tickers (you can include the one shown above)."
    )

    group_map = load_bank_groups()
    selected_group_labels: List[str] = []
    selected_group_tickers: List[str] = []
    if group_map:
        all_label = "All"
        original_groups = sorted(group_map)
        label_options = [all_label] + [grp.replace('_', ' ') for grp in original_groups]
        label_to_group = {label: original for label, original in zip(label_options[1:], original_groups)}
        selected_group_labels = st.multiselect(
            "Add predefined bank groups",
            options=label_options,
            default=[],
            help="Populate the watchlist using sector/type groupings from the reference file."
        )
        for label in selected_group_labels:
            if label == all_label:
                for tickers in group_map.values():
                    selected_group_tickers.extend(tickers)
            else:
                original_group = label_to_group[label]
                selected_group_tickers.extend(group_map.get(original_group, []))
        if selected_group_tickers:
            group_preview = ", ".join(sorted(set(selected_group_tickers)))
            st.caption(f"Group tickers included: {group_preview}")

    def _unique_preserve_order(items: List[str]) -> List[str]:
        seen: set[str] = set()
        ordered: List[str] = []
        for item in items:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered

    combined_watchlist = _unique_preserve_order(watchlist + selected_group_tickers)

    if st.button("Compute Watchlist"):
        if not combined_watchlist:
            st.warning("Add one or more tickers to compare.")
        else:
            rows = []
            for t in combined_watchlist:
                dfi = get_cached_stock_data(t, calc_days)
                if dfi is not None and not dfi.empty:
                    _sts = compute_short_trend(dfi)
                    _lts = compute_long_trend(dfi)
                    _obos = compute_obos(dfi, rsi_len=rsi_len, macd_fast=macd_fast, macd_slow=macd_slow, macd_signal=macd_signal)
                    rows.append({
                        "Ticker": t,
                        "STS": _sts.get('score', np.nan),
                        "LTS": _lts.get('score', np.nan),
                        "OBOS": _obos.get('score', np.nan),
                    })
            if rows:
                table = pd.DataFrame(rows).sort_values(["LTS", "STS"], ascending=False).reset_index(drop=True)
                st.dataframe(table, use_container_width=True)


if __name__ == "__main__":
    main()
