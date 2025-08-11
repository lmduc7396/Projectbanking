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

# Create sticky header with CSS
st.markdown("""
<style>
    /* Sticky metrics container */
    .sticky-metrics {
        position: -webkit-sticky;
        position: sticky;
        top: 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        z-index: 1000;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    
    .metrics-row {
        display: flex;
        justify-content: space-around;
        align-items: center;
    }
    
    .metric-box {
        text-align: center;
        color: white;
    }
    
    .metric-label {
        font-size: 1.2rem;
        opacity: 0.9;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: bold;
        margin: 0.5rem 0;
    }
    
    .metric-delta {
        font-size: 1rem;
        opacity: 0.9;
    }
    
    /* Ensure content scrolls under sticky header */
    .main .block-container {
        padding-top: 1rem;
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

# Create sticky header with HTML
st.markdown(f'''
<div class="sticky-metrics">
    <div class="metrics-row">
        <div class="metric-box">
            <div class="metric-label">2025 PBT</div>
            <div class="metric-value">{pbt_2025_adjusted/1e12:.2f}T</div>
            <div class="metric-delta">{pbt_yoy_2025_adjusted:+.1f}% YoY</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">2026 PBT</div>
            <div class="metric-value">{pbt_2026_adjusted/1e12:.2f}T</div>
            <div class="metric-delta">{pbt_yoy_2026_adjusted:+.1f}% YoY</div>
        </div>
    </div>
</div>
''', unsafe_allow_html=True)

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
pbt_change_2025 = (loan_growth_change_2025 / 2) * (pbt_2025_original / 100) + (nim_ratio_2025 - 1) * nii_2025_original

# For 2026
loan_growth_change_2026 = loan_growth_2026_new - loan_growth_2026_original
nim_ratio_2026 = (nim_2026_new / nim_2026_original) if nim_2026_original != 0 else 1
pbt_change_2026 = (loan_growth_change_2026 / 2) * (pbt_2026_original / 100) + (nim_ratio_2026 - 1) * nii_2026_original

# Update session state with adjusted PBT
st.session_state[f'{ticker}_pbt_2025_adjusted'] = pbt_2025_original + pbt_change_2025
st.session_state[f'{ticker}_pbt_2026_adjusted'] = pbt_2026_original + pbt_change_2026

# Display impact analysis
st.subheader("Impact Analysis")
impact_col1, impact_col2 = st.columns(2)

with impact_col1:
    st.markdown("**2025 Impact**")
    st.write(f"Loan Growth Change: {loan_growth_change_2025:.1f}%")
    st.write(f"NIM Ratio: {nim_ratio_2025:.3f}")
    st.write(f"PBT Change from Loan Growth: {(loan_growth_change_2025 / 2) * (pbt_2025_original / 100) / 1e12:.2f}T")
    st.write(f"PBT Change from NIM: {(nim_ratio_2025 - 1) * nii_2025_original / 1e12:.2f}T")
    st.write(f"**Total PBT Change: {pbt_change_2025 / 1e12:.2f}T**")

with impact_col2:
    st.markdown("**2026 Impact**")
    st.write(f"Loan Growth Change: {loan_growth_change_2026:.1f}%")
    st.write(f"NIM Ratio: {nim_ratio_2026:.3f}")
    st.write(f"PBT Change from Loan Growth: {(loan_growth_change_2026 / 2) * (pbt_2026_original / 100) / 1e12:.2f}T")
    st.write(f"PBT Change from NIM: {(nim_ratio_2026 - 1) * nii_2026_original / 1e12:.2f}T")
    st.write(f"**Total PBT Change: {pbt_change_2026 / 1e12:.2f}T**")

# Auto-update when inputs change (removed manual button since Streamlit auto-reruns on input change)

st.markdown("---")
st.markdown("### Segment 2 & 3: Coming Soon...")
st.info("Additional segments for adjusting other forecast parameters will be added here.")