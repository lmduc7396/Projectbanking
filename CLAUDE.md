# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Vietnamese banking analysis dashboard that combines financial data visualization with AI-powered insights using OpenAI's API. The system processes quarterly and yearly banking data to generate automated comments and comprehensive sector analysis.

## Critical Setup Requirements

Before running any component:
1. Ensure `OPENAI_API_KEY` is set in `.env` file
2. Install dependencies: `pip install -r requirements.txt streamlit`

## Common Commands

### Running the Application
```bash
# Main Streamlit dashboard
streamlit run streamlit_app.py

# Unified generator script (recommended)
python scripts/run_generators.py

# Individual generators
python generators/bulk_comment_generator.py
python generators/bulk_quarterly_analysis_generator.py
```

### Data Generation Workflows
```bash
# Generate comments for specific timeframe (e.g., Q1-Q3 2024)
# Use run_generators.py and select option 4 for quick generation

# Generate all comments and analysis
# Use run_generators.py and select option 3 for full pipeline
```

## Architecture & Key Components

### Data Flow Architecture
1. **Raw Data** (`Data/*.csv`, `Data/*.xlsx`) → 
2. **Generators** (create AI comments/analysis) → 
3. **Cache Files** (`banking_comments.xlsx`, `quarterly_analysis_results.xlsx`) →
4. **Streamlit Dashboard** (visualization and management)

### Quarter Format Convention
All quarter strings use format `XQyy` where:
- X = quarter number (1-4)
- yy = 2-digit year (e.g., "1Q24" = Q1 2024)

### Cross-Platform Path Handling
The system auto-detects OS and adjusts paths:
- Windows: `C:\Users\ducle\OneDrive\Work-related\projectbanking`
- Mac/Linux: Current working directory

Use `utilities.path_utils` for consistent path resolution.

### Generator Classes Architecture

Both generators follow similar patterns:
```python
class Generator:
    def __init__(self)  # Load data, setup OpenAI client
    def get_quarters_in_range(start, end)  # Filter quarters
    def generate_bulk_*(start, end, overwrite)  # Main generation
    def _save_progress()  # Incremental saving
```

Key parameters:
- `start_quarter`/`end_quarter`: None means earliest/latest
- `overwrite_existing`: Controls regeneration of existing data

### Streamlit Pages Structure
Pages in `pages/` folder are numbered for ordering:
- `1_📊_Banking_Plot.py` - Interactive charts
- `2_📋_Company_Table.py` - Performance tables  
- `3_🤖_OpenAI_Comment.py` - Generate individual comments
- `4_🔧_Comment_Management.py` - Manage all comments
- `5_🔍_Quarterly_Analysis.py` - View sector analysis

Each page uses `st.session_state` for data sharing and imports utilities from `utilities/` module.

### Utilities Module Organization
- `quarter_utils.py` - Quarter string manipulation (sorting, numeric conversion)
- `path_utils.py` - Cross-platform path resolution
- `banking_analysis.py` - Banking metrics calculations
- `openai_utils.py` - OpenAI API wrappers and prompt templates
- `banking_table.py`, `plot_chart.py` - Visualization helpers
- `openai_comments.py` - Comment generation logic

### Data Schema

Key columns in CSV files:
- `TICKER`: Bank code (3 chars for individual banks)
- `Type`: Bank sector classification
- `Date_Quarter`: Quarter in XQyy format
- KeyCode columns: Financial metrics (mapped via Key_items.xlsx)

Generated cache files:
- `banking_comments.xlsx`: TICKER, SECTOR, QUARTER, COMMENT, GENERATED_AT
- `quarterly_analysis_results.xlsx`: QUARTER, BANK_COUNT, KEY_CHANGES, INDIVIDUAL_HIGHLIGHTS, FORWARD_OUTLOOK, FULL_ANALYSIS, GENERATED_AT

## Code Style Guidelines

