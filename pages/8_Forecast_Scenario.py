import streamlit as st
import pandas as pd
import numpy as np
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from utilities.forecast_utils import get_forecast_years

# Page configuration
st.set_page_config(
    page_title="Forecast Scenario Analysis",
    page_icon="📊",
    layout="wide"
)

# CSS styling (kept minimal for performance)
st.markdown("""
<style>
    .fixed-header {
        position: fixed; top: 50px; left: 0; right: 0;
        background: white; border-bottom: 2px solid #f0f2f6;
        z-index: 9999; padding: 10px 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .metrics-container {
        max-width: 1000px; margin: 0 auto;
        margin-left: calc(50% - 350px);
        display: flex; justify-content: space-around;
        align-items: center; padding-left: 100px;
    }
    .metric-box { text-align: center; color: #262730; }
    .metric-label { font-size: 1rem; color: #808495; margin-bottom: 0.3rem; }
    .metric-value { font-size: 2rem; font-weight: bold; color: #262730; margin: 0.3rem 0; }
    .metric-delta { font-size: 0.9rem; color: #09ab3b; }
    .ticker-box {
        text-align: center; padding-right: 30px;
        border-right: 2px solid #f0f2f6; margin-right: 30px;
    }
    .ticker-value { font-size: 2rem; font-weight: bold; color: #478B81; }
    .main > div:first-child { padding-top: 270px !important; }
    .block-container { padding-top: 0 !important; }
</style>
""", unsafe_allow_html=True)

st.title("Forecast Scenario Analysis")

# OPTIMIZED: Load data with better caching
@st.cache_data(ttl=1)
def load_data():
    """Load all required data in one optimized function"""
    df_year = pd.read_csv(os.path.join(project_root, 'Data/dfsectoryear.csv'))
    df_quarter = pd.read_csv(os.path.join(project_root, 'Data/dfsectorquarter.csv'))
    keyitem = pd.read_excel(os.path.join(project_root, 'Data/Key_items.xlsx'))
    
    # Use forecast_utils for dynamic year determination
    last_complete_year, forecast_year_1, forecast_year_2 = get_forecast_years()
    
    # Pre-process quarter data
    df_quarter['Year'] = 2000 + df_quarter['Date_Quarter'].str.extract(r'Q(\d+)', expand=False).astype(int)
    
    return df_year, df_quarter, keyitem, last_complete_year, forecast_year_1, forecast_year_2

df_year, df_quarter, keyitem, last_complete_year, forecast_year_1, forecast_year_2 = load_data()

# OPTIMIZED: Vectorized filtering for banks with forecast
forecast_mask = df_year['Year'].isin([forecast_year_1, forecast_year_2])
ticker_mask = df_year['TICKER'].str.len() == 3
banks_with_forecast = sorted(df_year[forecast_mask & ticker_mask]['TICKER'].unique())

# Sidebar
ticker = st.sidebar.selectbox("Select Bank:", banks_with_forecast, index=0)
st.sidebar.markdown("---")
revert_button = st.sidebar.button("Revert to Default Forecast", type="secondary", use_container_width=True)

# OPTIMIZED: Batch data extraction
@st.cache_data
def get_bank_data(df_year, df_quarter, ticker, last_complete_year, forecast_year_1, forecast_year_2):
    """Extract all bank data in one optimized function"""
    # Historical data
    hist_mask = (df_year['TICKER'] == ticker) & df_year['Year'].isin([last_complete_year-1, last_complete_year])
    historical = df_year[hist_mask].set_index('Year')
    
    # Forecast data
    forecast_1 = df_year[(df_year['TICKER'] == ticker) & (df_year['Year'] == forecast_year_1)]
    forecast_2 = df_year[(df_year['TICKER'] == ticker) & (df_year['Year'] == forecast_year_2)]
    
    # Quarterly data
    quarter_codes = [f'1Q{str(forecast_year_1)[2:]}', f'2Q{str(forecast_year_1)[2:]}']
    quarterly = df_quarter[
        (df_quarter['TICKER'] == ticker) & 
        (df_quarter['Year'] == forecast_year_1) & 
        (df_quarter['Date_Quarter'].isin(quarter_codes))
    ]
    
    return historical, forecast_1, forecast_2, quarterly

