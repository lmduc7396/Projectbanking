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
    # Determine last complete year dynamically
    dfis = pd.read_csv(os.path.join(project_root, 'Data/IS_Bank.csv'))
    complete_years = dfis[dfis['LENGTHREPORT'] == 5]['YEARREPORT'].unique()
    last_complete_year = int(max(complete_years)) if len(complete_years) > 0 else 2024
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

# Get historical and forecast data for selected ticker
historical_data = df_year[(df_year['TICKER'] == ticker) & (df_year['Year'].isin([last_complete_year-1, last_complete_year])]
forecast_1 = df_year[(df_year['TICKER'] == ticker) & (df_year['Year'] == forecast_year_1)]
forecast_2 = df_year[(df_year['TICKER'] == ticker) & (df_year['Year'] == forecast_year_2)]

# Extract key values - with default fallbacks
if len(historical_data[historical_data['Year'] == last_complete_year]) > 0:
    loan_last_complete = historical_data[historical_data['Year'] == last_complete_year]['CA.10'].values[0]
    pbt_last_complete = historical_data[historical_data['Year'] == last_complete_year]['CA.16'].values[0]
    nii_last_complete = historical_data[historical_data['Year'] == last_complete_year]['CA.4'].values[0]
    opex_last_complete = historical_data[historical_data['Year'] == last_complete_year]['CA.11'].values[0]
    provision_last_complete = historical_data[historical_data['Year'] == last_complete_year]['CA.13'].values[0]
    npl_last_complete = historical_data[historical_data['Year'] == last_complete_year]['CA.20'].values[0]
else:
    loan_last_complete = 100000000000000  # 100T default
    pbt_last_complete = 10000000000000  # 10T default
    nii_last_complete = 20000000000000  # 20T default
    opex_last_complete = -10000000000000  # -10T default
    provision_last_complete = -5000000000000  # -5T default
    npl_last_complete = 0.02  # 2% default

# Get NIM and loan growth from forecast data
nim_forecast_1_original = forecast_1['CA.8'].values[0] * 100 if len(forecast_1) > 0 else 3.0
nim_forecast_2_original = forecast_2['CA.8'].values[0] * 100 if len(forecast_2) > 0 else 3.0

loan_forecast_1_original = forecast_1['CA.10'].values[0] if len(forecast_1) > 0 else loan_last_complete * 1.1
loan_forecast_2_original = forecast_2['CA.10'].values[0] if len(forecast_2) > 0 else loan_forecast_1_original * 1.1

loan_growth_forecast_year_1_original = ((loan_forecast_1_original / loan_last_complete) - 1) * 100 if loan_last_complete != 0 else 10.0
loan_growth_forecast_year_2_original = ((loan_forecast_2_original / loan_forecast_1_original) - 1) * 100 if loan_forecast_1_original != 0 else 10.0

nii_forecast_1_original = forecast_1['CA.4'].values[0] if len(forecast_1) > 0 else nii_last_complete * 1.1
nii_forecast_2_original = forecast_2['CA.4'].values[0] if len(forecast_2) > 0 else nii_forecast_1_original * 1.1

pbt_forecast_1_original = forecast_1['CA.16'].values[0] if len(forecast_1) > 0 else pbt_last_complete * 1.1
pbt_forecast_2_original = forecast_2['CA.16'].values[0] if len(forecast_2) > 0 else pbt_forecast_1_original * 1.1

# OPEX values (already negative)
opex_forecast_1_original = forecast_1['CA.11'].values[0] if len(forecast_1) > 0 else opex_last_complete * 1.1
opex_forecast_2_original = forecast_2['CA.11'].values[0] if len(forecast_2) > 0 else opex_forecast_1_original * 1.1

opex_growth_forecast_year_1_original = ((opex_forecast_1_original / opex_last_complete) - 1) * 100 if opex_last_complete != 0 else 10.0
opex_growth_forecast_year_2_original = ((opex_forecast_2_original / opex_forecast_1_original) - 1) * 100 if opex_forecast_1_original != 0 else 10.0

# Asset Quality values
npl_forecast_year_1_original = forecast_1['CA.20'].values[0] * 100 if len(forecast_1) > 0 else 2.0
npl_forecast_year_2_original = forecast_2['CA.20'].values[0] * 100 if len(forecast_2) > 0 else 2.0

# NPL Formation is already negative in the data, convert to positive for display
npl_formation_forecast_year_1_original = abs(forecast_1['CA.23'].values[0] * 100) if len(forecast_1) > 0 else 0.5
npl_formation_forecast_year_2_original = abs(forecast_2['CA.23'].values[0] * 100) if len(forecast_2) > 0 else 0.5

npl_coverage_forecast_year_1_original = forecast_1['CA.22'].values[0] * 100 if len(forecast_1) > 0 else 150.0
npl_coverage_forecast_year_2_original = forecast_2['CA.22'].values[0] * 100 if len(forecast_2) > 0 else 150.0

provision_forecast_1_original = forecast_1['CA.13'].values[0] if len(forecast_1) > 0 else provision_last_complete * 1.1
provision_forecast_2_original = forecast_2['CA.13'].values[0] if len(forecast_2) > 0 else provision_forecast_1_original * 1.1

# Create a container for all inputs (hidden with expander or processed first)
with st.container():
    # Collect all inputs first
    st.header("Segment 1: NII Assumptions")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**{forecast_year_1} Adjustments**")
        nim_forecast_year_1_new = st.number_input(
            f"NIM {forecast_year_1} (%)", 
            min_value=0.0, 
            max_value=10.0, 
            value=st.session_state.get(f"{ticker}_nim_{forecast_year_1}", nim_forecast_1_original),
            step=0.1,
            key=f"{ticker}_nim_{forecast_year_1}"
        )
        loan_growth_forecast_year_1_new = st.number_input(
            f"Loan Growth YoY {forecast_year_1} (%)", 
            min_value=-20.0, 
            max_value=50.0, 
            value=st.session_state.get(f"{ticker}_loan_growth_{forecast_year_1}", loan_growth_forecast_year_1_original),
            step=1.0,
            key=f"{ticker}_loan_growth_{forecast_year_1}"
        )

    with col2:
        st.markdown(f"**{forecast_year_2} Adjustments**")
        nim_forecast_year_2_new = st.number_input(
            f"NIM {forecast_year_2} (%)", 
            min_value=0.0, 
            max_value=10.0, 
            value=st.session_state.get(f"{ticker}_nim_{forecast_year_2}", nim_forecast_2_original),
            step=0.1,
            key=f"{ticker}_nim_{forecast_year_2}"
        )
        loan_growth_forecast_year_2_new = st.number_input(
            f"Loan Growth YoY {forecast_year_2} (%)", 
            min_value=-20.0, 
            max_value=50.0, 
            value=st.session_state.get(f"{ticker}_loan_growth_{forecast_year_2}", loan_growth_forecast_year_2_original),
            step=1.0,
            key=f"{ticker}_loan_growth_{forecast_year_2}"
        )
    
    st.markdown("---")
    st.header("Segment 2: OPEX Assumptions")
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown(f"**{forecast_year_1} Adjustments**")
        opex_growth_forecast_year_1_new = st.number_input(
            f"OPEX Growth YoY {forecast_year_1} (%)", 
            min_value=-20.0, 
            max_value=50.0, 
            value=st.session_state.get(f"{ticker}_opex_growth_{forecast_year_1}", opex_growth_forecast_year_1_original),
            step=1.0,
            key=f"{ticker}_opex_growth_{forecast_year_1}"
        )
    
    with col4:
        st.markdown(f"**{forecast_year_2} Adjustments**")
        opex_growth_forecast_year_2_new = st.number_input(
            f"OPEX Growth YoY {forecast_year_2} (%)", 
            min_value=-20.0, 
            max_value=50.0, 
            value=st.session_state.get(f"{ticker}_opex_growth_{forecast_year_2}", opex_growth_forecast_year_2_original),
            step=1.0,
            key=f"{ticker}_opex_growth_{forecast_year_2}"
        )
    
    st.markdown("---")
    st.header("Segment 3: Asset Quality Assumptions")
    col5, col6 = st.columns(2)
    
    with col5:
        st.markdown(f"**{forecast_year_1} Adjustments**")
        npl_forecast_year_1_new = st.number_input(
            f"NPL {forecast_year_1} (%)", 
            min_value=0.0, 
            max_value=10.0, 
            value=st.session_state.get(f"{ticker}_npl_{forecast_year_1}", npl_forecast_year_1_original),
            step=0.1,
            key=f"{ticker}_npl_{forecast_year_1}"
        )
        npl_formation_forecast_year_1_new = st.number_input(
            f"NPL Formation {forecast_year_1} (%)", 
            min_value=0.0, 
            max_value=5.0, 
            value=st.session_state.get(f"{ticker}_npl_formation_{forecast_year_1}", npl_formation_forecast_year_1_original),
            step=0.1,
            key=f"{ticker}_npl_formation_{forecast_year_1}"
        )
        npl_coverage_forecast_year_1_new = st.number_input(
            f"NPL Coverage {forecast_year_1} (%)", 
            min_value=50.0, 
            max_value=500.0, 
            value=st.session_state.get(f"{ticker}_npl_coverage_{forecast_year_1}", npl_coverage_forecast_year_1_original),
            step=5.0,
            key=f"{ticker}_npl_coverage_{forecast_year_1}"
        )
    
    with col6:
        st.markdown(f"**{forecast_year_2} Adjustments**")
        npl_forecast_year_2_new = st.number_input(
            f"NPL {forecast_year_2} (%)", 
            min_value=0.0, 
            max_value=10.0, 
            value=st.session_state.get(f"{ticker}_npl_{forecast_year_2}", npl_forecast_year_2_original),
            step=0.1,
            key=f"{ticker}_npl_{forecast_year_2}"
        )
        npl_formation_forecast_year_2_new = st.number_input(
            f"NPL Formation {forecast_year_2} (%)", 
            min_value=0.0, 
            max_value=5.0, 
            value=st.session_state.get(f"{ticker}_npl_formation_{forecast_year_2}", npl_formation_forecast_year_2_original),
            step=0.1,
            key=f"{ticker}_npl_formation_{forecast_year_2}"
        )
        npl_coverage_forecast_year_2_new = st.number_input(
            f"NPL Coverage {forecast_year_2} (%)", 
            min_value=50.0, 
            max_value=500.0, 
            value=st.session_state.get(f"{ticker}_npl_coverage_{forecast_year_2}", npl_coverage_forecast_year_2_original),
            step=5.0,
            key=f"{ticker}_npl_coverage_{forecast_year_2}"
        )

# Now calculate ALL PBT changes BEFORE rendering the header
# Segment 1 calculations
loan_growth_change_forecast_year_1 = loan_growth_forecast_year_1_new - loan_growth_forecast_year_1_original
pbt_change_loan_growth_forecast_year_1 = (loan_growth_change_forecast_year_1 / 2) / 100 * nii_forecast_1_original
nim_change_ratio_forecast_year_1 = (nim_forecast_year_1_new / nim_forecast_1_original - 1) if nim_forecast_1_original != 0 else 0
pbt_change_nim_forecast_year_1 = nim_change_ratio_forecast_year_1 * nii_forecast_1_original
pbt_change_segment1_forecast_year_1 = pbt_change_loan_growth_forecast_year_1 + pbt_change_nim_forecast_year_1

loan_growth_change_forecast_year_2 = loan_growth_forecast_year_2_new - loan_growth_forecast_year_2_original
pbt_change_loan_growth_forecast_year_2 = (loan_growth_change_forecast_year_2 / 2) / 100 * nii_forecast_2_original
nim_change_ratio_forecast_year_2 = (nim_forecast_year_2_new / nim_forecast_2_original - 1) if nim_forecast_2_original != 0 else 0
pbt_change_nim_forecast_year_2 = nim_change_ratio_forecast_year_2 * nii_forecast_2_original
pbt_change_segment1_forecast_year_2 = pbt_change_loan_growth_forecast_year_2 + pbt_change_nim_forecast_year_2

# Segment 2 calculations
opex_new_forecast_year_1 = opex_last_complete * (1 + opex_growth_forecast_year_1_new / 100)
opex_change_forecast_year_1 = opex_new_forecast_year_1 - opex_forecast_1_original
pbt_change_segment2_forecast_year_1 = opex_change_forecast_year_1

opex_new_forecast_year_2 = opex_forecast_1_original * (1 + opex_growth_forecast_year_2_new / 100)
opex_change_forecast_year_2 = opex_new_forecast_year_2 - opex_forecast_2_original
pbt_change_segment2_forecast_year_2 = opex_change_forecast_year_2

# Segment 3 calculations
# Calculate NPL amounts
npl_amount_last_complete = loan_last_complete * npl_last_complete
npl_amount_forecast_year_1 = loan_forecast_1_original * (npl_forecast_year_1_new / 100)
npl_amount_forecast_year_2 = loan_forecast_2_original * (npl_forecast_year_2_new / 100)

# Calculate NPL formation amounts (convert percentage to absolute)
npl_formation_amount_forecast_year_1 = loan_forecast_1_original * (npl_formation_forecast_year_1_new / 100)
npl_formation_amount_forecast_year_2 = loan_forecast_2_original * (npl_formation_forecast_year_2_new / 100)

# Calculate provision based on formula
provision_new_forecast_year_1 = (
    (npl_amount_forecast_year_1 - npl_amount_last_complete) +
    npl_formation_amount_forecast_year_1 +
    (provision_last_complete - provision_forecast_1_original)
)
pbt_change_segment3_forecast_year_1 = provision_new_forecast_year_1 - provision_forecast_1_original

provision_new_forecast_year_2 = (
    (npl_amount_forecast_year_2 - npl_amount_forecast_year_1) +
    npl_formation_amount_forecast_year_2 +
    (provision_forecast_1_original - provision_forecast_2_original)
)
pbt_change_segment3_forecast_year_2 = provision_new_forecast_year_2 - provision_forecast_2_original

# Calculate TOTAL PBT changes
pbt_change_total_forecast_year_1 = pbt_change_segment1_forecast_year_1 + pbt_change_segment2_forecast_year_1 + pbt_change_segment3_forecast_year_1
pbt_change_total_forecast_year_2 = pbt_change_segment1_forecast_year_2 + pbt_change_segment2_forecast_year_2 + pbt_change_segment3_forecast_year_2

# Update session state
pbt_forecast_1_adjusted = pbt_forecast_1_original + pbt_change_total_forecast_year_1
pbt_forecast_2_adjusted = pbt_forecast_2_original + pbt_change_total_forecast_year_2

# Calculate YoY growth
pbt_yoy_forecast_1_adjusted = ((pbt_forecast_1_adjusted / pbt_last_complete) - 1) * 100 if pbt_last_complete != 0 else 0
pbt_yoy_forecast_2_adjusted = ((pbt_forecast_2_adjusted / pbt_forecast_1_adjusted) - 1) * 100 if pbt_forecast_1_adjusted != 0 else 0

# NOW render the header with updated values
st.markdown(f'''
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

# Revert button in sidebar
revert_button = st.sidebar.button("Revert to Default Forecast", type="secondary", use_container_width=True)

if revert_button:
    # Set all values back to originals
    st.session_state[f"{ticker}_nim_{forecast_year_1}"] = nim_forecast_1_original
    st.session_state[f"{ticker}_nim_{forecast_year_2}"] = nim_forecast_2_original
    st.session_state[f"{ticker}_loan_growth_{forecast_year_1}"] = loan_growth_forecast_year_1_original
    st.session_state[f"{ticker}_loan_growth_{forecast_year_2}"] = loan_growth_forecast_year_2_original
    st.session_state[f"{ticker}_opex_growth_{forecast_year_1}"] = opex_growth_forecast_year_1_original
    st.session_state[f"{ticker}_opex_growth_{forecast_year_2}"] = opex_growth_forecast_year_2_original
    st.session_state[f"{ticker}_npl_{forecast_year_1}"] = npl_forecast_year_1_original
    st.session_state[f"{ticker}_npl_{forecast_year_2}"] = npl_forecast_year_2_original
    st.session_state[f"{ticker}_npl_formation_{forecast_year_1}"] = npl_formation_forecast_year_1_original
    st.session_state[f"{ticker}_npl_formation_{forecast_year_2}"] = npl_formation_forecast_year_2_original
    st.session_state[f"{ticker}_npl_coverage_{forecast_year_1}"] = npl_coverage_forecast_year_1_original
    st.session_state[f"{ticker}_npl_coverage_{forecast_year_2}"] = npl_coverage_forecast_year_2_original
    st.rerun()

# Display impact analysis and tables for each segment
st.markdown("---")
st.header("Impact Analysis")

# Segment 1 Impact Analysis
st.subheader("Segment 1: NII Impact")
col_impact1, col_impact2 = st.columns(2)

with col_impact1:
    st.markdown(f"**{forecast_year_1} Impact**")
    st.write(f"Loan Growth Change: {loan_growth_change_forecast_year_1:+.1f}pp")
    st.write(f"PBT from Loan Growth: {pbt_change_loan_growth_forecast_year_1 / 1e12:+.2f}T")
    st.write(f"NIM Change: {nim_forecast_year_1_new - nim_forecast_1_original:+.1f}pp")
    st.write(f"PBT from NIM: {pbt_change_nim_forecast_year_1 / 1e12:+.2f}T")
    st.write(f"**Total PBT Impact: {pbt_change_segment1_forecast_year_1 / 1e12:+.2f}T**")

with col_impact2:
    st.markdown(f"**{forecast_year_2} Impact**")
    st.write(f"Loan Growth Change: {loan_growth_change_forecast_year_2:+.1f}pp")
    st.write(f"PBT from Loan Growth: {pbt_change_loan_growth_forecast_year_2 / 1e12:+.2f}T")
    st.write(f"NIM Change: {nim_forecast_year_2_new - nim_forecast_2_original:+.1f}pp")
    st.write(f"PBT from NIM: {pbt_change_nim_forecast_year_2 / 1e12:+.2f}T")
    st.write(f"**Total PBT Impact: {pbt_change_segment1_forecast_year_2 / 1e12:+.2f}T**")

# Segment 2 Impact Analysis
st.subheader("Segment 2: OPEX Impact")
col_impact3, col_impact4 = st.columns(2)

with col_impact3:
    st.markdown(f"**{forecast_year_1} Impact**")
    st.write(f"OPEX Growth Change: {opex_growth_forecast_year_1_new - opex_growth_forecast_year_1_original:+.1f}pp")
    st.write(f"OPEX Change: {opex_change_forecast_year_1 / 1e12:.2f}T")
    st.write(f"**PBT Impact: {pbt_change_segment2_forecast_year_1 / 1e12:+.2f}T**")

with col_impact4:
    st.markdown(f"**{forecast_year_2} Impact**")
    st.write(f"OPEX Growth Change: {opex_growth_forecast_year_2_new - opex_growth_forecast_year_2_original:+.1f}pp")
    st.write(f"OPEX Change: {opex_change_forecast_year_2 / 1e12:.2f}T")
    st.write(f"**PBT Impact: {pbt_change_segment2_forecast_year_2 / 1e12:+.2f}T**")

# Segment 3 Impact Analysis
st.subheader("Segment 3: Asset Quality Impact")
col_impact5, col_impact6 = st.columns(2)

with col_impact5:
    st.markdown(f"**{forecast_year_1} Impact**")
    st.write(f"NPL Change: {npl_forecast_year_1_new - npl_forecast_year_1_original:+.1f}pp")
    st.write(f"NPL Formation: {npl_formation_forecast_year_1_new:.1f}%")
    st.write(f"Coverage Change: {npl_coverage_forecast_year_1_new - npl_coverage_forecast_year_1_original:+.1f}pp")
    st.write(f"**PBT Impact: {pbt_change_segment3_forecast_year_1 / 1e12:+.2f}T**")

with col_impact6:
    st.markdown(f"**{forecast_year_2} Impact**")
    st.write(f"NPL Change: {npl_forecast_year_2_new - npl_forecast_year_2_original:+.1f}pp")
    st.write(f"NPL Formation: {npl_formation_forecast_year_2_new:.1f}%")
    st.write(f"Coverage Change: {npl_coverage_forecast_year_2_new - npl_coverage_forecast_year_2_original:+.1f}pp")
    st.write(f"**PBT Impact: {pbt_change_segment3_forecast_year_2 / 1e12:+.2f}T**")

st.markdown("---")

# Summary Section
st.header("Summary of PBT Impact")
summary_col1, summary_col2 = st.columns(2)

with summary_col1:
    st.markdown(f"**{forecast_year_1} PBT Breakdown**")
    st.write(f"Original PBT: {pbt_forecast_1_original / 1e12:.2f}T")
    st.write(f"Segment 1 (NII) Impact: {pbt_change_segment1_forecast_year_1 / 1e12:+.2f}T")
    st.write(f"Segment 2 (OPEX) Impact: {pbt_change_segment2_forecast_year_1 / 1e12:+.2f}T")
    st.write(f"Segment 3 (Provision) Impact: {pbt_change_segment3_forecast_year_1 / 1e12:+.2f}T")
    st.write(f"**Adjusted PBT: {pbt_forecast_1_adjusted / 1e12:.2f}T**")

with summary_col2:
    st.markdown(f"**{forecast_year_2} PBT Breakdown**")
    st.write(f"Original PBT: {pbt_forecast_2_original / 1e12:.2f}T")
    st.write(f"Segment 1 (NII) Impact: {pbt_change_segment1_forecast_year_2 / 1e12:+.2f}T")
    st.write(f"Segment 2 (OPEX) Impact: {pbt_change_segment2_forecast_year_2 / 1e12:+.2f}T")
    st.write(f"Segment 3 (Provision) Impact: {pbt_change_segment3_forecast_year_2 / 1e12:+.2f}T")
    st.write(f"**Adjusted PBT: {pbt_forecast_2_adjusted / 1e12:.2f}T**")