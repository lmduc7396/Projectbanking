import pandas as pd
import os
import glob
from datetime import datetime

def emergency_save_progress():
    """Emergency function to save current progress and consolidate temp files"""
    
    print("EMERGENCY SAVE PROCEDURE")
    print("=" * 50)
    
    # Change to project directory
    os.chdir(r"C:\Users\ducle\OneDrive\Work-related\VS - Code project")
    
    # Find all temporary files
    temp_files = glob.glob("*temp*.xlsx") + glob.glob("Data/*temp*.xlsx")
    
    if temp_files:
        print(f"Found {len(temp_files)} temporary files:")
        for file in temp_files:
            print(f"  - {file}")
    else:
        print("No temporary files found")
    
    # Load existing comments if available
    comments_file = 'Data/banking_comments.xlsx'
    all_comments = []
    
    if os.path.exists(comments_file):
        try:
            existing_df = pd.read_excel(comments_file)
            all_comments.extend(existing_df.to_dict('records'))
            print(f"Loaded {len(existing_df)} existing comments from main file")
        except Exception as e:
            print(f"Error loading main file: {e}")
    
    # Load all temporary files
    temp_comments = []
    for temp_file in temp_files:
        try:
            temp_df = pd.read_excel(temp_file)
            temp_comments.extend(temp_df.to_dict('records'))
            print(f"Loaded {len(temp_df)} comments from {temp_file}")
        except Exception as e:
            print(f"Error loading {temp_file}: {e}")
    
    # Combine and deduplicate
    all_comments.extend(temp_comments)
    
    if all_comments:
        # Convert to DataFrame and remove duplicates
        final_df = pd.DataFrame(all_comments)
        
        # Remove duplicates based on TICKER and QUARTER
        before_dedup = len(final_df)
        final_df = final_df.drop_duplicates(subset=['TICKER', 'QUARTER'], keep='last')
        after_dedup = len(final_df)
        
        print(f"Removed {before_dedup - after_dedup} duplicate entries")
        
        # Save consolidated file
        backup_file = f"Data/banking_comments_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        final_df.to_excel(backup_file, index=False)
        final_df.to_excel(comments_file, index=False)
        
        print(f"Saved {len(final_df)} total comments to:")
        print(f"  Main file: {comments_file}")
        print(f"  Backup: {backup_file}")
        
        # Show progress summary
        print(f"\nProgress Summary:")
        print(f"  Total comments: {len(final_df)}")
        print(f"  Unique banks: {final_df['TICKER'].nunique()}")
        print(f"  Unique quarters: {final_df['QUARTER'].nunique()}")
        
        print(f"\nComments by sector:")
        sector_counts = final_df['SECTOR'].value_counts()
        for sector, count in sector_counts.items():
            print(f"  {sector}: {count}")
        
        # Clean up temporary files
        cleanup_response = input("\nDelete temporary files? (y/n): ")
        if cleanup_response.lower() == 'y':
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                    print(f"Deleted: {temp_file}")
                except Exception as e:
                    print(f"Could not delete {temp_file}: {e}")
        
        return final_df
    else:
        print("No comments found to save")
        return None

if __name__ == "__main__":
    try:
        result = emergency_save_progress()
        print("\nEmergency save completed successfully!")
    except Exception as e:
        print(f"Error during emergency save: {e}")
    
    input("Press Enter to exit...")
