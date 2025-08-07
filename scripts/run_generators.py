#!/usr/bin/env python3
"""
Unified script to run bulk generators for banking analysis
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generators.bulk_comment_generator import BulkCommentGenerator
from generators.bulk_quarterly_analysis_generator import BulkQuarterlyAnalysisGenerator
from datetime import datetime

def print_header(title):
    """Print a formatted header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def print_menu():
    """Print main menu"""
    print("\nMAIN MENU:")
    print("1. Generate Banking Comments")
    print("2. Generate Quarterly Analysis")
    print("3. Run Full Pipeline (Comments + Analysis)")
    print("4. Quick Generation (1Q24 to 3Q24)")
    print("5. Exit")
    return input("\nSelect option (1-5): ").strip()

def run_comment_generator():
    """Run the comment generator with options"""
    try:
        generator = BulkCommentGenerator()
        
        print_header("BANKING COMMENT GENERATOR")
        
        # Show available quarters
        available_quarters = generator.get_available_quarters()
        print(f"\nAvailable quarters: {available_quarters[0]} to {available_quarters[-1]}")
        
        print("\nGeneration Options:")
        print("1. Generate for ALL quarters")
        print("2. Generate for SPECIFIC timeframe")
        print("3. Back to main menu")
        
        choice = input("\nSelect option (1-3): ").strip()
        
        if choice == '1':
            # All quarters
            overwrite = input("\nOverwrite existing comments? (y/n): ").strip().lower() == 'y'
            
            print("\nStarting generation for ALL quarters...")
            result = generator.generate_bulk_comments(
                start_quarter=None,
                end_quarter=None,
                overwrite_existing=overwrite
            )
            
            print(f"\n[SUCCESS] Successfully generated {len(result)} comments")
            
        elif choice == '2':
            # Specific timeframe
            print("\nEnter timeframe (format: 1Q24, 2Q24, etc.)")
            start = input("Start quarter (or Enter for earliest): ").strip() or None
            end = input("End quarter (or Enter for latest): ").strip() or None
            overwrite = input("Overwrite existing comments? (y/n): ").strip().lower() == 'y'
            
            timeframe_desc = f"{start or 'earliest'} to {end or 'latest'}"
            print(f"\nStarting generation for {timeframe_desc}...")
            
            result = generator.generate_bulk_comments(
                start_quarter=start,
                end_quarter=end,
                overwrite_existing=overwrite
            )
            
            print(f"\n[SUCCESS] Successfully generated {len(result)} comments")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Error in comment generation: {e}")
        return False

def run_analysis_generator():
    """Run the quarterly analysis generator with options"""
    try:
        generator = BulkQuarterlyAnalysisGenerator()
        
        print_header("QUARTERLY ANALYSIS GENERATOR")
        
        # Show available quarters
        available_quarters = generator.get_available_quarters()
        if not available_quarters:
            print("\n[WARNING]  No comments found. Please generate comments first.")
            return False
        
        print(f"\nAvailable quarters: {available_quarters[0]} to {available_quarters[-1]}")
        
        print("\nAnalysis Options:")
        print("1. Analyze ALL quarters")
        print("2. Analyze SPECIFIC timeframe")
        print("3. Export analysis report")
        print("4. Back to main menu")
        
        choice = input("\nSelect option (1-4): ").strip()
        
        if choice == '1':
            # All quarters
            overwrite = input("\nOverwrite existing analysis? (y/n): ").strip().lower() == 'y'
            
            print("\nStarting analysis for ALL quarters...")
            result = generator.generate_bulk_analysis(
                start_quarter=None,
                end_quarter=None,
                overwrite_existing=overwrite
            )
            
            print(f"\n[SUCCESS] Successfully analyzed {len(result)} quarters")
            
        elif choice == '2':
            # Specific timeframe
            print("\nEnter timeframe (format: 1Q24, 2Q24, etc.)")
            start = input("Start quarter (or Enter for earliest): ").strip() or None
            end = input("End quarter (or Enter for latest): ").strip() or None
            overwrite = input("Overwrite existing analysis? (y/n): ").strip().lower() == 'y'
            
            timeframe_desc = f"{start or 'earliest'} to {end or 'latest'}"
            print(f"\nStarting analysis for {timeframe_desc}...")
            
            result = generator.generate_bulk_analysis(
                start_quarter=start,
                end_quarter=end,
                overwrite_existing=overwrite
            )
            
            print(f"\n[SUCCESS] Successfully analyzed {len(result)} quarters")
            
        elif choice == '3':
            # Export report
            output_file = generator.export_analysis_report()
            if output_file:
                print(f"\n[SUCCESS] Report exported to: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Error in analysis generation: {e}")
        return False

