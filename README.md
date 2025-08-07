# Banking Analysis Project

A comprehensive banking analysis dashboard with AI-powered insights using OpenAI's API.

## 📁 Project Structure

```
.
├── streamlit_app.py           # Main Streamlit application
├── requirements.txt           # Python dependencies
├── .env                      # Environment variables (not in repo)
│
├── Data/                     # Data files and datasets
│   ├── dfsectorquarter.csv
│   ├── dfsectoryear.csv
│   ├── Key_items.xlsx
│   ├── Bank_Type.xlsx
│   ├── banking_comments.xlsx
│   └── ...
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
├── scripts/                  # Utility scripts
│   ├── run_bulk_generator.py         # Script to run bulk comment generation
│   └── prepare_data.py              # Data preparation utilities
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

3. Set up environment variables:
Create a `.env` file in the project root with:
```
OPENAI_API_KEY=your_api_key_here
```

### Running the Application

#### Streamlit Dashboard
```bash
streamlit run streamlit_app.py
```

#### Bulk Comment Generation
```bash
python generators/bulk_comment_generator.py
```

#### Quarterly Analysis Generation
```bash
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

## 📝 Data Files

- `dfsectorquarter.csv`: Quarterly banking sector data
- `dfsectoryear.csv`: Yearly banking sector data
- `Key_items.xlsx`: Key item code mappings
- `Bank_Type.xlsx`: Bank type classifications
- `banking_comments.xlsx`: Generated AI comments cache

## 🔧 Configuration

The project supports both Windows and Mac/Linux environments with automatic path detection.

### Windows Path
```
C:\Users\ducle\OneDrive\Work-related\VS - Code project
```

### Mac/Linux Path
Current working directory structure

## 📄 License

[Add your license information here]

## 👥 Contributors

[Add contributor information here]