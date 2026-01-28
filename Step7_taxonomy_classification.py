"""
Taxonomy classification for ICD coding literature
Classifies papers across multiple dimensions: methods, ICD versions, data types, tasks, etc.
"""

import pandas as pd
import re
from collections import defaultdict

# ============================================
# Define Taxonomy Keyword Patterns
# ============================================

TAXONOMY = {
    'ML_Method': {
        'Traditional_ML': [
            r'\bSVM\b', r'\brandom forest\b', r'\bnaive bayes\b',
            r'\blogistic regression\b', r'\bk-nearest', r'\bdecision tree',
            r'\bXGBoost\b', r'\bgradient boosting\b', r'\bCRF\b',
            r'\bconditional random field\b', r'\blinear model\b'
        ],
        'RNN_LSTM': [
            r'\bRNN\b', r'\bLSTM\b', r'\bGRU\b', r'\brecurrent neural\b',
            r'\bbi-LSTM\b', r'\bbidirectional LSTM\b', r'\bBiLSTM\b'
        ],
        'CNN': [
            r'\bCNN\b', r'\bconvolutional neural\b', r'\bTextCNN\b',
            r'\bconvolution\b'
        ],
        'Attention': [
            r'\battention mechanism\b', r'\bself-attention\b',
            r'\bmulti-head attention\b', r'\battention-based\b',
            r'\battention layer\b'
        ],
        'BERT_Transformers': [
            r'\bBERT\b', r'\bRoBERTa\b', r'\bClinicalBERT\b', r'\bBioBERT\b',
            r'\btransformer\b', r'\bXLNet\b', r'\bALBERT\b', r'\bELECTRA\b',
            r'\bDeBERTa\b', r'\bLongformer\b', r'\bBigBird\b'
        ],
        'LLM': [
            r'\bLLM\b', r'\blarge language model\b', r'\bGPT\b',
            r'\bClaude\b', r'\bLLaMA\b', r'\bgemini\b', r'\bChatGPT\b',
            r'\bfew-shot prompt\b', r'\bin-context learning\b'
        ],
        'Graph_Neural': [
            r'\bGCN\b', r'\bGAT\b', r'\bgraph neural\b', r'\bRGCN\b',
            r'\bgraph convolutional\b', r'\bgraph attention\b'
        ],
        'Multi_task': [
            r'\bmulti-task\b', r'\bmultitask\b', r'\bjoint learning\b',
            r'\bjoint training\b'
        ],
        'Ensemble': [
            r'\bensemble\b', r'\bhybrid model\b', r'\bcombination\b',
            r'\bstacking\b', r'\bvoting\b'
        ],
        'Rule_Based': [
            r'\brule-based\b', r'\brule system\b', r'\bheuristic\b',
            r'\bregular expression\b', r'\bpattern matching\b',
            r'\bdictionary-based\b'
        ]
    },

    'ICD_Version': {
        'ICD-9': [r'\bICD-?9\b', r'\bICD-?9-?CM\b', r'\bICD-?9-?PCS\b'],
        'ICD-10': [r'\bICD-?10\b', r'\bICD-?10-?CM\b', r'\bICD-?10-?AM\b', r'\bICD-?10-?PCS\b'],
        'ICD-11': [r'\bICD-?11\b'],
        'ICD-O': [r'\bICD-?O\b', r'\boncology.*ICD\b'],
        'Multiple_Versions': [r'\bICD-?9.*ICD-?10\b', r'\bICD-?10.*ICD-?9\b', r'\bcrosswalk\b', r'\bmapping\b']
    },

    'Input_Data': {
        'Discharge_Summary': [r'\bdischarge summar\w+\b', r'\bdischarge note\b'],
        'Clinical_Notes': [
            r'\bclinical note\b', r'\bclinical text\b', r'\bclinical document\b',
            r'\bprogress note\b', r'\bdoctor.*note\b', r'\bphysician note\b'
        ],
        'Radiology': [r'\bradiology report\b', r'\bradiology\b', r'\bimaging report\b'],
        'Pathology': [r'\bpathology report\b', r'\bpathology\b'],
        'EHR': [
            r'\bEHR\b', r'\belectronic health record\b',
            r'\belectronic medical record\b', r'\bEMR\b'
        ],
        'Nursing': [r'\bnursing note\b', r'\bnursing documentation\b'],
        'Operative': [r'\boperative note\b', r'\bsurgery note\b', r'\bsurgical report\b'],
        'Emergency': [r'\bemergency.*note\b', r'\bED note\b', r'\bemergency department\b']
    },

    'Task_Type': {
        'Multi_label': [r'\bmulti-label\b', r'\bmultilabel\b', r'\bmultiple code\b'],
        'Hierarchical': [r'\bhierarchical\b', r'\bhierarchy\b', r'\btree structure\b'],
        'Explainable': [
            r'\bexplain\w+\b', r'\binterpret\w+\b', r'\bevidence\b',
            r'\battention visualization\b', r'\bXAI\b', r'\bLIME\b', r'\bSHAP\b'
        ],
        'Few_shot': [r'\bfew-shot\b', r'\bzero-shot\b', r'\blow-resource\b'],
        'Imbalance': [r'\bimbalanc\w+\b', r'\blong-tail\b', r'\brare code\b', r'\bdata scarcity\b'],
        'Extreme_Multilabel': [r'\bextreme multi-label\b', r'\bXMLC\b', r'\bthousands of code\b'],
        'Code_Assignment': [r'\bcode assignment\b', r'\bautomatic.*assign\b', r'\bautomatic.*cod\b']
    },

    'Dataset': {
        'MIMIC-III': [r'\bMIMIC-?III\b', r'\bMIMIC-?3\b', r'\bMIMIC3\b'],
        'MIMIC-IV': [r'\bMIMIC-?IV\b', r'\bMIMIC-?4\b', r'\bMIMIC4\b'],
        'eICU': [r'\beICU\b', r'\be-ICU\b'],
        'CMC': [r'\bCMC\b', r'\bComputational Medicine Center\b'],
        'Private_Hospital': [r'\bprivate.*hospital\b', r'\bhospital.*data\b', r'\binstitutional\b'],
        'Claims': [r'\bclaims data\b', r'\badministrative.*data\b', r'\binsurance.*data\b']
    },

    'Key_Contribution': {
        'Knowledge_Graph': [
            r'\bknowledge graph\b', r'\bontology\b', r'\bKG\b',
            r'\bSNOMED\b', r'\bUMLS\b', r'\bmedical ontology\b'
        ],
        'Transfer_Learning': [
            r'\btransfer learning\b', r'\bpre-train\w+\b', r'\bfine-tun\w+\b',
            r'\bdomain adaptation\b'
        ],
        'Efficiency': [
            r'\befficiency\b', r'\bfast\w*\b', r'\bscalabl\w+\b',
            r'\breal-time\b', r'\bcomputational cost\b', r'\bspeed\b'
        ],
        'Weakly_Supervised': [
            r'\bweakly supervised\b', r'\bdistant supervision\b',
            r'\bself-supervised\b', r'\bunsupervised\b'
        ],
        'Active_Learning': [r'\bactive learning\b', r'\bhuman-in-the-loop\b'],
        'Retrieval_Augmented': [r'\bRAG\b', r'\bretrieval.*augmented\b', r'\bretrieval-based\b'],
        'Prompt_Engineering': [r'\bprompt\b', r'\bprompting\b', r'\binstruction.*tuning\b']
    },

    'Evaluation_Metric': {
        'F1_Score': [r'\bF1\b', r'\bF-?1 score\b', r'\bmacro.*F1\b', r'\bmicro.*F1\b'],
        'Precision_Recall': [r'\bprecision\b', r'\brecall\b', r'\bPPV\b', r'\bsensitivity\b'],
        'Accuracy': [r'\baccuracy\b', r'\bcorrect.*rate\b'],
        'AUC': [r'\bAUC\b', r'\bAUROC\b', r'\barea under\b'],
        'Top_K': [r'\btop-?k\b', r'\btop-?5\b', r'\btop-?10\b', r'\btop k accuracy\b'],
        'Hamming': [r'\bHamming\b', r'\bHamming loss\b']
    }
}

