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
@st.cache_data
def load_data():
    df_year = pd.read_csv(os.path.join(project_root, 'Data/dfsectoryear.csv'))
    df_quarter = pd.read_csv(os.path.join(project_root, 'Data/dfsectorquarter.csv'))
    keyitem = pd.read_excel(os.path.join(project_root, 'Data/Key_items.xlsx'))
    return df_year, df_quarter, keyitem

df_year, df_quarter, keyitem = load_data()

# Get only banks with forecast data (exclude sectors and aggregates)
forecast_data = df_year[df_year['Year'].isin([2025, 2026])]
banks_with_forecast = forecast_data[forecast_data['TICKER'].str.len() == 3]['TICKER'].unique()
banks_with_forecast = sorted(banks_with_forecast)

# Sidebar: Choose ticker
ticker = st.sidebar.selectbox(
    "Select Bank:",
    banks_with_forecast,
    index=0
)

# Get historical and forecast data for selected ticker
historical_data = df_year[(df_year['TICKER'] == ticker) & (df_year['Year'].isin([2023, 2024]))]
forecast_2025 = df_year[(df_year['TICKER'] == ticker) & (df_year['Year'] == 2025)]
forecast_2026 = df_year[(df_year['TICKER'] == ticker) & (df_year['Year'] == 2026)]

# Get quarterly data for 2025
df_quarter['Year'] = 2000 + df_quarter['Date_Quarter'].str.extract(r'Q(\d+)').astype(int)
quarterly_2025 = df_quarter[(df_quarter['TICKER'] == ticker) & 
                            (df_quarter['Year'] == 2025) & 
                            (df_quarter['Date_Quarter'].isin(['1Q25', '2Q25']))]

# Initialize session state for forecast values if not exists
if 'forecast_values' not in st.session_state:
    st.session_state.forecast_values = {}

# Get current forecast PBT values
pbt_2025_original = forecast_2025['IS.18'].values[0] if len(forecast_2025) > 0 else 0
pbt_2026_original = forecast_2026['IS.18'].values[0] if len(forecast_2026) > 0 else 0
pbt_2024 = historical_data[historical_data['Year'] == 2024]['IS.18'].values[0] if len(historical_data[historical_data['Year'] == 2024]) > 0 else 0

# Calculate original YoY growth
pbt_yoy_2025_original = ((pbt_2025_original / pbt_2024) - 1) * 100 if pbt_2024 != 0 else 0
pbt_yoy_2026_original = ((pbt_2026_original / pbt_2025_original) - 1) * 100 if pbt_2025_original != 0 else 0

# Initialize adjusted values
if f'{ticker}_pbt_2025_adjusted' not in st.session_state:
    st.session_state[f'{ticker}_pbt_2025_adjusted'] = pbt_2025_original
    st.session_state[f'{ticker}_pbt_2026_adjusted'] = pbt_2026_original

# Calculate adjusted PBT values for display
pbt_2025_adjusted = st.session_state[f'{ticker}_pbt_2025_adjusted']
pbt_2026_adjusted = st.session_state[f'{ticker}_pbt_2026_adjusted']
pbt_yoy_2025_adjusted = ((pbt_2025_adjusted / pbt_2024) - 1) * 100 if pbt_2024 != 0 else 0
pbt_yoy_2026_adjusted = ((pbt_2026_adjusted / pbt_2025_adjusted) - 1) * 100 if pbt_2025_adjusted != 0 else 0

# Create fixed header with metrics
st.markdown(f'''
<div class="fixed-header">
    <div class="metrics-container">
        <div class="ticker-box">
            <div class="ticker-label">Bank</div>
            <div class="ticker-value">{ticker}</div>
            <div class="metric-subtitle">Profit Before Tax (PBT)</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">2025 Forecast</div>
            <div class="metric-value">{pbt_2025_adjusted/1e12:.2f}T</div>
            <div class="metric-delta">{pbt_yoy_2025_adjusted:+.1f}% YoY Growth</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">2026 Forecast</div>
            <div class="metric-value">{pbt_2026_adjusted/1e12:.2f}T</div>
            <div class="metric-delta">{pbt_yoy_2026_adjusted:+.1f}% YoY Growth</div>
        </div>
    </div>
</div>
''', unsafe_allow_html=True)

