# Banking Analysis Project

A comprehensive banking analysis dashboard with AI-powered insights using OpenAI's API.

## 📁 Project Structure (SQL-first)

```
.
├── streamlit_app.py           # Main Streamlit application
├── requirements.txt           # Python dependencies
├── .env                      # Environment variables (not in repo)
│
├── Data/                     # Legacy reference files (kept for staging/backfill only)
│   ├── Bank_Type.xlsx
│   ├── Key_items.xlsx
│   └── ... (other historical files no longer the primary source)
│
├── generators/               # Bulk generation scripts
│   ├── bulk_comment_generator.py      # Generate AI comments for all banks/quarters
│   └── bulk_quarterly_analysis_generator.py  # Generate quarterly analysis reports
│
├── pages/                    # Streamlit multipage app pages
│   ├── 1_Banking_Plot.py             # Interactive banking metrics visualization
│   ├── 2_Company_Table.py            # Company performance tables
│   ├── 3_OpenAI_Comment.py           # AI-powered banking comments
│   ├── 4_Comment_Management.py       # Manage and export comments
│   └── 5_Quarterly_Analysis.py       # Quarterly sector analysis
│
├── scripts/                  # ETL jobs feeding the warehouse
│   ├── run_generators.py
│   ├── prepare_data.py              # Reads legacy SQL → dbo.BankingMetrics etc.
│   ├── Prepare_earnings_driver.py   # Writes driver tables (EarningsQuality*)
│   └── prepare_valuation.py         # Loads valuation tables
│
└── utilities/               # Reusable utility modules
    ├── __init__.py
    ├── quarter_utils.py              # Quarter handling and sorting functions
    ├── path_utils.py                 # Cross-platform path utilities
    ├── banking_analysis.py          # Banking analysis functions
    ├── banking_table.py             # Banking table generation
    ├── plot_chart.py                # Plotting utilities
    ├── openai_utils.py              # OpenAI API utilities
    ├── openai_comments.py           # Comment generation logic
    ├── fetch_price_api.py           # Stock price fetching
    └── stock_candle.py              # Stock candlestick charts
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- OpenAI API key

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd "VS - Code project"
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables (local) or Streamlit secrets (cloud):
```
OPENAI_API_KEY=your_api_key_here
SOURCE_DB_CONNECTION_STRING="SERVER=tcp:...;DATABASE=...;UID=...;PWD=...;Connection Timeout=30;"
TARGET_DB_CONNECTION_STRING="DRIVER={ODBC Driver 18 for SQL Server};SERVER=sqls-dclab.database.windows.net,1433;DATABASE=dclab;UID=dclab_readonly;PWD=your_password;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
```
Connection strings may retain `DRIVER=...` segments for compatibility, but only the fields above are consumed by the pyodbc client.
Ensure the Microsoft ODBC Driver 17 or 18 for SQL Server is installed so the connector can establish connections successfully.

For Streamlit deployments, set the same value in `.streamlit/secrets.toml` using the `AZURE_SQL_ODBC` key:
```
AZURE_SQL_ODBC = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=sqls-dclab.database.windows.net,1433;DATABASE=dclab;UID=dclab_readonly;PWD=your_password;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
```
Additional fallback keys include `AZURE_SQL_CONNECTION_STRING`, `TARGET_DB_CONNECTION_STRING`, `DC_DB_STRING_MASTER`, and `DB_AILAB_CONN`.

### Running the Application

#### Streamlit Dashboard
```bash
streamlit run streamlit_app.py
```

#### Bulk Comment Generation
```bash
# Recommended unified runner
python scripts/run_generators.py

# Or run specific generator directly
python generators/bulk_comment_generator.py
```

#### Quarterly Analysis Generation
```bash
# Recommended unified runner
python scripts/run_generators.py

