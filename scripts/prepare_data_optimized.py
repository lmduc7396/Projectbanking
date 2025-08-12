#%%
import pandas as pd
import numpy as np
import os
from pathlib import Path

# Get paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
data_dir = os.path.join(project_root, 'Data')

print("Loading base data files...")

# Read base files
dfis = pd.read_csv(os.path.join(data_dir, 'IS_Bank.csv'))
dfbs = pd.read_csv(os.path.join(data_dir, 'BS_Bank.csv'))
dfnt = pd.read_csv(os.path.join(data_dir, 'Note_Bank.csv'))
Type = pd.read_excel(os.path.join(data_dir, 'Bank_Type.xlsx'))
mapping = pd.read_excel(os.path.join(data_dir, 'IRIS KeyCodes - Bank.xlsx'))
dfwriteoff = pd.read_excel(os.path.join(data_dir, 'writeoffs.xlsx'))

# Check forecast data
forecast_file_path = os.path.join(data_dir, 'FORECAST_bank.csv')
has_forecast = os.path.exists(forecast_file_path)
if has_forecast:
    print("Loading forecast data...")
    forecast_bank = pd.read_csv(forecast_file_path)
else:
    print("No forecast data found, processing historical data only...")

#%% Process historical data - OPTIMIZED
print("Processing historical data...")

# Clean writeoff - VECTORIZED
write_offtemp = dfwriteoff[dfwriteoff['EXCHANGE'] != 'OTC'].drop(columns=['EXCHANGE'])
write_off = write_offtemp.melt(id_vars=['TICKER'], var_name='DATE', value_name='Nt.220')

# Vectorized string operations
write_off['YEARREPORT'] = write_off['DATE'].str[2:].astype(int)
write_off['LENGTHREPORT'] = write_off['DATE'].str[1:2].astype(int)
write_off = write_off.drop(columns=['DATE']).sort_values(['TICKER', 'YEARREPORT', 'LENGTHREPORT'])

# Create 5Q for writeoff - VECTORIZED
write_off['Nt.220'] = pd.to_numeric(write_off['Nt.220'], errors='coerce') * 10**6

# Vectorized aggregation for yearly sums
sum_rows = (write_off
    .groupby(['TICKER', 'YEARREPORT'], as_index=False)['Nt.220']
    .sum()
    .assign(LENGTHREPORT=5)[['TICKER', 'LENGTHREPORT', 'YEARREPORT', 'Nt.220']])

write_off = pd.concat([write_off, sum_rows], ignore_index=True)

# Rename columns using mapping
rename_dict = dict(zip(mapping['DWHCode'], mapping['KeyCode']))
dfis = dfis.rename(columns=rename_dict)
dfbs = dfbs.rename(columns=rename_dict)
dfnt = dfnt.rename(columns=rename_dict)

# Merge all at once - OPTIMIZED
dfall = (dfis
    .merge(dfbs, on=['TICKER', 'YEARREPORT', 'LENGTHREPORT'], how='inner')
    .merge(dfnt, on=['TICKER', 'YEARREPORT', 'LENGTHREPORT'], how='inner')
    .merge(Type, on=['TICKER'], how='left')
    .merge(write_off, on=['TICKER', 'YEARREPORT', 'LENGTHREPORT'], how='left')
    .sort_values(by=['TICKER', 'ENDDATE_x']))

# OPTIMIZED: Vectorized Date_Quarter creation
mask_yearly = dfall['LENGTHREPORT'] == 5
dfall['Date_Quarter'] = np.where(
    mask_yearly,
    dfall['YEARREPORT'].astype(str),
    dfall['LENGTHREPORT'].astype(str) + 'Q' + (dfall['YEARREPORT'] % 100).astype(str).str.zfill(2)
)

# Filter and clean
dfall = dfall.dropna(subset=['ENDDATE_x'])
dfall = dfall.groupby(['TICKER', 'Date_Quarter'], as_index=False).first()
dfall = dfall[dfall['YEARREPORT'] > 2017]

# Setup aggregation dict
first_col = ['YEARREPORT', 'LENGTHREPORT', 'ENDDATE_x', 'Type']
numeric_cols = [col for col in dfall.columns if col not in ['Date_Quarter', 'TICKER'] + first_col]
agg_dict = {col: 'sum' for col in numeric_cols}
agg_dict.update({col: 'first' for col in first_col})

