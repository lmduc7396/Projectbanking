import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt

dfsectorquarter = pd.read_csv('./Data/dfsectorquarter.csv')
dfsectoryear = pd.read_csv('./Data/dfsectoryear.csv')
keyitem=pd.read_excel('./Data/Key_items.xlsx')

#Plot single ticker/ sector
def plot_single(df, X='None',Y=10,Z='NIM'):
    item=keyitem[keyitem['Name']==Z]['KeyCode']
    item=item.iloc[0]
    df=df.sort_values(by=['TICKER','ENDDATE_x'])
    if len(X)==3:
        df_temp=df[df.TICKER==X]
    else:
        df_temp=df[df['TICKER'].apply(len) >3]
        df_temp=df_temp[df_temp['Type']==X]
        df_temp=df_temp[df_temp['TICKER']==df_temp.iloc[0]['TICKER']]
    df_tempY=df_temp.tail(Y)
    #Draw plot
    fig = go.Figure(
        data=[
            go.Bar(
                x=df_tempY['Date_Quarter'],
                y=df_tempY[item],
            )
        ]
    )
    fig.update_layout(
        title=f'{X} {Z} by Quarter',
        xaxis_title='Date_Quarter',
        yaxis_title=item
    )
    fig.update_yaxes(tickformat=".2%")
    fig.show()

plot_single(dfsectorquarter,X='MBB',Z='NIM')
plot_single(dfsectorquarter,X='Sector',Z='CA.13')
plot_single(dfsectoryear, X='VPB',Y=10, Z='CA.13')


#Plot comparison of values for multiple tickers
def plot_compare(df, value_col, *tickers):
    """
    Plots the comparison of value_col for any number of tickers over time.
    
    Parameters:
    df : pandas.DataFrame
        Your DataFrame, must include columns: 'TICKER', 'Date_Quarter', value_col
    value_col : str
        The name of the column to plot values for.
    *tickers : str
        Any number of ticker names to compare.
    """
    if len(tickers) == 1 and isinstance(tickers[0], (list, tuple)):
        # User might pass a list, unpack it
        tickers = tickers[0]
    
    # Filter the DataFrame for selected tickers
    df_selected = df[df['TICKER'].isin(tickers)]
    
    # Ensure dates are sorted and remove rows with missing dates
    df_selected = df_selected.sort_values(by='ENDDATE_x')
    df_selected = df_selected.dropna(subset=['ENDDATE_x'])
    df_selected = df_selected.groupby(['TICKER', 'Date_Quarter'], as_index=False).first()
    # Pivot so each ticker becomes a column, indexed by Date_Quarter
    pivot = df_selected.pivot(index='Date_Quarter', columns='TICKER', values=value_col)
    
    # Extract year and quarter for proper sorting
    pivot['Year'] = pivot.index.str[-2:].astype(int)
    pivot['Quarter'] = pivot.index.str[:1].astype(int)
    
    # Sort by year, then by quarter
    pivot = pivot.sort_values(by=['Year', 'Quarter'])
    
    # Remove rows before year 18 (e.g., 2018)
    pivot = pivot[pivot['Year'] >= 18]
    
    # Drop helper columns
    pivot = pivot.drop(columns=['Year', 'Quarter'])
    
    #Set up gradient color
    import matplotlib
    import matplotlib.colors as mcolors
    n = len(pivot.columns)
    cmap = mcolors.LinearSegmentedColormap.from_list("custom_gradient", ['#405A52', '#C4FDE6'])
    color_list = [matplotlib.colors.rgb2hex(cmap(i/(n-1))) for i in range(n)]

    # Plot
    fig = go.Figure()
    for idx, col in enumerate(pivot.columns):
        fig.add_trace(go.Scatter(
            x=pivot.index,
            y=pivot[col],
            mode='lines+markers',
            name=col,
            line=dict(color=color_list[idx], width=3),
            marker=dict(color=color_list[idx])
        ))

    fig.update_layout(
        template='plotly_white',
        title=f'Comparison: {" vs ".join(tickers)}',
        xaxis_title='Quarter',
        yaxis_title=value_col,
        legend_title="Ticker"
    )
    fig.show()
plot_compare(dfcompaniesquarter, 'CA.13', 'MBB', 'ACB', 'VPB', 'HDB')
# %%
