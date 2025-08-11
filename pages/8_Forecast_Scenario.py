import streamlit as st
import pandas as pd
import sys
import os

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Page configuration
st.set_page_config(
    page_title="Forecast Scenario Analysis",
    page_icon="📊",
    layout="wide"
)

# CSS for fixed header positioning
st.markdown("""
<style>
    /* Fixed header that stays at top of viewport */
    .fixed-header {
        position: fixed;
        top: 50px;
        left: 0;
        right: 0;
        background: white;
        border-bottom: 2px solid #f0f2f6;
        z-index: 9999;
        padding: 10px 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Container for metrics - shifted right for better centering */
    .metrics-container {
        max-width: 1000px;
        margin: 0 auto;
        margin-left: calc(50% - 350px);
        display: flex;
        justify-content: space-around;
        align-items: center;
        padding-left: 100px;
    }
    
    .metric-box {
        text-align: center;
        color: #262730;
    }
    
    .metric-label {
        font-size: 1rem;
        color: #808495;
        margin-bottom: 0.3rem;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #262730;
        margin: 0.3rem 0;
    }
    
    .metric-delta {
        font-size: 0.9rem;
        color: #09ab3b;
    }
    
    .ticker-box {
        text-align: center;
        padding-right: 30px;
        border-right: 2px solid #f0f2f6;
        margin-right: 30px;
    }
    
    .ticker-label {
        font-size: 0.8rem;
        color: #808495;
        margin-bottom: 0.2rem;
    }
    
    .ticker-value {
        font-size: 2rem;
        font-weight: bold;
        color: #478B81;
    }
    
    .metric-subtitle {
        font-size: 0.75rem;
        color: #808495;
        margin-top: -0.2rem;
        margin-bottom: 0.2rem;
    }
    
    /* Add padding to main content to account for fixed header */
    .main > div:first-child {
        padding-top: 270px !important;
    }
    
    /* Adjust Streamlit's default container */
    .block-container {
        padding-top: 0 !important;
    }
    
    /* Reduce font sizes for main content */
    h1 {
        font-size: 1.6rem !important;
    }
    
    h2 {
        font-size: 1.15rem !important;
    }
    
    h3 {
        font-size: 1rem !important;
    }
    
    p, li, div[data-testid="stMarkdownContainer"] {
        font-size: 0.85rem !important;
    }
    
    /* Smaller text in dataframes */
    .dataframe, div[data-testid="stDataFrame"] * {
        font-size: 0.8rem !important;
    }
    
    /* Smaller input labels and text */
    label[data-testid="stWidgetLabel"] {
        font-size: 0.85rem !important;
    }
    
    input[type="number"], div[data-testid="stNumberInput"] input {
        font-size: 0.85rem !important;
        height: 2.3rem !important;
    }
    
    /* Impact Analysis section */
    div[data-testid="column"] p {
        font-size: 0.8rem !important;
        line-height: 1.4 !important;
    }
    
    /* Button text */
    button[kind="primary"] {
        font-size: 0.85rem !important;
        padding: 0.35rem 1rem !important;
    }
    
    /* Hide the duplicate metrics if Streamlit renders them */
    .element-container:has(.sticky-metrics) {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 9999;
    }
</style>
""", unsafe_allow_html=True)

st.title("Forecast Scenario Analysis")

# Load data
@st.cache_data(ttl=1)  # Set TTL to 1 second to force refresh
def load_data():
    df_year = pd.read_csv(os.path.join(project_root, 'Data/dfsectoryear.csv'))
    df_quarter = pd.read_csv(os.path.join(project_root, 'Data/dfsectorquarter.csv'))
    keyitem = pd.read_excel(os.path.join(project_root, 'Data/Key_items.xlsx'))
    # Determine last complete year dynamically
    dfis = pd.read_csv(os.path.join(project_root, 'Data/IS_Bank.csv'))
    complete_years = dfis[dfis['LENGTHREPORT'] == 5]['YEARREPORT'].unique()
    last_complete_year = int(max(complete_years)) if len(complete_years) > 0 else last_complete_year
    return df_year, df_quarter, keyitem, last_complete_year

df_year, df_quarter, keyitem, last_complete_year = load_data()

# Define forecast years dynamically
forecast_year_1 = last_complete_year + 1
forecast_year_2 = last_complete_year + 2

# Get only banks with forecast data (exclude sectors and aggregates)
forecast_data = df_year[df_year['Year'].isin([forecast_year_1, forecast_year_2])]
banks_with_forecast = forecast_data[forecast_data['TICKER'].str.len() == 3]['TICKER'].unique()
banks_with_forecast = sorted(banks_with_forecast)

# Sidebar: Choose ticker
ticker = st.sidebar.selectbox(
    "Select Bank:",
    banks_with_forecast,
    index=0
)

# Add separator
st.sidebar.markdown("---")

# Revert to Default button - we'll define this after loading the data
revert_button = st.sidebar.button("Revert to Default Forecast", type="secondary", use_container_width=True)

# Get historical and forecast data for selected ticker
historical_data = df_year[(df_year['TICKER'] == ticker) & (df_year['Year'].isin([last_complete_year-1, last_complete_year]))]
forecast_1 = df_year[(df_year['TICKER'] == ticker) & (df_year['Year'] == forecast_year_1)]
forecast_2 = df_year[(df_year['TICKER'] == ticker) & (df_year['Year'] == forecast_year_2)]

# Get quarterly data for first forecast year
df_quarter['Year'] = 2000 + df_quarter['Date_Quarter'].str.extract(r'Q(\d+)').astype(int)
quarter_codes = [f'1Q{str(forecast_year_1)[2:]}', f'2Q{str(forecast_year_1)[2:]}']
quarterly_forecast_1 = df_quarter[(df_quarter['TICKER'] == ticker) & 
                                  (df_quarter['Year'] == forecast_year_1) & 
                                  (df_quarter['Date_Quarter'].isin(quarter_codes))]

# Initialize session state for forecast values if not exists
if 'forecast_values' not in st.session_state:
    st.session_state.forecast_values = {}

