import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from .quarter_utils import sort_quarters, format_quarter_for_display

def Bankplot(df=None, keyitem=None):
    # Use global variables or session state if not provided as parameters
    if df is None:
        df = st.session_state.get('df')
    if keyitem is None:
        keyitem = st.session_state.get('keyitem')
    
    # Get forecast settings from session state
    include_forecast = st.session_state.get('include_forecast', False)
    last_historical_year = st.session_state.get('last_historical_year', 2024)
    
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
        default = ['TOI','PBT','NIM','Loan yield','NPL','GROUP 2','New NPL', 'New G2']
    )
    
    #Setup subplot
    
    rows = len(Z) // 2 + 1
    cols = 2 if len(Z) > 1 else 1
    
    fig = make_subplots(
        rows=rows, 
        cols=cols, 
        subplot_titles=Z
    )
    
    # Define metrics that should be displayed in billions
    billion_scale_metrics = [
        'TOI', 'PBT', 'OPEX', 'PPOP', 'Provision expense', 'NPATMI', 
        'Write-off', 'Fees Income', 'Net Interest Income', 'Loan', 
        'Deposit', 'Total Assets', 'Equity', 'Customer Deposit',
        'Total Liabilities', 'Gross Loan', 'Net Loan', 'Cash',
        'Interbank Assets', 'Securities', 'Other Income'
    ]
    
    #Draw chart
    
    for idx, z_name in enumerate(Z):
        # Use the name directly since columns already have descriptive names
        value_col = z_name
        
        # Check if this metric should be in billions
        is_billion_metric = value_col in billion_scale_metrics
        
        # Create a copy of the data for this metric and ensure numeric dtype
        df_display = df.copy()
        df_display[value_col] = pd.to_numeric(df_display[value_col], errors='coerce')

        if is_billion_metric:
            df_display[value_col] = df_display[value_col] / 1e9
            subplot_title = f"{z_name} (B VND)"
        else:
            subplot_title = z_name
        
        # Update the subplot title
        if idx == 0:
            fig.layout.annotations[idx].text = subplot_title
        else:
            if idx < len(fig.layout.annotations):
                fig.layout.annotations[idx].text = subplot_title
        
        metric_values = df_display[value_col].dropna()
        median_value = metric_values.median()
        median_value = abs(median_value)
        row = idx // 2 + 1
        col = idx % 2 + 1
        
        # Adjusted formatting logic
        if is_billion_metric:
            # For billion-scale metrics, use comma formatting
            tick_format = ",.0f"  # Show as whole numbers with commas
        elif median_value > 10:
            tick_format = ",.2s"  # SI units: k, M, B (for other large numbers)
        else:
            tick_format = ".2%"   # Percent
    
        for i, x in enumerate(X):
            show_legend = (idx == 0)
            if len(x) == 3:  # Stock ticker
                matched_rows = df_display[df_display['TICKER'] == x]
                if not matched_rows.empty:
                    df_temp = matched_rows.tail(Y)
                    
                    # Check if forecast data is included
                    if include_forecast and 'is_forecast' in df_temp.columns:
                        # Split into historical and forecast data
                        df_historical = df_temp[df_temp['is_forecast'] == False]
                        df_forecast = df_temp[df_temp['is_forecast'] == True]
                        
                        # Plot historical data with solid line
                        if not df_historical.empty:
                            fig.add_trace(
                                go.Scatter(
                                    x=df_historical[date_column],
                                    y=df_historical[value_col],
                                    mode='lines+markers',
                                    name=str(x),
                                    line=dict(color=color_sequence[i % len(color_sequence)], dash=None),
                                    showlegend=show_legend
                                ),
                                row=row,
                                col=col
                            )
                        
                        # Plot forecast data with dotted line
                        if not df_forecast.empty:
                            # Connect last historical point to first forecast point
                            if not df_historical.empty:
                                # Create connecting trace
                                last_hist = df_historical.iloc[-1]
                                first_forecast = df_forecast.iloc[0]
                                fig.add_trace(
                                    go.Scatter(
                                        x=[last_hist[date_column], first_forecast[date_column]],
                                        y=[last_hist[value_col], first_forecast[value_col]],
                                        mode='lines',
                                        name=str(x) + ' (forecast)',
                                        line=dict(color=color_sequence[i % len(color_sequence)], dash='dot'),
                                        showlegend=False
                                    ),
                                    row=row,
                                    col=col
                                )
                            
                            # Plot forecast points
                            fig.add_trace(
                                go.Scatter(
                                    x=df_forecast[date_column],
                                    y=df_forecast[value_col],
                                    mode='lines+markers',
                                    name=str(x) + ' (forecast)',
                                    line=dict(color=color_sequence[i % len(color_sequence)], dash='dot'),
                                    marker=dict(symbol='circle-open'),
                                    showlegend=show_legend
                                ),
                                row=row,
                                col=col
                            )
                    else:
                        # Normal plotting without forecast distinction
                        fig.add_trace(
                            go.Scatter(
                                x=df_temp[date_column],
                                y=df_temp[value_col],
                                mode='lines+markers',
                                name=str(x),
                                line=dict(color=color_sequence[i % len(color_sequence)]),
                                showlegend=show_legend
                            ),
                            row=row,
                            col=col
                        )
                        
            else:  # Bank type
                # For aggregated bank types, TICKER column contains the bank type name directly
                matched_rows = df_display[df_display['TICKER'] == x]
                if not matched_rows.empty:
                    df_temp = matched_rows.tail(Y)
                    
                    # Check if forecast data is included
                    if include_forecast and 'is_forecast' in df_temp.columns:
                        # Split into historical and forecast data
                        df_historical = df_temp[df_temp['is_forecast'] == False]
                        df_forecast = df_temp[df_temp['is_forecast'] == True]
                        
                        # Plot historical data with solid line
                        if not df_historical.empty:
                            fig.add_trace(
                                go.Scatter(
                                    x=df_historical[date_column],
                                    y=df_historical[value_col],
                                    mode='lines+markers',
                                    name=str(x),
                                    line=dict(color=color_sequence[i % len(color_sequence)], dash=None),
                                    showlegend=show_legend
                                ),
                                row=row,
                                col=col
                            )
                        
                        # Plot forecast data with dotted line
                        if not df_forecast.empty:
                            # Connect last historical point to first forecast point
                            if not df_historical.empty:
                                # Create connecting trace
                                last_hist = df_historical.iloc[-1]
                                first_forecast = df_forecast.iloc[0]
                                fig.add_trace(
                                    go.Scatter(
                                        x=[last_hist[date_column], first_forecast[date_column]],
                                        y=[last_hist[value_col], first_forecast[value_col]],
                                        mode='lines',
                                        name=str(x) + ' (forecast)',
                                        line=dict(color=color_sequence[i % len(color_sequence)], dash='dot'),
                                        showlegend=False
                                    ),
                                    row=row,
                                    col=col
                                )
                            
                            # Plot forecast points
                            fig.add_trace(
                                go.Scatter(
                                    x=df_forecast[date_column],
                                    y=df_forecast[value_col],
                                    mode='lines+markers',
                                    name=str(x) + ' (forecast)',
                                    line=dict(color=color_sequence[i % len(color_sequence)], dash='dot'),
                                    marker=dict(symbol='circle-open'),
                                    showlegend=show_legend
                                ),
                                row=row,
                                col=col
                            )
                    else:
                        # Normal plotting without forecast distinction
                        fig.add_trace(
                            go.Scatter(
                                x=df_temp[date_column],
                                y=df_temp[value_col],
                                mode='lines+markers',
                                name=str(x),
                                line=dict(color=color_sequence[i % len(color_sequence)]),
                                showlegend=show_legend
                            ),
                            row=row,
                            col=col
                        )
        
        # Update y-axis format for this subplot
        fig.update_yaxes(tickformat=tick_format, row=row, col=col)
  
    fig.update_layout(
        width=1400,
        height=1200,
        title_text=f"Banking Metrics: {', '.join(Z)}",
        legend_title="Ticker/Type"
    )
    
    # Sort x axis - use custom sort to handle mixed quarters and forecast years
    # Fix: Use the dynamic date_column variable instead of hardcoded 'Date_Quarter'
    date_order = sort_quarters(df[date_column].unique())
    
    # Create display labels in the format #Qyy
    display_labels = [format_quarter_for_display(date) for date in date_order]
    
    # Update x-axes with sorted order and custom display labels
    fig.update_xaxes(
        categoryorder='array', 
        categoryarray=date_order,
        ticktext=display_labels,
        tickvals=date_order
    )

    # Update y-axis formatting for each subplot
    # Note: tick_format is now specific to each metric
    st.plotly_chart(fig, use_container_width=True)
