import pandas as pd
import os
from utilities import quarter_to_numeric

try:
    print("=== Data Structure Analysis ===")
    
    # Load the main data
    df_quarter = pd.read_csv('Data/dfsectorquarter.csv')
    print(f"✓ Loaded dfsectorquarter.csv: {df_quarter.shape}")
    
    # Check Bank_Type.xlsx structure
    try:
        bank_type = pd.read_excel('Data/Bank_Type.xlsx')
        print(f"✓ Loaded Bank_Type.xlsx: {bank_type.shape}")
        print("Columns:", bank_type.columns.tolist())
        print("Sample data:")
        print(bank_type.head(3))
        print()
    except Exception as e:
        print(f"⚠️ Could not load Bank_Type.xlsx: {e}")
        print("Will use data from dfsectorquarter.csv instead")
        print()
    
    # Analyze individual banks
    individual_banks = df_quarter[df_quarter['TICKER'].str.len() == 3]
    print(f"Individual banks found: {individual_banks['TICKER'].nunique()}")
    
    # Show bank-sector mapping sample
    bank_sector_sample = individual_banks[['TICKER', 'Type']].drop_duplicates().head(10)
    print("Bank-Sector mapping sample:")
    print(bank_sector_sample)
    print()
    
    # Analyze quarters
    quarters = sorted(df_quarter['Date_Quarter'].unique())
    print(f"All quarters: {len(quarters)}")
    print("Sample quarters:", quarters[:5], "...", quarters[-5:])
    
    # Filter 2023+ quarters
    quarters_2023_plus = [q for q in quarters if quarter_to_numeric(q) >= 20231]
    print(f"Quarters from 2023 onwards: {len(quarters_2023_plus)}")
    print("2023+ quarters:", quarters_2023_plus[:3], "...", quarters_2023_plus[-3:])
    
    # Calculate total combinations
    total_banks = individual_banks['TICKER'].nunique()
    total_combinations = total_banks * len(quarters_2023_plus)
    estimated_cost = total_combinations * 0.06  # Rough estimate
    
    print(f"\n=== Generation Estimates ===")
    print(f"Banks to process: {total_banks}")
    print(f"Quarters to process: {len(quarters_2023_plus)}")
    print(f"Total combinations: {total_combinations:,}")
    print(f"Estimated API cost: ${estimated_cost:.2f}")
    
    # Check if comments file exists
    comments_file = 'Data/banking_comments.xlsx'
    if os.path.exists(comments_file):
        existing = pd.read_excel(comments_file)
        print(f"\n=== Existing Cache ===")
        print(f"Existing comments: {len(existing)}")
        print(f"Progress: {len(existing)/total_combinations*100:.1f}%")
    else:
        print(f"\n=== No existing cache found ===")
    
    print("\n✅ Analysis complete! Ready for bulk generation.")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
