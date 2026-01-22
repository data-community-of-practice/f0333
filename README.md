# Literature Review Data Fetcher for Automated ICD Coding

A comprehensive toolkit for collecting and organising academic literature on automated International Classification of Diseases (ICD) coding from multiple sources including PubMed, ACM Digital Library and Scopus. This is content material for an upcoming publication. This is a placeholder for future work.

## Overview - PART A

This project provides automated scripts to fetch research articles from major academic databases for systematic literature reviews. It's specifically designed to handle large-scale data collection with features like:

- Fetching unlimited results by bypassing API limitations
- Deduplication of articles across multiple sources
- Export to both JSON and CSV formats
- Support for year-based filtering
- Automatic retry and rate limiting

## Features

- **Multi-source fetching**: PubMed, ACM Digital Library, and Scopus APIs
- **Bypass API limits**: Year-by-year splitting for large result sets (>5000)
- **Flexible authentication**: API key and OAuth2 support
- **Rich metadata extraction**: Authors, abstracts, citations, MeSH terms, DOIs, etc.
- **Multiple export formats**: JSON and CSV
- **Automatic deduplication**: Remove duplicate articles by DOI
- **Configurable searches**: Customize queries and result limits via config file

## Project Structure

```
.
├── Step1_fetchallscopusresults.py      # Fetch ScienceDirect/Scopus results by year
├── Step1_pubmed_fetcher.py             # Fetch PubMed results
├── Helper_sciencedirect_fetcher_v2.py  # Helper class for ScienceDirect API
├── convert_pubmed_to_ris.py            # PubMed JSON to RIS converter
├── convert_scopus_to_ris.py            # Scopus JSON to RIS converter
├── convert_enw_to_ris.py               # ACM EndNote to RIS converter
├── Step2_convert_all_to_ris.py         # Master converter for all formats
├── Step3_merge_ris_by_keyphrase.py     # Merge and deduplicate RIS files
├── Step4_filter_by_journal.py          # Filter by target journals
├── Step5_filter_by_type.py             # Filter by article type (JOUR/CONF only)
├── Step6_filter_by_content.py          # Filter by content analysis (ICD as task)
├── Step7_filter_by_methodology.py      # Filter for methodological/technical papers
├── Step8_tag_papers.py                 # Tag papers by method/challenge/dataset/period
├── Step9_select_representatives.py     # Select representative papers from each bucket
├── template_config.ini                 # Configuration template
├── config.ini                          # Your actual config (not in git)
├── output_data.tar.gz                  # Sample output data archive
└── output/                             # All results
```

## Converting to RIS Format

All fetched data can be converted to RIS (Research Information Systems) format for easy import into reference management software like Zotero, Mendeley, EndNote, or RefWorks.

### Conversion Scripts

Three converter scripts are provided:

1. **convert_pubmed_to_ris.py** - Converts PubMed JSON files to RIS
2. **convert_scopus_to_ris.py** - Converts Scopus/ScienceDirect JSON files to RIS
3. **convert_enw_to_ris.py** - Converts ACM EndNote (.enw) files to RIS
4. **Step2_convert_all_to_ris.py** - Master script to convert all formats at once

### Usage

Convert all files at once:
```bash
python Step2_convert_all_to_ris.py output
```

Convert specific source individually:
```bash
# PubMed only
python convert_pubmed_to_ris.py output/pubmed_output/

# Scopus only
python convert_scopus_to_ris.py output/Scopus/

# ACM EndNote only
python convert_enw_to_ris.py output/acm_output/
```

Convert a single file:
```bash
python convert_pubmed_to_ris.py input.json output.ris
```

### Output

RIS files are created in the same directory as the source files:
- `output/pubmed_output/*.ris`
- `output/Scopus/*.ris`
- `output/acm_output/*.ris`

### Importing into Reference Managers

The generated RIS files can be directly imported into:
- **Zotero**: File → Import → Select RIS file
- **Mendeley**: File → Import → RIS
- **EndNote**: File → Import → File → Choose RIS filter
- **RefWorks**: Add → Import References → From File

## Merging and Deduplicating RIS Files - PART B

After converting all sources to RIS format, you may want to merge files by key phrase and remove duplicates across different sources (PubMed, Scopus, ACM).

### Merger Script

**Step3_merge_ris_by_keyphrase.py** - Merges RIS files by key phrase and deduplicates based on DOI

This script:
- Automatically groups RIS files by key phrase
- Merges all files for each key phrase (e.g., combines PubMed, Scopus, and ACM results for "automated_ICD_coding")
- Deduplicates based on DOI
- Retains all records without DOI

### Usage

```bash
python Step3_merge_ris_by_keyphrase.py output/ merged_output/
```

Or use default output directory:
```bash
python Step3_merge_ris_by_keyphrase.py output/
```

### Key Phrases Recognized

The script automatically recognizes these key phrases:
- `automated_ICD_coding`
- `automatic_international_classification_of_diseases`
- `computer_assisted_ICD_coding`
- `clinical_coding_ICD`

### Example Results

Running the merger on the sample data shows detailed tracking:

```
======================================================================
Key Phrase: automated_ICD_coding
======================================================================
Input: 2 file(s) to merge

Source files:
  - automated_ICD_coding_pubmed.ris                                 430 records
  - automated_ICD_coding_ALL_articles.ris                          3458 records

----------------------------------------------------------------------
BEFORE MERGING:    3888 total records
AFTER MERGING:     3733 unique records
----------------------------------------------------------------------
Change:             155 duplicates removed (4.0%)
```

**Overall Summary:**
```
OVERALL STATISTICS:
  Key phrases processed:     4
  Total records BEFORE:      51,774
  Total records AFTER:       49,767
  Total duplicates removed:   2,007 (3.9%)

BREAKDOWN BY KEY PHRASE:
----------------------------------------------------------------------
Key Phrase                                      Before    After  Removed
----------------------------------------------------------------------
Automated Icd Coding                              3888     3733      155
Automatic International Classification Of...     15161    14895      266
Clinical Coding Icd                              31815    30251     1564
Computer Assisted Icd Coding                       910      888       22
----------------------------------------------------------------------
TOTAL                                            51774    49767     2007
----------------------------------------------------------------------
```

**Merged files created:**
- `automated_ICD_coding_merged.ris` - 3,733 unique records
- `automatic_international_classification_of_diseases_merged.ris` - 14,895 unique records
- `clinical_coding_ICD_merged.ris` - 30,251 unique records
- `computer_assisted_ICD_coding_merged.ris` - 888 unique records

### Deduplication Logic

- **Primary key**: DOI (Digital Object Identifier)
- Records with the same DOI are considered duplicates
- First occurrence is kept, subsequent duplicates are removed
- Records without DOI are all retained (not deduplicated)

## Filtering - PART C

### Filtering by Target Journals

After merging and deduplication, you can further filter papers to keep only those published in specific high-quality journals relevant to your research.

### Filter Script

**Step4_filter_by_journal.py** - Filters RIS files to keep only papers from target journals

This script:
- Scans journal names in RIS files (JO, JF, and T2 tags)
- Matches against a predefined list of target journals
- Handles case-insensitive and partial matching
- Provides detailed statistics on filtering

### Target Journals

The script filters for these 11 journals:
1. Journal of Biomedical Informatics
2. Journal of the American Medical Informatics Association
3. International Journal of Medical Informatics
4. BMC Medical Informatics and Decision Making
5. Studies in Health Technology and Informatics
6. Computers in Biology and Medicine
7. IEEE Access
8. Expert Systems with Applications
9. Biomedical Signal Processing and Control
10. Sensors
11. Applied Sciences Switzerland

### Usage

Filter all merged files:
```bash
python Step4_filter_by_journal.py merged_output/ filtered_output/
```

Filter a single file:
```bash
python Step4_filter_by_journal.py input.ris output_filtered.ris
```

### Example Results

Filtering the merged files produces focused results:

```
OVERALL STATISTICS:
  Files processed:           4
  Total records BEFORE:      49,767
  Total records AFTER:        2,324
  Total records removed:     47,443 (95.3%)
  Retention rate:            4.7%

MATCHED JOURNALS DISTRIBUTION:
----------------------------------------------------------------------
  IEEE Access                                                     361
  Journal of Biomedical Informatics                               260
  Journal of the American Medical Informatics Association         227
  Studies in Health Technology and Informatics                    224
  Sensors                                                         223
  Computers in Biology and Medicine                               214
  BMC Medical Informatics and Decision Making                     200
  Biomedical Signal Processing and Control                        192
  International Journal of Medical Informatics                    158
  Expert Systems with Applications                                139
  Applied Sciences Switzerland                                    126
----------------------------------------------------------------------
  TOTAL                                                          2,324
```

**Filtered files created:**
- `automated_ICD_coding_merged_filtered.ris` - 338 records
- `automatic_international_classification_of_diseases_merged_filtered.ris` - 1,324 records
- `clinical_coding_ICD_merged_filtered.ris` - 615 records
- `computer_assisted_ICD_coding_merged_filtered.ris` - 47 records

### Customizing Target Journals

To modify the target journal list, edit the `TARGET_JOURNALS` list at the top of `Step4_filter_by_journal.py`:

```python
TARGET_JOURNALS = [
    "Your Journal Name Here",
    "Another Journal Name",
    # Add more journals as needed
]
```

## Filtering by Article Type

As a final filtering step, you can remove books and book chapters, keeping only journal articles and conference papers.

### Filter Script

**Step5_filter_by_type.py** - Filters RIS files by article type

This script:
- Keeps only journal articles (JOUR) and conference papers (CONF)
- Removes books (BOOK) and book chapters (CHAP)
- Shows detailed statistics on types filtered

### Usage

Filter all journal-filtered files:
```bash
python Step5_filter_by_type.py filtered_output/ final_output/
```

Filter a single file:
```bash
python Step5_filter_by_type.py input.ris output_type_filtered.ris
```

### Example Results

Filtering by article type produces focused research outputs:

```
OVERALL STATISTICS:
  Files processed:           4
  Total records BEFORE:      2,324
  Total records AFTER:       2,321
  Total records removed:     3 (0.1%)
  Retention rate:            99.9%

KEPT TYPES DISTRIBUTION:
----------------------------------------------------------------------
  Journal Article                                                2,182
  Conference Paper                                                 139
----------------------------------------------------------------------
  TOTAL KEPT                                                     2,321

REMOVED TYPES DISTRIBUTION:
----------------------------------------------------------------------
  Book                                                              3
----------------------------------------------------------------------
  TOTAL REMOVED                                                     3
```

