#%%

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

def process_earnings_quality(df, period_column):
    """
    Process dataframe to calculate Core TOI, Core PBT and Non-recurring income
    
    Parameters:
    df: input dataframe
    period_column: 'Date_Quarter' for quarterly or 'Year' for yearly data
    """
    
    # Select required columns
    columns_to_keep = [
        'TICKER', 
        'Type', 
        period_column,
        'TOI',
        'Net Interest Income',
        'Fees Income',
        'OPEX',
        'Provision expense',
        'PBT',
        'Loan',
        'NIM'
    ]
    
    # Filter columns that exist in the dataframe
    existing_columns = [col for col in columns_to_keep if col in df.columns]
    df_processed = df[existing_columns].copy()
    
    # Calculate Core TOI (Total Operating Income from core operations)
    # Core TOI = Net Interest Income + Fees Income
    df_processed['Core TOI'] = (
        df_processed['Net Interest Income'] + 
        df_processed['Fees Income']
    )
    
    # Calculate Core PBT
    # Core PBT = Net Interest Income + Fees Income + OPEX + Provision expense
    # Note: OPEX and Provision expense are typically negative, so we add them directly
    df_processed['Core PBT'] = (
        df_processed['Net Interest Income'] + 
        df_processed['Fees Income'] + 
        df_processed['OPEX'] + 
        df_processed['Provision expense']
    )
    
    # Calculate Non-recurring income
    # Non-recurring income = PBT - Core PBT
    df_processed['Non-recurring income'] = df_processed['PBT'] - df_processed['Core PBT']
    
    return df_processed

