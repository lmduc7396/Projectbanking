
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np

# Load your data
df_quarter = pd.read_csv('Data/dfsectorquarter.csv')
df_year = pd.read_csv('Data/dfsectoryear.csv')
keyitem=pd.read_excel('Data/Key_items.xlsx')
color_sequence=px.colors.qualitative.Bold

# Sidebar: Choose pages
page= st.sidebar.selectbox("Choose a page", ("Banking plot","Company Table"))

# Sidebar: Choose database
db_option = st.sidebar.radio("Choose database:", ("Quarterly", "Yearly"))

if db_option == "Quarterly":
    df = df_quarter.copy()
else:
    df = df_year.copy()


def Bankplot():
    # Define your options
    bank_type = ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']
    tickers = sorted([x for x in df['TICKER'].unique() if isinstance(x, str) and len(x) == 3])
    x_options = bank_type + tickers
    
    col1,col2,col3 = st.columns(3)
    with col1:
        X = st.multiselect("Select Stock Ticker or Bank Type (X):", x_options,
                          default = ['Private_1']
                          )
    with col2:
        Y = st.number_input("Number of latest periods to plot (Y):", min_value=1, max_value=20, value=10)
    with col3:
        Z = st.multiselect(
        "Select Value Column(s) (Z):", 
        keyitem['Name'].tolist(),
        default = ['NIM','Loan yield','NPL','GROUP 2','NPL Formation (%)', 'G2 Formation (%)']
    )
    
    #Setup subplot
    
    rows = len(Z) // 2 + 1
    cols = 2 if len(Z) > 1 else 1
    
    fig = make_subplots(
        rows=rows, 
        cols=cols, 
        subplot_titles=Z
    )
    
    #Draw chart
    
    for idx, z_name in enumerate(Z):
        value_col = keyitem[keyitem['Name']==z_name]['KeyCode'].iloc[0]
        metric_values=df[value_col].dropna()
        median_value=metric_values.median()
        median_value=abs(median_value)
        row = idx // 2 + 1
        col = idx % 2 + 1
        if median_value > 10:
            tick_format = ",.2s"  # SI units: k, M, B
        else:
            tick_format = ".2%"   # Percent
    
        for i, x in enumerate(X):
            show_legend = (idx == 0)
            if len(x) == 3:  # Stock ticker
                matched_rows = df[df['TICKER'] == x]
                if not matched_rows.empty:
                    df_tempY = matched_rows.tail(Y)
                    fig.add_trace(
                        go.Scatter(
                            x=df_tempY['Date_Quarter'],
                            y=df_tempY[value_col],
                            mode='lines+markers',
                            name=str(x),
                            line=dict(color=color_sequence[i % len(color_sequence)]),
                            showlegend = show_legend
                        ),
                        row=row,
                        col=col
                    )
            else:  # Bank type
                matched_rows = df[(df['Type'] == x) & (df['TICKER'].apply(len) > 3)]
                if not matched_rows.empty:
                    primary_ticker = matched_rows.iloc[0]['TICKER']
                    df_tempY = matched_rows[matched_rows['TICKER'] == primary_ticker].tail(Y)
                    fig.add_trace(
                        go.Scatter(
                            x=df_tempY['Date_Quarter'],
                            y=df_tempY[value_col],
                            mode='lines+markers',
                            name=str(x),
                            line=dict(color=color_sequence[i % len(color_sequence)]),
                            showlegend = show_legend
                        ),
                        row=row,
                        col=col
                    )
    
    fig.update_layout(
        width=1400,
        height=1200,
        title_text=f"Banking Metrics: {', '.join(Z)}",
        legend_title="Ticker/Type"
    )
    for i in range(1, len(Z)+1):
        fig.update_yaxes(tickformat=tick_format, row=(i-1)//2 + 1, col=(i-1)%2 + 1)
    
    st.plotly_chart(fig, use_container_width=True)

def Banking_table():
    # --- Define User Selection Options ---
    bank_type = ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']
    tickers = sorted([x for x in df['TICKER'].unique() if isinstance(x, str) and len(x) == 3])
    x_options = bank_type + tickers

    col1, col2, col3 = st.columns(3)
    with col1:
        X = st.selectbox("Select Stock Ticker or Bank Type (X):", x_options)
    with col2:
        Y = st.number_input("Number of latest periods to plot (Y):", min_value=1, max_value=20, value=6)
    with col3:
        if db_option == "Quarterly":
            Z = st.selectbox("QoQ or YoY growth (Z):", ['QoQ', 'YoY'], index=0)
        else:
            Z = st.selectbox("QoQ or YoY growth (Z):", ['YoY'], index=0)

    # --- Prepare List of Columns to Keep ---
    cols_keep = pd.DataFrame({
        'Name': [
            'Loan', 'TOI', 'Provision expense', 'PBT', 'ROA', 'ROE', 'NIM', 'Loan yield',
            'NPL', 'NPL Formation (%)', 'GROUP 2', 'G2 Formation (%)',
            'NPL Coverage ratio', 'Provision/ Total Loan'
        ]
    })
    cols_code_keep = cols_keep.merge(keyitem, on='Name', how='left')
    cols_keep_final = ['Date_Quarter'] + cols_code_keep['KeyCode'].tolist()

    # --- Filter Data for Table ---
    if X in bank_type:
        # Filter by Type (e.g. Sector, SOCB, etc.)
        df_temp = df[(df['Type'] == X) & (df['TICKER'].apply(lambda t: len(t) > 3))]
        df_temp = df_temp[df_temp['TICKER'] == df_temp['TICKER'].iloc[0]]
    else:
        # Filter by specific ticker
        df_temp = df[df['TICKER'] == X]
    df_temp = df_temp[cols_keep_final]

    # --- Calculate Growth Tables ---
    def get_growth_table(df_, period, suffix):
        """Calculate growth (%) and return formatted DataFrame."""
        growth = df_.iloc[:, 1:].pct_change(periods=period)
        growth.columns = growth.columns.map(dict(zip(cols_code_keep['KeyCode'], cols_code_keep['Name'])))
        growth = growth.add_suffix(f' {suffix} (%)')
        return pd.concat([df_['Date_Quarter'], growth.iloc[:, :4]], axis=1)

    QoQ_change = get_growth_table(df_temp, 1, 'QoQ')
    YoY_change = get_growth_table(df_temp, 4, 'YoY')

    # --- Rename Columns to Friendly Names, Remove Date_Quarter ---
    df_temp.columns = df_temp.columns.map(dict(zip(cols_code_keep['KeyCode'], cols_code_keep['Name'])))
    df_temp = df_temp.iloc[:, 1:]

    # --- Combine Data Based on User Choice (QoQ or YoY) ---
    if Z == 'QoQ':
        df_out = pd.concat([df_temp, QoQ_change], axis=1)
        col_order = [
            'Date_Quarter', 'Loan', 'Loan QoQ (%)', 'TOI', 'TOI QoQ (%)', 'Provision expense', 'Provision expense QoQ (%)',
            'PBT', 'PBT QoQ (%)', 'ROA', 'ROE', 'NIM', 'Loan yield', 'NPL', 'NPL Formation (%)', 'GROUP 2',
            'G2 Formation (%)', 'NPL Coverage ratio', 'Provision/ Total Loan'
        ]
    else:
        df_out = pd.concat([df_temp, YoY_change], axis=1)
        col_order = [
            'Date_Quarter', 'Loan', 'Loan YoY (%)', 'TOI', 'TOI YoY (%)', 'Provision expense', 'Provision expense YoY (%)',
            'PBT', 'PBT YoY (%)', 'ROA', 'ROE', 'NIM', 'Loan yield', 'NPL', 'NPL Formation (%)', 'GROUP 2',
            'G2 Formation (%)', 'NPL Coverage ratio', 'Provision/ Total Loan'
        ]

    # --- Reindex, Select Last Y Periods, Transpose for Display ---
    df_out = df_out.reindex(columns=col_order).tail(Y).T
    df_out.columns = df_out.iloc[0]
    df_out = df_out[1:]
    return df_out

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
            return [str(v) if v is not None else "" for v in row]
        median_val = np.median(np.abs(numeric_vals))
        if median_val > 100:
            return [human_format(v) if pd.notnull(v) and v != '' else "" for v in row]
        else:
            return ["{:.2f}%".format(float(v)*100) if pd.notnull(v) and v != '' else "" for v in row]
    formatted = df.apply(format_row, axis=1, result_type='broadcast')
    return formatted
        
    
    # Apply formatting row-wise, axis=1
    formatted = df.apply(format_row, axis=1, result_type='broadcast')
    return formatted


if page == "Banking plot":
    #Setup page:
    st.set_page_config(
        page_title="Project Banking Online",
        layout="wide")
    st.subheader("Project Banking Online")
    Bankplot()
elif page == "Company Table":
    st.subheader("Table")
    df_out = Banking_table()
    formatted = conditional_format(df_out)   # DataFrame with formatted strings

    # Define zebra coloring on DataFrame of strings
    def style_alternate_rows(df):
        colors = ["#f2f2f2", "#ffffff"]
        styled = []
        for i in range(df.shape[0]):
            styled.append([f"background-color: {colors[i % 2]}"] * df.shape[1])
        return pd.DataFrame(styled, index=df.index, columns=df.columns)

    styled_df = formatted.style.apply(lambda _: style_alternate_rows(formatted), axis=None)
    st.write(styled_df)
   