# Get current forecast PBT values
pbt_forecast_1_original = forecast_1['IS.18'].values[0] if len(forecast_1) > 0 else 0
pbt_forecast_2_original = forecast_2['IS.18'].values[0] if len(forecast_2) > 0 else 0
pbt_last_complete = historical_data[historical_data['Year'] == last_complete_year]['IS.18'].values[0] if len(historical_data[historical_data['Year'] == last_complete_year]) > 0 else 0

# Calculate original YoY growth
pbt_yoy_forecast_1_original = ((pbt_forecast_1_original / pbt_last_complete) - 1) * 100 if pbt_last_complete != 0 else 0
pbt_yoy_forecast_2_original = ((pbt_forecast_2_original / pbt_forecast_1_original) - 1) * 100 if pbt_forecast_1_original != 0 else 0

# Initialize adjusted values and segment changes
if f'{ticker}_pbt_{forecast_year_1}_adjusted' not in st.session_state:
    st.session_state[f'{ticker}_pbt_{forecast_year_1}_adjusted'] = pbt_forecast_1_original
    st.session_state[f'{ticker}_pbt_{forecast_year_2}_adjusted'] = pbt_forecast_2_original
    st.session_state[f'{ticker}_pbt_change_segment1_{forecast_year_1}'] = 0
    st.session_state[f'{ticker}_pbt_change_segment1_{forecast_year_2}'] = 0
    st.session_state[f'{ticker}_pbt_change_segment2_{forecast_year_1}'] = 0
    st.session_state[f'{ticker}_pbt_change_segment2_{forecast_year_2}'] = 0
    st.session_state[f'{ticker}_pbt_change_segment3_{forecast_year_1}'] = 0
    st.session_state[f'{ticker}_pbt_change_segment3_{forecast_year_2}'] = 0

# Placeholder for header - will be filled in after calculations
header_placeholder = st.empty()

# Add spacing to account for fixed header
st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

st.markdown("---")

# Segment 1: Net Interest Income
st.header("Segment 1: Net Interest Income Adjustment")

# Prepare historical data table for NIM and Loan
def prepare_historical_table():
    # Get data for last_complete_year-1-last_complete_year (yearly) and Q1-Q2 forecast_year_1
    data_rows = []
    
    # Add last_complete_year-1-last_complete_year yearly data
    for year in [last_complete_year-1, last_complete_year]:
        year_data = historical_data[historical_data['Year'] == year]
        if len(year_data) > 0:
            row = year_data.iloc[0]
            loan = row['BS.12'] if 'BS.12' in row and pd.notna(row['BS.12']) else row['BS.13']
            nim = row['CA.13'] if pd.notna(row['CA.13']) else 0
            nii = row['IS.3'] if pd.notna(row['IS.3']) else 0
            data_rows.append({
                'Period': str(year),
                'Loan (BS.12)': loan / 1e12,  # Convert to trillion
                'NIM (%)': nim * 100,
                'NII (IS.3)': nii / 1e12
            })
    
    # Add Q1-Q2 forecast_year_1 data
    for quarter in ['1Q25', '2Q25']:
        q_data = quarterly_forecast_1[quarterly_forecast_1['Date_Quarter'] == quarter]
        if len(q_data) > 0:
            row = q_data.iloc[0]
            loan = row['BS.12'] if 'BS.12' in row and pd.notna(row['BS.12']) else row['BS.13']
            nim = row['CA.13'] if pd.notna(row['CA.13']) else 0
            nii = row['IS.3'] if pd.notna(row['IS.3']) else 0
            data_rows.append({
                'Period': quarter,
                'Loan (BS.12)': loan / 1e12,
                'NIM (%)': nim * 100,
                'NII (IS.3)': nii / 1e12
            })
    
    # Add forecast data for forecast_year_1-forecast_year_2
    for year, forecast in [(forecast_year_1, forecast_1), (forecast_year_2, forecast_2)]:
        if len(forecast) > 0:
            row = forecast.iloc[0]
            loan = row['BS.12'] if 'BS.12' in row and pd.notna(row['BS.12']) else row['BS.13']
            nim = row['CA.13'] if pd.notna(row['CA.13']) else 0
            nii = row['IS.3'] if pd.notna(row['IS.3']) else 0
            
            # Calculate loan growth YoY
            if year == forecast_year_1:
                loan_prev = historical_data[historical_data['Year'] == last_complete_year]['BS.12'].values[0] if len(historical_data[historical_data['Year'] == last_complete_year]) > 0 else loan
                if pd.isna(loan_prev):
                    loan_prev = historical_data[historical_data['Year'] == last_complete_year]['BS.13'].values[0] if len(historical_data[historical_data['Year'] == last_complete_year]) > 0 else loan
            else:  # forecast_year_2
                loan_prev = forecast_1['BS.12'].values[0] if len(forecast_1) > 0 else loan
                if pd.isna(loan_prev):
                    loan_prev = forecast_1['BS.13'].values[0] if len(forecast_1) > 0 else loan
            
            loan_growth = ((loan / loan_prev) - 1) * 100 if loan_prev != 0 else 0
            
            data_rows.append({
                'Period': f"{year}F",
                'Loan (BS.12)': loan / 1e12,
                'Loan Growth YoY (%)': loan_growth,
                'NIM (%)': nim * 100,
                'NII (IS.3)': nii / 1e12
            })
    
    return pd.DataFrame(data_rows)

# Display historical table
historical_table = prepare_historical_table()
historical_table = historical_table.set_index('Period')
st.subheader("Historical and Forecast Data")
st.dataframe(historical_table.style.format({
    'Loan (BS.12)': '{:.2f}T',
    'Loan Growth YoY (%)': '{:.1f}%',
    'NIM (%)': '{:.2f}%',
    'NII (IS.3)': '{:.2f}T'
}), use_container_width=True)

# Input section for adjustments
st.subheader("Adjust Forecast Assumptions")

col1, col2 = st.columns(2)

