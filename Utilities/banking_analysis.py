#%%
"""
Banking analysis utility functions - Simplified with vectorized operations
"""

import pandas as pd
import numpy as np

#%% Main banking table creation function

def create_banking_table(ticker_or_type, num_periods, growth_type, df=None, keyitem=None):
    """
    Create banking analysis tables with earnings metrics and ratios
    Using simple formulas and vectorized operations
    
    Args:
        ticker_or_type: Bank ticker or type (Sector, SOCB, Private_1, etc.)
        num_periods: Number of periods to display
        growth_type: 'QoQ' or 'YoY' for growth calculations
        df: DataFrame with banking data
        keyitem: DataFrame with key item mappings
        
    Returns:
        tuple: (earnings_table, ratios_table)
    """
    # Use global variables if not provided
    if df is None:
        import streamlit as st
        df = st.session_state.get('df')
    if keyitem is None:
        import streamlit as st
        keyitem = st.session_state.get('keyitem')

    # Define metrics for each table
    earnings_metrics = ['Loan', 'TOI', 'Provision expense', 'PBT', 'ROA', 'ROE']
    ratio_metrics = ['NIM', 'Loan yield', 'NPL', 'NPL Formation (%)', 
                     'GROUP 2', 'G2 Formation (%)', 'NPL Coverage ratio', 'Provision/ Total Loan']
    
    # Get KeyCode mappings
    earnings_df = pd.DataFrame({'Name': earnings_metrics})
    ratios_df = pd.DataFrame({'Name': ratio_metrics})
    
    earnings_codes = earnings_df.merge(keyitem, on='Name', how='left')
    ratios_codes = ratios_df.merge(keyitem, on='Name', how='left')
    
    # Filter data based on ticker or type
    bank_types = ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']
    
    if ticker_or_type in bank_types:
        # Filter by Type - vectorized operation
        mask = (df['Type'] == ticker_or_type) & (df['TICKER'].str.len() > 3)
        df_filtered = df[mask].copy()
        # Get first ticker for aggregated types
        df_filtered = df_filtered[df_filtered['TICKER'] == df_filtered['TICKER'].iloc[0]]
    else:
        # Filter by specific ticker
        df_filtered = df[df['TICKER'] == ticker_or_type].copy()
    
    # Create earnings table
    earnings_table = process_table_data(
        df_filtered, earnings_codes, growth_type, num_periods, 
        include_growth=True, growth_cols=4
    )
    
    # Create ratios table
    ratios_table = process_table_data(
        df_filtered, ratios_codes, growth_type, num_periods, 
        include_growth=False
    )
    
    return earnings_table, ratios_table

#%% Process table data with growth calculations

def process_table_data(df_data, metrics_codes, growth_type, num_periods, include_growth=False, growth_cols=0):
    """
    Process data for a single table with optional growth calculations
    Using vectorized pandas operations
    """
    # Select columns
    cols_to_keep = ['Date_Quarter'] + metrics_codes['KeyCode'].tolist()
    df_table = df_data[cols_to_keep].copy()
    
    # Rename columns to friendly names
    rename_dict = dict(zip(metrics_codes['KeyCode'], metrics_codes['Name']))
    df_table.columns = ['Date_Quarter'] + [rename_dict.get(col, col) for col in df_table.columns[1:]]
    
    if include_growth:
        # Calculate growth using vectorized operations
        if growth_type == 'QoQ':
            # Quarter-over-quarter growth = (current - previous) / previous
            growth_df = df_table.iloc[:, 1:growth_cols+1].pct_change(periods=1)
        else:  # YoY
            # Year-over-year growth = (current - 4 quarters ago) / 4 quarters ago
            growth_df = df_table.iloc[:, 1:growth_cols+1].pct_change(periods=4)
        
        # Add suffix to growth columns
        growth_df.columns = [f"{col} {growth_type} (%)" for col in growth_df.columns]
        
        # Combine original and growth data
        result_df = pd.concat([df_table, growth_df], axis=1)
        
        # Reorder columns: Date_Quarter, then alternating metric and growth
        col_order = ['Date_Quarter']
        for i, name in enumerate(metrics_codes['Name'].tolist()):
            col_order.append(name)
            if i < growth_cols:
                col_order.append(f"{name} {growth_type} (%)")
        
        result_df = result_df[col_order]
    else:
        result_df = df_table
    
    # Select last N periods and transpose for display
    result_df = result_df.tail(num_periods).T
    result_df.columns = result_df.iloc[0]
    result_df = result_df[1:]
    
    return result_df

