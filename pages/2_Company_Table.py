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
from utilities.quarter_utils import sort_quarters

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import from utilities
from utilities.style_utils import apply_google_font
from utilities.sidebar_style import apply_sidebar_style
from utilities.data_access import load_banking_metrics, load_banking_forecast


AGGREGATED_TYPES = ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']


SUM_AGG_COLUMNS = {
    'Loan',
    'TOI',
    'Provision expense',
    'PBT',
    'NPATMI',
    'Total Assets',
    'Total Equity',
    'Net Interest Income',
    'Deposit',
    'OPEX',
    'PPOP',
    'Fees Income',
    'Provision on Balance Sheet',
    'Write-off'
}


WEIGHTED_RATIO_METRICS = {
    'Loan yield': 'Loan',
    'NPL': 'Loan',
    'GROUP 2': 'Loan',
    'New NPL': 'Loan',
    'New G2': 'Loan',
    'NPL Coverage ratio': 'Loan',
    'Provision/ Total Loan': 'Loan'
}


def _first_valid(series: pd.Series):
    valid = series.dropna()
    if valid.empty:
        return pd.NA
    return valid.iloc[0]


def _safe_sum(series: pd.Series):
    if series.empty:
        return pd.NA
    total = series.sum(min_count=1)
    return total if not pd.isna(total) else pd.NA


def _ratio(group: pd.DataFrame, numerator: str, denominator: str):
    if numerator not in group.columns or denominator not in group.columns:
        return pd.NA
    num = _safe_sum(pd.to_numeric(group[numerator], errors='coerce'))
    den = _safe_sum(pd.to_numeric(group[denominator], errors='coerce'))
    if pd.isna(num) or pd.isna(den) or den == 0:
        return pd.NA
    return num / den


def _weighted_avg(group: pd.DataFrame, value_col: str, weight_col: str):
    if value_col not in group.columns or weight_col not in group.columns:
        return pd.NA
    values = pd.to_numeric(group[value_col], errors='coerce')
    weights = pd.to_numeric(group[weight_col], errors='coerce')
    mask = (~values.isna()) & (~weights.isna()) & (weights != 0)
    if not mask.any():
        return pd.NA
    total_weight = weights[mask].sum()
    if pd.isna(total_weight) or total_weight == 0:
        return pd.NA
    return (values[mask] * weights[mask]).sum() / total_weight


def _aggregate_subset(subset: pd.DataFrame, label: str, period_col: str, is_quarterly: bool) -> pd.DataFrame:
    if subset.empty:
        return pd.DataFrame()

    group_cols = [period_col]
    if 'is_forecast' in subset.columns:
        group_cols.append('is_forecast')

    aggregated_rows: list[dict] = []
    for keys, group in subset.groupby(group_cols, dropna=False):
        if isinstance(keys, tuple):
            period_value, is_forecast = keys
        else:
            period_value = keys
            is_forecast = False

        row = {
            'TICKER': label,
            'Type': label,
            period_col: period_value,
            'is_forecast': bool(is_forecast) if 'is_forecast' in subset.columns else False
        }

        if 'Year' in group.columns:
            row['Year'] = _first_valid(group['Year'])
        if 'Quarter' in group.columns:
            row['Quarter'] = _first_valid(group['Quarter'])
        if 'YEARREPORT' in group.columns:
            row['YEARREPORT'] = _first_valid(group['YEARREPORT'])
        if 'LENGTHREPORT' in group.columns:
            row['LENGTHREPORT'] = _first_valid(group['LENGTHREPORT'])
        if 'ENDDATE_x' in group.columns:
            row['ENDDATE_x'] = _first_valid(group['ENDDATE_x'])

        for col in SUM_AGG_COLUMNS:
            if col in group.columns:
                row[col] = _safe_sum(pd.to_numeric(group[col], errors='coerce'))

        row['ROA'] = _ratio(group, 'NPATMI', 'Total Assets')
        row['ROE'] = _ratio(group, 'NPATMI', 'Total Equity')
        row['NIM'] = _ratio(group, 'Net Interest Income', 'Loan')

        for metric, weight_col in WEIGHTED_RATIO_METRICS.items():
            row[metric] = _weighted_avg(group, metric, weight_col)

        aggregated_rows.append(row)

    result = pd.DataFrame(aggregated_rows)

    if result.empty:
        return result

    if is_quarterly and period_col == 'Date_Quarter':
        order = sort_quarters(result[period_col].astype(str).tolist())
        category = pd.Categorical(result[period_col].astype(str), categories=order, ordered=True)
        result = result.assign(_order=category).sort_values('_order').drop(columns=['_order'])
    else:
        result = result.sort_values(period_col)

    return result.reset_index(drop=True)


def rebuild_dynamic_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    df = df.copy()
    if 'is_forecast' not in df.columns:
        df['is_forecast'] = False

    period_col = 'Date_Quarter' if 'Date_Quarter' in df.columns else 'Year'
    is_quarterly = period_col == 'Date_Quarter'

    base_mask = df['TICKER'].astype(str).str.len() == 3
    base_df = df[base_mask].copy()

    actual_base = base_df[base_df['is_forecast'] == False]
    if actual_base.empty or actual_base[period_col].dropna().empty:
        return df

    period_series = actual_base[period_col].dropna().astype(str)
    if is_quarterly:
        ordered_periods = sort_quarters(period_series.unique().tolist())
        if not ordered_periods:
            return df
        latest_period_key = ordered_periods[-1]
    else:
        numeric_periods = pd.to_numeric(period_series, errors='coerce').dropna()
        if numeric_periods.empty:
            return df
        latest_period_key = str(int(numeric_periods.max()))

    dynamic_rows: list[pd.DataFrame] = []

    for label in AGGREGATED_TYPES:
        subset = base_df if label == 'Sector' else base_df[base_df['Type'] == label]
        if subset.empty:
            continue

        subset_latest = subset[
            (subset['is_forecast'] == False)
            & (subset[period_col].astype(str) == latest_period_key)
        ]
        coverage_tickers = subset_latest['TICKER'].unique()
        if coverage_tickers.size == 0:
            continue

        filtered = subset[
            subset['TICKER'].isin(coverage_tickers)
            & (subset[period_col].astype(str) == latest_period_key)
        ]

        aggregated = _aggregate_subset(filtered, label, period_col, is_quarterly)
        if aggregated.empty:
            continue

        aggregated = aggregated[aggregated[period_col].astype(str) == latest_period_key]
        if aggregated.empty:
            continue

        dynamic_rows.append(aggregated)

    if not dynamic_rows:
        return df

    replacement_rows = pd.concat(dynamic_rows, ignore_index=True)

    drop_mask = (
        df['TICKER'].isin(AGGREGATED_TYPES)
        & (df['is_forecast'] == False)
        & (df[period_col].astype(str) == latest_period_key)
    )

    preserved = df[~drop_mask].copy()
    combined = pd.concat([preserved, replacement_rows], ignore_index=True)

    if is_quarterly:
        order = sort_quarters(combined[period_col].dropna().astype(str).unique().tolist())
        category = pd.Categorical(combined[period_col].astype(str), categories=order, ordered=True)
        combined = (
            combined.assign(_order=category)
            .sort_values(['_order', 'TICKER'])
            .drop(columns=['_order'])
        )
    else:
        combined = combined.sort_values([period_col, 'TICKER'])

    return combined.reset_index(drop=True)

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

df = rebuild_dynamic_aggregates(df)

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