# Get original forecast values
nim_forecast_1_original = forecast_1['CA.13'].values[0] * 100 if len(forecast_1) > 0 else 3.0
nim_forecast_2_original = forecast_2['CA.13'].values[0] * 100 if len(forecast_2) > 0 else 3.0

loan_last_complete = historical_data[historical_data['Year'] == last_complete_year]['BS.12'].values[0] if len(historical_data[historical_data['Year'] == last_complete_year]) > 0 else 1e15
if pd.isna(loan_last_complete):
    loan_last_complete = historical_data[historical_data['Year'] == last_complete_year]['BS.13'].values[0] if len(historical_data[historical_data['Year'] == last_complete_year]) > 0 else 1e15

loan_forecast_year_1_original = forecast_1['BS.12'].values[0] if len(forecast_1) > 0 else loan_last_complete * 1.15
if pd.isna(loan_forecast_year_1_original):
    loan_forecast_year_1_original = forecast_1['BS.13'].values[0] if len(forecast_1) > 0 else loan_last_complete * 1.15

loan_forecast_year_2_original = forecast_2['BS.12'].values[0] if len(forecast_2) > 0 else loan_forecast_year_1_original * 1.15
if pd.isna(loan_forecast_year_2_original):
    loan_forecast_year_2_original = forecast_2['BS.13'].values[0] if len(forecast_2) > 0 else loan_forecast_year_1_original * 1.15

loan_growth_forecast_year_1_original = ((loan_forecast_year_1_original / loan_last_complete) - 1) * 100 if loan_last_complete != 0 else 15
loan_growth_forecast_year_2_original = ((loan_forecast_year_2_original / loan_forecast_year_1_original) - 1) * 100 if loan_forecast_year_1_original != 0 else 15

nii_forecast_1_original = forecast_1['IS.3'].values[0] if len(forecast_1) > 0 else 0
nii_forecast_2_original = forecast_2['IS.3'].values[0] if len(forecast_2) > 0 else 0

# Handle revert button - set all values to original forecast
if revert_button:
    # Set all the session state keys to original values
    st.session_state[f"{ticker}_nim_{forecast_year_1}"] = nim_forecast_1_original
    st.session_state[f"{ticker}_nim_{forecast_year_2}"] = nim_forecast_2_original
    st.session_state[f"{ticker}_loan_growth_{forecast_year_1}"] = loan_growth_forecast_year_1_original
    st.session_state[f"{ticker}_loan_growth_{forecast_year_2}"] = loan_growth_forecast_year_2_original
    
    # We'll add OPEX and Asset Quality values after they're calculated below
    st.session_state['revert_needed'] = True
    st.sidebar.success("Values will be reverted to defaults!")

with col1:
    st.markdown(f"**{forecast_year_1} Adjustments**")
    nim_forecast_year_1_new = st.number_input(
        f"NIM {forecast_year_1} (%)", 
        min_value=0.0, 
        max_value=10.0, 
        value=nim_forecast_1_original,
        step=0.1,
        key=f"{ticker}_nim_{forecast_year_1}"
    )
    loan_growth_forecast_year_1_new = st.number_input(
        f"Loan Growth YoY {forecast_year_1} (%)", 
        min_value=-20.0, 
        max_value=50.0, 
        value=loan_growth_forecast_year_1_original,
        step=1.0,
        key=f"{ticker}_loan_growth_{forecast_year_1}"
    )

with col2:
    st.markdown(f"**{forecast_year_2} Adjustments**")
    nim_forecast_year_2_new = st.number_input(
        f"NIM {forecast_year_2} (%)", 
        min_value=0.0, 
        max_value=10.0, 
        value=nim_forecast_2_original,
        step=0.1,
        key=f"{ticker}_nim_{forecast_year_2}"
    )
    loan_growth_forecast_year_2_new = st.number_input(
        f"Loan Growth YoY {forecast_year_2} (%)", 
        min_value=-20.0, 
        max_value=50.0, 
        value=loan_growth_forecast_year_2_original,
        step=1.0,
        key=f"{ticker}_loan_growth_{forecast_year_2}"
    )

# Calculate PBT changes based on formula
# Formula: Change in PBT = (Loan growth YoY CHANGE vs. old forecast /2) + (New NIM/ Old NIM - 1) * Current NII forecast

# For forecast_year_1
loan_growth_change_forecast_year_1 = loan_growth_forecast_year_1_new - loan_growth_forecast_year_1_original
nim_ratio_forecast_year_1 = (nim_forecast_year_1_new / nim_forecast_1_original) if nim_forecast_1_original != 0 else 1
pbt_change_segment1_forecast_year_1 = (loan_growth_change_forecast_year_1 / 2) * (pbt_forecast_1_original / 100) + (nim_ratio_forecast_year_1 - 1) * nii_forecast_1_original

# For forecast_year_2
loan_growth_change_forecast_year_2 = loan_growth_forecast_year_2_new - loan_growth_forecast_year_2_original
nim_ratio_forecast_year_2 = (nim_forecast_year_2_new / nim_forecast_2_original) if nim_forecast_2_original != 0 else 1
pbt_change_segment1_forecast_year_2 = (loan_growth_change_forecast_year_2 / 2) * (pbt_forecast_2_original / 100) + (nim_ratio_forecast_year_2 - 1) * nii_forecast_2_original

# Store segment 1 changes for later use
st.session_state[f'{ticker}_pbt_change_segment1_{forecast_year_1}'] = pbt_change_segment1_forecast_year_1
st.session_state[f'{ticker}_pbt_change_segment1_{forecast_year_2}'] = pbt_change_segment1_forecast_year_2

# Display impact analysis
st.subheader("Impact Analysis")
impact_col1, impact_col2 = st.columns(2)

with impact_col1:
    st.markdown(f"**{forecast_year_1} Impact**")
    st.write(f"Loan Growth Change: {loan_growth_change_forecast_year_1:.1f}%")
    st.write(f"NIM Ratio: {nim_ratio_forecast_year_1:.3f}")
    st.write(f"PBT Change from Loan Growth: {(loan_growth_change_forecast_year_1 / 2) * (pbt_forecast_1_original / 100) / 1e12:.2f}T")
    st.write(f"PBT Change from NIM: {(nim_ratio_forecast_year_1 - 1) * nii_forecast_1_original / 1e12:.2f}T")
    st.write(f"**Total PBT Change: {pbt_change_segment1_forecast_year_1 / 1e12:.2f}T**")

