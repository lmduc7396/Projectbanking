import pandas as pd
import numpy as np

def Banking_table(X, Y, Z, df=None, keyitem=None):
    # Use global variables if not provided as parameters
    if df is None:
        import streamlit as st
        df = st.session_state.get('df')
    if keyitem is None:
        import streamlit as st
        keyitem = st.session_state.get('keyitem')

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
    
    cols_code_keep_table1 = cols_keep_table1.merge(keyitem, on='Name', how='left')
    cols_code_keep_table2 = cols_keep_table2.merge(keyitem, on='Name', how='left')
    
    cols_keep_final_table1 = ['Date_Quarter'] + cols_code_keep_table1['KeyCode'].tolist()
    cols_keep_final_table2 = ['Date_Quarter'] + cols_code_keep_table2['KeyCode'].tolist()

    # --- Filter Data for Table ---
    bank_type = ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']
    if X in bank_type:
        # Filter by Type (e.g. Sector, SOCB, etc.)
        df_temp = df[(df['Type'] == X) & (df['TICKER'].apply(lambda t: len(t) > 3))]
        df_temp = df_temp[df_temp['TICKER'] == df_temp['TICKER'].iloc[0]]
    else:
        # Filter by specific ticker
        df_temp = df[df['TICKER'] == X]

    # --- Calculate Growth Tables ---
    def get_growth_table(df_, period, suffix, cols_code_keep):
        """Calculate growth (%) and return formatted DataFrame."""
        cols_keep_final = ['Date_Quarter'] + cols_code_keep['KeyCode'].tolist()
        df_filtered = df_[cols_keep_final]
        growth = df_filtered.iloc[:, 1:].pct_change(periods=period)
        growth.columns = growth.columns.map(dict(zip(cols_code_keep['KeyCode'], cols_code_keep['Name'])))
        growth = growth.add_suffix(f' {suffix} (%)')
        return pd.concat([df_filtered['Date_Quarter'], growth], axis=1)

    def get_ytd_growth_table(df_, cols_code_keep):
        """Calculate YTD growth (%) from current quarter to Q4 of previous year."""
        cols_keep_final = ['Date_Quarter'] + cols_code_keep['KeyCode'].tolist()
        df_filtered = df_[cols_keep_final].copy()
        
        # Extract year and quarter from Date_Quarter (format: XQ##)
        df_filtered['Quarter'] = df_filtered['Date_Quarter'].str.extract(r'(\d+)Q').astype(int)
        df_filtered['Year'] = df_filtered['Date_Quarter'].str.extract(r'Q(\d+)').astype(int)
        
        # Calculate YTD growth
        ytd_growth = pd.DataFrame(index=df_filtered.index)
        ytd_growth['Date_Quarter'] = df_filtered['Date_Quarter']
        
        for col in cols_code_keep['KeyCode']:
            friendly_name = dict(zip(cols_code_keep['KeyCode'], cols_code_keep['Name']))[col]
            ytd_growth[f'{friendly_name} YTD (%)'] = np.nan
            
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
                        ytd_growth.iloc[i, ytd_growth.columns.get_loc(f'{friendly_name} YTD (%)')] = \
                            (current_value - prev_q4_value) / prev_q4_value
        
        return ytd_growth[['Date_Quarter'] + [col for col in ytd_growth.columns if 'YTD (%)' in col]]

    def create_table(cols_code_keep, table_name):
        cols_keep_final = ['Date_Quarter'] + cols_code_keep['KeyCode'].tolist()
        df_temp_table = df_temp[cols_keep_final]
        
        # --- Rename Columns to Friendly Names, Remove Date_Quarter ---
        df_temp_table.columns = df_temp_table.columns.map(dict(zip(cols_code_keep['KeyCode'], cols_code_keep['Name'])))
        df_temp_table = df_temp_table.iloc[:, 1:]

        # --- Only add growth columns for table 1 (Earnings metrics) ---
        if table_name == "Earnings metrics":
            QoQ_change = get_growth_table(df_temp, 1, 'QoQ', cols_code_keep)
            YoY_change = get_growth_table(df_temp, 4, 'YoY', cols_code_keep)
            
            # --- Combine Data Based on User Choice (QoQ or YoY) ---
            if Z == 'QoQ':
                df_out = pd.concat([df_temp[['Date_Quarter']], df_temp_table, QoQ_change.iloc[:, 1:]], axis=1)
                # Create column order dynamically
                col_order = ['Date_Quarter']
                for i, name in enumerate(cols_code_keep['Name'].tolist()):
                    col_order.append(name)
                    if i < 4:  # Only first 4 get growth columns
                        col_order.append(f"{name} QoQ (%)")
            else:
                df_out = pd.concat([df_temp[['Date_Quarter']], df_temp_table, YoY_change.iloc[:, 1:]], axis=1)
                # Create column order dynamically
                col_order = ['Date_Quarter']
                for i, name in enumerate(cols_code_keep['Name'].tolist()):
                    col_order.append(name)
                    if i < 4:  # Only first 4 get growth columns
                        col_order.append(f"{name} YoY (%)")
        else:
            # For table 2 (Ratios), don't add growth columns
            df_out = pd.concat([df_temp[['Date_Quarter']], df_temp_table], axis=1)
            col_order = ['Date_Quarter'] + cols_code_keep['Name'].tolist()

        # --- Reindex, Select Last Y Periods, Transpose for Display ---
        df_out = df_out[col_order].tail(Y).T
        df_out.columns = df_out.iloc[0]
        df_out = df_out[1:]
        
        # Return the table without displaying the title here
        return df_out

    # Create and display both tables
    df_table1 = create_table(cols_code_keep_table1, "Earnings metrics")
    df_table2 = create_table(cols_code_keep_table2, "Ratios")
    
    return df_table1, df_table2

