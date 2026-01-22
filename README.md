# Literature Review Data Fetcher for Automated ICD Coding - PART A

A comprehensive toolkit for collecting and organising academic literature on automated International Classification of Diseases (ICD) coding from multiple sources including PubMed, ACM Digital Library and Scopus. This is content material for an upcoming publication. This is a placeholder for future work.

## Overview

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
├── template_config.ini                 # Configuration template
├── config.ini                          # Your actual config (not in git)
├── output/                             # ScienceDirect/Scopus results
├── pubmed_output/                      # PubMed results
└── acm_output/                         # ACM Digital Library results
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

### Year Filters
In `config.ini`, modify your query:
```ini
query = automatic ICD coding AND PUBYEAR > 2005
```

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


