import streamlit as st
import pandas as pd
import numpy as np
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Page configuration
st.set_page_config(
    page_title="Forecast Scenario Analysis",
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

# OPTIMIZED: Load data with better caching
@st.cache_data(ttl=1)
def load_data():
    """Load all required data in one optimized function"""
    df_year = pd.read_csv(os.path.join(project_root, 'Data/dfsectoryear.csv'))
    df_quarter = pd.read_csv(os.path.join(project_root, 'Data/dfsectorquarter.csv'))
    keyitem = pd.read_excel(os.path.join(project_root, 'Data/Key_items.xlsx'))
    
    # Dynamically determine forecast years from data
    # Get years from actual bank data (3-letter tickers only)
    years_with_data = df_year[df_year['TICKER'].str.len() == 3]['Year'].unique()
    years_with_data = sorted(years_with_data)
    
    # Find the most recent historical year (not a forecast year)
    # Forecast years are typically the last 2 years in the data
    if len(years_with_data) >= 3:
        last_complete_year = int(years_with_data[-3])  # Third from last is the last complete year
        forecast_year_1 = int(years_with_data[-2])     # Second from last is first forecast year
        forecast_year_2 = int(years_with_data[-1])     # Last is second forecast year
    else:
        # If not enough years, use the available years
        last_complete_year = int(years_with_data[0]) if years_with_data else None
        forecast_year_1 = last_complete_year + 1 if last_complete_year else None
        forecast_year_2 = last_complete_year + 2 if last_complete_year else None
    
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

# Prepare NIM table with BS.13 as primary loan source
nim_metrics = {
    'Loan': 'BS.13',  # Use BS.13 as primary source
    'NIM (%)': 'CA.13',
    'NII': 'IS.3'
}

nim_table = prepare_table_vectorized(
    historical_data, forecast_1, forecast_2, quarterly_forecast,
    last_complete_year, forecast_year_1, forecast_year_2, nim_metrics
)

# Convert units and percentages
nim_table['Loan'] /= 1e12
nim_table['NIM (%)'] *= 100
nim_table['NII'] /= 1e12

# Calculate loan growth YoY for all periods
nim_table['Loan Growth YoY (%)'] = 0.0

# Historical years growth
if str(last_complete_year-1) in nim_table.index and str(last_complete_year-2) in nim_table.index:
    prev_loan = nim_table.loc[str(last_complete_year-2), 'Loan']
    curr_loan = nim_table.loc[str(last_complete_year-1), 'Loan']
    if prev_loan != 0:
        nim_table.loc[str(last_complete_year-1), 'Loan Growth YoY (%)'] = ((curr_loan / prev_loan) - 1) * 100

if str(last_complete_year) in nim_table.index and str(last_complete_year-1) in nim_table.index:
    prev_loan = nim_table.loc[str(last_complete_year-1), 'Loan']
    curr_loan = nim_table.loc[str(last_complete_year), 'Loan']
    if prev_loan != 0:
        nim_table.loc[str(last_complete_year), 'Loan Growth YoY (%)'] = ((curr_loan / prev_loan) - 1) * 100

# Forecast years growth
if f'{forecast_year_1}F' in nim_table.index and str(last_complete_year) in nim_table.index:
    prev_loan = nim_table.loc[str(last_complete_year), 'Loan']
    curr_loan = nim_table.loc[f'{forecast_year_1}F', 'Loan']
    if prev_loan != 0:
        nim_table.loc[f'{forecast_year_1}F', 'Loan Growth YoY (%)'] = ((curr_loan / prev_loan) - 1) * 100

if f'{forecast_year_2}F' in nim_table.index and f'{forecast_year_1}F' in nim_table.index:
    prev_loan = nim_table.loc[f'{forecast_year_1}F', 'Loan']
    curr_loan = nim_table.loc[f'{forecast_year_2}F', 'Loan']
    if prev_loan != 0:
        nim_table.loc[f'{forecast_year_2}F', 'Loan Growth YoY (%)'] = ((curr_loan / prev_loan) - 1) * 100

# Reorder columns: Loan, Loan Growth YoY, NIM, NII
nim_table = nim_table[['Loan', 'Loan Growth YoY (%)', 'NIM (%)', 'NII']]

st.subheader("Historical and Forecast Data")
st.dataframe(nim_table.style.format({
    'Loan': '{:.2f}T',
    'Loan Growth YoY (%)': '{:.1f}%',
    'NIM (%)': '{:.2f}%',
    'NII': '{:.2f}T'
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

# Initialize session state for inputs if not exists
for key, value in original_values.items():
    if f"{ticker}_{key}" not in st.session_state:
        st.session_state[f"{ticker}_{key}"] = value

# Handle revert button - reset to original forecast values
if revert_button:
    for key, value in original_values.items():
        st.session_state[f"{ticker}_{key}"] = value
    st.rerun()

# Input widgets
with col1:
    st.markdown(f"**{forecast_year_1} Adjustments**")
    nim_f1_new = st.number_input(f"NIM {forecast_year_1} (%)", 0.0, 10.0, 
                                 key=f"{ticker}_nim_f1", step=0.1)
    loan_growth_f1_new = st.number_input(f"Loan Growth YoY {forecast_year_1} (%)", -20.0, 50.0,
                                         key=f"{ticker}_loan_growth_f1", step=1.0)

with col2:
    st.markdown(f"**{forecast_year_2} Adjustments**")
    nim_f2_new = st.number_input(f"NIM {forecast_year_2} (%)", 0.0, 10.0,
                                 key=f"{ticker}_nim_f2", step=0.1)
    loan_growth_f2_new = st.number_input(f"Loan Growth YoY {forecast_year_2} (%)", -20.0, 50.0,
                                         key=f"{ticker}_loan_growth_f2", step=1.0)

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

# Store detailed impact for final analysis
impact_details_segment1 = {
    'loan_growth_change': [loan_growth_f1_new - original_values['loan_growth_f1'], 
                           loan_growth_f2_new - original_values['loan_growth_f2']],
    'nim_change': [nim_f1_new - original_values['nim_f1'],
                   nim_f2_new - original_values['nim_f2']],
    'pbt_from_loan': [(loan_growth_f1_new - original_values['loan_growth_f1']) / 2 * (forecast_1_vals['IS.18'] / 100),
                      (loan_growth_f2_new - original_values['loan_growth_f2']) / 2 * (forecast_2_vals['IS.18'] / 100)],
    'pbt_from_nim': [((nim_f1_new / original_values['nim_f1'] - 1) if original_values['nim_f1'] != 0 else 0) * forecast_1_vals['IS.3'],
                     ((nim_f2_new / original_values['nim_f2'] - 1) if original_values['nim_f2'] != 0 else 0) * forecast_2_vals['IS.3']]
}

st.markdown("---")

# Segment 2: OPEX
st.header("Segment 2: Operating Expenses (OPEX) Adjustment")

# Prepare OPEX historical table
opex_metrics = {
    'OPEX': 'IS.15',
    'TOI': 'IS.14',  # Keep for calculation but will hide
    'CIR (%)': 'CA.6'
}

opex_table = prepare_table_vectorized(
    historical_data, forecast_1, forecast_2, quarterly_forecast,
    last_complete_year, forecast_year_1, forecast_year_2, opex_metrics
)

# Convert units and calculate additional metrics
opex_table['OPEX'] /= 1e12
opex_table['TOI'] /= 1e12  # Keep for internal calculations
opex_table['CIR (%)'] *= 100

# Calculate OPEX growth YoY for all periods
opex_table['OPEX Growth YoY (%)'] = 0.0

# Historical years growth
if str(last_complete_year-1) in opex_table.index and str(last_complete_year-2) in opex_table.index:
    prev_opex = historical_data.loc[last_complete_year-2, 'IS.15'] if last_complete_year-2 in historical_data.index else 0
    curr_opex = historical_data.loc[last_complete_year-1, 'IS.15'] if last_complete_year-1 in historical_data.index else 0
    if prev_opex != 0:
        opex_table.loc[str(last_complete_year-1), 'OPEX Growth YoY (%)'] = ((curr_opex / prev_opex) - 1) * 100

if str(last_complete_year) in opex_table.index and str(last_complete_year-1) in opex_table.index:
    prev_opex = historical_data.loc[last_complete_year-1, 'IS.15'] if last_complete_year-1 in historical_data.index else 0
    curr_opex = historical_data.loc[last_complete_year, 'IS.15'] if last_complete_year in historical_data.index else 0
    if prev_opex != 0:
        opex_table.loc[str(last_complete_year), 'OPEX Growth YoY (%)'] = ((curr_opex / prev_opex) - 1) * 100

# Forecast years growth
opex_last = historical_data.loc[last_complete_year, 'IS.15'] if last_complete_year in historical_data.index else 0
if f'{forecast_year_1}F' in opex_table.index and opex_last != 0:
    opex_table.loc[f'{forecast_year_1}F', 'OPEX Growth YoY (%)'] = ((forecast_1_vals['IS.15'] / opex_last) - 1) * 100
if f'{forecast_year_2}F' in opex_table.index and forecast_1_vals['IS.15'] != 0:
    opex_table.loc[f'{forecast_year_2}F', 'OPEX Growth YoY (%)'] = ((forecast_2_vals['IS.15'] / forecast_1_vals['IS.15']) - 1) * 100

# Reorder columns: OPEX, OPEX Growth YoY, CIR (hide TOI)
display_table = opex_table[['OPEX', 'OPEX Growth YoY (%)', 'CIR (%)']]

st.subheader("Historical and Forecast OPEX & CIR")
st.dataframe(display_table.style.format({
    'OPEX': '{:.2f}T',
    'OPEX Growth YoY (%)': '{:.1f}%',
    'CIR (%)': '{:.1f}%'
}, na_rep=''), use_container_width=True)

# Input section
st.subheader("Adjust OPEX Growth")

opex_growth_f1_orig = ((forecast_1_vals['IS.15'] / opex_last) - 1) * 100 if opex_last != 0 else 10
opex_growth_f2_orig = ((forecast_2_vals['IS.15'] / forecast_1_vals['IS.15']) - 1) * 100 if forecast_1_vals['IS.15'] != 0 else 10

# Initialize session state for OPEX inputs
if f"{ticker}_opex_growth_f1" not in st.session_state:
    st.session_state[f"{ticker}_opex_growth_f1"] = opex_growth_f1_orig
if f"{ticker}_opex_growth_f2" not in st.session_state:
    st.session_state[f"{ticker}_opex_growth_f2"] = opex_growth_f2_orig

# Reset OPEX values if revert button was pressed
if revert_button:
    st.session_state[f"{ticker}_opex_growth_f1"] = opex_growth_f1_orig
    st.session_state[f"{ticker}_opex_growth_f2"] = opex_growth_f2_orig

col1, col2 = st.columns(2)
with col1:
    opex_growth_f1_new = st.number_input(f"OPEX Growth YoY {forecast_year_1} (%)", -30.0, 50.0,
                                         key=f"{ticker}_opex_growth_f1", step=1.0)

with col2:
    opex_growth_f2_new = st.number_input(f"OPEX Growth YoY {forecast_year_2} (%)", -30.0, 50.0,
                                         key=f"{ticker}_opex_growth_f2", step=1.0)

# Calculate OPEX changes
opex_f1_new = opex_last * (1 + opex_growth_f1_new / 100)
opex_f2_new = opex_f1_new * (1 + opex_growth_f2_new / 100)

pbt_change_segment2_f1 = opex_f1_new - forecast_1_vals['IS.15']
pbt_change_segment2_f2 = opex_f2_new - forecast_2_vals['IS.15']

st.session_state[f'{ticker}_pbt_change_segment2_{forecast_year_1}'] = pbt_change_segment2_f1
st.session_state[f'{ticker}_pbt_change_segment2_{forecast_year_2}'] = pbt_change_segment2_f2

# Calculate CIR impact
toi_f1 = forecast_1_vals['IS.14'] + st.session_state.get(f'{ticker}_pbt_change_segment1_{forecast_year_1}', 0)
toi_f2 = forecast_2_vals['IS.14'] + st.session_state.get(f'{ticker}_pbt_change_segment1_{forecast_year_2}', 0)

cir_f1_orig = (forecast_1_vals['IS.15'] / forecast_1_vals['IS.14'] * 100) if forecast_1_vals['IS.14'] != 0 else 0
cir_f2_orig = (forecast_2_vals['IS.15'] / forecast_2_vals['IS.14'] * 100) if forecast_2_vals['IS.14'] != 0 else 0

cir_f1_new = (opex_f1_new / toi_f1 * 100) if toi_f1 != 0 else 0
cir_f2_new = (opex_f2_new / toi_f2 * 100) if toi_f2 != 0 else 0

# Store for final analysis
impact_details_segment2 = {
    'opex_growth_change': [opex_growth_f1_new - opex_growth_f1_orig,
                          opex_growth_f2_new - opex_growth_f2_orig],
    'cir_change': [cir_f1_new - cir_f1_orig, cir_f2_new - cir_f2_orig],
    'pbt_impact': [pbt_change_segment2_f1, pbt_change_segment2_f2]
}

st.markdown("---")

# Segment 3: Asset Quality
st.header("Segment 3: Asset Quality Assumptions")

# Prepare Asset Quality historical table
asset_quality_metrics = {
    'NPL (%)': 'CA.3',
    'NPL Formation (%)': 'CA.23',
    'Provision (BS.14)': 'BS.14',  # Keep for calculation but won't display
    'Provision Expense': 'IS.17',
    'Write-off (Nt.220)': 'Nt.220'
}

asset_quality_table = prepare_table_vectorized(
    historical_data, forecast_1, forecast_2, quarterly_forecast,
    last_complete_year, forecast_year_1, forecast_year_2, asset_quality_metrics
)

# Convert units and calculate additional metrics
asset_quality_table['NPL (%)'] *= 100
asset_quality_table['NPL Formation (%)'] = asset_quality_table['NPL Formation (%)'].abs() * 100
asset_quality_table['Provision (BS.14)'] /= 1e12  # Keep for calculation
asset_quality_table['Provision Expense'] /= 1e12
asset_quality_table['Write-off (Nt.220)'] /= 1e12

# Calculate NPL Coverage for all periods including quarters
asset_quality_table['NPL Coverage (%)'] = 0.0

for period in asset_quality_table.index:
    loan_val = 0
    npl_val = 0
    bs14_val = 0
    
    if 'Q' in period:
        # For quarterly data
        quarter_row = quarterly_forecast[quarterly_forecast['Date_Quarter'] == period]
        if not quarter_row.empty:
            loan_val = quarter_row['BS.13'].values[0] if 'BS.13' in quarter_row.columns else 0
            npl_val = quarter_row['CA.3'].values[0] if 'CA.3' in quarter_row.columns else 0
            bs14_val = quarter_row['BS.14'].values[0] if 'BS.14' in quarter_row.columns else 0
    elif 'F' in period:
        # For forecast years
        year = int(period[:-1])
        if year == forecast_year_1:
            loan_val = loan_f1
            npl_val = forecast_1_vals['CA.3']
            bs14_val = forecast_1_vals['BS.14']
        else:
            loan_val = loan_f2
            npl_val = forecast_2_vals['CA.3']
            bs14_val = forecast_2_vals['BS.14']
    else:
        # For historical years
        year = int(period) if period.isdigit() else None
        if year and year in historical_data.index:
            loan_val = historical_data.loc[year, 'BS.13']
            npl_val = historical_data.loc[year, 'CA.3']
            bs14_val = historical_data.loc[year, 'BS.14']
    
    if npl_val != 0 and loan_val != 0:
        asset_quality_table.loc[period, 'NPL Coverage (%)'] = (-bs14_val / (npl_val * loan_val) * 100)

# Reorder columns: NPL, NPL Formation, NPL Coverage, Provision Expense, Write-off (hide Provision BS.14)
display_table = asset_quality_table[['NPL (%)', 'NPL Formation (%)', 'NPL Coverage (%)', 'Provision Expense', 'Write-off (Nt.220)']]

st.subheader("Historical and Forecast Asset Quality Metrics")
st.dataframe(display_table.style.format({
    'NPL (%)': '{:.2f}%',
    'NPL Formation (%)': '{:.2f}%',
    'NPL Coverage (%)': '{:.1f}%',
    'Provision Expense': '{:.2f}T',
    'Write-off (Nt.220)': '{:.2f}T'
}, na_rep=''), use_container_width=True)

# Input section with all three inputs
st.subheader("Adjust Asset Quality Assumptions")
col1, col2 = st.columns(2)

# Get original values
npl_f1_orig = forecast_1_vals['CA.3'] * 100
npl_f2_orig = forecast_2_vals['CA.3'] * 100

npl_formation_f1_orig = abs(forecast_1_vals['CA.23'] * 100) if forecast_1_vals['CA.23'] != 0 else 0.5
npl_formation_f2_orig = abs(forecast_2_vals['CA.23'] * 100) if forecast_2_vals['CA.23'] != 0 else 0.5

# Calculate original NPL coverage
bs14_f1 = forecast_1_vals['BS.14']
bs14_f2 = forecast_2_vals['BS.14']
npl_coverage_f1_orig = (-bs14_f1 / (npl_f1_orig/100 * loan_f1) * 100) if (npl_f1_orig * loan_f1) != 0 else 100
npl_coverage_f2_orig = (-bs14_f2 / (npl_f2_orig/100 * loan_f2) * 100) if (npl_f2_orig * loan_f2) != 0 else 100

# Initialize session state for NPL inputs
if f"{ticker}_npl_f1" not in st.session_state:
    st.session_state[f"{ticker}_npl_f1"] = npl_f1_orig
if f"{ticker}_npl_f2" not in st.session_state:
    st.session_state[f"{ticker}_npl_f2"] = npl_f2_orig
if f"{ticker}_npl_formation_f1" not in st.session_state:
    st.session_state[f"{ticker}_npl_formation_f1"] = npl_formation_f1_orig
if f"{ticker}_npl_formation_f2" not in st.session_state:
    st.session_state[f"{ticker}_npl_formation_f2"] = npl_formation_f2_orig
if f"{ticker}_npl_coverage_f1" not in st.session_state:
    st.session_state[f"{ticker}_npl_coverage_f1"] = npl_coverage_f1_orig
if f"{ticker}_npl_coverage_f2" not in st.session_state:
    st.session_state[f"{ticker}_npl_coverage_f2"] = npl_coverage_f2_orig

# Reset NPL values if revert button was pressed
if revert_button:
    st.session_state[f"{ticker}_npl_f1"] = npl_f1_orig
    st.session_state[f"{ticker}_npl_f2"] = npl_f2_orig
    st.session_state[f"{ticker}_npl_formation_f1"] = npl_formation_f1_orig
    st.session_state[f"{ticker}_npl_formation_f2"] = npl_formation_f2_orig
    st.session_state[f"{ticker}_npl_coverage_f1"] = npl_coverage_f1_orig
    st.session_state[f"{ticker}_npl_coverage_f2"] = npl_coverage_f2_orig

with col1:
    st.markdown(f"**{forecast_year_1} Adjustments**")
    npl_f1_new = st.number_input(f"NPL {forecast_year_1} (%)", 0.0, 10.0,
                                 key=f"{ticker}_npl_f1", step=0.1)
    npl_formation_f1_new = st.number_input(f"NPL Formation {forecast_year_1} (%)", 0.0, 5.0,
                                           key=f"{ticker}_npl_formation_f1", step=0.1)
    npl_coverage_f1_new = st.number_input(f"NPL Coverage {forecast_year_1} (%)", 0.0, 500.0,
                                          key=f"{ticker}_npl_coverage_f1", step=1.0)

with col2:
    st.markdown(f"**{forecast_year_2} Adjustments**")
    npl_f2_new = st.number_input(f"NPL {forecast_year_2} (%)", 0.0, 10.0,
                                 key=f"{ticker}_npl_f2", step=0.1)
    npl_formation_f2_new = st.number_input(f"NPL Formation {forecast_year_2} (%)", 0.0, 5.0,
                                           key=f"{ticker}_npl_formation_f2", step=0.1)
    npl_coverage_f2_new = st.number_input(f"NPL Coverage {forecast_year_2} (%)", 0.0, 500.0,
                                          key=f"{ticker}_npl_coverage_f2", step=1.0)

# Get loan values from Segment 1
loan_last = historical_data.loc[last_complete_year, 'BS.13'] if last_complete_year in historical_data.index else 1e15
loan_f1_new = loan_last * (1 + loan_growth_f1_new / 100)
loan_f2_new = loan_f1_new * (1 + loan_growth_f2_new / 100)

# Calculate provision expense using proper formula
# Get previous year values
bs14_last = historical_data.loc[last_complete_year, 'BS.14'] if last_complete_year in historical_data.index else 0
npl_last = historical_data.loc[last_complete_year, 'CA.3'] if last_complete_year in historical_data.index else 0.015

# Calculate absolute NPL
npl_abs_last = npl_last * loan_last
npl_abs_f1_new = (npl_f1_new / 100) * loan_f1_new
npl_abs_f2_new = (npl_f2_new / 100) * loan_f2_new
npl_abs_f1_orig = (npl_f1_orig / 100) * loan_f1
npl_abs_f2_orig = (npl_f2_orig / 100) * loan_f2

# Calculate NPL formation absolute
npl_formation_abs_f1_new = (npl_formation_f1_new / 100) * loan_last
npl_formation_abs_f2_new = (npl_formation_f2_new / 100) * loan_f1_new
npl_formation_abs_f1_orig = (npl_formation_f1_orig / 100) * loan_last
npl_formation_abs_f2_orig = (npl_formation_f2_orig / 100) * loan_f1

# Calculate provision balance
provision_last = -bs14_last
provision_f1_new = (npl_coverage_f1_new / 100) * npl_abs_f1_new
provision_f2_new = (npl_coverage_f2_new / 100) * npl_abs_f2_new
provision_f1_orig = (npl_coverage_f1_orig / 100) * npl_abs_f1_orig
provision_f2_orig = (npl_coverage_f2_orig / 100) * npl_abs_f2_orig

# Get write-off values
write_off_f1 = forecast_1_vals.get('Nt.220', 0)
write_off_f2 = forecast_2_vals.get('Nt.220', 0)

# Calculate provision expense
provision_expense_f1_new = -(-(npl_abs_f1_new - npl_abs_last) + npl_formation_abs_f1_new + (provision_f1_new - provision_last))
provision_expense_f2_new = -(-(npl_abs_f2_new - npl_abs_f1_new) + npl_formation_abs_f2_new + (provision_f2_new - provision_f1_new))

provision_expense_f1_orig = forecast_1_vals['IS.17']
provision_expense_f2_orig = forecast_2_vals['IS.17']

# Calculate PBT changes
provision_change_f1 = provision_expense_f1_new - provision_expense_f1_orig
provision_change_f2 = provision_expense_f2_new - provision_expense_f2_orig

pbt_change_segment3_f1 = provision_change_f1
pbt_change_segment3_f2 = provision_change_f2

st.session_state[f'{ticker}_pbt_change_segment3_{forecast_year_1}'] = pbt_change_segment3_f1
st.session_state[f'{ticker}_pbt_change_segment3_{forecast_year_2}'] = pbt_change_segment3_f2

# Store for final analysis
impact_details_segment3 = {
    'npl_change': [npl_f1_new - npl_f1_orig, npl_f2_new - npl_f2_orig],
    'npl_formation_change': [npl_formation_f1_new - npl_formation_f1_orig,
                            npl_formation_f2_new - npl_formation_f2_orig],
    'npl_coverage_change': [npl_coverage_f1_new - npl_coverage_f1_orig,
                           npl_coverage_f2_new - npl_coverage_f2_orig],
    'provision_expense_change': [provision_change_f1, provision_change_f2],
    'pbt_impact': [pbt_change_segment3_f1, pbt_change_segment3_f2]
}

st.markdown("---")

# Comprehensive Impact Analysis Table
st.header("Comprehensive Impact Analysis")

# Create detailed impact analysis DataFrame
impact_data = []

# Segment 1: Net Interest Income
impact_data.append({
    'Segment': 'Net Interest Income',
    'Input': 'NIM Change',
    f'{forecast_year_1} Change': f"{impact_details_segment1['nim_change'][0]:+.2f}pp",
    f'{forecast_year_1} PBT Impact (T)': impact_details_segment1['pbt_from_nim'][0] / 1e12,
    f'{forecast_year_2} Change': f"{impact_details_segment1['nim_change'][1]:+.2f}pp",
    f'{forecast_year_2} PBT Impact (T)': impact_details_segment1['pbt_from_nim'][1] / 1e12
})

impact_data.append({
    'Segment': 'Net Interest Income',
    'Input': 'Loan Growth Change',
    f'{forecast_year_1} Change': f"{impact_details_segment1['loan_growth_change'][0]:+.1f}pp",
    f'{forecast_year_1} PBT Impact (T)': impact_details_segment1['pbt_from_loan'][0] / 1e12,
    f'{forecast_year_2} Change': f"{impact_details_segment1['loan_growth_change'][1]:+.1f}pp",
    f'{forecast_year_2} PBT Impact (T)': impact_details_segment1['pbt_from_loan'][1] / 1e12
})

# Segment 1 Subtotal
impact_data.append({
    'Segment': 'Segment 1 Subtotal',
    'Input': '',
    f'{forecast_year_1} Change': '',
    f'{forecast_year_1} PBT Impact (T)': st.session_state.get(f'{ticker}_pbt_change_segment1_{forecast_year_1}', 0) / 1e12,
    f'{forecast_year_2} Change': '',
    f'{forecast_year_2} PBT Impact (T)': st.session_state.get(f'{ticker}_pbt_change_segment1_{forecast_year_2}', 0) / 1e12
})

# Segment 2: OPEX
impact_data.append({
    'Segment': 'Operating Expenses',
    'Input': 'OPEX Growth Change',
    f'{forecast_year_1} Change': f"{impact_details_segment2['opex_growth_change'][0]:+.1f}pp",
    f'{forecast_year_1} PBT Impact (T)': impact_details_segment2['pbt_impact'][0] / 1e12,
    f'{forecast_year_2} Change': f"{impact_details_segment2['opex_growth_change'][1]:+.1f}pp",
    f'{forecast_year_2} PBT Impact (T)': impact_details_segment2['pbt_impact'][1] / 1e12
})

impact_data.append({
    'Segment': 'Operating Expenses',
    'Input': 'CIR Change',
    f'{forecast_year_1} Change': f"{impact_details_segment2['cir_change'][0]:+.1f}pp",
    f'{forecast_year_1} PBT Impact (T)': 0,  # CIR is a result, not a driver
    f'{forecast_year_2} Change': f"{impact_details_segment2['cir_change'][1]:+.1f}pp",
    f'{forecast_year_2} PBT Impact (T)': 0
})

# Segment 2 Subtotal
impact_data.append({
    'Segment': 'Segment 2 Subtotal',
    'Input': '',
    f'{forecast_year_1} Change': '',
    f'{forecast_year_1} PBT Impact (T)': st.session_state.get(f'{ticker}_pbt_change_segment2_{forecast_year_1}', 0) / 1e12,
    f'{forecast_year_2} Change': '',
    f'{forecast_year_2} PBT Impact (T)': st.session_state.get(f'{ticker}_pbt_change_segment2_{forecast_year_2}', 0) / 1e12
})

# Segment 3: Asset Quality
impact_data.append({
    'Segment': 'Asset Quality',
    'Input': 'NPL Change',
    f'{forecast_year_1} Change': f"{impact_details_segment3['npl_change'][0]:+.2f}pp",
    f'{forecast_year_1} PBT Impact (T)': 0,  # Part of combined provision impact
    f'{forecast_year_2} Change': f"{impact_details_segment3['npl_change'][1]:+.2f}pp",
    f'{forecast_year_2} PBT Impact (T)': 0
})

impact_data.append({
    'Segment': 'Asset Quality',
    'Input': 'NPL Formation Change',
    f'{forecast_year_1} Change': f"{impact_details_segment3['npl_formation_change'][0]:+.2f}pp",
    f'{forecast_year_1} PBT Impact (T)': 0,  # Part of combined provision impact
    f'{forecast_year_2} Change': f"{impact_details_segment3['npl_formation_change'][1]:+.2f}pp",
    f'{forecast_year_2} PBT Impact (T)': 0
})

impact_data.append({
    'Segment': 'Asset Quality',
    'Input': 'NPL Coverage Change',
    f'{forecast_year_1} Change': f"{impact_details_segment3['npl_coverage_change'][0]:+.1f}pp",
    f'{forecast_year_1} PBT Impact (T)': 0,  # Part of combined provision impact
    f'{forecast_year_2} Change': f"{impact_details_segment3['npl_coverage_change'][1]:+.1f}pp",
    f'{forecast_year_2} PBT Impact (T)': 0
})

impact_data.append({
    'Segment': 'Asset Quality',
    'Input': 'Provision Expense Impact',
    f'{forecast_year_1} Change': f"{impact_details_segment3['provision_expense_change'][0] / 1e12:+.2f}T",
    f'{forecast_year_1} PBT Impact (T)': impact_details_segment3['pbt_impact'][0] / 1e12,
    f'{forecast_year_2} Change': f"{impact_details_segment3['provision_expense_change'][1] / 1e12:+.2f}T",
    f'{forecast_year_2} PBT Impact (T)': impact_details_segment3['pbt_impact'][1] / 1e12
})

# Segment 3 Subtotal
impact_data.append({
    'Segment': 'Segment 3 Subtotal',
    'Input': '',
    f'{forecast_year_1} Change': '',
    f'{forecast_year_1} PBT Impact (T)': st.session_state.get(f'{ticker}_pbt_change_segment3_{forecast_year_1}', 0) / 1e12,
    f'{forecast_year_2} Change': '',
    f'{forecast_year_2} PBT Impact (T)': st.session_state.get(f'{ticker}_pbt_change_segment3_{forecast_year_2}', 0) / 1e12
})

# Total Impact
total_change_f1 = sum([st.session_state.get(f'{ticker}_pbt_change_segment{i}_{forecast_year_1}', 0) for i in [1, 2, 3]])
total_change_f2 = sum([st.session_state.get(f'{ticker}_pbt_change_segment{i}_{forecast_year_2}', 0) for i in [1, 2, 3]])

impact_data.append({
    'Segment': 'TOTAL IMPACT',
    'Input': '',
    f'{forecast_year_1} Change': '',
    f'{forecast_year_1} PBT Impact (T)': total_change_f1 / 1e12,
    f'{forecast_year_2} Change': '',
    f'{forecast_year_2} PBT Impact (T)': total_change_f2 / 1e12
})

# Create DataFrame and set index
impact_df = pd.DataFrame(impact_data)

# Create combined index from Segment and Input columns
impact_df['Index'] = impact_df.apply(lambda row: row['Segment'] if row['Input'] == '' else f"  {row['Input']}", axis=1)
impact_df = impact_df.set_index('Index')
impact_df = impact_df.drop(columns=['Segment', 'Input'])

# Style function to bold and highlight subtotals and total
def style_impact_row(row):
    if 'Subtotal' in row.name or 'TOTAL' in row.name:
        return ['font-weight: bold; background-color: #e8e8e8'] * len(row)
    else:
        return [''] * len(row)

# Display the impact table
st.dataframe(
    impact_df.style
    .format({
        f'{forecast_year_1} PBT Impact (T)': '{:.2f}',
        f'{forecast_year_2} PBT Impact (T)': '{:.2f}'
    }, na_rep='')
    .apply(style_impact_row, axis=1)
    .set_properties(**{'text-align': 'right'}, subset=[f'{forecast_year_1} PBT Impact (T)', f'{forecast_year_2} PBT Impact (T)'])
    , use_container_width=True, height=480
)

# Calculate adjusted PBT
adjusted_pbt_f1 = forecast_1_vals['IS.18'] + total_change_f1
adjusted_pbt_f2 = forecast_2_vals['IS.18'] + total_change_f2

# Update session state
st.session_state[f'{ticker}_pbt_{forecast_year_1}_adjusted'] = adjusted_pbt_f1
st.session_state[f'{ticker}_pbt_{forecast_year_2}_adjusted'] = adjusted_pbt_f2

# Update header with final values
pbt_last = historical_data.loc[last_complete_year, 'IS.18'] if last_complete_year in historical_data.index else 1
pbt_yoy_f1 = ((adjusted_pbt_f1 / pbt_last) - 1) * 100 if pbt_last != 0 else 0
pbt_yoy_f2 = ((adjusted_pbt_f2 / adjusted_pbt_f1) - 1) * 100 if adjusted_pbt_f1 != 0 else 0

header_placeholder.markdown(f'''
<div class="fixed-header">
    <div class="metrics-container">
        <div class="ticker-box">
            <div class="metric-label">Bank</div>
            <div class="ticker-value">{ticker}</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">{forecast_year_1} Forecast</div>
            <div class="metric-value">{adjusted_pbt_f1/1e12:.2f}T</div>
            <div class="metric-delta">{pbt_yoy_f1:+.1f}% YoY</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">{forecast_year_2} Forecast</div>
            <div class="metric-value">{adjusted_pbt_f2/1e12:.2f}T</div>
            <div class="metric-delta">{pbt_yoy_f2:+.1f}% YoY</div>
        </div>
    </div>
</div>
''', unsafe_allow_html=True)