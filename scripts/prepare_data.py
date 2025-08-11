#%%
import pandas as pd
import numpy as np
import os
import re
from pathlib import Path

# Get the script directory and project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
data_dir = os.path.join(project_root, 'Data')

print("Loading base data files...")

# Read base files using absolute paths
dfis = pd.read_csv(os.path.join(data_dir, 'IS_Bank.csv'))
dfbs = pd.read_csv(os.path.join(data_dir, 'BS_Bank.csv'))
dfnt = pd.read_csv(os.path.join(data_dir, 'Note_Bank.csv'))
Type = pd.read_excel(os.path.join(data_dir, 'Bank_Type.xlsx'))
mapping = pd.read_excel(os.path.join(data_dir, 'IRIS KeyCodes - Bank.xlsx'))
dfwriteoff = pd.read_excel(os.path.join(data_dir, 'writeoffs.xlsx'))

# Check if forecast data exists
forecast_file_path = os.path.join(data_dir, 'FORECAST_bank.csv')
has_forecast = os.path.exists(forecast_file_path)

if has_forecast:
    print("Loading forecast data...")
    forecast_bank = pd.read_csv(forecast_file_path)
else:
    print("No forecast data found, processing historical data only...")

#%% Process historical data
print("Processing historical data...")

# Clean writeoff 
write_offtemp = dfwriteoff[~(dfwriteoff['EXCHANGE']=='OTC')]
write_offtemp = write_offtemp.drop(columns=['EXCHANGE'])
write_off = write_offtemp.melt(id_vars = ['TICKER'], var_name = 'DATE', value_name='Nt.220')
write_off['YEARREPORT'] = write_off['DATE'].str[2:].astype(int)
write_off['LENGTHREPORT'] = write_off['DATE'].str[1:2].astype(int)
write_off = write_off.drop(columns=['DATE'])
write_off = write_off.sort_values(['TICKER','YEARREPORT','LENGTHREPORT'])

# Create 5Q for writeoff
write_off['Nt.220'] = pd.to_numeric(write_off['Nt.220'], errors='coerce')
write_off['Nt.220'] = write_off['Nt.220']*(10**6)
sum_rows = (
    write_off.groupby(['TICKER','YEARREPORT'],as_index=False)['Nt.220']
    .sum()
    .assign(LENGTHREPORT=5)
)
sum_rows = sum_rows[['TICKER','LENGTHREPORT','YEARREPORT','Nt.220']]
write_off = pd.concat([write_off,sum_rows],ignore_index=True)

# Replace name & merge & Sort by date
rename_dict = dict(zip(mapping['DWHCode'],mapping['KeyCode']))
dfis = dfis.rename(columns=rename_dict)
dfbs = dfbs.rename(columns=rename_dict)
dfnt = dfnt.rename(columns=rename_dict)

temp = pd.merge(dfis,dfbs,on=['TICKER','YEARREPORT','LENGTHREPORT'],how='inner')
temp2 = pd.merge(temp,dfnt,on=['TICKER','YEARREPORT','LENGTHREPORT'],how='inner')
temp3 = pd.merge(temp2,Type,on=['TICKER'],how='left')
dfall = pd.merge(temp3,write_off,on=['TICKER','YEARREPORT','LENGTHREPORT'],how='left')
dfall = dfall.sort_values(by=['TICKER','ENDDATE_x'])
bank_type = ['SOCB','Private_1','Private_2','Private_3','Sector']

# Add in date columns
# For yearly data (LENGTHREPORT=5), use full year; for quarterly, use XQyy format
dfall['Date_Quarter'] = dfall.apply(
    lambda row: str(int(row['YEARREPORT'])) if row['LENGTHREPORT'] == 5 
    else str(int(row['LENGTHREPORT'])) + 'Q' + str(int(row['YEARREPORT']))[-2:], 
    axis=1
)
dfall = dfall.dropna(subset='ENDDATE_x')
dfall = dfall.groupby(['TICKER','Date_Quarter'],as_index=False).first()
dfall = dfall[dfall['YEARREPORT']>2017]