# Add spacing to account for fixed header
st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

st.markdown("---")

# Segment 1: Net Interest Income
st.header("Segment 1: Net Interest Income Adjustment")

# Prepare historical data table for NIM and Loan
def prepare_historical_table():
    # Get data for 2023-2024 (yearly) and Q1-Q2 2025
    data_rows = []
    
    # Add 2023-2024 yearly data
    for year in [2023, 2024]:
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
    
    # Add Q1-Q2 2025 data
    for quarter in ['1Q25', '2Q25']:
        q_data = quarterly_2025[quarterly_2025['Date_Quarter'] == quarter]
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
    
    # Add forecast data for 2025-2026
    for year, forecast in [(2025, forecast_2025), (2026, forecast_2026)]:
        if len(forecast) > 0:
            row = forecast.iloc[0]
            loan = row['BS.12'] if 'BS.12' in row and pd.notna(row['BS.12']) else row['BS.13']
            nim = row['CA.13'] if pd.notna(row['CA.13']) else 0
            nii = row['IS.3'] if pd.notna(row['IS.3']) else 0
            
            # Calculate loan growth YoY
            if year == 2025:
                loan_prev = historical_data[historical_data['Year'] == 2024]['BS.12'].values[0] if len(historical_data[historical_data['Year'] == 2024]) > 0 else loan
                if pd.isna(loan_prev):
                    loan_prev = historical_data[historical_data['Year'] == 2024]['BS.13'].values[0] if len(historical_data[historical_data['Year'] == 2024]) > 0 else loan
            else:  # 2026
                loan_prev = forecast_2025['BS.12'].values[0] if len(forecast_2025) > 0 else loan
                if pd.isna(loan_prev):
                    loan_prev = forecast_2025['BS.13'].values[0] if len(forecast_2025) > 0 else loan
            
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
nim_2025_original = forecast_2025['CA.13'].values[0] * 100 if len(forecast_2025) > 0 else 3.0
nim_2026_original = forecast_2026['CA.13'].values[0] * 100 if len(forecast_2026) > 0 else 3.0

loan_2024 = historical_data[historical_data['Year'] == 2024]['BS.12'].values[0] if len(historical_data[historical_data['Year'] == 2024]) > 0 else 1e15
if pd.isna(loan_2024):
    loan_2024 = historical_data[historical_data['Year'] == 2024]['BS.13'].values[0] if len(historical_data[historical_data['Year'] == 2024]) > 0 else 1e15

loan_2025_original = forecast_2025['BS.12'].values[0] if len(forecast_2025) > 0 else loan_2024 * 1.15
if pd.isna(loan_2025_original):
    loan_2025_original = forecast_2025['BS.13'].values[0] if len(forecast_2025) > 0 else loan_2024 * 1.15

loan_2026_original = forecast_2026['BS.12'].values[0] if len(forecast_2026) > 0 else loan_2025_original * 1.15
if pd.isna(loan_2026_original):
    loan_2026_original = forecast_2026['BS.13'].values[0] if len(forecast_2026) > 0 else loan_2025_original * 1.15

loan_growth_2025_original = ((loan_2025_original / loan_2024) - 1) * 100 if loan_2024 != 0 else 15
loan_growth_2026_original = ((loan_2026_original / loan_2025_original) - 1) * 100 if loan_2025_original != 0 else 15

nii_2025_original = forecast_2025['IS.3'].values[0] if len(forecast_2025) > 0 else 0
nii_2026_original = forecast_2026['IS.3'].values[0] if len(forecast_2026) > 0 else 0