**Final filtered files:**
- `automated_ICD_coding_merged_filtered_type_filtered.ris` - 338 records
- `automatic_international_classification_of_diseases_merged_filtered_type_filtered.ris` - 1,321 records
- `clinical_coding_ICD_merged_filtered_type_filtered.ris` - 615 records
- `computer_assisted_ICD_coding_merged_filtered_type_filtered.ris` - 47 records

### Article Type Distribution

After all filtering steps:
- **Journal Articles (JOUR)**: 2,182 records (94.0%)
- **Conference Papers (CONF)**: 139 records (6.0%)

## Filtering by Content (ICD Coding as Primary Task)

The final and most sophisticated filtering step uses content analysis to identify papers where ICD coding is the primary research task, not just used for cohort identification or metadata.

### Filter Script

**Step6_filter_by_content.py** - Intelligent content analysis filter

This script:
- Analyzes title, abstract, and keywords using regex patterns
- Identifies positive signals (ICD coding as the task)
- Detects negative signals (ICD codes used only for cohort/metadata)
- Uses a scoring system to make filtering decisions
- Provides detailed reasoning for each decision

### Filtering Criteria

**Positive Signals (KEEP):**
- Strong phrases: "ICD coding", "automated ICD", "code assignment", etc.
- Model verbs near ICD: "predict", "classify", "assign", "automate"
- ML/NLP signals: "machine learning", "deep learning", "transformer", "BERT"

**Negative Signals (REMOVE):**
- "used ICD codes to identify"
- "patients identified using ICD"
- "ICD ... cohort" / "ICD ... phenotyping"
- "retrospective cohort" / "population-based"
- "incidence" / "prevalence" / "mortality"

### Scoring System

The script calculates positive and negative scores:
- **Strong positive** (score ≥ 3): Keep regardless of negatives
- **Moderate positive** (score ≥ 2, negatives ≤ 2): Keep
- **Strong negative** (negatives ≥ 3, positives < 2): Remove
- **Weak positive** (any positive signals): Keep
- **No clear signals**: Remove (too ambiguous)

### Usage

Filter type-filtered files:
```bash
python Step6_filter_by_content.py final_output/ curated_output/
```

Filter a single file:
```bash
python Step6_filter_by_content.py input.ris output_content_filtered.ris
```

### Example Results

Content filtering produces highly curated research papers:

```
OVERALL STATISTICS:
  Files processed:           4
  Total records BEFORE:      2,321
  Total records AFTER:        942
  Total records removed:     1,379 (59.4%)
  Retention rate:            40.6%

REASONS FOR KEEPING RECORDS:
----------------------------------------------------------------------
  Weak positive signals                                           509
  Strong positive signals                                         332
  Moderate positive signals                                       101
----------------------------------------------------------------------
  TOTAL KEPT                                                      942

REASONS FOR REMOVING RECORDS:
----------------------------------------------------------------------
  No clear ICD coding task signals                               1,350
  Strong negative signals (cohort/metadata use)                    29
----------------------------------------------------------------------
  TOTAL REMOVED                                                  1,379
```

**Curated files created:**
- `automated_ICD_coding_merged_filtered_type_filtered_content_filtered.ris` - 165 records
- `automatic_international_classification_of_diseases_merged_filtered_type_filtered_content_filtered.ris` - 473 records
- `clinical_coding_ICD_merged_filtered_type_filtered_content_filtered.ris` - 276 records
- `computer_assisted_ICD_coding_merged_filtered_type_filtered_content_filtered.ris` - 28 records

### Example Decisions

**Kept (Strong Positive):**
- Title: "Automated ICD coding via unsupervised knowledge integration"
- Reason: Strong positive signals (Score: +16 / -0)

**Removed (No Clear Signals):**
- Title: "Knowledge acquisition for computation of semantic distance between WHO-ART terms"
- Reason: No clear ICD coding task signals (Score: +0 / -0)

**Removed (Strong Negative):**
- Title: "Using clinical data to predict high-cost performance coding issues associated with pressure ulcers"
- Reason: ICD used for cohort identification only (Score: +1 / -9)

### Customizing Filtering Patterns

To modify the filtering patterns, edit the lists at the top of `Step6_filter_by_content.py`:

```python
POS_PHRASES = [
    r"\bicd coding\b",
    r"\bclinical coding\b",
    # Add your patterns...
]

NEG_PHRASES = [
    r"\bused icd (codes? )?to identify\b",
    # Add your patterns...
]
```

## Filtering by Methodology (Technical/Methods Focus)

The final filtering step focuses on methodological and technical papers by keeping papers with method or evaluation signals and removing non-methodological studies like audits, training programs, or guidelines.

### Filter Script

**Step7_filter_by_methodology.py** - Filters for methodological/technical papers

This script:
- Keeps papers with method signals (ML, NLP, algorithms, systems)
- Keeps papers with evaluation signals (metrics, benchmarking, validation)
- Removes audit/quality studies, training, billing, qualitative, and guidelines
- Provides detailed statistics and reasoning

### Filtering Criteria

**KEEPS papers with:**

