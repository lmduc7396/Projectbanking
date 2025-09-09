#!/usr/bin/env python3
"""
Diagnostic: fetch ticker data via TCBS (through utilities.stock_candle),
run ZigZag swing detection and pullback/extension leg selection, and print details.

Usage:
  python scripts/diag_pullback.py VPB 400 percent 5.0
  python scripts/diag_pullback.py VPB 400 atrx 3.0
"""
import os
import sys
from datetime import datetime
import numpy as np
import pandas as pd

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from utilities.stock_candle import get_cached_stock_data


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=1).mean()


def compute_sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = np.maximum(high - low, np.maximum((high - prev_close).abs(), (low - prev_close).abs()))
    atr = tr.ewm(alpha=1/length, adjust=False, min_periods=1).mean()
    return atr


def zigzag_swings(close: pd.Series, high: pd.Series, low: pd.Series, mode: str = 'percent', threshold: float = 5.0,
                  atr_series: pd.Series | None = None, atr_mult: float = 3.0, max_lookback: int = 250,
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


def legs_from_pivots(pivots, close: pd.Series):
    up_legs, dn_legs = [], []
    for i in range(len(pivots) - 1):
        a, b = pivots[i], pivots[i+1]
        if not (a.get('confirmed') and b.get('confirmed')):
            continue
        if a['type'] == 'L' and b['type'] == 'H':
            L_idx, H_idx = a['idx'], b['idx']
            move_pct = (float(close.iloc[H_idx]) / max(1e-9, float(close.iloc[L_idx])) - 1.0) * 100.0
            bars = max(1, H_idx - L_idx)
            up_legs.append(('up', L_idx, H_idx, move_pct, bars))
        elif a['type'] == 'H' and b['type'] == 'L':
            H_idx, L_idx = a['idx'], b['idx']
            move_pct = (1.0 - float(close.iloc[L_idx]) / max(1e-9, float(close.iloc[H_idx]))) * 100.0
            bars = max(1, L_idx - H_idx)
            dn_legs.append(('down', H_idx, L_idx, move_pct, bars))
    return up_legs, dn_legs


def compute_lts_score(close: pd.Series) -> float:
    ema50 = compute_ema(close, 50)
    sma200 = compute_sma(close, 200)
    ma_align = 30.0 if float(ema50.iloc[-1]) > float(sma200.iloc[-1]) else -30.0 if float(ema50.iloc[-1]) < float(sma200.iloc[-1]) else 0.0
    # slope scale
    def _linreg_slope(series: pd.Series, lookback: int) -> float:
        s = pd.Series(series).dropna()
        if len(s) < max(3, lookback):
            return 0.0
        y = s.iloc[-lookback:]
        x = np.arange(len(y), dtype=float)
        xm, ym = x.mean(), y.mean()
        denom = ((x - xm)**2).sum()
        if denom == 0: return 0.0
        return float(((x - xm) * (y - ym)).sum() / denom)
    slope = _linreg_slope(sma200, lookback=min(100, len(sma200)))
    avg_price = float(close.iloc[-100:].mean()) if len(close) >= 100 else float(close.iloc[-1])
    ppm = (slope / max(1e-9, avg_price)) * 10000.0
    slope_sc = float(np.clip(ppm / 1.5, -1, 1) * 25.0)
    price_pos = 35.0 if float(close.iloc[-1]) > float(sma200.iloc[-1]) else -35.0 if float(close.iloc[-1]) < float(sma200.iloc[-1]) else 0.0
    ema50_conf = 10.0 if float(ema50.iloc[-1]) > float(ema50.iloc[-5]) else -10.0
    score = float(np.clip(ma_align + slope_sc + price_pos + ema50_conf, -100.0, 100.0))
    return round(score, 1)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('ticker')
    ap.add_argument('days', type=int, nargs='?', default=400)
    ap.add_argument('mode', choices=['percent','atrx'], nargs='?', default='percent')
    ap.add_argument('threshold', type=float, nargs='?', default=5.0)
    args = ap.parse_args()

    df = get_cached_stock_data(args.ticker, args.days)
    if df is None or df.empty:
        print('No data fetched')
        sys.exit(1)
    df = df.sort_values('tradingDate').reset_index(drop=True)
    for c in ['open','high','low','close','volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    close, high, low = df['close'], df['high'], df['low']
    a = compute_atr(high, low, close)
    piv = zigzag_swings(close, high, low, mode=args.mode, threshold=args.threshold, atr_series=a, atr_mult=args.threshold, max_lookback=250, min_swing_bars=5)
    up, dn = legs_from_pivots(piv, close)
    lts = compute_lts_score(close)
    print(f"Ticker {args.ticker} | days={args.days} | mode={args.mode} | threshold={args.threshold}")
    print(f"LTS score: {lts:+.1f}")
    print(f"Total pivots: {len(piv)} (last 10):")
    for p in piv[-10:]:
        dt = df['tradingDate'].iloc[p['idx']].strftime('%Y-%m-%d')
        print(f"  {dt} {p['type']} {p['price']:.2f} confirmed={p.get('confirmed')}")
    def print_legs(arr, name):
        print(name)
        for leg in arr[-6:]:
            dirn, i0, i1, pct, bars = leg
            d0 = df['tradingDate'].iloc[i0].strftime('%Y-%m-%d')
            d1 = df['tradingDate'].iloc[i1].strftime('%Y-%m-%d')
            print(f"  {dirn} {d0}->{d1}: {pct:+.2f}% over {bars} bars")
    print_legs(up, 'UP legs')
    print_legs(dn, 'DOWN legs')

if __name__ == '__main__':
    main()

