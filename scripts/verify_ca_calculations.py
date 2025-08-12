import pandas as pd

# Load the data
df = pd.read_csv('../Data/dfsectoryear_with_forecast.csv')

# Check ACB forecast data
sample = df[(df['TICKER'] == 'ACB') & (df['Year'].isin(['2025', '2026']))][
    ['TICKER', 'Year', 'BS.13', 'Nt.67', 'Nt.68', 'Nt.69', 'Nt.70', 'CA.3', 'CA.5']
]

print('ACB Forecast Data:')
print(sample)
print()

for _, row in sample.iterrows():
    npl_sum = row['Nt.68'] + row['Nt.69'] + row['Nt.70']
    
    if pd.notna(row['BS.13']) and row['BS.13'] != 0:
        ca3_calc = npl_sum / row['BS.13']
        ca5_calc = row['Nt.67'] / row['BS.13']
        
        print(f"{row['Year']}:")
        print(f"  BS.13 = {row['BS.13']:.2e}")
        print(f"  NPL sum (Nt.68+69+70) = {npl_sum:.2e}")
        print(f"  Group 2 (Nt.67) = {row['Nt.67']:.2e}")
        print(f"  CA.3 calculated = {ca3_calc:.4f} (stored: {row['CA.3']:.4f})")
        print(f"  CA.5 calculated = {ca5_calc:.4f} (stored: {row['CA.5']:.4f})")
        print()