*Method/System Signals:*
- Machine learning, deep learning, neural networks (LSTM, CNN, BERT, transformers)
- NLP, language models, LLMs, GPT
- Classification, prediction models, algorithms, pipelines, frameworks
- Multi-label, hierarchical classification
- Weak/distant/self-supervised learning
- Retrieval-augmented systems, prompting, in-context learning
- Embeddings, fine-tuning, pre-training
- Knowledge graphs, ontologies, SNOMED, UMLS
- Rule-based, heuristic, pattern matching systems

*Evaluation Signals:*
- Metrics: F1, precision, recall, accuracy, AUC, AUROC
- Hamming loss, top-k, exact match
- Sensitivity, specificity, PPV, NPV
- Evaluation language: performance, benchmark, baseline, comparison
- Cross-validation, train/test/validation sets, external validation
- Ablation studies, error analysis, confusion matrices

**REMOVES papers with:**
- Audit, chart review, manual review, coding quality studies
- Inter-rater reliability, kappa, agreement studies
- Coder training, education programs, workforce issues
- Billing, reimbursement, DRG, claims processing
- Qualitative studies, interviews, focus groups, surveys, implementation studies
- Guidelines, policies, position papers, editorials, commentaries

### Usage

Filter content-curated files:
```bash
python Step7_filter_by_methodology.py curated_output/ refined_output/
```

Filter a single file:
```bash
python Step7_filter_by_methodology.py input.ris output_methodology_filtered.ris
```

### Example Results

Step 7 filtering produces focused methodological papers:

```
OVERALL STATISTICS:
  Files processed:           4
  Total records BEFORE:       942
  Total records AFTER:        728
  Total records removed:      214 (22.7%)
  Retention rate:            77.3%

REASONS FOR KEEPING RECORDS:
----------------------------------------------------------------------
  Method signals present                                          554
  Strong methodology signals (method + evaluation)                171
  Evaluation signals present                                        3
----------------------------------------------------------------------
  TOTAL KEPT                                                      728

REASONS FOR REMOVING RECORDS:
----------------------------------------------------------------------
  Non-methodological focus (audit/billing/qualitative/guideline)    109
  No methodology or evaluation signals                            105
----------------------------------------------------------------------
  TOTAL REMOVED                                                   214
```

**Refined files created:**
- `automated_ICD_coding_merged_filtered_type_filtered_content_filtered_methodology_filtered.ris` - 121 records
- `automatic_international_classification_of_diseases_merged_filtered_type_filtered_content_filtered_methodology_filtered.ris` - 398 records
- `clinical_coding_ICD_merged_filtered_type_filtered_content_filtered_methodology_filtered.ris` - 195 records
- `computer_assisted_ICD_coding_merged_filtered_type_filtered_content_filtered_methodology_filtered.ris` - 14 records

This step focuses on:
- Technical system development papers
- Novel algorithm/model papers
- Evaluation and benchmarking studies
- Method comparison studies

### Example Decisions

**Kept (Strong Methodology Signals):**
- "Deep learning for automated ICD coding: BERT-based multi-label classification"
- Reason: Method signals + evaluation signals

**Kept (Method Signals):**
- "Rule-based system for ICD code assignment using clinical notes"
- Reason: Method signals present (rule-based, system)

**Removed (Non-Methodological):**
- "Audit of ICD-10 coding accuracy in hospital records"
- Reason: Audit/quality study (not system development)

**Removed (No Signals):**
- "Policy recommendations for ICD-11 adoption"
- Reason: Guideline/policy paper (no methods or evaluation)

### Customizing Filtering Patterns

To modify the filtering patterns, edit the pattern lists at the top of `Step7_filter_by_methodology.py`:

```python
METHOD_PATTERNS = [
    r"\b(machine learning|deep learning|...)\b",
    # Add your patterns...
]

EVAL_PATTERNS = [
    r"\b(f1|precision|recall|...)\b",
    # Add your patterns...
]

NEG_PATTERNS = [
    r"\b(audit|chart review|...)\b",
    # Add your patterns...
]
```

## Tagging Papers by Method, Challenge, and Dataset

After filtering to methodological papers, Step 8 automatically tags each paper to identify research trends, methods used, challenges addressed, and datasets employed.

### Tagging Script

**Step8_tag_papers.py** - Automatic paper tagging and analysis

This script:
- Tags papers by method family (LLM, Transformer, Deep Learning, Classical ML, Rule-based)
- Identifies challenges addressed (Hierarchy, Rare labels, Long text, etc.)
- Detects datasets used (MIMIC, eICU, UCSF, Claims)
- Categorizes by time period (pre2012 to 2023+)
- Detects evaluation metrics, novelty language, and coding task specificity
- Outputs tagged RIS files and analysis CSV

### Tagging Criteria

**Method Families:**
- **LLM_RAG_XAI**: Large language models, GPT, ChatGPT, RAG, prompting, agents
- **TRANSFORMER**: BERT, RoBERTa, DeBERTa, Longformer, BigBird, transformers
- **DEEP_CNN_RNN**: CNN, RNN, LSTM, BiLSTM, GRU, attention mechanisms
- **CLASSICAL_ML**: SVM, logistic regression, naive Bayes, random forest, XGBoost, CRF, HMM
- **RULE_BASED**: Rule-based systems, heuristics, dictionary-based, pattern matching