with col1:
    st.markdown("**2025 Adjustments**")
    nim_2025_new = st.number_input(
        "NIM 2025 (%)", 
        min_value=0.0, 
        max_value=10.0, 
        value=nim_2025_original,
        step=0.1,
        key=f"{ticker}_nim_2025"
    )
    loan_growth_2025_new = st.number_input(
        "Loan Growth YoY 2025 (%)", 
        min_value=-20.0, 
        max_value=50.0, 
        value=loan_growth_2025_original,
        step=1.0,
        key=f"{ticker}_loan_growth_2025"
    )

with col2:
    st.markdown("**2026 Adjustments**")
    nim_2026_new = st.number_input(
        "NIM 2026 (%)", 
        min_value=0.0, 
        max_value=10.0, 
        value=nim_2026_original,
        step=0.1,
        key=f"{ticker}_nim_2026"
    )
    loan_growth_2026_new = st.number_input(
        "Loan Growth YoY 2026 (%)", 
        min_value=-20.0, 
        max_value=50.0, 
        value=loan_growth_2026_original,
        step=1.0,
        key=f"{ticker}_loan_growth_2026"
    )

# Calculate PBT changes based on formula
# Formula: Change in PBT = (Loan growth YoY CHANGE vs. old forecast /2) + (New NIM/ Old NIM - 1) * Current NII forecast

# For 2025
loan_growth_change_2025 = loan_growth_2025_new - loan_growth_2025_original
nim_ratio_2025 = (nim_2025_new / nim_2025_original) if nim_2025_original != 0 else 1
pbt_change_segment1_2025 = (loan_growth_change_2025 / 2) * (pbt_2025_original / 100) + (nim_ratio_2025 - 1) * nii_2025_original

# For 2026
loan_growth_change_2026 = loan_growth_2026_new - loan_growth_2026_original
nim_ratio_2026 = (nim_2026_new / nim_2026_original) if nim_2026_original != 0 else 1
pbt_change_segment1_2026 = (loan_growth_change_2026 / 2) * (pbt_2026_original / 100) + (nim_ratio_2026 - 1) * nii_2026_original

# Store segment 1 changes for later use
st.session_state[f'{ticker}_pbt_change_segment1_2025'] = pbt_change_segment1_2025
st.session_state[f'{ticker}_pbt_change_segment1_2026'] = pbt_change_segment1_2026

# Display impact analysis
st.subheader("Impact Analysis")
impact_col1, impact_col2 = st.columns(2)

with impact_col1:
    st.markdown("**2025 Impact**")
    st.write(f"Loan Growth Change: {loan_growth_change_2025:.1f}%")
    st.write(f"NIM Ratio: {nim_ratio_2025:.3f}")
    st.write(f"PBT Change from Loan Growth: {(loan_growth_change_2025 / 2) * (pbt_2025_original / 100) / 1e12:.2f}T")
    st.write(f"PBT Change from NIM: {(nim_ratio_2025 - 1) * nii_2025_original / 1e12:.2f}T")
    st.write(f"**Total PBT Change: {pbt_change_segment1_2025 / 1e12:.2f}T**")

with impact_col2:
    st.markdown("**2026 Impact**")
    st.write(f"Loan Growth Change: {loan_growth_change_2026:.1f}%")
    st.write(f"NIM Ratio: {nim_ratio_2026:.3f}")
    st.write(f"PBT Change from Loan Growth: {(loan_growth_change_2026 / 2) * (pbt_2026_original / 100) / 1e12:.2f}T")
    st.write(f"PBT Change from NIM: {(nim_ratio_2026 - 1) * nii_2026_original / 1e12:.2f}T")
    st.write(f"**Total PBT Change: {pbt_change_segment1_2026 / 1e12:.2f}T**")

# Auto-update when inputs change (removed manual button since Streamlit auto-reruns on input change)

st.markdown("---")

# Segment 2: OPEX
st.header("Segment 2: Operating Expenses (OPEX) Adjustment")

