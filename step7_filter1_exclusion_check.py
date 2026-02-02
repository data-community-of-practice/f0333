"""
PRISMA Filter 1: Exclusion Criteria Check (Non-Medical ICD Terms)
Papers MUST NOT contain non-medical ICD terms to pass this filter

Input: prisma_screening_results_all_filtered.csv (papers filtered by year 2005-2026 and type CONF/JOUR)
Output: Papers that do not mention non-medical meanings of ICD (cardiac devices, etc.)
"""

import pandas as pd
import re
from datetime import datetime

# ============================================
# EXCLUSION KEYWORDS (If found, paper is excluded)
# ============================================

EXCLUSION_KEYWORDS = {
    # Non-Medical ICD Terms (ICD means something completely different in these contexts)
    'Cardiac Device': r'\b(implantable cardioverter|defibrillator device|cardiac device|ventricular arrhythmia)\b',  # ICD = Implantable Cardioverter Defibrillator
    'Quantum Computing': r'\bquantum computing\b',  # ICD = Interpolation-based Coordinate Descent
    'Satellite': r'\b(satellite.*interface control|interface control document.*satellite)\b',  # ICD = Interface Control Documents
    'Gaming': r'\b(game.*internal cooldown|cooldown.*game)\b',  # ICD = Internal Cooldown
    'Security/Intelligence': r'\b(intelligence community directive|insecure code detector)\b'  # ICD = Intelligence Community Directive / Insecure Code Detector
}

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_text_from_row(row):
    """Extract and combine Title, Abstract, and Keywords"""
    title = str(row.get('Title', '')).lower() if pd.notna(row.get('Title')) else ''
    abstract = str(row.get('Abstract', '')).lower() if pd.notna(row.get('Abstract')) else ''
    keywords = str(row.get('Keywords', '')).lower() if pd.notna(row.get('Keywords')) else ''

    return title, abstract, keywords

def find_exclusion_keywords(text):
    """Find all exclusion keywords that match in the text"""
    matches = []
    for keyword_name, pattern in EXCLUSION_KEYWORDS.items():
        if re.search(pattern, text, re.IGNORECASE):
            matches.append(keyword_name)
    return matches

def check_exclusion_criteria(row):
    """
    Check if paper should be excluded based on exclusion keywords
    Returns: (decision, matched_terms, reason)
    """
    title, abstract, keywords = get_text_from_row(row)

    # Check if all fields are empty
    if not title and not abstract and not keywords:
        return 'EXCLUDE', '', 'No title, abstract, or keywords available for evaluation'

    # Combine all text for searching
    all_text = f"{title} {abstract} {keywords}"

    # Check for exclusion keywords
    exclusion_matches = find_exclusion_keywords(all_text)

    if exclusion_matches:
        matched_terms_str = '; '.join(exclusion_matches)
        reason = f"Paper contains exclusion keywords: {matched_terms_str}. Not about automated ICD coding (likely about {exclusion_matches[0].lower()})."
        return 'EXCLUDE', matched_terms_str, reason

    # No exclusion keywords found - paper passes Filter 1
    reason = "Paper does not contain non-medical ICD terms (cardiac devices, quantum computing, etc.). Passes Filter 1 and proceeds to Filter 2 for ICD relevance check."
    return 'PASS', '', reason

# ============================================
# MAIN FILTERING FUNCTION
# ============================================