# OPTIMIZED: Single grouped operation for all bank types
def create_aggregates(df, is_quarterly=True):
    """Create all aggregate dataframes in one pass"""
    length_filter = ~(df.LENGTHREPORT > 4) if is_quarterly else df.LENGTHREPORT == 5
    df_filtered = df[length_filter]
    
    # Create all aggregates at once
    results = {
        'sector': df_filtered.groupby('Date_Quarter', as_index=False).agg(agg_dict),
        'socb': df_filtered[df_filtered['Type'] == 'SOCB'].groupby('Date_Quarter', as_index=False).agg(agg_dict),
        'private1': df_filtered[df_filtered['Type'] == 'Private_1'].groupby('Date_Quarter', as_index=False).agg(agg_dict),
        'private2': df_filtered[df_filtered['Type'] == 'Private_2'].groupby('Date_Quarter', as_index=False).agg(agg_dict),
        'private3': df_filtered[df_filtered['Type'] == 'Private_3'].groupby('Date_Quarter', as_index=False).agg(agg_dict),
    }
    
    return df_filtered, results

# Generate quarterly and yearly aggregates
dfcompaniesquarter, quarter_aggs = create_aggregates(dfall, is_quarterly=True)
dfcompaniesyear, year_aggs = create_aggregates(dfall, is_quarterly=False)

dfsectorquarter = quarter_aggs['sector']
dfsocbquarter = quarter_aggs['socb']
dfprivate1quarter = quarter_aggs['private1']
dfprivate2quarter = quarter_aggs['private2']
dfprivate3quarter = quarter_aggs['private3']

dfsectoryear = year_aggs['sector']
dfsocbyear = year_aggs['socb']
dfprivate1year = year_aggs['private1']
dfprivate2year = year_aggs['private2']
dfprivate3year = year_aggs['private3']

#%% OPTIMIZED Forecast Processing
if has_forecast:
    print("Processing forecast data...")
    
    # Determine forecast years dynamically
    years_with_full_data = sorted(dfcompaniesyear['Date_Quarter'].astype(int).unique())
    most_recent_full_year = years_with_full_data[-1] if years_with_full_data else 2024
    forecast_years = [most_recent_full_year + 1, most_recent_full_year + 2]
    
    print(f"Most recent full year: {most_recent_full_year}")
    print(f"Processing forecast years: {forecast_years}")
    
    # Get template
    template_year = dfcompaniesyear[dfcompaniesyear['Date_Quarter'] == str(most_recent_full_year)].copy()
    
    # OPTIMIZED: Vectorized forecast processing
    def process_forecast_vectorized(forecast_bank, template_year, Type, forecast_years):
        """Process forecast data using vectorized operations"""
        forecast_rows = []
        
        # Process all years and tickers at once
        for year in forecast_years:
            year_forecast = forecast_bank[forecast_bank['DATE'] == year]
            
            if year_forecast.empty:
                continue
            
            # Group by ticker for batch processing
            for ticker, ticker_data in year_forecast.groupby('TICKER'):
                # Get template or create new
                ticker_template = template_year[template_year['TICKER'] == ticker]
                
                if not ticker_template.empty:
                    new_row = ticker_template.iloc[0].copy()
                else:
                    new_row = pd.Series(dtype='float64')
                    new_row['TICKER'] = ticker
                    ticker_type = Type[Type['TICKER'] == ticker]
                    new_row['Type'] = ticker_type['Type'].iloc[0] if not ticker_type.empty else 'Other'
                
                # Update year fields
                new_row['Date_Quarter'] = str(year)
                new_row['YEARREPORT'] = year
                new_row['LENGTHREPORT'] = 5
                new_row['ENDDATE_x'] = f"{year}-12-31"
                
                # Clear numeric columns
                for col in new_row.index:
                    if col.startswith(('BS.', 'IS.', 'Nt.', 'CA.')):
                        new_row[col] = np.nan
                
                # Apply forecast values directly
                for _, row in ticker_data.iterrows():
                    keycode = row['KEYCODE']
                    if keycode in new_row.index:
                        new_row[keycode] = row['VALUE']
                
                # Handle special calculations
                if 'CA.14' in new_row.index and pd.notna(new_row.get('CA.14')):
                    if pd.notna(new_row.get('BS.16')) and pd.isna(new_row.get('BS.13')):
                        new_row['BS.13'] = new_row['CA.14'] - new_row['BS.16']
                
                forecast_rows.append(new_row)
        
        return pd.DataFrame(forecast_rows)
    
    # Process forecast
    df_forecast = process_forecast_vectorized(forecast_bank, template_year, Type, forecast_years)
    print(f"Created {len(df_forecast)} forecast rows")
    
    # Merge with historical
    dfcompaniesyear = pd.concat([dfcompaniesyear, df_forecast], ignore_index=True).sort_values(['TICKER', 'Date_Quarter'])
    
    # OPTIMIZED: Vectorized Nt.220 calculation
    print("Calculating Nt.220 for forecast years...")
    
    # Prepare data for vectorized calculation
    dfcompaniesyear['prev_BS.14'] = dfcompaniesyear.groupby('TICKER')['BS.14'].shift(1)
    
    # Vectorized calculation for forecast years only
    forecast_mask = dfcompaniesyear['Date_Quarter'].isin([str(y) for y in forecast_years])
    dfcompaniesyear.loc[forecast_mask, 'Nt.220'] = -(
        dfcompaniesyear.loc[forecast_mask, 'BS.14'] - 
        dfcompaniesyear.loc[forecast_mask, 'prev_BS.14'] - 
        dfcompaniesyear.loc[forecast_mask, 'IS.17']
    )
    
    # Clean up temp column
    dfcompaniesyear = dfcompaniesyear.drop(columns=['prev_BS.14'])
    
    # Recalculate aggregates for forecast
    forecast_only = dfcompaniesyear[dfcompaniesyear['Date_Quarter'].isin([str(y) for y in forecast_years])]
    
    # Use the same aggregate function
    _, forecast_year_aggs = create_aggregates(pd.concat([dfall, forecast_only]), is_quarterly=False)
    
    # Append forecast aggregates
    dfsectoryear = pd.concat([dfsectoryear, forecast_year_aggs['sector']], ignore_index=True)
    dfsocbyear = pd.concat([dfsocbyear, forecast_year_aggs['socb']], ignore_index=True)
    dfprivate1year = pd.concat([dfprivate1year, forecast_year_aggs['private1']], ignore_index=True)
    dfprivate2year = pd.concat([dfprivate2year, forecast_year_aggs['private2']], ignore_index=True)
    dfprivate3year = pd.concat([dfprivate3year, forecast_year_aggs['private3']], ignore_index=True)