**Challenges Addressed:**
- **HIERARCHY**: Hierarchical classification, taxonomy, tree-structured codes
- **RARE_LABELS**: Rare/long-tail labels, few-shot learning, data sparsity, imbalanced data
- **LONG_TEXT**: Long documents/notes, sequence length issues, truncation, segmentation
- **EXTREME_MULTILABEL**: Extreme multi-label classification, XMLC
- **COOCCURRENCE_RULES**: Code co-occurrence, combination rules, dependencies
- **MAPPING_INTEROP**: ICD version mapping, crosswalks, ICD-9/10/11 transitions
- **KNOWLEDGE_AUG**: Ontologies, knowledge graphs, UMLS, SNOMED integration
- **EXPLAINABILITY**: Explainable AI, interpretability, LIME, SHAP, rationales

**Datasets:**
- **MIMIC**: MIMIC-III, MIMIC-IV
- **EICU**: eICU database
- **UCSF**: UCSF data
- **CLAIMS**: Administrative claims data

**Time Periods:**
- **pre2012**: Before 2012
- **2012_2016**: 2012-2016
- **2017_2019**: 2017-2019
- **2020_2022**: 2020-2022
- **2023_plus**: 2023 and later

### Usage

Tag refined papers:
```bash
python Step8_tag_papers.py refined_output/ tagged_output/ paper_tags_analysis.csv
```

Tag with defaults:
```bash
python Step8_tag_papers.py refined_output/
```

### Example Results

Tagging the 728 methodological papers produces comprehensive analysis:

```
OVERALL STATISTICS:
  Files processed:           4
  Total papers tagged:       728

METHOD FAMILIES (a paper can have multiple):
----------------------------------------------------------------------
  DEEP_CNN_RNN                    117 papers ( 16.1%)
  TRANSFORMER                      67 papers (  9.2%)
  LLM_RAG_XAI                      21 papers (  2.9%)
  CLASSICAL_ML                     21 papers (  2.9%)
  RULE_BASED                       13 papers (  1.8%)

CHALLENGES ADDRESSED (a paper can address multiple):
----------------------------------------------------------------------
  MAPPING_INTEROP                 167 papers ( 22.9%)
  HIERARCHY                        50 papers (  6.9%)
  KNOWLEDGE_AUG                    38 papers (  5.2%)
  EXTREME_MULTILABEL               30 papers (  4.1%)
  LONG_TEXT                        29 papers (  4.0%)
  RARE_LABELS                      17 papers (  2.3%)
  COOCCURRENCE_RULES                2 papers (  0.3%)
  EXPLAINABILITY                    1 papers (  0.1%)

DATASETS USED:
----------------------------------------------------------------------
  MIMIC                            24 papers (  3.3%)

TIME PERIODS:
----------------------------------------------------------------------
  pre2012                          38 papers (  5.2%)
  2012_2016                        41 papers (  5.6%)
  2017_2019                        96 papers ( 13.2%)
  2020_2022                       236 papers ( 32.4%)
  2023_plus                       317 papers ( 43.5%)

CONTENT FLAGS:
----------------------------------------------------------------------
  Has evaluation metrics:      94 papers ( 12.9%)
  Has novelty language:        77 papers ( 10.6%)
  Explicit coding task:       100 papers ( 13.7%)
```

### Key Insights

**Method Evolution:**
- Deep CNN/RNN methods dominate (16.1% of papers)
- Transformer models growing rapidly (9.2%)
- Emerging LLM/RAG approaches (2.9%)

**Research Focus:**
- Mapping/interoperability is the top challenge (22.9%)
- Hierarchical classification is second (6.9%)
- Knowledge augmentation gaining traction (5.2%)

**Time Trends:**
- **76% of papers from 2020 onwards**
- Recent explosion: 43.5% from 2023+
- Field is rapidly evolving

**Dataset Diversity:**
- Low MIMIC concentration (3.3%) suggests diverse data sources
- Many papers use proprietary/institutional datasets

### Output Files

**Tagged RIS Files:**
Tags are embedded as `N1` (notes) fields in RIS format:
```
N1  - [AUTO_TAGS] PERIOD: 2023_plus | METHODS: TRANSFORMER, DEEP_CNN_RNN | CHALLENGES: HIERARCHY, EXTREME_MULTILABEL | DATASETS: MIMIC | FLAGS: HAS_METRICS, NOVEL, CODING_TASK
```

**Analysis CSV:**
Tabular format (`paper_tags_analysis.csv`) with columns:
- file, title, doi, year, year_bucket
- phases (method families)
- challenges (challenges addressed)
- datasets (datasets used)
- has_metrics, has_novelty, has_coding_task (boolean flags)

Perfect for:
- Pivot tables and statistical analysis
- Trend visualization
- Gap analysis (underexplored methods/challenges)
- Literature review categorization

## Selecting Representative Papers

After tagging all papers, Step 9 selects a curated set of representative papers from each bucket (method × challenge combination) using intelligent scoring heuristics.

### Selection Script

**Step9_select_representatives.py** - Representative paper selector with scoring

This script:
- Uses priority-based method tagging (LLM > Transformer > Deep > Classical > Rule-based)
- Tags multiple challenges per paper
- Scores papers by quality indicators (metrics, novelty, coding task, length)
- Buckets papers by method family × challenge
- Selects top N papers per bucket (configurable)
- Outputs CSV and RIS files with representative papers

