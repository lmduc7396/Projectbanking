#%%
import pandas as pd
import os

# Get the script directory and project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
data_dir = os.path.join(project_root, 'Data')

# Read files using absolute paths
dfis=pd.read_csv(os.path.join(data_dir, 'IS_Bank.csv'))
dfbs=pd.read_csv(os.path.join(data_dir, 'BS_Bank.csv'))
dfnt=pd.read_csv(os.path.join(data_dir, 'Note_Bank.csv'))
Type=pd.read_excel(os.path.join(data_dir, 'Bank_Type.xlsx'))
mapping=pd.read_excel(os.path.join(data_dir, 'IRIS KeyCodes - Bank.xlsx'))
dfwriteoff=pd.read_excel(os.path.join(data_dir, 'writeoffs.xlsx'))


#Clean writeoff 
write_offtemp=dfwriteoff[~(dfwriteoff['EXCHANGE']=='OTC')]
write_offtemp=write_offtemp.drop(columns=['EXCHANGE'])
write_off= write_offtemp.melt(id_vars = ['TICKER'], var_name = 'DATE', value_name='Nt.220')
write_off['YEARREPORT'] = write_off['DATE'].str[2:].astype(int)
write_off['LENGTHREPORT']=write_off['DATE'].str[1:2].astype(int)
write_off=write_off.drop(columns=['DATE'])
write_off=write_off.sort_values(['TICKER','YEARREPORT','LENGTHREPORT'])
#Create 5Q for writeoff
write_off['Nt.220'] = pd.to_numeric(write_off['Nt.220'], errors='coerce')
write_off['Nt.220']=write_off['Nt.220']*(10**6)
sum_rows=(
    write_off.groupby(['TICKER','YEARREPORT'],as_index=False)['Nt.220']
    .sum()
    .assign(LENGTHREPORT=5)
)
sum_rows=sum_rows[['TICKER','LENGTHREPORT','YEARREPORT','Nt.220']]
write_off=pd.concat([write_off,sum_rows],ignore_index=True)

#Replace name & merge & Sort by date
rename_dict=dict(zip(mapping['DWHCode'],mapping['KeyCode']))
dfis=dfis.rename(columns=rename_dict)
dfbs=dfbs.rename(columns=rename_dict)
dfnt=dfnt.rename(columns=rename_dict)

temp=pd.merge(dfis,dfbs,on=['TICKER','YEARREPORT','LENGTHREPORT'],how='inner')
temp2=pd.merge(temp,dfnt,on=['TICKER','YEARREPORT','LENGTHREPORT'],how='inner')
temp3=pd.merge(temp2,Type,on=['TICKER'],how='left')
dfall=pd.merge(temp3,write_off,on=['TICKER','YEARREPORT','LENGTHREPORT'],how='left')
dfall=dfall.sort_values(by=['TICKER','ENDDATE_x'])
bank_type=['SOCB','Private_1','Private_2','Private_3','Sector']

#Add in date columns
# For yearly data (LENGTHREPORT=5), use full year; for quarterly, use XQyy format
dfall['Date_Quarter'] = dfall.apply(
    lambda row: str(int(row['YEARREPORT'])) if row['LENGTHREPORT'] == 5 
    else str(int(row['LENGTHREPORT'])) + 'Q' + str(int(row['YEARREPORT']))[-2:], 
    axis=1
)
dfall=dfall.dropna(subset='ENDDATE_x')
dfall=dfall.groupby(['TICKER','Date_Quarter'],as_index=False).first()
dfall=dfall[dfall['YEARREPORT']>2017]
first_col=['YEARREPORT','LENGTHREPORT','ENDDATE_x','Type']
agg_dict={col:'sum' for col in dfall.columns if col not in ['Date_Quarter']+first_col}
for col in first_col:
    agg_dict[col] = 'first'


#Set up quarter only
dfcompaniesquarter=dfall[~(dfall.LENGTHREPORT>4)]
dfsectorquarter=dfcompaniesquarter.groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfsocbquarter=dfcompaniesquarter[dfcompaniesquarter['Type']=='SOCB'].groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfprivate1quarter=dfcompaniesquarter[dfcompaniesquarter['Type']=='Private_1'].groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfprivate2quarter=dfcompaniesquarter[dfcompaniesquarter['Type']=='Private_2'].groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfprivate3quarter=dfcompaniesquarter[dfcompaniesquarter['Type']=='Private_3'].groupby('Date_Quarter',as_index=False).agg(agg_dict)

