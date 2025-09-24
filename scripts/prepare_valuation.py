#%%
import pandas as pd
import numpy as np

from utilities.db import get_connection, upsert_dataframe
from utilities.data_catalog import get_table


def load_valuation_data() -> pd.DataFrame:
    with get_connection(db="target") as conn:
        df = pd.read_sql("SELECT * FROM dbo.Valuation", conn)
    rename_map = {
        'P/E': 'PE_RATIO',
        'P/B': 'PX_TO_BOOK_RATIO',
        'P/S': 'PX_TO_SALES_RATIO',
        'EV/EBITDA': 'EV_EBITDA',
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    return df


def load_bank_classification() -> pd.DataFrame:
    query = (
        "SELECT DISTINCT TICKER, BANK_TYPE AS Type "
        "FROM dbo.BankingMetrics "
        "WHERE LEN(TICKER) = 3"
    )
    with get_connection(db="target") as conn:
        df = pd.read_sql(query, conn)
    df['Type'] = df['Type'].fillna('Other')
    return df


#%% Load data
print("Loading data from warehouse...")

valuation_df = load_valuation_data()
print(f"Loaded {len(valuation_df)} rows of valuation data")

bank_type_df = load_bank_classification()
print(f"Loaded {len(bank_type_df)} bank classifications from BankingMetrics")

#%% Clean and filter data
print("\nCleaning valuation data...")

# Filter only banking tickers
valid_tickers = set(bank_type_df['TICKER'].unique())
valuation_banking = valuation_df[valuation_df['TICKER'].isin(valid_tickers)].copy()

print(f"Filtered to {len(valuation_banking)} rows for {valuation_banking['TICKER'].nunique()} banks")

# Convert date to datetime
valuation_banking['TRADE_DATE'] = pd.to_datetime(valuation_banking['TRADE_DATE'])

# Add bank type information
valuation_banking = valuation_banking.merge(
    bank_type_df[['TICKER', 'Type']], 
    on='TICKER', 
    how='left'
)

# Fill missing types with 'Other' for banks not in Bank_Type.xlsx
valuation_banking['Type'] = valuation_banking['Type'].fillna('Other')

#%% Data quality improvements
print("\nApplying data quality improvements...")

# Remove rows where all valuation metrics are null
valuation_cols = ['PE_RATIO', 'PX_TO_BOOK_RATIO']
valuation_banking = valuation_banking.dropna(subset=valuation_cols, how='all')

# Handle outliers and invalid values
# PE Ratio: Remove negative values and cap at 100
valuation_banking.loc[valuation_banking['PE_RATIO'] < 0, 'PE_RATIO'] = np.nan
valuation_banking.loc[valuation_banking['PE_RATIO'] > 100, 'PE_RATIO'] = 100

# PB Ratio: Remove negative values and cap at 10
valuation_banking.loc[valuation_banking['PX_TO_BOOK_RATIO'] < 0, 'PX_TO_BOOK_RATIO'] = np.nan
valuation_banking.loc[valuation_banking['PX_TO_BOOK_RATIO'] > 10, 'PX_TO_BOOK_RATIO'] = 10

print(f"After cleaning: {len(valuation_banking)} rows remain")

#%% Calculate sector-level valuations
print("\nCalculating sector-level valuations...")

# Define function to calculate robust median (ignoring NaN)
def robust_median(series):
    clean_series = series.dropna()
    if len(clean_series) >= 2:  # Require at least 2 data points
        return clean_series.median()
    return np.nan

# Group by date and type to calculate sector medians
sector_valuations = []

for date in valuation_banking['TRADE_DATE'].unique():
    date_data = valuation_banking[valuation_banking['TRADE_DATE'] == date]
    
    # Calculate for each bank type
    for bank_type in ['SOCB', 'Private_1', 'Private_2', 'Private_3']:
        type_data = date_data[date_data['Type'] == bank_type]
        
        if len(type_data) >= 2:  # Need at least 2 banks for median
            sector_row = {
                'TICKER': bank_type,
                'TRADE_DATE': date,
                'Type': bank_type,
                'PE_RATIO': robust_median(type_data['PE_RATIO']),
                'PX_TO_BOOK_RATIO': robust_median(type_data['PX_TO_BOOK_RATIO'])
            }
            sector_valuations.append(sector_row)
    
    # Calculate overall sector (all banks)
    if len(date_data) >= 3:  # Need at least 3 banks for sector median
        sector_row = {
            'TICKER': 'Sector',
            'TRADE_DATE': date,
            'Type': 'Sector',
            'PE_RATIO': robust_median(date_data['PE_RATIO']),
            'PX_TO_BOOK_RATIO': robust_median(date_data['PX_TO_BOOK_RATIO'])
        }
        sector_valuations.append(sector_row)

# Convert to DataFrame
sector_df = pd.DataFrame(sector_valuations)
print(f"Created {len(sector_df)} sector-level valuation rows")

#%% Combine individual and sector data
print("\nCombining individual and sector data...")

# Select columns for final output
output_columns = ['TICKER', 'TRADE_DATE', 'Type', 'PE_RATIO', 'PX_TO_BOOK_RATIO']

# Combine individual banks and sectors
individual_banks = valuation_banking[output_columns].copy()
final_df = pd.concat([individual_banks, sector_df], ignore_index=True)

# Sort by ticker and date
final_df = final_df.sort_values(['TICKER', 'TRADE_DATE'])

#%% Forward-fill missing values for continuity (weekends/holidays)
print("\nForward-filling missing values for continuity...")

# Sort first to ensure proper forward fill
final_df = final_df.sort_values(['TICKER', 'TRADE_DATE'])

# Group by ticker and forward-fill for up to 5 days
for ticker in final_df['TICKER'].unique():
    mask = final_df['TICKER'] == ticker
    for col in valuation_cols:
        final_df.loc[mask, col] = final_df.loc[mask, col].ffill(limit=5)

#%% Save output
valuation_table = get_table('ValuationBanking')
db_final = final_df.rename(columns={'Type': 'BANK_TYPE'})
inserted_rows = upsert_dataframe(
    db_final,
    table=valuation_table.name,
    key_columns=valuation_table.key_columns,
)
print(f"\nLoaded {inserted_rows} valuation rows into {valuation_table.name}")

#%% Summary statistics
print("\n" + "="*50)
print("SUMMARY STATISTICS")
print("="*50)

# Count by type
print("\nRows by Type:")
type_counts = final_df.groupby('Type')['TICKER'].nunique()
for bank_type, count in type_counts.items():
    print(f"  {bank_type}: {count} entities")

# Date range
print(f"\nDate Range: {final_df['TRADE_DATE'].min()} to {final_df['TRADE_DATE'].max()}")

# Valuation ranges
print("\nValuation Metrics (median across all data):")
for col in valuation_cols:
    median_val = final_df[col].median()
    min_val = final_df[col].min()
    max_val = final_df[col].max()
    print(f"  {col}:")
    print(f"    Median: {median_val:.2f}")
    print(f"    Range: {min_val:.2f} - {max_val:.2f}")

# Data completeness
print("\nData Completeness:")
for col in valuation_cols:
    completeness = (final_df[col].notna().sum() / len(final_df)) * 100
    print(f"  {col}: {completeness:.1f}% complete")

print("\n" + "="*50)
print("Processing complete!")
print("="*50)
