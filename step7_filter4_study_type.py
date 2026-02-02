"""
PRISMA Filter 4: Study Type Classification
Distinguish between primary research, secondary studies, and non-research items

Input: filter3_passed.csv (papers that passed Filters 1-3: automated ICD coding papers)
Output: Categorized papers by study type
"""

import pandas as pd
import re
from datetime import datetime

# ============================================
# STUDY TYPE KEYWORDS
# ============================================

# Secondary Studies - Valuable for background but different purpose
SECONDARY_STUDY_KEYWORDS = {
    # Literature Reviews
    'Systematic Review': r'\bsystematic review\b',
    'Literature Review': r'\bliterature review\b',
    'Scoping Review': r'\bscoping review\b',
    'Meta-Analysis': r'\bmeta-analysis\b',
    'Meta-Review': r'\bmeta-review\b',
    'Umbrella Review': r'\bumbrella review\b',

    # Surveys & Overviews (more specific context)
    'Survey': r'\b(survey of|survey on|survey:|^survey)\b',  # Avoid "survey study" (primary research)
    'State-of-the-Art Review': r'\b(state-of-the-art (survey|review|overview)|survey of (the )?state-of-the-art)\b',
    'Overview': r'\b(overview of|overview on|overview:)\b',

    # Review phrases (must be in title or start of abstract)
    'Review Article': r'\b(review of|review on|a review of) (automated|automatic|machine learning|deep learning|AI|methods|approaches|techniques|algorithms)\b',
    'Comprehensive Review': r'\bcomprehensive (review|survey|overview)\b',
    'Recent Advances': r'\brecent advances in (automated|automatic|machine learning|deep learning|AI)\b',
}

# Non-Research Items - Exclude entirely
# NOTE: These patterns should be VERY specific to avoid false positives
# Only match when clearly indicating paper TYPE, not just using words in passing
NON_RESEARCH_KEYWORDS = {
    # Editorials & Opinions (must be in title or as paper type descriptor)
    'Editorial': r'\b(editorial|^editorial)\b',
    'Commentary': r'\b(commentary|^commentary)\b',
    'Opinion Piece': r'\b(opinion piece|opinion article)\b',
    'Viewpoint': r'\b(viewpoint|^viewpoint)\b',

    # Correspondence (very specific patterns - must be clear paper type indicator)
    'Letter to Editor': r'\b(letter to( the)? editor|correspondence( to( the)?)? editor)\b',
    'Author Reply': r'\b(author.?s? (response|reply)|reply to (comment|letter)|response to (comment|letter))\b',

    # Other Non-Research (clear non-research indicators)
    'News Item': r'\bnews( item| article)\b',
    'Erratum': r'\b(erratum|errata)\b',
    'Retraction': r'\bretraction\b',
    'Corrigendum': r'\bcorrigendum\b',
    'Preface': r'\bpreface( to)?\b',
    'Book Review': r'\bbook review\b',
    'Meeting Report': r'\b(conference summary|workshop summary|meeting report)\b',
}

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_text_from_row(row):
    """Extract and combine Title, Abstract, and Keywords"""
    title = str(row.get('Title', '')).lower() if pd.notna(row.get('Title')) else ''
    abstract = str(row.get('Abstract', '')).lower() if pd.notna(row.get('Abstract')) else ''
    keywords = str(row.get('Keywords', '')).lower() if pd.notna(row.get('Keywords')) else ''
    pub_type = str(row.get('Type', '')).lower() if pd.notna(row.get('Type')) else ''

    return title, abstract, keywords, pub_type

def find_matching_keywords(text, keyword_dict):
    """Find all keywords that match in the text"""
    matches = []
    for keyword_name, pattern in keyword_dict.items():
        if re.search(pattern, text, re.IGNORECASE):
            matches.append(keyword_name)
    return matches

