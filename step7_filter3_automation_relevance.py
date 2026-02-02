"""
PRISMA Filter 3: Automation/AI Relevance Check
Papers MUST mention automation/AI/ML methods to pass this filter

Input: filter2_passed.csv (papers that passed Filter 1: Exclusion + Filter 2: ICD Relevance)
Output: FINAL dataset of papers relevant to automated ICD coding
"""

import pandas as pd
import re
from datetime import datetime

# ============================================
# AUTOMATION/AI/ML KEYWORDS (Mandatory)
# ============================================

AUTOMATION_KEYWORDS = {
    # General Automation Terms
    'Automated': r'\bautomated\b',
    'Automatic': r'\bautomatic\b',
    'Computer-Assisted': r'\bcomputer-assisted\b',
    'Algorithm': r'\balgorithm\b',
    'Computational': r'\bcomputational\b',

    # AI/ML General (FIXED: AI acronym now matches!)
    'AI': r'\bAI\b',  # Matches "AI-driven", "AI-based", "AI model"
    'Artificial Intelligence': r'\bartificial intelligence\b',
    'ML': r'\bML\b',  # Matches "ML-based", "ML model"
    'Machine Learning': r'\bmachine learning\b',
    'Deep Learning': r'\bdeep learning\b',
    'Model': r'\bmodel\b',
    'Prediction': r'\bprediction\b',
    'Training': r'\btraining\b',
    'Inference': r'\binference\b',

    # NLP
    'NLP': r'\bNLP\b',
    'Natural Language Processing': r'\bnatural language processing\b',
    'Text Classification': r'\btext classification\b',
    'Text Mining': r'\btext mining\b',
    'Data Mining': r'\bdata mining\b',

    # Neural Networks & Architectures
    'Neural Network': r'\bneural network\b',
    'Deep Neural Network': r'\bdeep neural network\b',
    'Convolutional Neural Network': r'\bconvolutional neural\b',
    'Recurrent Neural Network': r'\brecurrent neural\b',
    'CNN': r'\bCNN\b',
    'RNN': r'\bRNN\b',
    'LSTM': r'\bLSTM\b',
    'BiLSTM': r'\b(BiLSTM|Bi-LSTM|bidirectional LSTM)\b',
    'GRU': r'\bGRU\b',

    # Transformers & LLMs
    'Transformer': r'\btransformer\b',
    'BERT': r'\bBERT\b',
    'GPT': r'\bGPT\b',
    'LLM': r'\bLLM\b',
    'Large Language Model': r'\blarge language model\b',
    'Attention Mechanism': r'\battention mechanism\b',
    'Self-Attention': r'\bself-attention\b',
    'Encoder-Decoder': r'\bencoder-decoder\b',
    'Seq2Seq': r'\b(seq2seq|sequence-to-sequence)\b',

    # Learning Paradigms
    'Supervised Learning': r'\bsupervised learning\b',
    'Unsupervised Learning': r'\bunsupervised learning\b',
    'Semi-Supervised': r'\bsemi-supervised\b',
    'Self-Supervised': r'\bself-supervised\b',
    'Reinforcement Learning': r'\breinforcement learning\b',
    'Transfer Learning': r'\btransfer learning\b',
    'Multi-Task Learning': r'\bmulti-task learning\b',
    'Few-Shot': r'\bfew-shot\b',
    'Zero-Shot': r'\bzero-shot\b',

    # Classification & Labeling
    'Classification Model': r'\bclassification model\b',
    'Multi-Label': r'\bmulti-label\b',
    'Multi-Class': r'\bmulti-class\b',
    'Hierarchical': r'\bhierarchical\b',
    'Label Embedding': r'\blabel embedding\b',

    # Traditional ML Algorithms
    'Support Vector': r'\bsupport vector\b',
    'SVM': r'\bSVM\b',
    'Random Forest': r'\brandom forest\b',
    'Decision Tree': r'\bdecision tree\b',
    'XGBoost': r'\bXGBoost\b',
    'Gradient Boosting': r'\bgradient boosting\b',
    'Naive Bayes': r'\bnaive bayes\b',
    'Logistic Regression': r'\blogistic regression\b',
    'K-Nearest': r'\bk-nearest\b',

    # Embeddings & Representations
    'Embedding': r'\bembedding\b',
    'Word2Vec': r'\bword2vec\b',
    'GloVe': r'\bGloVe\b',
    'FastText': r'\bfasttext\b',
    'Feature Extraction': r'\bfeature extraction\b',
    'Representation Learning': r'\brepresentation learning\b',

    # Training Techniques
    'Fine-Tuning': r'\bfine-tun(e|ing)\b',
    'Pre-Training': r'\bpre-train(ed|ing)\b',
    'Pre-Trained': r'\bpre-trained\b',

    # Knowledge-Based
    'Rule-Based': r'\brule-based\b',
    'Knowledge Graph': r'\bknowledge graph\b',
    'Ontology': r'\bontology\b'
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

def find_automation_keywords(text):
    """Find all automation/AI keywords that match in the text"""
    matches = []
    for keyword_name, pattern in AUTOMATION_KEYWORDS.items():
        if re.search(pattern, text, re.IGNORECASE):
            matches.append(keyword_name)
    return matches

def check_automation_relevance(row):
    """
    Check if paper is about automation/AI/ML methods
    Returns: (decision, matched_terms, location, reason)
    """
    title, abstract, keywords = get_text_from_row(row)

    # Check if all fields are empty
    if not title and not abstract and not keywords:
        return 'EXCLUDE', '', 'N/A', 'No title, abstract, or keywords available for evaluation'

    # Check Title first
    title_matches = find_automation_keywords(title)
    if title_matches:
        matched_terms_str = '; '.join(title_matches)
        reason = f"Paper mentions automation/AI terms in TITLE: {matched_terms_str}. Relevant to automated ICD coding."
        return 'PASS', matched_terms_str, 'Title', reason

    # Check Abstract
    abstract_matches = find_automation_keywords(abstract)
    if abstract_matches:
        matched_terms_str = '; '.join(abstract_matches)
        reason = f"Paper mentions automation/AI terms in ABSTRACT: {matched_terms_str}. Relevant to automated ICD coding."
        return 'PASS', matched_terms_str, 'Abstract', reason

    # Check Keywords
    keyword_matches = find_automation_keywords(keywords)
    if keyword_matches:
        matched_terms_str = '; '.join(keyword_matches)
        reason = f"Paper mentions automation/AI terms in KEYWORDS: {matched_terms_str}. Relevant to automated ICD coding."
        return 'PASS', matched_terms_str, 'Keywords', reason

    # No automation/AI terms found anywhere
    reason = "Paper does not mention automation, AI, machine learning, or computational methods. Likely about manual ICD coding, coding guidelines, or general ICD topics without automation."
    return 'EXCLUDE', '', 'N/A', reason

# ============================================
# MAIN FILTERING FUNCTION
# ============================================

def filter_automation_relevance(input_csv='filter2_passed.csv',
                                output_all='filter3_all_results.csv',
                                output_pass='filter3_passed.csv',
                                output_exclude='filter3_excluded.csv'):
    """
    Filter 3: Check for Automation/AI relevance

    Parameters:
    - input_csv: Input CSV file (papers that passed Filter 1: Exclusion and Filter 2: ICD Relevance)
    - output_all: Complete results with all papers
    - output_pass: Papers that PASSED (have automation/AI terms)
    - output_exclude: Papers that were EXCLUDED (no automation/AI terms)
    """

    print("="*80)
    print("PRISMA FILTER 3: AUTOMATION/AI RELEVANCE CHECK")
    print("="*80)
    print("\nCriteria: Paper MUST mention automation/AI/ML methods")
    print("Action: If NO automation/AI terms found -> EXCLUDE")
    print("Checking: Title OR Abstract OR Keywords")

    # Load data
    print(f"\nLoading data from {input_csv}...")
    df = pd.read_csv(input_csv, low_memory=False)
    print(f"Total records loaded: {len(df):,}")
    print("(Papers that passed Filter 1: Exclusion + Filter 2: ICD Relevance)")

    # ============================================
    # APPLY AUTOMATION RELEVANCE FILTER
    # ============================================

    print("\n" + "-"*80)
    print("Applying Automation/AI Relevance Filter...")
    print("-"*80)

    # Apply the filter
    results = df.apply(check_automation_relevance, axis=1)
    df['Filter3_Decision'] = results.apply(lambda x: x[0])
    df['Filter3_Matched_Terms'] = results.apply(lambda x: x[1])
    df['Filter3_Match_Location'] = results.apply(lambda x: x[2])
    df['Filter3_Reason'] = results.apply(lambda x: x[3])

    # Count results
    passed_count = (df['Filter3_Decision'] == 'PASS').sum()
    excluded_count = (df['Filter3_Decision'] == 'EXCLUDE').sum()

    # ============================================
    # DISPLAY RESULTS
    # ============================================

    print("\n" + "="*80)
    print("FILTER 2 RESULTS: AUTOMATION/AI RELEVANCE")
    print("="*80)
    print(f"\nTotal papers evaluated: {len(df):,}")
    print(f"\n  [PASS] PASSED (has automation/AI terms):  {passed_count:,} ({passed_count/len(df)*100:.1f}%)")
    print(f"  [EXCLUDE] EXCLUDED (no automation/AI terms): {excluded_count:,} ({excluded_count/len(df)*100:.1f}%)")

    # Show where automation/AI terms were found (for passed papers)
    if passed_count > 0:
        print("\n" + "-"*80)
        print("Automation/AI Terms Found In:")
        print("-"*80)
        location_counts = df[df['Filter3_Decision'] == 'PASS']['Filter3_Match_Location'].value_counts()
        for location, count in location_counts.items():
            print(f"  {location:15s}: {count:5,} papers ({count/passed_count*100:.1f}%)")

    # ============================================
    # EXPORT RESULTS
    # ============================================

    # Select columns for output
    output_columns = [
        'Filter1_Decision', 'Filter1_Matched_Terms', 'Filter1_Match_Location',
        'Filter3_Decision', 'Filter3_Matched_Terms', 'Filter3_Match_Location', 'Filter3_Reason',
        'Title', 'Authors', 'Year', 'Publication', 'Type', 'DOI', 'Abstract', 'Keywords', 'URL'
    ]
    output_columns = [col for col in output_columns if col in df.columns]

    print("\n" + "="*80)
    print("EXPORTING RESULTS")
    print("="*80)

    # 1. Save all results
    print(f"\n1. Saving all papers with Filter 2 decisions to {output_all}...")
    df_output = df[output_columns].copy()
    df_output = df_output.sort_values('Filter3_Decision', ascending=False)  # PASS first
    df_output.to_csv(output_all, index=False, encoding='utf-8')
    print(f"   [SUCCESS] {len(df_output):,} papers saved")

    # 2. Save passed papers
    df_passed = df[df['Filter3_Decision'] == 'PASS'].copy()
    print(f"\n2. Saving PASSED papers to {output_pass}...")
    df_passed[output_columns].to_csv(output_pass, index=False, encoding='utf-8')
    print(f"   [SUCCESS] {len(df_passed):,} papers saved")
    print(f"   *** THIS IS THE FINAL DATASET FOR LITERATURE REVIEW ***")

    # 3. Save excluded papers
    df_excluded = df[df['Filter3_Decision'] == 'EXCLUDE'].copy()
    print(f"\n3. Saving EXCLUDED papers to {output_exclude}...")
    df_excluded[output_columns].to_csv(output_exclude, index=False, encoding='utf-8')
    print(f"   [SUCCESS] {len(df_excluded):,} papers saved")
    print(f"   -> These papers are about ICD coding but not automated")

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
            print(f"  Matched: {row['Filter3_Matched_Terms'][:100]}")
            print(f"  Location: {row['Filter3_Match_Location']}")
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
            print(f"  Reason: {row['Filter3_Reason'][:120]}...")
    else:
        print("  No papers were excluded.")

    # ============================================
    # SUMMARY
    # ============================================

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print(f"1. Review {output_all} to see all filtering decisions")
    print(f"2. This is your FINAL dataset for literature review")
    print(f"3. Archive {output_exclude} (ICD coding but not automated - manual coding)")
    print("\nFilter 3 Complete! All systematic filtering done!")
    print("="*80)

    return df

# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    import sys

    # Default parameters
    input_file = 'filter2_passed.csv'
    output_all = 'filter3_all_results.csv'
    output_pass = 'filter3_passed.csv'
    output_exclude = 'filter3_excluded.csv'

    # Command-line arguments
    if len(sys.argv) > 1:
        input_file = sys.argv[1]

    # Run Filter 2
    filter_automation_relevance(input_file, output_all, output_pass, output_exclude)