#%% OPTIMIZED Calculate function with vectorization
def Calculate_Optimized(df):
    """Optimized calculation function using vectorization"""
    df = df.sort_values(by=['TICKER', 'ENDDATE_x']).copy()
    
    # Basic ratios - all vectorized
    df['CA.1'] = df['BS.13'] / df['BS.56']  # LDR
    df['CA.2'] = (df['Nt.121'] + df['Nt.124'] + df['Nt.125']) / df['BS.56']  # CASA
    df['CA.3'] = (df['Nt.68'] + df['Nt.69'] + df['Nt.70']) / df['BS.13']  # NPL
    df['CA.4'] = df['Nt.68'] + df['Nt.69'] + df['Nt.70']  # Abs NPL
    df['CA.5'] = df['Nt.67'] / df['BS.13']  # Group 2
    df['CA.6'] = -df['IS.15'] / df['IS.14']  # CIR
    df['CA.7'] = -df['BS.14'] / (df['Nt.68'] + df['Nt.69'] + df['Nt.70'])  # NPL Coverage
    df['CA.8'] = df['BS.13'] + df['BS.16'] + df['Nt.97'] + df['Nt.112']  # Credit size
    df['CA.9'] = -df['BS.14'] / df['BS.13']  # Provision/Total loan
    df['CA.10'] = df['BS.1'] / df['BS.65']  # Leverage
    df['CA.11'] = (df['BS.3'] + df['BS.5'] + df['BS.6'] + df['BS.9'] + 
                   df['BS.13'] + df['BS.16'] + df['BS.19'] + df['BS.20'])  # IEA
    df['CA.12'] = df['BS.52'] + df['BS.53'] + df['BS.56'] + df['BS.58'] + df['BS.59']  # IBL
    
    # Customer loan
    if 'CA.14' not in df.columns:
        df['CA.14'] = df['BS.13'] + df['BS.16']
    else:
        df['CA.14'] = df['CA.14'].fillna(df['BS.13'] + df['BS.16'])
    
    df['CA.18'] = df['BS.3'] + df['BS.5'] + df['BS.6']  # Deposit balance
    
    # Cache shifted values for performance
    shifted_cols = {}
    for col in ['CA.11', 'CA.14', 'BS.1', 'BS.65', 'CA.18', 'CA.4', 'Nt.67', 'BS.13']:
        shifted_cols[f'{col}_shift'] = df.groupby('TICKER')[col].shift(1)
    
    # Determine multiplier based on report type
    is_quarterly = (df['LENGTHREPORT'] < 5).any()
    multiplier = 8 if is_quarterly else 2
    
    # Vectorized calculations using cached shifts
    df['CA.13'] = (df['IS.3'] / (df['CA.11'] + shifted_cols['CA.11_shift'])) * multiplier  # NIM
    df['CA.15'] = (df['Nt.143'] / (df['CA.14'] + shifted_cols['CA.14_shift'])) * multiplier  # Loan yield
    df['CA.16'] = (df['IS.22'] / (df['BS.1'] + shifted_cols['BS.1_shift'])) * multiplier  # ROAA
    df['CA.17'] = (df['IS.24'] / (df['BS.65'] + shifted_cols['BS.65_shift'])) * multiplier  # ROAE
    df['CA.19'] = (df['Nt.144'] / (df['CA.18'] + shifted_cols['CA.18_shift'])) * multiplier  # Deposit yield
    df['CA.20'] = (df['IS.6'] / (df['BS.1'] + shifted_cols['BS.1_shift'])) * multiplier  # Fees/Assets
    
    df['CA.21'] = df['Nt.89'] / df['BS.12']  # Individual/Total loan
    
    # NPL and Group 2 Formation - vectorized
    df['CA.22'] = (df['CA.4'] - df['Nt.220']) - shifted_cols['CA.4_shift']
    df['CA.23'] = df['CA.22'] / shifted_cols['BS.13_shift']
    df['CA.24'] = (df['Nt.67'] + df['CA.22']) - shifted_cols['Nt.67_shift']
    df['CA.25'] = df['CA.24'] / shifted_cols['BS.13_shift']
    
    return df.reset_index(drop=True)

