import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import the function from Streamlit pages folder
streamlit_pages_path = os.path.join(project_root, "Streamlit pages")
sys.path.append(streamlit_pages_path)

# Import by executing the file and getting the function
import importlib.util
spec = importlib.util.spec_from_file_location("plotchart", os.path.join(streamlit_pages_path, "Plotchart.py"))
plotchart_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plotchart_module)
Bankplot = plotchart_module.Bankplot

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
    page_title="Banking Plot",
    page_icon="📊",
    layout="wide"
)

# Sidebar: Choose database
db_option = st.sidebar.radio("Choose database:", ("Quarterly", "Yearly"))

if db_option == "Quarterly":
    df = df_quarter.copy()
else:
    df = df_year.copy()

# Make the data available globally for the Bankplot function
st.session_state.df = df
st.session_state.keyitem = keyitem

st.title("📊 Banking Plot")
st.markdown("---")

# Call the banking plot function
Bankplot(df, keyitem)