first_col = ['YEARREPORT','LENGTHREPORT','ENDDATE_x','Type']
agg_dict = {col:'sum' for col in dfall.columns if col not in ['Date_Quarter']+first_col}
for col in first_col:
    agg_dict[col] = 'first'

# Set up quarter only
dfcompaniesquarter = dfall[~(dfall.LENGTHREPORT>4)]
dfsectorquarter = dfcompaniesquarter.groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfsocbquarter = dfcompaniesquarter[dfcompaniesquarter['Type']=='SOCB'].groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfprivate1quarter = dfcompaniesquarter[dfcompaniesquarter['Type']=='Private_1'].groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfprivate2quarter = dfcompaniesquarter[dfcompaniesquarter['Type']=='Private_2'].groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfprivate3quarter = dfcompaniesquarter[dfcompaniesquarter['Type']=='Private_3'].groupby('Date_Quarter',as_index=False).agg(agg_dict)

# Set up yearly only - Date_Quarter now contains full year (e.g., "2024")
dfcompaniesyear = dfall[(dfall.LENGTHREPORT==5)]
dfsectoryear = dfcompaniesyear.groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfsocbyear = dfcompaniesyear[dfcompaniesyear['Type']=='SOCB'].groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfprivate1year = dfcompaniesyear[dfcompaniesyear['Type']=='Private_1'].groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfprivate2year = dfcompaniesyear[dfcompaniesyear['Type']=='Private_2'].groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfprivate3year = dfcompaniesyear[dfcompaniesyear['Type']=='Private_3'].groupby('Date_Quarter',as_index=False).agg(agg_dict)

