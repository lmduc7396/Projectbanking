import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Company Table",
    page_icon="Table",
    layout="wide"
)

import pandas as pd
import plotly.express as px
import numpy as np
import sys
import os

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import from utilities
from utilities.style_utils import apply_google_font
from utilities.sidebar_style import apply_sidebar_style
from utilities.data_access import load_banking_metrics, load_banking_forecast

# Apply Google Fonts
apply_google_font()

# Apply consistent sidebar styling
apply_sidebar_style()

# Import from utilities
from utilities.banking_table import Banking_table
from utilities.stock_candle import Stock_price_plot

# Load your data (same as main file)
@st.cache_data(ttl=3600)
def load_data():
    df_quarter = load_banking_metrics('Q')
    df_year = load_banking_metrics('Y')

    df_forecast = load_banking_forecast()
    if df_forecast.empty:
        df_forecast = None

    keyitem = pd.read_excel(os.path.join(project_root, 'Data/Key_items.xlsx'))
    return df_quarter, df_year, df_forecast, keyitem

df_quarter, df_year, df_forecast, keyitem = load_data()
color_sequence = px.colors.qualitative.Bold

forecast_years = []
if df_forecast is not None and not df_forecast.empty:
    forecast_years = sorted(
        pd.to_numeric(df_forecast['Year'], errors='coerce')
        .dropna()
        .astype(int)
        .unique()
    )

# Function to detect the last complete year from historical data
@st.cache_data(ttl=3600)  # Refresh cache every hour
def get_last_historical_year():
    """Detect the last completed historical year from prepared Parquet data (flexible, data-driven)."""
    years = pd.to_numeric(df_year.get('Year'), errors='coerce').dropna()
    if not years.empty:
        return int(years.max())

    years_quarter = pd.to_numeric(df_quarter.get('Year'), errors='coerce').dropna()
    if not years_quarter.empty:
        return int(years_quarter.max())

    from datetime import datetime
    return datetime.now().year - 1

# Get the last historical year
last_historical_year = get_last_historical_year()

# Sidebar: Choose database and forecast option
db_option = st.sidebar.radio("Choose database:", ("Quarterly", "Yearly"))

# Add forecast checkbox
include_forecast = st.sidebar.checkbox(
    "Include Forecast Data", 
    value=False,
    help="Show available forecast data in the table"
)

# Process data based on selections
if db_option == "Quarterly":
    df = df_quarter.copy()
    df['is_forecast'] = False

    if include_forecast and df_forecast is not None and forecast_years:
        df_forecast_quarterly = df_forecast.copy()
        df_forecast_quarterly['Year'] = pd.to_numeric(
            df_forecast_quarterly['Year'], errors='coerce'
        ).astype('Int64')
        df_forecast_quarterly['Date_Quarter'] = df_forecast_quarterly['Year'].apply(
            lambda x: f"{int(x)}" if pd.notna(x) else None
        )
        df_forecast_quarterly['Quarter'] = pd.NA
        df_forecast_quarterly['is_forecast'] = True
        df = pd.concat([df, df_forecast_quarterly], ignore_index=True)
else:
    df = df_year.copy()
    
    if include_forecast and df_forecast is not None and not df_forecast.empty:
        df['is_forecast'] = False
        df_forecast_copy = df_forecast.copy()
        df_forecast_copy['is_forecast'] = True
        df = pd.concat([df, df_forecast_copy], ignore_index=True)
    else:
        df['is_forecast'] = False
        if 'Year' in df.columns:
            df = df[df['Year'].isna() | (df['Year'] <= last_historical_year)]

# Conditional format function
def conditional_format(df):
    def human_format(num):
        try:
            num = float(num)
        except:
            return ""
        abs_num = abs(num)
        if abs_num >= 1_000_000_000:
            return f"{num/1_000_000_000:,.0f}"
        else:
            return f"{num:.1f}"
    
    def format_row(row):
        vals = pd.to_numeric(row, errors='coerce').values  # Ensures a NumPy array
        numeric_vals = vals[~np.isnan(vals)]
        if len(numeric_vals) == 0:
            return pd.Series([str(v) if v is not None else "" for v in row], index=row.index)
        median_val = np.median(np.abs(numeric_vals))
        if median_val > 100:
            return pd.Series([human_format(v) if pd.notnull(v) and v != '' else "" for v in row], index=row.index)
        else:
            return pd.Series(["{:.2f}%".format(float(v)*100) if pd.notnull(v) and v != '' else "" for v in row], index=row.index)
    # Apply formatting row-wise, axis=1
    formatted = df.apply(format_row, axis=1)
    return formatted

# Set session state variables for the imported functions
st.session_state.df = df
st.session_state.keyitem = keyitem
st.session_state.df_quarter = df_quarter
st.session_state.include_forecast = include_forecast
st.session_state.last_historical_year = last_historical_year
st.session_state.forecast_years = forecast_years

st.title("Company Table")
st.markdown("---")

# Show a note if forecast is included
if include_forecast:
    if forecast_years:
        year_label = ", ".join(str(year) for year in forecast_years)
        st.info(f"Forecast data ({year_label}) is included in the table")
    else:
        st.info("Forecast data is included in the table")

# --- Define User Selection Options ---
bank_type = ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']
tickers = sorted([x for x in df['TICKER'].unique() if isinstance(x, str) and len(x) == 3])
x_options = bank_type + tickers

col1, col2 = st.columns(2)
with col1:
    X = st.selectbox("Select Stock Ticker or Bank Type (X):", x_options)
with col2:
    Y = st.number_input("Number of latest periods to plot (Y):", min_value=1, max_value=20, value=6)

if len(X) == 3:
    Stock_price_plot(X)

# QoQ/YoY selection underneath the stock price plot
if db_option == "Quarterly":
    Z = st.selectbox("QoQ or YoY growth (Z):", ['QoQ', 'YoY'], index=0)
else:
    Z = st.selectbox("QoQ or YoY growth (Z):", ['YoY'], index=0)

df_table1, df_table2, forecast_columns = Banking_table(X, Y, Z, df, keyitem)

# Function to apply forecast column highlighting
def highlight_forecast_columns(df, forecast_cols):
    """Apply light background color to forecast columns"""
    def style_forecast(col):
        if str(col.name) in forecast_cols or (isinstance(col.name, (int, float)) and str(int(col.name)) in forecast_cols):
            return ['background-color: rgba(255, 255, 0, 0.1)'] * len(col)
        return [''] * len(col)
    
    return df.style.apply(style_forecast, axis=0)

# Format and display first table
st.subheader("Earnings metrics")
formatted1 = conditional_format(df_table1)

# Apply highlighting if there are forecast columns
if include_forecast and forecast_columns:
    st.write("*Highlighted columns show forecast data*")
    styled_df1 = highlight_forecast_columns(formatted1, forecast_columns)
    st.dataframe(styled_df1, use_container_width=True)
else:
    st.dataframe(formatted1, use_container_width=True)

# Format and display second table
st.subheader("Ratios")
formatted2 = conditional_format(df_table2)

# Apply highlighting if there are forecast columns
if include_forecast and forecast_columns:
    styled_df2 = highlight_forecast_columns(formatted2, forecast_columns)
    st.dataframe(styled_df2, use_container_width=True)
else:
    st.dataframe(formatted2, use_container_width=True)
