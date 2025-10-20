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
from utilities.data_access import load_banking_metrics, load_banking_forecast


AGGREGATED_TYPES = ["Sector", "SOCB", "Private_1", "Private_2", "Private_3"]


def filter_incomplete_aggregates(
    combined_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    aggregated_labels: list[str],
) -> pd.DataFrame:
    """Drop aggregated rows for periods where component banks are incomplete."""

    if actual_df is None or actual_df.empty:
        return combined_df

    candidate_columns = ["Date_Quarter", "Year"]
    period_column = next((col for col in candidate_columns if col in actual_df.columns), None)
    if period_column is None:
        return combined_df

    if "TICKER" not in actual_df.columns or "Type" not in actual_df.columns:
        return combined_df

    bank_rows = actual_df[actual_df["TICKER"].astype(str).str.len() == 3].copy()
    if bank_rows.empty:
        return combined_df

    bank_rows = bank_rows.dropna(subset=[period_column])
    if bank_rows.empty:
        return combined_df

    bank_rows["Type"] = bank_rows["Type"].astype(str)
    bank_rows["period_key"] = bank_rows[period_column].astype(str)

    expected_counts = (
        bank_rows[bank_rows["Type"].isin(aggregated_labels)]
        .groupby("Type")["TICKER"]
        .nunique()
        .to_dict()
    )

    # Sector represents all banks irrespective of sub-type
    if "Sector" in aggregated_labels:
        expected_counts.setdefault("Sector", bank_rows["TICKER"].nunique())

    if not expected_counts:
        return combined_df

    reported_counts = (
        bank_rows[bank_rows["Type"].isin(expected_counts.keys())]
        .groupby(["Type", "period_key"])["TICKER"]
        .nunique()
    )

    if reported_counts.empty:
        return combined_df

    valid_periods: dict[str, set[str]] = {}
    for (agg_type, period_key), count in reported_counts.items():
        expected = expected_counts.get(agg_type)
        if expected and count >= expected:
            valid_periods.setdefault(agg_type, set()).add(period_key)

    if not valid_periods:
        return combined_df

    def _is_valid_row(row: pd.Series) -> bool:
        ticker = row.get("TICKER")
        if ticker not in aggregated_labels:
            return True
        if row.get("is_forecast") is True:
            return True
        period_value = row.get(period_column)
        if pd.isna(period_value):
            return False
        allowed_periods = valid_periods.get(ticker)
        if not allowed_periods:
            return False
        return str(period_value) in allowed_periods

    mask = combined_df.apply(_is_valid_row, axis=1)
    return combined_df[mask].reset_index(drop=True)

# Apply Google Fonts
apply_google_font()

# Apply consistent sidebar styling
apply_sidebar_style()

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

    # Fallback to current year - 1 as a flexible heuristic
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
    help="Show available forecast data with dotted lines"
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

        available_quarters = {}
        quarter_counts = (
            df.dropna(subset=['TICKER', 'Year', 'Quarter'])
            .groupby(['TICKER', 'Year'])['Quarter']
            .nunique()
        )
        for (ticker_key, year_key), count in quarter_counts.items():
            if pd.isna(year_key) or ticker_key is None:
                continue
            available_quarters[(ticker_key, int(year_key))] = int(count)

        income_expense_metrics = [
            'PBT', 'TOI', 'OPEX', 'PPOP', 'Provision expense',
            'NPATMI', 'Write-off', 'Fees Income'
        ]
        flow_metrics = ['New NPL', 'New G2']

        actual_quarter = df.copy()

        for ticker in df_forecast_quarterly['TICKER'].dropna().unique():
            ticker_mask = df_forecast_quarterly['TICKER'] == ticker

            for idx, year in enumerate(forecast_years):
                year_mask = ticker_mask & (df_forecast_quarterly['Year'] == year)
                if not year_mask.any():
                    continue

                if idx == 0:
                    qtrs_available = available_quarters.get((ticker, year), 0)
                    remaining_qtrs = max(4 - qtrs_available, 1)

                    for metric in income_expense_metrics:
                        if metric in df_forecast_quarterly.columns:
                            forecast_series = pd.to_numeric(
                                df_forecast_quarterly.loc[year_mask, metric],
                                errors='coerce'
                            ).fillna(0.0)
                            if forecast_series.empty:
                                continue
                            ytd_mask = (
                                (actual_quarter['TICKER'] == ticker)
                                & (actual_quarter['Year'] == year)
                            )
                            if metric in actual_quarter.columns:
                                ytd_series = pd.to_numeric(
                                    actual_quarter.loc[ytd_mask, metric],
                                    errors='coerce'
                                ).fillna(0.0)
                                ytd_sum = float(ytd_series.sum())
                            else:
                                ytd_sum = 0.0
                            if not forecast_series.empty:
                                annual_value = float(forecast_series.iloc[0])
                                adjusted_value = (annual_value - ytd_sum) / remaining_qtrs
                                df_forecast_quarterly.loc[year_mask, metric] = adjusted_value
                else:
                    for metric in income_expense_metrics:
                        if metric in df_forecast_quarterly.columns:
                            forecast_series = pd.to_numeric(
                                df_forecast_quarterly.loc[year_mask, metric],
                                errors='coerce'
                            ).fillna(0.0)
                            df_forecast_quarterly.loc[year_mask, metric] = forecast_series / 4

                for metric in flow_metrics:
                    if metric in df_forecast_quarterly.columns:
                        flow_series = pd.to_numeric(
                            df_forecast_quarterly.loc[year_mask, metric],
                            errors='coerce'
                        ).fillna(0.0)
                        df_forecast_quarterly.loc[year_mask, metric] = flow_series / 4

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

df = filter_incomplete_aggregates(
    df,
    df_quarter if db_option == "Quarterly" else df_year,
    AGGREGATED_TYPES,
)

# Make the data available globally for the Bankplot function
st.session_state.df = df
st.session_state.keyitem = keyitem
st.session_state.include_forecast = include_forecast
st.session_state.last_historical_year = last_historical_year
st.session_state.forecast_years = forecast_years

st.title("Banking Plot")
st.markdown("---")

# Show a note if forecast is included
if include_forecast:
    if forecast_years:
        year_label = ", ".join(str(year) for year in forecast_years)
        st.info(f"📊 Forecast data ({year_label}) is shown with dotted lines")
    else:
        st.info("📊 Forecast data is shown with dotted lines")

# Call the banking plot function
Bankplot(df, keyitem)
