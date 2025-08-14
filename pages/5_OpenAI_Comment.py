import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os
from dotenv import load_dotenv

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import utilities
from utilities.quarter_utils import quarter_sort_key, sort_quarters
from utilities.openai_comments import openai_comment

# Load environment variables
load_dotenv()

# Load your data (same as main file)
# Cache version: increment this when data structure changes to force cache refresh
CACHE_VERSION = 3  # Incremented to force cache refresh for EVF sector fix

@st.cache_data
def load_data(version=CACHE_VERSION):
    df_quarter = pd.read_csv(os.path.join(project_root, 'Data/dfsectorquarter.csv'))
    df_year = pd.read_csv(os.path.join(project_root, 'Data/dfsectoryear.csv'))
    keyitem = pd.read_excel(os.path.join(project_root, 'Data/Key_items.xlsx'))
    bank_type = pd.read_excel(os.path.join(project_root, 'Data/Bank_Type.xlsx'))
    return df_quarter, df_year, keyitem, bank_type

df_quarter, df_year, keyitem, bank_type_mapping = load_data()
color_sequence = px.colors.qualitative.Bold

def get_ticker_sector(ticker, df_quarter, bank_type_mapping):
    """Get sector for a ticker with fallback logic"""
    # First try to get from df_quarter
    ticker_data = df_quarter[df_quarter['TICKER'] == ticker]
    if not ticker_data.empty and 'Type' in ticker_data.columns:
        sector = ticker_data['Type'].iloc[0]
        if pd.notna(sector) and sector != 'nan':
            return sector
    
    # Fallback to Bank_Type.xlsx mapping
    if ticker in bank_type_mapping['TICKER'].values:
        bank_row = bank_type_mapping[bank_type_mapping['TICKER'] == ticker].iloc[0]
        if 'Type' in bank_row and pd.notna(bank_row['Type']):
            return bank_row['Type']
    
    # If ticker is a sector itself (like "Sector", "SOCB", etc.)
    if len(ticker) > 3:
        return ticker
    
    return "Unknown"

# Page configuration
st.set_page_config(
    page_title="OpenAI Comment",
    page_icon="AI",
    layout="wide"
)

# Set session state variables for the imported function
st.session_state.df_quarter = df_quarter
st.session_state.keyitem = keyitem

st.title("AI-Powered Banking Analysis")
st.markdown("Generate intelligent banking analysis using OpenAI with cached results for faster access")

# Add cache control in sidebar
with st.sidebar:
    if st.button("Clear Data Cache", help="Click to refresh cached data if you see old values"):
        st.cache_data.clear()
        st.success("Cache cleared! Page will reload with fresh data.")
        st.rerun()

# Check if comments cache exists
comments_file = os.path.join(project_root, 'Data/banking_comments.xlsx')
cache_exists = os.path.exists(comments_file)


# Main interface
st.subheader("Generate Banking Analysis")

# Define options - include all unique tickers (banks and sectors)
tickers = sorted([x for x in df_quarter['TICKER'].unique() if isinstance(x, str) and x.strip()])

# Sort quarters properly using utilities function (newest first)
available_quarters = sort_quarters(df_quarter['Date_Quarter'].unique(), reverse=True)

# Input controls
col1, col2, col3 = st.columns(3)

with col1:
    ticker = st.selectbox(
        "Select Ticker:", 
        tickers, 
        index=tickers.index('ACB') if 'ACB' in tickers else 0,
        help="Choose a bank or sector ticker to analyze"
    )

with col2:
    selected_quarter = st.selectbox(
        "Select Quarter:", 
        available_quarters, 
        index=0,
        help="Choose the quarter to view or generate analysis for"
    )

with col3:
    force_regenerate = st.checkbox(
        "Force Regenerate", 
        value=False,
        help="Bypass cache and generate new analysis (costs API credits)"
    )

# Show ticker information if available
if ticker:
    ticker_data = df_quarter[df_quarter['TICKER'] == ticker]
    if not ticker_data.empty:
        # Get sector from the database for this ticker using fallback logic
        ticker_sector = get_ticker_sector(ticker, df_quarter, bank_type_mapping)
        
        # Check if data exists for selected quarter
        quarter_data = ticker_data[ticker_data['Date_Quarter'] == selected_quarter]
        quarter_status = "Available" if not quarter_data.empty else "No data"
        
        st.info(f"**{ticker}** | Quarter: **{selected_quarter}** ({quarter_status}) | Sector: **{ticker_sector}**")
        
        # Check if cached analysis exists for this ticker and quarter
        if cache_exists and not force_regenerate:
            try:
                cached_comments = pd.read_excel(comments_file)
                ticker_cache = cached_comments[
                    (cached_comments['TICKER'] == ticker) & 
                    (cached_comments['QUARTER'] == selected_quarter)
                ]
                if not ticker_cache.empty:
                    latest_cached = ticker_cache.iloc[-1]
                    # Safely extract date part
                    try:
                        generated_date = pd.to_datetime(latest_cached['GENERATED_DATE']).strftime('%Y-%m-%d')
                    except:
                        generated_date = str(latest_cached['GENERATED_DATE'])[:10] if len(str(latest_cached['GENERATED_DATE'])) >= 10 else str(latest_cached['GENERATED_DATE'])
                    
                    st.success(f"Cached analysis available for {ticker} - {selected_quarter} "
                             f"(Generated: {generated_date})")
                    
                    # Display the cached comment
                    st.subheader(f"Analysis for {ticker} - {selected_quarter}")
                    st.markdown(latest_cached['COMMENT'])
                else:
                    st.warning(f"No cached analysis found for {ticker} - {selected_quarter}. Will generate new analysis.")
            except Exception as e:
                st.warning(f"Could not check cache: {e}")
    else:
        st.error(f"No data found for ticker {ticker}")

# Generate button
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    generate_button = st.button("Generate Analysis", type="primary")

with col2:
    if cache_exists:
        view_cache_button = st.button("View All Cached", help="View all cached analyses")
    else:
        view_cache_button = False

# Generation logic
if generate_button and ticker and selected_quarter:
    # Get sector from database using fallback logic
    ticker_data = df_quarter[df_quarter['TICKER'] == ticker]
    if not ticker_data.empty:
        sector = get_ticker_sector(ticker, df_quarter, bank_type_mapping)
        
        # Check if data exists for the selected quarter
        quarter_data = ticker_data[ticker_data['Date_Quarter'] == selected_quarter]
        if quarter_data.empty:
            st.error(f"No data available for {ticker} in quarter {selected_quarter}. Please select a different quarter.")
        else:
            with st.spinner(f"Generating banking analysis for {ticker} - {selected_quarter}..."):
                try:
                    # Call the openai_comment function with force_regenerate parameter
                    openai_comment(
                        ticker=ticker, 
                        sector=sector, 
                        df_quarter=df_quarter,
                        keyitem=keyitem,
                        force_regenerate=force_regenerate
                    )
                except Exception as e:
                    st.error(f"Error generating analysis: {e}")
                    st.info("Please check your OpenAI API key and try again.")
    else:
        st.error(f"No data found for ticker {ticker}")

# View cached comments
if view_cache_button:
    st.switch_page("pages/4_Comment_Management.py")
