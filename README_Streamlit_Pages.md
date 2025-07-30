# Banking Analysis Dashboard

A comprehensive Streamlit application for analyzing banking sector financial data with interactive visualizations and AI-powered insights.

## Features

### 🏠 **Home Page**
- Dashboard overview with key metrics
- Data summary and navigation guide
- Quick access to all analysis tools

### 📊 **Banking Plot**
- Interactive visualization of banking metrics
- Compare multiple banks or bank types  
- Customizable time periods and metrics
- Support for both quarterly and yearly data

### 📋 **Company Table**
- Detailed financial tables for individual banks or sectors
- Growth analysis (QoQ/YoY/YTD)
- Earnings metrics and financial ratios
- Stock price visualization for individual tickers

### 🤖 **OpenAI Comment**
- AI-powered analysis and commentary
- Bank performance insights
- Sector comparison analysis
- Generate detailed reports using OpenAI

## File Structure

```
├── Github.py                    # Main application (Home page)
├── pages/                       # Streamlit pages
│   ├── 1_📊_Banking_Plot.py
│   ├── 2_📋_Company_Table.py  
│   └── 3_🤖_OpenAI_Comment.py
├── Streamlit pages/             # Function modules
│   ├── Plotchart.py            # Banking plot functions
│   ├── Banking_table.py        # Table generation functions
│   └── OpenAIcomments          # OpenAI integration functions
├── Utilities/                   # Utility functions
│   └── Stockcandle.py          # Stock price chart functions
├── Data/                        # Data files
│   ├── dfsectorquarter.csv     # Quarterly banking data
│   ├── dfsectoryear.csv        # Yearly banking data
│   └── Key_items.xlsx          # Metric definitions
└── requirements.txt            # Python dependencies
```

## How to Run

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   - Create a `.env` file in the project root
   - Add your OpenAI API key: `OPENAI_API_KEY=your_key_here`

3. **Run the application:**
   ```bash
   streamlit run Github.py
   ```

4. **Navigate the app:**
   - Use the sidebar navigation to switch between pages
   - Select database type (Quarterly/Yearly) in the sidebar
   - Configure analysis options on each page

## Data Requirements

- **Quarterly Data**: `dfsectorquarter.csv` with banking financial statements
- **Yearly Data**: `dfsectoryear.csv` with annual financial performance  
- **Key Items**: `Key_items.xlsx` with metric definitions and codes
- **Bank Types**: Sector, SOCB, Private_1, Private_2, Private_3
- **Individual Tickers**: 3-letter bank codes

## Page Navigation

The application uses Streamlit's native multipage functionality:
- **Home**: Overview and data summary
- **Banking Plot**: Interactive visualizations
- **Company Table**: Financial analysis tables
- **OpenAI Comment**: AI-powered insights

Each page loads independently with shared data and maintains consistent navigation through the sidebar.