# Prepare OPEX and CIR historical data
def prepare_opex_table():
    data_rows = []
    
    # Add 2023-2024 yearly data
    for year in [2023, 2024]:
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
    
    # Add forecast data for 2025-2026
    for year, forecast in [(2025, forecast_2025), (2026, forecast_2026)]:
        if len(forecast) > 0:
            row = forecast.iloc[0]
            opex = row['IS.15'] if pd.notna(row['IS.15']) else 0
            toi = row['IS.14'] if pd.notna(row['IS.14']) else 0
            cir = row['CA.6'] if pd.notna(row['CA.6']) else (opex/toi if toi != 0 else 0)
            
            # Calculate YoY growth
            if year == 2025:
                opex_prev = historical_data[historical_data['Year'] == 2024]['IS.15'].values[0] if len(historical_data[historical_data['Year'] == 2024]) > 0 else opex
            else:  # 2026
                opex_prev = forecast_2025['IS.15'].values[0] if len(forecast_2025) > 0 else opex
            
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
opex_2024 = historical_data[historical_data['Year'] == 2024]['IS.15'].values[0] if len(historical_data[historical_data['Year'] == 2024]) > 0 else 0
opex_2025_original = forecast_2025['IS.15'].values[0] if len(forecast_2025) > 0 else opex_2024 * 1.1
opex_2026_original = forecast_2026['IS.15'].values[0] if len(forecast_2026) > 0 else opex_2025_original * 1.1

opex_growth_2025_original = ((opex_2025_original / opex_2024) - 1) * 100 if opex_2024 != 0 else 10
opex_growth_2026_original = ((opex_2026_original / opex_2025_original) - 1) * 100 if opex_2025_original != 0 else 10

# Get original TOI values
toi_2025_original = forecast_2025['IS.14'].values[0] if len(forecast_2025) > 0 else 0
toi_2026_original = forecast_2026['IS.14'].values[0] if len(forecast_2026) > 0 else 0

with col1:
    st.markdown("**2025 Adjustments**")
    opex_growth_2025_new = st.number_input(
        "OPEX Growth YoY 2025 (%)", 
        min_value=-30.0, 
        max_value=50.0, 
        value=opex_growth_2025_original,
        step=1.0,
        key=f"{ticker}_opex_growth_2025"
    )

with col2:
    st.markdown("**2026 Adjustments**")
    opex_growth_2026_new = st.number_input(
        "OPEX Growth YoY 2026 (%)", 
        min_value=-30.0, 
        max_value=50.0, 
        value=opex_growth_2026_original,
        step=1.0,
        key=f"{ticker}_opex_growth_2026"
    )

# Calculate new OPEX values
opex_2025_new = opex_2024 * (1 + opex_growth_2025_new / 100)
opex_2026_new = opex_2025_new * (1 + opex_growth_2026_new / 100)

# Calculate OPEX changes
opex_change_2025 = opex_2025_new - opex_2025_original
opex_change_2026 = opex_2026_new - opex_2026_original

# Calculate PBT changes from OPEX (OPEX is already negative in P&L)
pbt_change_segment2_2025 = opex_change_2025
pbt_change_segment2_2026 = opex_change_2026

# Store segment 2 changes
st.session_state[f'{ticker}_pbt_change_segment2_2025'] = pbt_change_segment2_2025
st.session_state[f'{ticker}_pbt_change_segment2_2026'] = pbt_change_segment2_2026

# Calculate new TOI (original TOI + PBT changes from Segment 1)
# TOI = Revenue - COGS, and NII changes affect TOI
toi_2025_new = toi_2025_original + st.session_state.get(f'{ticker}_pbt_change_segment1_2025', 0)
toi_2026_new = toi_2026_original + st.session_state.get(f'{ticker}_pbt_change_segment1_2026', 0)

# Calculate new CIR
cir_2025_original = (opex_2025_original / toi_2025_original * 100) if toi_2025_original != 0 else 0
cir_2026_original = (opex_2026_original / toi_2026_original * 100) if toi_2026_original != 0 else 0

