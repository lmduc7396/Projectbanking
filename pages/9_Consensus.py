import streamlit as st
import pandas as pd
import numpy as np
import re
import sys
import os

# Page configuration
st.set_page_config(
    page_title="Consensus Forecast",
    page_icon="📈",
    layout="wide"
)

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from utilities.style_utils import apply_google_font
from utilities.sidebar_style import apply_sidebar_style
import importlib
import utilities.data_access as data_access

# Ensure latest data access helpers are available when running in long-lived sessions
if not hasattr(data_access, 'load_forecast_consensus'):
    data_access = importlib.reload(data_access)

if not hasattr(data_access, 'load_forecast_consensus'):
    st.error("`load_forecast_consensus` is not available. Please update `utilities/data_access.py`.")
    st.stop()

load_forecast_consensus = data_access.load_forecast_consensus
load_banking_forecast = data_access.load_banking_forecast

# Apply styling
apply_google_font()
apply_sidebar_style()


def _normalize_metric_label(value: str) -> str:
    label = str(value) if value is not None else ""
    label = label.replace("_", " ").strip()
    if not label:
        return "Unknown"
    return label


def _normalize_metric_key(value: str) -> str:
    label = str(value) if value is not None else ""
    return re.sub(r"[^A-Za-z0-9]", "", label).upper()


@st.cache_data(ttl=1800)
def load_data():
    consensus_df = load_forecast_consensus()
    forecast_df = load_banking_forecast('Y')
    return consensus_df, forecast_df


consensus_df, forecast_df = load_data()


def _banking_tickers_from_forecast(df: pd.DataFrame) -> list[str]:
    if df.empty or 'TICKER' not in df.columns:
        return []
    tickers = [
        t.strip() for t in df['TICKER'].dropna().astype(str).unique()
        if isinstance(t, str) and t.strip()
    ]
    banking = [t for t in tickers if len(t) == 3 and t.isalpha()]
    return sorted(banking)


banking_tickers = _banking_tickers_from_forecast(forecast_df)
if banking_tickers:
    consensus_df = consensus_df[consensus_df['TICKER'].isin(banking_tickers)]

if consensus_df.empty:
    st.warning("No consensus data available for banking tickers.")
    st.stop()

st.title("Broker Consensus vs In-house Forecast")
st.markdown("Analyze the latest broker projections, consensus statistics, and how they compare with your current forecast.")

if consensus_df.empty:
    st.warning("Consensus database is empty. Please refresh the data pipeline and try again.")
    st.stop()


