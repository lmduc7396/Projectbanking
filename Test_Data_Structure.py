import pandas as pd
import os
from utilities import quarter_to_numeric

print("Testing data structure for bulk comment generation...")

try:
    # Load the data files
    df_quarter = pd.read_csv('Data/dfsectorquarter.csv')
    print(f"✓ Loaded dfsectorquarter.csv: {df_quarter.shape}")
    
    # Check Bank_Type.xlsx
    try:
        bank_type = pd.read_excel('Data/Bank_Type.xlsx')
        print(f"✓ Loaded Bank_Type.xlsx: {bank_type.shape}")
        print("Columns:", bank_type.columns.tolist())
        print("First few rows:")
        print(bank_type.head())
    except Exception as e:
        print(f"⚠️ Could not load Bank_Type.xlsx: {e}")
        print("Will use sector info from dfsectorquarter.csv instead")
    
    # Analyze bank data
    banks = df_quarter[df_quarter['TICKER'].str.len() == 3]['TICKER'].unique()
    print(f"Found {len(banks)} individual banks")
    
    # Check sector mappings
    bank_sectors = df_quarter[df_quarter['TICKER'].str.len() == 3][['TICKER', 'Type']].drop_duplicates()
    print("Bank-Sector mappings sample:")
    print(bank_sectors.head(10))
    
    # Check quarters
    quarters = df_quarter['Date_Quarter'].unique()
    print(f"Found {len(quarters)} quarters")
    
    # Filter quarters from 2021
    quarters_2021_plus = [q for q in quarters if quarter_to_numeric(q) >= 20211]
    quarters_2021_plus.sort(key=quarter_to_numeric)
    print(f"Quarters from 2021 onwards: {len(quarters_2021_plus)}")
    print("Sample quarters:", quarters_2021_plus[:5], "...", quarters_2021_plus[-5:])
    
    total_combinations = len(banks) * len(quarters_2021_plus)
    print(f"Total bank-quarter combinations to process: {total_combinations:,}")
    
    # Estimate API cost
    estimated_cost = total_combinations * 0.06  # Rough estimate of $0.06 per analysis
    print(f"Estimated API cost: ${estimated_cost:.2f}")
    
    print("\n✅ Data structure analysis complete!")
    print("You can now run the bulk generation script safely.")
    
except Exception as e:
    print(f"❌ Error analyzing data: {e}")
