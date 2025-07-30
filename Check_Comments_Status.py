import pandas as pd
import os

try:
    comments_file = 'Data/banking_comments.xlsx'
    
    if os.path.exists(comments_file):
        df = pd.read_excel(comments_file)
        
        print("📊 Current Comments Database Status:")
        print(f"Total comments: {len(df)}")
        print(f"Unique banks: {df['TICKER'].nunique()}")
        print(f"Unique quarters: {df['QUARTER'].nunique()}")
        
        if len(df) > 0:
            print(f"\n🏦 Banks with comments:")
            bank_counts = df['TICKER'].value_counts()
            for bank, count in bank_counts.head(10).items():
                print(f"  {bank}: {count} quarters")
            
            print(f"\n📅 Quarters covered:")
            quarter_counts = df['QUARTER'].value_counts()
            sorted_quarters = sorted(quarter_counts.index)
            print(f"  Range: {sorted_quarters[0]} to {sorted_quarters[-1]}")
            print(f"  Total quarters: {len(sorted_quarters)}")
            
            print(f"\n🏢 Comments by sector:")
            sector_counts = df['SECTOR'].value_counts()
            for sector, count in sector_counts.items():
                print(f"  {sector}: {count}")
            
            # Show most recent
            print(f"\n🕒 Most recent comments:")
            df['GENERATED_DATE'] = pd.to_datetime(df['GENERATED_DATE'])
            recent = df.nlargest(5, 'GENERATED_DATE')[['TICKER', 'QUARTER', 'GENERATED_DATE']]
            for _, row in recent.iterrows():
                print(f"  {row['TICKER']} - {row['QUARTER']} ({row['GENERATED_DATE'].strftime('%Y-%m-%d %H:%M')})")
            
            print(f"\n✅ Comments database is ready for use!")
        else:
            print("\n⚠️ Comments file exists but is empty")
    else:
        print("❌ No comments file found")
        
except Exception as e:
    print(f"Error checking comments: {e}")
    import traceback
    traceback.print_exc()