### Scoring Heuristic

Papers are scored to identify the best representatives:

**Score Components:**
- **+3 points**: Has evaluation metrics (F1, precision, recall, accuracy, AUC, etc.)
- **+2 points**: Has novelty language ("we propose", "novel", "new framework")
- **+2 points**: Explicit coding task terminology
- **+1 point**: Substantial abstract (> 600 characters)

**Selection Process:**
1. Papers are bucketed by (method family, primary challenge)
2. Within each bucket, sort by: score (desc) → year (desc) → title length (desc)
3. Select top 3 papers per bucket
4. Optional total cap can be applied

### Configuration

Edit the script to modify selection parameters:

```python
TOP_N_PER_BUCKET = 3      # Papers per bucket
TOTAL_CAP = None          # Optional cap on total papers
BUCKET_MODE = "phase_x_challenge"  # Options: phase_only, phase_x_dataset, phase_x_challenge
WRITE_SELECTED_RIS = True  # Export to RIS format
```

### Usage

Select representatives from tagged papers:
```bash
python Step9_select_representatives.py tagged_output/ representatives/
```

Use default output directory:
```bash
python Step9_select_representatives.py tagged_output/
```

### Example Results

Selecting from 728 tagged papers produces focused representatives:

```
OVERALL STATISTICS:
  Total records loaded:      728
  Tagged with scores:        230 papers
  Buckets created:           24
  Representatives selected:  62 papers

REPRESENTATIVES BY METHOD FAMILY:
----------------------------------------------------------------------
  UNSPECIFIED                      15 papers
  DEEP_CNN_RNN                     14 papers
  TRANSFORMER                      13 papers
  LLM_RAG_XAI                       8 papers
  RULE_BASED                        6 papers
  CLASSICAL_ML                      6 papers

REPRESENTATIVES BY CHALLENGE/DIMENSION:
----------------------------------------------------------------------
  MAPPING_INTEROP                  18 papers
  GENERAL                          15 papers
  HIERARCHY                        12 papers
  RARE_LABELS                       7 papers
  EXTREME_MULTILABEL                5 papers
  KNOWLEDGE_AUG                     3 papers
  LONG_TEXT                         1 papers
  COOCCURRENCE_RULES                1 papers

REPRESENTATIVES BY TIME PERIOD:
----------------------------------------------------------------------
  pre2012                           2 papers
  2012_2016                         4 papers
  2017_2019                         9 papers
  2020_2022                        17 papers
  2023_plus                        30 papers (48.4%)
```

### Output Files

**1. tagged_papers.csv**
- All papers that scored > 0
- Includes: title, DOI, year, method, challenges, datasets, scores
- Useful for understanding what was evaluated

**2. selected_representatives.csv**
- Representative papers only (62 papers)
- Additional columns: bucket_phase, bucket_dim, bucket
- Perfect for literature review table creation

**3. selected_representatives.ris**
- Representative papers in RIS format
- Ready for import into reference management software
- Can be used as core citation set for the review

### Use Cases

**Literature Review:**
- Create a representative sample across all method × challenge combinations
- Ensure balanced coverage of the field
- Identify exemplary papers for each approach

**Gap Analysis:**
- Identify under-explored method × challenge combinations
- Buckets with fewer papers indicate research opportunities
- Guide future research directions

**Systematic Review:**
- Focus deep reading on high-quality representative papers
- Use as seed set for snowball sampling
- Extract key insights from each methodological approach

### Key Insights from Selection

**Method Distribution:**
- Deep learning methods dominate representatives (14 papers)
- Transformer models well-represented (13 papers)
- Emerging LLM approaches gaining traction (8 papers)

**Challenge Focus:**
- Mapping/interoperability most common (18 papers)
- Hierarchical classification well-studied (12 papers)
- Rare labels receiving attention (7 papers)

**Temporal Distribution:**
- **77.4% from 2020 onwards** (47 / 62 papers)
- Recent explosion in 2023+ (30 papers)
- Field rapidly evolving with modern methods

## Complete Pipeline Summary

The complete literature review pipeline consists of 9 steps:

1. **Step 1**: Fetch data from PubMed, Scopus, and ACM Digital Library
   - Use `Step1_pubmed_fetcher.py` and `Step1_fetchallscopusresults.py`
   - Result: Raw data in JSON, CSV, and ENW formats

2. **Step 2**: Convert all data to RIS format
   - Use `Step2_convert_all_to_ris.py`
   - Result: 51,774 records in RIS format

3. **Step 3**: Merge and deduplicate by key phrase
   - Use `Step3_merge_ris_by_keyphrase.py`
   - Result: 49,767 unique records (3.9% duplicates removed)

4. **Step 4**: Filter by target journals
   - Use `Step4_filter_by_journal.py`
   - Result: 2,324 high-quality papers from 11 top journals (4.7% retention)

5. **Step 5**: Filter by article type
   - Use `Step5_filter_by_type.py`
   - Result: 2,321 journal articles and conference papers (99.9% retention)

6. **Step 6**: Filter by content analysis
   - Use `Step6_filter_by_content.py`
   - Result: 942 papers where ICD coding is the primary task (40.6% retention)