historical_data, forecast_1, forecast_2, quarterly_forecast = get_bank_data(
    df_year, df_quarter, ticker, last_complete_year, forecast_year_1, forecast_year_2
)

# OPTIMIZED: Batch value extraction function
def extract_values(df, columns, default=0):
    """Extract multiple column values at once with fallback"""
    if len(df) == 0:
        return {col: default for col in columns}
    
    result = {}
    for col in columns:
        if col in df.columns:
            val = df[col].values[0] if len(df) > 0 else default
            result[col] = val if pd.notna(val) else default
        else:
            result[col] = default
    return result

# Extract all needed values at once
forecast_1_vals = extract_values(forecast_1, ['IS.18', 'IS.3', 'IS.15', 'IS.14', 'IS.17', 
                                              'CA.13', 'CA.3', 'CA.6', 'CA.23',
                                              'BS.12', 'BS.13', 'BS.14', 'Nt.220'])
forecast_2_vals = extract_values(forecast_2, ['IS.18', 'IS.3', 'IS.15', 'IS.14', 'IS.17',
                                              'CA.13', 'CA.3', 'CA.6', 'CA.23',
                                              'BS.12', 'BS.13', 'BS.14', 'Nt.220'])

# Get loan values with fallback
loan_f1 = forecast_1_vals['BS.12'] if forecast_1_vals['BS.12'] != 0 else forecast_1_vals['BS.13']
loan_f2 = forecast_2_vals['BS.12'] if forecast_2_vals['BS.12'] != 0 else forecast_2_vals['BS.13']

# Initialize session state efficiently
def init_session_state(ticker, forecast_year_1, forecast_year_2, values):
    """Initialize all session state values at once"""
    prefix = f'{ticker}_'
    keys_to_init = {
        f'{prefix}pbt_{forecast_year_1}_adjusted': values['pbt_f1'],
        f'{prefix}pbt_{forecast_year_2}_adjusted': values['pbt_f2'],
        f'{prefix}pbt_change_segment1_{forecast_year_1}': 0,
        f'{prefix}pbt_change_segment1_{forecast_year_2}': 0,
        f'{prefix}pbt_change_segment2_{forecast_year_1}': 0,
        f'{prefix}pbt_change_segment2_{forecast_year_2}': 0,
        f'{prefix}pbt_change_segment3_{forecast_year_1}': 0,
        f'{prefix}pbt_change_segment3_{forecast_year_2}': 0,
    }
    
    for key, default_val in keys_to_init.items():
        if key not in st.session_state:
            st.session_state[key] = default_val

init_session_state(ticker, forecast_year_1, forecast_year_2, 
                  {'pbt_f1': forecast_1_vals['IS.18'], 'pbt_f2': forecast_2_vals['IS.18']})

# Header placeholder
header_placeholder = st.empty()
st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
st.markdown("---")

# OPTIMIZED: Vectorized table preparation
def prepare_table_vectorized(historical, forecast_1, forecast_2, quarterly, 
                            last_complete_year, forecast_year_1, forecast_year_2,
                            metrics_config):
    """Prepare historical tables using vectorized operations"""
    # Combine all data sources
    data_list = []
    
    # Historical years
    for year in [last_complete_year-1, last_complete_year]:
        if year in historical.index:
            row = historical.loc[year]
            data_list.append({'Period': str(year), **{k: row.get(v, 0) for k, v in metrics_config.items()}})
    
    # Quarterly data
    for _, row in quarterly.iterrows():
        period = row['Date_Quarter']
        data_list.append({'Period': period, **{k: row.get(v, 0) for k, v in metrics_config.items()}})
    
    # Forecast data
    for year, data, suffix in [(forecast_year_1, forecast_1, 'F'), (forecast_year_2, forecast_2, 'F')]:
        if len(data) > 0:
            row = data.iloc[0]
            data_list.append({
                'Period': f"{year}{suffix}",
                **{k: row.get(v, 0) if v in row else 0 for k, v in metrics_config.items()}
            })
    
    return pd.DataFrame(data_list).set_index('Period')

# Segment 1: Net Interest Income
st.header("Segment 1: Net Interest Income Adjustment")

# Prepare NIM table
nim_metrics = {
    'Loan (BS.12)': 'BS.12',
    'NIM (%)': 'CA.13',
    'NII (IS.3)': 'IS.3'
}