def run_full_pipeline():
    """Run both generators in sequence"""
    print_header("FULL PIPELINE: Comments + Analysis")
    
    print("\nThis will run both generators in sequence.")
    print("Choose timeframe option:")
    print("1. ALL quarters")
    print("2. SPECIFIC timeframe")
    print("3. Cancel")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == '3':
        return
    
    # Get parameters
    start_quarter = None
    end_quarter = None
    
    if choice == '2':
        print("\nEnter timeframe (format: 1Q24, 2Q24, etc.)")
        start_quarter = input("Start quarter (or Enter for earliest): ").strip() or None
        end_quarter = input("End quarter (or Enter for latest): ").strip() or None
    
    overwrite = input("Overwrite existing data? (y/n): ").strip().lower() == 'y'
    
    # Run comment generator
    print("\n" + "-"*50)
    print("STEP 1: Generating Comments")
    print("-"*50)
    
    try:
        comment_gen = BulkCommentGenerator()
        comments_result = comment_gen.generate_bulk_comments(
            start_quarter=start_quarter,
            end_quarter=end_quarter,
            overwrite_existing=overwrite
        )
        print(f"[SUCCESS] Generated {len(comments_result)} comments")
    except Exception as e:
        print(f"[ERROR] Comment generation failed: {e}")
        return
    
    # Run analysis generator
    print("\n" + "-"*50)
    print("STEP 2: Generating Analysis")
    print("-"*50)
    
    try:
        analysis_gen = BulkQuarterlyAnalysisGenerator()
        analysis_result = analysis_gen.generate_bulk_analysis(
            start_quarter=start_quarter,
            end_quarter=end_quarter,
            overwrite_existing=overwrite
        )
        print(f"[SUCCESS] Generated analysis for {len(analysis_result)} quarters")
    except Exception as e:
        print(f"[ERROR] Analysis generation failed: {e}")
        return
    
    print("\n" + "="*50)
    print("[SUCCESS] FULL PIPELINE COMPLETE!")
    print("="*50)

def quick_generation():
    """Quick generation for 1Q24 to 3Q24"""
    print_header("QUICK GENERATION: 1Q24 to 3Q24")
    
    print("\nThis will generate comments and analysis for Q1-Q3 2024.")
    overwrite = input("Overwrite existing data? (y/n): ").strip().lower() == 'y'
    
    # Run comment generator
    print("\n" + "-"*50)
    print("Generating Comments for 1Q24 to 3Q24")
    print("-"*50)
    
    try:
        comment_gen = BulkCommentGenerator()
        comments_result = comment_gen.generate_bulk_comments(
            start_quarter='1Q24',
            end_quarter='3Q24',
            overwrite_existing=overwrite
        )
        print(f"[SUCCESS] Generated {len(comments_result)} comments")
    except Exception as e:
        print(f"[ERROR] Comment generation failed: {e}")
        return
    
    # Run analysis generator
    print("\n" + "-"*50)
    print("Generating Analysis for 1Q24 to 3Q24")
    print("-"*50)
    
    try:
        analysis_gen = BulkQuarterlyAnalysisGenerator()
        analysis_result = analysis_gen.generate_bulk_analysis(
            start_quarter='1Q24',
            end_quarter='3Q24',
            overwrite_existing=overwrite
        )
        print(f"[SUCCESS] Generated analysis for {len(analysis_result)} quarters")
        
        # Auto-export report
        print("\nExporting analysis report...")
        output_file = analysis_gen.export_analysis_report()
        if output_file:
            print(f"[SUCCESS] Report exported to: {output_file}")
            
    except Exception as e:
        print(f"[ERROR] Analysis generation failed: {e}")
        return
    
    print("\n" + "="*50)
    print("[SUCCESS] QUICK GENERATION COMPLETE!")
    print("="*50)

def main():
    """Main entry point"""
    print_header("BANKING ANALYSIS GENERATOR SUITE")
    print("\nWelcome to the Banking Analysis Generator Suite!")
    print("This tool helps generate AI-powered banking comments and quarterly analysis.")
    
    while True:
        choice = print_menu()
        
        if choice == '1':
            run_comment_generator()
        elif choice == '2':
            run_analysis_generator()
        elif choice == '3':
            run_full_pipeline()
        elif choice == '4':
            quick_generation()
        elif choice == '5':
            print("\nThank you for using the Banking Analysis Generator!")
            print("Goodbye!")
            break
        else:
            print("\n[WARNING]  Invalid option. Please try again.")
        
        if choice in ['1', '2', '3', '4']:
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()