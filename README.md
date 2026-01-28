# Literature Review Data Fetcher for Automated ICD Coding

A comprehensive toolkit for collecting and organising academic literature on automated International Classification of Diseases (ICD) coding from multiple sources including PubMed, ACM Digital Library and Scopus. This is content material for an upcoming publication. This is a placeholder for future work.

## Fetch Papers from different sources - PART A

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

## Global Merging and Deduplication - PART B

After converting all sources to RIS format, the next step is to perform **global deduplication** across all data sources (ACM, PubMed, Scopus) and all keyphrases. This approach differs from the previous keyphrase-based merging by:

1. **Merging everything at once** - All RIS files from all sources and keyphrases are merged into a single dataset
2. **Global deduplication** - Removes duplicates based on DOI across the entire dataset
3. **Comprehensive statistics** - Provides detailed analysis of duplicates by source and keyphrase

### Data Files

Three compressed archives contain the raw RIS files from each source:
- `acm_output.tar.gz` - ACM Digital Library results (6,112 records)
- `pubmed_output.tar.gz` - PubMed search results (36,333 records)
- `scopus_output.tar.gz` - Scopus search results (124,823 records)

**Extract the data:**
```bash
tar -xzf acm_output.tar.gz
tar -xzf pubmed_output.tar.gz
tar -xzf scopus_output.tar.gz
```

### Search Keyphrases Used

The following keyphrases were used to search for ICD coding papers:
- `automated ICD coding`
- `automatic international classification of diseases coding`
- `computer-assisted ICD coding`
- `clinical coding ICD`
- `icd coding`
- `icd classification`

### Deduplication Scripts

Three scripts handle the global deduplication pipeline:

#### Step 3: Merge and Deduplicate
**Step3_merge_and_deduplicate.py** - Main deduplication script

This script:
- Reads all RIS files from the three source folders
- Merges them into a single dataset
- Deduplicates based on DOI (normalized, case-insensitive)
- Tracks metadata (source, keyphrase, duplicate sources)
- Generates comprehensive statistics

**Usage:**
```bash
python Step3_merge_and_deduplicate.py
```

**Output:**
- `merged_deduplicated_papers.ris` - All unique papers in RIS format
- `deduplication_statistics.txt` - Summary statistics

#### Step 4: Export to CSV
**Step4_export_to_csv.py** - Converts RIS to CSV format

This script:
- Converts the merged RIS file to CSV format
- Includes all metadata fields (title, DOI, authors, abstract, keywords, etc.)
- Easy to open in Excel or Google Sheets for analysis

**Usage:**
```bash
python Step4_export_to_csv.py
```

**Output:**
- `merged_deduplicated_papers.csv` - All unique papers in CSV format

#### Step 5: Analyze Duplicates
**Step5_analyze_duplicates.py** - Detailed duplicate analysis (optional)

This script:
- Analyzes which papers appear in multiple sources
- Shows which papers appear under multiple keyphrases
- Provides detailed overlap statistics
- Useful for understanding data source coverage

**Usage:**
```bash
python Step5_analyze_duplicates.py
```

**Output:**
- `duplicate_analysis_report.txt` - Detailed duplicate analysis

### Running the Complete Pipeline

Use the master script to run all three steps in sequence:

```bash
python run_deduplication_pipeline.py
```

This will execute:
1. Step 5: Analyze duplicates (shows overlap before merging)
2. Step 3: Merge and deduplicate (creates unified dataset)
3. Step 4: Export to CSV (creates spreadsheet format)

### Example Results

Running the deduplication pipeline produces:

```
OVERALL STATISTICS:
  Total records collected:        167,268
  Unique DOIs:                     93,815
  Records without DOI:             12,105
  DOIs with duplicates:            38,269
  Total duplicate records:         61,348
  Deduplication rate:              36.68%

SOURCE OVERLAP ANALYSIS:
  scopus                           24,216 papers
  pubmed & scopus                   9,571 papers
  pubmed                            3,451 papers
  acm                                 885 papers
  acm & scopus                        141 papers
  acm & pubmed & scopus                 4 papers
  acm & pubmed                          1 papers

DEDUPLICATION STATISTICS:
  Total files processed: 19

  Records per source:
    acm            :  6,112 records
    pubmed         : 36,333 records
    scopus         :124,823 records

  Records per keyphrase:
    icd_classification                  : 62,937 records
    icd_coding                          : 51,137 records
    clinical_coding_ICD                 : 31,815 records
    automatic_intl_class_of_diseases    : 13,948 records
    automated_ICD_coding                :  3,888 records
    computer_assisted_ICD_coding        :  1,660 records

  ------------------------------------------------------------
  Total records before deduplication: 167,268
    - Records with DOI:                155,163
    - Records without DOI:              12,105

  Duplicates removed:                   61,348
  Total records after deduplication:   105,920

  Deduplication rate: 36.68%
```

**Generated files:**
- `merged_deduplicated_papers.ris` - 105,920 unique papers (98MB)
- `merged_deduplicated_papers.csv` - 105,920 unique papers (85MB)
- `deduplication_statistics.txt` - Summary statistics
- `duplicate_analysis_report.txt` - Detailed overlap analysis

### Deduplication Logic