cir_2025_new = (opex_2025_new / toi_2025_new * 100) if toi_2025_new != 0 else 0
cir_2026_new = (opex_2026_new / toi_2026_new * 100) if toi_2026_new != 0 else 0

# Display CIR analysis
st.subheader("CIR Impact Analysis")
cir_col1, cir_col2 = st.columns(2)

with cir_col1:
    st.markdown("**2025 CIR Analysis**")
    st.write(f"Original CIR: {cir_2025_original:.1f}%")
    st.write(f"New CIR: {cir_2025_new:.1f}%")
    st.write(f"CIR Change: {cir_2025_new - cir_2025_original:+.1f}pp")
    st.write(f"")
    st.write(f"OPEX Change: {opex_change_2025 / 1e12:.2f}T")
    st.write(f"**PBT Impact: {pbt_change_segment2_2025 / 1e12:+.2f}T**")

with cir_col2:
    st.markdown("**2026 CIR Analysis**")
    st.write(f"Original CIR: {cir_2026_original:.1f}%")
    st.write(f"New CIR: {cir_2026_new:.1f}%")
    st.write(f"CIR Change: {cir_2026_new - cir_2026_original:+.1f}pp")
    st.write(f"")
    st.write(f"OPEX Change: {opex_change_2026 / 1e12:.2f}T")
    st.write(f"**PBT Impact: {pbt_change_segment2_2026 / 1e12:+.2f}T**")

# Calculate total PBT changes (Segment 1 + Segment 2)
pbt_change_total_2025 = st.session_state.get(f'{ticker}_pbt_change_segment1_2025', 0) + pbt_change_segment2_2025
pbt_change_total_2026 = st.session_state.get(f'{ticker}_pbt_change_segment1_2026', 0) + pbt_change_segment2_2026

# Update session state with total adjusted PBT
st.session_state[f'{ticker}_pbt_2025_adjusted'] = pbt_2025_original + pbt_change_total_2025
st.session_state[f'{ticker}_pbt_2026_adjusted'] = pbt_2026_original + pbt_change_total_2026

st.markdown("---")

# Segment 3: Asset Quality
st.header("Segment 3: Asset Quality Assumptions")

# Prepare Asset Quality historical data
def prepare_asset_quality_table():
    data_rows = []
    
    # Add 2023-2024 yearly data
    for year in [2023, 2024]:
        year_data = historical_data[historical_data['Year'] == year]
        if len(year_data) > 0:
            row = year_data.iloc[0]
            loan = row['BS.12'] if 'BS.12' in row and pd.notna(row['BS.12']) else row['BS.13']
            npl = row['CA.3'] if pd.notna(row['CA.3']) else 0
            npl_formation = row['CA.23'] if pd.notna(row['CA.23']) else 0
            bs14 = row['BS.14'] if pd.notna(row['BS.14']) else 0
            npl_coverage = (-bs14 / (npl * loan) * 100) if (npl * loan) != 0 else 0
            provision_expense = row['IS.17'] if pd.notna(row['IS.17']) else 0
            
            data_rows.append({
                'Period': str(year),
                'NPL (%)': npl * 100,
                'NPL Formation (%)': npl_formation * 100,
                'NPL Coverage (%)': npl_coverage,
                'Provision Expense': provision_expense / 1e12
            })
    
    # Add forecast data for 2025-2026
    for year, forecast in [(2025, forecast_2025), (2026, forecast_2026)]:
        if len(forecast) > 0:
            row = forecast.iloc[0]
            loan = row['BS.12'] if 'BS.12' in row and pd.notna(row['BS.12']) else row['BS.13']
            npl = row['CA.3'] if pd.notna(row['CA.3']) else 0
            npl_formation = row['CA.23'] if pd.notna(row['CA.23']) else 0
            bs14 = row['BS.14'] if pd.notna(row['BS.14']) else 0
            npl_coverage = (-bs14 / (npl * loan) * 100) if (npl * loan) != 0 else 0
            provision_expense = row['IS.17'] if pd.notna(row['IS.17']) else 0
            
            data_rows.append({
                'Period': f"{year}F",
                'NPL (%)': npl * 100,
                'NPL Formation (%)': npl_formation * 100,
                'NPL Coverage (%)': npl_coverage,
                'Provision Expense': provision_expense / 1e12
            })
    
    return pd.DataFrame(data_rows)

