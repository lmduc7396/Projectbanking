import pandas as pd
import os

# Change to the correct directory
os.chdir(r"C:\Users\ducle\OneDrive\Work-related\VS - Code project")

try:
    # Read the comments file
    df = pd.read_excel('Data/banking_comments.xlsx')
    
    print("=" * 50)
    print("BANKING COMMENTS DATABASE STATUS")
    print("=" * 50)
    print(f"Total comments saved: {len(df)}")
    print(f"Unique banks: {df['TICKER'].nunique()}")
    print(f"Unique quarters: {df['QUARTER'].nunique()}")
    print(f"Date range: {df['QUARTER'].min()} to {df['QUARTER'].max()}")
    
    print("\nBank coverage:")
    for bank in sorted(df['TICKER'].unique()):
        count = len(df[df['TICKER'] == bank])
        print(f"  {bank}: {count} quarters")
    
    print("\nQuarter coverage:")
    for quarter in sorted(df['QUARTER'].unique()):
        count = len(df[df['QUARTER'] == quarter])
        print(f"  {quarter}: {count} banks")
    
    # Check if there are any temp files
    temp_files = [f for f in os.listdir('.') if f.startswith('temp_banking_comments_')]
    if temp_files:
        print(f"\nFound {len(temp_files)} temporary files - these may need to be consolidated")
    else:
        print("\nNo temporary files found")
        
except Exception as e:
    print(f"Error reading comments file: {e}")
    
print("\nProcess stopped successfully!")