7. **Step 7**: Filter by methodology
   - Use `Step7_filter_by_methodology.py`
   - Result: 728 methodological/technical papers (77.3% retention, 22.7% removed)

8. **Step 8**: Tag papers by method, challenge, and dataset
   - Use `Step8_tag_papers.py`
   - Result: 728 tagged papers with comprehensive metadata
   - Output: Tagged RIS files + analysis CSV

9. **Step 9**: Select representative papers from each bucket
   - Use `Step9_select_representatives.py`
   - Result: 62 representative papers (top 3 per method × challenge bucket)
   - Output: Selected representatives CSV + RIS file

**Final Result**: From 51,774 initial records to 728 highly refined papers, with 62 carefully selected representatives covering all method × challenge combinations!

### Pipeline Statistics

| Step | Records | Change | Description |
|------|---------|--------|-------------|
| 1-2 | 51,774 | - | Fetch & convert to RIS |
| 3 | 49,767 | -3.9% | Merge & deduplicate |
| 4 | 2,324 | -95.3% | Filter by journals |
| 5 | 2,321 | -0.1% | Filter by type |
| 6 | 942 | -59.4% | Filter by content |
| 7 | 728 | -22.7% | Filter by methodology |
| 8 | 728 | tagged | Tag by method/challenge/dataset |
| 9 | 62 | selected | Select representatives (top 3 per bucket) |

**Final retention: 1.4% of original records (728 / 51,774)**
**Representative sample: 0.12% of original records (62 / 51,774)**

### Tagged Paper Distribution

**By Method (728 papers, papers can have multiple methods):**
- Deep CNN/RNN: 117 papers (16.1%)
- Transformer: 67 papers (9.2%)
- LLM/RAG/XAI: 21 papers (2.9%)
- Classical ML: 21 papers (2.9%)
- Rule-based: 13 papers (1.8%)

**By Time Period:**
- 2023+: 317 papers (43.5%)
- 2020-2022: 236 papers (32.4%)
- 2017-2019: 96 papers (13.2%)
- 2012-2016: 41 papers (5.6%)
- pre-2012: 38 papers (5.2%)

**Top Challenges:**
- Mapping/Interoperability: 167 papers (22.9%)
- Hierarchy: 50 papers (6.9%)
- Knowledge Augmentation: 38 papers (5.2%)

## Sample Data

This repository includes a sample dataset (`output_data.tar.gz`) containing pre-fetched literature review results on automated ICD coding. The archive includes:

- Multiple search queries (automated ICD coding, clinical coding, computer-assisted coding, etc.)
- Data from both PubMed and Scopus/ScienceDirect sources
- Both JSON and CSV formats for each query
- Approximately 14MB compressed data

### Extracting Sample Data

To extract and explore the sample data:

```bash
tar -xzf output_data.tar.gz
```

This has an `output/` directory with subdirectories:
- `output/pubmed_output/` - PubMed search results
- `output/Scopus/` - ScienceDirect/Scopus search results
- `output/acm_output/` - ACM Digital Library results (if available)

## Installation

### Prerequisites

- Python 3.7 or higher
- pip package manager

### Setup

1. Clone this repository:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Install required packages:
```bash
pip install requests
```

3. Create your configuration file:
```bash
cp template_config.ini config.ini
```

4. Edit `config.ini` with your credentials and search parameters

## Configuration

### Setting up config.ini

The `config.ini` file contains your API credentials and search parameters. **Never commit this file to git** - use `template_config.ini` as a reference.

```ini
[ScienceDirect]
api_key = YOUR_API_KEY_HERE
base_url = https://api.elsevier.com

[OAuth]
client_id = YOUR_CLIENT_ID
client_secret = YOUR_CLIENT_SECRET

[Search]
query = automatic international classification of diseases coding
max_results = 0  # 0 = fetch all available results

[PubMed]
api_key = YOUR_API_KEY_HERE
email = your.email@example.com  # Required by NCBI

[Output]
output_dir = ./output
```

### Getting API Keys

#### PubMed (NCBI E-utilities)
1. Create an NCBI account at https://www.ncbi.nlm.nih.gov/account/
2. Navigate to Settings > API Key Management
3. Create a new API key
4. Copy the key to `config.ini` under `[PubMed]`

**Note**: API key is optional for PubMed but recommended for higher rate limits (10 req/sec vs 3 req/sec)

#### ScienceDirect/Scopus (Elsevier)
1. Register at https://dev.elsevier.com/
2. Create an application
3. Choose authentication method:
   - **API Key** (simpler): Copy key to `[ScienceDirect]` section
   - **OAuth2** (alternative): Copy client_id and client_secret to `[OAuth]` section

## Usage

### 1. Fetching from PubMed

```bash
python Step1_pubmed_fetcher.py
```

This script:
- Searches PubMed using your query
- Fetches all available articles (or up to max_results)
- Extracts metadata including PMID, DOI, abstract, MeSH terms, etc.
- Saves results to JSON and CSV in the output directory

**Features**:
- No hard API limits (can fetch 100,000+ results)
- Rich metadata with MeSH terms and keywords
- Structured abstract parsing
- Publication type classification

### 2. Fetching from ScienceDirect/Scopus

```bash
python Step1_fetchallscopusresults.py
```

