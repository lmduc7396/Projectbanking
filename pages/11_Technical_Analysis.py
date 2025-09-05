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
    # Price vs MAs
    above_list = []
    below_list = []
    for w, mv in mas.items():
        if last > mv:
            score += 3; above_list.append(str(w))
        else:
            score -= 3; below_list.append(str(w))
    # MA stacking (bullish if shorter > longer)
    sorted_ws = sorted(ma_windows)
    stacked = all(mas[sorted_ws[i]] >= mas[sorted_ws[i+1]] for i in range(len(sorted_ws)-1))
    if stacked:
        score += 10; reasons.append(f"MA alignment bullish ({' > '.join(map(str, sorted_ws))})")
    else:
        score -= 5; reasons.append("MA alignment not bullish")
    # Trend slope
    if slope_pct > 0:
        score += min(10, slope_pct)
        reasons.append(f"MA{w_mid} slope positive ({slope_pct:.2f}‰)")
    else:
        score += max(-10, slope_pct); reasons.append(f"MA{w_mid} slope negative ({slope_pct:.2f}‰)")
    # RSI contribution
    if 50 <= rsi_last <= 70:
        score += 5; reasons.append(f"RSI supportive ({rsi_last:.1f})")
    elif rsi_last > 70:
        score -= 5; reasons.append(f"RSI overbought ({rsi_last:.1f})")
    elif 30 <= rsi_last < 50:
        score -= 2; reasons.append(f"RSI weak ({rsi_last:.1f})")
    else:  # < 30
        score += 5; reasons.append(f"RSI oversold ({rsi_last:.1f})")
    # Volume confirmation
    if vol10 > vol50 * 1.1:
        score += 5; reasons.append(f"Rising volume (10/50={vol10/vol50:.2f}x)")
    elif vol10 < vol50 * 0.9:
        score -= 3; reasons.append(f"Weak volume (10/50={vol10/vol50:.2f}x)")

    # MACD contribution
    if macd_last > 0:
        score += 5; reasons.append("MACD above signal")
    else:
        score -= 3; reasons.append("MACD below signal")

    # Stochastic contribution
    if k_last > d_last and 20 < k_last < 80:
        score += 4; reasons.append(f"Stoch bullish (%K={k_last:.1f} > %D={d_last:.1f})")
    elif k_last >= 80:
        score -= 3; reasons.append(f"Stoch overbought (%K={k_last:.1f})")
    elif k_last <= 20:
        score += 2; reasons.append(f"Stoch oversold (%K={k_last:.1f})")

    score = max(0, min(100, round(score, 1)))
    if above_list or below_list:
        if above_list:
            reasons.insert(0, f"Price above MAs: {', '.join(above_list)}")
        if below_list:
            reasons.insert(1 if above_list else 0, f"Price below MAs: {', '.join(below_list)}")
    return {"score": score, "rationale": reasons, "rsi": round(rsi_last, 1)}


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
    fig.update_xaxes(title_text='Date', row=3, col=1, tickmode='array', tickvals=tickvals, ticktext=ticktext, tickangle=-45)
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    fig.update_xaxes(showticklabels=False, row=2, col=1)

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
        st.metric("Technical Score", f"{result['score']}/100")
        st.caption(f"RSI: {result.get('rsi', '—')}")
    with col2:
        if result.get('rationale'):
            st.write("Reasons:")
            for r in result['rationale']:
                st.write(f"• {r}")

    # Watchlist comparison
    st.markdown("---")
    st.subheader("Watchlist Scores")
    watchlist = st.multiselect("Select additional tickers", options=[t for t in load_bank_tickers() if t != ticker], default=[], help="Compare scores using the same settings")
    if st.button("Compute Watchlist") and watchlist:
        rows = []
        for t in watchlist:
            dfi = get_cached_stock_data(t, days)
            if dfi is not None and not dfi.empty:
                res = rating_score(dfi, ma_type, ma_windows, rsi_len, macd_fast, macd_slow, macd_signal, stoch_k, stoch_d)
                rows.append({"Ticker": t, "Score": res['score'], "RSI": res.get('rsi', np.nan)})
        if rows:
            table = pd.DataFrame(rows).sort_values("Score", ascending=False).reset_index(drop=True)
            st.dataframe(table, use_container_width=True)


if __name__ == "__main__":
    main()