def preprocess_consensus(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data['FORECASTDATE'] = pd.to_datetime(data['FORECASTDATE'], errors='coerce')
    data['DATE'] = pd.to_datetime(data['DATE'], errors='coerce')
    data['KEYCODE'] = data['KEYCODE'].astype(str)
    data['Metric'] = data['KEYCODE'].str.split('.', n=1).str[-1]
    data.loc[data['Metric'] == data['KEYCODE'], 'Metric'] = data['KEYCODENAME']
    data['Metric'] = data['Metric'].fillna(data['KEYCODENAME'])
    data['Metric'] = data['Metric'].apply(_normalize_metric_label)
    data['MetricKey'] = data['Metric'].apply(_normalize_metric_key)
    keycode_year = pd.to_numeric(data['KEYCODE'].str.extract(r'(\d{4})')[0], errors='coerce')
    data['ForecastYear'] = keycode_year.astype('Int64')
    needs_year = data['ForecastYear'].isna() & data['DATE'].notna()
    data.loc[needs_year, 'ForecastYear'] = data.loc[needs_year, 'DATE'].dt.year
    data['ForecastYear'] = data['ForecastYear'].astype('Int64')
    data['EffectiveDate'] = data['FORECASTDATE'].where(data['FORECASTDATE'].notna(), data['DATE'])
    data['EffectiveDate'] = data['EffectiveDate'].fillna(pd.Timestamp.min)
    return data


consensus_df = preprocess_consensus(consensus_df)

available_tickers = sorted(x for x in consensus_df['TICKER'].dropna().unique())
if not available_tickers:
    st.warning("No tickers found in the consensus database.")
    st.stop()

with st.sidebar:
    st.header("Configure View")
    ticker = st.selectbox("Ticker", available_tickers, index=available_tickers.index('VCB') if 'VCB' in available_tickers else 0)

    ticker_data = consensus_df[consensus_df['TICKER'] == ticker]
    year_options = sorted(ticker_data['ForecastYear'].dropna().unique())
    default_years = year_options[-2:] if len(year_options) > 2 else year_options
    selected_years = st.multiselect(
        "Forecast Years",
        options=year_options,
        default=default_years if default_years else year_options
    )

    metric_options = sorted(ticker_data['Metric'].dropna().unique())
    default_metrics = [m for m in metric_options if _normalize_metric_key(m) in {
        'PBT', 'NPATMI', 'LOAN', 'NIM', 'NPL'
    }]
    if not default_metrics:
        default_metrics = metric_options
    selected_metrics = st.multiselect(
        "Metrics",
        options=metric_options,
        default=default_metrics if default_metrics else metric_options
    )

    st.markdown("---")
    st.caption("Latest record per broker × metric × year is displayed below.")

if selected_years:
    ticker_data = ticker_data[ticker_data['ForecastYear'].isin(selected_years)]

if selected_metrics:
    selected_metric_keys = {_normalize_metric_key(m) for m in selected_metrics}
    ticker_data = ticker_data[ticker_data['MetricKey'].isin(selected_metric_keys)]

if ticker_data.empty:
    st.info("No consensus entries match the selected filters.")
    st.stop()


BROKER_STOPWORDS = {
    'BUY', 'SELL', 'HOLD', 'OUTPERFORM', 'UNDERPERFORM', 'NEUTRAL', 'ADD',
    'OVERWEIGHT', 'UNDERWEIGHT', 'ACCUMULATE', 'REDUCE', 'OUTLOOK', 'FORECAST',
    'TARGET', 'PRICE', 'CONSENSUS'
}


def _extract_broker_label(row: pd.Series, ticker: str) -> str:
    raw_org = str(row.get('ORGANCODE') or '').strip()
    ticker_upper = ticker.upper()
    if raw_org and not raw_org.upper().startswith(ticker_upper):
        return raw_org

    keycodename = str(row.get('KEYCODENAME') or '')
    tokens = re.findall(r'[A-Z]{2,6}', keycodename.upper())
    for token in reversed(tokens):
        if token == ticker_upper:
            continue
        if token in BROKER_STOPWORDS:
            continue
        if token.isalpha() and len(token) >= 2:
            return token

    if raw_org:
        return raw_org
    return 'Unknown'


def latest_per_broker(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    work = df.copy()
    group_cols = ['ORGANCODE', 'MetricKey', 'ForecastYear']
    idx = work.groupby(group_cols, dropna=False)['EffectiveDate'].idxmax()
    latest = work.loc[idx].copy()
    latest = latest.sort_values(['ForecastYear', 'Metric', 'ORGANCODE']).reset_index(drop=True)
    latest['VALUE'] = pd.to_numeric(latest['VALUE'], errors='coerce')
    latest['Broker'] = latest.apply(lambda row: _extract_broker_label(row, ticker), axis=1)
    return latest


latest_consensus = latest_per_broker(ticker_data, ticker)

st.subheader("Latest Broker Forecasts")

rating_counts = latest_consensus['RATING'].dropna().value_counts().to_dict()
cols = st.columns(len(rating_counts) or 1)
if rating_counts:
    for (label, count), col in zip(rating_counts.items(), cols):
        col.metric(label, f"{int(count)} broker{'s' if count != 1 else ''}")
else:
    cols[0].info("No ratings submitted.")

display_cols = ['Broker', 'Metric', 'ForecastYear', 'VALUE', 'RATING', 'FORECASTDATE', 'DATE']
for c in ['FORECASTDATE', 'DATE']:
    latest_consensus[c] = pd.to_datetime(latest_consensus[c], errors='coerce')

latest_consensus_display = latest_consensus[display_cols].rename(columns={
    'ForecastYear': 'Year',
    'VALUE': 'Value',
    'RATING': 'Rating',
    'FORECASTDATE': 'Published',
    'DATE': 'Target Date'
})

for date_col in ['Published', 'Target Date']:
    latest_consensus_display[date_col] = latest_consensus_display[date_col].dt.date

latest_consensus_styler = latest_consensus_display.style.format({'Value': '{:,.2f}'})

st.dataframe(latest_consensus_styler, use_container_width=True)


def consensus_summary(df: pd.DataFrame) -> pd.DataFrame:
    aggregated = df.groupby(['Metric', 'MetricKey', 'ForecastYear']).agg(
        brokers=('ORGANCODE', 'nunique'),
        avg=('VALUE', 'mean'),
        median=('VALUE', 'median'),
        min=('VALUE', 'min'),
        max=('VALUE', 'max')
    ).reset_index()
    return aggregated


summary_df = consensus_summary(latest_consensus)


def prepare_inhouse_forecast(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    data = df[df['TICKER'] == ticker].copy()
    if data.empty:
        return data
    data['Year'] = pd.to_numeric(data.get('Year'), errors='coerce').astype('Int64')
    numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
    unwanted = {'Year', 'Quarter', 'is_forecast'}
    numeric_cols = [c for c in numeric_cols if c not in unwanted]
    if not numeric_cols:
        return pd.DataFrame()
    melted = data[['Year'] + numeric_cols].melt(id_vars='Year', var_name='Metric', value_name='OurForecast')
    melted = melted.dropna(subset=['Year', 'OurForecast'])
    melted['MetricKey'] = melted['Metric'].apply(_normalize_metric_key)
    return melted


our_forecast_long = prepare_inhouse_forecast(forecast_df, ticker)

comparison = summary_df.merge(
    our_forecast_long,
    left_on=['MetricKey', 'ForecastYear'],
    right_on=['MetricKey', 'Year'],
    how='left',
    suffixes=('', '_Inhouse')
)

if 'Metric_Inhouse' in comparison.columns:
    comparison = comparison.drop(columns=['Metric_Inhouse'])

if 'Year' in comparison.columns:
    comparison = comparison.drop(columns=['Year'])

comparison['OurForecast'] = pd.to_numeric(comparison['OurForecast'], errors='coerce')
comparison['Delta'] = comparison['avg'] - comparison['OurForecast']
comparison['Delta %'] = np.where(
    comparison['OurForecast'].abs() > 1e-9,
    comparison['Delta'] / comparison['OurForecast'] * 100,
    np.nan
)

comparison_display = comparison[['Metric', 'ForecastYear', 'brokers', 'avg', 'median', 'min', 'max', 'OurForecast', 'Delta', 'Delta %']]
comparison_display = comparison_display.rename(columns={
    'ForecastYear': 'Year',
    'brokers': '# Brokers',
    'avg': 'Consensus Avg',
    'median': 'Consensus Median',
    'min': 'Low',
    'max': 'High',
    'OurForecast': 'In-house Forecast',
    'Delta': 'Difference',
    'Delta %': 'Difference %'
}).sort_values(['Metric', 'Year'])


st.subheader("Consensus Summary vs In-house Forecast")
numeric_cols = ['# Brokers', 'Consensus Avg', 'Consensus Median', 'Low', 'High', 'In-house Forecast', 'Difference']
percent_cols = ['Difference %']

format_dict = {col: '{:,.2f}' for col in numeric_cols if col in comparison_display.columns}
if '# Brokers' in comparison_display.columns:
    format_dict['# Brokers'] = '{:,.0f}'
percent_format = {col: '{:+,.2f}%' for col in percent_cols if col in comparison_display.columns}

comparison_styler = comparison_display.style.format(format_dict).format(percent_format)

st.dataframe(comparison_styler, use_container_width=True)


st.caption("Consensus statistics use the most recent forecast from each broker for the selected ticker, metric, and year. Differences are calculated as Consensus Avg minus your in-house forecast.")