This script:
- Prompts for year range (default: 2000 to current year)
- Splits query by year to bypass the 5000 result limit
- Fetches all articles year by year
- Deduplicates results by DOI
- Saves combined results to JSON and CSV

**Why year-based splitting?**
The Scopus API has a hard limit of 5000 results per query. By splitting the query by publication year, you can fetch all available results.

**Example workflow**:
```
Enter start year (default 2000): 2015
Enter end year (default 2025): 2024

YEAR: 2015
✓ Year 2015: 234 articles fetched

YEAR: 2016
✓ Year 2016: 287 articles fetched

...

Total unique articles: 2,543
Duplicates removed: 12
```

### 3. Direct ScienceDirect Fetching (Single Query)

If you know your query returns fewer than 5000 results, you can use the helper directly:

```bash
python Helper_sciencedirect_fetcher_v2.py
```

### 4. ACM Digital Library Fetching
ACM Digital Library does not have an API. The key terms were searched and the results were downloaded in EndNote format. The filter was set beetn 2005 to 2026. There is a limit of 1000 for the number of records that can be downloaded in one attempt. So for search results>1000, the exporting was done in parts. The first 1000 in one download and the rest in the next. 

## Output Format

### CSV Output
Comma-separated values with columns:
- PubMed: `pmid`, `title`, `abstract`, `authors`, `journal`, `publication_date`, `doi`, `mesh_terms`, `keywords`, etc.
- Scopus: `title`, `authors`, `publication_name`, `cover_date`, `doi`, `scopus_id`, `abstract`, `cited_by_count`, etc.

### JSON Output
Structured JSON array with article objects containing the same fields as CSV.

## Handling Large Result Sets

### Problem: 5000 Result Limit
Scopus API returns a maximum of 5000 results per query, even if more exist.

### Solution: Year-Based Splitting
Use `Step1_fetchallscopusresults.py` which:
1. Splits your query by publication year
2. Fetches results for each year separately
3. Combines and deduplicates all results

### Example
If your query "ICD coding" returns 15,000 total results:
- Traditional query: Gets only 5,000 results (missing 10,000)
- Year-based query: Gets all 15,000 results across multiple years

## Deduplication

Articles are deduplicated based on DOI (Digital Object Identifier):
- Articles with the same DOI are considered duplicates
- Only the first occurrence is kept
- Articles without DOI are all retained

## Rate Limiting

Scripts automatically respect API rate limits:
- **PubMed**: 3 requests/sec (without key) or 10 requests/sec (with key)
- **ScienceDirect/Scopus**: Built-in delays and 429 status code handling

## Troubleshooting

### "Error: config.ini not found"
Run: `cp template_config.ini config.ini` and add your credentials

### "Error: Please add either an API key or OAuth credentials"
Edit `config.ini` and replace placeholder values with actual credentials

### "Rate limit hit. Waiting 60 seconds..."
The script automatically handles rate limiting. Just wait for it to continue.

### "API LIMIT REACHED: 5000 results"
Use `Step1_fetchallscopusresults.py` with year-based splitting to get all results

### Authentication errors
- Verify your API keys are correct
- Check if your API key has the necessary permissions
- Ensure your institutional access is active (for ScienceDirect)

## Search Query Options
- automated ICD coding
- automatic international classification of diseases coding
- computer-assisted ICD coding
- clinical coding ICD

## Best Practices

1. **Start with a small max_results** to test your query before fetching everything
2. **Use specific search terms** to reduce irrelevant results
3. **Check result counts** before fetching to estimate time
4. **Review the first few results** to ensure query relevance
5. **Keep your config.ini secure** - never commit it to version control
6. **Use year-based splitting** for queries with >5000 results

## Data Fields

### PubMed Fields
- `pmid`: PubMed unique identifier
- `title`: Article title
- `abstract`: Full abstract text
- `authors`: Comma-separated author list
- `journal`: Journal name
- `issn`: Journal ISSN
- `publication_date`: Publication date
- `doi`: Digital Object Identifier
- `pmc_id`: PubMed Central ID
- `pubmed_url`: Direct link to PubMed
- `publication_types`: Article type classifications
- `mesh_terms`: Medical Subject Headings
- `keywords`: Author keywords

### ScienceDirect/Scopus Fields
- `title`: Article title
- `authors`: Author names
- `publication_name`: Journal/conference name
- `cover_date`: Publication date
- `doi`: Digital Object Identifier
- `scopus_id`: Scopus unique identifier
- `pii`: Publisher Item Identifier
- `link`: Direct link to article
- `abstract`: Abstract text
- `article_type`: Document type
- `issn`: Publication ISSN
- `volume`: Volume number
- `page_range`: Page numbers
- `cited_by_count`: Citation count

## License

This project is intended for academic research purposes. Please respect the terms of service of each API provider:
- PubMed: https://www.ncbi.nlm.nih.gov/home/about/policies/
- Elsevier: https://dev.elsevier.com/policy.html

## Citation

If you use this tool in your research, please cite your data sources appropriately and follow the citation requirements of each database.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review API provider documentation
3. Open an issue in this repository

## Acknowledgments

This project uses:
- NCBI E-utilities API for PubMed access
- Elsevier ScienceDirect/Scopus Search API
- Python requests library for HTTP operations