#Set up yearly only - Date_Quarter now contains full year (e.g., "2024")
dfcompaniesyear=dfall[(dfall.LENGTHREPORT==5)]
dfsectoryear=dfcompaniesyear.groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfsocbyear=dfcompaniesyear[dfcompaniesyear['Type']=='SOCB'].groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfprivate1year=dfcompaniesyear[dfcompaniesyear['Type']=='Private_1'].groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfprivate2year=dfcompaniesyear[dfcompaniesyear['Type']=='Private_2'].groupby('Date_Quarter',as_index=False).agg(agg_dict)
dfprivate3year=dfcompaniesyear[dfcompaniesyear['Type']=='Private_3'].groupby('Date_Quarter',as_index=False).agg(agg_dict)

#Calculation all CA set up
def Calculate(df):
    df=df.sort_values(by=['TICKER','ENDDATE_x'])
    #CA.1 LDR: Bs.13/Bs.56
    df['CA.1'] = (df['BS.13'] / df['BS.56'])
    #CA.2 CASA: (Nt.121+Nt.124+Nt.125)/BS.56
    df['CA.2']=(df['Nt.121']+df['Nt.124']+df['Nt.125'])/df['BS.56']
    #CA.3 NPL: (Nt.68+Nt.69+Nt.70)/Nt.65
    df['CA.3']=(df['Nt.68']+df['Nt.69']+df['Nt.70'])/df['Nt.65']
    #CA.4 Abs NPL: Nt.68+Nt.69+Nt.70
    df['CA.4'] = df['Nt.68'] + df['Nt.69'] + df['Nt.70']
    #CA.5: Group 2: Nt.67/Nt.65
    df['CA.5'] = df['Nt.67'] / df['Nt.65']
    #CA.6: CIR: -IS.15/IS.14
    df['CA.6'] = -df['IS.15'] / df['IS.14']
    #CA.7: NPL Coverage Ratio Bs.14/(Nt.68+Nt.69+Nt.70)
    df['CA.7'] = -df['BS.14'] / (df['Nt.68'] + df['Nt.69'] + df['Nt.70'])
    #CA.8: Credit size: Bs.13+BS.16+Nt.97+Nt.112
    df['CA.8'] = df['BS.13'] + df['BS.16'] + df['Nt.97'] + df['Nt.112']
    #CA.9: Provision/ Total loan -Bs.14/Bs.13
    df['CA.9'] = -df['BS.14'] / df['BS.13']
    #CA.10: Leverage Bs.1/Bs.65
    df['CA.10'] = df['BS.1'] / df['BS.65']
    #CA.11: IEA (Bs.3+Bs.5+Bs.6+Bs.9+Bs.13+Bs.16+Bs.19+Bs.20)
    df['CA.11'] = (df['BS.3'] + df['BS.5'] + df['BS.6'] + df['BS.9'] + df['BS.13'] + df['BS.16'] + df['BS.19'] + df['BS.20'])
    #CA.12: IBL Bs.52+Bs.53+Bs.56+Bs.58+Bs.59
    df['CA.12'] = df['BS.52'] + df['BS.53'] + df['BS.56'] + df['BS.58'] + df['BS.59']
    #CA.13: NIM (IS.3/Average(CA.11, CA.11 t-1)*2)
    if df.iloc[0]['LENGTHREPORT'] < 5:
        df['CA.13'] = (df['IS.3'] / (df['CA.11'] + df['CA.11'].shift(1))) * 8
    else:
        df['CA.13'] = (df['IS.3'] / (df['CA.11'] + df['CA.11'].shift(1))) * 2
    #CA.14: Customer loan Bs.13+Bs.16
    df['CA.14'] = df['BS.13'] + df['BS.16']
    #CA.15: Loan yield Nt.143/CA.14
    if df.iloc[0]['LENGTHREPORT'] < 5:
        df['CA.15'] = (df['Nt.143'] / (df['CA.14'] + df['CA.14'].shift(1))) * 8
    else:
        df['CA.15'] = (df['Nt.143'] / (df['CA.14'] + df['CA.14'].shift(1))) * 2
    #CA.16: ROAA IS.22/BS.1
    if df.iloc[0]['LENGTHREPORT'] < 5:
        df['CA.16'] = (df['IS.22'] / (df['BS.1'] + df['BS.1'].shift(1))) * 8
    else:
        df['CA.16'] = (df['IS.22'] / (df['BS.1'] + df['BS.1'].shift(1))) * 2
    #CA.17: ROAE: IS.24/BS.65
    if df.iloc[0]['LENGTHREPORT'] < 5:
        df['CA.17'] = (df['IS.24'] / (df['BS.65'] + df['BS.65'].shift(1))) * 8
    else:
        df['CA.17'] = (df['IS.24'] / (df['BS.65'] + df['BS.65'].shift(1))) * 2
    #CA.18: Deposit balance Bs.3+Bs.5+Bs.6
    df['CA.18'] = df['BS.3'] + df['BS.5'] + df['BS.6']
    #CA.19: Deposit yield: Nt.144/ Ca.18
    if df.iloc[0]['LENGTHREPORT'] < 5:
        df['CA.19'] = (df['Nt.144'] / (df['CA.18'] + df['CA.18'].shift(1))) * 8
    else:
        df['CA.19'] = (df['Nt.144'] / (df['CA.18'] + df['CA.18'].shift(1))) * 2
    #CA.20: Fees Income/ Total asset Is.6/BS.1
    if df.iloc[0]['LENGTHREPORT'] < 5:
        df['CA.20'] = (df['IS.6'] / (df['BS.1'] + df['BS.1'].shift(1))) * 8
    else:
        df['CA.20'] = (df['IS.6'] / (df['BS.1'] + df['BS.1'].shift(1))) * 2
    #CA.21: Individual/ Total loan: Nt.89/BS.12
    df['CA.21'] = df['Nt.89'] / df['BS.12']
    #CA.22: NPL Formation:
    df['CA.22'] = (df['CA.4'] - df['Nt.220']) - (df['CA.4'].shift(1))
    #CA.23: NPL Formation (%):
    df['CA.23'] = df['CA.22'] / df['BS.13'].shift(1)
    #CA.24: Group 2 Formation
    df['CA.24'] = (df['Nt.67'] + df['CA.22']) - df['Nt.67'].shift(1)
    #CA.25: Group 2 Formation (%):
    df['CA.25'] = df['CA.24'] /  df['BS.13'].shift(1)
    #Reset Index
    df = df.reset_index(drop=True)
    return df

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