with impact_col2:
    st.markdown(f"**{forecast_year_2} Impact**")
    st.write(f"Loan Growth Change: {loan_growth_change_forecast_year_2:.1f}%")
    st.write(f"NIM Ratio: {nim_ratio_forecast_year_2:.3f}")
    st.write(f"PBT Change from Loan Growth: {(loan_growth_change_forecast_year_2 / 2) * (pbt_forecast_2_original / 100) / 1e12:.2f}T")
    st.write(f"PBT Change from NIM: {(nim_ratio_forecast_year_2 - 1) * nii_forecast_2_original / 1e12:.2f}T")
    st.write(f"**Total PBT Change: {pbt_change_segment1_forecast_year_2 / 1e12:.2f}T**")

# Auto-update when inputs change (removed manual button since Streamlit auto-reruns on input change)

st.markdown("---")

# Segment 2: OPEX
st.header("Segment 2: Operating Expenses (OPEX) Adjustment")

# Prepare OPEX and CIR historical data
def prepare_opex_table():
    data_rows = []
    
    # Add last_complete_year-1-last_complete_year yearly data
    for year in [last_complete_year-1, last_complete_year]:
        year_data = historical_data[historical_data['Year'] == year]
        if len(year_data) > 0:
            row = year_data.iloc[0]
            opex = row['IS.15'] if pd.notna(row['IS.15']) else 0
            toi = row['IS.14'] if pd.notna(row['IS.14']) else 0
            cir = row['CA.6'] if pd.notna(row['CA.6']) else (opex/toi if toi != 0 else 0)
            data_rows.append({
                'Period': str(year),
                'OPEX (IS.15)': opex / 1e12,
                'TOI (IS.14)': toi / 1e12,
                'CIR (%)': cir * 100
            })
    
    # Add forecast data for forecast_year_1-forecast_year_2
    for year, forecast in [(forecast_year_1, forecast_1), (forecast_year_2, forecast_2)]:
        if len(forecast) > 0:
            row = forecast.iloc[0]
            opex = row['IS.15'] if pd.notna(row['IS.15']) else 0
            toi = row['IS.14'] if pd.notna(row['IS.14']) else 0
            cir = row['CA.6'] if pd.notna(row['CA.6']) else (opex/toi if toi != 0 else 0)
            
            # Calculate YoY growth
            if year == forecast_year_1:
                opex_prev = historical_data[historical_data['Year'] == last_complete_year]['IS.15'].values[0] if len(historical_data[historical_data['Year'] == last_complete_year]) > 0 else opex
            else:  # forecast_year_2
                opex_prev = forecast_1['IS.15'].values[0] if len(forecast_1) > 0 else opex
            
            opex_growth = ((opex / opex_prev) - 1) * 100 if opex_prev != 0 else 0
            
            data_rows.append({
                'Period': f"{year}F",
                'OPEX (IS.15)': opex / 1e12,
                'OPEX Growth YoY (%)': opex_growth,
                'TOI (IS.14)': toi / 1e12,
                'CIR (%)': cir * 100
            })
    
    return pd.DataFrame(data_rows)

# Display OPEX table
opex_table = prepare_opex_table()
opex_table = opex_table.set_index('Period')
st.subheader("Historical and Forecast OPEX & CIR")
st.dataframe(opex_table.style.format({
    'OPEX (IS.15)': '{:.2f}T',
    'OPEX Growth YoY (%)': '{:.1f}%',
    'TOI (IS.14)': '{:.2f}T',
    'CIR (%)': '{:.1f}%'
}), use_container_width=True)

# Input section for OPEX adjustments
st.subheader("Adjust OPEX Growth")

col1, col2 = st.columns(2)

# Get original OPEX values
opex_last_complete_year = historical_data[historical_data['Year'] == last_complete_year]['IS.15'].values[0] if len(historical_data[historical_data['Year'] == last_complete_year]) > 0 else 0
opex_forecast_year_1_original = forecast_1['IS.15'].values[0] if len(forecast_1) > 0 else opex_last_complete_year * 1.1
opex_forecast_year_2_original = forecast_2['IS.15'].values[0] if len(forecast_2) > 0 else opex_forecast_year_1_original * 1.1

opex_growth_forecast_year_1_original = ((opex_forecast_year_1_original / opex_last_complete_year) - 1) * 100 if opex_last_complete_year != 0 else 10
opex_growth_forecast_year_2_original = ((opex_forecast_year_2_original / opex_forecast_year_1_original) - 1) * 100 if opex_forecast_year_1_original != 0 else 10

# Get original TOI values
toi_forecast_year_1_original = forecast_1['IS.14'].values[0] if len(forecast_1) > 0 else 0
toi_forecast_year_2_original = forecast_2['IS.14'].values[0] if len(forecast_2) > 0 else 0

# Handle revert for OPEX if needed
if st.session_state.get('revert_needed', False):
    st.session_state[f"{ticker}_opex_growth_{forecast_year_1}"] = opex_growth_forecast_year_1_original
    st.session_state[f"{ticker}_opex_growth_{forecast_year_2}"] = opex_growth_forecast_year_2_original

with col1:
    st.markdown(f"**{forecast_year_1} Adjustments**")
    opex_growth_forecast_year_1_new = st.number_input(
        f"OPEX Growth YoY {forecast_year_1} (%)", 
        min_value=-30.0, 
        max_value=50.0, 
        value=opex_growth_forecast_year_1_original,
        step=1.0,
        key=f"{ticker}_opex_growth_{forecast_year_1}"
    )

with col2:
    st.markdown(f"**{forecast_year_2} Adjustments**")
    opex_growth_forecast_year_2_new = st.number_input(
        f"OPEX Growth YoY {forecast_year_2} (%)", 
        min_value=-30.0, 
        max_value=50.0, 
        value=opex_growth_forecast_year_2_original,
        step=1.0,
        key=f"{ticker}_opex_growth_{forecast_year_2}"
    )