**Primary method:** Papers are deduplicated based on DOI (Digital Object Identifier)

**DOI normalization:**
- Convert to lowercase
- Remove URL prefixes (`http://doi.org/`, `https://dx.doi.org/`)
- Remove `doi:` prefix
- Trim whitespace

**Handling records without DOI:**
- Papers without DOI are all retained (not deduplicated)
- 12,105 records (7.2%) have no DOI

**Duplicate tracking:**
- First occurrence is kept
- Source and keyphrase metadata is preserved
- Duplicate sources are tracked for analysis

### Key Insights

**Significant overlap across sources:**
- 36.68% of all records are duplicates
- PubMed & Scopus have highest overlap (9,571 papers)
- Some papers appear in all three sources

**Keyphrase redundancy:**
- Many papers match multiple keyphrases
- `icd_coding` and `clinical_coding_ICD` have most overlap (18,279 papers)
- Broad terms like `icd_classification` capture most papers (62,937)

**Why global deduplication?**
- Previous approach: Deduplicate within each keyphrase separately
- New approach: Deduplicate globally across all keyphrases and sources
- Result: Single unified dataset ready for filtering

### Next Steps

After global deduplication, the unified dataset (105,920 papers) is ready for further analysis and filtering based on your research needs:
- Filter by target journals (quality filter)
- Filter by article type (remove books/chapters)
- Content analysis (identify papers where ICD coding is the primary task)
- Methodology filtering (focus on technical/methods papers)
- Manual review and selection


## Project Structure (Updated)

```
.
├── Step1_fetchallscopusresults.py      # Fetch ScienceDirect/Scopus results by year
├── Step1_pubmed_fetcher.py             # Fetch PubMed results
├── Helper_sciencedirect_fetcher_v2.py  # Helper class for ScienceDirect API
├── convert_pubmed_to_ris.py            # PubMed JSON to RIS converter
├── convert_scopus_to_ris.py            # Scopus JSON to RIS converter
├── convert_enw_to_ris.py               # ACM EndNote to RIS converter
├── Step2_convert_all_to_ris.py         # Master converter for all formats
├── Step3_merge_and_deduplicate.py      # Global merge and deduplication
├── Step4_export_to_csv.py              # Export merged data to CSV
├── Step5_analyze_duplicates.py         # Detailed duplicate analysis
├── run_deduplication_pipeline.py       # Run Steps 3-5 in sequence
├── template_config.ini                 # Configuration template
├── acm_output.tar.gz                   # ACM source data (6,112 records)
├── pubmed_output.tar.gz                # PubMed source data (36,333 records)
├── scopus_output.tar.gz                # Scopus source data (124,823 records)
└── output_data_complete.tar.gz         # Legacy output archive
```

## Complete Pipeline Summary

The complete literature review pipeline consists of 5 main steps:

### Step 1: Fetch Data from Sources
- Use `Step1_pubmed_fetcher.py` for PubMed
- Use `Step1_fetchallscopusresults.py` for Scopus
- Manually download from ACM Digital Library (no API)
- Result: Raw data in JSON, CSV, and ENW formats

### Step 2: Convert to RIS Format  
- Use `Step2_convert_all_to_ris.py`
- Converts all formats to standardized RIS
- Result: 167,268 records in RIS format across 19 files

### Step 3: Global Merge and Deduplicate
- Use `Step3_merge_and_deduplicate.py`
- Merges all sources and keyphrases
- Deduplicates based on DOI (normalized)
- Result: 105,920 unique papers (36.68% deduplication rate)
- Output: `merged_deduplicated_papers.ris`

### Step 4: Export to CSV
- Use `Step4_export_to_csv.py`
- Converts RIS to spreadsheet format
- Result: 105,920 papers in CSV format
- Output: `merged_deduplicated_papers.csv`

### Step 5: Analyze Duplicates (Optional)
- Use `Step5_analyze_duplicates.py`
- Detailed analysis of overlap across sources
- Shows which papers appear in multiple databases
- Output: `duplicate_analysis_report.txt`

### Running the Complete Deduplication Pipeline

```bash
# Extract the data archives
tar -xzf acm_output.tar.gz
tar -xzf pubmed_output.tar.gz
tar -xzf scopus_output.tar.gz

# Run the complete pipeline
python run_deduplication_pipeline.py
```

## Pipeline Statistics

| Step | Records | Change | Description |
|------|---------|--------|-------------|
| 1-2 | 167,268 | - | Fetch & convert to RIS |
| 3 | 105,920 | -36.7% | Global merge & deduplicate |
| 4 | 105,920 | - | Export to CSV format |
| 5 | - | - | Analyze duplicates (optional) |

**Final result: 105,920 unique papers from 167,268 total records**

**Source breakdown:**
- ACM Digital Library: 6,112 records (3.7%)
- PubMed: 36,333 records (21.7%)
- Scopus: 124,823 records (74.6%)

**Keyphrase breakdown:**
- icd_classification: 62,937 records (37.6%)
- icd_coding: 51,137 records (30.6%)
- clinical_coding_ICD: 31,815 records (19.0%)
- automatic_international_classification_of_diseases: 13,948 records (8.3%)
- Other keyphrases: 7,431 records (4.5%)

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