# Display Asset Quality table
asset_quality_table = prepare_asset_quality_table()
st.subheader("Historical and Forecast Asset Quality Metrics")
st.dataframe(asset_quality_table.style.format({
    'NPL (%)': '{:.2f}%',
    'NPL Formation (%)': '{:.2f}%',
    'NPL Coverage (%)': '{:.1f}%',
    'Provision Expense': '{:.2f}T'
}), use_container_width=True)

# Input section for Asset Quality adjustments
st.subheader("Adjust Asset Quality Assumptions")

col1, col2 = st.columns(2)

# Get original values
npl_2025_original = forecast_2025['CA.3'].values[0] * 100 if len(forecast_2025) > 0 else 1.5
npl_2026_original = forecast_2026['CA.3'].values[0] * 100 if len(forecast_2026) > 0 else 1.5

npl_formation_2025_original = forecast_2025['CA.23'].values[0] * 100 if len(forecast_2025) > 0 else 0.5
npl_formation_2026_original = forecast_2026['CA.23'].values[0] * 100 if len(forecast_2026) > 0 else 0.5

# Calculate original NPL coverage
loan_2025_forecast = forecast_2025['BS.12'].values[0] if len(forecast_2025) > 0 else 0
if pd.isna(loan_2025_forecast):
    loan_2025_forecast = forecast_2025['BS.13'].values[0] if len(forecast_2025) > 0 else 0

loan_2026_forecast = forecast_2026['BS.12'].values[0] if len(forecast_2026) > 0 else 0
if pd.isna(loan_2026_forecast):
    loan_2026_forecast = forecast_2026['BS.13'].values[0] if len(forecast_2026) > 0 else 0

bs14_2025 = forecast_2025['BS.14'].values[0] if len(forecast_2025) > 0 else 0
bs14_2026 = forecast_2026['BS.14'].values[0] if len(forecast_2026) > 0 else 0

npl_coverage_2025_original = (-bs14_2025 / (npl_2025_original/100 * loan_2025_forecast) * 100) if (npl_2025_original * loan_2025_forecast) != 0 else 100
npl_coverage_2026_original = (-bs14_2026 / (npl_2026_original/100 * loan_2026_forecast) * 100) if (npl_2026_original * loan_2026_forecast) != 0 else 100

with col1:
    st.markdown("**2025 Adjustments**")
    npl_2025_new = st.number_input(
        "NPL 2025 (%)", 
        min_value=0.0, 
        max_value=10.0, 
        value=npl_2025_original,
        step=0.1,
        key=f"{ticker}_npl_2025"
    )
    npl_formation_2025_new = st.number_input(
        "NPL Formation 2025 (%)", 
        min_value=0.0, 
        max_value=5.0, 
        value=npl_formation_2025_original,
        step=0.1,
        key=f"{ticker}_npl_formation_2025"
    )
    npl_coverage_2025_new = st.number_input(
        "NPL Coverage 2025 (%)", 
        min_value=0.0, 
        max_value=200.0, 
        value=npl_coverage_2025_original,
        step=1.0,
        key=f"{ticker}_npl_coverage_2025"
    )

