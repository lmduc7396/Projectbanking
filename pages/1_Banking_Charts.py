import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os

# Page configuration - MUST BE FIRST STREAMLIT COMMAND
st.set_page_config(
    page_title="Banking Charts",
    page_icon="Chart",
    layout="wide"
)

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import from utilities
from utilities.plot_chart import Bankplot
from utilities.style_utils import apply_google_font
from utilities.sidebar_style import apply_sidebar_style

# Apply Google Fonts
apply_google_font()

# Apply consistent sidebar styling
apply_sidebar_style()

# Load your data (same as main file)
@st.cache_data(ttl=3600)  # Refresh cache every hour
def load_data():
    df_quarter = pd.read_parquet(os.path.join(project_root, 'Data/dfsectorquarter.parquet'))
    df_year = pd.read_parquet(os.path.join(project_root, 'Data/dfsectoryear.parquet'))
    
    # Load forecast data if it exists
    forecast_path = os.path.join(project_root, 'Data/dfsectorforecast.parquet')
    df_forecast = None
    if os.path.exists(forecast_path):
        df_forecast = pd.read_parquet(forecast_path)
    
    keyitem = pd.read_excel(os.path.join(project_root, 'Data/Key_items.xlsx'))
    return df_quarter, df_year, df_forecast, keyitem

df_quarter, df_year, df_forecast, keyitem = load_data()
color_sequence = px.colors.qualitative.Bold

# Function to detect the last complete year from historical data
@st.cache_data(ttl=3600)  # Refresh cache every hour
def get_last_historical_year():
    """Detect the last complete year (LENGTHREPORT=5) from original historical data"""
    try:
        # Read original IS data to find the last complete year
        dfis = pd.read_csv(os.path.join(project_root, 'Data/IS_Bank.csv'))
        # Find years that have LENGTHREPORT=5 (complete year data)
        complete_years = dfis[dfis['LENGTHREPORT'] == 5]['YEARREPORT'].unique()
        if len(complete_years) > 0:
            return int(max(complete_years))
        else:
            # Fallback: use 2024 if no complete year data found
            return 2024
    except:
        # Fallback if file reading fails
        return 2024

# Get the last historical year
last_historical_year = get_last_historical_year()

# Sidebar: Choose database and forecast option
db_option = st.sidebar.radio("Choose database:", ("Quarterly", "Yearly"))

# Add forecast checkbox
include_forecast = st.sidebar.checkbox(
    "Include Forecast Data", 
    value=False,
    help="Show forecast data (2025-2026) with dotted lines"
)

# Process data based on selections
if db_option == "Quarterly":
    df = df_quarter.copy()
    
    # If forecast is included and available, append yearly forecast to quarterly data
    if include_forecast and df_forecast is not None:
        # For quarterly view, append yearly forecast data directly
        # The forecast data will show as years (2025, 2026) after quarters
        # Rename Year column to Date_Quarter for consistency
        df_forecast_quarterly = df_forecast.copy()
        df_forecast_quarterly['Date_Quarter'] = df_forecast_quarterly['Year'].astype(str)
        
        # Get forecast years dynamically
        forecast_years = sorted(df_forecast_quarterly['Year'].unique())
        
        # Identify available quarters for each year in the quarterly data
        # Parse year from Date_Quarter format (e.g., "2025-Q1" -> 2025)
        df['Year_from_quarter'] = df['Date_Quarter'].str.extract(r'(\d{4})-Q', expand=False).astype(float)
        
        # For each forecast year, count available quarters
        available_quarters = {}
        for year in forecast_years:
            year_int = int(year)
            quarters_in_year = df[df['Year_from_quarter'] == year_int]['Date_Quarter'].nunique()
            available_quarters[year] = quarters_in_year
        
        # Clean up temporary column
        df = df.drop('Year_from_quarter', axis=1)
        
        # Define metrics that need quarterly adjustment (income/expense flow metrics)
        income_expense_metrics = ['PBT', 'TOI', 'OPEX', 'PPOP', 'Provision expense', 
                                  'NPATMI', 'Write-off', 'Fees Income']
        
        # For flow/formation metrics, divide annual values by 4 to get quarterly average
        # This applies only to "New NPL" and "New G2" which are cumulative annual metrics
        flow_metrics = ['New NPL', 'New G2']
        
        # Process adjustments for each ticker
        for ticker in df_forecast_quarterly['TICKER'].unique():
            ticker_mask = df_forecast_quarterly['TICKER'] == ticker
            
            for i, year in enumerate(forecast_years):
                year_mask = ticker_mask & (df_forecast_quarterly['Year'] == year)
                
                if i == 0:  # First forecast year (e.g., 2025)
                    # Calculate remaining quarters
                    qtrs_available = available_quarters.get(year, 0)
                    remaining_qtrs = max(4 - qtrs_available, 1)  # At least 1 to avoid division by 0
                    
                    # For income/expense metrics, calculate remaining quarter average
                    for metric in income_expense_metrics:
                        if metric in df_forecast_quarterly.columns:
                            # Get YTD sum from quarterly data for this ticker and year
                            year_int = int(year)
                            ytd_mask = (df['TICKER'] == ticker) & \
                                      (df['Date_Quarter'].str.contains(str(year_int)))
                            ytd_sum = df.loc[ytd_mask, metric].sum() if metric in df.columns else 0
                            
                            # Adjust forecast value: (Annual - YTD) / remaining quarters
                            annual_value = df_forecast_quarterly.loc[year_mask, metric].values
                            if len(annual_value) > 0:
                                adjusted_value = (annual_value[0] - ytd_sum) / remaining_qtrs
                                df_forecast_quarterly.loc[year_mask, metric] = adjusted_value
                else:  # Second forecast year (e.g., 2026)
                    # Simply divide by 4 for quarterly average
                    for metric in income_expense_metrics:
                        if metric in df_forecast_quarterly.columns:
                            df_forecast_quarterly.loc[year_mask, metric] = \
                                df_forecast_quarterly.loc[year_mask, metric] / 4
                
                # Handle flow metrics (New NPL, New G2) - always divide by 4
                for metric in flow_metrics:
                    if metric in df_forecast_quarterly.columns:
                        df_forecast_quarterly.loc[year_mask, metric] = \
                            df_forecast_quarterly.loc[year_mask, metric] / 4
        
        # Add is_forecast flag
        df['is_forecast'] = False
        df_forecast_quarterly['is_forecast'] = True
        
        # Combine the dataframes
        df = pd.concat([df, df_forecast_quarterly], ignore_index=True)
else:
    df = df_year.copy()
    
    if include_forecast and df_forecast is not None:
        # For yearly view, combine historical and forecast
        df['is_forecast'] = False
        df_forecast['is_forecast'] = True
        df = pd.concat([df, df_forecast], ignore_index=True)
    else:
        # Filter out any forecast years if not including forecast
        df = df[df['Year'] <= last_historical_year]
        df['is_forecast'] = False

# Make the data available globally for the Bankplot function
st.session_state.df = df
st.session_state.keyitem = keyitem
st.session_state.include_forecast = include_forecast
st.session_state.last_historical_year = last_historical_year

st.title("Banking Plot")
st.markdown("---")

# Show a note if forecast is included
if include_forecast:
    st.info("📊 Forecast data (2025-2026) is shown with dotted lines")

# Call the banking plot function
Bankplot(df, keyitem)