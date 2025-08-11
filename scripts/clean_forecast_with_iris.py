#%%
"""
Clean Forecast Data for Banking Sector with IRIS_KEYCODE Matching
This script processes raw forecast data to create a clean dataset
specifically for banking sector with formula mapping from IRIS_KEYCODE.
"""

import pandas as pd
from pathlib import Path
import re

# Get project directories
script_dir = Path(__file__).parent
project_root = script_dir.parent
data_dir = project_root / 'Data'

#%% Load data
print("Loading data files...")

# Load raw forecast data
forecast_df = pd.read_csv(data_dir / 'FORECAST.csv')
print(f"Loaded {len(forecast_df)} rows of forecast data")

# Load IRIS_KEYCODE data
iris_keycode_df = pd.read_csv(data_dir / 'IRIS_KEYCODE.csv')
print(f"Loaded {len(iris_keycode_df)} rows of IRIS_KEYCODE data")

# Load banking tickers from existing data sources
# Get bank list from quarterly data
quarter_df = pd.read_csv(data_dir / 'dfsectorquarter.csv')
all_bank_tickers = quarter_df[quarter_df['TICKER'].str.len() == 3]['TICKER'].unique()
print(f"Found {len(all_bank_tickers)} bank tickers in quarterly data")

# Also load bank types if available
try:
    bank_type_df = pd.read_excel(data_dir / 'Bank_Type.xlsx')
    bank_tickers_from_types = bank_type_df['TICKER'].unique()
    print(f"Found {len(bank_tickers_from_types)} banks in Bank_Type.xlsx")
    
    # Combine all banking tickers
    valid_tickers = set(all_bank_tickers) | set(bank_tickers_from_types)
except:
    print("Bank_Type.xlsx not found or couldn't be read, using quarterly data only")
    valid_tickers = set(all_bank_tickers)

print(f"Total unique banking tickers: {len(valid_tickers)}")

#%% Step 1: Filter forecast data for banking tickers only
print("\nStep 1: Filtering forecast data for banking tickers...")

# Filter forecast data for banking tickers
forecast_banking = forecast_df[forecast_df['TICKER'].isin(valid_tickers)].copy()
print(f"Filtered to {len(forecast_banking)} rows for {forecast_banking['TICKER'].nunique()} banks")

# Show sample of data
print("\nSample of filtered forecast data:")
print(forecast_banking.head())

#%% Step 2: Filter IRIS_KEYCODE for Bank format only
print("\nStep 2: Filtering IRIS_KEYCODE for Bank format...")

# Filter IRIS_KEYCODE for ReportFormat = 'Bank'
iris_bank = iris_keycode_df[iris_keycode_df['ReportFormat'] == 'Bank'].copy()
print(f"Filtered IRIS_KEYCODE to {len(iris_bank)} rows with Bank format")

# Show unique KeyCodes available
print(f"Unique KeyCodes in IRIS Bank format: {iris_bank['KeyCode'].nunique()}")

#%% Step 2.5: Filter dates for current and next year
print("\nStep 2.5: Filtering dates for current and next year...")

# Get the latest year from quarterly data to determine current year
quarter_df = pd.read_csv(data_dir / 'dfsectorquarter.csv')
# Extract year from Date_Quarter column (format: XQyy where yy is 2-digit year)
quarter_df['Year'] = 2000 + quarter_df['Date_Quarter'].str.extract(r'Q(\d+)').astype(int)
current_year = quarter_df['Year'].max()
next_year = current_year + 1

print(f"Current year detected: {current_year}")
print(f"Keeping data for: {current_year} and {next_year}")

# Filter forecast data for current and next year only
forecast_banking = forecast_banking[forecast_banking['DATE'].isin([current_year, next_year])].copy()
print(f"After date filtering: {len(forecast_banking)} rows")

#%% Step 3: Match KeyCode and add Formula column
print("\nStep 3: Matching KeyCode from forecast with IRIS_KEYCODE...")

# Create a mapping dictionary from IRIS_KEYCODE
# KeyCode -> Formula mapping
keycode_to_formula = dict(zip(iris_bank['KeyCode'], iris_bank['Formula']))

# Also create KeyCode -> KeyCodeName mapping for reference
keycode_to_name = dict(zip(iris_bank['KeyCode'], iris_bank['KeyCodeName']))

# Add Formula column to forecast_banking
forecast_banking['Formula'] = forecast_banking['KEYCODE'].map(keycode_to_formula)
forecast_banking['IRIS_KeyCodeName'] = forecast_banking['KEYCODE'].map(keycode_to_name)

# Count matches
matched_count = forecast_banking['Formula'].notna().sum()
total_rows = len(forecast_banking)
match_rate = (matched_count / total_rows * 100) if total_rows > 0 else 0

print(f"Matched {matched_count} out of {total_rows} rows ({match_rate:.1f}%)")

#%% Step 3.5: Filter Formula column for valid formats
print("\nStep 3.5: Filtering Formula column for valid formats...")

def is_valid_formula(formula):
    """
    Check if formula is in valid format:
    - XX.NN format (e.g., IS.5, BS.15, Nt.2)
    - Formula containing XX.NN elements (e.g., IS.5 + IS.6)
    """
    if pd.isna(formula) or formula is None:
        return False
    
    formula_str = str(formula)
    
    # Pattern for XX.NN format (letters followed by dot and numbers)
    code_pattern = r'[A-Za-z]+\.\d+'
    
    # Check if the formula contains at least one valid code pattern
    if re.search(code_pattern, formula_str):
        return True
    
    return False

