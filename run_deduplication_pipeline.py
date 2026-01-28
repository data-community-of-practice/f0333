"""
Master script to run the complete deduplication pipeline (Steps 3-5)
"""

import subprocess
import sys
from pathlib import Path


def run_script(script_name, description):
    """
    Run a Python script and handle errors
    """
    print("\n" + "="*80)
    print(f"STEP: {description}")
    print("="*80 + "\n")

    try:
        result = subprocess.run(
            [sys.executable, script_name],
            check=True,
            capture_output=False,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"\nError running {script_name}: {e}")
        return False


def main():
    print("="*80)
    print("ICD CODING PAPERS - GLOBAL DEDUPLICATION PIPELINE (Steps 3-5)")
    print("="*80)

    scripts = [
        ("Step5_analyze_duplicates.py", "Step 5: Analyzing duplicates in source data"),
        ("Step3_merge_and_deduplicate.py", "Step 3: Merging and deduplicating papers"),
        ("Step4_export_to_csv.py", "Step 4: Exporting results to CSV format")
    ]

    # Check if all scripts exist
    for script_name, _ in scripts:
        if not Path(script_name).exists():
            print(f"Error: {script_name} not found!")
            return

    # Run each script
    for script_name, description in scripts:
        success = run_script(script_name, description)
        if not success:
            print(f"\nPipeline stopped due to error in {script_name}")
            return

    print("\n" + "="*80)
    print("PIPELINE COMPLETED SUCCESSFULLY!")
    print("="*80)
    print("\nGenerated files:")
    print("  1. duplicate_analysis_report.txt  - Detailed analysis of duplicates")
    print("  2. merged_deduplicated_papers.ris - Merged papers in RIS format")
    print("  3. deduplication_statistics.txt   - Statistics summary")
    print("  4. merged_deduplicated_papers.csv - Merged papers in CSV format")
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
