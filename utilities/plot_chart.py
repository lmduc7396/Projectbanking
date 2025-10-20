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

    percentage_metrics = {
        'NIM', 'Loan yield', 'Deposit yield', 'ROA', 'ROE', 'NPL',
        'GROUP 2', 'LDR', 'NPL Coverage ratio', 'Provision/ Total Loan',
        'CAR', 'Cost of Fund', 'CASA', 'Credit growth', 'TOI growth',
        'PBT growth', 'Loan growth', 'Deposit growth', 'ROE (Annualized)',
        'ROA (Annualized)', 'NPL <=90 days', 'NPL >90 days'
    }
    
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
    selected_item = X[0] if single_selection else None

    ma_line_color = '#F95D6A'
    single_actual_color = '#61C2A8'
    single_forecast_color = '#A8E0D1'

    def prepare_selection_data(selection: str, source: pd.DataFrame) -> pd.DataFrame:
        matched_rows = sort_by_period(source[source['TICKER'] == selection])
        if matched_rows.empty:
            return matched_rows
        trimmed = matched_rows.tail(Y)
        return sort_by_period(trimmed)

    def split_actual_forecast(selection_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        if include_forecast and 'is_forecast' in selection_df.columns:
            historical = selection_df[selection_df['is_forecast'] == False]
            forecast = selection_df[selection_df['is_forecast'] == True]
            return historical, forecast
        return selection_df, pd.DataFrame(columns=selection_df.columns)

    for idx, z_name in enumerate(Z):
        # Use the name directly since columns already have descriptive names
        value_col = z_name
        
        # Check if this metric needs special formatting
        is_billion_metric = value_col in billion_scale_metrics
        is_percentage_metric = value_col in percentage_metrics

        # Create a copy of the data for this metric and ensure numeric dtype
        df_display = df.copy()
        df_display[value_col] = pd.to_numeric(df_display[value_col], errors='coerce')

        if is_billion_metric:
            df_display[value_col] = df_display[value_col].apply(
                lambda v: float(v) / 1e9 if pd.notnull(v) else float('nan')
            )
            subplot_title = f"{z_name} (B VND)"
        elif is_percentage_metric:
            df_display[value_col] = df_display[value_col] * 100
            subplot_title = f"{z_name} (%)"
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
        tick_suffix = None
        if is_billion_metric:
            tick_format = ",.0f"
        elif is_percentage_metric:
            tick_format = ",.1f"
            tick_suffix = "%"
        elif median_value > 10:
            tick_format = ",.2s"
        else:
            tick_format = ".2f"
    
        if single_selection and selected_item is not None:
            df_temp = prepare_selection_data(selected_item, df_display)
            if df_temp.empty:
                continue

            df_historical, df_forecast = split_actual_forecast(df_temp)
            color = color_sequence[0]
            legend_name = str(selected_item)
            show_legend = (idx == 0)

            if not df_historical.empty:
                fig.add_trace(
                    go.Bar(
                        x=df_historical[date_column],
                        y=df_historical[value_col],
                        name=legend_name,
                        marker=dict(color=single_actual_color),
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
                        name=f"{legend_name} (forecast)",
                        marker=dict(
                            color=single_forecast_color,
                            opacity=0.8,
                            pattern=dict(shape='/', fillmode='overlay')
                        ),
                        showlegend=show_legend
                    ),
                    row=row,
                    col=col
                )

            ma_series = (
                pd.to_numeric(df_temp[value_col], errors='coerce')
                .rolling(window=4, min_periods=1)
                .mean()
            )
            fig.add_trace(
                go.Scatter(
                    x=df_temp[date_column],
                    y=ma_series,
                    mode='lines+markers',
                    name=f"{legend_name} MA4",
                    line=dict(color=ma_line_color, width=2, dash='solid'),
                    marker=dict(symbol='diamond', size=7, color=ma_line_color),
                    showlegend=show_legend
                ),
                row=row,
                col=col
            )

            continue

        for i, selection in enumerate(X):
            show_legend = (idx == 0)
            color = color_sequence[i % len(color_sequence)]
            df_temp = prepare_selection_data(selection, df_display)
            if df_temp.empty:
                continue

            df_historical, df_forecast = split_actual_forecast(df_temp)

            if not df_historical.empty:
                fig.add_trace(
                    go.Scatter(
                        x=df_historical[date_column],
                        y=df_historical[value_col],
                        mode='lines+markers',
                        name=str(selection),
                        line=dict(color=color, dash=None),
                        marker=dict(size=7),
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
                            name=str(selection) + ' transition',
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
                        name=str(selection) + ' (forecast)',
                        line=dict(color=color, dash='dot'),
                        marker=dict(symbol='circle-open', size=7),
                        showlegend=show_legend
                    ),
                    row=row,
                    col=col
                )
        
        # Update y-axis format for this subplot
        fig.update_yaxes(
            tickformat=tick_format,
            ticksuffix=tick_suffix,
            automargin=True,
            row=row,
            col=col
        )
  
    fig.update_layout(
        width=1400,
        height=max(600, rows * 360),
        title_text=f"Banking Metrics: {', '.join(Z)}",
        legend_title="Ticker/Type",
        margin=dict(l=70, r=30, t=80, b=50)
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