#%% Advanced Formula Resolution Engine with Equation Solving (if forecast exists)
if has_forecast:
    print("Building advanced formula resolution engine for forecast data...")
    
    def parse_formula(formula):
        """Parse a formula string to extract operators and operands"""
        if pd.isna(formula) or formula is None:
            return None, None, None
        
        formula = str(formula).strip()
        
        # Check for operations
        if '+' in formula:
            parts = formula.split('+')
            return '+', [p.strip() for p in parts], None
        elif '-' in formula and formula.count('-') == 1 and not formula.startswith('-'):
            parts = formula.split('-')
            return '-', [parts[0].strip(), parts[1].strip()], None
        elif '*' in formula:
            parts = formula.split('*')
            if len(parts) == 2:
                return '*', [parts[0].strip(), parts[1].strip()], None
        elif '/' in formula:
            parts = formula.split('/')
            if len(parts) == 2:
                return '/', [parts[0].strip(), parts[1].strip()], None
        else:
            # Simple formula
            return 'simple', [formula], None

    def build_equation_system(ticker_forecast_data):
        """
        Build a system of equations from forecast data
        Returns a dictionary mapping formulas to values and derived relationships
        """
        equations = {}
        simple_assignments = {}
        composite_formulas = {}
        
        for _, row in ticker_forecast_data.iterrows():
            formula = row['Formula']
            value = row['VALUE']
            keycode = row['KEYCODE']
            
            if pd.isna(formula):
                continue
                
            operator, operands, _ = parse_formula(formula)
            
            if operator == 'simple':
                # Direct assignment: KeyCode = value
                simple_assignments[operands[0]] = value
            else:
                # Composite formula: store the equation
                composite_formulas[keycode] = {
                    'formula': formula,
                    'value': value,
                    'operator': operator,
                    'operands': operands
                }
        
        return simple_assignments, composite_formulas

    def solve_equations(simple_assignments, composite_formulas):
        """
        Solve the system of equations to derive unknown values
        """
        solved_values = simple_assignments.copy()
        max_iterations = 20
        
        for iteration in range(max_iterations):
            changed = False
            
            for keycode, formula_info in composite_formulas.items():
                operator = formula_info['operator']
                operands = formula_info['operands']
                target_value = formula_info['value']
                
                if operator == '+':
                    # Equation: A + B + ... = target_value
                    # Try to solve for unknowns
                    known_sum = 0
                    unknown_operands = []
                    
                    for operand in operands:
                        if operand in solved_values:
                            known_sum += solved_values[operand]
                        else:
                            unknown_operands.append(operand)
                    
                    # If we have exactly one unknown, we can solve for it
                    if len(unknown_operands) == 1:
                        unknown = unknown_operands[0]
                        solved_value = target_value - known_sum
                        if unknown not in solved_values:
                            solved_values[unknown] = solved_value
                            changed = True
                            print(f"  Solved {unknown} = {solved_value:.2e} from equation {formula_info['formula']} = {target_value:.2e}")
                    
                    # If all operands are known, verify consistency
                    elif len(unknown_operands) == 0:
                        calculated_sum = sum(solved_values[op] for op in operands)
                        if abs(calculated_sum - target_value) > 1:  # Allow small rounding errors
                            # There's an inconsistency, prefer the composite formula value
                            # This handles cases where individual components might be wrong
                            pass
                
                elif operator == '-':
                    # Equation: A - B = target_value
                    if len(operands) == 2:
                        A, B = operands
                        
                        if A in solved_values and B not in solved_values:
                            # B = A - target_value
                            solved_values[B] = solved_values[A] - target_value
                            changed = True
                            print(f"  Solved {B} = {solved_values[B]:.2e} from {A} - {B} = {target_value:.2e}")
                        elif B in solved_values and A not in solved_values:
                            # A = target_value + B
                            solved_values[A] = target_value + solved_values[B]
                            changed = True
                            print(f"  Solved {A} = {solved_values[A]:.2e} from {A} - {B} = {target_value:.2e}")
                
                elif operator == '*':
                    # Equation: A * B = target_value
                    if len(operands) == 2:
                        A, B = operands
                        
                        if A in solved_values and B not in solved_values and solved_values[A] != 0:
                            solved_values[B] = target_value / solved_values[A]
                            changed = True
                            print(f"  Solved {B} = {solved_values[B]:.2e} from {A} * {B} = {target_value:.2e}")
                        elif B in solved_values and A not in solved_values and solved_values[B] != 0:
                            solved_values[A] = target_value / solved_values[B]
                            changed = True
                            print(f"  Solved {A} = {solved_values[A]:.2e} from {A} * {B} = {target_value:.2e}")
                
                elif operator == '/':
                    # Equation: A / B = target_value
                    if len(operands) == 2:
                        A, B = operands
                        
                        if B in solved_values and B not in solved_values and solved_values[B] != 0:
                            # A = target_value * B
                            solved_values[A] = target_value * solved_values[B]
                            changed = True
                            print(f"  Solved {A} = {solved_values[A]:.2e} from {A} / {B} = {target_value:.2e}")
                        elif A in solved_values and B not in solved_values and target_value != 0:
                            # B = A / target_value
                            solved_values[B] = solved_values[A] / target_value
                            changed = True
                            print(f"  Solved {B} = {solved_values[B]:.2e} from {A} / {B} = {target_value:.2e}")
            
            if not changed:
                break
        
        return solved_values

    #%% Create forecast structure for future years
    print("Creating forecast structure for 2025 and 2026...")
    
    # Get the structure from 2024 data to use as template
    template_year = dfcompaniesyear[dfcompaniesyear['Date_Quarter'] == '2024'].copy()
    
    # Get unique tickers from forecast data
    forecast_tickers = forecast_bank['TICKER'].unique()
    
    # Initialize list to hold forecast rows
    forecast_rows = []
    
    for year in [2025, 2026]:
        print(f"\nProcessing year {year}...")
        
        # Get forecast data for this year
        year_forecast = forecast_bank[forecast_bank['DATE'] == year].copy()
        
        # For each ticker in forecast
        for ticker in forecast_tickers:
            ticker_forecast = year_forecast[year_forecast['TICKER'] == ticker]
            
            if len(ticker_forecast) == 0:
                continue
            
            print(f"  Processing {ticker} for {year}...")
            
            # Try to find template from 2024 or create new
            if ticker in template_year['TICKER'].values:
                # Use 2024 as template
                new_row = template_year[template_year['TICKER'] == ticker].iloc[0].copy()
            else:
                # Create new row with default structure
                new_row = pd.Series(dtype='float64')
                new_row['TICKER'] = ticker
                
                # Set Type based on Bank_Type
                if ticker in Type['TICKER'].values:
                    new_row['Type'] = Type[Type['TICKER'] == ticker]['Type'].iloc[0]
                else:
                    new_row['Type'] = 'Other'
            
            # Update year-specific fields
            new_row['Date_Quarter'] = str(year)
            new_row['YEARREPORT'] = year
            new_row['LENGTHREPORT'] = 5  # Yearly data
            new_row['ENDDATE_x'] = f"{year}-12-31"
            
            # Clear all numeric columns to prepare for forecast values
            for col in new_row.index:
                if col.startswith(('BS.', 'IS.', 'Nt.', 'CA.')):
                    new_row[col] = np.nan
            
            # Build and solve equation system
            simple_assignments, composite_formulas = build_equation_system(ticker_forecast)
            solved_values = solve_equations(simple_assignments, composite_formulas)
            
            # Apply solved values to the row
            for col, value in solved_values.items():
                if col in new_row.index:
                    new_row[col] = value
            
            # Also handle composite formulas that directly map to target columns
            # Special cases for known aggregate columns
            special_mappings = {
                'Customer_loan': 'CA.14',  # BS.13+BS.16
                'Provision_for_customer_loan': None,  # BS.17+BS.14 - we'll calculate BS.14 from this
            }
            
            for _, forecast_row in ticker_forecast.iterrows():
                keycode_name = forecast_row['KEYCODENAME']
                formula = forecast_row['Formula']
                value = forecast_row['VALUE']
                
                # Handle special aggregate columns
                if keycode_name == 'Customer_loan' and formula == 'BS.13+BS.16':
                    # We have Customer_loan = BS.13 + BS.16
                    # We need to check if BS.16 is known to derive BS.13
                    if 'BS.16' in solved_values and 'BS.13' not in solved_values:
                        new_row['BS.13'] = value - solved_values['BS.16']
                        print(f"    Derived BS.13 = {new_row['BS.13']:.2e} from Customer_loan - BS.16")
                    elif 'BS.13' in solved_values and 'BS.16' not in solved_values:
                        new_row['BS.16'] = value - solved_values['BS.13']
                        print(f"    Derived BS.16 = {new_row['BS.16']:.2e} from Customer_loan - BS.13")
                    # Store the aggregate value
                    new_row['CA.14'] = value
                
                elif keycode_name == 'Provision_for_customer_loan' and formula == 'BS.17+BS.14':
                    # We have Provision_for_customer_loan = BS.17 + BS.14
                    if 'BS.17' in solved_values and 'BS.14' not in solved_values:
                        new_row['BS.14'] = value - solved_values['BS.17']
                        print(f"    Derived BS.14 = {new_row['BS.14']:.2e} from Provision_for_customer_loan - BS.17")
                    elif 'BS.14' in solved_values and 'BS.17' not in solved_values:
                        new_row['BS.17'] = value - solved_values['BS.14']
                        print(f"    Derived BS.17 = {new_row['BS.17']:.2e} from Provision_for_customer_loan - BS.14")
            
            # Final pass: ensure BS.13 is filled if we have CA.14 and BS.16
            if pd.isna(new_row.get('BS.13', np.nan)) and not pd.isna(new_row.get('CA.14', np.nan)) and not pd.isna(new_row.get('BS.16', np.nan)):
                new_row['BS.13'] = new_row['CA.14'] - new_row['BS.16']
                print(f"    Final derivation: BS.13 = {new_row['BS.13']:.2e} from CA.14 - BS.16")
            
            forecast_rows.append(new_row)
    
    # Convert list to DataFrame
    df_forecast = pd.DataFrame(forecast_rows)
    
    print(f"\nCreated {len(df_forecast)} forecast rows")
    
    #%% Merge forecast with historical data
    print("\nMerging forecast with historical data...")
    
    # Append forecast to companies year
    dfcompaniesyear = pd.concat([dfcompaniesyear, df_forecast], ignore_index=True)
    
    # Sort by ticker and year
    dfcompaniesyear = dfcompaniesyear.sort_values(['TICKER', 'Date_Quarter'])
    
    #%% Calculate sector aggregates for forecast years
    print("Calculating sector aggregates for forecast years...")
    
    # Filter forecast data only
    forecast_only = dfcompaniesyear[dfcompaniesyear['Date_Quarter'].isin(['2025', '2026'])]
    
    # Calculate aggregates
    dfsectoryear_forecast = forecast_only.groupby('Date_Quarter', as_index=False).agg(agg_dict)
    dfsocbyear_forecast = forecast_only[forecast_only['Type']=='SOCB'].groupby('Date_Quarter', as_index=False).agg(agg_dict)
    dfprivate1year_forecast = forecast_only[forecast_only['Type']=='Private_1'].groupby('Date_Quarter', as_index=False).agg(agg_dict)
    dfprivate2year_forecast = forecast_only[forecast_only['Type']=='Private_2'].groupby('Date_Quarter', as_index=False).agg(agg_dict)
    dfprivate3year_forecast = forecast_only[forecast_only['Type']=='Private_3'].groupby('Date_Quarter', as_index=False).agg(agg_dict)
    
    # Append to historical aggregates
    dfsectoryear = pd.concat([dfsectoryear, dfsectoryear_forecast], ignore_index=True)
    dfsocbyear = pd.concat([dfsocbyear, dfsocbyear_forecast], ignore_index=True)
    dfprivate1year = pd.concat([dfprivate1year, dfprivate1year_forecast], ignore_index=True)
    dfprivate2year = pd.concat([dfprivate2year, dfprivate2year_forecast], ignore_index=True)
    dfprivate3year = pd.concat([dfprivate3year, dfprivate3year_forecast], ignore_index=True)

