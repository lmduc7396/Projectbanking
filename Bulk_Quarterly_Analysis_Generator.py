#%%
#!/usr/bin/env python3
"""
Bulk Quarterly Analysis Generator
Generates AI analysis for all quarters from 1Q24 to current and saves to Excel file
"""

import pandas as pd
import os
import sys
from datetime import datetime
import openai
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

# Import utilities
from utilities import quarter_sort_key, sort_quarters
from Check_laptopOS import get_data_path, get_comments_file_path

class BulkQuarterlyAnalysisGenerator:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = openai.OpenAI(api_key=self.api_key)
        self.comments_file = get_comments_file_path()
        self.analysis_file = os.path.join(get_data_path(), "quarterly_analysis_results.xlsx")
        
        print(f"Comments file: {self.comments_file}")
        print(f"Analysis results will be saved to: {self.analysis_file}")
    
    def load_comments_data(self):
        """Load banking comments data"""
        if not os.path.exists(self.comments_file):
            raise FileNotFoundError(f"Comments file not found: {self.comments_file}")
        
        return pd.read_excel(self.comments_file)
    
    def get_quarters_to_analyze(self, comments_df):
        """Get all quarters from 1Q24 onwards"""
        all_quarters = comments_df['QUARTER'].unique().tolist()
        sorted_quarters = sort_quarters(all_quarters)
        
        # Filter quarters from 1Q24 onwards
        quarters_to_analyze = []
        for quarter in sorted_quarters:
            # Extract year from quarter (e.g., "1Q24" -> 24)
            if 'Q' in quarter:
                year_part = quarter.split('Q')[1]
                try:
                    year = int(year_part)
                    if year >= 24:  # 2024 onwards
                        quarters_to_analyze.append(quarter)
                except ValueError:
                    continue
        
        return quarters_to_analyze
    
    def load_existing_analysis(self):
        """Load existing analysis results if file exists"""
        if os.path.exists(self.analysis_file):
            try:
                return pd.read_excel(self.analysis_file)
            except Exception as e:
                print(f"Error loading existing analysis file: {e}")
                return pd.DataFrame()
        return pd.DataFrame()
    
    def analyze_quarter(self, quarter_comments_df, quarter):
        """Analyze a single quarter using ChatGPT"""
        try:
            print(f"  Analyzing {len(quarter_comments_df)} comments...")
            
            # Prepare comments data for analysis
            comments_text = ""
            bank_count = 0
            for _, row in quarter_comments_df.iterrows():
                comments_text += f"\n\n**{row['TICKER']} ({row['SECTOR']}):**\n{row['COMMENT']}"
                bank_count += 1
            
            # Create the analysis prompt
            prompt = f"""
            You are a senior banking analyst with expertise in Vietnamese banking sector. Please analyze the following {bank_count} banking comments for {quarter} and provide a comprehensive analysis.

            BANKING COMMENTS FOR {quarter}:
            {comments_text}

            Please provide analysis in the following three sections:

            ## 1. KEY CHANGES SUMMARY
            Summarize the most significant trends and changes across all banks in this quarter. Focus on:
            - Overall banking sector performance and market conditions
            - Common themes and patterns across different bank types
            
            ## 2. SENTIMENT ANALYSIS & NOTABLE BANKS  
            Analyze the tone and sentiment of comments:
            - Overall sector sentiment (positive/neutral/negative)
            - Banks with most positive developments and specific reasons why
            - Banks with most concerning issues and specific reasons for concern

            ## 3. SIGNIFICANT BANK CHANGES BY TOPIC
            Identify which specific banks showed the most significant changes in each key area:

            **Net Interest Margin (NIM) & Profitability:**
            - Most improved: [Specific Bank Name] - [detailed reason based on comment data]
            - Most concerning: [Specific Bank Name] - [detailed reason based on comment data]

            **Credit Growth & Lending:**
            - Strongest growth: [Specific Bank Name] - [detailed reason based on comment data]
            - Weakest/declining: [Specific Bank Name] - [detailed reason based on comment data]

            **Asset Quality & Risk Management:**
            - Most improved: [Specific Bank Name] - [detailed reason based on comment data]
            - Most deteriorated: [Specific Bank Name] - [detailed reason based on comment data]

            **Instructions:**
            - Be specific with actual bank names (tickers) mentioned in the comments
            - Write in bullet points format, be punchy and concise
            - Provide clear, data-driven reasoning based on the comments provided
            - Use quantitative insights where available in the comments
            - Maintain professional banking analyst tone
            - If insufficient data for a category, clearly state "Insufficient data available"
            """

            # Send to OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4.1", 
                messages=[
                    {"role": "system", "content": "You are a senior banking analyst with deep expertise in financial analysis, market trends, and Vietnamese banking sector dynamics. Provide detailed, professional analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                top_p=0.9
            )
            
            analysis_text = response.choices[0].message.content
            
            return {
                'quarter': quarter,
                'analysis_text': analysis_text,
                'bank_count': bank_count,
                'generated_date': datetime.now(),
                'status': 'success'
            }
            
        except Exception as e:
            print(f"  Error analyzing quarter {quarter}: {str(e)}")
            return {
                'quarter': quarter,
                'analysis_text': f"Error generating analysis: {str(e)}",
                'bank_count': len(quarter_comments_df),
                'generated_date': datetime.now(),
                'status': 'error'
            }
    
    def save_analysis_results(self, analysis_results):
        """Save analysis results to Excel file"""
        try:
            # Convert to DataFrame
            results_df = pd.DataFrame(analysis_results)
            
            # Sort by quarter
            results_df['quarter_sort'] = results_df['quarter'].apply(quarter_sort_key)
            results_df = results_df.sort_values('quarter_sort').drop('quarter_sort', axis=1)
            
            # Save to Excel
            results_df.to_excel(self.analysis_file, index=False)
            print(f"\n✅ Analysis results saved to: {self.analysis_file}")
            
            return True
        except Exception as e:
            print(f"❌ Error saving analysis results: {e}")
            return False
    
    def run_bulk_analysis(self, skip_existing=True):
        """Run bulk analysis for all quarters"""
        try:
            print("🔍 Starting Bulk Quarterly Analysis Generation")
            print("=" * 50)
            
            # Load comments data
            print("📊 Loading banking comments data...")
            comments_df = self.load_comments_data()
            print(f"   Loaded {len(comments_df)} total comments")
            
            # Get quarters to analyze
            quarters_to_analyze = self.get_quarters_to_analyze(comments_df)
            print(f"   Found {len(quarters_to_analyze)} quarters from 1Q24 onwards")
            print(f"   Quarters: {', '.join(quarters_to_analyze)}")
            
            # Load existing analysis if available
            existing_analysis = self.load_existing_analysis()
            existing_quarters = set()
            if not existing_analysis.empty and skip_existing:
                existing_quarters = set(existing_analysis['quarter'].tolist())
                print(f"   Found {len(existing_quarters)} existing analysis results")
            
            # Filter quarters that need analysis
            quarters_needing_analysis = [q for q in quarters_to_analyze if q not in existing_quarters]
            
            if not quarters_needing_analysis:
                print("✅ All quarters already have analysis results!")
                return True
            
            print(f"📝 Will analyze {len(quarters_needing_analysis)} quarters: {', '.join(quarters_needing_analysis)}")
            
            # Confirm before proceeding
            user_input = input("\n⚠️  This will use OpenAI API credits. Continue? (y/N): ").strip().lower()
            if user_input != 'y':
                print("❌ Analysis cancelled by user")
                return False
            
            print("\n🤖 Starting AI analysis generation...")
            print("-" * 30)
            
            analysis_results = []
            
            # Add existing results if any
            if not existing_analysis.empty:
                for _, row in existing_analysis.iterrows():
                    analysis_results.append({
                        'quarter': row['quarter'],
                        'analysis_text': row['analysis_text'],
                        'bank_count': row['bank_count'],
                        'generated_date': row['generated_date'],
                        'status': row['status']
                    })
            
            # Analyze each quarter
            for i, quarter in enumerate(quarters_needing_analysis, 1):
                print(f"\n📋 Processing {quarter} ({i}/{len(quarters_needing_analysis)})")
                
                # Get comments for this quarter
                quarter_comments = comments_df[comments_df['QUARTER'] == quarter]
                
                if quarter_comments.empty:
                    print(f"  ⚠️  No comments found for {quarter}")
                    continue
                
                # Generate analysis
                result = self.analyze_quarter(quarter_comments, quarter)
                analysis_results.append(result)
                
                if result['status'] == 'success':
                    print(f"  ✅ Analysis completed for {quarter}")
                else:
                    print(f"  ❌ Analysis failed for {quarter}")
                
                # Save progress after each quarter
                self.save_analysis_results(analysis_results)
                
                # Add delay to avoid rate limiting
                if i < len(quarters_needing_analysis):
                    print(f"  ⏱️  Waiting 2 seconds before next quarter...")
                    time.sleep(2)
            
            print("\n" + "=" * 50)
            print("🎉 Bulk analysis generation completed!")
            print(f"📁 Results saved to: {self.analysis_file}")
            
            # Show summary
            successful = sum(1 for r in analysis_results if r['status'] == 'success')
            total = len(analysis_results)
            print(f"📊 Summary: {successful}/{total} quarters analyzed successfully")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in bulk analysis: {e}")
            return False

def main():
    """Main function to run the bulk analysis"""
    try:
        generator = BulkQuarterlyAnalysisGenerator()
        
        print("🏦 Banking Quarterly Analysis - Bulk Generator")
        print("This tool will generate AI analysis for all quarters from 1Q24 onwards")
        print()
        
        # Check if analysis file already exists
        if os.path.exists(generator.analysis_file):
            existing_df = pd.read_excel(generator.analysis_file)
            print(f"📋 Existing analysis file found with {len(existing_df)} quarters")
            
            choice = input("Options:\n1. Skip existing quarters (recommended)\n2. Regenerate all quarters\nChoose (1/2): ").strip()
            skip_existing = choice != '2'
        else:
            skip_existing = True
        
        # Run bulk analysis
        success = generator.run_bulk_analysis(skip_existing=skip_existing)
        
        if success:
            print("\n✅ Process completed successfully!")
        else:
            print("\n❌ Process completed with errors")
            
    except Exception as e:
        print(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()
