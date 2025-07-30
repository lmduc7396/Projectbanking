#%%
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
import openai
import os
from dotenv import load_dotenv
import requests
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Banking Analysis Dashboard",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment variables
load_dotenv()

# Load your data
@st.cache_data
def load_data():
    df_quarter = pd.read_csv('Data/dfsectorquarter.csv')
    df_year = pd.read_csv('Data/dfsectoryear.csv')
    keyitem = pd.read_excel('Data/Key_items.xlsx')
    return df_quarter, df_year, keyitem

df_quarter, df_year, keyitem = load_data()
color_sequence = px.colors.qualitative.Bold

# Main page content
st.title("🏦 Banking Analysis Dashboard")
st.markdown("---")

st.markdown("""
### Welcome to the Banking Analysis Dashboard

This comprehensive dashboard provides tools for analyzing banking sector data with the following features:

#### 📊 **Banking Plot**
- Interactive visualization of banking metrics
- Compare multiple banks or bank types
- Customizable time periods and metrics
- Support for both quarterly and yearly data

#### 📋 **Company Table** 
- Detailed financial tables for individual banks or sectors
- Growth analysis (QoQ/YoY)
- Earnings metrics and financial ratios
- Stock price visualization for individual tickers

#### 🤖 **OpenAI Comment**
- AI-powered analysis and commentary
- Bank performance insights
- Sector comparison analysis
- Generate detailed reports using OpenAI

### How to Use
1. **Select a page** from the sidebar navigation
2. **Choose your database** (Quarterly or Yearly) in the sidebar
3. **Configure your analysis** using the interactive controls on each page

### Data Coverage
- **Quarterly Data**: Detailed quarterly financial statements
- **Yearly Data**: Annual financial performance
- **Bank Types**: Sector, SOCB, Private_1, Private_2, Private_3
- **Individual Tickers**: 3-letter bank codes

### Getting Started
👈 **Use the sidebar navigation** to explore different analysis tools and begin your banking sector analysis.
""")

# Display some summary statistics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="Total Banks (Quarterly)",
        value=len(df_quarter['TICKER'].unique())
    )

with col2:
    st.metric(
        label="Total Banks (Yearly)", 
        value=len(df_year['TICKER'].unique())
    )

with col3:
    st.metric(
        label="Available Metrics",
        value=len(keyitem)
    )

with col4:
    latest_quarter = df_quarter['Date_Quarter'].max() if not df_quarter.empty else "N/A"
    st.metric(
        label="Latest Quarter",
        value=latest_quarter
    )

# Display recent data preview
st.markdown("### 📈 Recent Data Overview")
if not df_quarter.empty:
    # Show latest quarter data for a few key metrics
    latest_data = df_quarter[df_quarter['Date_Quarter'] == df_quarter['Date_Quarter'].max()]
    key_metrics = ['TICKER', 'Type'] + keyitem['KeyCode'].head(5).tolist()
    available_metrics = [col for col in key_metrics if col in latest_data.columns]
    
    if len(available_metrics) > 2:
        preview_data = latest_data[available_metrics].head(10)
        st.dataframe(preview_data, use_container_width=True)
    else:
        st.info("Data preview not available - please check the data structure.")
else:
    st.warning("No quarterly data available.")

st.markdown("---")
st.markdown("**Ready to start your analysis?** Navigate to any page using the sidebar! 👈")

   
