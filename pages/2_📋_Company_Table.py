import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import sys
import os

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import the functions
streamlit_pages_path = os.path.join(project_root, "Streamlit pages")
utilities_path = os.path.join(project_root, "Utilities")
sys.path.append(streamlit_pages_path)
sys.path.append(utilities_path)

# Import using importlib
import importlib.util

# Import Banking_table function
spec1 = importlib.util.spec_from_file_location("banking_table", os.path.join(streamlit_pages_path, "Banking_table.py"))
banking_table_module = importlib.util.module_from_spec(spec1)
spec1.loader.exec_module(banking_table_module)
Banking_table = banking_table_module.Banking_table

# Import Stock_price_plot function with error handling
try:
    spec2 = importlib.util.spec_from_file_location("stockcandle", os.path.join(utilities_path, "Stockcandle.py"))
    stockcandle_module = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(stockcandle_module)
    Stock_price_plot = stockcandle_module.Stock_price_plot
except Exception as e:
    st.error(f"Error loading Stock_price_plot: {e}")
    # Create a fallback function
    def Stock_price_plot(ticker):
        st.info(f"Stock price chart for {ticker} is temporarily unavailable.")

# Load your data (same as main file)
@st.cache_data
def load_data():
    df_quarter = pd.read_csv(os.path.join(project_root, 'Data/dfsectorquarter.csv'))
    df_year = pd.read_csv(os.path.join(project_root, 'Data/dfsectoryear.csv'))
    keyitem = pd.read_excel(os.path.join(project_root, 'Data/Key_items.xlsx'))
    return df_quarter, df_year, keyitem

df_quarter, df_year, keyitem = load_data()
color_sequence = px.colors.qualitative.Bold

# Page configuration
st.set_page_config(
    page_title="Company Table",
    page_icon="📋",
    layout="wide"
)

# Sidebar: Choose database
db_option = st.sidebar.radio("Choose database:", ("Quarterly", "Yearly"))

if db_option == "Quarterly":
    df = df_quarter.copy()
else:
    df = df_year.copy()

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

st.title("📋 Company Table")
st.markdown("---")

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

df_table1, df_table2 = Banking_table(X, Y, Z, df, keyitem)

# Format and display first table
st.subheader("Earnings metrics")
formatted1 = conditional_format(df_table1)
st.dataframe(formatted1, use_container_width=True)

# Format and display second table
st.subheader("Ratios")
formatted2 = conditional_format(df_table2)
st.dataframe(formatted2, use_container_width=True)
