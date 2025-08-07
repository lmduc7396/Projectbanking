"""
OpenAI API utility functions for generating banking comments and analysis
"""

import pandas as pd
import numpy as np
import openai
import os
from datetime import datetime
import json

def get_openai_client():
    """Get or create OpenAI client"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    return openai.OpenAI(api_key=api_key)

def load_cached_comment(ticker, quarter, cache_dir='Data'):
    """
    Load cached comment for a specific ticker and quarter
    
    Args:
        ticker: Bank ticker
        quarter: Quarter string (e.g., '1Q25')
        cache_dir: Directory containing cache files
        
    Returns:
        str or None: Cached comment if exists
    """
    cache_file = os.path.join(cache_dir, 'banking_comments.xlsx')
    
    if os.path.exists(cache_file):
        try:
            df = pd.read_excel(cache_file)
            # Look for matching ticker and quarter
            matching_row = df[(df['TICKER'] == ticker) & (df['QUARTER'] == quarter)]
            if not matching_row.empty:
                return matching_row.iloc[0]['COMMENT']
        except Exception as e:
            print(f"Error loading cache: {e}")
    
    return None

def save_comment_to_cache(ticker, sector, quarter, comment, cache_dir='Data'):
    """
    Save generated comment to cache
    
    Args:
        ticker: Bank ticker
        sector: Bank sector
        quarter: Quarter string
        comment: Generated comment
        cache_dir: Directory for cache files
    """
    cache_file = os.path.join(cache_dir, 'banking_comments.xlsx')
    
    # Create new row
    new_row = pd.DataFrame({
        'TICKER': [ticker],
        'SECTOR': [sector],
        'QUARTER': [quarter],
        'COMMENT': [comment],
        'GENERATED_AT': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
    })
    
    # Load existing file or create new
    if os.path.exists(cache_file):
        df = pd.read_excel(cache_file)
        # Remove existing entry if present
        df = df[~((df['TICKER'] == ticker) & (df['QUARTER'] == quarter))]
        # Append new row
        df = pd.concat([df, new_row], ignore_index=True)
    else:
        df = new_row
    
    # Save back to file
    df.to_excel(cache_file, index=False)
    print(f"[Saved] Comment for {ticker} - {quarter} to cache")

def generate_banking_comment_prompt(ticker, sector, quarter_data):
    """
    Generate prompt for banking comment analysis
    
    Args:
        ticker: Bank ticker
        sector: Bank sector
        quarter_data: Dictionary containing quarter financial data
        
    Returns:
        str: Formatted prompt for OpenAI
    """
    prompt = f"""You are a banking analyst expert. Based on the data provided for {ticker} ({sector} bank), 
    analyze the performance and provide insights.
    
    Data for analysis:
    {json.dumps(quarter_data, indent=2)}
    
    Please provide:
    1. Performance summary (2-3 sentences)
    2. Key strengths and concerns
    3. Notable trends or changes
    4. Risk assessment
    5. Forward outlook
    
    Keep the analysis concise but comprehensive (around 200-250 words)."""
    
    return prompt

def generate_quarterly_analysis_prompt(quarter, comments_data):
    """
    Generate prompt for quarterly banking sector analysis
    
    Args:
        quarter: Quarter string
        comments_data: DataFrame or text with all banking comments for the quarter
        
    Returns:
        str: Formatted prompt for OpenAI
    """
    bank_count = len(comments_data) if isinstance(comments_data, pd.DataFrame) else "multiple"
    
    prompt = f"""You are a senior banking analyst with expertise in Vietnamese banking sector. 
    Please analyze the following {bank_count} banking comments for {quarter} and provide a comprehensive analysis.

    BANKING COMMENTS FOR {quarter}:
    {comments_data if isinstance(comments_data, str) else comments_data.to_string()}

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
    
    Keep each section clear and concise. Total analysis should be 400-500 words."""
    
    return prompt