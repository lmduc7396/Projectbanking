import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import from utilities
from utilities.plot_chart import Bankplot

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
    page_title="Banking Charts",
    page_icon="Chart",
    layout="wide"
)

# Function to detect the last complete year from historical data
@st.cache_data
def get_last_historical_year():
    """Detect the last complete year (LENGTHREPORT=5) from original historical data"""
    try:
        # Read original IS data to find the last complete year
        dfis = pd.read_csv(os.path.join(project_root, 'Data/IS_Bank.csv'))
        # Find years that have LENGTHREPORT=5 (complete year data)
        complete_years = dfis[dfis['LENGTHREPORT'] == 5]['YEARREPORT'].unique()
        if len(complete_years) > 0:
            return int(max(complete_years))
        else:
            # Fallback: use 2024 if no complete year data found
            return 2024
    except:
        # Fallback if file reading fails
        return 2024

# Get the last historical year
last_historical_year = get_last_historical_year()

# Sidebar: Choose database
db_option = st.sidebar.radio("Choose database:", ("Quarterly", "Yearly"))

if db_option == "Quarterly":
    df = df_quarter.copy()
else:
    df = df_year.copy()
    # Filter out forecast years (anything beyond last complete historical year)
    df = df[df['Year'] <= last_historical_year]

# Make the data available globally for the Bankplot function
st.session_state.df = df
st.session_state.keyitem = keyitem

st.title("Banking Plot")
st.markdown("---")

# Call the banking plot function
Bankplot(df, keyitem)
