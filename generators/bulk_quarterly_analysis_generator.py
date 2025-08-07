#!/usr/bin/env python3
#%%
"""
Bulk Quarterly Analysis Generator - Jupyter-style interactive script
Generates AI analysis for quarters and saves to Excel file
"""

import pandas as pd
import os
import sys
from datetime import datetime
import openai
from dotenv import load_dotenv
import time

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import utilities
from utilities.quarter_utils import quarter_sort_key, sort_quarters, quarter_to_numeric
from utilities.path_utils import get_data_path, get_comments_file_path

#%% Load environment and initialize
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

client = openai.OpenAI(api_key=api_key)
comments_file = get_comments_file_path()
analysis_file = os.path.join(get_data_path(), "quarterly_analysis_results.xlsx")

print(f"Comments file: {comments_file}")
print(f"Analysis file: {analysis_file}")

#%% Data loading functions

def load_comments_data():
    """Load banking comments data"""
    if not os.path.exists(comments_file):
        raise FileNotFoundError(f"Comments file not found: {comments_file}")
    return pd.read_excel(comments_file)

def load_existing_analysis():
    """Load existing analysis results if file exists"""
    if os.path.exists(analysis_file):
        try:
            return pd.read_excel(analysis_file)
        except Exception as e:
            print(f"Error loading existing analysis: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

#%% Quarter filtering functions

def get_available_quarters():
    """Get all available quarters from comments data"""
    comments_df = load_comments_data()
    all_quarters = comments_df['QUARTER'].unique()
    return sort_quarters(all_quarters, reverse=False)

def filter_quarters_by_range(start_quarter=None, end_quarter=None):
    """Filter quarters within a specific range using vectorized operations"""
    quarters_df = pd.DataFrame({'quarter': get_available_quarters()})
    quarters_df['quarter_numeric'] = quarters_df['quarter'].apply(quarter_to_numeric)
    
    # Apply filters
    if start_quarter:
        start_numeric = quarter_to_numeric(start_quarter)
        quarters_df = quarters_df[quarters_df['quarter_numeric'] >= start_numeric]
    
    if end_quarter:
        end_numeric = quarter_to_numeric(end_quarter)
        quarters_df = quarters_df[quarters_df['quarter_numeric'] <= end_numeric]
    
    return quarters_df['quarter'].tolist()

#%% Analysis generation function

def analyze_single_quarter(quarter_comments_df, quarter):
    """Analyze a single quarter using ChatGPT"""
    try:
        bank_count = len(quarter_comments_df)
        print(f"  Analyzing {bank_count} comments...")
        
        # Prepare comments text using vectorized string operations
        comments_text = '\n\n'.join(
            quarter_comments_df.apply(
                lambda row: f"**{row['TICKER']} ({row['SECTOR']}):**\n{row['COMMENT']}", 
                axis=1
            )
        )
        
        # Create analysis prompt
        prompt = f"""
        You are a senior banking analyst with expertise in Vietnamese banking sector. 
        Please analyze the following {bank_count} banking comments for {quarter} and provide a comprehensive analysis.

        BANKING COMMENTS FOR {quarter}:
        {comments_text}

        Please provide analysis in the following three sections:

        ## 1. KEY CHANGES SUMMARY
        Summarize the most significant trends and changes across all banks in this quarter. Focus on:
        - Overall banking sector performance and market conditions
        - Major shifts in credit growth, asset quality, profitability
        - Regulatory changes or market events impacting the sector
        - Notable outliers or exceptional performances

        ## 2. INDIVIDUAL BANK HIGHLIGHTS
        For each bank, provide a brief 1-2 sentence summary of their key performance points.
        Format as: **TICKER**: [summary]

        ## 3. FORWARD OUTLOOK
        Based on the current quarter's performance, provide:
        - Expected trends for next quarter
        - Key risks to monitor
        - Opportunities in the sector
        
        Keep each section clear and concise. Total analysis should be 400-500 words.
        """
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a senior banking analyst providing quarterly sector analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=800
        )
        
        analysis_text = response.choices[0].message.content
        
        # Parse sections using string operations
        sections = {
            'KEY_CHANGES': '',
            'INDIVIDUAL_HIGHLIGHTS': '',
            'FORWARD_OUTLOOK': ''
        }
        
        # Split and extract sections
        if '## 1.' in analysis_text or 'KEY CHANGES' in analysis_text:
            parts = analysis_text.split('## ')
            for part in parts:
                if 'KEY CHANGES' in part.upper() or '1.' in part:
                    sections['KEY_CHANGES'] = part.split('\n', 1)[1] if '\n' in part else part
                elif 'INDIVIDUAL' in part.upper() or '2.' in part:
                    sections['INDIVIDUAL_HIGHLIGHTS'] = part.split('\n', 1)[1] if '\n' in part else part
                elif 'FORWARD' in part.upper() or '3.' in part:
                    sections['FORWARD_OUTLOOK'] = part.split('\n', 1)[1] if '\n' in part else part
        else:
            sections['KEY_CHANGES'] = analysis_text
        
        return {
            'QUARTER': quarter,
            'BANK_COUNT': bank_count,
            'KEY_CHANGES': sections['KEY_CHANGES'].strip(),
            'INDIVIDUAL_HIGHLIGHTS': sections['INDIVIDUAL_HIGHLIGHTS'].strip(),
            'FORWARD_OUTLOOK': sections['FORWARD_OUTLOOK'].strip(),
            'FULL_ANALYSIS': analysis_text,
            'GENERATED_AT': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        print(f"    Error: {str(e)}")
        return None

#%% Bulk analysis generation

def generate_bulk_analysis(start_quarter=None, end_quarter=None, overwrite_existing=False):
    """
    Generate analysis for multiple quarters using vectorized operations
    """
    # Load comments data
    comments_df = load_comments_data()
    
    # Get quarters to process
    quarters_to_analyze = filter_quarters_by_range(start_quarter, end_quarter)
    
    # Load existing analysis
    existing_analysis = load_existing_analysis()
    
    print(f"\n{'='*60}")
    print(f"Starting bulk quarterly analysis generation")
    print(f"Quarters to analyze: {len(quarters_to_analyze)}")
    if quarters_to_analyze:
        print(f"Range: {quarters_to_analyze[0]} to {quarters_to_analyze[-1]}")
    print(f"Overwrite existing: {overwrite_existing}")
    print(f"{'='*60}\n")
    
    # Process quarters
    all_results = []
    
    for i, quarter in enumerate(quarters_to_analyze, 1):
        print(f"\n[{i}/{len(quarters_to_analyze)}] Processing {quarter}:")
        
        # Check if already exists
        if not overwrite_existing and not existing_analysis.empty:
            if quarter in existing_analysis['QUARTER'].values:
                print(f"  Skipped (already exists)")
                # Add existing to results
                existing_row = existing_analysis[existing_analysis['QUARTER'] == quarter].iloc[0]
                all_results.append(existing_row.to_dict())
                continue
        
        # Get comments for this quarter
        quarter_comments = comments_df[comments_df['QUARTER'] == quarter]
        
        if quarter_comments.empty:
            print(f"  No comments found")
            continue
        
        # Analyze the quarter
        result = analyze_single_quarter(quarter_comments, quarter)
        
        if result:
            all_results.append(result)
            print(f"  [Done] Analysis complete")
            
            # Save progress
            save_analysis_progress(all_results, existing_analysis, overwrite_existing)
        else:
            print(f"  [Failed] Analysis failed")
        
        # Rate limiting
        time.sleep(1)
    
    # Create final DataFrame
    results_df = pd.DataFrame(all_results) if all_results else pd.DataFrame()
    
    print(f"\n{'='*60}")
    print(f"[COMPLETE] Analysis generation finished!")
    print(f"Generated analysis for {len(all_results)} quarters")
    print(f"Results saved to: {analysis_file}")
    print(f"{'='*60}\n")
    
    return results_df

#%% Save and export functions

def save_analysis_progress(new_results, existing_df, overwrite):
    """Save progress incrementally using vectorized operations"""
    new_df = pd.DataFrame(new_results)
    
    if overwrite and not existing_df.empty:
        # Remove quarters being regenerated
        quarters_to_remove = new_df['QUARTER'].unique()
        existing_df = existing_df[~existing_df['QUARTER'].isin(quarters_to_remove)]
    
    # Combine dataframes
    combined_df = pd.concat([existing_df, new_df], ignore_index=True) if not existing_df.empty else new_df
    
    # Remove duplicates keeping latest
    combined_df = combined_df.drop_duplicates(subset=['QUARTER'], keep='last')
    
    # Sort by quarter
    combined_df['quarter_numeric'] = combined_df['QUARTER'].apply(quarter_to_numeric)
    combined_df = combined_df.sort_values('quarter_numeric').drop('quarter_numeric', axis=1)
    
    # Save to Excel
    combined_df.to_excel(analysis_file, index=False)

def export_analysis_report(output_file=None):
    """Export a formatted analysis report"""
    if not os.path.exists(analysis_file):
        print("No analysis results found. Please generate analysis first.")
        return
    
    analysis_df = pd.read_excel(analysis_file)
    
    if output_file is None:
        output_file = os.path.join(
            get_data_path(), 
            f"quarterly_analysis_report_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )
    
    # Create Excel writer with multiple sheets
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Summary sheet
        analysis_df[['QUARTER', 'BANK_COUNT', 'GENERATED_AT']].to_excel(
            writer, sheet_name='Summary', index=False
        )
        
        # Key Changes sheet
        analysis_df[['QUARTER', 'KEY_CHANGES']].to_excel(
            writer, sheet_name='Key Changes', index=False
        )
        
        # Individual Highlights sheet
        analysis_df[['QUARTER', 'INDIVIDUAL_HIGHLIGHTS']].to_excel(
            writer, sheet_name='Individual Highlights', index=False
        )
        
        # Forward Outlook sheet
        analysis_df[['QUARTER', 'FORWARD_OUTLOOK']].to_excel(
            writer, sheet_name='Forward Outlook', index=False
        )
        
        # Full Analysis sheet
        analysis_df[['QUARTER', 'FULL_ANALYSIS']].to_excel(
            writer, sheet_name='Full Analysis', index=False
        )
    
    print(f"Analysis report exported to: {output_file}")
    return output_file

#%% Main execution

def main():
    """Main function with menu interface"""
    print("\n" + "="*60)
    print("BULK QUARTERLY ANALYSIS GENERATOR")
    print("="*60)
    
    # Show available quarters
    try:
        available_quarters = get_available_quarters()
        print(f"\nAvailable quarters: {available_quarters[0]} to {available_quarters[-1]}")
    except Exception as e:
        print(f"\nError loading quarters: {e}")
        print("Please ensure banking_comments.xlsx exists with generated comments.")
        return
    
    print("\nOptions:")
    print("1. Analyze ALL quarters")
    print("2. Analyze SPECIFIC timeframe")
    print("3. Export analysis report")
    print("4. Exit")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == '1':
        # All quarters
        print("\nAnalyze ALL quarters")
        overwrite = input("Overwrite existing analysis? (y/n): ").strip().lower() == 'y'
        
        generate_bulk_analysis(
            start_quarter=None,
            end_quarter=None,
            overwrite_existing=overwrite
        )
        
    elif choice == '2':
        # Specific timeframe
        print("\nAnalyze SPECIFIC timeframe")
        print("Enter quarters in format like '1Q24' or press Enter to skip")
        
        start = input("Start quarter (or Enter for earliest): ").strip() or None
        end = input("End quarter (or Enter for latest): ").strip() or None
        overwrite = input("Overwrite existing analysis? (y/n): ").strip().lower() == 'y'
        
        generate_bulk_analysis(
            start_quarter=start,
            end_quarter=end,
            overwrite_existing=overwrite
        )
        
    elif choice == '3':
        # Export report
        export_analysis_report()
        
    else:
        print("Exiting...")

#%% Execute if run directly
if __name__ == "__main__":
    main()