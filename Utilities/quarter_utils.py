#%% Import libraries
import re

def quarter_to_numeric(quarter_str):
    """Convert quarter string to numeric for sorting (e.g., '1Q24' -> 2024.25)"""
    try:
        match = re.match(r'(\d+)Q(\d+)', quarter_str)
        if match:
            quarter, year = match.groups()
            quarter, year = int(quarter), int(year)
            
            if year < 50:
                year += 2000
            elif year < 100:
                year += 1900
            
            return year + (quarter - 1) * 0.25
        return 0
    except:
        return 0

def quarter_sort_key(quarter_str):
    """Sort key function for quarter strings"""
    return quarter_to_numeric(quarter_str)

def sort_quarters(quarter_list):
    """Sort list of quarter strings chronologically"""
    return sorted(quarter_list, key=quarter_sort_key)