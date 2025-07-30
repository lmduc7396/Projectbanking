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
from utilities import quarter_sort_key, sort_quarters

# Import the function
streamlit_pages_path = os.path.join(project_root, "Streamlit pages")
sys.path.append(streamlit_pages_path)

# Import using importlib
import importlib.util
try:
    spec = importlib.util.spec_from_file_location("openaicomments", os.path.join(streamlit_pages_path, "OpenAIcomments_new.py"))
    openai_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(openai_module)
    openai_comment = openai_module.openai_comment
except Exception as e:
    st.error(f"Error loading OpenAI module: {e}")
    # Create a fallback function
    def openai_comment(ticker, sector, df_quarter=None, keyitem=None, force_regenerate=False):
        st.info("OpenAI analysis is temporarily unavailable.")

# Load environment variables
load_dotenv()

# Load your data (same as main file)
@st.cache_data
def load_data():
    df_quarter = pd.read_csv(os.path.join(project_root, 'Data/dfsectorquarter.csv'))
    df_year = pd.read_csv(os.path.join(project_root, 'Data/dfsectoryear.csv'))
    keyitem = pd.read_excel(os.path.join(project_root, 'Data/Key_items.xlsx'))
    return df_quarter, df_year, keyitem

df_quarter, df_year, keyitem = load_data()
color_sequence = px.colors.qualitative.Bold

# Page configuration
st.set_page_config(
    page_title="OpenAI Comment",
    page_icon="🤖",
    layout="wide"
)

# Set session state variables for the imported function
st.session_state.df_quarter = df_quarter
st.session_state.keyitem = keyitem

st.title("🤖 AI-Powered Banking Analysis")
st.markdown("Generate intelligent banking analysis using OpenAI with cached results for faster access")

# Check if comments cache exists
comments_file = os.path.join(project_root, 'Data/banking_comments.xlsx')
cache_exists = os.path.exists(comments_file)


# Main interface
st.subheader("Generate Banking Analysis")

# Define options
tickers = sorted([x for x in df_quarter['TICKER'].unique() if isinstance(x, str) and len(x) == 3])

# Sort quarters properly using utilities function
available_quarters = sort_quarters(df_quarter['Date_Quarter'].unique())

# Input controls
col1, col2, col3 = st.columns(3)

with col1:
    ticker = st.selectbox(
        "Select Bank Ticker:", 
        tickers, 
        index=tickers.index('ACB') if 'ACB' in tickers else 0,
        help="Choose a bank ticker to analyze"
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
        # Get sector from the database for this ticker
        ticker_sector = ticker_data['Type'].iloc[0] if not ticker_data.empty else "Unknown"
        
        # Check if data exists for selected quarter
        quarter_data = ticker_data[ticker_data['Date_Quarter'] == selected_quarter]
        quarter_status = "✅ Available" if not quarter_data.empty else "❌ No data"
        
        st.info(f"📊 **{ticker}** | Quarter: **{selected_quarter}** ({quarter_status}) | Sector: {ticker_sector}")
        
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
                    
                    st.success(f"✅ Cached analysis available for {ticker} - {selected_quarter} "
                             f"(Generated: {generated_date})")
                    
                    # Display the cached comment
                    st.subheader(f"📝 Analysis for {ticker} - {selected_quarter}")
                    st.markdown(latest_cached['COMMENT'])
                else:
                    st.warning(f"⚠️ No cached analysis found for {ticker} - {selected_quarter}. Will generate new analysis.")
            except Exception as e:
                st.warning(f"Could not check cache: {e}")
    else:
        st.error(f"No data found for ticker {ticker}")

# Generate button
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    generate_button = st.button("🚀 Generate Analysis", type="primary")

with col2:
    if cache_exists:
        view_cache_button = st.button("👁️ View All Cached", help="View all cached analyses")
    else:
        view_cache_button = False

# Generation logic
if generate_button and ticker and selected_quarter:
    # Get sector from database
    ticker_data = df_quarter[df_quarter['TICKER'] == ticker]
    if not ticker_data.empty:
        sector = ticker_data['Type'].iloc[0]
        
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
    st.switch_page("pages/4_🔧_Comment_Management.py")