def calculate_score_drivers_quarterly(df):
    """
    Calculate score drivers for quarterly data using T12M (trailing 12 months) comparison
    """
    df = df.sort_values(['TICKER', 'Date_Quarter']).copy()
    
    # Calculate T12M (rolling mean of previous 4 quarters) 
    metrics = ['Core TOI', 'PBT', 'OPEX', 'Provision expense', 'Non-recurring income', 
               'Net Interest Income', 'Fees Income', 'Loan', 'NIM']
    
    for metric in metrics:
        df[f'{metric}_T12M'] = df.groupby('TICKER')[metric].transform(
            lambda x: x.rolling(window=4, min_periods=4).mean().shift(1)
        )
    
    # Calculate changes vs T12M
    df['Core_TOI_Change'] = df['Core TOI'] - df['Core TOI_T12M']
    df['PBT_Change'] = df['PBT'] - df['PBT_T12M']
    df['OPEX_Change'] = df['OPEX'] - df['OPEX_T12M']
    df['Provision_Change'] = df['Provision expense'] - df['Provision expense_T12M']
    df['Non_Recurring_Change'] = df['Non-recurring income'] - df['Non-recurring income_T12M']
    df['NII_Change'] = df['Net Interest Income'] - df['Net Interest Income_T12M']
    df['Fee_Change'] = df['Fees Income'] - df['Fees Income_T12M']
    
    # Calculate Loan Growth % and NIM Change
    df['Loan_Avg'] = (df['Loan'] + df['Loan_T12M']) / 2
    df['Loan_Growth_%'] = np.where(
        df['Loan_Avg'] != 0,
        ((df['Loan'] - df['Loan_T12M']) / df['Loan_Avg']) * 100,
        0
    )
    
    # NIM Change in basis points
    df['NIM_Change_bps'] = (df['NIM'] - df['NIM_T12M']) * 100
    
    # Calculate raw contributions (should sum to PBT_Change)
    df['Raw_Top_Line'] = df['Core_TOI_Change']
    df['Raw_Cost_Cutting'] = df['OPEX_Change'] + df['Provision_Change']
    df['Raw_Non_Recurring'] = df['Non_Recurring_Change']
    
    # Verify accounting identity (for debugging)
    df['Check_Sum'] = df['Raw_Top_Line'] + df['Raw_Cost_Cutting'] + df['Raw_Non_Recurring']
    
    # Avoid division by zero
    df['PBT_Change_NonZero'] = df['PBT_Change'].replace(0, np.nan)
    
    # Add safeguard for very small PBT changes (less than 50 billion in absolute value)
    # These cause extreme score magnification and are likely noise
    small_pbt_threshold = 50_000_000_000  # 50 billion
    mask_small_pbt = df['PBT_Change'].abs() < small_pbt_threshold
    
    # For small PBT changes, cap the scores to reasonable ranges
    # Use the larger of PBT_Change or threshold for normalization
    df['PBT_Change_Adjusted'] = df['PBT_Change_NonZero'].copy()
    df.loc[mask_small_pbt & (df['PBT_Change'] > 0), 'PBT_Change_Adjusted'] = small_pbt_threshold
    df.loc[mask_small_pbt & (df['PBT_Change'] < 0), 'PBT_Change_Adjusted'] = -small_pbt_threshold
    
    # Normalized Scores as % of ABSOLUTE adjusted PBT change
    df['PBT_Change_Abs_Adjusted'] = df['PBT_Change_Adjusted'].abs()
    
    # Calculate scores as % of absolute PBT change
    df['Top_Line_Score'] = (df['Raw_Top_Line'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Cost_Cutting_Score'] = (df['Raw_Cost_Cutting'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Non_Recurring_Score'] = (df['Raw_Non_Recurring'] / df['PBT_Change_Abs_Adjusted']) * 100
    
    # Sub-scores as % of absolute adjusted PBT change
    df['NII_Sub_Score'] = (df['NII_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Fee_Sub_Score'] = (df['Fee_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['OPEX_Sub_Score'] = (df['OPEX_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Provision_Sub_Score'] = (df['Provision_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    
    # Calculate NII sub-component scores using simple logic
    # Loan Growth Score = Loan_Growth_% / 2
    # NIM Change Score = NII_Sub_Score - Loan_Growth_Score
    
    df['Loan_Growth_Score'] = df['Loan_Growth_%'] / 2
    df['NIM_Change_Score'] = df['NII_Sub_Score'] - df['Loan_Growth_Score']
    
    # Apply sign convention: positive PBT -> +100%, negative PBT -> -100%
    # For negative PBT changes, we keep the natural signs which sum to -100%
    # For positive PBT changes, the natural signs sum to +100%
    # No flipping needed - the math works out correctly!
    
    # Add a flag for small PBT changes
    df['Small_PBT_Flag'] = mask_small_pbt
    
    # Cap extreme scores at ±500% to maintain readability
    # Track which scores were capped
    score_cols = ['Top_Line_Score', 'Cost_Cutting_Score', 'Non_Recurring_Score',
                  'NII_Sub_Score', 'Fee_Sub_Score', 'OPEX_Sub_Score', 'Provision_Sub_Score',
                  'Loan_Growth_Score', 'NIM_Change_Score']
    
    df['Scores_Capped'] = False
    for col in score_cols:
        # Track if any score was capped
        df.loc[df[col].abs() > 500, 'Scores_Capped'] = True
        # Cap the scores
        df[col] = df[col].clip(lower=-500, upper=500)
    
    # Calculate initial total score
    df['Total_Score'] = df['Top_Line_Score'] + df['Cost_Cutting_Score'] + df['Non_Recurring_Score']
    
    # For small PBT cases, scale scores proportionally to maintain ±100% convention
    # This ensures scores always sum to exactly ±100% even when using threshold
    if 'Small_PBT_Flag' in df.columns:
        small_pbt_mask = df['Small_PBT_Flag'] & df['Total_Score'].notna()
        
        if small_pbt_mask.any():
            # Calculate target total (100 for positive PBT, -100 for negative PBT)
            df.loc[small_pbt_mask, 'Target_Total'] = np.where(
                df.loc[small_pbt_mask, 'PBT_Change'] > 0, 100, -100
            )
            
            # Calculate scaling factor
            df.loc[small_pbt_mask, 'Scale_Factor'] = (
                df.loc[small_pbt_mask, 'Target_Total'] / df.loc[small_pbt_mask, 'Total_Score']
            )
            
            # Apply scaling to main scores
            for col in ['Top_Line_Score', 'Cost_Cutting_Score', 'Non_Recurring_Score']:
                df.loc[small_pbt_mask, col] = (
                    df.loc[small_pbt_mask, col] * df.loc[small_pbt_mask, 'Scale_Factor']
                )
            
            # Apply scaling to sub-scores
            for col in ['NII_Sub_Score', 'Fee_Sub_Score', 'OPEX_Sub_Score', 'Provision_Sub_Score',
                       'Loan_Growth_Score', 'NIM_Change_Score']:
                df.loc[small_pbt_mask, col] = (
                    df.loc[small_pbt_mask, col] * df.loc[small_pbt_mask, 'Scale_Factor']
                )
            
            # Recalculate total after scaling
            df['Total_Score'] = df['Top_Line_Score'] + df['Cost_Cutting_Score'] + df['Non_Recurring_Score']
            
            # Clean up temporary columns
            df = df.drop(['Target_Total', 'Scale_Factor'], axis=1, errors='ignore')
    
    # Round scores for readability
    score_columns = ['Top_Line_Score', 'Cost_Cutting_Score', 'Non_Recurring_Score', 'Total_Score',
                    'NII_Sub_Score', 'Fee_Sub_Score', 'OPEX_Sub_Score', 'Provision_Sub_Score',
                    'Loan_Growth_Score', 'NIM_Change_Score']
    for col in score_columns:
        df[col] = df[col].round(1)
    
    # Calculate weighted impacts (no suffix for T12M as it's the default)
    df = calculate_weighted_impacts(df, '')
    
    return df

def calculate_score_drivers_qoq(df):
    """Calculate Quarter-over-Quarter scores (previous quarter comparison)"""
    df = df.sort_values(['TICKER', 'Date_Quarter']).copy()
    
    # Calculate QoQ base values (previous quarter)
    metrics = ['Core TOI', 'PBT', 'OPEX', 'Provision expense', 'Non-recurring income', 
               'Net Interest Income', 'Fees Income', 'Loan', 'NIM']
    
    for metric in metrics:
        df[f'{metric}_QoQ'] = df.groupby('TICKER')[metric].shift(1)
    
    # Calculate changes vs prior quarter
    df['Core_TOI_Change'] = df['Core TOI'] - df['Core TOI_QoQ']
    df['PBT_Change'] = df['PBT'] - df['PBT_QoQ']
    df['OPEX_Change'] = df['OPEX'] - df['OPEX_QoQ']
    df['Provision_Change'] = df['Provision expense'] - df['Provision expense_QoQ']
    df['Non_Recurring_Change'] = df['Non-recurring income'] - df['Non-recurring income_QoQ']
    df['NII_Change'] = df['Net Interest Income'] - df['Net Interest Income_QoQ']
    df['Fee_Change'] = df['Fees Income'] - df['Fees Income_QoQ']
    
    # Rest of calculation same as T12M
    df['Loan_Avg'] = (df['Loan'] + df['Loan_QoQ']) / 2
    df['Loan_Growth_%'] = np.where(
        df['Loan_Avg'] != 0,
        ((df['Loan'] - df['Loan_QoQ']) / df['Loan_Avg']) * 100,
        0
    )
    df['NIM_Change_bps'] = (df['NIM'] - df['NIM_QoQ']) * 100
    
    # Continue with standard score calculation (copy from quarterly function)
    # ... rest is same as calculate_score_drivers_quarterly from line 94 onwards
    # Copying the rest of the logic
    df['Raw_Top_Line'] = df['Core_TOI_Change']
    df['Raw_Cost_Cutting'] = df['OPEX_Change'] + df['Provision_Change']
    df['Raw_Non_Recurring'] = df['Non_Recurring_Change']
    
    df['PBT_Change_NonZero'] = df['PBT_Change'].replace(0, np.nan)
    
    small_pbt_threshold = 50_000_000_000
    mask_small_pbt = df['PBT_Change'].abs() < small_pbt_threshold
    
    df['PBT_Change_Adjusted'] = df['PBT_Change_NonZero'].copy()
    df.loc[mask_small_pbt & (df['PBT_Change'] > 0), 'PBT_Change_Adjusted'] = small_pbt_threshold
    df.loc[mask_small_pbt & (df['PBT_Change'] < 0), 'PBT_Change_Adjusted'] = -small_pbt_threshold
    
    df['PBT_Change_Abs_Adjusted'] = df['PBT_Change_Adjusted'].abs()
    
    df['Top_Line_Score'] = (df['Raw_Top_Line'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Cost_Cutting_Score'] = (df['Raw_Cost_Cutting'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Non_Recurring_Score'] = (df['Raw_Non_Recurring'] / df['PBT_Change_Abs_Adjusted']) * 100
    
    df['NII_Sub_Score'] = (df['NII_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Fee_Sub_Score'] = (df['Fee_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['OPEX_Sub_Score'] = (df['OPEX_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Provision_Sub_Score'] = (df['Provision_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    
    df['Loan_Growth_Score'] = df['Loan_Growth_%'] / 2
    df['NIM_Change_Score'] = df['NII_Sub_Score'] - df['Loan_Growth_Score']
    
    df['Small_PBT_Flag'] = mask_small_pbt
    
    score_cols = ['Top_Line_Score', 'Cost_Cutting_Score', 'Non_Recurring_Score',
                  'NII_Sub_Score', 'Fee_Sub_Score', 'OPEX_Sub_Score', 'Provision_Sub_Score',
                  'Loan_Growth_Score', 'NIM_Change_Score']
    
    df['Scores_Capped'] = False
    for col in score_cols:
        df.loc[df[col].abs() > 500, 'Scores_Capped'] = True
        df[col] = df[col].clip(lower=-500, upper=500)
    
    df['Total_Score'] = df['Top_Line_Score'] + df['Cost_Cutting_Score'] + df['Non_Recurring_Score']
    
    # Scale for small PBT cases
    if 'Small_PBT_Flag' in df.columns:
        small_pbt_mask = df['Small_PBT_Flag'] & df['Total_Score'].notna()
        if small_pbt_mask.any():
            df.loc[small_pbt_mask, 'Target_Total'] = np.where(
                df.loc[small_pbt_mask, 'PBT_Change'] > 0, 100, -100
            )
            df.loc[small_pbt_mask, 'Scale_Factor'] = (
                df.loc[small_pbt_mask, 'Target_Total'] / df.loc[small_pbt_mask, 'Total_Score']
            )
            for col in score_cols + ['Total_Score']:
                df.loc[small_pbt_mask, col] = (
                    df.loc[small_pbt_mask, col] * df.loc[small_pbt_mask, 'Scale_Factor']
                )
            df = df.drop(['Target_Total', 'Scale_Factor'], axis=1, errors='ignore')
    
    # Round scores
    for col in score_cols + ['Total_Score']:
        df[col] = df[col].round(1)
    
    return df

def calculate_score_drivers_yoy(df):
    """Calculate Year-over-Year scores (same quarter last year)"""
    df = df.sort_values(['TICKER', 'Date_Quarter']).copy()
    
    # Calculate YoY base values (4 quarters ago)
    metrics = ['Core TOI', 'PBT', 'OPEX', 'Provision expense', 'Non-recurring income', 
               'Net Interest Income', 'Fees Income', 'Loan', 'NIM']
    
    for metric in metrics:
        df[f'{metric}_YoY'] = df.groupby('TICKER')[metric].shift(4)
    
    # Calculate changes vs same quarter last year
    df['Core_TOI_Change'] = df['Core TOI'] - df['Core TOI_YoY']
    df['PBT_Change'] = df['PBT'] - df['PBT_YoY'] 
    df['OPEX_Change'] = df['OPEX'] - df['OPEX_YoY']
    df['Provision_Change'] = df['Provision expense'] - df['Provision expense_YoY']
    df['Non_Recurring_Change'] = df['Non-recurring income'] - df['Non-recurring income_YoY']
    df['NII_Change'] = df['Net Interest Income'] - df['Net Interest Income_YoY']
    df['Fee_Change'] = df['Fees Income'] - df['Fees Income_YoY']
    
    # Loan growth and NIM change
    df['Loan_Avg'] = (df['Loan'] + df['Loan_YoY']) / 2
    df['Loan_Growth_%'] = np.where(
        df['Loan_Avg'] != 0,
        ((df['Loan'] - df['Loan_YoY']) / df['Loan_Avg']) * 100,
        0
    )
    df['NIM_Change_bps'] = (df['NIM'] - df['NIM_YoY']) * 100
    
    # Rest of calculation same as T12M
    df['Raw_Top_Line'] = df['Core_TOI_Change']
    df['Raw_Cost_Cutting'] = df['OPEX_Change'] + df['Provision_Change']
    df['Raw_Non_Recurring'] = df['Non_Recurring_Change']
    
    df['PBT_Change_NonZero'] = df['PBT_Change'].replace(0, np.nan)
    
    small_pbt_threshold = 50_000_000_000
    mask_small_pbt = df['PBT_Change'].abs() < small_pbt_threshold
    
    df['PBT_Change_Adjusted'] = df['PBT_Change_NonZero'].copy()
    df.loc[mask_small_pbt & (df['PBT_Change'] > 0), 'PBT_Change_Adjusted'] = small_pbt_threshold
    df.loc[mask_small_pbt & (df['PBT_Change'] < 0), 'PBT_Change_Adjusted'] = -small_pbt_threshold
    
    df['PBT_Change_Abs_Adjusted'] = df['PBT_Change_Adjusted'].abs()
    
    df['Top_Line_Score'] = (df['Raw_Top_Line'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Cost_Cutting_Score'] = (df['Raw_Cost_Cutting'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Non_Recurring_Score'] = (df['Raw_Non_Recurring'] / df['PBT_Change_Abs_Adjusted']) * 100
    
    df['NII_Sub_Score'] = (df['NII_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Fee_Sub_Score'] = (df['Fee_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['OPEX_Sub_Score'] = (df['OPEX_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Provision_Sub_Score'] = (df['Provision_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    
    df['Loan_Growth_Score'] = df['Loan_Growth_%'] / 2
    df['NIM_Change_Score'] = df['NII_Sub_Score'] - df['Loan_Growth_Score']
    
    df['Small_PBT_Flag'] = mask_small_pbt
    
    score_cols = ['Top_Line_Score', 'Cost_Cutting_Score', 'Non_Recurring_Score',
                  'NII_Sub_Score', 'Fee_Sub_Score', 'OPEX_Sub_Score', 'Provision_Sub_Score',
                  'Loan_Growth_Score', 'NIM_Change_Score']
    
    df['Scores_Capped'] = False
    for col in score_cols:
        df.loc[df[col].abs() > 500, 'Scores_Capped'] = True
        df[col] = df[col].clip(lower=-500, upper=500)
    
    df['Total_Score'] = df['Top_Line_Score'] + df['Cost_Cutting_Score'] + df['Non_Recurring_Score']
    
    # Scale for small PBT cases
    if 'Small_PBT_Flag' in df.columns:
        small_pbt_mask = df['Small_PBT_Flag'] & df['Total_Score'].notna()
        if small_pbt_mask.any():
            df.loc[small_pbt_mask, 'Target_Total'] = np.where(
                df.loc[small_pbt_mask, 'PBT_Change'] > 0, 100, -100
            )
            df.loc[small_pbt_mask, 'Scale_Factor'] = (
                df.loc[small_pbt_mask, 'Target_Total'] / df.loc[small_pbt_mask, 'Total_Score']
            )
            for col in score_cols + ['Total_Score']:
                df.loc[small_pbt_mask, col] = (
                    df.loc[small_pbt_mask, col] * df.loc[small_pbt_mask, 'Scale_Factor']
                )
            df = df.drop(['Target_Total', 'Scale_Factor'], axis=1, errors='ignore')
    
    # Round scores
    for col in score_cols + ['Total_Score']:
        df[col] = df[col].round(1)
    
    return df

def calculate_weighted_impacts(df, suffix=''):
    """
    Calculate weighted impact scores from raw scores
    Formula: Impact = (Score * |PBT_Growth_%|) / 100
    Special case for Loan and NIM: Not weighted, just divided by 2
    """
    # Get the appropriate column names based on suffix
    if suffix:
        pbt_col = f'PBT_{suffix}'
        pbt_change_col = f'PBT_Change_{suffix}'
        score_suffix = f'_{suffix}'
    else:
        pbt_col = 'PBT'
        pbt_change_col = 'PBT_Change'
        score_suffix = ''
    
    # Calculate PBT Growth % for the appropriate period
    if suffix == 'T12M':
        df['PBT_Growth_%'] = np.where(
            df['PBT_T12M'].notna() & (df['PBT_T12M'] != 0),
            (df[pbt_change_col] / df['PBT_T12M'].abs()) * 100,
            0
        )
    elif suffix == 'QoQ':
        df['PBT_Growth_%'] = np.where(
            df['PBT_QoQ'].notna() & (df['PBT_QoQ'] != 0),
            (df[pbt_change_col] / df['PBT_QoQ'].abs()) * 100,
            0
        )
    elif suffix == 'YoY':
        df['PBT_Growth_%'] = np.where(
            df['PBT_YoY'].notna() & (df['PBT_YoY'] != 0),
            (df[pbt_change_col] / df['PBT_YoY'].abs()) * 100,
            0
        )
    elif 'PBT_Prior_Year' in df.columns:
        # For yearly data
        df['PBT_Growth_%'] = np.where(
            df['PBT_Prior_Year'].notna() & (df['PBT_Prior_Year'] != 0),
            (df['PBT_Change'] / df['PBT_Prior_Year'].abs()) * 100,
            0
        )
    else:
        # For T12M without suffix (quarterly default)
        df['PBT_Growth_%'] = np.where(
            df['PBT_T12M'].notna() & (df['PBT_T12M'] != 0),
            (df['PBT_Change'] / df['PBT_T12M'].abs()) * 100,
            0
        )
    
    # Store PBT Growth % with suffix
    df[f'PBT_Growth_%{score_suffix}'] = df['PBT_Growth_%']
    
    # Calculate weighted impacts for main scores
    main_scores = ['Top_Line_Score', 'Cost_Cutting_Score', 'Non_Recurring_Score']
    for score in main_scores:
        score_col = f'{score}{score_suffix}'
        impact_col = score_col.replace('_Score', '_Impact')
        if score_col in df.columns:
            df[impact_col] = (df[score_col] * df['PBT_Growth_%'].abs()) / 100
            df[impact_col] = df[impact_col].round(1)
    
    # Calculate weighted impacts for sub-scores (except Loan and NIM)
    sub_scores = ['NII_Sub_Score', 'Fee_Sub_Score', 'OPEX_Sub_Score', 'Provision_Sub_Score']
    for score in sub_scores:
        score_col = f'{score}{score_suffix}'
        impact_col = score_col.replace('_Sub_Score', '_Impact')
        if score_col in df.columns:
            df[impact_col] = (df[score_col] * df['PBT_Growth_%'].abs()) / 100
            df[impact_col] = df[impact_col].round(1)
    
    # Special calculation for Loan and NIM impacts
    # Loan_Impact = Loan_Growth_% / 2 (not weighted)
    # NIM_Impact = NII_Impact - Loan_Impact
    loan_growth_col = f'Loan_Growth_%{score_suffix}'
    if loan_growth_col in df.columns:
        df[f'Loan_Impact{score_suffix}'] = df[loan_growth_col] / 2
        df[f'Loan_Impact{score_suffix}'] = df[f'Loan_Impact{score_suffix}'].round(1)
        
        # NIM Impact = NII_Impact - Loan_Impact
        nii_impact_col = f'NII_Impact{score_suffix}'
        if nii_impact_col in df.columns:
            df[f'NIM_Impact{score_suffix}'] = df[nii_impact_col] - df[f'Loan_Impact{score_suffix}']
            df[f'NIM_Impact{score_suffix}'] = df[f'NIM_Impact{score_suffix}'].round(1)
    
    # Calculate Total Impact (sum of main impacts)
    revenue_impact_col = f'Top_Line_Impact{score_suffix}'
    cost_impact_col = f'Cost_Cutting_Impact{score_suffix}'
    non_recurring_impact_col = f'Non_Recurring_Impact{score_suffix}'
    
    if all(col in df.columns for col in [revenue_impact_col, cost_impact_col, non_recurring_impact_col]):
        df[f'Total_Impact{score_suffix}'] = (
            df[revenue_impact_col] + df[cost_impact_col] + df[non_recurring_impact_col]
        )
        df[f'Total_Impact{score_suffix}'] = df[f'Total_Impact{score_suffix}'].round(1)
    
    # Clean up temporary PBT_Growth_% column only if it's different from the suffixed version
    if 'PBT_Growth_%' in df.columns and f'PBT_Growth_%{score_suffix}' in df.columns:
        # Only drop if they are different columns (i.e., suffix is not empty)
        if f'PBT_Growth_%{score_suffix}' != 'PBT_Growth_%':
            df = df.drop('PBT_Growth_%', axis=1)
    
    return df

def add_suffix_to_scores(df, suffix):
    """Add suffix to score columns for different comparison types"""
    score_cols = ['Top_Line_Score', 'Cost_Cutting_Score', 'Non_Recurring_Score', 'Total_Score',
                  'NII_Sub_Score', 'Fee_Sub_Score', 'OPEX_Sub_Score', 'Provision_Sub_Score',
                  'Loan_Growth_Score', 'NIM_Change_Score']
    
    base_cols = ['PBT_Change', 'Core_TOI_Change', 'OPEX_Change', 'Provision_Change',
                 'Non_Recurring_Change', 'NII_Change', 'Fee_Change', 'Loan_Growth_%', 'NIM_Change_bps']
    
    # Add suffix to score columns
    for col in score_cols:
        if col in df.columns:
            df[f'{col}_{suffix}'] = df[col]
            df = df.drop(col, axis=1)
    
    # Add suffix to base columns
    for col in base_cols:
        if col in df.columns:
            df[f'{col}_{suffix}'] = df[col]
            df = df.drop(col, axis=1)
    
    # Also rename base period columns
    if suffix == 'QoQ':
        base_suffix = '_QoQ'
    elif suffix == 'YoY':
        base_suffix = '_YoY'
    else:
        base_suffix = '_T12M'
    
    # Rename comparison base columns
    for metric in ['PBT', 'Core TOI', 'OPEX', 'Provision expense', 'Non-recurring income', 
                   'Net Interest Income', 'Fees Income', 'Loan', 'NIM']:
        old_col = f'{metric}{base_suffix}'
        if old_col in df.columns:
            df[f'{metric}_{suffix}'] = df[old_col]
            if old_col != f'{metric}_{suffix}':
                df = df.drop(old_col, axis=1)
    
    return df

def merge_all_scores(df_base, df_t12m, df_qoq, df_yoy):
    """Merge all three comparison dataframes"""
    
    # Start with base columns
    base_cols = ['TICKER', 'Type', 'Date_Quarter', 'TOI', 'Net Interest Income', 'Fees Income',
                 'OPEX', 'Provision expense', 'PBT', 'Loan', 'NIM', 'Core TOI', 'Core PBT', 
                 'Non-recurring income']
    
    df_merged = df_base[base_cols].copy()
    
    # Add T12M columns (including backward compatibility unsuffixed versions)
    for col in df_t12m.columns:
        if col not in df_merged.columns:
            df_merged[col] = df_t12m[col]
    
    # For backward compatibility, also add unsuffixed versions from T12M for both scores and impacts
    score_cols = ['Top_Line_Score', 'Cost_Cutting_Score', 'Non_Recurring_Score', 'Total_Score',
                  'NII_Sub_Score', 'Fee_Sub_Score', 'OPEX_Sub_Score', 'Provision_Sub_Score',
                  'Loan_Growth_Score', 'NIM_Change_Score']
    
    impact_cols = ['Top_Line_Impact', 'Cost_Cutting_Impact', 'Non_Recurring_Impact', 'Total_Impact',
                   'NII_Impact', 'Fee_Impact', 'OPEX_Impact', 'Provision_Impact',
                   'Loan_Impact', 'NIM_Impact']
    
    # Add unsuffixed versions from T12M (default comparison)
    for col in score_cols:
        if f'{col}_T12M' in df_merged.columns:
            df_merged[col] = df_merged[f'{col}_T12M']
    
    for col in impact_cols:
        if col in df_merged.columns:
            # Already added from T12M without suffix
            pass
    
    # Also keep base T12M columns without suffix for backward compatibility
    if 'PBT_Change_T12M' in df_merged.columns:
        df_merged['PBT_Change'] = df_merged['PBT_Change_T12M']
    if 'Loan_Growth_%_T12M' in df_merged.columns:
        df_merged['Loan_Growth_%'] = df_merged['Loan_Growth_%_T12M']
    if 'PBT_Growth_%' in df_merged.columns:
        # Already added from T12M without suffix
        pass
    
    # Add QoQ columns
    for col in df_qoq.columns:
        if col not in df_merged.columns and ('_QoQ' in col or 'Impact_QoQ' in col):
            df_merged[col] = df_qoq[col]
    
    # Add YoY columns
    for col in df_yoy.columns:
        if col not in df_merged.columns and ('_YoY' in col or 'Impact_YoY' in col):
            df_merged[col] = df_yoy[col]
    
    # Keep flag columns
    if 'Small_PBT_Flag' in df_t12m.columns:
        df_merged['Small_PBT_Flag'] = df_t12m['Small_PBT_Flag']
    if 'Scores_Capped' in df_t12m.columns:
        df_merged['Scores_Capped'] = df_t12m['Scores_Capped']
    
    return df_merged

def calculate_score_drivers_yearly(df):
    """
    Calculate score drivers for yearly data using YoY comparison with normalized scores (sum to 100%)
    """
    df = df.sort_values(['TICKER', 'Year']).copy()
    
    # Calculate year-over-year changes
    metrics = ['Core TOI', 'PBT', 'OPEX', 'Provision expense', 'Non-recurring income',
               'Net Interest Income', 'Fees Income', 'Loan', 'NIM']
    
    for metric in metrics:
        df[f'{metric}_Prior_Year'] = df.groupby('TICKER')[metric].shift(1)
    
    # Calculate changes vs prior year
    df['Core_TOI_Change'] = df['Core TOI'] - df['Core TOI_Prior_Year']
    df['PBT_Change'] = df['PBT'] - df['PBT_Prior_Year']
    df['OPEX_Change'] = df['OPEX'] - df['OPEX_Prior_Year']
    df['Provision_Change'] = df['Provision expense'] - df['Provision expense_Prior_Year']
    df['Non_Recurring_Change'] = df['Non-recurring income'] - df['Non-recurring income_Prior_Year']
    df['NII_Change'] = df['Net Interest Income'] - df['Net Interest Income_Prior_Year']
    df['Fee_Change'] = df['Fees Income'] - df['Fees Income_Prior_Year']
    
    # Calculate Loan Growth % and NIM Change for NII sub-component analysis
    # Loan Growth % = (Current - Prior) / Average
    df['Loan_Avg'] = (df['Loan'] + df['Loan_Prior_Year']) / 2
    df['Loan_Growth_%'] = np.where(
        df['Loan_Avg'] != 0,
        ((df['Loan'] - df['Loan_Prior_Year']) / df['Loan_Avg']) * 100,
        0
    )
    
    # NIM Change in basis points (absolute change)
    df['NIM_Change_bps'] = (df['NIM'] - df['NIM_Prior_Year']) * 100  # Convert to basis points
    
    # Calculate raw contributions (should sum to PBT_Change)
    df['Raw_Top_Line'] = df['Core_TOI_Change']
    df['Raw_Cost_Cutting'] = df['OPEX_Change'] + df['Provision_Change']  # No negation - they're already negative when costs increase
    df['Raw_Non_Recurring'] = df['Non_Recurring_Change']
    
    # Verify accounting identity (for debugging)
    df['Check_Sum'] = df['Raw_Top_Line'] + df['Raw_Cost_Cutting'] + df['Raw_Non_Recurring']
    
    # Avoid division by zero
    df['PBT_Change_NonZero'] = df['PBT_Change'].replace(0, np.nan)
    
    # Add safeguard for very small PBT changes (less than 50 billion in absolute value)
    # These cause extreme score magnification and are likely noise
    small_pbt_threshold = 50_000_000_000  # 50 billion
    mask_small_pbt = df['PBT_Change'].abs() < small_pbt_threshold
    
    # For small PBT changes, cap the scores to reasonable ranges
    # Use the larger of PBT_Change or threshold for normalization
    df['PBT_Change_Adjusted'] = df['PBT_Change_NonZero'].copy()
    df.loc[mask_small_pbt & (df['PBT_Change'] > 0), 'PBT_Change_Adjusted'] = small_pbt_threshold
    df.loc[mask_small_pbt & (df['PBT_Change'] < 0), 'PBT_Change_Adjusted'] = -small_pbt_threshold
    
    # Normalized Scores as % of ABSOLUTE adjusted PBT change
    df['PBT_Change_Abs_Adjusted'] = df['PBT_Change_Adjusted'].abs()
    
    # Calculate scores as % of absolute PBT change
    df['Top_Line_Score'] = (df['Raw_Top_Line'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Cost_Cutting_Score'] = (df['Raw_Cost_Cutting'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Non_Recurring_Score'] = (df['Raw_Non_Recurring'] / df['PBT_Change_Abs_Adjusted']) * 100
    
    # Sub-scores as % of absolute adjusted PBT change
    df['NII_Sub_Score'] = (df['NII_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Fee_Sub_Score'] = (df['Fee_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['OPEX_Sub_Score'] = (df['OPEX_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    df['Provision_Sub_Score'] = (df['Provision_Change'] / df['PBT_Change_Abs_Adjusted']) * 100
    
    # Calculate NII sub-component scores using simple logic
    # Loan Growth Score = Loan_Growth_% / 2
    # NIM Change Score = NII_Sub_Score - Loan_Growth_Score
    
    df['Loan_Growth_Score'] = df['Loan_Growth_%'] / 2
    df['NIM_Change_Score'] = df['NII_Sub_Score'] - df['Loan_Growth_Score']
    
    # Apply sign convention: positive PBT -> +100%, negative PBT -> -100%
    # For negative PBT changes, we keep the natural signs which sum to -100%
    # For positive PBT changes, the natural signs sum to +100%
    # No flipping needed - the math works out correctly!
    
    # Add a flag for small PBT changes
    df['Small_PBT_Flag'] = mask_small_pbt
    
    # Cap extreme scores at ±500% to maintain readability
    # Track which scores were capped
    score_cols = ['Top_Line_Score', 'Cost_Cutting_Score', 'Non_Recurring_Score',
                  'NII_Sub_Score', 'Fee_Sub_Score', 'OPEX_Sub_Score', 'Provision_Sub_Score',
                  'Loan_Growth_Score', 'NIM_Change_Score']
    
    df['Scores_Capped'] = False
    for col in score_cols:
        # Track if any score was capped
        df.loc[df[col].abs() > 500, 'Scores_Capped'] = True
        # Cap the scores
        df[col] = df[col].clip(lower=-500, upper=500)
    
    # Calculate initial total score
    df['Total_Score'] = df['Top_Line_Score'] + df['Cost_Cutting_Score'] + df['Non_Recurring_Score']
    
    # For small PBT cases, scale scores proportionally to maintain ±100% convention
    # This ensures scores always sum to exactly ±100% even when using threshold
    if 'Small_PBT_Flag' in df.columns:
        small_pbt_mask = df['Small_PBT_Flag'] & df['Total_Score'].notna()
        
        if small_pbt_mask.any():
            # Calculate target total (100 for positive PBT, -100 for negative PBT)
            df.loc[small_pbt_mask, 'Target_Total'] = np.where(
                df.loc[small_pbt_mask, 'PBT_Change'] > 0, 100, -100
            )
            
            # Calculate scaling factor
            df.loc[small_pbt_mask, 'Scale_Factor'] = (
                df.loc[small_pbt_mask, 'Target_Total'] / df.loc[small_pbt_mask, 'Total_Score']
            )
            
            # Apply scaling to main scores
            for col in ['Top_Line_Score', 'Cost_Cutting_Score', 'Non_Recurring_Score']:
                df.loc[small_pbt_mask, col] = (
                    df.loc[small_pbt_mask, col] * df.loc[small_pbt_mask, 'Scale_Factor']
                )
            
            # Apply scaling to sub-scores
            for col in ['NII_Sub_Score', 'Fee_Sub_Score', 'OPEX_Sub_Score', 'Provision_Sub_Score',
                       'Loan_Growth_Score', 'NIM_Change_Score']:
                df.loc[small_pbt_mask, col] = (
                    df.loc[small_pbt_mask, col] * df.loc[small_pbt_mask, 'Scale_Factor']
                )
            
            # Recalculate total after scaling
            df['Total_Score'] = df['Top_Line_Score'] + df['Cost_Cutting_Score'] + df['Non_Recurring_Score']
            
            # Clean up temporary columns
            df = df.drop(['Target_Total', 'Scale_Factor'], axis=1, errors='ignore')
    
    # Round scores for readability
    score_columns = ['Top_Line_Score', 'Cost_Cutting_Score', 'Non_Recurring_Score', 'Total_Score',
                    'NII_Sub_Score', 'Fee_Sub_Score', 'OPEX_Sub_Score', 'Provision_Sub_Score',
                    'Loan_Growth_Score', 'NIM_Change_Score']
    for col in score_columns:
        df[col] = df[col].round(1)
    
    # Calculate weighted impacts (no suffix for yearly as it's standalone)
    df = calculate_weighted_impacts(df, '')
    
    return df

def main():
    """
    Main function to process quarterly and yearly data with score drivers
    """
    
    print("Starting Earnings Quality Analysis with Detailed Score Drivers...")
    
    # Process Quarterly Data
    try:
        print("\nProcessing quarterly data...")
        df_quarter = pd.read_csv('Data/dfsectorquarter.csv')
        df_quarter_processed = process_earnings_quality(df_quarter, 'Date_Quarter')
        
        print("  Calculating T12M scores...")
        # Calculate score drivers for quarterly data - T12M (existing)
        df_t12m = calculate_score_drivers_quarterly(df_quarter_processed.copy())
        df_t12m = add_suffix_to_scores(df_t12m, 'T12M')
        df_t12m = calculate_weighted_impacts(df_t12m, 'T12M')
        
        print("  Calculating QoQ scores...")
        # Calculate QoQ scores
        df_qoq = calculate_score_drivers_qoq(df_quarter_processed.copy())
        df_qoq = add_suffix_to_scores(df_qoq, 'QoQ')
        df_qoq = calculate_weighted_impacts(df_qoq, 'QoQ')
        
        print("  Calculating YoY scores...")
        # Calculate YoY scores  
        df_yoy = calculate_score_drivers_yoy(df_quarter_processed.copy())
        df_yoy = add_suffix_to_scores(df_yoy, 'YoY')
        df_yoy = calculate_weighted_impacts(df_yoy, 'YoY')
        
        print("  Merging all comparison types...")
        # Merge all three
        df_quarter_with_scores = merge_all_scores(df_quarter_processed, df_t12m, df_qoq, df_yoy)
        
        # Sort by ticker and date for better readability
        df_quarter_with_scores = df_quarter_with_scores.sort_values(['TICKER', 'Date_Quarter'])
        
        # Save to CSV
        df_quarter_with_scores.to_csv('Data/earnings_quality_quarterly.csv', index=False)
        print(f"Done - Quarterly data processed: {len(df_quarter_with_scores)} records with T12M, QoQ, and YoY scores")
        
        # Display sample with scores
        print("\nSample of quarterly data with detailed score drivers:")
        sample_cols = ['TICKER', 'Date_Quarter', 'Top_Line_Score', 'NII_Sub_Score', 
                      'Fee_Sub_Score', 'Cost_Cutting_Score', 'OPEX_Sub_Score', 'Provision_Sub_Score']
        # Filter out rows without scores (first 4 quarters per ticker)
        sample_data = df_quarter_with_scores[df_quarter_with_scores['Top_Line_Score'].notna()]
        if len(sample_data) > 0:
            print(sample_data[sample_cols].head(10))
        
    except Exception as e:
        print(f"Error processing quarterly data: {e}")
    
    # Process Yearly Data
    try:
        print("\n\nProcessing yearly data...")
        df_year = pd.read_csv('Data/dfsectoryear.csv')
        df_year_processed = process_earnings_quality(df_year, 'Year')
        
        # Calculate score drivers for yearly data
        df_year_with_scores = calculate_score_drivers_yearly(df_year_processed)
        
        # Sort by ticker and year for better readability
        df_year_with_scores = df_year_with_scores.sort_values(['TICKER', 'Year'])
        
        # Save to CSV
        df_year_with_scores.to_csv('Data/earnings_quality_yearly.csv', index=False)
        print(f"Done - Yearly data processed: {len(df_year_with_scores)} records")
        
        # Display sample with scores
        print("\nSample of yearly data with detailed score drivers:")
        sample_cols = ['TICKER', 'Year', 'Top_Line_Score', 'NII_Sub_Score', 
                      'Fee_Sub_Score', 'Cost_Cutting_Score', 'OPEX_Sub_Score', 'Provision_Sub_Score']
        # Filter out rows without scores (first year per ticker)
        sample_data = df_year_with_scores[df_year_with_scores['Top_Line_Score'].notna()]
        if len(sample_data) > 0:
            print(sample_data[sample_cols].head(10))
        
    except Exception as e:
        print(f"Error processing yearly data: {e}")
    
    # Generate summary insights
    print("\n" + "="*60)
    print("DETAILED SCORE DRIVER ANALYSIS SUMMARY")
    print("="*60)
    
    try:
        # Analyze latest year score drivers
        df_year = pd.read_csv('Data/earnings_quality_yearly.csv')
        latest_year = df_year['Year'].max()
        latest_data = df_year[(df_year['Year'] == latest_year) & (df_year['Top_Line_Score'].notna())].copy()
        
        if len(latest_data) > 0:
            print(f"\nScore Driver Averages for {latest_year}:")
            print(f"Top Line Score: {latest_data['Top_Line_Score'].mean():.1f}%")
            print(f"  - NII Sub-score: {latest_data['NII_Sub_Score'].mean():.1f}%")
            print(f"  - Fee Sub-score: {latest_data['Fee_Sub_Score'].mean():.1f}%")
            print(f"Cost Cutting Score: {latest_data['Cost_Cutting_Score'].mean():.1f}%")
            print(f"  - OPEX Sub-score: {latest_data['OPEX_Sub_Score'].mean():.1f}%")
            print(f"  - Provision Sub-score: {latest_data['Provision_Sub_Score'].mean():.1f}%")
            print(f"Non-Recurring Score: {latest_data['Non_Recurring_Score'].mean():.1f}%")
            
            # Identify banks with best NII-driven growth
            print(f"\n\nTop 5 Banks with NII-Driven Growth ({latest_year}):")
            top_nii = latest_data.nlargest(5, 'NII_Sub_Score')[
                ['TICKER', 'Type', 'NII_Sub_Score', 'Fee_Sub_Score', 'Total_Score']
            ]
            print(top_nii.to_string(index=False))
        
    except Exception as e:
        print(f"Error generating summary: {e}")
    
    print("\nAnalysis complete! Check Data folder for CSV files with full results and detailed sub-scores.")

if __name__ == "__main__":
    main()