# Calculate new OPEX values
opex_forecast_year_1_new = opex_last_complete_year * (1 + opex_growth_forecast_year_1_new / 100)
opex_forecast_year_2_new = opex_forecast_year_1_new * (1 + opex_growth_forecast_year_2_new / 100)

# Calculate OPEX changes
opex_change_forecast_year_1 = opex_forecast_year_1_new - opex_forecast_year_1_original
opex_change_forecast_year_2 = opex_forecast_year_2_new - opex_forecast_year_2_original

# Calculate PBT changes from OPEX (OPEX is already negative in P&L)
pbt_change_segment2_forecast_year_1 = opex_change_forecast_year_1
pbt_change_segment2_forecast_year_2 = opex_change_forecast_year_2

# Store segment 2 changes
st.session_state[f'{ticker}_pbt_change_segment2_{forecast_year_1}'] = pbt_change_segment2_forecast_year_1
st.session_state[f'{ticker}_pbt_change_segment2_{forecast_year_2}'] = pbt_change_segment2_forecast_year_2

# Calculate new TOI (original TOI + PBT changes from Segment 1)
# TOI = Revenue - COGS, and NII changes affect TOI
toi_forecast_year_1_new = toi_forecast_year_1_original + st.session_state.get(f'{ticker}_pbt_change_segment1_{forecast_year_1}', 0)
toi_forecast_year_2_new = toi_forecast_year_2_original + st.session_state.get(f'{ticker}_pbt_change_segment1_{forecast_year_2}', 0)

# Calculate new CIR
cir_forecast_year_1_original = (opex_forecast_year_1_original / toi_forecast_year_1_original * 100) if toi_forecast_year_1_original != 0 else 0
cir_forecast_year_2_original = (opex_forecast_year_2_original / toi_forecast_year_2_original * 100) if toi_forecast_year_2_original != 0 else 0

cir_forecast_year_1_new = (opex_forecast_year_1_new / toi_forecast_year_1_new * 100) if toi_forecast_year_1_new != 0 else 0
cir_forecast_year_2_new = (opex_forecast_year_2_new / toi_forecast_year_2_new * 100) if toi_forecast_year_2_new != 0 else 0

# Display CIR analysis
st.subheader("CIR Impact Analysis")
cir_col1, cir_col2 = st.columns(2)

with cir_col1:
    st.markdown(f"**{forecast_year_1} CIR Analysis**")
    st.write(f"Original CIR: {cir_forecast_year_1_original:.1f}%")
    st.write(f"New CIR: {cir_forecast_year_1_new:.1f}%")
    st.write(f"CIR Change: {cir_forecast_year_1_new - cir_forecast_year_1_original:+.1f}pp")
    st.write(f"")
    st.write(f"OPEX Change: {opex_change_forecast_year_1 / 1e12:.2f}T")
    st.write(f"**PBT Impact: {pbt_change_segment2_forecast_year_1 / 1e12:+.2f}T**")

with cir_col2:
    st.markdown(f"**{forecast_year_2} CIR Analysis**")
    st.write(f"Original CIR: {cir_forecast_year_2_original:.1f}%")
    st.write(f"New CIR: {cir_forecast_year_2_new:.1f}%")
    st.write(f"CIR Change: {cir_forecast_year_2_new - cir_forecast_year_2_original:+.1f}pp")
    st.write(f"")
    st.write(f"OPEX Change: {opex_change_forecast_year_2 / 1e12:.2f}T")
    st.write(f"**PBT Impact: {pbt_change_segment2_forecast_year_2 / 1e12:+.2f}T**")

# Calculate total PBT changes (Segment 1 + Segment 2)
pbt_change_total_forecast_year_1 = st.session_state.get(f'{ticker}_pbt_change_segment1_{forecast_year_1}', 0) + pbt_change_segment2_forecast_year_1
pbt_change_total_forecast_year_2 = st.session_state.get(f'{ticker}_pbt_change_segment1_{forecast_year_2}', 0) + pbt_change_segment2_forecast_year_2

# Update session state with total adjusted PBT
st.session_state[f'{ticker}_pbt_{forecast_year_1}_adjusted'] = pbt_forecast_1_original + pbt_change_total_forecast_year_1
st.session_state[f'{ticker}_pbt_{forecast_year_2}_adjusted'] = pbt_forecast_2_original + pbt_change_total_forecast_year_2

st.markdown("---")

# Segment 3: Asset Quality
st.header("Segment 3: Asset Quality Assumptions")

# Prepare Asset Quality historical data
def prepare_asset_quality_table():
    data_rows = []
    
    # Add last_complete_year-1-last_complete_year yearly data
    for year in [last_complete_year-1, last_complete_year]:
        year_data = historical_data[historical_data['Year'] == year]
        if len(year_data) > 0:
            row = year_data.iloc[0]
            loan = row['BS.12'] if 'BS.12' in row and pd.notna(row['BS.12']) else row['BS.13']
            npl = row['CA.3'] if pd.notna(row['CA.3']) else 0
            npl_formation = abs(row['CA.23']) if pd.notna(row['CA.23']) else 0
            bs14 = row['BS.14'] if pd.notna(row['BS.14']) else 0
            npl_coverage = (-bs14 / (npl * loan) * 100) if (npl * loan) != 0 else 0
            provision_expense = row['IS.17'] if pd.notna(row['IS.17']) else 0
            # Write-offs are stored as negative values
            write_off = row['Nt.220'] if 'Nt.220' in row and pd.notna(row['Nt.220']) else 0
            
            data_rows.append({
                'Period': str(year),
                'NPL (%)': npl * 100,
                'NPL Formation (%)': npl_formation * 100,
                'NPL Coverage (%)': npl_coverage,
                'Provision Expense': provision_expense / 1e12,
                'Write-off (Nt.220)': write_off / 1e12
            })
    
    # Add forecast data for forecast_year_1-forecast_year_2
    for year, forecast in [(forecast_year_1, forecast_1), (forecast_year_2, forecast_2)]:
        if len(forecast) > 0:
            row = forecast.iloc[0]
            loan = row['BS.12'] if 'BS.12' in row and pd.notna(row['BS.12']) else row['BS.13']
            npl = row['CA.3'] if pd.notna(row['CA.3']) else 0
            npl_formation = abs(row['CA.23']) if pd.notna(row['CA.23']) else 0
            bs14 = row['BS.14'] if pd.notna(row['BS.14']) else 0
            npl_coverage = (-bs14 / (npl * loan) * 100) if (npl * loan) != 0 else 0
            provision_expense = row['IS.17'] if pd.notna(row['IS.17']) else 0
            # Write-offs are stored as negative values
            write_off = row['Nt.220'] if 'Nt.220' in row and pd.notna(row['Nt.220']) else 0
            
            data_rows.append({
                'Period': f"{year}F",
                'NPL (%)': npl * 100,
                'NPL Formation (%)': npl_formation * 100,
                'NPL Coverage (%)': npl_coverage,
                'Provision Expense': provision_expense / 1e12,
                'Write-off (Nt.220)': write_off / 1e12
            })
    
    return pd.DataFrame(data_rows)

