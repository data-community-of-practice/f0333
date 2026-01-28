"""
PRISMA-style screening and filtering for ICD coding literature
Categorizes papers by relevance using automated criteria
"""

import pandas as pd
import re
from datetime import datetime

# ============================================
# STEP 1: Define Inclusion/Exclusion Criteria
# ============================================

# ICD-related terms (must appear in title, abstract, or keywords)
ICD_TERMS = [
    r'\bICD[-\s]?\d*\b',  # ICD, ICD-9, ICD-10, ICD9, ICD10, etc.
    r'\binternational classification of diseases\b',
    r'\bmedical cod(ing|e|es)\b',
    r'\bclinical cod(ing|e|es)\b',
    r'\bdiagnosis cod(ing|e|es)\b',
    r'\bdiagnostic cod(ing|e|es)\b',
    r'\bcode assignment\b',
    r'\bICD code\b'
]

# AI/ML/Automation terms (indicates automated/computational approach)
AI_ML_TERMS = [
    r'\bdeep learning\b',
    r'\bmachine learning\b',
    r'\bneural network\b',
    r'\bBERT\b',
    r'\bLSTM\b',
    r'\btransformer\b',
    r'\bGPT\b',
    r'\bLLM\b',
    r'\blarge language model\b',
    r'\bNLP\b',
    r'\bnatural language processing\b',
    r'\bconvolutional neural\b',
    r'\brecurrent neural\b',
    r'\bRNN\b',
    r'\bCNN\b',
    r'\bGRU\b',
    r'\battention mechanism\b',
    r'\bmulti-task learning\b',
    r'\bsupervised learning\b',
    r'\bunsupervised learning\b',
    r'\bclassification model\b',
    r'\btext classification\b',
    r'\bautomated\b',
    r'\bautomatic\b',
    r'\bcomputer-assisted\b',
    r'\balgorithm\b',
    r'\brule-based\b',
    r'\bknowledge graph\b',
    r'\bontology\b',
    r'\bembedding\b',
    r'\bfine-tun(e|ing)\b',
    r'\bpre-train(ed|ing)\b'
]

# Exclusion terms (papers NOT about ICD coding automation)
EXCLUSION_TERMS = [
    r'\bcoding errors? only\b',
    r'\bcoding guidelines\b',
    r'\bmanual coding\b',
    r'\bcoder training\b',
    r'\bbilling\b',
    r'\breimbursement\b',
    r'\bDRG\b',
    r'\bclaims processing\b',
    r'\bquantum\b',  # Papers about quantum computing, not ICD coding
    r'\bsatellite\b',
    r'\bcontrail detection\b',
    r'\bwearable device\b',
    r'\bgame-based\b',
    r'\bsecurity assessment\b',
    r'\bcode generation security\b',
    r'\binter-rater reliability\b',
    r'\bchart review\b',
    r'\baudit\b',
    r'\bqualitative study\b',
    r'\binterview\b',
    r'\bfocus group\b',
    r'\bsurvey\b',
    r'\beditorial\b',
    r'\bcommentary\b',
    r'\bpolicy\b',
    r'\bguideline\b'
]

# ============================================
# STEP 2: Helper Functions
# ============================================

def combine_text_fields(row):
    """Combine Title, Abstract, and Keywords for searching"""
    text = ''
    if pd.notna(row.get('Title')):
        text += str(row['Title']).lower() + ' '
    if pd.notna(row.get('Abstract')):
        text += str(row['Abstract']).lower() + ' '
    if pd.notna(row.get('Keywords')):
        text += str(row['Keywords']).lower() + ' '
    return text

def contains_any_pattern(text, patterns):
    """Check if text contains any of the regex patterns"""
    if pd.isna(text) or text == '':
        return False
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def count_pattern_matches(text, patterns):
    """Count how many patterns match in the text"""
    if pd.isna(text) or text == '':
        return 0
    count = 0
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            count += 1
    return count

