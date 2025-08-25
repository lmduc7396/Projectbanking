#%% Import libraries
import re

def quarter_to_numeric(quarter_str):
    """Convert quarter string to numeric for sorting (e.g., '2024-Q1' -> 2024.00)
    Forecast years (pure year format) get 0.99 added to sort after quarters"""
    try:
        # Handle new format: YYYY-Q#
        if '-Q' in str(quarter_str):
            parts = str(quarter_str).split('-Q')
            year = int(parts[0])
            quarter = int(parts[1])
            return year + (quarter - 1) * 0.25
        
        # Handle pure year format (e.g., '2024', '2025') - these are forecast years
        # Add 0.99 to ensure they sort after all quarters (Q4 = 0.75)
        if str(quarter_str).isdigit() and len(str(quarter_str)) == 4:
            return float(quarter_str) + 0.99
            
        return 0
    except:
        return 0

def quarter_sort_key(quarter_str):
    """Sort key function for quarter strings
    With new format YYYY-Q#, alphabetical sort works naturally,
    but we keep this for backward compatibility and numeric sorting needs
    """
    return quarter_to_numeric(quarter_str)

def sort_quarters(quarter_list, reverse=False):
    """Sort list of quarter strings chronologically
    With new format YYYY-Q#, simple alphabetical sort works,
    but we keep numeric sort for mixed year/quarter lists
    """
    return sorted(quarter_list, key=quarter_sort_key, reverse=reverse)

def format_quarter_for_display(quarter_str):
    """Convert quarter string from YYYY-Q# to #Qyy format for display only
    Examples: '2025-Q1' -> '1Q25', '2024-Q3' -> '3Q24'
    Pure years remain unchanged: '2025' -> '2025'
    """
    try:
        quarter_str = str(quarter_str)
        
        # Handle new format: YYYY-Q#
        if '-Q' in quarter_str:
            parts = quarter_str.split('-Q')
            year = parts[0]
            quarter = parts[1]
            # Extract last 2 digits of year
            year_short = year[-2:]
            return f"{quarter}Q{year_short}"
        
        # Pure year format remains unchanged (for forecast years)
        return quarter_str
    except:
        return quarter_str