# Display Asset Quality table
asset_quality_table = prepare_asset_quality_table()
asset_quality_table = asset_quality_table.set_index('Period')
st.subheader("Historical and Forecast Asset Quality Metrics")
st.dataframe(asset_quality_table.style.format({
    'NPL (%)': '{:.2f}%',
    'NPL Formation (%)': '{:.2f}%',
    'NPL Coverage (%)': '{:.1f}%',
    'Provision Expense': '{:.2f}T',
    'Write-off (Nt.220)': '{:.2f}T'
}), use_container_width=True)

# Input section for Asset Quality adjustments
st.subheader("Adjust Asset Quality Assumptions")

col1, col2 = st.columns(2)

# Get original values
npl_forecast_year_1_original = forecast_1['CA.3'].values[0] * 100 if len(forecast_1) > 0 else 1.5
npl_forecast_year_2_original = forecast_2['CA.3'].values[0] * 100 if len(forecast_2) > 0 else 1.5

# NPL formation in data is negative, convert to positive for display/input
npl_formation_forecast_year_1_original = abs(forecast_1['CA.23'].values[0] * 100) if len(forecast_1) > 0 else 0.5
npl_formation_forecast_year_2_original = abs(forecast_2['CA.23'].values[0] * 100) if len(forecast_2) > 0 else 0.5

# Calculate original NPL coverage
loan_forecast_year_1_forecast = forecast_1['BS.12'].values[0] if len(forecast_1) > 0 else 0
if pd.isna(loan_forecast_year_1_forecast):
    loan_forecast_year_1_forecast = forecast_1['BS.13'].values[0] if len(forecast_1) > 0 else 0

loan_forecast_year_2_forecast = forecast_2['BS.12'].values[0] if len(forecast_2) > 0 else 0
if pd.isna(loan_forecast_year_2_forecast):
    loan_forecast_year_2_forecast = forecast_2['BS.13'].values[0] if len(forecast_2) > 0 else 0

bs14_forecast_year_1 = forecast_1['BS.14'].values[0] if len(forecast_1) > 0 else 0
bs14_forecast_year_2 = forecast_2['BS.14'].values[0] if len(forecast_2) > 0 else 0

npl_coverage_forecast_year_1_original = (-bs14_forecast_year_1 / (npl_forecast_year_1_original/100 * loan_forecast_year_1_forecast) * 100) if (npl_forecast_year_1_original * loan_forecast_year_1_forecast) != 0 else 100
npl_coverage_forecast_year_2_original = (-bs14_forecast_year_2 / (npl_forecast_year_2_original/100 * loan_forecast_year_2_forecast) * 100) if (npl_forecast_year_2_original * loan_forecast_year_2_forecast) != 0 else 100

# Handle revert for Asset Quality if needed
if st.session_state.get('revert_needed', False):
    st.session_state[f"{ticker}_npl_{forecast_year_1}"] = npl_forecast_year_1_original
    st.session_state[f"{ticker}_npl_{forecast_year_2}"] = npl_forecast_year_2_original
    st.session_state[f"{ticker}_npl_formation_{forecast_year_1}"] = npl_formation_forecast_year_1_original
    st.session_state[f"{ticker}_npl_formation_{forecast_year_2}"] = npl_formation_forecast_year_2_original
    st.session_state[f"{ticker}_npl_coverage_{forecast_year_1}"] = npl_coverage_forecast_year_1_original
    st.session_state[f"{ticker}_npl_coverage_{forecast_year_2}"] = npl_coverage_forecast_year_2_original
    
    # Clear the revert flag and rerun
    del st.session_state['revert_needed']
    st.rerun()

with col1:
    st.markdown(f"**{forecast_year_1} Adjustments**")
    npl_forecast_year_1_new = st.number_input(
        f"NPL {forecast_year_1} (%)", 
        min_value=0.0, 
        max_value=10.0, 
        value=npl_forecast_year_1_original,
        step=0.1,
        key=f"{ticker}_npl_{forecast_year_1}"
    )
    npl_formation_forecast_year_1_new = st.number_input(
        f"NPL Formation {forecast_year_1} (%)", 
        min_value=0.0, 
        max_value=5.0, 
        value=npl_formation_forecast_year_1_original,
        step=0.1,
        key=f"{ticker}_npl_formation_{forecast_year_1}"
    )
    npl_coverage_forecast_year_1_new = st.number_input(
        f"NPL Coverage {forecast_year_1} (%)", 
        min_value=0.0, 
        max_value=500.0, 
        value=npl_coverage_forecast_year_1_original,
        step=1.0,
        key=f"{ticker}_npl_coverage_{forecast_year_1}"
    )

