"""
Update all file references from CSV/Excel to Parquet format
"""

import os
from pathlib import Path
import re

# Get project root directory
project_root = Path(__file__).parent.parent

# Define file replacements
replacements = {
    # CSV to Parquet
    "'dfsectorquarter.parquet'": "'dfsectorquarter.parquet'",
    '"dfsectorquarter.parquet"': '"dfsectorquarter.parquet"',
    "'dfsectoryear.parquet'": "'dfsectoryear.parquet'",
    '"dfsectoryear.parquet"': '"dfsectoryear.parquet"',
    "'dfsectorforecast.parquet'": "'dfsectorforecast.parquet'",
    '"dfsectorforecast.parquet"': '"dfsectorforecast.parquet"',
    "'Valuation_banking.parquet'": "'Valuation_banking.parquet'",
    '"Valuation_banking.parquet"': '"Valuation_banking.parquet"',
    "'earnings_quality_quarterly.parquet'": "'earnings_quality_quarterly.parquet'",
    '"earnings_quality_quarterly.parquet"': '"earnings_quality_quarterly.parquet"',
    "'earnings_quality_yearly.parquet'": "'earnings_quality_yearly.parquet'",
    '"earnings_quality_yearly.parquet"': '"earnings_quality_yearly.parquet"',
    
    # Excel to Parquet
    "'banking_comments.parquet'": "'banking_comments.parquet'",
    '"banking_comments.parquet"': '"banking_comments.parquet"',
    "'quarterly_analysis_results.parquet'": "'quarterly_analysis_results.parquet'",
    '"quarterly_analysis_results.parquet"': '"quarterly_analysis_results.parquet"',
    
    # Change read functions
    "pd.read_parquet(os.path.join(data_dir, 'dfsectorquarter": "pd.read_parquet(os.path.join(data_dir, 'dfsectorquarter",
    "pd.read_parquet(os.path.join(data_dir, 'dfsectoryear": "pd.read_parquet(os.path.join(data_dir, 'dfsectoryear",
    "pd.read_parquet(os.path.join(data_dir, 'dfsectorforecast": "pd.read_parquet(os.path.join(data_dir, 'dfsectorforecast",
    "pd.read_parquet(os.path.join(data_dir, 'Valuation_banking": "pd.read_parquet(os.path.join(data_dir, 'Valuation_banking",
    "pd.read_parquet(os.path.join(data_dir, 'earnings_quality": "pd.read_parquet(os.path.join(data_dir, 'earnings_quality",
    
    "pd.read_parquet(os.path.join(project_root, 'Data/dfsectorquarter": "pd.read_parquet(os.path.join(project_root, 'Data/dfsectorquarter",
    "pd.read_parquet(os.path.join(project_root, 'Data/dfsectoryear": "pd.read_parquet(os.path.join(project_root, 'Data/dfsectoryear",
    "pd.read_parquet(os.path.join(project_root, 'Data/dfsectorforecast": "pd.read_parquet(os.path.join(project_root, 'Data/dfsectorforecast",
    "pd.read_parquet(os.path.join(project_root, 'Data/Valuation_banking": "pd.read_parquet(os.path.join(project_root, 'Data/Valuation_banking",
    "pd.read_parquet(os.path.join(project_root, 'Data/earnings_quality": "pd.read_parquet(os.path.join(project_root, 'Data/earnings_quality",
    
    "pd.read_parquet(os.path.join(data_dir, 'banking_comments": "pd.read_parquet(os.path.join(data_dir, 'banking_comments",
    "pd.read_parquet(os.path.join(data_dir, 'quarterly_analysis": "pd.read_parquet(os.path.join(data_dir, 'quarterly_analysis",
    
    "pd.read_parquet(self.data_dir / 'banking_comments": "pd.read_parquet(self.data_dir / 'banking_comments",
    "pd.read_parquet(self.data_dir / 'quarterly_analysis": "pd.read_parquet(self.data_dir / 'quarterly_analysis",
    
    "pd.read_parquet(self.data_dir / 'dfsectorquarter": "pd.read_parquet(self.data_dir / 'dfsectorquarter",
    "pd.read_parquet(self.data_dir / 'dfsectoryear": "pd.read_parquet(self.data_dir / 'dfsectoryear",
    "pd.read_parquet(self.data_dir / 'dfsectorforecast": "pd.read_parquet(self.data_dir / 'dfsectorforecast",
    "pd.read_parquet(self.data_dir / 'Valuation_banking": "pd.read_parquet(self.data_dir / 'Valuation_banking",
    "pd.read_parquet(self.data_dir / 'earnings_quality": "pd.read_parquet(self.data_dir / 'earnings_quality",
    
    # For standalone paths
    "pd.read_parquet('Data/dfsectorquarter": "pd.read_parquet('Data/dfsectorquarter",
    "pd.read_parquet('Data/dfsectoryear": "pd.read_parquet('Data/dfsectoryear",
    "pd.read_parquet('Data/earnings_quality": "pd.read_parquet('Data/earnings_quality",
}

def update_file(file_path):
    """Update a single Python file with new references"""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    changes_made = []
    
    for old, new in replacements.items():
        if old in content:
            content = content.replace(old, new)
            changes_made.append(f"  - {old} → {new}")
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"✓ Updated {file_path.relative_to(project_root)}")
        for change in changes_made[:3]:  # Show first 3 changes
            print(change)
        if len(changes_made) > 3:
            print(f"  ... and {len(changes_made) - 3} more changes")
        return True
    return False

def main():
    """Main update function"""
    print("=" * 60)
    print("Updating file references to Parquet format")
    print("=" * 60)
    
    # Define directories to update
    directories = [
        project_root / 'utilities',
        project_root / 'pages',
        project_root / 'generators',
        project_root / 'scripts',
    ]
    
    # Also update streamlit_app.py
    standalone_files = [
        project_root / 'streamlit_app.py',
        project_root / 'regenerate_specific_quarters.py',
    ]
    
    files_updated = 0
    files_checked = 0
    
    # Process directories
    for directory in directories:
        if not directory.exists():
            continue
            
        for py_file in directory.glob("*.py"):
            files_checked += 1
            if update_file(py_file):
                files_updated += 1
    
    # Process standalone files
    for file_path in standalone_files:
        if file_path.exists():
            files_checked += 1
            if update_file(file_path):
                files_updated += 1
    
    print("\n" + "=" * 60)
    print("Update Summary")
    print("=" * 60)
    print(f"Files checked: {files_checked}")
    print(f"Files updated: {files_updated}")
    print("\n✓ File references updated successfully!")
    
    print("\nNext steps:")
    print("1. Test all pages and generators to ensure compatibility")
    print("2. Run 'streamlit run streamlit_app.py' to test the application")

if __name__ == "__main__":
    main()