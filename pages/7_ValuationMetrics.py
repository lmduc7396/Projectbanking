"""
Valuation Analysis Page
Provides comprehensive valuation metrics analysis for Vietnamese banking sector
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import sys
from datetime import timedelta

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import utilities
from utilities.valuation_analysis import (
    get_metric_column,
    calculate_historical_stats,
    prepare_statistics_table,
    get_sector_and_components,
    get_valuation_status
)

# Page configuration
st.set_page_config(
    page_title="Valuation Analysis",
    page_icon="",
    layout="wide"
)

# Load data
@st.cache_data
def load_valuation_data():
    """Load valuation data"""
    file_path = os.path.join(project_root, 'Data', 'Valuation_banking.csv')
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df['TRADE_DATE'] = pd.to_datetime(df['TRADE_DATE'])
        return df
    return None

# Title and description
st.title("Banking Sector Valuation Analysis")
st.markdown("Comprehensive valuation metrics analysis with distribution charts, historical trends, and statistical measures")

# Load data
df = load_valuation_data()

if df is None:
    st.error("Valuation data not found. Please run prepare_valuation.py script first.")
    st.stop()

# Sidebar metric selection
with st.sidebar:
    st.markdown("### Settings")
    metric_type = st.radio(
        "Valuation Metric:",
        ["P/E", "P/B"],
        index=1,  # Default to P/B (index 1)
        help="This selection will update all charts and tables"
    )
    metric_col = get_metric_column(metric_type)


# Chart 1: Valuation Distribution Candle Chart
st.markdown("---")
st.subheader("Valuation Distribution by Bank")

# Sector selection above the chart
sector_options = ["Sector", "SOCB", "Private_1", "Private_2", "Private_3"]
selected_sector = st.selectbox(
    "Select Sector:",
    sector_options,
    help="Shows selected sector plus all component banks"
)

# Get tickers to display
display_tickers = get_sector_and_components(df, selected_sector)

# Create candle chart
fig_candle = go.Figure()

# Prepare data for each ticker
valid_tickers = []
for ticker in display_tickers:
    ticker_data = df[df['TICKER'] == ticker][metric_col].dropna()
    
    if len(ticker_data) < 20:  # Skip if insufficient data
        continue
    
    valid_tickers.append(ticker)
    
    # Calculate percentiles with smart outlier handling
    # First, identify extreme outliers (e.g., P/E > 100 when median is 20)
    median_val = ticker_data.median()
    
    # Only exclude extreme outliers (values more than 5x the median)
    if metric_type == "P/E":
        # For P/E, be more aggressive with outlier removal
        upper_limit = min(100, median_val * 5) if median_val > 0 else 100
        clean_data = ticker_data[ticker_data <= upper_limit]
    else:
        # For P/B, be more lenient
        upper_limit = median_val * 4 if median_val > 0 else 10
        clean_data = ticker_data[ticker_data <= upper_limit]
    
    # Ensure we still have enough data
    if len(clean_data) < 20:
        clean_data = ticker_data  # Use original if too much was filtered
    
    # Calculate percentiles for candle
    p5 = clean_data.quantile(0.05)
    p25 = clean_data.quantile(0.25)
    p50 = clean_data.quantile(0.50)
    p75 = clean_data.quantile(0.75)
    p95 = clean_data.quantile(0.95)
    
    # Get current value
    current_val = ticker_data.iloc[-1] if len(ticker_data) > 0 else None
    
    # Add candlestick with light grey color
    fig_candle.add_trace(go.Candlestick(
        x=[ticker],
        open=[p25],
        high=[p95],  # Use p95 for upper wick
        low=[p5],    # Use p5 for lower wick
        close=[p75],
        name=ticker,
        showlegend=False,
        increasing_line_color='lightgrey',
        decreasing_line_color='lightgrey'
    ))
    
    # Add current value as scatter point with smaller size and custom color
    if current_val and not pd.isna(current_val):
        # Calculate percentile
        percentile = np.sum(clean_data <= current_val) / len(clean_data) * 100
        
        fig_candle.add_trace(go.Scatter(
            x=[ticker],
            y=[current_val],
            mode='markers',
            marker=dict(size=8, color='#478B81', symbol='circle'),
            name=f"{ticker} Current",
            showlegend=False,
            hovertemplate=(
                f"<b>{ticker}</b><br>" +
                f"Current: {current_val:.2f}<br>" +
                f"Percentile: {percentile:.1f}%<br>" +
                f"Median: {p50:.2f}<br>" +
                "<extra></extra>"
            )
        ))

# Update layout
fig_candle.update_layout(
    title=f"{metric_type} Distribution - {selected_sector}",
    xaxis_title="Bank",
    yaxis_title=f"{metric_type} Ratio",
    height=500,
    hovermode='x unified',
    xaxis=dict(
        categoryorder='array',
        categoryarray=valid_tickers  # Maintain order
    )
)

st.plotly_chart(fig_candle, use_container_width=True, config={'displayModeBar': False})

# Chart 2: Historical Valuation Time Series
st.markdown("---")
st.subheader("Historical Valuation Trend")

col1, col2 = st.columns([2, 8])

with col1:
    # Ticker selection for time series
    all_tickers = sorted(df['TICKER'].unique())
    selected_ticker = st.selectbox(
        "Select Bank/Sector:",
        all_tickers,
        index=all_tickers.index('Sector') if 'Sector' in all_tickers else 0
    )
    
    # Date range selection
    date_range = st.selectbox(
        "Time Period:",
        ["1 Year", "2 Years", "3 Years", "5 Years", "All Time"],
        index=2  # Default to 3 years
    )
    
    # Calculate date filter
    if date_range == "1 Year":
        start_date = latest_date - timedelta(days=365)
    elif date_range == "2 Years":
        start_date = latest_date - timedelta(days=730)
    elif date_range == "3 Years":
        start_date = latest_date - timedelta(days=1095)
    elif date_range == "5 Years":
        start_date = latest_date - timedelta(days=1825)
    else:
        start_date = df['TRADE_DATE'].min()

with col2:
    # Filter data for selected ticker and date range
    ticker_df = df[(df['TICKER'] == selected_ticker) & (df['TRADE_DATE'] >= start_date)].copy()
    ticker_df = ticker_df.sort_values('TRADE_DATE')
    
    if len(ticker_df) > 0:
        # Calculate statistics
        hist_stats = calculate_historical_stats(df, selected_ticker, metric_col)
        
        if hist_stats:
            # Create figure
            fig_ts = go.Figure()
            
            # Add main valuation line with custom color
            fig_ts.add_trace(go.Scatter(
                x=ticker_df['TRADE_DATE'],
                y=ticker_df[metric_col],
                mode='lines',
                name=f'{metric_type} Ratio',
                line=dict(color='#478B81', width=2)
            ))
            
            # Add mean line
            fig_ts.add_trace(go.Scatter(
                x=[ticker_df['TRADE_DATE'].min(), ticker_df['TRADE_DATE'].max()],
                y=[hist_stats['mean'], hist_stats['mean']],
                mode='lines',
                name='Mean',
                line=dict(color='black', width=2, dash='solid')
            ))
            
            # Add +1 SD line
            fig_ts.add_trace(go.Scatter(
                x=[ticker_df['TRADE_DATE'].min(), ticker_df['TRADE_DATE'].max()],
                y=[hist_stats['upper_1sd'], hist_stats['upper_1sd']],
                mode='lines',
                name='+1 SD',
                line=dict(color='red', width=1, dash='dash')
            ))
            
            # Add -1 SD line
            fig_ts.add_trace(go.Scatter(
                x=[ticker_df['TRADE_DATE'].min(), ticker_df['TRADE_DATE'].max()],
                y=[hist_stats['lower_1sd'], hist_stats['lower_1sd']],
                mode='lines',
                name='-1 SD',
                line=dict(color='green', width=1, dash='dash')
            ))
            
            # Add current value marker as small grey dot
            if hist_stats['current'] is not None:
                fig_ts.add_trace(go.Scatter(
                    x=[ticker_df['TRADE_DATE'].max()],
                    y=[hist_stats['current']],
                    mode='markers',
                    name='Current',
                    marker=dict(size=8, color='grey', symbol='circle')
                ))
            
            # Update layout
            fig_ts.update_layout(
                title=f"{selected_ticker} - {metric_type} Historical Trend",
                xaxis_title="Date",
                yaxis_title=f"{metric_type} Ratio",
                height=500,
                hovermode='x unified',
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            st.plotly_chart(fig_ts, use_container_width=True)
            
            # Show statistics
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            with col_stat1:
                st.metric("Current", f"{hist_stats['current']:.2f}" if hist_stats['current'] else "N/A")
            with col_stat2:
                st.metric("Mean", f"{hist_stats['mean']:.2f}")
            with col_stat3:
                st.metric("Std Dev", f"{hist_stats['std']:.2f}")
            with col_stat4:
                z_score = hist_stats.get('z_score')
                if z_score is not None:
                    status, color = get_valuation_status(z_score)
                    st.metric("Z-Score", f"{z_score:.2f}", delta=status)
    else:
        st.warning(f"No data available for {selected_ticker}")

# Table 3: Valuation Statistics Table
st.markdown("---")
st.subheader("Valuation Statistics Summary")

# Prepare statistics table
stats_df = prepare_statistics_table(df, metric_col)

if not stats_df.empty:
    # Format the dataframe for display
    display_df = stats_df.copy()
    
    # Format numeric columns
    for col in ['Current', 'Mean']:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
    
    if 'CDF (%)' in display_df.columns:
        display_df['CDF (%)'] = display_df['CDF (%)'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A")
    
    if 'Z-Score' in display_df.columns:
        display_df['Z-Score'] = display_df['Z-Score'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
    
    # Define pastel colors for status
    def color_status(val):
        if val == "Very Cheap":
            return 'background-color: #90EE90; color: black'  # Light green
        elif val == "Cheap":
            return 'background-color: #B8E6B8; color: black'  # Lighter green
        elif val == "Fair":
            return 'background-color: #FFFFCC; color: black'  # Light yellow
        elif val == "Expensive":
            return 'background-color: #FFD4A3; color: black'  # Light orange
        elif val == "Very Expensive":
            return 'background-color: #FFB3B3; color: black'  # Light red
        return ''
    
    # Function to highlight sector rows
    def highlight_sectors(row):
        if row['Ticker'] in ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']:
            return ['background-color: #E8E8E8; font-weight: bold'] * len(row)
        return [''] * len(row)
    
    # Apply styling
    styled_df = display_df.style.apply(highlight_sectors, axis=1).applymap(color_status, subset=['Status'])
    
    # Display table
    st.dataframe(
        styled_df,
        use_container_width=True,
        height=600
    )
    
    # Summary statistics
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        cheap_count = len(stats_df[stats_df['Status'].isin(['Very Cheap', 'Cheap'])])
        st.metric("Undervalued Banks", cheap_count)
    
    with col2:
        fair_count = len(stats_df[stats_df['Status'] == 'Fair'])
        st.metric("Fairly Valued Banks", fair_count)
    
    with col3:
        expensive_count = len(stats_df[stats_df['Status'].isin(['Expensive', 'Very Expensive'])])
        st.metric("Overvalued Banks", expensive_count)
else:
    st.warning("Insufficient data to generate statistics table")

# Footer
st.markdown("---")
st.caption("Data updated through: " + latest_date.strftime('%Y-%m-%d'))
st.caption("Note: Valuations are based on historical distributions. Past performance does not guarantee future results.")