with col2:
    st.markdown(f"**{forecast_year_2} Adjustments**")
    npl_forecast_year_2_new = st.number_input(
        f"NPL {forecast_year_2} (%)", 
        min_value=0.0, 
        max_value=10.0, 
        value=npl_forecast_year_2_original,
        step=0.1,
        key=f"{ticker}_npl_{forecast_year_2}"
    )
    npl_formation_forecast_year_2_new = st.number_input(
        f"NPL Formation {forecast_year_2} (%)", 
        min_value=0.0, 
        max_value=5.0, 
        value=npl_formation_forecast_year_2_original,
        step=0.1,
        key=f"{ticker}_npl_formation_{forecast_year_2}"
    )
    npl_coverage_forecast_year_2_new = st.number_input(
        f"NPL Coverage {forecast_year_2} (%)", 
        min_value=0.0, 
        max_value=500.0, 
        value=npl_coverage_forecast_year_2_original,
        step=1.0,
        key=f"{ticker}_npl_coverage_{forecast_year_2}"
    )

# Get loan values from Segment 1 (adjusted for loan growth)
loan_last_complete_value = loan_last_complete  # From segment 1
loan_forecast_year_1_new = loan_last_complete_value * (1 + loan_growth_forecast_year_1_new / 100)
loan_forecast_year_2_new = loan_forecast_year_1_new * (1 + loan_growth_forecast_year_2_new / 100)

# Get previous year values
bs14_last_complete_year = historical_data[historical_data['Year'] == last_complete_year]['BS.14'].values[0] if len(historical_data[historical_data['Year'] == last_complete_year]) > 0 else 0
npl_last_complete_year = historical_data[historical_data['Year'] == last_complete_year]['CA.3'].values[0] if len(historical_data[historical_data['Year'] == last_complete_year]) > 0 else 0.015

# Calculate new provision expense using the formula
# Step 1: Calculate Absolute NPL
npl_absolute_last_complete_year = npl_last_complete_year * loan_last_complete_value
npl_absolute_forecast_year_1_new = (npl_forecast_year_1_new / 100) * loan_forecast_year_1_new
npl_absolute_forecast_year_2_new = (npl_forecast_year_2_new / 100) * loan_forecast_year_2_new

npl_absolute_forecast_year_1_original = (npl_forecast_year_1_original / 100) * loan_forecast_year_1_forecast
npl_absolute_forecast_year_2_original = (npl_forecast_year_2_original / 100) * loan_forecast_year_2_forecast

# Step 2: Calculate Absolute NPL Formation
npl_formation_absolute_forecast_year_1_new = (npl_formation_forecast_year_1_new / 100) * loan_last_complete_value
npl_formation_absolute_forecast_year_2_new = (npl_formation_forecast_year_2_new / 100) * loan_forecast_year_1_new

npl_formation_absolute_forecast_year_1_original = (npl_formation_forecast_year_1_original / 100) * loan_last_complete_value
npl_formation_absolute_forecast_year_2_original = (npl_formation_forecast_year_2_original / 100) * loan_forecast_year_1_forecast

# Step 3: Calculate Provision absolute value
provision_last_complete_year = -bs14_last_complete_year  # BS.14 is negative, so negate it
provision_forecast_year_1_new = (npl_coverage_forecast_year_1_new / 100) * npl_absolute_forecast_year_1_new
provision_forecast_year_2_new = (npl_coverage_forecast_year_2_new / 100) * npl_absolute_forecast_year_2_new

provision_forecast_year_1_original = (npl_coverage_forecast_year_1_original / 100) * npl_absolute_forecast_year_1_original
provision_forecast_year_2_original = (npl_coverage_forecast_year_2_original / 100) * npl_absolute_forecast_year_2_original

# Step 4: Calculate New Provision Expense
# Formula needs to account for write-offs (which are negative)
# Get write-off values from forecast data
write_off_forecast_year_1 = forecast_1['Nt.220'].values[0] if len(forecast_1) > 0 and 'Nt.220' in forecast_1.columns and pd.notna(forecast_1['Nt.220'].values[0]) else 0
write_off_forecast_year_2 = forecast_2['Nt.220'].values[0] if len(forecast_2) > 0 and 'Nt.220' in forecast_2.columns and pd.notna(forecast_2['Nt.220'].values[0]) else 0

# Formula: Provision_expense = Change_in_NPL + NPL_formation - write_offs + Change_in_provision_balance
# Since write-offs are negative, we subtract them (which adds their absolute value)
provision_expense_forecast_year_1_new = -((npl_absolute_forecast_year_1_new - npl_absolute_last_complete_year) + npl_formation_absolute_forecast_year_1_new - write_off_forecast_year_1 + (provision_forecast_year_1_new - provision_last_complete_year))
provision_expense_forecast_year_2_new = -((npl_absolute_forecast_year_2_new - npl_absolute_forecast_year_1_new) + npl_formation_absolute_forecast_year_2_new - write_off_forecast_year_2 + (provision_forecast_year_2_new - provision_forecast_year_1_new))

provision_expense_forecast_year_1_original = forecast_1['IS.17'].values[0] if len(forecast_1) > 0 else 0
provision_expense_forecast_year_2_original = forecast_2['IS.17'].values[0] if len(forecast_2) > 0 else 0

# Calculate changes in provision expense
provision_change_forecast_year_1 = provision_expense_forecast_year_1_new - provision_expense_forecast_year_1_original
provision_change_forecast_year_2 = provision_expense_forecast_year_2_new - provision_expense_forecast_year_2_original

# Calculate PBT changes from provision expense
pbt_change_segment3_forecast_year_1 = provision_change_forecast_year_1
pbt_change_segment3_forecast_year_2 = provision_change_forecast_year_2

# Store segment 3 changes
st.session_state[f'{ticker}_pbt_change_segment3_{forecast_year_1}'] = pbt_change_segment3_forecast_year_1
st.session_state[f'{ticker}_pbt_change_segment3_{forecast_year_2}'] = pbt_change_segment3_forecast_year_2

# Display Provision Analysis
st.subheader("Provision Expense Impact Analysis")
prov_col1, prov_col2 = st.columns(2)