# Apply the filter
before_filter = len(forecast_banking)
valid_formula_mask = forecast_banking['Formula'].apply(is_valid_formula)

# Count invalid formulas before removing
invalid_formulas = forecast_banking[~valid_formula_mask & forecast_banking['Formula'].notna()]['Formula'].unique()
print(f"Found {len(invalid_formulas)} unique invalid formula values")
if len(invalid_formulas) > 0 and len(invalid_formulas) <= 20:
    print("Invalid formulas being removed:")
    for formula in invalid_formulas[:20]:
        print(f"  - {formula}")

# Set invalid formulas to None
forecast_banking.loc[~valid_formula_mask, 'Formula'] = None

# Count valid formulas
valid_formula_count = forecast_banking['Formula'].notna().sum()
print(f"Valid formulas: {valid_formula_count} out of {before_filter} rows ({valid_formula_count/before_filter*100:.1f}%)")

# Remove rows with blank/empty Formula column
print("\nRemoving rows with blank/empty Formula column...")
before_removal = len(forecast_banking)
forecast_banking = forecast_banking[forecast_banking['Formula'].notna()].copy()
after_removal = len(forecast_banking)
print(f"Removed {before_removal - after_removal} rows with blank/empty formulas")
print(f"Remaining rows: {after_removal}")

# Show unmatched KEYCODEs that were removed
removed_keycodes = forecast_banking[forecast_banking['Formula'].isna()]['KEYCODE'].unique() if len(forecast_banking[forecast_banking['Formula'].isna()]) > 0 else []
if len(removed_keycodes) > 0:
    print(f"\nRemoved KEYCODEs: {len(removed_keycodes)}")
    print("Sample of removed KEYCODEs (first 20):")
    for code in sorted(removed_keycodes)[:20]:
        print(f"  - {code}")

#%% Data quality checks
print("\nPerforming data quality checks...")

# Check for null values in critical columns
null_counts = forecast_banking[['TICKER', 'KEYCODE', 'DATE', 'VALUE']].isnull().sum()
print("\nNull values in critical columns:")
for col, count in null_counts.items():
    print(f"  {col}: {count}")

# Check date range
if 'DATE' in forecast_banking.columns:
    date_range = forecast_banking['DATE'].unique()
    print(f"\nDate range in data: {sorted(date_range)}")

#%% Step 4: Save output
print("\nStep 4: Saving output to FORECAST_bank.csv...")

# Define output columns
output_columns = [
    'KEYCODE', 'KEYCODENAME', 'ORGANCODE', 'TICKER', 'DATE', 
    'VALUE', 'RATING', 'FORECASTDATE', 'Formula', 'IRIS_KeyCodeName'
]

# Select only columns that exist
available_columns = [col for col in output_columns if col in forecast_banking.columns]
final_df = forecast_banking[available_columns].copy()

# Sort by ticker, date, and keycode for better organization
sort_columns = []
if 'TICKER' in final_df.columns:
    sort_columns.append('TICKER')
if 'DATE' in final_df.columns:
    sort_columns.append('DATE')
if 'KEYCODE' in final_df.columns:
    sort_columns.append('KEYCODE')

if sort_columns:
    final_df = final_df.sort_values(sort_columns)

# Save to CSV
output_path = data_dir / 'FORECAST_bank.csv'
final_df.to_csv(output_path, index=False)
print(f"Saved to {output_path}")

#%% Summary statistics
print("\n" + "="*60)
print("SUMMARY STATISTICS")
print("="*60)

# Basic statistics
print(f"\nTotal rows in output: {len(final_df):,}")
print(f"Unique banks: {final_df['TICKER'].nunique()}")
print(f"Unique KEYCODEs: {final_df['KEYCODE'].nunique()}")

# Banks list
print(f"\nBanks included:")
banks_list = sorted(final_df['TICKER'].unique())
for i in range(0, len(banks_list), 10):
    print(f"  {', '.join(banks_list[i:i+10])}")

# Date coverage
if 'DATE' in final_df.columns:
    print(f"\nDate coverage:")
    date_counts = final_df['DATE'].value_counts().sort_index()
    for date, count in date_counts.items():
        print(f"  {date}: {count:,} rows")

# Formula coverage
formula_coverage = final_df['Formula'].notna().sum()
formula_percentage = (formula_coverage / len(final_df) * 100) if len(final_df) > 0 else 0
print(f"\nFormula matching:")
print(f"  Rows with Formula: {formula_coverage:,} ({formula_percentage:.1f}%)")
print(f"  Rows without Formula: {len(final_df) - formula_coverage:,} ({100 - formula_percentage:.1f}%)")

# Top KEYCODEs
print(f"\nTop 10 KEYCODEs by frequency:")
top_keycodes = final_df['KEYCODE'].value_counts().head(10)
for code, count in top_keycodes.items():
    name = final_df[final_df['KEYCODE'] == code]['KEYCODENAME'].iloc[0] if len(final_df[final_df['KEYCODE'] == code]) > 0 else 'N/A'
    has_formula = "✓" if code in keycode_to_formula and keycode_to_formula[code] is not None else "✗"
    print(f"  {code}: {count:,} rows - {name} [Formula: {has_formula}]")

print("\n" + "="*60)
print("Processing complete!")
print("="*60)