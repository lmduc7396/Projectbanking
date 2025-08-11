import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

def Bankplot(df=None, keyitem=None):
    # Use global variables or session state if not provided as parameters
    if df is None:
        df = st.session_state.get('df')
    if keyitem is None:
        keyitem = st.session_state.get('keyitem')
    
    # Determine the date column name
    if 'Date_Quarter' in df.columns:
        date_column = 'Date_Quarter'
    elif 'Year' in df.columns:
        date_column = 'Year'
    else:
        raise ValueError("DataFrame must have either 'Date_Quarter' or 'Year' column")
    
    color_sequence = px.colors.qualitative.Bold

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
                            x=df_tempY[date_column],
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
                # For aggregated bank types, TICKER column contains the bank type name directly
                matched_rows = df[df['TICKER'] == x]
                if not matched_rows.empty:
                    df_tempY = matched_rows.tail(Y)
                    fig.add_trace(
                        go.Scatter(
                            x=df_tempY[date_column],
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
    #Sort x asis
    def quarter_sort_key(q):
        # Example: "5Q21" → (21, 5)
        if 'Q' in q:
            parts = q.split('Q')
            return (int(parts[1]), int(parts[0]))
        return (0, 0)
    date_order = df[['Date_Quarter']].drop_duplicates().copy()
    date_order['Sortkey'] = date_order['Date_Quarter'].apply(quarter_sort_key)
    date_order = date_order.sort_values(by='Sortkey')
    fig.update_xaxes(categoryorder='array', categoryarray=date_order['Date_Quarter'])

    for i in range(1, len(Z)+1):
        fig.update_yaxes(tickformat=tick_format, row=(i-1)//2 + 1, col=(i-1)%2 + 1)    
    st.plotly_chart(fig, use_container_width=True)