nim_table = prepare_table_vectorized(
    historical_data, forecast_1, forecast_2, quarterly_forecast,
    last_complete_year, forecast_year_1, forecast_year_2, nim_metrics
)

# Convert units and percentages
nim_table['Loan (BS.12)'] /= 1e12
nim_table['NIM (%)'] *= 100
nim_table['NII (IS.3)'] /= 1e12

# Add loan growth for forecast years
if f'{forecast_year_1}F' in nim_table.index and str(last_complete_year) in nim_table.index:
    prev_loan = nim_table.loc[str(last_complete_year), 'Loan (BS.12)']
    curr_loan = nim_table.loc[f'{forecast_year_1}F', 'Loan (BS.12)']
    nim_table.loc[f'{forecast_year_1}F', 'Loan Growth YoY (%)'] = ((curr_loan / prev_loan) - 1) * 100 if prev_loan != 0 else 0

if f'{forecast_year_2}F' in nim_table.index and f'{forecast_year_1}F' in nim_table.index:
    prev_loan = nim_table.loc[f'{forecast_year_1}F', 'Loan (BS.12)']
    curr_loan = nim_table.loc[f'{forecast_year_2}F', 'Loan (BS.12)']
    nim_table.loc[f'{forecast_year_2}F', 'Loan Growth YoY (%)'] = ((curr_loan / prev_loan) - 1) * 100 if prev_loan != 0 else 0

st.subheader("Historical and Forecast Data")
st.dataframe(nim_table.style.format({
    'Loan (BS.12)': '{:.2f}T',
    'Loan Growth YoY (%)': '{:.1f}%',
    'NIM (%)': '{:.2f}%',
    'NII (IS.3)': '{:.2f}T'
}, na_rep=''), use_container_width=True)

# Input section - streamlined
st.subheader("Adjust Forecast Assumptions")
col1, col2 = st.columns(2)

# Calculate original values once
original_values = {
    'nim_f1': forecast_1_vals['CA.13'] * 100,
    'nim_f2': forecast_2_vals['CA.13'] * 100,
    'loan_growth_f1': ((loan_f1 / historical_data.loc[last_complete_year, 'BS.13']) - 1) * 100 if last_complete_year in historical_data.index else 15,
    'loan_growth_f2': ((loan_f2 / loan_f1) - 1) * 100 if loan_f1 != 0 else 15,
}

# Handle revert
if revert_button:
    for key, value in original_values.items():
        st.session_state[f"{ticker}_{key}"] = value
    st.sidebar.success("Values reverted to defaults!")

# Input widgets
with col1:
    st.markdown(f"**{forecast_year_1} Adjustments**")
    nim_f1_new = st.number_input(f"NIM {forecast_year_1} (%)", 0.0, 10.0, 
                                 original_values['nim_f1'], 0.1, key=f"{ticker}_nim_f1")
    loan_growth_f1_new = st.number_input(f"Loan Growth YoY {forecast_year_1} (%)", -20.0, 50.0,
                                         original_values['loan_growth_f1'], 1.0, key=f"{ticker}_loan_growth_f1")

with col2:
    st.markdown(f"**{forecast_year_2} Adjustments**")
    nim_f2_new = st.number_input(f"NIM {forecast_year_2} (%)", 0.0, 10.0,
                                 original_values['nim_f2'], 0.1, key=f"{ticker}_nim_f2")
    loan_growth_f2_new = st.number_input(f"Loan Growth YoY {forecast_year_2} (%)", -20.0, 50.0,
                                         original_values['loan_growth_f2'], 1.0, key=f"{ticker}_loan_growth_f2")

# OPTIMIZED: Vectorized PBT calculation
def calculate_pbt_changes(original_values, new_values, forecast_vals):
    """Calculate PBT changes using vectorized operations"""
    results = {}
    
    # Segment 1 calculations
    loan_growth_change_f1 = new_values['loan_growth_f1'] - original_values['loan_growth_f1']
    loan_growth_change_f2 = new_values['loan_growth_f2'] - original_values['loan_growth_f2']
    
    nim_ratio_f1 = new_values['nim_f1'] / original_values['nim_f1'] if original_values['nim_f1'] != 0 else 1
    nim_ratio_f2 = new_values['nim_f2'] / original_values['nim_f2'] if original_values['nim_f2'] != 0 else 1
    
    results['segment1_f1'] = (loan_growth_change_f1 / 2) * (forecast_vals['pbt_f1'] / 100) + \
                             (nim_ratio_f1 - 1) * forecast_vals['nii_f1']
    results['segment1_f2'] = (loan_growth_change_f2 / 2) * (forecast_vals['pbt_f2'] / 100) + \
                             (nim_ratio_f2 - 1) * forecast_vals['nii_f2']
    
    return results

