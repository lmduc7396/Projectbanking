import numpy as np
import pandas as pd
from typing import Dict
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


def compute_obos(df: pd.DataFrame, rsi_len: int = 14, macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9) -> Dict:
    if df is None or df.empty:
        return {"score": 0.0, "regime": "Neutral"}
    close = pd.to_numeric(df['close'], errors='coerce')
    rsi = compute_rsi(close, rsi_len)
    rsi_last = float(rsi.iloc[-1]) if len(rsi) else 50.0
    macd_line, macd_sig, macd_hist = compute_macd(close, macd_fast, macd_slow, macd_signal)
    hist_rising = len(macd_hist) >= 4 and all(macd_hist.iloc[-i] > macd_hist.iloc[-i-1] for i in range(1, 4))
    hist_falling = len(macd_hist) >= 4 and all(macd_hist.iloc[-i] < macd_hist.iloc[-i-1] for i in range(1, 4))
    recent_cross_up = any(macd_line.iloc[-i] > macd_sig.iloc[-i] and macd_line.iloc[-i-1] <= macd_sig.iloc[-i-1] for i in range(1, min(4, len(macd_line))))
    recent_cross_dn = any(macd_line.iloc[-i] < macd_sig.iloc[-i] and macd_line.iloc[-i-1] >= macd_sig.iloc[-i-1] for i in range(1, min(4, len(macd_line))))
    rsi_core = _rsi_core_score(rsi_last)
    macd_shift = 0.0
    if (rsi_last < 40 and (hist_rising or recent_cross_up)):
        macd_shift = 20.0
    elif (rsi_last > 60 and (hist_falling or recent_cross_dn)):
        macd_shift = -20.0
    score = float(np.clip(rsi_core + macd_shift, -100.0, 100.0))
    regime = "Bullish OS" if score >= 40 else "Bearish OB" if score <= -40 else "Neutral"
    return {"score": round(score, 1), "regime": regime}


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
            obos = compute_obos(df_calc)
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