with col2:
    st.markdown("**2026 Adjustments**")
    npl_2026_new = st.number_input(
        "NPL 2026 (%)", 
        min_value=0.0, 
        max_value=10.0, 
        value=npl_2026_original,
        step=0.1,
        key=f"{ticker}_npl_2026"
    )
    npl_formation_2026_new = st.number_input(
        "NPL Formation 2026 (%)", 
        min_value=0.0, 
        max_value=5.0, 
        value=npl_formation_2026_original,
        step=0.1,
        key=f"{ticker}_npl_formation_2026"
    )
    npl_coverage_2026_new = st.number_input(
        "NPL Coverage 2026 (%)", 
        min_value=0.0, 
        max_value=200.0, 
        value=npl_coverage_2026_original,
        step=1.0,
        key=f"{ticker}_npl_coverage_2026"
    )

# Get loan values from Segment 1 (adjusted for loan growth)
loan_2024_value = loan_2024  # From segment 1
loan_2025_new = loan_2024_value * (1 + loan_growth_2025_new / 100)
loan_2026_new = loan_2025_new * (1 + loan_growth_2026_new / 100)

# Get previous year values
bs14_2024 = historical_data[historical_data['Year'] == 2024]['BS.14'].values[0] if len(historical_data[historical_data['Year'] == 2024]) > 0 else 0
npl_2024 = historical_data[historical_data['Year'] == 2024]['CA.3'].values[0] if len(historical_data[historical_data['Year'] == 2024]) > 0 else 0.015

# Calculate new provision expense using the formula
# Step 1: Calculate Absolute NPL
npl_absolute_2024 = npl_2024 * loan_2024_value
npl_absolute_2025_new = (npl_2025_new / 100) * loan_2025_new
npl_absolute_2026_new = (npl_2026_new / 100) * loan_2026_new

npl_absolute_2025_original = (npl_2025_original / 100) * loan_2025_forecast
npl_absolute_2026_original = (npl_2026_original / 100) * loan_2026_forecast

# Step 2: Calculate Absolute NPL Formation
npl_formation_absolute_2025_new = (npl_formation_2025_new / 100) * loan_2024_value
npl_formation_absolute_2026_new = (npl_formation_2026_new / 100) * loan_2025_new

npl_formation_absolute_2025_original = (npl_formation_2025_original / 100) * loan_2024_value
npl_formation_absolute_2026_original = (npl_formation_2026_original / 100) * loan_2025_forecast

# Step 3: Calculate Provision absolute value
provision_2024 = -bs14_2024  # BS.14 is negative, so negate it
provision_2025_new = (npl_coverage_2025_new / 100) * npl_absolute_2025_new
provision_2026_new = (npl_coverage_2026_new / 100) * npl_absolute_2026_new

provision_2025_original = (npl_coverage_2025_original / 100) * npl_absolute_2025_original
provision_2026_original = (npl_coverage_2026_original / 100) * npl_absolute_2026_original

# Step 4: Calculate New Provision Expense
# Formula: (NPL_abs - NPL_abs(t-1)) + NPL_formation_abs + (Provision(t-1) - Provision)
provision_expense_2025_new = (npl_absolute_2025_new - npl_absolute_2024) + npl_formation_absolute_2025_new + (provision_2024 - provision_2025_new)
provision_expense_2026_new = (npl_absolute_2026_new - npl_absolute_2025_new) + npl_formation_absolute_2026_new + (provision_2025_new - provision_2026_new)

provision_expense_2025_original = forecast_2025['IS.17'].values[0] if len(forecast_2025) > 0 else 0
provision_expense_2026_original = forecast_2026['IS.17'].values[0] if len(forecast_2026) > 0 else 0

# Calculate changes in provision expense
provision_change_2025 = provision_expense_2025_new - provision_expense_2025_original
provision_change_2026 = provision_expense_2026_new - provision_expense_2026_original

# Calculate PBT changes from provision expense
pbt_change_segment3_2025 = provision_change_2025
pbt_change_segment3_2026 = provision_change_2026

# Store segment 3 changes
st.session_state[f'{ticker}_pbt_change_segment3_2025'] = pbt_change_segment3_2025
st.session_state[f'{ticker}_pbt_change_segment3_2026'] = pbt_change_segment3_2026

