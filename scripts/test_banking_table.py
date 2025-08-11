import pandas as pd
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utilities.banking_table import Banking_table

# Load data
df_quarter = pd.read_csv('Data/dfsectorquarter.csv')
df_year = pd.read_csv('Data/dfsectoryear.csv')
keyitem = pd.read_excel('Data/Key_items.xlsx')

print("Testing with quarterly data...")
try:
    df_table1_q, df_table2_q = Banking_table('ACB', 5, 'QoQ', df_quarter, keyitem)
    print("Quarterly data - SUCCESS")
    print("Table 1 shape:", df_table1_q.shape)
except Exception as e:
    print(f"Quarterly data - ERROR: {e}")

print("\nTesting with yearly data...")
try:
    df_table1_y, df_table2_y = Banking_table('ACB', 5, 'YoY', df_year, keyitem)
    print("Yearly data - SUCCESS")
    print("Table 1 shape:", df_table1_y.shape)
except Exception as e:
    print(f"Yearly data - ERROR: {e}")

print("\nTesting with Sector data (yearly)...")
try:
    df_table1_s, df_table2_s = Banking_table('Sector', 5, 'YoY', df_year, keyitem)
    print("Sector data - SUCCESS")
    print("Table 1 shape:", df_table1_s.shape)
except Exception as e:
    print(f"Sector data - ERROR: {e}")