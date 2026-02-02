"""
PRISMA Filter 1: ICD Relevance Check
Papers MUST mention ICD coding/classification to pass this filter

Input: prisma_screening_results_all_filtered.csv (already filtered by year 2005-2026 and type CONF/JOUR)
Output: Papers that mention ICD-related terms
"""

import pandas as pd
import re
from datetime import datetime

# ============================================
# ICD-RELATED KEYWORDS (Mandatory)
# ============================================

ICD_KEYWORDS = {
    'ICD': r'\bICD[-\s]?\d*\b',
    'ICD Code': r'\bICD\s+cod(e|ing|es)\b',
    'International Classification of Diseases': r'\binternational classification of diseases\b',
    'Medical Coding': r'\bmedical cod(ing|e|es)\b',
    'Clinical Coding': r'\bclinical cod(ing|e|es)\b',
    'Diagnosis Coding': r'\bdiagnos(is|tic) cod(ing|e|es)\b',
    'Diagnostic Coding': r'\bdiagnostic cod(ing|e|es)\b',
    'Code Assignment': r'\bcode assignment\b',
    'Disease Classification': r'\bdisease classification\b',
    'Health Record Coding': r'\bhealth record cod(ing|e)\b',
    'Clinical Classification': r'\bclinical classification\b'
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

def find_icd_keywords(text):
    """Find all ICD keywords that match in the text"""
    matches = []
    for keyword_name, pattern in ICD_KEYWORDS.items():
        if re.search(pattern, text, re.IGNORECASE):
            matches.append(keyword_name)
    return matches

def check_icd_relevance(row):
    """
    Check if paper is relevant to ICD coding/classification
    Returns: (decision, matched_terms, location, reason)
    """
    title, abstract, keywords = get_text_from_row(row)

    # Check if all fields are empty
    if not title and not abstract and not keywords:
        return 'EXCLUDE', '', 'N/A', 'No title, abstract, or keywords available for evaluation'

    # Check Title first
    title_matches = find_icd_keywords(title)
    if title_matches:
        matched_terms_str = '; '.join(title_matches)
        reason = f"Paper mentions ICD-related terms in TITLE: {matched_terms_str}. Relevant to ICD coding/classification."
        return 'PASS', matched_terms_str, 'Title', reason

    # Check Abstract
    abstract_matches = find_icd_keywords(abstract)
    if abstract_matches:
        matched_terms_str = '; '.join(abstract_matches)
        reason = f"Paper mentions ICD-related terms in ABSTRACT: {matched_terms_str}. Relevant to ICD coding/classification."
        return 'PASS', matched_terms_str, 'Abstract', reason

    # Check Keywords
    keyword_matches = find_icd_keywords(keywords)
    if keyword_matches:
        matched_terms_str = '; '.join(keyword_matches)
        reason = f"Paper mentions ICD-related terms in KEYWORDS: {matched_terms_str}. Relevant to ICD coding/classification."
        return 'PASS', matched_terms_str, 'Keywords', reason

    # No ICD terms found anywhere
    reason = "Paper does not mention any ICD-related terms (ICD, International Classification of Diseases, medical/clinical coding, etc.) in title, abstract, or keywords. Not relevant to ICD coding research."
    return 'EXCLUDE', '', 'N/A', reason

# ============================================
# MAIN FILTERING FUNCTION
# ============================================

def filter_icd_relevance(input_csv='prisma_screening_results_all_filtered.csv',
                         output_all='filter1_all_results.csv',
                         output_pass='filter1_passed.csv',
                         output_exclude='filter1_excluded.csv'):
    """
    Filter 1: Check for ICD relevance

    Parameters:
    - input_csv: Input CSV file (already filtered by year and publication type)
    - output_all: Complete results with all papers
    - output_pass: Papers that PASSED (have ICD terms)
    - output_exclude: Papers that were EXCLUDED (no ICD terms)
    """

    print("="*80)
    print("PRISMA FILTER 1: ICD RELEVANCE CHECK")
    print("="*80)
    print("\nCriteria: Paper MUST mention ICD coding/classification")
    print("Action: If NO ICD terms found → EXCLUDE")
    print("Checking: Title OR Abstract OR Keywords")

    # Load data
    print(f"\nLoading data from {input_csv}...")
    df = pd.read_csv(input_csv, low_memory=False)
    print(f"Total records loaded: {len(df):,}")
    print("(Already filtered by: Year 2005-2026, Publication Type CONF/JOUR)")

    # ============================================
    # APPLY ICD RELEVANCE FILTER
    # ============================================

    print("\n" + "-"*80)
    print("Applying ICD Relevance Filter...")
    print("-"*80)

    # Apply the filter
    results = df.apply(check_icd_relevance, axis=1)
    df['Filter1_Decision'] = results.apply(lambda x: x[0])
    df['Filter1_Matched_Terms'] = results.apply(lambda x: x[1])
    df['Filter1_Match_Location'] = results.apply(lambda x: x[2])
    df['Filter1_Reason'] = results.apply(lambda x: x[3])

    # Count results
    passed_count = (df['Filter1_Decision'] == 'PASS').sum()
    excluded_count = (df['Filter1_Decision'] == 'EXCLUDE').sum()

    # ============================================
    # DISPLAY RESULTS
    # ============================================

    print("\n" + "="*80)
    print("FILTER 1 RESULTS: ICD RELEVANCE")
    print("="*80)
    print(f"\nTotal papers evaluated: {len(df):,}")
    print(f"\n  ✓ PASSED (has ICD terms):  {passed_count:,} ({passed_count/len(df)*100:.1f}%)")
    print(f"  ✗ EXCLUDED (no ICD terms): {excluded_count:,} ({excluded_count/len(df)*100:.1f}%)")

    # Show where ICD terms were found (for passed papers)
    if passed_count > 0:
        print("\n" + "-"*80)
        print("ICD Terms Found In:")
        print("-"*80)
        location_counts = df[df['Filter1_Decision'] == 'PASS']['Filter1_Match_Location'].value_counts()
        for location, count in location_counts.items():
            print(f"  {location:15s}: {count:5,} papers ({count/passed_count*100:.1f}%)")

    # ============================================
    # EXPORT RESULTS
    # ============================================

    # Select columns for output
    output_columns = [
        'Filter1_Decision', 'Filter1_Matched_Terms', 'Filter1_Match_Location', 'Filter1_Reason',
        'Title', 'Authors', 'Year', 'Publication', 'Type', 'DOI', 'Abstract', 'Keywords', 'URL'
    ]
    output_columns = [col for col in output_columns if col in df.columns]

    print("\n" + "="*80)
    print("EXPORTING RESULTS")
    print("="*80)

    # 1. Save all results
    print(f"\n1. Saving all papers with Filter 1 decisions to {output_all}...")
    df_output = df[output_columns].copy()
    df_output = df_output.sort_values('Filter1_Decision', ascending=False)  # PASS first
    df_output.to_csv(output_all, index=False, encoding='utf-8')
    print(f"   [SUCCESS] {len(df_output):,} papers saved")

    # 2. Save passed papers
    df_passed = df[df['Filter1_Decision'] == 'PASS'].copy()
    print(f"\n2. Saving PASSED papers to {output_pass}...")
    df_passed[output_columns].to_csv(output_pass, index=False, encoding='utf-8')
    print(f"   [SUCCESS] {len(df_passed):,} papers saved")
    print(f"   → These papers will proceed to Filter 2")

    # 3. Save excluded papers
    df_excluded = df[df['Filter1_Decision'] == 'EXCLUDE'].copy()
    print(f"\n3. Saving EXCLUDED papers to {output_exclude}...")
    df_excluded[output_columns].to_csv(output_exclude, index=False, encoding='utf-8')
    print(f"   [SUCCESS] {len(df_excluded):,} papers saved")
    print(f"   → These papers are not relevant to ICD coding")

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
            print(f"  Matched: {row['Filter1_Matched_Terms']}")
            print(f"  Location: {row['Filter1_Match_Location']}")
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
            print(f"  Reason: {row['Filter1_Reason'][:120]}...")
    else:
        print("  No papers were excluded.")

    # ============================================
    # SUMMARY
    # ============================================

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print(f"1. Review {output_all} to see all filtering decisions")
    print(f"2. Use {output_pass} as input for Filter 2 (Automation/AI check)")
    print(f"3. Archive {output_exclude} (papers not relevant to ICD coding)")
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
    filter_icd_relevance(input_file, output_all, output_pass, output_exclude)
