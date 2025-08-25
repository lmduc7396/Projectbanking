import pandas as pd
import numpy as np
from .quarter_utils import sort_quarters, format_quarter_for_display

def Banking_table(X, Y, Z, df=None, keyitem=None):
    # Use global variables if not provided as parameters
    if df is None:
        import streamlit as st
        df = st.session_state.get('df')
    if keyitem is None:
        import streamlit as st
        keyitem = st.session_state.get('keyitem')
    
    # Get forecast settings from session state
    import streamlit as st
    include_forecast = st.session_state.get('include_forecast', False)
    last_historical_year = st.session_state.get('last_historical_year', 2024)

    # Determine if we're working with quarterly or yearly data
    if 'Date_Quarter' in df.columns:
        date_column = 'Date_Quarter'
        is_quarterly = True
    elif 'Year' in df.columns:
        date_column = 'Year'
        is_quarterly = False
    else:
        raise ValueError("DataFrame must have either 'Date_Quarter' or 'Year' column")

    # --- Prepare List of Columns to Keep ---
    cols_keep_table1 = pd.DataFrame({
        'Name': [
            'Loan', 'TOI', 'Provision expense', 'PBT', 'ROA', 'ROE'
        ]
    })
    
    cols_keep_table2 = pd.DataFrame({
        'Name': [
            'NIM', 'Loan yield', 'NPL', 'NPL Formation (%)', 'GROUP 2', 'G2 Formation (%)',
            'NPL Coverage ratio', 'Provision/ Total Loan'
        ]
    })
    
    # No need to merge with keyitem since columns already have descriptive names
    cols_keep_final_table1 = [date_column] + cols_keep_table1['Name'].tolist()
    cols_keep_final_table2 = [date_column] + cols_keep_table2['Name'].tolist()

    # --- Filter Data for Table ---
    bank_type = ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']
    if X in bank_type:
        # For aggregated bank types, TICKER column contains the bank type name directly
        df_temp = df[df['TICKER'] == X]
    else:
        # Filter by specific ticker
        df_temp = df[df['TICKER'] == X]

    # --- Calculate Growth Tables ---
    def get_growth_table(df_, period, suffix, cols_names):
        """Calculate growth (%) and return formatted DataFrame."""
        cols_keep_final = [date_column] + cols_names['Name'].tolist()
        df_filtered = df_[cols_keep_final]
        growth = df_filtered.iloc[:, 1:].pct_change(periods=period, fill_method=None)
        growth = growth.add_suffix(f' {suffix} (%)')
        return pd.concat([df_filtered[date_column], growth], axis=1)

    def get_ytd_growth_table(df_, cols_names):
        """Calculate YTD growth (%) from current quarter to Q4 of previous year."""
        cols_keep_final = [date_column] + cols_names['Name'].tolist()
        df_filtered = df_[cols_keep_final].copy()
        
        if is_quarterly:
            # Extract year and quarter from Date_Quarter (format: YYYY-Q#)
            df_filtered['Year'] = df_filtered[date_column].str.extract(r'(\d{4})-Q').astype(int)
            df_filtered['Quarter'] = df_filtered[date_column].str.extract(r'-Q(\d)').astype(int)
        else:
            # For yearly data, Year column already contains the full year as integer
            df_filtered['Quarter'] = 4  # Treat yearly data as Q4
            # Convert Year column to ensure it's numeric (in case it's string)
            df_filtered['Year'] = pd.to_numeric(df_filtered[date_column])
        
        # Calculate YTD growth
        ytd_growth = pd.DataFrame(index=df_filtered.index)
        ytd_growth[date_column] = df_filtered[date_column]
        
        for col in cols_names['Name']:
            ytd_growth[f'{col} YTD (%)'] = np.nan
            
            for i in range(len(df_filtered)):
                current_year = df_filtered.iloc[i]['Year']
                current_value = df_filtered.iloc[i][col]
                
                # Find Q4 of previous year
                prev_year_q4 = df_filtered[
                    (df_filtered['Year'] == current_year - 1) & 
                    (df_filtered['Quarter'] == 4)
                ]
                
                if not prev_year_q4.empty and pd.notnull(current_value):
                    prev_q4_value = prev_year_q4.iloc[0][col]
                    if pd.notnull(prev_q4_value) and prev_q4_value != 0:
                        ytd_growth.iloc[i, ytd_growth.columns.get_loc(f'{col} YTD (%)')] = \
                            (current_value - prev_q4_value) / prev_q4_value
        
        return ytd_growth[[date_column] + [col for col in ytd_growth.columns if 'YTD (%)' in col]]

    def create_table(cols_names, table_name):
        cols_keep_final = [date_column] + cols_names['Name'].tolist()
        df_temp_table = df_temp[cols_keep_final]
        
        # --- Remove Date_Quarter column (columns already have friendly names) ---
        df_temp_table = df_temp_table.iloc[:, 1:]

        # --- Only add growth columns for table 1 (Earnings metrics) ---
        if table_name == "Earnings metrics":
            if is_quarterly:
                QoQ_change = get_growth_table(df_temp, 1, 'QoQ', cols_names)
                YoY_change = get_growth_table(df_temp, 4, 'YoY', cols_names)
            else:
                # For yearly data, YoY is comparing with previous year (period=1)
                YoY_change = get_growth_table(df_temp, 1, 'YoY', cols_names)
            
            # --- Combine Data Based on User Choice (QoQ or YoY) ---
            if Z == 'QoQ' and is_quarterly:
                df_out = pd.concat([df_temp[[date_column]], df_temp_table, QoQ_change.iloc[:, 1:]], axis=1)
                # Create column order dynamically
                col_order = [date_column]
                for i, name in enumerate(cols_names['Name'].tolist()):
                    col_order.append(name)
                    if i < 4:  # Only first 4 get growth columns
                        col_order.append(f"{name} QoQ (%)")
            else:
                # For yearly data or when YoY is selected
                df_out = pd.concat([df_temp[[date_column]], df_temp_table, YoY_change.iloc[:, 1:]], axis=1)
                # Create column order dynamically
                col_order = [date_column]
                for i, name in enumerate(cols_names['Name'].tolist()):
                    col_order.append(name)
                    if i < 4:  # Only first 4 get growth columns
                        col_order.append(f"{name} YoY (%)")
        else:
            # For table 2 (Ratios), don't add growth columns
            df_out = pd.concat([df_temp[[date_column]], df_temp_table], axis=1)
            col_order = [date_column] + cols_names['Name'].tolist()

        # --- Reindex, Select Last Y Periods, Transpose for Display ---
        df_out = df_out[col_order].tail(Y).T
        df_out.columns = df_out.iloc[0]
        df_out = df_out[1:]
        
        # Sort columns properly when forecast is included
        if include_forecast and 'is_forecast' in df_temp.columns:
            # Get the original column order (dates)
            date_cols = df_out.columns.tolist()
            # Sort using our custom quarter sorting function
            sorted_cols = sort_quarters(date_cols)
            # Reorder the dataframe columns
            df_out = df_out[sorted_cols]
        
        # Format column names for display
        if is_quarterly:
            # Convert column names to display format (YYYY-Q# -> #Qyy)
            display_cols = [format_quarter_for_display(col) for col in df_out.columns]
            df_out.columns = display_cols
        else:
            # For yearly data, convert float column names to integers for year display
            df_out.columns = [int(col) if isinstance(col, (float, np.float64)) else col for col in df_out.columns]
        
        # Return the table without displaying the title here
        return df_out

    # Create and display both tables
    df_table1 = create_table(cols_keep_table1, "Earnings metrics")
    df_table2 = create_table(cols_keep_table2, "Ratios")
    
    # Identify forecast columns if forecast is included
    forecast_columns = []
    if include_forecast and 'is_forecast' in df_temp.columns:
        # Get the dates that are forecasts
        forecast_dates = df_temp[df_temp['is_forecast'] == True][date_column].unique()
        # Convert to display format for column matching
        if is_quarterly:
            forecast_columns = [format_quarter_for_display(str(d)) for d in forecast_dates]
        else:
            forecast_columns = [str(d) for d in forecast_dates]
    
    return df_table1, df_table2, forecast_columns