# Display Provision Analysis
st.subheader("Provision Expense Impact Analysis")
prov_col1, prov_col2 = st.columns(2)

with prov_col1:
    st.markdown("**2025 Provision Analysis**")
    st.write(f"NPL Change: {npl_2025_new - npl_2025_original:+.2f}pp")
    st.write(f"NPL Coverage Change: {npl_coverage_2025_new - npl_coverage_2025_original:+.1f}pp")
    st.write(f"")
    st.write(f"Original Provision Expense: {provision_expense_2025_original / 1e12:.2f}T")
    st.write(f"New Provision Expense: {provision_expense_2025_new / 1e12:.2f}T")
    st.write(f"**PBT Impact: {pbt_change_segment3_2025 / 1e12:+.2f}T**")

with prov_col2:
    st.markdown("**2026 Provision Analysis**")
    st.write(f"NPL Change: {npl_2026_new - npl_2026_original:+.2f}pp")
    st.write(f"NPL Coverage Change: {npl_coverage_2026_new - npl_coverage_2026_original:+.1f}pp")
    st.write(f"")
    st.write(f"Original Provision Expense: {provision_expense_2026_original / 1e12:.2f}T")
    st.write(f"New Provision Expense: {provision_expense_2026_new / 1e12:.2f}T")
    st.write(f"**PBT Impact: {pbt_change_segment3_2026 / 1e12:+.2f}T**")

# Calculate total PBT changes (Segment 1 + Segment 2 + Segment 3)
pbt_change_total_2025 = (
    st.session_state.get(f'{ticker}_pbt_change_segment1_2025', 0) + 
    st.session_state.get(f'{ticker}_pbt_change_segment2_2025', 0) + 
    pbt_change_segment3_2025
)
pbt_change_total_2026 = (
    st.session_state.get(f'{ticker}_pbt_change_segment1_2026', 0) + 
    st.session_state.get(f'{ticker}_pbt_change_segment2_2026', 0) + 
    pbt_change_segment3_2026
)

# Update session state with total adjusted PBT
st.session_state[f'{ticker}_pbt_2025_adjusted'] = pbt_2025_original + pbt_change_total_2025
st.session_state[f'{ticker}_pbt_2026_adjusted'] = pbt_2026_original + pbt_change_total_2026

st.markdown("---")

# Summary Section
st.header("Summary of PBT Impact")
summary_col1, summary_col2 = st.columns(2)

with summary_col1:
    st.markdown("**2025 PBT Breakdown**")
    st.write(f"Original PBT: {pbt_2025_original / 1e12:.2f}T")
    st.write(f"Segment 1 (NII) Impact: {st.session_state.get(f'{ticker}_pbt_change_segment1_2025', 0) / 1e12:+.2f}T")
    st.write(f"Segment 2 (OPEX) Impact: {st.session_state.get(f'{ticker}_pbt_change_segment2_2025', 0) / 1e12:+.2f}T")
    st.write(f"Segment 3 (Provision) Impact: {pbt_change_segment3_2025 / 1e12:+.2f}T")
    st.write(f"**Adjusted PBT: {st.session_state[f'{ticker}_pbt_2025_adjusted'] / 1e12:.2f}T**")

with summary_col2:
    st.markdown("**2026 PBT Breakdown**")
    st.write(f"Original PBT: {pbt_2026_original / 1e12:.2f}T")
    st.write(f"Segment 1 (NII) Impact: {st.session_state.get(f'{ticker}_pbt_change_segment1_2026', 0) / 1e12:+.2f}T")
    st.write(f"Segment 2 (OPEX) Impact: {st.session_state.get(f'{ticker}_pbt_change_segment2_2026', 0) / 1e12:+.2f}T")
    st.write(f"Segment 3 (Provision) Impact: {pbt_change_segment3_2026 / 1e12:+.2f}T")
    st.write(f"**Adjusted PBT: {st.session_state[f'{ticker}_pbt_2026_adjusted'] / 1e12:.2f}T**")