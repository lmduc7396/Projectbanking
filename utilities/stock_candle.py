#%% Import libraries
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import requests
from datetime import datetime, timedelta

def fetch_historical_price(ticker: str, days: int = 365) -> pd.DataFrame:
    """Fetch stock historical price and volume data from TCBS API"""
    
    # TCBS API endpoint for historical data
    url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term"
    
    # Calculate from timestamp (days ago from now)
    from_timestamp = int((datetime.now() - timedelta(days=days)).timestamp())
    to_timestamp = int(datetime.now().timestamp())
    
    # Parameters for the stock
    params = {
        "ticker": ticker,
        "type": "stock",
        "resolution": "D",  # Daily data
        "from": str(from_timestamp),
        "to": str(to_timestamp)
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'data' in data and data['data']:
            # Convert to DataFrame for easier manipulation
            df = pd.DataFrame(data['data'])
            
            # Convert timestamp to datetime
            if 'tradingDate' in df.columns:
                # Check if tradingDate is already in ISO format
                if df['tradingDate'].dtype == 'object' and isinstance(df['tradingDate'].iloc[0], str) and 'T' in df['tradingDate'].iloc[0]:
                    df['tradingDate'] = pd.to_datetime(df['tradingDate'])
                else:
                    df['tradingDate'] = pd.to_datetime(df['tradingDate'], unit='ms')
            
            # Select relevant columns
            columns_to_keep = ['tradingDate', 'open', 'high', 'low', 'close', 'volume']
            df = df[[col for col in columns_to_keep if col in df.columns]]
            
            # Sort by date
            df = df.sort_values('tradingDate')
            
            return df
        else:
            return None
            
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from TCBS: {e}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_cached_stock_data(ticker: str, days: int = 365) -> pd.DataFrame:
    """Cached wrapper for fetch_historical_price to avoid excessive API calls"""
    return fetch_historical_price(ticker, days)

def Stock_price_plot(ticker: str):
    """Display candlestick chart with volume for a given ticker"""
    st.subheader(f"Stock Price Chart for {ticker}")
    
    # Add time period selector
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        period_options = {
            "1 Month": 30,
            "3 Months": 90,
            "6 Months": 180,
            "1 Year": 365,
            "2 Years": 730
        }
        selected_period = st.selectbox(
            "Select Time Period:",
            options=list(period_options.keys()),
            index=2,  # Default to 6 months
            key=f"period_{ticker}"
        )
        days = period_options[selected_period]
    
    with col2:
        if st.button("Refresh Data", key=f"refresh_{ticker}"):
            st.cache_data.clear()
            st.rerun()
    
    # Fetch data with loading spinner
    with st.spinner(f"Loading stock data for {ticker}..."):
        df = get_cached_stock_data(ticker, days)
    
    if df is not None and not df.empty:
        # Convert dates to strings for categorical x-axis (removes gaps)
        df['date_str'] = df['tradingDate'].dt.strftime('%Y-%m-%d')
        
        # Create subplots: candlestick on top, volume on bottom
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3],
            subplot_titles=(f'{ticker} Price', 'Volume')
        )
        
        # Add candlestick chart with string dates (no gaps)
        fig.add_trace(
            go.Candlestick(
                x=df['date_str'],  # Use string dates for categorical axis
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='Price',
                increasing_line_color='green',
                decreasing_line_color='red',
                hovertext=df['date_str'],  # Show date in hover
                hoverinfo='x+y+text'
            ),
            row=1, col=1
        )
        
        # Add volume bars
        colors = ['red' if row['close'] < row['open'] else 'green' 
                  for _, row in df.iterrows()]
        
        fig.add_trace(
            go.Bar(
                x=df['date_str'],  # Use string dates for categorical axis
                y=df['volume'],
                name='Volume',
                marker_color=colors,
                showlegend=False,
                hovertext=df['date_str'],  # Show date in hover
                hoverinfo='x+y+text'
            ),
            row=2, col=1
        )
        
        # Update layout
        fig.update_layout(
            title=f"{ticker} - Stock Price & Volume",
            height=600,
            showlegend=False,
            xaxis_rangeslider_visible=False,
            hovermode='x unified'
        )
        
        # Update x-axes to categorical (removes gaps for non-trading days)
        fig.update_xaxes(
            type='category',  # Categorical axis removes gaps
            title_text="Date", 
            row=2, col=1,
            tickangle=-45,  # Angle the dates for better readability
            nticks=20  # Limit number of ticks shown
        )
        
        # Update y-axes
        fig.update_yaxes(title_text="Price (VND)", row=1, col=1, tickformat=",.0f")
        fig.update_yaxes(title_text="Volume", row=2, col=1, tickformat=",.0f")
        
        # Display the chart
        st.plotly_chart(fig, use_container_width=True)
        
        # Show summary statistics
        with st.expander("View Statistics"):
            latest = df.iloc[-1]
            first = df.iloc[0]
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Latest Close",
                    f"{latest['close']:,.0f} VND",
                    f"{((latest['close'] - first['close']) / first['close'] * 100):.2f}%"
                )
            
            with col2:
                st.metric(
                    "Highest",
                    f"{df['high'].max():,.0f} VND"
                )
            
            with col3:
                st.metric(
                    "Lowest",
                    f"{df['low'].min():,.0f} VND"
                )
            
            with col4:
                avg_volume = df['volume'].mean()
                st.metric(
                    "Avg Volume",
                    f"{avg_volume:,.0f}"
                )
    else:
        # Show helpful message if no data
        st.warning(f"No stock price data available for {ticker}")
        st.info("""
        Possible reasons:
        - The ticker symbol might not be correct
        - The stock might not be listed on HOSE/HNX/UPCOM
        - Network connection issues
        
        Please verify the ticker symbol and try again.
        """)