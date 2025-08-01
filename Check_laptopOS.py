import os
import platform

def get_data_path():
    """Get the appropriate data path based on operating system"""
    if platform.system() == "Windows":
        # Windows path (your work laptop)
        return r"c:\Users\ducle\OneDrive\Work-related\VS - Code project\Data"
    else:
        # Mac/Linux path (current directory)
        # Get the directory where this script is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, "Data")

def get_comments_file_path():
    """Get the full path to the banking comments file"""
    data_path = get_data_path()
    return os.path.join(data_path, "banking_comments.xlsx")
