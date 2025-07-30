import sys
import os

# Change to the correct directory
os.chdir(r"C:\Users\ducle\OneDrive\Work-related\VS - Code project")

# Import and run the bulk generator
from Bulk_Comment_Generator import generate_all_comments

print("Starting automated bulk comment generation...")
print("This will generate comments for all banks and quarters from Q1 2023 onwards.")
print("Progress will be saved every 10 comments.")

try:
    result = generate_all_comments()
    if result is not None:
        print(f"\n✅ SUCCESS: Generated {len(result)} total comments!")
    else:
        print("\n❌ No comments were generated")
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")

print("\nBulk generation completed!")
input("Press Enter to exit...")