# Or run specific generator directly
python generators/bulk_quarterly_analysis_generator.py
```

## 📊 Features

### 1. Banking Plot (📊)
- Interactive visualization of banking metrics
- Compare multiple banks or bank types
- Customizable time periods and metrics
- Support for quarterly and yearly data

### 2. Company Table (📋)
- Detailed performance tables for individual banks
- Growth metrics (QoQ, YoY)
- Key financial ratios
- Stock price integration

### 3. OpenAI Comments (🤖)
- AI-powered analysis of banking performance
- Automated comment generation
- Caching system for efficiency
- Regeneration capability

### 4. Comment Management (🔧)
- View and manage all generated comments
- Export to Excel
- Quarterly analysis generation
- Comment history tracking

### 5. Quarterly Analysis (🔍)
- Comprehensive sector analysis
- Individual bank highlights
- Forward outlook
- Trend identification

## 🛠️ Utilities

### Quarter Utilities
- `quarter_sort_key()`: Convert quarter strings to sortable tuples
- `quarter_to_numeric()`: Convert quarters to numeric format
- `sort_quarters()`: Sort quarters chronologically

### Path Utilities
- `get_data_path()`: Get platform-specific data directory
- `get_comments_file_path()`: Get banking comments file path
- `get_project_root()`: Get project root directory

### Banking Analysis
- `create_banking_table()`: Generate banking analysis tables
- `get_bank_sector_mapping()`: Map banks to sectors

### OpenAI Utilities
- `get_openai_client()`: Initialize OpenAI client
- `load_cached_comment()`: Load cached comments
- `save_comment_to_cache()`: Save generated comments
- `generate_banking_comment_prompt()`: Create analysis prompts
- `generate_quarterly_analysis_prompt()`: Create quarterly prompts

## 📝 Data Files (Primary)

- `dfsectorquarter.parquet`: Quarterly banking sector data
- `dfsectoryear.parquet`: Yearly banking sector data
- `dfsectorforecast.parquet`: Forecasts (e.g., 2025–2026)
- `Valuation_banking.parquet`: Valuation time series
- `earnings_quality_quarterly.parquet` and `earnings_quality_yearly.parquet`: Driver datasets
- `banking_comments.parquet`: Generated AI comments cache
- `quarterly_analysis_results.parquet`: Sector analysis cache
- Reference (Excel, unchanged): `Bank_Type.xlsx`, `Key_items.xlsx`

First-time setup: run `python scripts/prepare_data.py`, `python scripts/Prepare_earnings_driver.py`, and `python scripts/prepare_valuation.py` to generate all Parquet files.

## 🔧 Configuration

The project supports both Windows and Mac/Linux environments with automatic path detection.

### Windows Path
```
C:\Users\ducle\OneDrive\Work-related\VS - Code project
```

### Mac/Linux Path
Current working directory structure

## 🔗 Dependency Map (Pages → Utilities)

- `pages/1_Banking_Plot.py`:
  - Uses: `utilities.quarter_utils`, `utilities.banking_analysis`, `utilities.plot_chart`, `utilities.path_utils`
- `pages/2_Company_Table.py`:
  - Uses: `utilities.banking_table`, `utilities.quarter_utils`, `utilities.path_utils`
- `pages/3_OpenAI_Comment.py`:
  - Uses: `utilities.openai_utils`, `utilities.openai_comments`, `utilities.path_utils`
- `pages/4_Comment_Management.py`:
  - Uses: `utilities.openai_utils`, `utilities.path_utils`
- `pages/5_Quarterly_Analysis.py`:
  - Uses: `utilities.openai_utils`, `utilities.openai_comments`, `utilities.banking_analysis`, `utilities.path_utils`
- `streamlit_app.py` (entry):
  - Orchestrates multipage app; initializes shared state; delegates to pages.

Utilities common patterns:
- `utilities/Banking_MCP.py`: MCP tools with lazy loading + 5-minute result TTL.
- `utilities/path_utils.py`: Cross-platform project/data path resolution.
- `utilities/quarter_utils.py`: Quarter parsing/sorting and conversion.

## 📄 License

[Add your license information here]

## 👥 Contributors

[Add contributor information here]
