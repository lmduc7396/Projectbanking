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


def rating_score(df: pd.DataFrame, ma_type: str, ma_windows: List[int], rsi_len: int,
                 macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9,
                 stoch_k: int = 14, stoch_d: int = 3) -> dict:
    """Compute a simple 0-100 technical score with rationale."""
    if df.empty:
        return {"score": 0, "rationale": ["No data" ]}
    close = df['close']
    last = close.iloc[-1]
    # MAs
    ma_func = compute_sma if ma_type == 'SMA' else compute_ema
    mas = {w: ma_func(close, w).iloc[-1] for w in ma_windows}
    # Trend strength via slope of medium MA (use median window)
    w_mid = int(np.median(ma_windows))
    mid_series = ma_func(close, w_mid)
    # slope over last 10 points normalized by price
    lookback = min(10, len(mid_series) - 1)
    slope = 0.0
    if lookback > 1:
        y = mid_series.iloc[-lookback:]
        x = np.arange(len(y))
        # least squares slope
        x_mean = x.mean(); y_mean = y.mean()
        denom = ((x - x_mean)**2).sum()
        slope = float(((x - x_mean) * (y - y_mean)).sum() / denom) if denom != 0 else 0.0
        slope_pct = (slope / max(1.0, last)) * 1000  # scale
    else:
        slope_pct = 0.0
    # RSI
    rsi_series = compute_rsi(close, rsi_len)
    rsi_last = float(rsi_series.iloc[-1])
    # Volume pressure (10d vs 50d)
    vol = df['volume'].astype(float)
    vol10 = float(vol.rolling(10, min_periods=1).mean().iloc[-1])
    vol50 = float(vol.rolling(50, min_periods=1).mean().iloc[-1])

    # MACD
    macd_line, macd_sig, macd_hist = compute_macd(close, macd_fast, macd_slow, macd_signal)
    macd_last = float(macd_line.iloc[-1] - macd_sig.iloc[-1])  # positive when bullish
    # Stochastic
    k, d = compute_stochastic(df['high'].astype(float), df['low'].astype(float), close, stoch_k, stoch_d)
    k_last, d_last = float(k.iloc[-1]), float(d.iloc[-1])

    score = 50.0
    reasons = []
    breakdown = []  # list of {component, contribution, detail}
    # Price vs MAs
    # Tuning weights (reduced MA influence)
    MA_POINTS_PER = 2.0         # was 3.0
    MA_ALIGN_POS = 6.0          # was +10
    MA_ALIGN_NEG = -3.0         # was -5
    MA_SLOPE_MAX = 6.0          # was 10 (cap for slope contribution)

    above_list = []
    below_list = []
    for w, mv in mas.items():
        if last > mv:
            above_list.append(str(w))
        else:
            below_list.append(str(w))
    ma_contrib = MA_POINTS_PER * len(above_list) - MA_POINTS_PER * len(below_list)
    score += ma_contrib
    breakdown.append({
        "component": "Price vs MAs",
        "contribution": round(ma_contrib, 1),
        "detail": f"Above: {', '.join(above_list) if above_list else '—'}; Below: {', '.join(below_list) if below_list else '—'}",
        "meta": {"above": above_list, "below": below_list, "points_per_ma": MA_POINTS_PER, "total_mas": len(ma_windows)}
    })
    # MA stacking (bullish if shorter > longer)
    sorted_ws = sorted(ma_windows)
    stacked = all(mas[sorted_ws[i]] >= mas[sorted_ws[i+1]] for i in range(len(sorted_ws)-1))
    if stacked:
        score += MA_ALIGN_POS; reasons.append(f"MA alignment bullish ({' > '.join(map(str, sorted_ws))})")
        breakdown.append({"component": "MA alignment", "contribution": MA_ALIGN_POS, "detail": "Shorter MAs above longer", "meta": {"stack": sorted_ws}})
    else:
        score += MA_ALIGN_NEG; reasons.append("MA alignment not bullish")
        breakdown.append({"component": "MA alignment", "contribution": MA_ALIGN_NEG, "detail": "Shorter MAs not above longer", "meta": {"stack": sorted_ws}})
    # Trend slope
    if slope_pct > 0:
        slope_contrib = float(min(MA_SLOPE_MAX, slope_pct))
        score += slope_contrib
        reasons.append(f"MA{w_mid} slope positive ({slope_pct:.2f}‰)")
    else:
        slope_contrib = float(max(-MA_SLOPE_MAX, slope_pct))
        score += slope_contrib
        reasons.append(f"MA{w_mid} slope negative ({slope_pct:.2f}‰)")
    breakdown.append({"component": f"MA{w_mid} slope", "contribution": round(slope_contrib, 1), "detail": f"{slope_pct:.2f}‰ over {lookback} bars", "meta": {"slope_ppm": slope_pct, "lookback": lookback}})
    # RSI contribution
    # RSI scoring per spec -> map RSI to 0..100 buckets, then to 0..10 scale, then center to contribution around 0
    # 0 points for RSI 0-30 and 80-100.
    # 25 points for RSI 30-40 and 70-80.
    # 50 points for RSI 40-45 and 65-70.
    # 75 points for RSI 45-50 and 60-65.
    # 100 points for RSI 50-60.
    rsi_pts_100 = 0
    if 50 <= rsi_last <= 60:
        rsi_pts_100 = 100
    elif (45 <= rsi_last < 50) or (60 < rsi_last <= 65):
        rsi_pts_100 = 75
    elif (40 <= rsi_last < 45) or (65 < rsi_last <= 70):
        rsi_pts_100 = 50
    elif (30 <= rsi_last < 40) or (70 < rsi_last < 80):
        rsi_pts_100 = 25
    else:  # 0-30 or 80-100
        rsi_pts_100 = 0
    rsi_score_10 = rsi_pts_100 / 10.0
    # Convert to centered contribution around 0 (so 5 is neutral)
    rsi_contrib = round(rsi_score_10 - 5.0, 1)
    score += rsi_contrib
    reasons.append(f"RSI {rsi_last:.1f} → bucket {rsi_pts_100} → {rsi_contrib:+.1f}")
    breakdown.append({"component": "RSI", "contribution": rsi_contrib, "detail": f"RSI={rsi_last:.1f}, bucket={rsi_pts_100}", "meta": {"rsi": rsi_last, "bucket": rsi_pts_100, "score10": rsi_score_10}})
    # Volume confirmation
    vol_ratio = vol10 / vol50 if vol50 > 0 else np.nan
    if vol50 > 0 and vol_ratio > 1.1:
        vol_contrib = 5; score += vol_contrib; reasons.append(f"Rising volume (10/50={vol_ratio:.2f}x)")
    elif vol50 > 0 and vol_ratio < 0.9:
        vol_contrib = -3; score -= 3; reasons.append(f"Weak volume (10/50={vol_ratio:.2f}x)")
    else:
        vol_contrib = 0
    breakdown.append({"component": "Volume", "contribution": vol_contrib, "detail": f"10/50={vol_ratio:.2f}x" if vol50 > 0 else "N/A", "meta": {"ratio": vol_ratio}})

    # MACD contribution
    if macd_last > 0:
        macd_contrib = 5; score += macd_contrib; reasons.append("MACD above signal")
    else:
        macd_contrib = -3; score -= 3; reasons.append("MACD below signal")
    breakdown.append({"component": "MACD", "contribution": macd_contrib, "detail": f"Δ={macd_last:.2f}", "meta": {"delta": macd_last}})

    # Stochastic contribution
    if k_last > d_last and 20 < k_last < 80:
        stoch_contrib = 4; score += stoch_contrib; reasons.append(f"Stoch bullish (%K={k_last:.1f} > %D={d_last:.1f})")
    elif k_last >= 80:
        stoch_contrib = -3; score -= 3; reasons.append(f"Stoch overbought (%K={k_last:.1f})")
    elif k_last <= 20:
        stoch_contrib = 2; score += 2; reasons.append(f"Stoch oversold (%K={k_last:.1f})")
    else:
        stoch_contrib = 0
    breakdown.append({"component": "Stochastic", "contribution": stoch_contrib, "detail": f"%K={k_last:.1f}, %D={d_last:.1f}", "meta": {"k": k_last, "d": d_last}})

    score = max(0, min(100, round(score, 1)))
    if above_list or below_list:
        if above_list:
            reasons.insert(0, f"Price above MAs: {', '.join(above_list)}")
        if below_list:
            reasons.insert(1 if above_list else 0, f"Price below MAs: {', '.join(below_list)}")
    return {"score": max(0, min(100, round(score, 1))), "rationale": reasons, "rsi": round(rsi_last, 1), "breakdown": breakdown}


