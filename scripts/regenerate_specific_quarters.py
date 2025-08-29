import pandas as pd
import numpy as np
import openai
import os
from dotenv import load_dotenv
from datetime import datetime
import time
import sys

# Add parent directory to path for utilities import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utilities.quarter_utils import quarter_to_numeric, quarter_sort_key
from generators.bulk_comment_generator import openai_comment_bulk, get_bank_sector_mapping

# Load environment variables
load_dotenv()

# Get project root directory
project_root = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(project_root, 'Data')

def regenerate_specific_quarters(quarters_to_regenerate=['2025-Q1', '2025-Q2']):
    """
    Regenerate comments for specific quarters only.
    This will delete existing comments for these quarters and generate new ones.
    """
    
    # Load data
    print("Loading data...")
    df_quarter = pd.read_parquet(os.path.join(data_dir, 'dfsectorquarter.parquet'))
    keyitem = pd.read_excel(os.path.join(data_dir, 'Key_items.xlsx'))  # Still needed for compatibility
    bank_type_mapping = pd.read_excel(os.path.join(data_dir, 'Bank_Type.xlsx'))
    df_earnings_quality = pd.read_parquet(os.path.join(data_dir, 'earnings_quality_quarterly.parquet'))
    
    # Get bank-sector mapping
    print("Getting bank-sector mapping...")
    bank_sector_mapping = get_bank_sector_mapping()
    
    # Load existing comments
    comments_file = os.path.join(data_dir, 'banking_comments.parquet')
    if os.path.exists(comments_file):
        existing_comments = pd.read_parquet(comments_file)
        print(f"Found existing comments file with {len(existing_comments)} entries")
        
        # Remove comments for quarters we want to regenerate
        print(f"Removing existing comments for quarters: {quarters_to_regenerate}")
        comments_to_keep = existing_comments[~existing_comments['QUARTER'].isin(quarters_to_regenerate)]
        print(f"Keeping {len(comments_to_keep)} existing comments")
        
        # Convert to list of dictionaries for easier manipulation
        all_comments = comments_to_keep.to_dict('records')
    else:
        print("No existing comments file found, starting fresh")
        all_comments = []
    
    # Get all tickers
    all_tickers = list(bank_sector_mapping.keys())
    print(f"Found {len(all_tickers)} tickers to process")
    
    # Generate comments for specified quarters only
    total_to_generate = len(all_tickers) * len(quarters_to_regenerate)
    processed = 0
    errors = 0
    generated = 0
    
    print(f"\nStarting generation for {total_to_generate} combinations...")
    print(f"Quarters to regenerate: {quarters_to_regenerate}")
    print("="*50)
    
    for ticker in all_tickers:
        sector = bank_sector_mapping.get(ticker, 'Unknown')
        
        for quarter in quarters_to_regenerate:
            processed += 1
            
            print(f"[{processed}/{total_to_generate}] Generating comment for {ticker} ({sector}) - {quarter}")
            
            try:
                # Check if bank has data for this quarter
                bank_data = df_quarter[
                    (df_quarter['TICKER'] == ticker) & 
                    (df_quarter['Date_Quarter'] == quarter)
                ]
                
                if bank_data.empty:
                    print(f"  No data found for {ticker} in {quarter} - skipping")
                    continue
                
                # Generate comment
                comment = openai_comment_bulk(ticker, sector, quarter, df_quarter, keyitem, df_earnings_quality)
                
                if comment:
                    all_comments.append({
                        'TICKER': ticker,
                        'SECTOR': sector,
                        'QUARTER': quarter,
                        'COMMENT': comment,
                        'GENERATED_DATE': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    generated += 1
                    print(f"  Generated successfully")
                else:
                    errors += 1
                    print(f"  Failed to generate comment")
                
                # Add small delay to avoid rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                errors += 1
                print(f"  Error: {str(e)}")
                continue
            
            # Save progress every 10 comments
            if processed % 10 == 0:
                temp_df = pd.DataFrame(all_comments)
                temp_file = os.path.join(data_dir, f'banking_comments_temp_regen_{processed}.parquet')
                temp_df.to_parquet(temp_file, index=False, engine='pyarrow', compression='snappy')
                print(f"  Saved temporary progress: {len(all_comments)} total comments")
    
    # Save final results
    if all_comments:
        final_df = pd.DataFrame(all_comments)
        # Sort by quarter and ticker for better organization
        final_df['quarter_numeric'] = final_df['QUARTER'].apply(quarter_to_numeric)
        final_df = final_df.sort_values(['quarter_numeric', 'TICKER'])
        final_df = final_df.drop('quarter_numeric', axis=1)
        
        # Save to file
        final_df.to_parquet(comments_file, index=False, engine='pyarrow', compression='snappy')
        
        print("\n" + "="*50)
        print(f"Completed! Generated {generated} new comments")
        print(f"Total comments in file: {len(final_df)}")
        print(f"Errors encountered: {errors}")
        print(f"Saved to: {comments_file}")
        
        # Show summary for regenerated quarters
        for quarter in quarters_to_regenerate:
            quarter_comments = final_df[final_df['QUARTER'] == quarter]
            print(f"\n{quarter}: {len(quarter_comments)} comments")
            if len(quarter_comments) > 0:
                print(f"  Banks included: {', '.join(quarter_comments['TICKER'].head(10).tolist())}")
                if len(quarter_comments) > 10:
                    print(f"  ... and {len(quarter_comments) - 10} more")
        
        return final_df
    else:
        print("\nNo comments were generated")
        return None


def main():
    """Main function to run the regeneration"""
    print("="*60)
    print("REGENERATING COMMENTS FOR Q1-2025 AND Q2-2025")
    print("="*60)
    
    # Confirm with user
    print("\nThis will:")
    print("1. Delete all existing comments for Q1-2025 and Q2-2025")
    print("2. Generate new comments for these quarters")
    print("3. Keep all other quarters unchanged")
    print("")
    
    response = input("Do you want to proceed? (y/n): ")
    if response.lower() != 'y':
        print("Regeneration cancelled.")
        return
    
    # Run regeneration
    print("\nStarting regeneration...")
    result = regenerate_specific_quarters(['2025-Q1', '2025-Q2'])
    
    if result is not None:
        print("\nRegeneration complete!")
    else:
        print("\nRegeneration failed.")


if __name__ == "__main__":
    main()