#%% Calculation all CA set up
def Calculate(df):
    df = df.sort_values(by=['TICKER','ENDDATE_x'])
    
    # CA.1 LDR: BS.13/BS.56
    df['CA.1'] = (df['BS.13'] / df['BS.56'])
    
    # CA.2 CASA: (Nt.121+Nt.124+Nt.125)/BS.56
    df['CA.2'] = (df['Nt.121']+df['Nt.124']+df['Nt.125'])/df['BS.56']
    
    # CA.3 NPL: (Nt.68+Nt.69+Nt.70)/BS.13
    df['CA.3'] = (df['Nt.68']+df['Nt.69']+df['Nt.70'])/df['BS.13']
    
    # CA.4 Abs NPL: Nt.68+Nt.69+Nt.70
    df['CA.4'] = df['Nt.68'] + df['Nt.69'] + df['Nt.70']
    
    # CA.5: Group 2: Nt.67/BS.13
    df['CA.5'] = df['Nt.67'] / df['BS.13']
    
    # CA.6: CIR: -IS.15/IS.14
    df['CA.6'] = -df['IS.15'] / df['IS.14']
    
    # CA.7: NPL Coverage Ratio BS.14/(Nt.68+Nt.69+Nt.70)
    df['CA.7'] = -df['BS.14'] / (df['Nt.68'] + df['Nt.69'] + df['Nt.70'])
    
    # CA.8: Credit size: BS.13+BS.16+Nt.97+Nt.112
    df['CA.8'] = df['BS.13'] + df['BS.16'] + df['Nt.97'] + df['Nt.112']
    
    # CA.9: Provision/ Total loan -BS.14/BS.13
    df['CA.9'] = -df['BS.14'] / df['BS.13']
    
    # CA.10: Leverage BS.1/BS.65
    df['CA.10'] = df['BS.1'] / df['BS.65']
    
    # CA.11: IEA (BS.3+BS.5+BS.6+BS.9+BS.13+BS.16+BS.19+BS.20)
    df['CA.11'] = (df['BS.3'] + df['BS.5'] + df['BS.6'] + df['BS.9'] + 
                   df['BS.13'] + df['BS.16'] + df['BS.19'] + df['BS.20'])
    
    # CA.12: IBL BS.52+BS.53+BS.56+BS.58+BS.59
    df['CA.12'] = df['BS.52'] + df['BS.53'] + df['BS.56'] + df['BS.58'] + df['BS.59']
    
    # CA.13: NIM (IS.3/Average(CA.11, CA.11 t-1)*2)
    if len(df) > 0 and df.iloc[0]['LENGTHREPORT'] < 5:
        df['CA.13'] = (df['IS.3'] / (df['CA.11'] + df['CA.11'].shift(1))) * 8
    else:
        df['CA.13'] = (df['IS.3'] / (df['CA.11'] + df['CA.11'].shift(1))) * 2
    
    # CA.14: Customer loan BS.13+BS.16  
    # Check if CA.14 exists first (for forecast data), otherwise calculate it
    if 'CA.14' in df.columns:
        df['CA.14'] = np.where(df['CA.14'].isna(), df['BS.13'] + df['BS.16'], df['CA.14'])
    else:
        df['CA.14'] = df['BS.13'] + df['BS.16']
    
    # CA.15: Loan yield Nt.143/CA.14
    if len(df) > 0 and df.iloc[0]['LENGTHREPORT'] < 5:
        df['CA.15'] = (df['Nt.143'] / (df['CA.14'] + df['CA.14'].shift(1))) * 8
    else:
        df['CA.15'] = (df['Nt.143'] / (df['CA.14'] + df['CA.14'].shift(1))) * 2
    
    # CA.16: ROAA IS.22/BS.1
    if len(df) > 0 and df.iloc[0]['LENGTHREPORT'] < 5:
        df['CA.16'] = (df['IS.22'] / (df['BS.1'] + df['BS.1'].shift(1))) * 8
    else:
        df['CA.16'] = (df['IS.22'] / (df['BS.1'] + df['BS.1'].shift(1))) * 2
    
    # CA.17: ROAE: IS.24/BS.65
    if len(df) > 0 and df.iloc[0]['LENGTHREPORT'] < 5:
        df['CA.17'] = (df['IS.24'] / (df['BS.65'] + df['BS.65'].shift(1))) * 8
    else:
        df['CA.17'] = (df['IS.24'] / (df['BS.65'] + df['BS.65'].shift(1))) * 2
    
    # CA.18: Deposit balance BS.3+BS.5+BS.6
    df['CA.18'] = df['BS.3'] + df['BS.5'] + df['BS.6']
    
    # CA.19: Deposit yield: Nt.144/ CA.18
    if len(df) > 0 and df.iloc[0]['LENGTHREPORT'] < 5:
        df['CA.19'] = (df['Nt.144'] / (df['CA.18'] + df['CA.18'].shift(1))) * 8
    else:
        df['CA.19'] = (df['Nt.144'] / (df['CA.18'] + df['CA.18'].shift(1))) * 2
    
    # CA.20: Fees Income/ Total asset IS.6/BS.1
    if len(df) > 0 and df.iloc[0]['LENGTHREPORT'] < 5:
        df['CA.20'] = (df['IS.6'] / (df['BS.1'] + df['BS.1'].shift(1))) * 8
    else:
        df['CA.20'] = (df['IS.6'] / (df['BS.1'] + df['BS.1'].shift(1))) * 2
    
    # CA.21: Individual/ Total loan: Nt.89/BS.12
    df['CA.21'] = df['Nt.89'] / df['BS.12']
    
    # CA.22: NPL Formation:
    df['CA.22'] = (df['CA.4'] - df['Nt.220']) - (df['CA.4'].shift(1))
    
    # CA.23: NPL Formation (%):
    df['CA.23'] = df['CA.22'] / df['BS.13'].shift(1)
    
    # CA.24: Group 2 Formation
    df['CA.24'] = (df['Nt.67'] + df['CA.22']) - df['Nt.67'].shift(1)
    
    # CA.25: Group 2 Formation (%):
    df['CA.25'] = df['CA.24'] / df['BS.13'].shift(1)
    
    # Reset Index
    df = df.reset_index(drop=True)
    return df