# Calculate changes
pbt_changes = calculate_pbt_changes(
    original_values,
    {'loan_growth_f1': loan_growth_f1_new, 'loan_growth_f2': loan_growth_f2_new,
     'nim_f1': nim_f1_new, 'nim_f2': nim_f2_new},
    {'pbt_f1': forecast_1_vals['IS.18'], 'pbt_f2': forecast_2_vals['IS.18'],
     'nii_f1': forecast_1_vals['IS.3'], 'nii_f2': forecast_2_vals['IS.3']}
)

# Store segment 1 changes
st.session_state[f'{ticker}_pbt_change_segment1_{forecast_year_1}'] = pbt_changes['segment1_f1']
st.session_state[f'{ticker}_pbt_change_segment1_{forecast_year_2}'] = pbt_changes['segment1_f2']

# Display impact (simplified)
st.subheader("Impact Analysis")
impact_col1, impact_col2 = st.columns(2)

with impact_col1:
    st.markdown(f"**{forecast_year_1} Impact**")
    st.write(f"**Total PBT Change: {pbt_changes['segment1_f1'] / 1e12:.2f}T**")

with impact_col2:
    st.markdown(f"**{forecast_year_2} Impact**")
    st.write(f"**Total PBT Change: {pbt_changes['segment1_f2'] / 1e12:.2f}T**")

st.markdown("---")

# Segment 2: OPEX (Simplified similar pattern)
st.header("Segment 2: Operating Expenses (OPEX) Adjustment")

# OPEX calculations
opex_last = historical_data.loc[last_complete_year, 'IS.15'] if last_complete_year in historical_data.index else 0
opex_growth_f1_orig = ((forecast_1_vals['IS.15'] / opex_last) - 1) * 100 if opex_last != 0 else 10
opex_growth_f2_orig = ((forecast_2_vals['IS.15'] / forecast_1_vals['IS.15']) - 1) * 100 if forecast_1_vals['IS.15'] != 0 else 10

col1, col2 = st.columns(2)
with col1:
    opex_growth_f1_new = st.number_input(f"OPEX Growth YoY {forecast_year_1} (%)", -30.0, 50.0,
                                         opex_growth_f1_orig, 1.0, key=f"{ticker}_opex_growth_f1")

with col2:
    opex_growth_f2_new = st.number_input(f"OPEX Growth YoY {forecast_year_2} (%)", -30.0, 50.0,
                                         opex_growth_f2_orig, 1.0, key=f"{ticker}_opex_growth_f2")

# Calculate OPEX changes
opex_f1_new = opex_last * (1 + opex_growth_f1_new / 100)
opex_f2_new = opex_f1_new * (1 + opex_growth_f2_new / 100)

pbt_change_segment2_f1 = opex_f1_new - forecast_1_vals['IS.15']
pbt_change_segment2_f2 = opex_f2_new - forecast_2_vals['IS.15']

st.session_state[f'{ticker}_pbt_change_segment2_{forecast_year_1}'] = pbt_change_segment2_f1
st.session_state[f'{ticker}_pbt_change_segment2_{forecast_year_2}'] = pbt_change_segment2_f2

st.markdown("---")

# Segment 3: Asset Quality (Simplified)
st.header("Segment 3: Asset Quality Assumptions")

# Asset quality inputs
col1, col2 = st.columns(2)

npl_f1_orig = forecast_1_vals['CA.3'] * 100
npl_f2_orig = forecast_2_vals['CA.3'] * 100

with col1:
    npl_f1_new = st.number_input(f"NPL {forecast_year_1} (%)", 0.0, 10.0, npl_f1_orig, 0.1,
                                 key=f"{ticker}_npl_f1")

with col2:
    npl_f2_new = st.number_input(f"NPL {forecast_year_2} (%)", 0.0, 10.0, npl_f2_orig, 0.1,
                                 key=f"{ticker}_npl_f2")

