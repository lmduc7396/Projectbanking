"""
Utility functions for banking analysis project
"""

def quarter_sort_key(quarter_str):
    """
    Convert quarter string (e.g., '1Q25') to sortable tuple (year, quarter)
    
    Args:
        quarter_str (str): Quarter string in format 'XQyy' where X is quarter number and yy is 2-digit year
        
    Returns:
        tuple: (year, quarter) tuple for proper chronological sorting
        
    Examples:
        >>> quarter_sort_key('1Q25')
        (2025, 1)
        >>> quarter_sort_key('4Q24')
        (2024, 4)
    """
    if 'Q' in str(quarter_str):
        parts = str(quarter_str).split('Q')
        quarter_num = int(parts[0])
        year = int(parts[1])
        # Convert to full year if needed
        if year < 50:  # Assuming years 00-49 are 2000s
            year += 2000
        elif year < 100:  # Years 50-99 are 1900s (shouldn't happen for our data)
            year += 1900
        return (year, quarter_num)
    return (0, 0)

def quarter_to_numeric(quarter_str):
    """
    Convert quarter format (e.g., '1Q23') to numeric for sorting
    
    Args:
        quarter_str (str): Quarter string in format 'XQyy'
        
    Returns:
        int: Numeric representation (year * 10 + quarter)
        
    Examples:
        >>> quarter_to_numeric('1Q25')
        20251
        >>> quarter_to_numeric('4Q24')
        20244
    """
    if 'Q' in str(quarter_str):
        parts = str(quarter_str).split('Q')
        quarter_num = int(parts[0])
        year = int(parts[1])
        # Convert to full year if needed
        if year < 50:  # Assuming years 00-49 are 2000s
            year += 2000
        elif year < 100:  # Years 50-99 are 1900s (shouldn't happen for our data)
            year += 1900
        return year * 10 + quarter_num
    return 0

def sort_quarters(quarters_list, reverse=True):
    """
    Sort a list of quarters in chronological order
    
    Args:
        quarters_list (list): List of quarter strings
        reverse (bool): If True, sort in descending order (newest first)
        
    Returns:
        list: Sorted list of quarters
    """
    return sorted(quarters_list, key=quarter_sort_key, reverse=reverse)