#%% Apply Calculate function to all dataframes
print("Calculating CA metrics for all data...")

dfcompaniesquarter = Calculate(dfcompaniesquarter)
dfcompaniesyear = Calculate(dfcompaniesyear)
dfsectorquarter = Calculate(dfsectorquarter)
dfsectoryear = Calculate(dfsectoryear)
dfsocbquarter = Calculate(dfsocbquarter)
dfsocbyear = Calculate(dfsocbyear)
dfprivate1quarter = Calculate(dfprivate1quarter)
dfprivate2quarter = Calculate(dfprivate2quarter)
dfprivate3quarter = Calculate(dfprivate3quarter)
dfprivate1year = Calculate(dfprivate1year)
dfprivate2year = Calculate(dfprivate2year)
dfprivate3year = Calculate(dfprivate3year)

#%% Merge dataset
print("Merging and finalizing datasets...")

dfsectoryear['Type'] = 'Sector'
dfsectorquarter['Type'] = 'Sector'
dfsectoryear = pd.concat([dfcompaniesyear, dfsectoryear, dfsocbyear, 
                          dfprivate1year, dfprivate2year, dfprivate3year], ignore_index=True)
dfsectorquarter = pd.concat([dfcompaniesquarter, dfsectorquarter, dfsocbquarter, 
                             dfprivate1quarter, dfprivate2quarter, dfprivate3quarter], ignore_index=True)

