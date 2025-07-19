#%%

import openai
import pandas as pd
import streamlit as st

# 1. Dataframe preparation

df_quarter = pd.read_csv('Data/dfsectorquarter.csv')
df_year = pd.read_csv('Data/dfsectoryear.csv')
keyitem=pd.read_excel('Data/Key_items.xlsx')



def openai_comment(X):
    def get_data(X):
        cols_keep = pd.DataFrame({
        'Name': [
            'Loan', 'TOI', 'Provision expense', 'PBT', 'ROA', 'ROE', 'NIM', 'Loan yield',
            'NPL', 'NPL Formation (%)', 'GROUP 2', 'G2 Formation (%)',
            'NPL Coverage ratio', 'Provision/ Total Loan'
        ]
        })
        cols_code_keep = cols_keep.merge(keyitem, on='Name', how='left')
        cols_keep_final = ['Date_Quarter'] + cols_code_keep['KeyCode'].tolist()
        rename_dict = dict(zip(cols_code_keep['KeyCode'], cols_code_keep['Name']))


        df_temp = df_quarter[df_quarter['TICKER'] == X]
        df_temp = df_temp[cols_keep_final]

        df_out = df_temp.rename(columns=rename_dict).tail(6).T
        df_out.columns = df_out.iloc[0]
        df_out = df_out[1:]
        return df_out


# 3. Build the analysis prompt
    client = openai.OpenAI(
        api_key="REMOVEDproj-SY3Eu0hMa2lylml4FaIS1trKex5vi5kf886-MiJOmmm7rzxpK5fkztdvgUFPJnoUkwLLOhwdoFT3BlbkFJQiHv3oWBhSwESwg_Doyj1dXsKs5NMU46yTzxRAkk3jx3aU3QzdSp3WcZ-w8LbHESeEcsRGpWYA"
    )
    prompt = f"""
    You are a financial analyst, looking for investment recommendations on the bank financial performance.
    Analyze this bank for me
    Your response MUST be in bullet points format, be concise with about 3-4 bullet points and maximum 300 words.
    Focus on trend and the most recent quarter's changes. Don't just describe the number for me but intepret further

    Data: The bank: {X}
    {get_data(X).to_markdown(index=True, tablefmt='grid')}
    """

    # 4. Send to OpenAI
    response = client.chat.completions.create(
        model="gpt-4.1",   # or "gpt-4-turbo"
        messages=[
            {"role": "system", "content": "You are a financial analyst."},
            {"role": "user", "content": prompt}
        ]
    )

    print(response.choices[0].message.content)

openai_comment('ACB')