#Merge dataset
dfsectoryear['Type']='Sector'
dfsectorquarter['Type']='Sector'
dfsectoryear=pd.concat([dfcompaniesyear,dfsectoryear,dfsocbyear,dfprivate1year,dfprivate2year,dfprivate3year],ignore_index=True)
dfsectorquarter=pd.concat([dfcompaniesquarter,dfsectorquarter,dfsocbquarter,dfprivate1quarter,dfprivate2quarter,dfprivate3quarter],ignore_index=True)

# Replace TICKER with Type when TICKER is longer than 3 characters
dfsectoryear.loc[dfsectoryear['TICKER'].str.len() > 3, 'TICKER'] = dfsectoryear.loc[dfsectoryear['TICKER'].str.len() > 3, 'Type']
dfsectorquarter.loc[dfsectorquarter['TICKER'].str.len() > 3, 'TICKER'] = dfsectorquarter.loc[dfsectorquarter['TICKER'].str.len() > 3, 'Type']

# Rename Date_Quarter to Year for yearly data for clarity
dfsectoryear = dfsectoryear.rename(columns={'Date_Quarter': 'Year'})

#Sort by TICKER and Year
dfsectoryear = dfsectoryear.sort_values(by=['TICKER', 'Year'])
dfsectorquarter = dfsectorquarter.sort_values(by=['TICKER', 'ENDDATE_x'])

# Save files
dfsectoryear.to_csv(os.path.join(data_dir, 'dfsectoryear.csv'), index=False)
dfsectorquarter.to_csv(os.path.join(data_dir, 'dfsectorquarter.csv'), index=False)