# Replace TICKER with Type when TICKER is longer than 3 characters
dfsectoryear.loc[dfsectoryear['TICKER'].str.len() > 3, 'TICKER'] = \
    dfsectoryear.loc[dfsectoryear['TICKER'].str.len() > 3, 'Type']
dfsectorquarter.loc[dfsectorquarter['TICKER'].str.len() > 3, 'TICKER'] = \
    dfsectorquarter.loc[dfsectorquarter['TICKER'].str.len() > 3, 'Type']

# Rename Date_Quarter to Year for yearly data for clarity
dfsectoryear = dfsectoryear.rename(columns={'Date_Quarter': 'Year'})

# Sort by TICKER and Year
dfsectoryear = dfsectoryear.sort_values(by=['TICKER', 'Year'])
dfsectorquarter = dfsectorquarter.sort_values(by=['TICKER', 'ENDDATE_x'])

#%% Save files
print("\nSaving final datasets...")

# Save files - dfsectoryear now includes forecast data if available
dfsectoryear.to_csv(os.path.join(data_dir, 'dfsectoryear.csv'), index=False)
dfsectorquarter.to_csv(os.path.join(data_dir, 'dfsectorquarter.csv'), index=False)

print(f"Files saved:")
print(f"  - dfsectoryear.csv: {len(dfsectoryear)} rows")
print(f"  - dfsectorquarter.csv: {len(dfsectorquarter)} rows")

