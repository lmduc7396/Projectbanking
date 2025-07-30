import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import requests
import sys
import os

# Add the current directory to path to import FetchpriceAPI
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Import the fetch function
try:
    from FetchpriceAPI import fetch_historical_price
except ImportError:
    # Fallback implementation if FetchpriceAPI is not available
    def fetch_historical_price(ticker):
        st.error(f"Unable to fetch data for {ticker}. FetchpriceAPI module not found.")
        return None

def Stock_price_plot(X):
    # Fetch historical price data
    df = fetch_historical_price(X)
    if df is not None:
        # Filter data to show only last 2 years
        current_year = datetime.now().year
        two_years_ago = current_year - 2
        df['year'] = df['tradingDate'].dt.year
        df = df[df['year'] >= two_years_ago].copy()
        df = df.drop('year', axis=1)  # Remove the helper column
        
        # Create subplots with secondary y-axis for volume
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=(f'{X} Stock Price', 'Volume'),
            row_width=[0.2, 0.7]
        )
        
        # Add candlestick chart
        fig.add_trace(
            go.Candlestick(
                x=df['tradingDate'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='Price',
                increasing_line_color='green',
                decreasing_line_color='red'
            ),
            row=1, col=1
        )
        
        # Add volume bars
        fig.add_trace(
            go.Bar(
                x=df['tradingDate'],
                y=df['volume'],
                name='Volume',
                marker_color='lightblue',
                opacity=0.7
            ),
            row=2, col=1
        )
        
        # Update layout
        fig.update_layout(
            title=f'{X} Stock Analysis',
            xaxis_rangeslider_visible=False,
            height=600,
            showlegend=False
        )
        
        # Update y-axes
        fig.update_yaxes(title_text="Price (VND)", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        fig.update_xaxes(title_text="Date", row=2, col=1)
        
        # Display in Streamlit
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("No data available for plotting.")