### Jupyter-Style Interactive Development
- Use `#%%` cell markers to enable interactive execution in VS Code
- Structure code in logical blocks that can be run independently
- Include intermediate print statements for debugging/verification
- Keep data exploration and transformation visible for step-by-step checking

### Pandas Operations
- **Always use vectorized operations** instead of loops when working with DataFrames
- Prefer: `df['new_col'] = df['col1'] * df['col2']`
- Avoid: `for i in range(len(df)): df.loc[i, 'new_col'] = ...`
- Use `.apply()` with lambda only when vectorization isn't possible
- Chain operations where readable: `df.groupby().agg().reset_index()`

### Simple Formula Style
- **Write calculations as clear, simple formulas** that match business logic
- Use descriptive variable names that match financial terminology
- Examples:
  ```python
  df['gross_profit'] = df['revenue'] - df['cogs']
  df['net_margin'] = df['net_income'] / df['revenue']
  df['roa'] = df['net_income'] / df['total_assets']
  df['loan_growth_qoq'] = df['loan'].pct_change()
  df['provision_coverage'] = df['provision'] / df['npl']
  ```
- Avoid complex nested calculations - break them into intermediate steps:
  ```python
  # Good - clear steps
  df['operating_income'] = df['revenue'] - df['operating_expenses']
  df['ebit'] = df['operating_income'] - df['depreciation']
  df['net_income'] = df['ebit'] - df['interest'] - df['tax']
  
  # Avoid - hard to understand
  df['net_income'] = df['revenue'] - df['operating_expenses'] - df['depreciation'] - df['interest'] - df['tax']
  ```

### Class Design Philosophy
- **Avoid classes unless managing state or encapsulation is essential**
- Prefer simple functions for data transformations
- Use classes only for:
  - Generators that maintain configuration and state (e.g., BulkCommentGenerator)
  - Components that need initialization and multiple related methods
- For single-use operations, use standalone functions

### Testing Approach
- **No edge case testing required** - focus on main functionality
- Assume data inputs are valid and properly formatted
- Handle obvious errors (missing files, API keys) but don't over-engineer
- Trust that data files follow expected schema

### No Emojis in Code
- **Never use emojis in any code files** - keep all code professional and clean
- No emojis in:
  - Comments or docstrings
  - Print statements or log messages
  - Variable names or function names
  - Error messages or success indicators
- Use plain text alternatives:
  - Instead of "✓" or "✅" use "Done" or "Complete"
  - Instead of "✗" or "❌" use "Failed" or "Error"
  - Instead of "📊" use "[Plot]" or "Chart:"
  - Instead of "⚠️" use "Warning:" or "Alert:"

### Code Organization Examples
```python
#%% Load and prepare data
df = pd.read_csv('data.csv')
print(f"Loaded {len(df)} rows")

#%% Transform data - vectorized approach
df['quarter_numeric'] = df['Date_Quarter'].apply(quarter_to_numeric)
df['growth'] = df.groupby('TICKER')['value'].pct_change()

#%% Generate results
results = df[df['quarter_numeric'] > 20240].groupby('TICKER').agg({
    'growth': 'mean',
    'value': 'last'
})
print(results.head())
```

## Important Considerations

### Rate Limiting
- OpenAI API calls include `time.sleep(0.5)` between requests
- Generators save progress every 10 items to prevent data loss

### Error Handling
- Missing data files will raise FileNotFoundError with specific file paths
- API failures are caught and logged but don't stop bulk processing
- Incremental saves ensure partial progress is preserved

### Performance Optimization
- Comments are cached in `banking_comments.xlsx` to avoid regeneration
- Use `overwrite_existing=False` to skip existing data
- Streamlit uses `@st.cache_data` for data loading

### Windows vs Mac/Linux Differences
- File paths are handled automatically via `utilities.path_utils`
- Always use forward slashes in code; they're converted as needed
- CSV/Excel reading is consistent across platforms