def score_relevance(row):
    """Calculate relevance score for each paper"""
    text = combine_text_fields(row)
    title = str(row.get('Title', '')).lower() if pd.notna(row.get('Title')) else ''
    abstract = str(row.get('Abstract', '')).lower() if pd.notna(row.get('Abstract')) else ''

    score = 0
    reasons = []

    # Check for ICD terms
    icd_in_title = contains_any_pattern(title, ICD_TERMS)
    icd_in_abstract = contains_any_pattern(abstract, ICD_TERMS)

    if icd_in_title:
        score += 10
        reasons.append("ICD in title")
    elif icd_in_abstract:
        score += 5
        reasons.append("ICD in abstract")
    else:
        # If no ICD terms found, it's likely not relevant
        score -= 10
        reasons.append("No ICD terms found")

    # Check for AI/ML terms
    ai_count = count_pattern_matches(text, AI_ML_TERMS)
    ai_score = min(ai_count * 2, 10)  # Max 10 points for AI/ML
    score += ai_score
    if ai_count > 0:
        reasons.append(f"{ai_count} AI/ML terms (+{ai_score})")

    # Check for exclusion terms
    exclusion_count = count_pattern_matches(text, EXCLUSION_TERMS)
    if exclusion_count > 0:
        penalty = min(exclusion_count * 5, 15)
        score -= penalty
        reasons.append(f"Contains {exclusion_count} exclusion terms (-{penalty})")

    # Boost for specific highly relevant terms in title
    if re.search(r'automat(ed|ic|ion).*ICD|ICD.*automat', title, re.IGNORECASE):
        score += 5
        reasons.append("Automated ICD in title (+5)")

    # Boost for "code assignment", "coding task", etc.
    if re.search(r'(code|coding)\s+(assignment|task|prediction|generation)', title, re.IGNORECASE):
        score += 3
        reasons.append("Coding task terminology (+3)")

    # Check for evaluation metrics (indicates technical paper)
    metrics = r'\b(F1|precision|recall|accuracy|AUC|AUROC|evaluation|performance|benchmark)\b'
    if re.search(metrics, text, re.IGNORECASE):
        score += 2
        reasons.append("Has evaluation metrics (+2)")

    return score, '; '.join(reasons)

def categorize_paper(score):
    """Categorize paper based on relevance score"""
    if score >= 15:
        return 'HIGH - Definite Include'
    elif score >= 8:
        return 'MEDIUM - Review Abstract'
    elif score >= 0:
        return 'LOW - Likely Exclude'
    else:
        return 'EXCLUDE - Clear Exclusion'

