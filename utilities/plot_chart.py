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
    
    def sort_by_period(df_input: pd.DataFrame) -> pd.DataFrame:
        if date_column == 'Year':
            numeric_years = pd.to_numeric(df_input[date_column], errors='coerce')
            order = pd.Series(numeric_years).dropna().sort_values().unique()
            categorical_order = pd.Categorical(
                numeric_years,
                categories=order,
                ordered=True
            )
            sorted_df = df_input.assign(_order=categorical_order).sort_values('_order')
            return sorted_df.drop(columns=['_order'])

        quarter_strings = df_input[date_column].astype(str).tolist()
        ordered = sort_quarters(quarter_strings)
        categorical = pd.Categorical(
            df_input[date_column].astype(str),
            categories=ordered,
            ordered=True
        )
        return df_input.assign(_order=categorical).sort_values('_order').drop(columns='_order')

    #Draw chart
    single_selection = len(X) == 1

    for idx, z_name in enumerate(Z):
        # Use the name directly since columns already have descriptive names
        value_col = z_name
        
        # Check if this metric should be in billions
        is_billion_metric = value_col in billion_scale_metrics
        
        # Create a copy of the data for this metric and ensure numeric dtype
        df_display = df.copy()
        df_display[value_col] = pd.to_numeric(df_display[value_col], errors='coerce')

        if is_billion_metric:
            df_display[value_col] = df_display[value_col].apply(
                lambda v: float(v) / 1e9 if pd.notnull(v) else float('nan')
            )
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
            color = color_sequence[i % len(color_sequence)]

            if len(x) == 3:
                matched_rows = sort_by_period(df_display[df_display['TICKER'] == x])
            else:
                matched_rows = sort_by_period(df_display[df_display['TICKER'] == x])

            if matched_rows.empty:
                continue

            df_temp = matched_rows.tail(Y)
            df_temp = sort_by_period(df_temp)

            if include_forecast and 'is_forecast' in df_temp.columns:
                df_historical = df_temp[df_temp['is_forecast'] == False]
                df_forecast = df_temp[df_temp['is_forecast'] == True]
            else:
                df_historical = df_temp
                df_forecast = pd.DataFrame(columns=df_temp.columns)

            if single_selection:
                if not df_historical.empty:
                    fig.add_trace(
                        go.Bar(
                            x=df_historical[date_column],
                            y=df_historical[value_col],
                            name=str(x),
                            marker=dict(color=color),
                            showlegend=show_legend
                        ),
                        row=row,
                        col=col
                    )

                if not df_forecast.empty:
                    fig.add_trace(
                        go.Bar(
                            x=df_forecast[date_column],
                            y=df_forecast[value_col],
                            name=str(x) + ' (forecast)',
                            marker=dict(color=color, opacity=0.6, pattern=dict(shape='/')),
                            showlegend=show_legend
                        ),
                        row=row,
                        col=col
                    )

                if not df_temp.empty:
                    ma_series = (
                        pd.to_numeric(df_temp[value_col], errors='coerce')
                        .rolling(window=4, min_periods=1)
                        .mean()
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=df_temp[date_column],
                            y=ma_series,
                            mode='lines',
                            name=f"{x} MA4",
                            line=dict(color=color, width=2, dash='dash'),
                            showlegend=show_legend
                        ),
                        row=row,
                        col=col
                    )

                # Only need to process the single selection once
                break

            else:
                if not df_historical.empty:
                    fig.add_trace(
                        go.Scatter(
                            x=df_historical[date_column],
                            y=df_historical[value_col],
                            mode='lines+markers',
                            name=str(x),
                            line=dict(color=color, dash=None),
                            showlegend=show_legend
                        ),
                        row=row,
                        col=col
                    )

                if not df_forecast.empty:
                    if not df_historical.empty:
                        last_hist = df_historical.iloc[-1]
                        first_forecast = df_forecast.iloc[0]
                        fig.add_trace(
                            go.Scatter(
                                x=[last_hist[date_column], first_forecast[date_column]],
                                y=[last_hist[value_col], first_forecast[value_col]],
                                mode='lines',
                                name=str(x) + ' transition',
                                line=dict(color=color, dash='dot'),
                                showlegend=False
                            ),
                            row=row,
                            col=col
                        )

                    fig.add_trace(
                        go.Scatter(
                            x=df_forecast[date_column],
                            y=df_forecast[value_col],
                            mode='lines+markers',
                            name=str(x) + ' (forecast)',
                            line=dict(color=color, dash='dot'),
                            marker=dict(symbol='circle-open'),
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

    if single_selection:
        fig.update_layout(barmode='group')
    
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