def explain_score(ticker: str, result: dict, ma_windows: List[int]) -> str:
    """Build an intuitive explanation of how the technical score was computed (signed scale)."""
    base = 0
    lines = [f"Net score starts at {base} (neutral)."]
    # Price vs MAs
    b_ma = next((b for b in result['breakdown'] if b['component'] == 'Price vs MAs'), None)
    if b_ma:
        above = b_ma.get('meta', {}).get('above', [])
        below = b_ma.get('meta', {}).get('below', [])
        per = b_ma.get('meta', {}).get('points_per_ma', 3)
        lines.append(f"Price vs MAs: +{per} for each MA above, -{per} for each below. Above {len(above)}/{len(ma_windows)} ({', '.join(above) or '–'}), Below {len(below)} ({', '.join(below) or '–'}) -> {b_ma['contribution']:+.1f}.")
    # MA alignment
    b_align = next((b for b in result['breakdown'] if b['component'] == 'MA alignment'), None)
    if b_align:
        lines.append(f"MA alignment ({' > '.join(map(str, b_align.get('meta', {}).get('stack', ma_windows)))}) -> {b_align['contribution']:+.1f}.")
    # MA slope
    b_slope = next((b for b in result['breakdown'] if b['component'].startswith('MA') and 'slope' in b['component']), None)
    if b_slope:
        lines.append(f"{b_slope['component']}: slope {b_slope.get('meta', {}).get('slope_ppm', 0):+.2f}‰ over {b_slope.get('meta', {}).get('lookback', 0)} bars -> {b_slope['contribution']:+.1f}.")
    # RSI
    b_rsi = next((b for b in result['breakdown'] if b['component'] == 'RSI'), None)
    if b_rsi:
        lines.append(f"RSI {b_rsi.get('meta', {}).get('rsi', 0):.1f} -> {b_rsi['contribution']:+.1f}.")
    # Volume
    b_vol = next((b for b in result['breakdown'] if b['component'] == 'Volume'), None)
    if b_vol:
        ratio = b_vol.get('meta', {}).get('ratio', np.nan)
        lines.append(f"Volume 10/50 = {ratio:.2f}x -> {b_vol['contribution']:+.1f}.")
    # MACD
    b_macd = next((b for b in result['breakdown'] if b['component'] == 'MACD'), None)
    if b_macd:
        lines.append(f"MACD delta (line - signal) {b_macd.get('meta', {}).get('delta', 0):+.2f} -> {b_macd['contribution']:+.1f}.")
    # Stochastic
    b_sto = next((b for b in result['breakdown'] if b['component'] == 'Stochastic'), None)
    if b_sto:
        lines.append(f"Stochastic %K/%D = {b_sto.get('meta', {}).get('k', 0):.1f}/{b_sto.get('meta', {}).get('d', 0):.1f} -> {b_sto['contribution']:+.1f}.")
    # Compute final net score (centered around 0)
    net_final = float(result.get('score', 50)) - 50.0
    lines.append(f"Final net score for {ticker}: {net_final:+.1f}.")
    return "\n".join(lines)


