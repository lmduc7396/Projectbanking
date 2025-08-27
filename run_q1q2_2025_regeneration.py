#%%
#!/usr/bin/env python
"""
Quick script to regenerate Q1-2025 and Q2-2025 comments
Run this directly: python run_q1q2_2025_regeneration.py
"""

from regenerate_specific_quarters import regenerate_specific_quarters

if __name__ == "__main__":
    print("="*60)
    print("QUICK REGENERATION FOR Q1-2025 AND Q2-2025")
    print("="*60)
    print("\nThis will regenerate all comments for Q1-2025 and Q2-2025")
    print("Existing comments for these quarters will be replaced.")
    print("")
    
    response = input("Proceed? (y/n): ")
    if response.lower() == 'y':
        result = regenerate_specific_quarters(['2025-Q1', '2025-Q2'])
        if result is not None:
            print("\nSuccess! Comments regenerated.")
    else:
            print("\nFailed to regenerate comments.")
else:
        print("Cancelled.")