def filter_exclusion_criteria(input_csv='prisma_screening_results_all_filtered.csv',
                              output_all='filter1_all_results.csv',
                              output_pass='filter1_passed.csv',
                              output_exclude='filter1_excluded.csv'):
    """
    Filter 1: Check for non-medical ICD exclusion criteria

    Parameters:
    - input_csv: Input CSV file (papers filtered by year 2005-2026 and type CONF/JOUR)
    - output_all: Complete results with all papers and Filter 1 decisions
    - output_pass: Papers that PASSED (no non-medical ICD terms) - proceed to Filter 2
    - output_exclude: Papers that were EXCLUDED (contain non-medical ICD terms like cardiac devices)
    """

    print("="*80)
    print("PRISMA FILTER 1: EXCLUSION CRITERIA CHECK")
    print("="*80)
    print("\nCriteria: Paper MUST NOT contain exclusion keywords")
    print("Action: If exclusion keywords found -> EXCLUDE")
    print("Checking: Title AND Abstract AND Keywords for exclusion terms")

    # Load data
    print(f"\nLoading data from {input_csv}...")
    df = pd.read_csv(input_csv, low_memory=False)
    print(f"Total records loaded: {len(df):,}")
    print("(Papers after year and publication type filtering)")

    # ============================================
    # APPLY EXCLUSION CRITERIA FILTER
    # ============================================

    print("\n" + "-"*80)
    print("Applying Exclusion Criteria Filter...")
    print("-"*80)

    # Apply the filter
    results = df.apply(check_exclusion_criteria, axis=1)
    df['Filter1_Decision'] = results.apply(lambda x: x[0])
    df['Filter1_Matched_Exclusions'] = results.apply(lambda x: x[1])
    df['Filter1_Reason'] = results.apply(lambda x: x[2])

    # Count results
    passed_count = (df['Filter1_Decision'] == 'PASS').sum()
    excluded_count = (df['Filter1_Decision'] == 'EXCLUDE').sum()

    # ============================================
    # DISPLAY RESULTS
    # ============================================

    print("\n" + "="*80)
    print("FILTER 1 RESULTS: EXCLUSION CRITERIA")
    print("="*80)
    print(f"\nTotal papers evaluated: {len(df):,}")
    print(f"\n  [PASS] PASSED (no exclusion keywords):  {passed_count:,} ({passed_count/len(df)*100:.1f}%)")
    print(f"  [EXCLUDE] EXCLUDED (has exclusion keywords): {excluded_count:,} ({excluded_count/len(df)*100:.1f}%)")

    # Show exclusion reasons (for excluded papers)
    if excluded_count > 0:
        print("\n" + "-"*80)
        print("Top Exclusion Reasons:")
        print("-"*80)
        # Get top exclusion keywords
        all_exclusions = df[df['Filter1_Decision'] == 'EXCLUDE']['Filter1_Matched_Exclusions'].str.split('; ')
        exclusion_list = [item for sublist in all_exclusions if isinstance(sublist, list) for item in sublist]
        from collections import Counter
        exclusion_counts = Counter(exclusion_list)
        for keyword, count in exclusion_counts.most_common(10):
            print(f"  {keyword:40s}: {count:4,} papers ({count/excluded_count*100:.1f}%)")

    # ============================================
    # EXPORT RESULTS
    # ============================================

    # Select columns for output
    output_columns = [
        'Filter1_Decision', 'Filter1_Matched_Exclusions', 'Filter1_Reason',
        'Title', 'Authors', 'Year', 'Publication', 'Type', 'DOI', 'Abstract', 'Keywords', 'URL'
    ]
    output_columns = [col for col in output_columns if col in df.columns]

    print("\n" + "="*80)
    print("EXPORTING RESULTS")
    print("="*80)

    # 1. Save all results
    print(f"\n1. Saving all papers with Filter 3 decisions to {output_all}...")
    df_output = df[output_columns].copy()
    df_output = df_output.sort_values('Filter1_Decision', ascending=False)  # PASS first
    df_output.to_csv(output_all, index=False, encoding='utf-8')
    print(f"   [SUCCESS] {len(df_output):,} papers saved")

    # 2. Save passed papers (FINAL DATASET)
    df_passed = df[df['Filter1_Decision'] == 'PASS'].copy()
    print(f"\n2. Saving PASSED papers to {output_pass}...")
    df_passed[output_columns].to_csv(output_pass, index=False, encoding='utf-8')
    print(f"   [SUCCESS] {len(df_passed):,} papers saved")
    print(f"   -> These papers proceed to Filter 2 (ICD Relevance)")

    # 3. Save excluded papers
    df_excluded = df[df['Filter1_Decision'] == 'EXCLUDE'].copy()
    print(f"\n3. Saving EXCLUDED papers to {output_exclude}...")
    df_excluded[output_columns].to_csv(output_exclude, index=False, encoding='utf-8')
    print(f"   [SUCCESS] {len(df_excluded):,} papers saved")
    print(f"   -> These papers mention non-medical ICD terms (excluded)")

    # ============================================
    # SAMPLE OUTPUTS
    # ============================================

    print("\n" + "="*80)
    print("SAMPLE PASSED PAPERS (showing first 5)")
    print("="*80)
    if passed_count > 0:
        sample_passed = df_passed.head(5)
        for idx, row in sample_passed.iterrows():
            title = row['Title'][:70] + '...' if len(str(row['Title'])) > 70 else row['Title']
            print(f"\n  Title: {title}")
            print(f"  Year: {row.get('Year', 'N/A')}")
            print(f"  ICD Terms: {row.get('Filter1_Matched_Terms', '')[:50]}")
            print(f"  AI Terms: {row.get('Filter2_Matched_Terms', '')[:50]}")
    else:
        print("  No papers passed this filter.")

    print("\n" + "="*80)
    print("SAMPLE EXCLUDED PAPERS (showing first 3)")
    print("="*80)
    if excluded_count > 0:
        sample_excluded = df_excluded.head(3)
        for idx, row in sample_excluded.iterrows():
            title = row['Title'][:70] + '...' if len(str(row['Title'])) > 70 else row['Title']
            print(f"\n  Title: {title}")
            print(f"  Exclusion: {row['Filter1_Matched_Exclusions']}")
            print(f"  Reason: {row['Filter1_Reason'][:100]}...")
    else:
        print("  No papers were excluded.")

    # ============================================
    # FINAL SUMMARY
    # ============================================

    print("\n" + "="*80)
    print("FILTER 1 SUMMARY")
    print("="*80)
    print(f"\nTotal papers evaluated: {len(df):,}")
    print(f"Papers PASSED (no non-medical ICD): {passed_count:,} ({passed_count/len(df)*100:.1f}%)")
    print(f"Papers EXCLUDED (non-medical ICD): {excluded_count:,} ({excluded_count/len(df)*100:.1f}%)")

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print(f"1. Review {output_all} to see all filtering decisions")
    print(f"2. Use {output_pass} as input for Filter 2 (ICD Relevance check)")
    print(f"3. Archive {output_exclude} (papers about non-medical ICD terms)")
    print("\nFilter 1 Complete!")
    print("="*80)

    return df

# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    import sys

    # Default parameters
    input_file = 'prisma_screening_results_all_filtered.csv'
    output_all = 'filter1_all_results.csv'
    output_pass = 'filter1_passed.csv'
    output_exclude = 'filter1_excluded.csv'

    # Command-line arguments
    if len(sys.argv) > 1:
        input_file = sys.argv[1]

    # Run Filter 1
    filter_exclusion_criteria(input_file, output_all, output_pass, output_exclude)
