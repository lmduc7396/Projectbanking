import pandas as pd
import sys
import os

print("Starting script...")
print(f"Current working directory: {os.getcwd()}")
print(f"Script location: {__file__}")

try:
    # Try multiple path approaches
    paths_to_try = [
        r"Data\Prompt testing.xlsx",
        r".\Data\Prompt testing.xlsx", 
        r"c:\Users\ducle\OneDrive\Work-related\VS - Code project\Data\Prompt testing.xlsx",
        os.path.join(os.getcwd(), "Data", "Prompt testing.xlsx"),
        os.path.join(os.path.dirname(__file__), "Data", "Prompt testing.xlsx")
    ]
    
    for i, file_path in enumerate(paths_to_try):
        print(f"\nTrying path {i+1}: {file_path}")
        print(f"File exists: {os.path.exists(file_path)}")
        
        if os.path.exists(file_path):
            print(f"SUCCESS! Found file at: {file_path}")
            df = pd.read_excel(file_path)
            print("Successfully read the file!")
            print("Columns:", df.columns.tolist())
            print("Shape:", df.shape)
            print("\nData preview:")
            print(df.to_string())
            break
    else:
        print("No valid path found!")
        
except Exception as e:
    print(f"Error reading file: {e}")
    
try:
    print(f"\nFiles in current directory: {os.listdir('.')}")
    if os.path.exists("Data"):
        print(f"Files in Data directory: {os.listdir('Data')}")
    else:
        print("Data directory does not exist in current location")
except Exception as e:
    print(f"Error listing files: {e}")
