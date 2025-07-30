import pandas as pd
import os
import glob

def save_current_progress():
    """Save any current progress from temporary files to the main comments file"""
    
    print("🛑 Stopping bulk generation and saving progress...")
    
    # Check for temporary files
    temp_files = glob.glob('Data/banking_comments_temp_*.xlsx')
    print(f"Found {len(temp_files)} temporary files")
    
    # Load existing comments file if it exists
    comments_file = 'Data/banking_comments.xlsx'
    if os.path.exists(comments_file):
        existing_comments = pd.read_excel(comments_file)
        print(f"Existing comments file has {len(existing_comments)} entries")
    else:
        existing_comments = pd.DataFrame(columns=['TICKER', 'SECTOR', 'QUARTER', 'COMMENT', 'GENERATED_DATE'])
        print("No existing comments file found")
    
    all_comments = []
    
    # Add existing comments
    if not existing_comments.empty:
        for _, row in existing_comments.iterrows():
            all_comments.append({
                'TICKER': row['TICKER'],
                'SECTOR': row['SECTOR'],
                'QUARTER': row['QUARTER'],
                'COMMENT': row['COMMENT'],
                'GENERATED_DATE': row['GENERATED_DATE']
            })
    
    # Process temporary files
    new_comments = 0
    for temp_file in temp_files:
        print(f"Processing {temp_file}...")
        try:
            temp_df = pd.read_excel(temp_file)
            for _, row in temp_df.iterrows():
                # Check if this comment already exists
                exists = any(
                    existing['TICKER'] == row['TICKER'] and existing['QUARTER'] == row['QUARTER']
                    for existing in all_comments
                )
                
                if not exists:
                    all_comments.append({
                        'TICKER': row['TICKER'],
                        'SECTOR': row['SECTOR'],
                        'QUARTER': row['QUARTER'],
                        'COMMENT': row['COMMENT'],
                        'GENERATED_DATE': row['GENERATED_DATE']
                    })
                    new_comments += 1
        except Exception as e:
            print(f"Error processing {temp_file}: {e}")
    
    # Save consolidated comments
    if all_comments:
        final_df = pd.DataFrame(all_comments)
        final_df.to_excel(comments_file, index=False)
        print(f"\n✅ Progress saved successfully!")
        print(f"📊 Total comments: {len(final_df)}")
        print(f"🆕 New comments added: {new_comments}")
        print(f"🏦 Banks covered: {final_df['TICKER'].nunique()}")
        print(f"📅 Quarters covered: {final_df['QUARTER'].nunique()}")
        print(f"💾 Saved to: {comments_file}")
        
        # Show progress by sector
        print(f"\n📈 Comments by sector:")
        sector_counts = final_df['SECTOR'].value_counts()
        for sector, count in sector_counts.items():
            print(f"  {sector}: {count}")
        
        # Show recent comments
        print(f"\n🕒 Most recent comments:")
        final_df['GENERATED_DATE'] = pd.to_datetime(final_df['GENERATED_DATE'])
        recent = final_df.nlargest(5, 'GENERATED_DATE')[['TICKER', 'QUARTER', 'GENERATED_DATE']]
        for _, row in recent.iterrows():
            print(f"  {row['TICKER']} - {row['QUARTER']} ({row['GENERATED_DATE'].strftime('%Y-%m-%d %H:%M')})")
        
        # Clean up temporary files
        cleanup = input("\nDelete temporary files? (y/n): ")
        if cleanup.lower() == 'y':
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                    print(f"Deleted {temp_file}")
                except Exception as e:
                    print(f"Could not delete {temp_file}: {e}")
        
        return final_df
    else:
        print("\n❌ No comments found to save")
        return None

if __name__ == "__main__":
    result = save_current_progress()
    
    if result is not None:
        print(f"\n🎉 All done! Your comments database is ready with {len(result)} entries.")
        print("You can now use the Streamlit app to access cached comments instantly.")
    else:
        print("\n⚠️ No progress to save. Try running the bulk generator first.")