def write_ris_file(df, output_file):
    """
    Write DataFrame to RIS file format
    Converts CSV columns back to RIS format
    """
    # Mapping of common CSV column names to RIS tags
    column_to_ris_tag = {
        'Type': 'TY',
        'Title': 'TI',
        'DOI': 'DO',
        'Year': 'PY',
        'Authors': 'AU',
        'Publication': 'T2',
        'Abstract': 'AB',
        'Keywords': 'KW',
        'URL': 'UR',
        'Publisher': 'PB',
        'Volume': 'VL',
        'Pages': 'SP',
        'Issue': 'IS'
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        for _, row in df.iterrows():
            # Write each field if it exists and has a value
            for col, tag in column_to_ris_tag.items():
                if col in row and pd.notna(row[col]) and str(row[col]).strip():
                    value = str(row[col])

                    # Handle multiple values (like multiple authors separated by semicolon)
                    if col == 'Authors' and ';' in value:
                        authors = [a.strip() for a in value.split(';') if a.strip()]
                        for author in authors:
                            f.write(f"{tag}  - {author}\n")
                    elif col == 'Keywords' and ';' in value:
                        keywords = [k.strip() for k in value.split(';') if k.strip()]
                        for keyword in keywords:
                            f.write(f"KW  - {keyword}\n")
                    else:
                        f.write(f"{tag}  - {value}\n")

            # Add relevance score and category as notes
            if 'relevance_score' in row and pd.notna(row['relevance_score']):
                f.write(f"N1  - [PRISMA] Score: {row['relevance_score']} | Category: {row['category']}\n")
            if 'reasons' in row and pd.notna(row['reasons']):
                f.write(f"N1  - [PRISMA] Reasons: {row['reasons']}\n")

            # End of record
            f.write("ER  - \n\n")

# ============================================
# STEP 3: Main Processing Function
# ============================================

def screen_papers(input_csv, output_excel='prisma_screening_results.xlsx',
                  year_start=2005, year_end=2026):
    """
    Main function to screen papers using PRISMA-style criteria

    Parameters:
    - input_csv: Path to merged_deduplicated_papers.csv
    - output_excel: Output Excel file with categorized results
    - year_start: Start year for filtering (default 2005)
    - year_end: End year for filtering (default 2026)
    """

    print("="*80)
    print("PRISMA SCREENING FOR ICD CODING LITERATURE")
    print("="*80)

    # Load the data
    print(f"\nLoading data from {input_csv}...")
    df = pd.read_csv(input_csv, low_memory=False)
    print(f"Total records loaded: {len(df):,}")

    # Convert Year to numeric, handling any non-numeric values
    df['Year'] = pd.to_numeric(df['Year'], errors='coerce')

    # Initial count
    total_original = len(df)

    # ============================================
    # STEP 4: Apply Filters
    # ============================================

    # Year filter
    df_filtered = df[df['Year'].between(year_start, year_end, inclusive='both')].copy()
    after_year = len(df_filtered)
    print(f"After year filter ({year_start}-{year_end}): {after_year:,}")
    print(f"  Excluded (outside date range): {total_original - after_year:,}")

    # Publication type filter (keep CONF and JOUR if Type column exists)
    if 'Type' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Type'].isin(['CONF', 'JOUR'])].copy()
        after_pubtype = len(df_filtered)
        print(f"After publication type filter (CONF/JOUR): {after_pubtype:,}")
        print(f"  Excluded (non-CONF/JOUR): {after_year - after_pubtype:,}")
    else:
        after_pubtype = after_year
        print("Note: 'Type' column not found, skipping publication type filter")

    # Calculate relevance scores
    print("\nCalculating relevance scores...")
    df_filtered[['relevance_score', 'reasons']] = df_filtered.apply(
        lambda row: pd.Series(score_relevance(row)), axis=1
    )

    # Categorize papers
    df_filtered['category'] = df_filtered['relevance_score'].apply(categorize_paper)

    # ============================================
    # STEP 5: Generate PRISMA Numbers
    # ============================================

    print("\n" + "="*80)
    print("PRISMA SCREENING RESULTS")
    print("="*80)

    print(f"\n1. Records identified through database searching: {total_original:,}")
    print(f"2. Records after year filter ({year_start}-{year_end}): {after_year:,}")
    print(f"   Excluded (outside date range): {total_original - after_year:,}")
    print(f"3. Records after publication type filter: {after_pubtype:,}")
    print(f"   Excluded (non-CONF/JOUR): {after_year - after_pubtype:,}")

    print("\n" + "-"*80)
    print("RELEVANCE CATEGORIZATION")
    print("-"*80)

    category_counts = df_filtered['category'].value_counts().sort_index()
    for category, count in category_counts.items():
        percentage = (count / len(df_filtered)) * 100
        print(f"{category:30s}: {count:5,} ({percentage:5.1f}%)")

    print(f"\n{'TOTAL':30s}: {len(df_filtered):5,}")

    # ============================================
    # STEP 6: Export Results
    # ============================================

    print(f"\nExporting results to {output_excel}...")

    # Sort by relevance score (highest first)
    df_filtered_sorted = df_filtered.sort_values('relevance_score', ascending=False)

    # Split by category
    df_high = df_filtered_sorted[df_filtered_sorted['category'] == 'HIGH - Definite Include']
    df_medium = df_filtered_sorted[df_filtered_sorted['category'] == 'MEDIUM - Review Abstract']
    df_low = df_filtered_sorted[df_filtered_sorted['category'] == 'LOW - Likely Exclude']
    df_exclude = df_filtered_sorted[df_filtered_sorted['category'] == 'EXCLUDE - Clear Exclusion']

    # Save to Excel with multiple sheets
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        # Summary sheet
        summary_data = {
            'Category': ['HIGH - Definite Include', 'MEDIUM - Review Abstract',
                         'LOW - Likely Exclude', 'EXCLUDE - Clear Exclusion', 'TOTAL'],
            'Count': [len(df_high), len(df_medium), len(df_low), len(df_exclude), len(df_filtered_sorted)],
            'Percentage': [
                f"{(len(df_high)/len(df_filtered_sorted)*100):.1f}%",
                f"{(len(df_medium)/len(df_filtered_sorted)*100):.1f}%",
                f"{(len(df_low)/len(df_filtered_sorted)*100):.1f}%",
                f"{(len(df_exclude)/len(df_filtered_sorted)*100):.1f}%",
                "100.0%"
            ]
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

        # Category sheets
        df_high.to_excel(writer, sheet_name='High_Relevance', index=False)
        df_medium.to_excel(writer, sheet_name='Medium_Relevance', index=False)
        df_low.to_excel(writer, sheet_name='Low_Relevance', index=False)
        df_exclude.to_excel(writer, sheet_name='Excluded', index=False)

        # All filtered results
        df_filtered_sorted.to_excel(writer, sheet_name='All_Filtered', index=False)

    print(f"\n[SUCCESS] Results exported to {output_excel}")
    print("\nSheets created:")
    print(f"  - Summary: Overview statistics")
    print(f"  - High_Relevance: {len(df_high):,} papers (definite include)")
    print(f"  - Medium_Relevance: {len(df_medium):,} papers (review abstract)")
    print(f"  - Low_Relevance: {len(df_low):,} papers (likely exclude)")
    print(f"  - Excluded: {len(df_exclude):,} papers (clear exclusion)")
    print(f"  - All_Filtered: {len(df_filtered_sorted):,} papers (all results)")

    # ============================================
    # STEP 7: Export RIS Files
    # ============================================

    # Create included papers RIS file (HIGH + MEDIUM)
    df_included = pd.concat([df_high, df_medium])
    included_ris = output_excel.replace('.xlsx', '_included.ris')
    print(f"\nExporting included papers to {included_ris}...")
    write_ris_file(df_included, included_ris)
    print(f"[SUCCESS] Included papers exported: {len(df_included):,} papers")

    # Create excluded papers RIS file (LOW + EXCLUDE)
    df_excluded = pd.concat([df_low, df_exclude])
    excluded_ris = output_excel.replace('.xlsx', '_excluded.ris')
    print(f"\nExporting excluded papers to {excluded_ris}...")
    write_ris_file(df_excluded, excluded_ris)
    print(f"[SUCCESS] Excluded papers exported: {len(df_excluded):,} papers")

    print("\nRIS files created:")
    print(f"  - {included_ris}: {len(df_included):,} papers (HIGH + MEDIUM)")
    print(f"  - {excluded_ris}: {len(df_excluded):,} papers (LOW + EXCLUDE)")

    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    print(f"1. Start with HIGH relevance papers ({len(df_high):,} papers)")
    print(f"2. Review abstracts of MEDIUM relevance papers ({len(df_medium):,} papers)")
    print(f"3. Consider LOW relevance papers if you need more coverage ({len(df_low):,} papers)")
    print(f"4. EXCLUDED papers can be safely ignored ({len(df_exclude):,} papers)")
    print("\nRIS FILES:")
    print(f"- Import '{included_ris}' to reference manager for included papers")
    print(f"- Archive '{excluded_ris}' for record keeping")
    print("="*80)

    return df_filtered_sorted

# ============================================
# STEP 8: Main Execution
# ============================================

if __name__ == "__main__":
    import sys

    # Default parameters
    input_file = 'merged_deduplicated_papers.csv'
    output_file = 'prisma_screening_results.xlsx'
    year_start = 2005
    year_end = 2026

    # Command-line arguments support
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    if len(sys.argv) > 3:
        year_start = int(sys.argv[3])
    if len(sys.argv) > 4:
        year_end = int(sys.argv[4])

    # Run screening
    screen_papers(input_file, output_file, year_start, year_end)