def classify_study_type(row):
    """
    Classify paper as PRIMARY, SECONDARY, or EXCLUDE
    Returns: (decision, category, matched_terms, reason)
    """
    title, abstract, keywords, pub_type = get_text_from_row(row)

    # Check if all fields are empty
    if not title and not abstract:
        return 'EXCLUDE', 'Insufficient Data', '', 'No title or abstract available for evaluation'

    # Keep title and abstract separate for context-specific matching
    # combined_text = f"{title} {title} {abstract}"  # Title counted twice for emphasis

    # ============================================
    # STEP 1: Check for NON-RESEARCH items (EXCLUDE)
    # ============================================
    # ONLY check title for non-research keywords (most reliable indicator)
    # If these terms are just in the abstract, they're likely false positives
    non_research_matches = find_matching_keywords(title, NON_RESEARCH_KEYWORDS)

    # Also check publication type field
    if pub_type in ['editorial', 'letter', 'note', 'erratum', 'retraction', 'commentary']:
        non_research_matches.append(f'Publication Type: {pub_type}')

    if non_research_matches:
        matched_terms_str = '; '.join(non_research_matches)
        reason = f"Non-research item: {matched_terms_str}. Editorials, commentaries, letters, and news items are not original research."
        return 'EXCLUDE', 'Non-Research', matched_terms_str, reason

    # ============================================
    # STEP 2: Check for SECONDARY STUDIES (FLAG)
    # ============================================
    # Check title FIRST - review papers typically have "review" or "survey" in title
    secondary_matches = find_matching_keywords(title, SECONDARY_STUDY_KEYWORDS)

    # If strong indicators in title, classify as secondary
    if secondary_matches:
        matched_terms_str = '; '.join(secondary_matches)
        reason = f"Secondary study (in title): {matched_terms_str}. Systematic reviews and surveys are valuable for background but are not primary research."
        return 'SECONDARY', 'Review/Survey', matched_terms_str, reason

    # Check abstract for review indicators (but be more cautious)
    # Only flag as secondary if multiple indicators or very strong single indicator
    abstract_secondary_matches = find_matching_keywords(abstract, SECONDARY_STUDY_KEYWORDS)

    # Check publication type for review indicators
    if 'review' in pub_type and 'peer' not in pub_type:  # "peer review" is not a review paper
        abstract_secondary_matches.append(f'Publication Type: {pub_type}')

    # Only classify as secondary if we have strong evidence from abstract
    if len(abstract_secondary_matches) >= 2 or 'Systematic Review' in abstract_secondary_matches or 'Meta-Analysis' in abstract_secondary_matches:
        matched_terms_str = '; '.join(abstract_secondary_matches)
        reason = f"Secondary study: {matched_terms_str}. Systematic reviews and surveys are valuable for background but are not primary research."
        return 'SECONDARY', 'Review/Survey', matched_terms_str, reason

    # ============================================
    # STEP 3: Default to PRIMARY RESEARCH (INCLUDE)
    # ============================================

    # If not a review or non-research item, it's primary research
    reason = "Primary research: Original contribution (no review/survey/editorial indicators detected)."
    return 'PRIMARY', 'Original Research', '', reason

# ============================================
# MAIN FILTERING FUNCTION
# ============================================