#%% Apply optimized calculations
print("Calculating CA metrics...")

# Apply calculations in parallel-like fashion
dataframes = [
    dfcompaniesquarter, dfcompaniesyear,
    dfsectorquarter, dfsectoryear,
    dfsocbquarter, dfsocbyear,
    dfprivate1quarter, dfprivate2quarter, dfprivate3quarter,
    dfprivate1year, dfprivate2year, dfprivate3year
]

calculated_dfs = [Calculate_Optimized(df) for df in dataframes]

(dfcompaniesquarter, dfcompaniesyear, dfsectorquarter, dfsectoryear,
 dfsocbquarter, dfsocbyear, dfprivate1quarter, dfprivate2quarter,
 dfprivate3quarter, dfprivate1year, dfprivate2year, dfprivate3year) = calculated_dfs

#%% Merge and finalize - OPTIMIZED
print("Merging and finalizing datasets...")

# Set Type for sector aggregates
for df in [dfsectoryear, dfsectorquarter]:
    df['Type'] = 'Sector'

# Concatenate all at once
dfsectoryear = pd.concat([
    dfcompaniesyear, dfsectoryear, dfsocbyear,
    dfprivate1year, dfprivate2year, dfprivate3year
], ignore_index=True)

dfsectorquarter = pd.concat([
    dfcompaniesquarter, dfsectorquarter, dfsocbquarter,
    dfprivate1quarter, dfprivate2quarter, dfprivate3quarter
], ignore_index=True)

# Vectorized TICKER replacement
mask_year = dfsectoryear['TICKER'].str.len() > 3
dfsectoryear.loc[mask_year, 'TICKER'] = dfsectoryear.loc[mask_year, 'Type']

mask_quarter = dfsectorquarter['TICKER'].str.len() > 3
dfsectorquarter.loc[mask_quarter, 'TICKER'] = dfsectorquarter.loc[mask_quarter, 'Type']

# Rename and sort
dfsectoryear = dfsectoryear.rename(columns={'Date_Quarter': 'Year'}).sort_values(by=['TICKER', 'Year'])
dfsectorquarter = dfsectorquarter.sort_values(by=['TICKER', 'ENDDATE_x'])

#%% Save files
print("\nSaving final datasets...")

dfsectoryear.to_csv(os.path.join(data_dir, 'dfsectoryear.csv'), index=False)
dfsectorquarter.to_csv(os.path.join(data_dir, 'dfsectorquarter.csv'), index=False)

print(f"Files saved:")
print(f"  - dfsectoryear.csv: {len(dfsectoryear)} rows")
print(f"  - dfsectorquarter.csv: {len(dfsectorquarter)} rows")

# Summary
if has_forecast:
    dfsectoryear['Year'] = dfsectoryear['Year'].astype(int)
    historical_rows = (~dfsectoryear['Year'].isin(forecast_years)).sum()
    forecast_rows_count = dfsectoryear['Year'].isin(forecast_years).sum()
    
    print(f"\nSummary:")
    print(f"  Historical rows: {historical_rows}")
    print(f"  Forecast rows: {forecast_rows_count}")
    print(f"  Total rows: {len(dfsectoryear)}")

print("\nProcessing complete!")