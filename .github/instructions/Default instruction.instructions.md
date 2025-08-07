---
applyTo: '**/*.py'
---
## Coding Guidelines for Claude

When writing code for this repository:

1. **Jupyter/Interactive Style**:
   - Use `#%%` cell markers for code organization
   - Assume pandas, numpy, and plotly are already imported
   - Write code that can be run cell-by-cell in Jupyter

2. **Calculation Focus**:
   - Prioritize mathematical correctness and clarity
   - Use vectorized pandas operations
   - Don't add excessive try/except blocks
   - Assume data exists and is in expected format

3. **Data Analysis Patterns**:
   ```python
   # Good - direct calculation
   df['metric'] = df['revenue'] / df['assets']
   
   # Avoid - over-engineered
   def calculate_metric(df):
       if 'revenue' not in df.columns:
           raise ValueError("Missing revenue column")
       # ... more checks
   ```

4. **Variable Naming**:
   - Use descriptive names for financial metrics
   - Keep DataFrame names short (df_q, df_a, etc.)
   - Use standard financial abbreviations (ROE, ROA, NPAT)

5. **Output Style**:
   - Display DataFrames directly without wrapping
   - Use simple print statements for quick checks
   - Format numbers inline with f-strings when needed