#%% Bank sector mapping function

def get_bank_sector_mapping(df_quarter, bank_type_mapping=None):
    """
    Create a mapping of bank tickers to their sectors
    Using vectorized operations
    
    Args:
        df_quarter: DataFrame with quarter data
        bank_type_mapping: Optional DataFrame with bank type mappings
        
    Returns:
        dict: Mapping of ticker to sector
    """
    if bank_type_mapping is not None:
        if 'TICKER' in bank_type_mapping.columns and 'Type' in bank_type_mapping.columns:
            return dict(zip(bank_type_mapping['TICKER'], bank_type_mapping['Type']))
    
    # Create mapping from df_quarter using vectorized operations
    # Filter to individual banks (3-char tickers)
    banks_df = df_quarter[df_quarter['TICKER'].str.len() == 3].copy()
    
    # Get first type for each ticker
    mapping = banks_df.groupby('TICKER')['Type'].first().to_dict()
    
    return mapping

#%% Calculate growth metrics

def calculate_growth_metrics(df, metric_col, growth_type='QoQ'):
    """
    Calculate growth metrics using simple formulas
    
    Args:
        df: DataFrame with time series data
        metric_col: Column name to calculate growth for
        growth_type: 'QoQ', 'YoY', or 'YTD'
    
    Returns:
        Series with growth percentages
    """
    if growth_type == 'QoQ':
        # Quarter over quarter growth
        growth = df[metric_col].pct_change(periods=1)
    elif growth_type == 'YoY':
        # Year over year growth
        growth = df[metric_col].pct_change(periods=4)
    elif growth_type == 'YTD':
        # Year to date growth - requires special handling
        df['year'] = df['Date_Quarter'].str.extract(r'Q(\d+)').astype(int)
        df['quarter'] = df['Date_Quarter'].str.extract(r'(\d+)Q').astype(int)
        
        # For each row, find Q4 of previous year
        growth = pd.Series(index=df.index, dtype=float)
        for idx in df.index:
            current_year = df.loc[idx, 'year']
            current_value = df.loc[idx, metric_col]
            
            # Find previous year Q4
            prev_q4_mask = (df['year'] == current_year - 1) & (df['quarter'] == 4)
            if prev_q4_mask.any():
                prev_q4_value = df.loc[prev_q4_mask, metric_col].iloc[0]
                growth[idx] = (current_value - prev_q4_value) / prev_q4_value if prev_q4_value != 0 else np.nan
    
    return growth * 100  # Convert to percentage

#%% Financial ratio calculations

def calculate_banking_ratios(df):
    """
    Calculate key banking ratios using simple formulas
    All calculations use vectorized operations
    """
    # Asset quality ratios
    df['npl_ratio'] = df['npl'] / df['total_loans']
    df['npl_coverage'] = df['provisions'] / df['npl']
    df['group2_ratio'] = df['group2_loans'] / df['total_loans']
    
    # Profitability ratios
    df['roa'] = df['net_income'] / df['total_assets']
    df['roe'] = df['net_income'] / df['equity']
    df['nim'] = df['net_interest_income'] / df['average_earning_assets']
    
    # Efficiency ratios
    df['cost_income_ratio'] = df['operating_expenses'] / df['operating_income']
    df['loan_deposit_ratio'] = df['total_loans'] / df['total_deposits']
    
    # Growth metrics
    df['loan_growth_qoq'] = df['total_loans'].pct_change()
    df['deposit_growth_qoq'] = df['total_deposits'].pct_change()
    df['revenue_growth_qoq'] = df['total_revenue'].pct_change()
    
    return df