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


def compute_obos(df: pd.DataFrame, rsi_len: int = 14, macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9) -> dict:
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

    score = float(np.clip(rsi_core + macd_shift, -100.0, 100.0))
    regime = "Bullish OS" if score >= 40 else "Bearish OB" if score <= -40 else "Neutral"
    return {
        "score": round(score, 1),
        "regime": regime,
        "components": {"rsi_core": round(rsi_core, 1), "macd_shift": macd_shift, "rsi": round(rsi_last, 1)},
        "labels": labels,
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
                 show_stoch: bool, stoch_k: int, stoch_d: int, df_calc=None):
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

    fig.update_layout(height=900 if (show_macd or show_stoch) else 760, showlegend=True, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1), hovermode='x unified', xaxis_rangeslider_visible=False)
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

    # Render chart and indicators (compute indicators on extended history)
    render_chart(df, ticker, ma_type, ma_windows, rsi_len, show_bbands, show_macd, macd_fast, macd_slow, macd_signal, show_stoch, stoch_k, stoch_d, df_calc=df_calc)

    # New scoring: Short-term trend, Long-term trend, Overbought/Oversold
    st.markdown("---")
    st.subheader("Trend & Overbought/Oversold Scores")

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
    obos = compute_obos(df, rsi_len=rsi_len, macd_fast=macd_fast, macd_slow=macd_slow, macd_signal=macd_signal)

    def make_gauge(title: str, value: float, subtitle: str):
        rng = [-100, 100]
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=value,
            number={'suffix': ''},
            title={'text': f"{title}<br><span style='font-size:0.8em;color:gray'>{subtitle}</span>", 'font': {'size': 14}},
            gauge={
                'axis': {'range': rng},
                'bar': {'color': '#398278'},
                'steps': [
                    {'range': [-100, -40], 'color': 'rgba(204,124,94,0.25)'},
                    {'range': [-40, 40], 'color': 'rgba(128,128,128,0.15)'},
                    {'range': [40, 100], 'color': 'rgba(57,130,120,0.25)'}
                ],
            }
        ))
        fig.update_layout(height=200, margin=dict(l=10, r=10, t=40, b=10))
        return fig

    c1, c2, c3 = st.columns(3)
    with c1:
        st.plotly_chart(make_gauge("Short-Term Trend", float(sts['score']), sts['regime']), use_container_width=True)
        st.caption("Components: EMA20 vs EMA50, EMA20 slope, price vs EMA20, HH/HL")
    with c2:
        st.plotly_chart(make_gauge("Long-Term Trend", float(lts['score']), lts['regime']), use_container_width=True)
        st.caption("Components: EMA50 vs SMA200, SMA200 slope, price vs SMA200, EMA50 slope")
    with c3:
        st.plotly_chart(make_gauge("Overbought/Oversold", float(obos['score']), obos['regime']), use_container_width=True)
        st.caption("RSI core with MACD turn confirmation")
    st.caption("Indicators are computed on extended history to stabilize EMA/SMA even on short display windows.")

    # Component breakdowns
    with st.expander("Details: Short-Term Trend components"):
        st.json(sts['components'])
    with st.expander("Details: Long-Term Trend components"):
        st.json(lts['components'])
    with st.expander("Details: OB/OS components"):
        st.json(obos['components'])

    # Watchlist comparison
    st.markdown("---")
    st.subheader("Watchlist Scores")
    watchlist = st.multiselect("Select additional tickers", options=[t for t in load_bank_tickers() if t != ticker], default=[], help="Compare scores using the same settings")
    if st.button("Compute Watchlist") and watchlist:
        rows = []
        for t in watchlist:
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
