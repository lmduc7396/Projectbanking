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
if not hasattr(data_access, 'load_forecast_consensus') or not hasattr(data_access, 'load_banking_metrics'):
    data_access = importlib.reload(data_access)

if not hasattr(data_access, 'load_forecast_consensus') or not hasattr(data_access, 'load_banking_metrics'):
    st.error("Consensus data helpers are unavailable. Please update `utilities/data_access.py`.")
    st.stop()

load_forecast_consensus = data_access.load_forecast_consensus
load_banking_forecast = data_access.load_banking_forecast
load_banking_metrics = data_access.load_banking_metrics

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


def _format_int(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{int(round(float(value))):,}"


def _format_pct(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{int(round(float(value))):+d}%"


def _highlight_inhouse(row: pd.Series) -> list[str]:
    styles = [''] * len(row)
    columns = list(row.index)
    if 'Consensus Median (B VND)' in columns and 'In-house Forecast (B VND)' in columns:
        consensus = row['Consensus Median (B VND)']
        inhouse = row['In-house Forecast (B VND)']
        if pd.notna(consensus) and pd.notna(inhouse):
            consensus_idx = columns.index('Consensus Median (B VND)')
            inhouse_idx = columns.index('In-house Forecast (B VND)')

            gap_ratio = None
            if 'GapRatio' in columns:
                gap_ratio = row['GapRatio']
            elif abs(consensus) > 1e-9:
                gap_ratio = (inhouse - consensus) / consensus

            if gap_ratio is not None and pd.notna(gap_ratio) and abs(gap_ratio) <= 0.02:
                return styles

            if gap_ratio is not None and pd.notna(gap_ratio):
                gap_ratio = gap_ratio / 100

            if gap_ratio is None and abs(consensus) > 1e-9:
                gap_ratio = (inhouse - consensus) / consensus

            if gap_ratio is not None and pd.notna(gap_ratio) and abs(gap_ratio) <= 0.02:
                return styles

            if inhouse > consensus:
                styles[consensus_idx] = 'background-color: rgba(220, 20, 60, 0.12)'
                styles[inhouse_idx] = 'background-color: rgba(34, 139, 34, 0.15)'
            elif inhouse < consensus:
                styles[consensus_idx] = 'background-color: rgba(34, 139, 34, 0.15)'
                styles[inhouse_idx] = 'background-color: rgba(220, 20, 60, 0.12)'
    return styles


@st.cache_data(ttl=1800)
def load_data():
    consensus_df = load_forecast_consensus()
    forecast_df = load_banking_forecast('Y')
    actual_year_df = load_banking_metrics('Y')
    return consensus_df, forecast_df, actual_year_df


consensus_df, forecast_df, actual_year_df = load_data()


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

summary_container = st.container()

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

filters_container = st.container()

with filters_container:
    st.header("Configure View")
    col_ticker, col_years = st.columns(2)
    ticker_default_index = available_tickers.index('VCB') if 'VCB' in available_tickers else 0
    ticker = col_ticker.selectbox("Ticker", available_tickers, index=ticker_default_index, key="ticker_select")

    ticker_data = consensus_df[consensus_df['TICKER'] == ticker]
    year_options = sorted(ticker_data['ForecastYear'].dropna().unique())
    default_years = year_options
    selected_years = col_years.multiselect(
        "Forecast Years",
        options=year_options,
        default=default_years if default_years else year_options,
        key="year_multiselect"
    )

    st.caption("Latest record per broker × metric × year is displayed below.")

if selected_years:
    ticker_data = ticker_data[ticker_data['ForecastYear'].isin(selected_years)]

if ticker_data.empty:
    st.info("No consensus entries match the selected filters.")
    st.stop()



BROKER_STOPWORDS = {
    'BUY', 'SELL', 'HOLD', 'OUTPERFORM', 'UNDERPERFORM', 'NEUTRAL', 'ADD', 'TRADING',
    'OVERWEIGHT', 'UNDERWEIGHT', 'ACCUMULATE', 'REDUCE', 'OUTLOOK', 'FORECAST', 'TARGET',
    'PRICE', 'CONSENSUS', 'ESTIMATE', 'BASE', 'SCENARIO', 'NPATMI', 'PBT', 'NIM', 'NPL',
    'LOAN', 'ROA', 'ROE', 'CIR', 'TOI', 'EBIT', 'EBITDA'
}


def _tokenize_candidate(*values: str) -> list[str]:
    tokens: list[str] = []
    for value in values:
        if not value:
            continue
        parts = re.split(r'[^A-Z]', value.upper())
        tokens.extend([p for p in parts if p])
    return tokens


def _derive_broker_code(row: pd.Series, ticker: str) -> str:
    ticker_upper = ticker.upper()
    raw_org = str(row.get('ORGANCODE') or '').strip()
    candidates = []

    if raw_org:
        cleaned = re.sub(rf'\b{ticker_upper}\b', '', raw_org.upper())
        candidates.extend(_tokenize_candidate(cleaned))
        if cleaned.strip() and cleaned.strip() != raw_org.upper():
            candidates.append(cleaned.strip())

    keycodename = str(row.get('KEYCODENAME') or '')
    keycode = str(row.get('KEYCODE') or '')
    candidates.extend(_tokenize_candidate(keycodename, keycode))

    for token in reversed(candidates):
        if token == ticker_upper:
            continue
        if token in BROKER_STOPWORDS:
            continue
        if token.isalpha() and 2 <= len(token) <= 6:
            return token

    if raw_org:
        return raw_org.strip()
    return 'Unknown'


def latest_consensus_all_tickers(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    work = df.copy()
    if 'BrokerCode' not in work.columns:
        work['BrokerCode'] = work.apply(
            lambda row: _derive_broker_code(row, str(row.get('TICKER', ''))),
            axis=1
        )

    group_cols = ['TICKER', 'BrokerCode', 'MetricKey', 'ForecastYear']
    idx = work.groupby(group_cols, dropna=False)['EffectiveDate'].idxmax()
    latest = work.loc[idx].copy()
    latest['VALUE'] = pd.to_numeric(latest['VALUE'], errors='coerce')
    return latest


def latest_per_broker(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    work = df.copy()
    work['BrokerCode'] = work.apply(lambda row: _derive_broker_code(row, ticker), axis=1)
    group_cols = ['BrokerCode', 'MetricKey', 'ForecastYear']
    idx = work.groupby(group_cols, dropna=False)['EffectiveDate'].idxmax()
    latest = work.loc[idx].copy()
    latest = latest.sort_values(['ForecastYear', 'Metric', 'ORGANCODE']).reset_index(drop=True)
    latest['VALUE'] = pd.to_numeric(latest['VALUE'], errors='coerce')
    latest['Broker'] = latest['BrokerCode'].fillna('Unknown')
    return latest


def aggregate_consensus(latest_df: pd.DataFrame) -> pd.DataFrame:
    if latest_df.empty:
        return pd.DataFrame()

    aggregated = latest_df.groupby(['TICKER', 'Metric', 'MetricKey', 'ForecastYear']).agg(
        brokers=('BrokerCode', 'nunique'),
        consensus_median=('VALUE', 'median')
    ).reset_index()
    return aggregated


def prepare_inhouse_forecast(df: pd.DataFrame, ticker: str | None = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    data = df.copy()
    if ticker is not None and 'TICKER' in data.columns:
        data = data[data['TICKER'] == ticker]

    if data.empty:
        return pd.DataFrame()

    data['Year'] = pd.to_numeric(data.get('Year'), errors='coerce').astype('Int64')
    numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
    unwanted = {'Year', 'Quarter', 'is_forecast'}
    numeric_cols = [c for c in numeric_cols if c not in unwanted]
    if not numeric_cols:
        return pd.DataFrame()

    id_vars = ['Year']
    if 'TICKER' in data.columns:
        id_vars.insert(0, 'TICKER')

    melted = data[id_vars + numeric_cols].melt(id_vars=id_vars, var_name='Metric', value_name='OurForecast')
    melted = melted.dropna(subset=['Year', 'OurForecast'])
    melted['MetricKey'] = melted['Metric'].apply(_normalize_metric_key)

    if ticker is not None and 'TICKER' in melted.columns:
        melted = melted.drop(columns=['TICKER'])

    return melted


def prepare_actuals(df: pd.DataFrame, ticker: str | None = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    data = df.copy()
    if ticker is not None and 'TICKER' in data.columns:
        data = data[data['TICKER'] == ticker]

    if data.empty:
        return pd.DataFrame()

    data['Year'] = pd.to_numeric(data.get('Year'), errors='coerce').astype('Int64')
    numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
    unwanted = {'Year', 'Quarter'}
    numeric_cols = [c for c in numeric_cols if c not in unwanted]
    if not numeric_cols:
        return pd.DataFrame()

    id_vars = ['Year']
    if 'TICKER' in data.columns:
        id_vars.insert(0, 'TICKER')

    melted = data[id_vars + numeric_cols].melt(id_vars=id_vars, var_name='Metric', value_name='ActualValue')
    melted = melted.dropna(subset=['Year', 'ActualValue'])
    melted['MetricKey'] = melted['Metric'].apply(_normalize_metric_key)

    if ticker is not None and 'TICKER' in melted.columns:
        melted = melted.drop(columns=['TICKER'])

    return melted


latest_consensus_all = latest_consensus_all_tickers(consensus_df)
consensus_all_summary = aggregate_consensus(latest_consensus_all)
our_forecast_long_all = prepare_inhouse_forecast(forecast_df)
actuals_long_all = prepare_actuals(actual_year_df)

if not our_forecast_long_all.empty:
    our_forecast_long_all = our_forecast_long_all.drop(columns=['Metric'], errors='ignore')

global_summary_enriched = pd.DataFrame()
actual_lookup_all = {}

if not actuals_long_all.empty:
    actual_lookup_all = actuals_long_all.set_index(['TICKER', 'MetricKey', 'Year'])['ActualValue'].to_dict()

if not consensus_all_summary.empty:
    summary_combined = consensus_all_summary.copy()

    if not our_forecast_long_all.empty:
        summary_combined = summary_combined.merge(
            our_forecast_long_all,
            left_on=['TICKER', 'MetricKey', 'ForecastYear'],
            right_on=['TICKER', 'MetricKey', 'Year'],
            how='left'
        )
        summary_combined = summary_combined.drop(columns=['Year'], errors='ignore')

    summary_combined['consensus_median'] = pd.to_numeric(summary_combined['consensus_median'], errors='coerce')
    summary_combined['OurForecast'] = pd.to_numeric(summary_combined.get('OurForecast'), errors='coerce')

    summary_combined['Consensus YoY %'] = np.nan
    summary_combined['In-house YoY %'] = np.nan

    for (ticker_key, metric_key), metric_group in summary_combined.groupby(['TICKER', 'MetricKey']):
        metric_group = metric_group.sort_values('ForecastYear')
        prev_consensus = None
        prev_inhouse = None

        for idx, row in metric_group.iterrows():
            year = row['ForecastYear']
            consensus_value = row['consensus_median']
            inhouse_value = row.get('OurForecast')

            base_consensus = actual_lookup_all.get((ticker_key, metric_key, year - 1))
            base_inhouse = actual_lookup_all.get((ticker_key, metric_key, year - 1))

            if base_consensus is None and prev_consensus is not None:
                base_consensus = prev_consensus
            if base_inhouse is None and prev_inhouse is not None:
                base_inhouse = prev_inhouse

            if pd.notna(consensus_value) and pd.notna(base_consensus) and base_consensus not in (None, 0):
                summary_combined.loc[idx, 'Consensus YoY %'] = (consensus_value - base_consensus) / base_consensus * 100

            if pd.notna(inhouse_value) and pd.notna(base_inhouse) and base_inhouse not in (None, 0):
                summary_combined.loc[idx, 'In-house YoY %'] = (inhouse_value - base_inhouse) / base_inhouse * 100

            if pd.notna(consensus_value):
                prev_consensus = consensus_value
            if pd.notna(inhouse_value):
                prev_inhouse = inhouse_value

    global_summary_enriched = summary_combined


with summary_container:
    st.subheader("Banking Forecast Overview")
    if global_summary_enriched.empty:
        st.info("Consensus summary is unavailable. Refresh data sources and retry.")
    else:
        overview_npatmi = global_summary_enriched[global_summary_enriched['MetricKey'] == 'NPATMI'].copy()
        if overview_npatmi.empty:
            st.info("NPATMI consensus data is unavailable for the summary table.")
        else:
            year_options_overview = sorted(overview_npatmi['ForecastYear'].dropna().unique())
            if not year_options_overview:
                st.info("No forecast years available for summary display.")
            else:
                selected_year_overview = st.selectbox(
                    "Forecast Year",
                    options=year_options_overview,
                    index=0,
                    key="overview_year_select"
                )

                overview_filtered = overview_npatmi[
                    overview_npatmi['ForecastYear'] == selected_year_overview
                ].copy()

                if overview_filtered.empty:
                    st.info("No consensus records match the selected year.")
                else:
                    overview_filtered = overview_filtered.sort_values('TICKER')
                    display_df = overview_filtered[[
                        'TICKER',
                        'brokers',
                        'consensus_median',
                        'OurForecast',
                        'Consensus YoY %',
                        'In-house YoY %'
                    ]].rename(columns={
                        'TICKER': 'Ticker',
                        'brokers': '# Brokers',
                        'consensus_median': 'Consensus Median (B VND)',
                        'OurForecast': 'In-house Forecast (B VND)'
                    })

                    display_df['# Brokers'] = pd.to_numeric(display_df['# Brokers'], errors='coerce')
                    display_df['Consensus Median (B VND)'] = pd.to_numeric(
                        display_df['Consensus Median (B VND)'], errors='coerce'
                    ) / 1e9
                    display_df['In-house Forecast (B VND)'] = pd.to_numeric(
                        display_df['In-house Forecast (B VND)'], errors='coerce'
                    ) / 1e9
                    display_df['Consensus YoY %'] = pd.to_numeric(display_df['Consensus YoY %'], errors='coerce')
                    display_df['In-house YoY %'] = pd.to_numeric(display_df['In-house YoY %'], errors='coerce')

                    display_df['GapRatio'] = np.where(
                        display_df['Consensus Median (B VND)'].abs() > 1e-9,
                        (display_df['In-house Forecast (B VND)'] - display_df['Consensus Median (B VND)'])
                        / display_df['Consensus Median (B VND)'] * 100,
                        np.nan
                    )

                    styled_df = (
                        display_df.style
                        .format({
                            '# Brokers': _format_int,
                            'Consensus Median (B VND)': _format_int,
                            'In-house Forecast (B VND)': _format_int,
                            'Consensus YoY %': _format_pct,
                            'In-house YoY %': _format_pct
                        })
                        .apply(_highlight_inhouse, axis=1)
                        .hide(axis='columns', subset=['GapRatio'])
                    )

                    st.dataframe(styled_df, use_container_width=True, hide_index=True)

                    gap_stats = display_df[['Ticker', 'GapRatio']].dropna()
                    if not gap_stats.empty:
                        above_mask = gap_stats['GapRatio'] > 2
                        below_mask = gap_stats['GapRatio'] < -2
                        above_count = int(above_mask.sum())
                        below_count = int(below_mask.sum())
                        neutral_count = int((~above_mask & ~below_mask).sum())
                        st.caption(
                            " | ".join([
                                f"In-house > consensus: {above_count}",
                                f"In-house < consensus: {below_count}",
                                f"Within ±2% gap: {neutral_count}"
                            ])
                        )


latest_consensus = latest_per_broker(ticker_data, ticker)
latest_consensus['YoY %'] = np.nan


def consensus_summary(df: pd.DataFrame) -> pd.DataFrame:
    aggregated = df.groupby(['Metric', 'MetricKey', 'ForecastYear']).agg(
        brokers=('BrokerCode', 'nunique'),
        avg=('VALUE', 'mean'),
        median=('VALUE', 'median'),
        min=('VALUE', 'min'),
        max=('VALUE', 'max')
    ).reset_index()
    return aggregated


summary_df = consensus_summary(latest_consensus)


our_forecast_long = pd.DataFrame()
if not our_forecast_long_all.empty:
    our_forecast_long = our_forecast_long_all[our_forecast_long_all['TICKER'] == ticker].drop(columns=['TICKER'], errors='ignore')

actuals_long = pd.DataFrame()
if not actuals_long_all.empty:
    actuals_long = actuals_long_all[actuals_long_all['TICKER'] == ticker].drop(columns=['TICKER'], errors='ignore')

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
comparison['ConsensusValue'] = pd.to_numeric(comparison['median'], errors='coerce')
comparison['Delta'] = comparison['ConsensusValue'] - comparison['OurForecast']
comparison['Delta %'] = np.where(
    comparison['OurForecast'].abs() > 1e-9,
    comparison['Delta'] / comparison['OurForecast'] * 100,
    np.nan
)

actual_lookup = {}
if not actuals_long.empty:
    actual_lookup = actuals_long.set_index(['MetricKey', 'Year'])['ActualValue'].to_dict()

comparison['Consensus YoY %'] = np.nan
comparison['In-house YoY %'] = np.nan

for metric_key, metric_group in comparison.groupby('MetricKey'):
    metric_group_sorted = metric_group.sort_values('ForecastYear')
    prev_consensus = None
    prev_inhouse = None

    for idx, row in metric_group_sorted.iterrows():
        year = row['ForecastYear']
        consensus_value = pd.to_numeric(row['ConsensusValue'], errors='coerce')
        inhouse_value = pd.to_numeric(row['OurForecast'], errors='coerce')

        base_consensus = prev_consensus
        base_inhouse = prev_inhouse

        if base_consensus is None:
            base_consensus = actual_lookup.get((metric_key, year - 1))
        if base_inhouse is None:
            base_inhouse = actual_lookup.get((metric_key, year - 1))

        if pd.notna(consensus_value) and base_consensus not in (None, 0) and pd.notna(base_consensus):
            comparison.loc[idx, 'Consensus YoY %'] = (consensus_value - base_consensus) / base_consensus * 100
        if pd.notna(inhouse_value) and base_inhouse not in (None, 0) and pd.notna(base_inhouse):
            comparison.loc[idx, 'In-house YoY %'] = (inhouse_value - base_inhouse) / base_inhouse * 100

        if pd.notna(consensus_value):
            prev_consensus = consensus_value
        if pd.notna(inhouse_value):
            prev_inhouse = inhouse_value

# Compute broker-level YoY growth
for (broker_code, metric_key), broker_group in latest_consensus.groupby(['BrokerCode', 'MetricKey']):
    broker_group_sorted = broker_group.sort_values('ForecastYear')
    prev_value = None

    for idx, row in broker_group_sorted.iterrows():
        year = row['ForecastYear']
        forecast_value = pd.to_numeric(row['VALUE'], errors='coerce')

        base_value = prev_value
        if base_value is None:
            base_value = actual_lookup.get((metric_key, year - 1))

        if pd.notna(forecast_value) and pd.notna(base_value) and base_value not in (None, 0):
            latest_consensus.loc[idx, 'YoY %'] = (forecast_value - base_value) / base_value * 100

        if pd.notna(forecast_value):
            prev_value = forecast_value

st.subheader("Latest Broker Forecasts")

display_cols = ['Broker', 'Metric', 'ForecastYear', 'VALUE', 'YoY %', 'FORECASTDATE']
latest_consensus['FORECASTDATE'] = pd.to_datetime(latest_consensus['FORECASTDATE'], errors='coerce')

latest_consensus_display = latest_consensus[display_cols].rename(columns={
    'ForecastYear': 'Year',
    'VALUE': 'Value (B VND)',
    'YoY %': 'YoY %',
    'FORECASTDATE': 'Published'
})

value_numeric = pd.to_numeric(latest_consensus_display['Value (B VND)'], errors='coerce') / 1e9
latest_consensus_display['Value (B VND)'] = value_numeric.apply(_format_int)
latest_consensus_display['YoY %'] = pd.to_numeric(latest_consensus_display['YoY %'], errors='coerce').apply(_format_pct)
latest_consensus_display['Published'] = latest_consensus_display['Published'].dt.date.apply(lambda d: d.isoformat() if pd.notna(d) else "")

st.dataframe(latest_consensus_display, use_container_width=True)

scale_columns = ['median', 'OurForecast', 'Delta', 'ConsensusValue']
for col in scale_columns:
    if col in comparison.columns:
        comparison[col] = pd.to_numeric(comparison[col], errors='coerce') / 1e9

comparison_display = comparison[
    ['Metric', 'ForecastYear', 'brokers', 'median', 'OurForecast', 'Delta', 'Delta %', 'Consensus YoY %', 'In-house YoY %']
]
comparison_display = comparison_display.rename(columns={
    'ForecastYear': 'Year',
    'brokers': '# Brokers',
    'median': 'Consensus Median (B VND)',
    'OurForecast': 'In-house Forecast (B VND)',
    'Delta': 'Difference (B VND)',
    'Delta %': 'Difference %',
    'Consensus YoY %': 'Consensus YoY %',
    'In-house YoY %': 'In-house YoY %'
}).sort_values(['Metric', 'Year'])


st.subheader("Consensus Summary vs In-house Forecast")
# Drop helper column
if 'ConsensusValue' in comparison.columns:
    comparison_display = comparison_display.drop(columns=['ConsensusValue'], errors='ignore')

numeric_cols = [
    '# Brokers',
    'Consensus Median (B VND)',
    'In-house Forecast (B VND)',
    'Difference (B VND)'
]
percent_cols = ['Difference %', 'Consensus YoY %', 'In-house YoY %']

formatted_rows = []
for metric, metric_group in comparison_display.groupby('Metric'):
    metric_group = metric_group.sort_values('Year')
    table_rows = []
    for _, record in metric_group.iterrows():
        table_rows.append({
            'Year': int(record['Year']),
            '# Brokers': _format_int(record['# Brokers']),
            'Consensus Median (B VND)': _format_int(record['Consensus Median (B VND)']),
            'In-house Forecast (B VND)': _format_int(record['In-house Forecast (B VND)']),
            'Difference (B VND)': _format_int(record['Difference (B VND)']),
            'Difference %': _format_pct(record['Difference %']),
            'Consensus YoY %': _format_pct(record['Consensus YoY %']),
            'In-house YoY %': _format_pct(record['In-house YoY %'])
        })
    formatted_rows.append((metric, table_rows))

for metric, rows in formatted_rows:
    st.markdown(f"#### {metric}")
    metric_df = pd.DataFrame(rows)
    metric_df = metric_df[['Year', '# Brokers', 'Consensus Median (B VND)', 'In-house Forecast (B VND)',
                           'Difference (B VND)', 'Difference %', 'Consensus YoY %', 'In-house YoY %']]
    st.dataframe(metric_df, use_container_width=True, hide_index=True)


st.caption("Consensus statistics use the most recent forecast from each broker for the selected ticker, metric, and year. Differences are calculated as Consensus Median minus your in-house forecast.")