# Summary statistics
if has_forecast:
    # Convert Year to int for comparison
    dfsectoryear['Year'] = dfsectoryear['Year'].astype(int)
    historical_rows = len(dfsectoryear[~dfsectoryear['Year'].isin([2025, 2026])])
    forecast_rows = len(dfsectoryear[dfsectoryear['Year'].isin([2025, 2026])])
    
    print(f"\nSummary:")
    print(f"  Historical rows (2018-2024): {historical_rows}")
    print(f"  Forecast rows (2025-2026): {forecast_rows}")
    print(f"  Total rows: {len(dfsectoryear)}")
    
    # Generate simple coverage report for forecast years
    print("\nForecast coverage summary:")
    forecast_years_data = dfsectoryear[dfsectoryear['Year'].isin([2025, 2026])]
    key_metrics = ['BS.13', 'BS.56', 'IS.22', 'IS.24', 'CA.3', 'CA.5', 'CA.16', 'CA.17']
    for metric in key_metrics:
        if metric in forecast_years_data.columns:
            coverage = forecast_years_data[metric].notna().sum()
            total = len(forecast_years_data)
            pct = (coverage / total * 100) if total > 0 else 0
            print(f"  {metric}: {coverage}/{total} ({pct:.1f}%)")
else:
    print(f"\nTotal rows (historical only): {len(dfsectoryear)}")

print("\nProcessing complete!")