with prov_col1:
    st.markdown(f"**{forecast_year_1} Provision Analysis**")
    st.write(f"NPL Change: {npl_forecast_year_1_new - npl_forecast_year_1_original:+.2f}pp")
    st.write(f"NPL Coverage Change: {npl_coverage_forecast_year_1_new - npl_coverage_forecast_year_1_original:+.1f}pp")
    st.write(f"Write-offs: {write_off_forecast_year_1 / 1e12:.2f}T")
    st.write(f"")
    st.write(f"Original Provision Expense: {provision_expense_forecast_year_1_original / 1e12:.2f}T")
    st.write(f"New Provision Expense: {provision_expense_forecast_year_1_new / 1e12:.2f}T")
    st.write(f"**PBT Impact: {pbt_change_segment3_forecast_year_1 / 1e12:+.2f}T**")

with prov_col2:
    st.markdown(f"**{forecast_year_2} Provision Analysis**")
    st.write(f"NPL Change: {npl_forecast_year_2_new - npl_forecast_year_2_original:+.2f}pp")
    st.write(f"NPL Coverage Change: {npl_coverage_forecast_year_2_new - npl_coverage_forecast_year_2_original:+.1f}pp")
    st.write(f"Write-offs: {write_off_forecast_year_2 / 1e12:.2f}T")
    st.write(f"")
    st.write(f"Original Provision Expense: {provision_expense_forecast_year_2_original / 1e12:.2f}T")
    st.write(f"New Provision Expense: {provision_expense_forecast_year_2_new / 1e12:.2f}T")
    st.write(f"**PBT Impact: {pbt_change_segment3_forecast_year_2 / 1e12:+.2f}T**")

# Calculate total PBT changes (Segment 1 + Segment 2 + Segment 3)
pbt_change_total_forecast_year_1 = (
    st.session_state.get(f'{ticker}_pbt_change_segment1_{forecast_year_1}', 0) + 
    st.session_state.get(f'{ticker}_pbt_change_segment2_{forecast_year_1}', 0) + 
    pbt_change_segment3_forecast_year_1
)
pbt_change_total_forecast_year_2 = (
    st.session_state.get(f'{ticker}_pbt_change_segment1_{forecast_year_2}', 0) + 
    st.session_state.get(f'{ticker}_pbt_change_segment2_{forecast_year_2}', 0) + 
    pbt_change_segment3_forecast_year_2
)

# Update session state with total adjusted PBT
st.session_state[f'{ticker}_pbt_{forecast_year_1}_adjusted'] = pbt_forecast_1_original + pbt_change_total_forecast_year_1
st.session_state[f'{ticker}_pbt_{forecast_year_2}_adjusted'] = pbt_forecast_2_original + pbt_change_total_forecast_year_2

st.markdown("---")

# Summary Section
st.header("Summary of PBT Impact")
summary_col1, summary_col2 = st.columns(2)

with summary_col1:
    st.markdown(f"**{forecast_year_1} PBT Breakdown**")
    st.write(f"Original PBT: {pbt_forecast_1_original / 1e12:.2f}T")
    st.write(f"Segment 1 (NII) Impact: {st.session_state.get(f'{ticker}_pbt_change_segment1_{forecast_year_1}', 0) / 1e12:+.2f}T")
    st.write(f"Segment 2 (OPEX) Impact: {st.session_state.get(f'{ticker}_pbt_change_segment2_{forecast_year_1}', 0) / 1e12:+.2f}T")
    st.write(f"Segment 3 (Provision) Impact: {pbt_change_segment3_forecast_year_1 / 1e12:+.2f}T")
    st.write(f"**Adjusted PBT: {st.session_state[f'{ticker}_pbt_{forecast_year_1}_adjusted'] / 1e12:.2f}T**")

with summary_col2:
    st.markdown(f"**{forecast_year_2} PBT Breakdown**")
    st.write(f"Original PBT: {pbt_forecast_2_original / 1e12:.2f}T")
    st.write(f"Segment 1 (NII) Impact: {st.session_state.get(f'{ticker}_pbt_change_segment1_{forecast_year_2}', 0) / 1e12:+.2f}T")
    st.write(f"Segment 2 (OPEX) Impact: {st.session_state.get(f'{ticker}_pbt_change_segment2_{forecast_year_2}', 0) / 1e12:+.2f}T")
    st.write(f"Segment 3 (Provision) Impact: {pbt_change_segment3_forecast_year_2 / 1e12:+.2f}T")
    st.write(f"**Adjusted PBT: {st.session_state[f'{ticker}_pbt_{forecast_year_2}_adjusted'] / 1e12:.2f}T**")

# Update the header with final calculated values
pbt_forecast_1_adjusted = st.session_state[f'{ticker}_pbt_{forecast_year_1}_adjusted']
pbt_forecast_2_adjusted = st.session_state[f'{ticker}_pbt_{forecast_year_2}_adjusted']
pbt_yoy_forecast_1_adjusted = ((pbt_forecast_1_adjusted / pbt_last_complete) - 1) * 100 if pbt_last_complete != 0 else 0
pbt_yoy_forecast_2_adjusted = ((pbt_forecast_2_adjusted / pbt_forecast_1_adjusted) - 1) * 100 if pbt_forecast_1_adjusted != 0 else 0

header_placeholder.markdown(f'''
<div class="fixed-header">
    <div class="metrics-container">
        <div class="ticker-box">
            <div class="ticker-label">Bank</div>
            <div class="ticker-value">{ticker}</div>
            <div class="metric-subtitle">Profit Before Tax (PBT)</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">{forecast_year_1} Forecast</div>
            <div class="metric-value">{pbt_forecast_1_adjusted/1e12:.2f}T</div>
            <div class="metric-delta">{pbt_yoy_forecast_1_adjusted:+.1f}% YoY Growth</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">{forecast_year_2} Forecast</div>
            <div class="metric-value">{pbt_forecast_2_adjusted/1e12:.2f}T</div>
            <div class="metric-delta">{pbt_yoy_forecast_2_adjusted:+.1f}% YoY Growth</div>
        </div>
    </div>
</div>
''', unsafe_allow_html=True)