# ============================================
# Helper Functions
# ============================================

def combine_text_fields(row):
    """Combine Title, Abstract, and Keywords for classification"""
    text = ''
    if pd.notna(row.get('Title')):
        text += str(row['Title']).lower() + ' '
    if pd.notna(row.get('Abstract')):
        text += str(row['Abstract']).lower() + ' '
    if pd.notna(row.get('Keywords')):
        text += str(row['Keywords']).lower() + ' '
    return text

def classify_paper(row):
    """Classify a paper across all taxonomy dimensions"""
    text = combine_text_fields(row)

    classification = {}

    for dimension, categories in TAXONOMY.items():
        matches = []
        for category, patterns in categories.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    matches.append(category)
                    break  # Only count once per category

        classification[dimension] = matches if matches else ['Unclassified']

    return classification

# ============================================
# Main Function
# ============================================

def classify_papers(input_csv='prisma_screening_results_all_filtered.csv',
                   output_csv='papers_with_taxonomy.csv',
                   include_only=True):
    """
    Classify papers using taxonomy

    Parameters:
    - input_csv: Input CSV file (from Step 6)
    - output_csv: Output CSV with taxonomy classifications
    - include_only: If True, only classify HIGH + MEDIUM papers
    """

    print("="*80)
    print("TAXONOMY CLASSIFICATION FOR ICD CODING LITERATURE")
    print("="*80)

    # Load data
    print(f"\nLoading data from {input_csv}...")
    df = pd.read_csv(input_csv, low_memory=False)
    print(f"Total papers loaded: {len(df):,}")

    # Filter for included papers only if requested
    if include_only:
        if 'category' in df.columns:
            df = df[df['category'].isin(['HIGH - Definite Include', 'MEDIUM - Review Abstract'])].copy()
            print(f"Filtering for HIGH + MEDIUM papers: {len(df):,}")
        else:
            print("Warning: 'category' column not found. Classifying all papers.")

    # Apply classification
    print("\nClassifying papers across taxonomy dimensions...")
    print("This may take a few minutes...")

    classifications = df.apply(classify_paper, axis=1)

    # Convert to separate columns
    for dimension in TAXONOMY.keys():
        df[dimension] = classifications.apply(lambda x: '; '.join(x[dimension]))

    # Save classified results
    print(f"\nSaving classified results to {output_csv}...")
    df.to_csv(output_csv, index=False)
    print(f"[SUCCESS] Taxonomy classification complete! ({len(df):,} papers)")

    # ============================================
    # Generate Taxonomy Statistics
    # ============================================

    print("\n" + "="*80)
    print("TAXONOMY DISTRIBUTION")
    print("="*80)

    stats_output = []

    for dimension in TAXONOMY.keys():
        print(f"\n{dimension}:")
        print("-" * 60)
        stats_output.append(f"\n{dimension}:")
        stats_output.append("-" * 60)

        # Count each category
        category_counts = defaultdict(int)
        for categories in df[dimension]:
            for cat in categories.split('; '):
                category_counts[cat] += 1

        # Sort and display
        for category, count in sorted(category_counts.items(),
                                       key=lambda x: x[1], reverse=True):
            percentage = (count / len(df)) * 100
            line = f"  {category:35s}: {count:5,} ({percentage:5.1f}%)"
            print(line)
            stats_output.append(line)

    # Save statistics to file
    stats_file = output_csv.replace('.csv', '_statistics.txt')
    with open(stats_file, 'w', encoding='utf-8') as f:
        f.write("TAXONOMY DISTRIBUTION STATISTICS\n")
        f.write("="*80 + "\n")
        f.write(f"Total papers analyzed: {len(df):,}\n")
        f.write('\n'.join(stats_output))

    print(f"\n[SUCCESS] Statistics saved to {stats_file}")

    # ============================================
    # Cross-tabulation Analysis
    # ============================================

    print("\n" + "="*80)
    print("CROSS-TABULATION: ML Method × ICD Version")
    print("="*80)

    # Create crosstab (use primary category only)
    method_simple = df['ML_Method'].str.split('; ').str[0]
    version_simple = df['ICD_Version'].str.split('; ').str[0]

    crosstab = pd.crosstab(method_simple, version_simple, margins=True)
    print(crosstab)

    # Save crosstab
    crosstab_file = output_csv.replace('.csv', '_crosstab_method_version.csv')
    crosstab.to_csv(crosstab_file)
    print(f"\n[SUCCESS] Cross-tabulation saved to {crosstab_file}")

    # ============================================
    # Temporal Evolution Analysis
    # ============================================

    if 'Year' in df.columns:
        print("\n" + "="*80)
        print("TEMPORAL EVOLUTION: Methods Over Time")
        print("="*80)

        # Convert Year to numeric
        df['Year'] = pd.to_numeric(df['Year'], errors='coerce')

        # Group by year and primary method
        df_temporal = df[df['Year'].notna()].copy()
        temporal = df_temporal.groupby(
            ['Year', df_temporal['ML_Method'].str.split('; ').str[0]]
        ).size().unstack(fill_value=0)

        print(temporal)

        # Export for visualization
        temporal_file = output_csv.replace('.csv', '_temporal_evolution.csv')
        temporal.to_csv(temporal_file)
        print(f"\n[SUCCESS] Temporal evolution saved to {temporal_file}")

    # ============================================
    # Summary Statistics
    # ============================================

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total papers classified: {len(df):,}")
    print(f"\nOutput files:")
    print(f"  1. {output_csv} - Papers with taxonomy classifications")
    print(f"  2. {stats_file} - Detailed statistics")
    print(f"  3. {crosstab_file} - Method × ICD Version cross-tabulation")
    if 'Year' in df.columns:
        print(f"  4. {temporal_file} - Temporal evolution of methods")
    print("="*80)

    return df

# ============================================
# Main Execution
# ============================================

if __name__ == "__main__":
    import sys

    # Default parameters
    input_file = 'prisma_screening_results_all_filtered.csv'
    output_file = 'papers_with_taxonomy.csv'
    include_only = True

    # Command-line arguments support
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    if len(sys.argv) > 3:
        include_only = sys.argv[3].lower() in ['true', '1', 'yes']

    # Run classification
    classify_papers(input_file, output_file, include_only)
