import streamlit as st
import pandas as pd
import os
import subprocess
import time
from datetime import datetime
import sys

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import utilities
from utilities import quarter_to_numeric

def show_comment_management():
    st.title("🤖 Banking Comment Management")
    st.markdown("Manage bulk generation and cached comments for banking analysis")
    
    # Check if comments file exists
    comments_file = r"c:\Users\ducle\OneDrive\Work-related\VS - Code project\Data\banking_comments.xlsx"
    comments_exist = os.path.exists(comments_file)
    
    # Sidebar for navigation
    st.sidebar.subheader("Comment Management")
    tab = st.sidebar.radio("Choose Action", [
        "📊 View Cached Comments", 
        "🔄 Bulk Generation", 
        "📈 Statistics",
        "🗑️ Manage Cache"
    ])
    
    if tab == "📊 View Cached Comments":
        st.header("Cached Comments Overview")
        
        if comments_exist:
            try:
                comments_df = pd.read_excel(comments_file)
                
                # Display summary statistics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Comments", len(comments_df))
                with col2:
                    st.metric("Unique Banks", comments_df['TICKER'].nunique())
                with col3:
                    st.metric("Unique Quarters", comments_df['QUARTER'].nunique())
                with col4:
                    # Convert GENERATED_DATE to datetime for finding the latest
                    if not comments_df.empty:
                        comments_df_temp = comments_df.copy()
                        comments_df_temp['GENERATED_DATE'] = pd.to_datetime(comments_df_temp['GENERATED_DATE'])
                        latest_date = comments_df_temp['GENERATED_DATE'].max().strftime('%Y-%m-%d')
                    else:
                        latest_date = "N/A"
                    st.metric("Latest Update", latest_date)
                
                # Filter options
                st.subheader("Filter Comments")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    selected_ticker = st.selectbox(
                        "Select Bank:", 
                        ["All"] + sorted(comments_df['TICKER'].unique().tolist())
                    )
                
                with col2:
                    selected_sector = st.selectbox(
                        "Select Sector:", 
                        ["All"] + sorted(comments_df['SECTOR'].unique().tolist())
                    )
                
                with col3:
                    selected_quarter = st.selectbox(
                        "Select Quarter:", 
                        ["All"] + sorted(comments_df['QUARTER'].unique().tolist(), reverse=True)
                    )
                
                # Apply filters
                filtered_df = comments_df.copy()
                if selected_ticker != "All":
                    filtered_df = filtered_df[filtered_df['TICKER'] == selected_ticker]
                if selected_sector != "All":
                    filtered_df = filtered_df[filtered_df['SECTOR'] == selected_sector]
                if selected_quarter != "All":
                    filtered_df = filtered_df[filtered_df['QUARTER'] == selected_quarter]
                
                # Display filtered results
                st.subheader(f"Comments ({len(filtered_df)} results)")
                
                if not filtered_df.empty:
                    # Create a summary table
                    summary_df = filtered_df[['TICKER', 'SECTOR', 'QUARTER', 'GENERATED_DATE']].copy()
                    # Convert to datetime and format for display
                    summary_df['GENERATED_DATE'] = pd.to_datetime(summary_df['GENERATED_DATE']).dt.strftime('%Y-%m-%d %H:%M')
                    
                    # Display table with row selection
                    selected_rows = st.dataframe(
                        summary_df,
                        use_container_width=True,
                        hide_index=True,
                        on_select="rerun",
                        selection_mode="single-row"
                    )
                    
                    # Display selected comment
                    if selected_rows and hasattr(selected_rows, 'selection') and selected_rows.selection.rows:
                        selected_idx = selected_rows.selection.rows[0]
                        selected_comment = filtered_df.iloc[selected_idx]
                        
                        st.subheader(f"Analysis: {selected_comment['TICKER']} - {selected_comment['QUARTER']}")
                        st.info(f"Generated: {selected_comment['GENERATED_DATE']} | Sector: {selected_comment['SECTOR']}")
                        
                        with st.container():
                            st.markdown(selected_comment['COMMENT'])
                        
                        # Option to delete this comment
                        if st.button("🗑️ Delete This Comment", key=f"delete_{selected_comment['TICKER']}_{selected_comment['QUARTER']}"):
                            if delete_comment(selected_comment['TICKER'], selected_comment['QUARTER']):
                                st.success("Comment deleted successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to delete comment")
                
                else:
                    st.info("No comments found matching the selected filters.")
                    
            except Exception as e:
                st.error(f"Error loading comments: {e}")
        else:
            st.info("No cached comments found. Run bulk generation first.")
    
    elif tab == "🔄 Bulk Generation":
        st.header("Bulk Comment Generation")
        
        # Load data to show statistics
        try:
            df_quarter = pd.read_csv(r"c:\Users\ducle\OneDrive\Work-related\VS - Code project\Data\dfsectorquarter.csv")
            bank_type = pd.read_excel(r"c:\Users\ducle\OneDrive\Work-related\VS - Code project\Data\Bank_Type.xlsx")
            
            # Get statistics
            all_banks = df_quarter[df_quarter['TICKER'].str.len() == 3]['TICKER'].nunique()
            all_quarters = df_quarter['Date_Quarter'].nunique()
            
            # Filter quarters from 2023
            quarters_2023_plus = [q for q in df_quarter['Date_Quarter'].unique() 
                                if quarter_to_numeric(q) >= 20231]
            
            total_combinations = all_banks * len(quarters_2023_plus)
            
            # Show generation statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Banks to Process", all_banks)
            with col2:
                st.metric("Quarters (2023+)", len(quarters_2023_plus))
            with col3:
                st.metric("Total Combinations", total_combinations)
            
            # Show existing progress
            if comments_exist:
                existing_comments = pd.read_excel(comments_file)
                existing_count = len(existing_comments)
                progress_pct = (existing_count / total_combinations) * 100
                
                st.subheader("Current Progress")
                st.progress(progress_pct / 100)
                st.info(f"Progress: {existing_count:,} / {total_combinations:,} comments ({progress_pct:.1f}%)")
                
                # Show recent activity
                if not existing_comments.empty:
                    # Convert GENERATED_DATE to datetime for proper sorting
                    existing_comments_copy = existing_comments.copy()
                    existing_comments_copy['GENERATED_DATE'] = pd.to_datetime(existing_comments_copy['GENERATED_DATE'])
                    recent_comments = existing_comments_copy.nlargest(5, 'GENERATED_DATE')
                    # Convert back to string for display
                    recent_comments['GENERATED_DATE'] = recent_comments['GENERATED_DATE'].dt.strftime('%Y-%m-%d %H:%M:%S')
                    st.subheader("Recent Comments")
                    st.dataframe(
                        recent_comments[['TICKER', 'SECTOR', 'QUARTER', 'GENERATED_DATE']],
                        use_container_width=True,
                        hide_index=True
                    )
            
            # Generation options
            st.subheader("Generation Options")
            
            col1, col2 = st.columns(2)
            with col1:
                generation_mode = st.radio(
                    "Generation Mode:",
                    ["Skip Existing (Recommended)", "Regenerate All", "Missing Only"]
                )
            
            with col2:
                estimate_cost = st.checkbox("Show Cost Estimate")
                if estimate_cost:
                    # Rough cost estimate (GPT-4 pricing as of 2024)
                    avg_tokens_per_request = 2000  # Rough estimate
                    cost_per_1k_tokens = 0.03  # GPT-4 input cost
                    estimated_cost = (total_combinations * avg_tokens_per_request * cost_per_1k_tokens) / 1000
                    st.warning(f"⚠️ Estimated API cost: ${estimated_cost:.2f}")
            
            # Warning about API costs and time
            st.warning("⚠️ **Important Notes:**\n"
                      "- This will make many API calls to OpenAI (costs money)\n"
                      "- Process may take several hours depending on the number of combinations\n"
                      "- Progress is saved incrementally\n"
                      "- Make sure you have sufficient OpenAI API credits")
            
            # Start generation button
            if st.button("🚀 Start Bulk Generation", type="primary"):
                if st.session_state.get('confirm_generation', False):
                    run_bulk_generation(generation_mode)
                else:
                    st.session_state['confirm_generation'] = True
                    st.warning("Click again to confirm and start generation")
            
            # Reset confirmation
            if st.button("Cancel"):
                st.session_state['confirm_generation'] = False
                st.info("Generation cancelled")
                
        except Exception as e:
            st.error(f"Error loading data for bulk generation: {e}")
    
    elif tab == "📈 Statistics":
        st.header("Comment Statistics")
        
        if comments_exist:
            try:
                comments_df = pd.read_excel(comments_file)
                
                # Overall statistics
                st.subheader("Overall Statistics")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Comments", len(comments_df))
                with col2:
                    st.metric("Unique Banks", comments_df['TICKER'].nunique())
                with col3:
                    st.metric("Unique Quarters", comments_df['QUARTER'].nunique())
                with col4:
                    avg_length = comments_df['COMMENT'].str.len().mean()
                    st.metric("Avg Comment Length", f"{avg_length:.0f} chars")
                
                # Comments by sector
                st.subheader("Comments by Sector")
                sector_counts = comments_df['SECTOR'].value_counts()
                st.bar_chart(sector_counts)
                
                # Comments by quarter
                st.subheader("Comments by Quarter")
                quarter_counts = comments_df['QUARTER'].value_counts()
                st.bar_chart(quarter_counts)
                
                # Timeline
                st.subheader("Generation Timeline")
                comments_df_timeline = comments_df.copy()
                comments_df_timeline['GENERATED_DATE'] = pd.to_datetime(comments_df_timeline['GENERATED_DATE'])
                comments_df_timeline['Generation_Day'] = comments_df_timeline['GENERATED_DATE'].dt.date
                daily_counts = comments_df_timeline['Generation_Day'].value_counts().sort_index()
                st.line_chart(daily_counts)
                
                # Missing data analysis
                st.subheader("Coverage Analysis")
                
                # Load original data to check coverage
                df_quarter = pd.read_csv(r"c:\Users\ducle\OneDrive\Work-related\VS - Code project\Data\dfsectorquarter.csv")
                all_banks = df_quarter[df_quarter['TICKER'].str.len() == 3]['TICKER'].unique()
                all_quarters = df_quarter['Date_Quarter'].unique()
                
                coverage_data = []
                for bank in all_banks:
                    bank_comments = comments_df[comments_df['TICKER'] == bank]
                    coverage_data.append({
                        'Bank': bank,
                        'Comments': len(bank_comments),
                        'Coverage': f"{len(bank_comments)}/{len(all_quarters)}"
                    })
                
                coverage_df = pd.DataFrame(coverage_data)
                st.dataframe(coverage_df, use_container_width=True, hide_index=True)
                
            except Exception as e:
                st.error(f"Error generating statistics: {e}")
        else:
            st.info("No comments data available for statistics.")
    
    elif tab == "🗑️ Manage Cache":
        st.header("Cache Management")
        
        if comments_exist:
            try:
                comments_df = pd.read_excel(comments_file)
                
                st.subheader("Cache Information")
                file_size = os.path.getsize(comments_file) / (1024 * 1024)  # MB
                st.info(f"Cache file size: {file_size:.2f} MB")
                
                # Cleanup options
                st.subheader("Cleanup Options")
                
                # Delete by date
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🗑️ Delete All Comments"):
                        if st.session_state.get('confirm_delete_all', False):
                            if delete_all_comments():
                                st.success("All comments deleted!")
                                st.rerun()
                            else:
                                st.error("Failed to delete comments")
                        else:
                            st.session_state['confirm_delete_all'] = True
                            st.warning("Click again to confirm deletion of ALL comments")
                
                with col2:
                    # Delete old comments
                    days_old = st.number_input("Delete comments older than (days):", min_value=1, value=30)
                    if st.button(f"🗑️ Delete Comments Older Than {days_old} Days"):
                        try:
                            cutoff_date = datetime.now() - pd.Timedelta(days=days_old)
                            comments_df_temp = comments_df.copy()
                            comments_df_temp['GENERATED_DATE'] = pd.to_datetime(comments_df_temp['GENERATED_DATE'])
                            old_comments = comments_df_temp[comments_df_temp['GENERATED_DATE'] < cutoff_date]
                            if len(old_comments) > 0:
                                st.warning(f"This will delete {len(old_comments)} comments. Click again to confirm.")
                            else:
                                st.info("No comments older than specified date.")
                        except Exception as e:
                            st.error(f"Error checking old comments: {e}")
                
                # Reset confirmations
                if st.button("Cancel All"):
                    st.session_state['confirm_delete_all'] = False
                    st.info("All confirmations cancelled")
                
            except Exception as e:
                st.error(f"Error managing cache: {e}")
        else:
            st.info("No cache file found.")
            
def delete_comment(ticker, quarter):
    """Delete a specific comment from the cache"""
    try:
        comments_file = r"c:\Users\ducle\OneDrive\Work-related\VS - Code project\Data\banking_comments.xlsx"
        comments_df = pd.read_excel(comments_file)
        
        # Remove the specific comment
        comments_df = comments_df[~((comments_df['TICKER'] == ticker) & (comments_df['QUARTER'] == quarter))]
        
        # Save back to file
        comments_df.to_excel(comments_file, index=False)
        return True
        
    except Exception as e:
        st.error(f"Error deleting comment: {e}")
        return False

def delete_all_comments():
    """Delete all cached comments"""
    try:
        comments_file = r"c:\Users\ducle\OneDrive\Work-related\VS - Code project\Data\banking_comments.xlsx"
        
        # Create empty DataFrame with same structure
        empty_df = pd.DataFrame(columns=['TICKER', 'SECTOR', 'QUARTER', 'COMMENT', 'GENERATED_DATE'])
        empty_df.to_excel(comments_file, index=False)
        
        return True
        
    except Exception as e:
        st.error(f"Error deleting all comments: {e}")
        return False

if __name__ == "__main__":
    show_comment_management()
