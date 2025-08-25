import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import from utilities
from utilities.plot_chart import Bankplot

# Load your data (same as main file)
@st.cache_data(ttl=3600)  # Refresh cache every hour
def load_data():
    df_quarter = pd.read_csv(os.path.join(project_root, 'Data/dfsectorquarter.csv'))
    df_year = pd.read_csv(os.path.join(project_root, 'Data/dfsectoryear.csv'))
    
    # Load forecast data if it exists
    forecast_path = os.path.join(project_root, 'Data/dfsectorforecast.csv')
    df_forecast = None
    if os.path.exists(forecast_path):
        df_forecast = pd.read_csv(forecast_path)
    
    keyitem = pd.read_excel(os.path.join(project_root, 'Data/Key_items.xlsx'))
    return df_quarter, df_year, df_forecast, keyitem

df_quarter, df_year, df_forecast, keyitem = load_data()
color_sequence = px.colors.qualitative.Bold

# Page configuration
st.set_page_config(
    page_title="Banking Charts",
    page_icon="Chart",
    layout="wide"
)

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