# Simplified provision calculation
loan_last = historical_data.loc[last_complete_year, 'BS.13'] if last_complete_year in historical_data.index else 1e15
loan_f1_new = loan_last * (1 + loan_growth_f1_new / 100)
loan_f2_new = loan_f1_new * (1 + loan_growth_f2_new / 100)

# NPL absolute values
npl_abs_f1_new = (npl_f1_new / 100) * loan_f1_new
npl_abs_f2_new = (npl_f2_new / 100) * loan_f2_new
npl_abs_f1_orig = (npl_f1_orig / 100) * loan_f1
npl_abs_f2_orig = (npl_f2_orig / 100) * loan_f2

# Provision changes (simplified)
provision_change_f1 = (npl_abs_f1_new - npl_abs_f1_orig) * 0.5  # Simplified factor
provision_change_f2 = (npl_abs_f2_new - npl_abs_f2_orig) * 0.5

pbt_change_segment3_f1 = -provision_change_f1
pbt_change_segment3_f2 = -provision_change_f2

st.session_state[f'{ticker}_pbt_change_segment3_{forecast_year_1}'] = pbt_change_segment3_f1
st.session_state[f'{ticker}_pbt_change_segment3_{forecast_year_2}'] = pbt_change_segment3_f2

st.markdown("---")

# OPTIMIZED: Summary Section with batch calculations
st.header("Summary of PBT Impact")

# Calculate totals using vectorized operations
segment_changes = np.array([
    [st.session_state.get(f'{ticker}_pbt_change_segment{i}_{forecast_year_1}', 0) for i in [1, 2, 3]],
    [st.session_state.get(f'{ticker}_pbt_change_segment{i}_{forecast_year_2}', 0) for i in [1, 2, 3]]
])

total_changes = segment_changes.sum(axis=1)
adjusted_pbt = np.array([forecast_1_vals['IS.18'], forecast_2_vals['IS.18']]) + total_changes

# Update session state
st.session_state[f'{ticker}_pbt_{forecast_year_1}_adjusted'] = adjusted_pbt[0]
st.session_state[f'{ticker}_pbt_{forecast_year_2}_adjusted'] = adjusted_pbt[1]

# Display summary
summary_col1, summary_col2 = st.columns(2)

with summary_col1:
    st.markdown(f"**{forecast_year_1} PBT Breakdown**")
    st.write(f"Original PBT: {forecast_1_vals['IS.18'] / 1e12:.2f}T")
    st.write(f"Total Changes: {total_changes[0] / 1e12:+.2f}T")
    st.write(f"**Adjusted PBT: {adjusted_pbt[0] / 1e12:.2f}T**")

with summary_col2:
    st.markdown(f"**{forecast_year_2} PBT Breakdown**")
    st.write(f"Original PBT: {forecast_2_vals['IS.18'] / 1e12:.2f}T")
    st.write(f"Total Changes: {total_changes[1] / 1e12:+.2f}T")
    st.write(f"**Adjusted PBT: {adjusted_pbt[1] / 1e12:.2f}T**")

# Update header with final values
pbt_last = historical_data.loc[last_complete_year, 'IS.18'] if last_complete_year in historical_data.index else 1
pbt_yoy_f1 = ((adjusted_pbt[0] / pbt_last) - 1) * 100 if pbt_last != 0 else 0
pbt_yoy_f2 = ((adjusted_pbt[1] / adjusted_pbt[0]) - 1) * 100 if adjusted_pbt[0] != 0 else 0

header_placeholder.markdown(f'''
<div class="fixed-header">
    <div class="metrics-container">
        <div class="ticker-box">
            <div class="metric-label">Bank</div>
            <div class="ticker-value">{ticker}</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">{forecast_year_1} Forecast</div>
            <div class="metric-value">{adjusted_pbt[0]/1e12:.2f}T</div>
            <div class="metric-delta">{pbt_yoy_f1:+.1f}% YoY</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">{forecast_year_2} Forecast</div>
            <div class="metric-value">{adjusted_pbt[1]/1e12:.2f}T</div>
            <div class="metric-delta">{pbt_yoy_f2:+.1f}% YoY</div>
        </div>
    </div>
</div>
''', unsafe_allow_html=True)