def score_waterfall(result: dict):
    """Return a Plotly Waterfall (signed): contributions from 0 to final net score."""
    import plotly.graph_objects as go
    base = 0
    measures = ['absolute']
    x = ['Base']
    y = [base]
    text = ['Base 0']
    for b in result.get('breakdown', []):
        measures.append('relative')
        x.append(b['component'])
        y.append(b['contribution'])
        text.append(b['detail'])
    measures.append('total')
    x.append('Final')
    # show final net score (score centered around 0)
    net_final = float(result.get('score', 50)) - 50.0
    y.append(0)
    text.append(f"{net_final:+.1f}")
    fig = go.Figure(go.Waterfall(
        name="Score",
        orientation="v",
        measure=measures,
        x=x,
        text=text,
        y=y,
        connector={'line': {'color': 'rgba(0,0,0,0.2)'}}
    ))
    fig.update_layout(height=360, showlegend=False)
    return fig


def render_chart(df: pd.DataFrame, ticker: str, ma_type: str, ma_windows: List[int], rsi_len: int,
                 show_bbands: bool, show_macd: bool, macd_fast: int, macd_slow: int, macd_signal: int,
                 show_stoch: bool, stoch_k: int, stoch_d: int):
    # Prepare
    dfx = df.copy()
    dfx['date'] = pd.to_datetime(dfx['tradingDate'])
    dfx['date_str'] = dfx['date'].dt.strftime('%Y-%m-%d')
    # Ensure numeric OHLC and drop rows with missing OHLC to avoid Plotly errors
    for c in ['open', 'high', 'low', 'close', 'volume']:
        if c in dfx.columns:
            dfx[c] = pd.to_numeric(dfx[c], errors='coerce')
    dfx = dfx.dropna(subset=['open', 'high', 'low', 'close']).reset_index(drop=True)
    # Use string date for categorical x-axis to avoid gaps and show real dates in tooltip
    dfx['x'] = dfx['date_str']

    # MAs
    ma_func = compute_sma if ma_type == 'SMA' else compute_ema
    for w in ma_windows:
        dfx[f'{ma_type}{w}'] = ma_func(dfx['close'], w)

    # RSI
    dfx['RSI'] = compute_rsi(dfx['close'], rsi_len)
    # MACD
    if show_macd:
        macd_line, macd_sig, macd_hist = compute_macd(dfx['close'], macd_fast, macd_slow, macd_signal)
        dfx['MACD'] = macd_line; dfx['MACD_SIG'] = macd_sig; dfx['MACD_HIST'] = macd_hist
    # Stochastic
    if show_stoch:
        k, d = compute_stochastic(dfx['high'], dfx['low'], dfx['close'], stoch_k, stoch_d)
        dfx['STO_K'] = k; dfx['STO_D'] = d

    # Bollinger
    if show_bbands:
        bb_ma, bb_up, bb_lo = compute_bollinger(dfx['close'])
        dfx['BB_MA'] = bb_ma; dfx['BB_UP'] = bb_up; dfx['BB_LO'] = bb_lo

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
        st.session_state['ta_show_macd'] = show_macd
        st.session_state['ta_macd_fast'] = macd_fast
        st.session_state['ta_macd_slow'] = macd_slow
        st.session_state['ta_macd_signal'] = macd_signal
        st.session_state['ta_show_stoch'] = show_stoch
        st.session_state['ta_stoch_k'] = stoch_k
        st.session_state['ta_stoch_d'] = stoch_d

    with st.spinner(f"Fetching {ticker} data..."):
        df = get_cached_stock_data(ticker, days)

    if df is None or df.empty:
        st.error("No price data found.")
        return

    # Render chart and indicators
    render_chart(df, ticker, ma_type, ma_windows, rsi_len, show_bbands, show_macd, macd_fast, macd_slow, macd_signal, show_stoch, stoch_k, stoch_d)

    # Compute rating
    result = rating_score(df, ma_type, ma_windows, rsi_len, macd_fast, macd_slow, macd_signal, stoch_k, stoch_d)
    col1, col2 = st.columns([1, 3])
    with col1:
        signed = float(result.get('score', 50)) - 50.0
        st.metric("Technical Score", f"{signed:+.1f}")
        st.caption("Negative = bearish, Positive = bullish; Neutral = 0")
        st.caption(f"RSI: {result.get('rsi', '—')}")
    with col2:
        if result.get('rationale'):
            st.write("Reasons:")
            for r in result['rationale']:
                st.write(f"• {r}")

    # Score breakdown table
    if result.get('breakdown'):
        st.subheader("Score Breakdown")
        bdf = pd.DataFrame(result['breakdown'])
        bdf = bdf.sort_values('contribution', ascending=False).reset_index(drop=True)
        # Hide internal 'meta' column from end users
        bdf = bdf.drop(columns=['meta'], errors='ignore')
        st.dataframe(bdf, use_container_width=True)
        # Waterfall and narrative
        wf = score_waterfall(result)
        st.plotly_chart(wf, use_container_width=True)
        st.subheader("How this score was computed")
        st.text(explain_score(ticker, result, ma_windows))

    # Watchlist comparison
    st.markdown("---")
    st.subheader("Watchlist Scores (signed)")
    watchlist = st.multiselect("Select additional tickers", options=[t for t in load_bank_tickers() if t != ticker], default=[], help="Compare scores using the same settings")
    if st.button("Compute Watchlist") and watchlist:
        rows = []
        for t in watchlist:
            dfi = get_cached_stock_data(t, days)
            if dfi is not None and not dfi.empty:
                res = rating_score(dfi, ma_type, ma_windows, rsi_len, macd_fast, macd_slow, macd_signal, stoch_k, stoch_d)
                rows.append({"Ticker": t, "Score": float(res.get('score', 50)) - 50.0, "RSI": res.get('rsi', np.nan)})
        if rows:
            table = pd.DataFrame(rows).sort_values("Score", ascending=False).reset_index(drop=True)
            st.dataframe(table, use_container_width=True)


if __name__ == "__main__":
    main()