def filter_study_type(input_csv='filter3_passed.csv',
                      output_all='filter4_all_results.csv',
                      output_primary='filter4_primary_research.csv',
                      output_secondary='filter4_secondary_studies.csv',
                      output_exclude='filter4_excluded.csv'):
    """
    Filter 4: Classify papers by study type

    Parameters:
    - input_csv: Input CSV file (papers that passed Filters 1-3)
    - output_all: Complete results with all papers and classifications
    - output_primary: PRIMARY research papers (main dataset for literature review)
    - output_secondary: SECONDARY studies (reviews/surveys - flagged for separate analysis)
    - output_exclude: EXCLUDED non-research items (editorials, letters, etc.)
    """

    print("="*80)
    print("PRISMA FILTER 4: STUDY TYPE CLASSIFICATION")
    print("="*80)
    print("\nCategories:")
    print("  PRIMARY   : Original research (methods, experiments, implementations)")
    print("  SECONDARY : Reviews/surveys (valuable but different purpose)")
    print("  EXCLUDE   : Non-research (editorials, commentaries, letters)")

    # Load data
    print(f"\nLoading data from {input_csv}...")
    df = pd.read_csv(input_csv, low_memory=False)
    print(f"Total records loaded: {len(df):,}")
    print("(Papers that passed Filters 1-3: Automated ICD coding papers)")

    # ============================================
    # APPLY STUDY TYPE CLASSIFICATION
    # ============================================

    print("\n" + "-"*80)
    print("Applying Study Type Classification...")
    print("-"*80)

    # Apply the filter
    results = df.apply(classify_study_type, axis=1)
    df['Filter4_Decision'] = results.apply(lambda x: x[0])
    df['Filter4_Category'] = results.apply(lambda x: x[1])
    df['Filter4_Matched_Terms'] = results.apply(lambda x: x[2])
    df['Filter4_Reason'] = results.apply(lambda x: x[3])

    # Count results
    primary_count = (df['Filter4_Decision'] == 'PRIMARY').sum()
    secondary_count = (df['Filter4_Decision'] == 'SECONDARY').sum()
    excluded_count = (df['Filter4_Decision'] == 'EXCLUDE').sum()

    # ============================================
    # DISPLAY RESULTS
    # ============================================

    print("\n" + "="*80)
    print("FILTER 4 RESULTS: STUDY TYPE CLASSIFICATION")
    print("="*80)
    print(f"\nTotal papers evaluated: {len(df):,}")
    print(f"\n  [PRIMARY] Original Research:    {primary_count:,} ({primary_count/len(df)*100:.1f}%)")
    print(f"  [SECONDARY] Reviews/Surveys:    {secondary_count:,} ({secondary_count/len(df)*100:.1f}%)")
    print(f"  [EXCLUDE] Non-Research Items:   {excluded_count:,} ({excluded_count/len(df)*100:.1f}%)")

    # Show breakdown of categories
    if secondary_count > 0:
        print("\n" + "-"*80)
        print("Secondary Studies Breakdown:")
        print("-"*80)
        secondary_df = df[df['Filter4_Decision'] == 'SECONDARY']
        category_counts = secondary_df['Filter4_Category'].value_counts()
        for category, count in category_counts.items():
            print(f"  {category:30s}: {count:4,} papers ({count/secondary_count*100:.1f}%)")

    if excluded_count > 0:
        print("\n" + "-"*80)
        print("Non-Research Items Breakdown:")
        print("-"*80)
        excluded_df = df[df['Filter4_Decision'] == 'EXCLUDE']
        category_counts = excluded_df['Filter4_Category'].value_counts()
        for category, count in category_counts.items():
            print(f"  {category:30s}: {count:4,} papers ({count/excluded_count*100:.1f}%)")

    # ============================================
    # EXPORT RESULTS
    # ============================================

    # Select columns for output
    output_columns = [
        'Filter1_Decision', 'Filter1_Matched_Terms', 'Filter1_Match_Location',
        'Filter2_Decision', 'Filter2_Matched_Terms', 'Filter2_Match_Location',
        'Filter3_Decision', 'Filter3_Matched_Terms', 'Filter3_Match_Location',
        'Filter4_Decision', 'Filter4_Category', 'Filter4_Matched_Terms', 'Filter4_Reason',
        'Title', 'Authors', 'Year', 'Publication', 'Type', 'DOI', 'Abstract', 'Keywords', 'URL'
    ]
    output_columns = [col for col in output_columns if col in df.columns]

    print("\n" + "="*80)
    print("EXPORTING RESULTS")
    print("="*80)

    # 1. Save all results
    print(f"\n1. Saving all papers with Filter 4 classifications to {output_all}...")
    df_output = df[output_columns].copy()
    df_output = df_output.sort_values('Filter4_Decision', ascending=True)  # PRIMARY first, then SECONDARY, then EXCLUDE
    df_output.to_csv(output_all, index=False, encoding='utf-8')
    print(f"   [SUCCESS] {len(df_output):,} papers saved")

    # 2. Save primary research papers (MAIN DATASET)
    df_primary = df[df['Filter4_Decision'] == 'PRIMARY'].copy()
    print(f"\n2. Saving PRIMARY research papers to {output_primary}...")
    df_primary[output_columns].to_csv(output_primary, index=False, encoding='utf-8')
    print(f"   [SUCCESS] {len(df_primary):,} papers saved")
    print(f"   *** THIS IS YOUR MAIN DATASET FOR LITERATURE REVIEW ***")

    # 3. Save secondary studies (FLAGGED for separate review)
    df_secondary = df[df['Filter4_Decision'] == 'SECONDARY'].copy()
    print(f"\n3. Saving SECONDARY studies (reviews/surveys) to {output_secondary}...")
    df_secondary[output_columns].to_csv(output_secondary, index=False, encoding='utf-8')
    print(f"   [SUCCESS] {len(df_secondary):,} papers saved")
    print(f"   -> Use these for background/related work section")

    # 4. Save excluded non-research items
    df_excluded = df[df['Filter4_Decision'] == 'EXCLUDE'].copy()
    print(f"\n4. Saving EXCLUDED non-research items to {output_exclude}...")
    df_excluded[output_columns].to_csv(output_exclude, index=False, encoding='utf-8')
    print(f"   [SUCCESS] {len(df_excluded):,} papers saved")
    print(f"   -> Editorials, commentaries, letters (not original research)")

    # ============================================
    # SAMPLE OUTPUTS
    # ============================================

    print("\n" + "="*80)
    print("SAMPLE PRIMARY RESEARCH PAPERS (showing first 5)")
    print("="*80)
    if primary_count > 0:
        sample_primary = df_primary.head(5)
        for idx, row in sample_primary.iterrows():
            title = row['Title'][:90] + '...' if len(str(row['Title'])) > 90 else row['Title']
            print(f"\n  Title: {title}")
            print(f"  Category: {row['Filter4_Category']}")
    else:
        print("  No primary research papers found.")

    print("\n" + "="*80)
    print("SAMPLE SECONDARY STUDIES (showing first 3)")
    print("="*80)
    if secondary_count > 0:
        sample_secondary = df_secondary.head(3)
        for idx, row in sample_secondary.iterrows():
            title = row['Title'][:80] + '...' if len(str(row['Title'])) > 80 else row['Title']
            print(f"\n  Title: {title}")
            print(f"  Category: {row['Filter4_Category']}")
            print(f"  Matched: {row['Filter4_Matched_Terms'][:80]}")
    else:
        print("  No secondary studies found.")

    print("\n" + "="*80)
    print("SAMPLE EXCLUDED NON-RESEARCH (showing first 3)")
    print("="*80)
    if excluded_count > 0:
        sample_excluded = df_excluded.head(3)
        for idx, row in sample_excluded.iterrows():
            title = row['Title'][:80] + '...' if len(str(row['Title'])) > 80 else row['Title']
            print(f"\n  Title: {title}")
            print(f"  Category: {row['Filter4_Category']}")
            print(f"  Matched: {row['Filter4_Matched_Terms'][:80]}")
    else:
        print("  No non-research items excluded.")

    # ============================================
    # SUMMARY
    # ============================================

    print("\n" + "="*80)
    print("FILTER 4 SUMMARY")
    print("="*80)
    print(f"\nTotal papers evaluated: {len(df):,}")
    print(f"\nPRIMARY Research (original contributions):  {primary_count:,} ({primary_count/len(df)*100:.1f}%)")
    print(f"SECONDARY Studies (reviews/surveys):        {secondary_count:,} ({secondary_count/len(df)*100:.1f}%)")
    print(f"EXCLUDED Non-Research (editorials/letters): {excluded_count:,} ({excluded_count/len(df)*100:.1f}%)")

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print(f"1. Use {output_primary} as your MAIN dataset for systematic review")
    print(f"2. Review {output_secondary} separately for background/related work")
    print(f"3. Archive {output_exclude} (non-research items)")
    print(f"\nYour main dataset now contains {primary_count:,} primary research papers!")
    print("\nFilter 4 Complete!")
    print("="*80)

    return df

# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    import sys

    # Default parameters
    input_file = 'filter3_passed.csv'
    output_all = 'filter4_all_results.csv'
    output_primary = 'filter4_primary_research.csv'
    output_secondary = 'filter4_secondary_studies.csv'
    output_exclude = 'filter4_excluded.csv'

    # Command-line arguments
    if len(sys.argv) > 1:
        input_file = sys.argv[1]

    # Run Filter 4
    filter_study_type(input_file, output_all, output_primary, output_secondary, output_exclude)
