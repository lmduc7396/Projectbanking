import pandas as pd
import os

def test_examples_loading():
    """Test function to verify we can load the writing examples"""
    
    # Try multiple path approaches to find the examples file
    possible_paths = [
        # From current file location
        os.path.join(os.path.dirname(__file__), "Data", "Prompt testing.xlsx"),
        # Absolute path
        r"c:\Users\ducle\OneDrive\Work-related\VS - Code project\Data\Prompt testing.xlsx",
        # Relative from current working directory
        os.path.join("Data", "Prompt testing.xlsx"),
        # Try going up one directory
        os.path.join("..", "Data", "Prompt testing.xlsx"),
        # Another relative approach
        "./Data/Prompt testing.xlsx"
    ]
    
    print("Testing different paths to find Prompt testing.xlsx:")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Script location: {__file__}")
    print()
    
    for i, path in enumerate(possible_paths, 1):
        print(f"Path {i}: {path}")
        print(f"  Absolute path: {os.path.abspath(path)}")
        print(f"  Exists: {os.path.exists(path)}")
        
        if os.path.exists(path):
            try:
                df = pd.read_excel(path)
                print(f"  ✅ SUCCESS! Loaded file with {len(df)} rows")
                print(f"  Columns: {df.columns.tolist()}")
                print(f"  Sample data:")
                print(df.head().to_string())
                return path, df
            except Exception as e:
                print(f"  ❌ Error reading file: {e}")
        print()
    
    print("❌ No valid path found!")
    return None, None

if __name__ == "__main__":
    test_examples_loading()
