#%% Import libraries
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

def Stock_price_plot(ticker):
    st.subheader(f"Stock Price Chart for {ticker}")
    
    try:
        df_quarter = st.session_state.get('df_quarter')
        if df_quarter is None:
            st.error("No quarterly data available")
            return
        
        ticker_data = df_quarter[df_quarter['TICKER'] == ticker].copy()
        
        if ticker_data.empty:
            st.warning(f"No data found for ticker {ticker}")
            return
        
        ticker_data = ticker_data.sort_values('Date_Quarter')
        
        if 'KeyCode011' in ticker_data.columns:
            prices = ticker_data['KeyCode011'].dropna()
            quarters = ticker_data.loc[prices.index, 'Date_Quarter']
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=quarters,
                y=prices,
                mode='lines+markers',
                name=f'{ticker} Stock Price',
                line=dict(color='#1f77b4', width=2),
                marker=dict(size=6)
            ))
            
            fig.update_layout(
                title=f"{ticker} Stock Price Trend",
                xaxis_title="Quarter",
                yaxis_title="Price",
                height=400,
                showlegend=True
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"Stock price data not available for {ticker}")
            
    except Exception as e:
        st.error(f"Error loading stock price data: {str(e)}")