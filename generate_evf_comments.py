#!/usr/bin/env python3
"""
Generate comments for EVF from 1Q24 to 2Q25
"""

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

# Load environment variables
load_dotenv()

# Get project root directory
project_root = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(project_root, 'Data')

# Import the comment generation function from bulk_comment_generator
from generators.bulk_comment_generator import openai_comment_bulk, get_bank_sector_mapping

def generate_evf_comments():
    """Generate comments for EVF from 1Q24 to 2Q25"""
    
    # Load data
    print("Loading data...")
    df_quarter = pd.read_csv(os.path.join(data_dir, 'dfsectorquarter.csv'))
    keyitem = pd.read_excel(os.path.join(data_dir, 'Key_items.xlsx'))
    bank_type_mapping = pd.read_excel(os.path.join(data_dir, 'Bank_Type.xlsx'))
    
    # Get bank sector mapping
    bank_sector_mapping = get_bank_sector_mapping()
    
    # Check if EVF exists in the data
    if 'EVF' not in df_quarter['TICKER'].unique():
        print("Error: EVF not found in the data")
        return None
    
    # Get EVF's sector
    evf_sector = bank_sector_mapping.get('EVF', 'Unknown')
    print(f"EVF Sector: {evf_sector}")
    
    # Define quarters from 1Q24 to 2Q25
    quarters_to_generate = [
        '1Q24', '2Q24', '3Q24', '4Q24',  # 2024 quarters
        '1Q25', '2Q25'  # 2025 quarters
    ]
    
    # Filter for quarters that actually exist in the data
    available_quarters = df_quarter['Date_Quarter'].unique()
    quarters_to_process = [q for q in quarters_to_generate if q in available_quarters]
    
    print(f"Quarters to process: {quarters_to_process}")
    
    # Load existing comments if any
    comments_file = os.path.join(data_dir, 'banking_comments.xlsx')
    if os.path.exists(comments_file):
        existing_comments = pd.read_excel(comments_file)
        print(f"Loaded {len(existing_comments)} existing comments")
    else:
        existing_comments = pd.DataFrame(columns=['TICKER', 'SECTOR', 'QUARTER', 'COMMENT', 'GENERATED_DATE'])
        print("No existing comments file found - will create new one")
    
    # Generate comments for each quarter
    new_comments = []
    
    for quarter in quarters_to_process:
        # Check if comment already exists for EVF in this quarter
        existing_entry = existing_comments[
            (existing_comments['TICKER'] == 'EVF') & 
            (existing_comments['QUARTER'] == quarter)
        ]
        
        if not existing_entry.empty:
            print(f"Comment for EVF {quarter} already exists - keeping existing")
            continue
        
        print(f"\nGenerating comment for EVF - {quarter}...")
        
        try:
            # Check if EVF has data for this quarter
            evf_data = df_quarter[
                (df_quarter['TICKER'] == 'EVF') & 
                (df_quarter['Date_Quarter'] == quarter)
            ]
            
            if evf_data.empty:
                print(f"  No data found for EVF in {quarter} - skipping")
                continue
            
            # Generate comment
            comment = openai_comment_bulk('EVF', evf_sector, quarter, df_quarter, keyitem)
            
            if comment:
                new_comments.append({
                    'TICKER': 'EVF',
                    'SECTOR': evf_sector,
                    'QUARTER': quarter,
                    'COMMENT': comment,
                    'GENERATED_DATE': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                print(f"  ✓ Generated successfully")
                print(f"  Preview: {comment[:150]}...")
            else:
                print(f"  ✗ Failed to generate comment")
            
            # Add delay to avoid rate limiting
            time.sleep(1)
            
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            continue
    
    # Merge with existing comments
    if new_comments:
        new_df = pd.DataFrame(new_comments)
        
        # Remove any existing EVF comments for these quarters from existing_comments
        if not existing_comments.empty:
            # Keep non-EVF comments and EVF comments not in our quarter range
            existing_comments = existing_comments[
                ~((existing_comments['TICKER'] == 'EVF') & 
                  (existing_comments['QUARTER'].isin(quarters_to_process)))
            ]
        
        # Combine existing and new comments
        final_df = pd.concat([existing_comments, new_df], ignore_index=True)
        
        # Sort by ticker and quarter
        final_df['quarter_numeric'] = final_df['QUARTER'].apply(quarter_to_numeric)
        final_df = final_df.sort_values(['TICKER', 'quarter_numeric'])
        final_df = final_df.drop('quarter_numeric', axis=1)
        
        # Save to Excel
        final_df.to_excel(comments_file, index=False)
        
        print(f"\n✓ Completed!")
        print(f"✓ Generated {len(new_comments)} new comments for EVF")
        print(f"✓ Total comments in file: {len(final_df)}")
        print(f"✓ Saved to: {comments_file}")
        
        # Show EVF comments summary
        evf_comments = final_df[final_df['TICKER'] == 'EVF']
        print(f"\nEVF Comments Summary:")
        print(f"- Total EVF comments: {len(evf_comments)}")
        print(f"- Quarters covered: {sorted(evf_comments['QUARTER'].tolist())}")
        
        return final_df
    else:
        print("\n✓ No new comments needed - all quarters already have comments or no data available")
        return existing_comments

if __name__ == "__main__":
    # Check API key first
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment variables")
        print("Please set your OpenAI API key in the .env file")
        sys.exit(1)
    
    print("EVF Comment Generator")
    print("=" * 50)
    print("This will generate comments for EVF from 1Q24 to 2Q25")
    print()
    
    # Confirm before proceeding
    response = input("Do you want to proceed? (y/n): ")
    if response.lower() == 'y':
        result = generate_evf_comments()
    else:
        print("Generation cancelled.")