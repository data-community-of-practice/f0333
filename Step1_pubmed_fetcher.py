#!/usr/bin/env python3
"""
PubMed API Data Fetcher
Fetches search results using NCBI's E-utilities API
No API key required, but recommended for higher rate limits
"""

import requests
import json
import time
from typing import List, Dict, Any, Optional
import os
import configparser
import xml.etree.ElementTree as ET
from datetime import datetime


class PubMedFetcher:
    def __init__(self, api_key: str = None, email: str = None):
        """
        Initialize the fetcher with optional API credentials
        
        Args:
            api_key: Your NCBI API key (optional but recommended)
            email: Your email (required by NCBI)
        """
        self.api_key = api_key
        self.email = email
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        
        # Rate limiting: 3 requests/sec without key, 10 requests/sec with key
        self.rate_limit = 0.34 if api_key else 0.34  # seconds between requests
        
    def search_pubmed(self, query: str, max_results: int = 0, retmax: int = 500) -> List[str]:
        """
        Search PubMed and get list of PMIDs
        
        Args:
            query: Search query string
            max_results: Maximum number of results (0 = all available)
            retmax: Number of IDs to fetch per request (max 10000)
            
        Returns:
            List of PubMed IDs (PMIDs)
        """
        all_pmids = []
        retstart = 0
        retmax = min(retmax, 10000)  # API maximum per request
        
        print(f"Searching PubMed for: {query}")
        if max_results == 0:
            print("Max results: All available")
        else:
            print(f"Max results: {max_results}")
        
        while True:
            # Build search URL
            search_url = f"{self.base_url}/esearch.fcgi"
            params = {
                'db': 'pubmed',
                'term': query,
                'retstart': retstart,
                'retmax': retmax,
                'retmode': 'json',
                'sort': 'relevance'
            }
            
            if self.email:
                params['email'] = self.email
            if self.api_key:
                params['api_key'] = self.api_key
            
            try:
                print(f"Fetching PMIDs {retstart} to {retstart + retmax}...")
                response = requests.get(search_url, params=params)
                response.raise_for_status()
                
                data = response.json()
                esearchresult = data.get('esearchresult', {})
                
                # Get total count
                total_count = int(esearchresult.get('count', 0))
                if retstart == 0:
                    print(f"Total results available: {total_count}")
                
                # Get PMIDs from this batch
                pmids = esearchresult.get('idlist', [])
                
                if not pmids:
                    print("No more results.")
                    break
                
                all_pmids.extend(pmids)
                print(f"Retrieved {len(pmids)} PMIDs. Total so far: {len(all_pmids)}")
                
                # Check if we should continue
                if max_results > 0 and len(all_pmids) >= max_results:
                    all_pmids = all_pmids[:max_results]
                    break
                
                if len(all_pmids) >= total_count:
                    break
                
                # Move to next batch
                retstart += retmax
                
                # Rate limiting
                time.sleep(self.rate_limit)
                
            except Exception as e:
                print(f"Error searching PubMed: {e}")
                break
        
        print(f"\nTotal PMIDs retrieved: {len(all_pmids)}")
        return all_pmids
    
    def fetch_details(self, pmids: List[str], batch_size: int = 200) -> List[Dict[str, Any]]:
        """
        Fetch detailed information for list of PMIDs
        
        Args:
            pmids: List of PubMed IDs
            batch_size: Number of articles to fetch per request (max 500)
            
        Returns:
            List of article details
        """
        all_articles = []
        total = len(pmids)
        
        print(f"\nFetching details for {total} articles...")
        
        # Process in batches
        for i in range(0, total, batch_size):
            batch = pmids[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size
            
            print(f"Fetching batch {batch_num}/{total_batches} ({len(batch)} articles)...")
            
            # Build fetch URL
            fetch_url = f"{self.base_url}/efetch.fcgi"
            params = {
                'db': 'pubmed',
                'id': ','.join(batch),
                'retmode': 'xml'
            }
            
            if self.email:
                params['email'] = self.email
            if self.api_key:
                params['api_key'] = self.api_key
            
            try:
                response = requests.get(fetch_url, params=params)
                response.raise_for_status()
                
                # Parse XML response
                root = ET.fromstring(response.content)
                articles = self._parse_pubmed_xml(root)
                all_articles.extend(articles)
                
                print(f"Parsed {len(articles)} articles. Total: {len(all_articles)}")
                
                # Rate limiting
                time.sleep(self.rate_limit)
                
            except Exception as e:
                print(f"Error fetching batch: {e}")
                continue
        
        print(f"\nTotal articles with details: {len(all_articles)}")
        return all_articles
    
    def _parse_pubmed_xml(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Parse PubMed XML and extract article information"""
        articles = []
        
        for article_elem in root.findall('.//PubmedArticle'):
            try:
                article = {}
                
                # Get MedlineCitation
                medline = article_elem.find('MedlineCitation')
                if medline is None:
                    continue
                
                # PMID
                pmid_elem = medline.find('PMID')
                article['pmid'] = pmid_elem.text if pmid_elem is not None else 'N/A'
                
                # Article element
                article_node = medline.find('Article')
                if article_node is None:
                    continue
                
                # Title
                title_elem = article_node.find('.//ArticleTitle')
                article['title'] = title_elem.text if title_elem is not None else 'N/A'
                
                # Abstract
                abstract_texts = article_node.findall('.//AbstractText')
                if abstract_texts:
                    abstract_parts = []
                    for abs_text in abstract_texts:
                        label = abs_text.get('Label', '')
                        text = abs_text.text or ''
                        if label:
                            abstract_parts.append(f"{label}: {text}")
                        else:
                            abstract_parts.append(text)
                    article['abstract'] = ' '.join(abstract_parts)
                else:
                    article['abstract'] = 'N/A'
                
                # Authors
                authors = []
                author_list = article_node.find('AuthorList')
                if author_list is not None:
                    for author in author_list.findall('Author'):
                        last_name = author.find('LastName')
                        fore_name = author.find('ForeName')
                        if last_name is not None:
                            name = last_name.text
                            if fore_name is not None:
                                name = f"{fore_name.text} {name}"
                            authors.append(name)
                article['authors'] = ', '.join(authors) if authors else 'N/A'
                
                # Journal
                journal = article_node.find('.//Journal')
                if journal is not None:
                    journal_title = journal.find('Title')
                    article['journal'] = journal_title.text if journal_title is not None else 'N/A'
                    
                    # ISSN
                    issn = journal.find('ISSN')
                    article['issn'] = issn.text if issn is not None else 'N/A'
                else:
                    article['journal'] = 'N/A'
                    article['issn'] = 'N/A'
                
                # Publication Date
                pub_date = article_node.find('.//PubDate')
                if pub_date is not None:
                    year = pub_date.find('Year')
                    month = pub_date.find('Month')
                    day = pub_date.find('Day')
                    
                    date_parts = []
                    if year is not None:
                        date_parts.append(year.text)
                    if month is not None:
                        date_parts.append(month.text)
                    if day is not None:
                        date_parts.append(day.text)
                    
                    article['publication_date'] = '-'.join(date_parts) if date_parts else 'N/A'
                else:
                    article['publication_date'] = 'N/A'
                
                # DOI
                article_ids = article_elem.find('.//ArticleIdList')
                article['doi'] = 'N/A'
                article['pmc_id'] = 'N/A'
                
                if article_ids is not None:
                    for article_id in article_ids.findall('ArticleId'):
                        id_type = article_id.get('IdType', '')
                        if id_type == 'doi':
                            article['doi'] = article_id.text
                        elif id_type == 'pmc':
                            article['pmc_id'] = article_id.text
                
                # PubMed URL
                article['pubmed_url'] = f"https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/"
                
                # Publication Types
                pub_types = article_node.findall('.//PublicationType')
                article['publication_types'] = ', '.join([pt.text for pt in pub_types]) if pub_types else 'N/A'
                
                # MeSH Terms (Medical Subject Headings)
                mesh_headings = medline.findall('.//MeshHeading/DescriptorName')
                article['mesh_terms'] = ', '.join([mh.text for mh in mesh_headings]) if mesh_headings else 'N/A'
                
                # Keywords
                keywords = article_node.findall('.//Keyword')
                article['keywords'] = ', '.join([kw.text for kw in keywords if kw.text]) if keywords else 'N/A'
                
                articles.append(article)
                
            except Exception as e:
                print(f"Error parsing article: {e}")
                continue
        
        return articles
    
    def save_to_json(self, data: List[Dict[str, Any]], filename: str):
        """Save data to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved to: {filename}")
    
    def save_to_csv(self, data: List[Dict[str, Any]], filename: str):
        """Save data to CSV file"""
        import csv
        
        if not data:
            print("No data to save")
            return
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        print(f"✓ Saved to: {filename}")


def load_config(config_file: str = "config.ini") -> dict:
    """Load configuration from config file"""
    if not os.path.exists(config_file):
        print(f"Error: {config_file} not found!")
        print("\nCreating a template config file...")
        create_config_template(config_file)
        print(f"Please edit {config_file} and run the script again.")
        return None
    
    config = configparser.ConfigParser()
    config.read(config_file)
    
    try:
        api_key = config['PubMed'].get('api_key', '')
        email = config['PubMed'].get('email', '')
        query = config['Search']['query']
        max_results = config['Search'].getint('max_results', 0)
        output_dir = config.get('Output', 'output_dir', fallback='./output')
        
        if not email:
            print("Warning: Email is recommended by NCBI")
        
        if not query:
            print("Error: Please add a search query to config")
            return None
        
        return {
            'api_key': api_key if api_key else None,
            'email': email if email else None,
            'query': query,
            'max_results': max_results,
            'output_dir': output_dir
        }
    except KeyError as e:
        print(f"Error: config file is missing required section or key: {e}")
        return None


def create_config_template(config_file: str = "config.ini"):
    """Create a template config file"""
    config = configparser.ConfigParser()
    config['PubMed'] = {
        'api_key': '',
        'email': 'your.email@example.com'
    }
    config['Search'] = {
        'query': 'automatic international classification of diseases coding',
        'max_results': '0'
    }
    config['Output'] = {
        'output_dir': './output'
    }
    
    with open(config_file, 'w') as f:
        config.write(f)
    
    print(f"\nTemplate {config_file} created:")
    print("-" * 70)
    print("[PubMed]")
    print("api_key =  # Optional - get from https://www.ncbi.nlm.nih.gov/account/")
    print("email = your.email@example.com  # Required by NCBI")
    print()
    print("[Search]")
    print("query = automatic international classification of diseases coding")
    print("max_results = 0  # 0 = fetch all available")
    print()
    print("[Output]")
    print("output_dir = ./output")
    print("-" * 70)


def main():
    """Main execution function"""
    
    # Load configuration
    config = load_config("config.ini")
    if not config:
        return
    
    # Initialize fetcher
    fetcher = PubMedFetcher(
        api_key=config['api_key'],
        email=config['email']
    )
    
    query = config['query']
    max_results = config['max_results']
    output_dir = config['output_dir']
    
    print("=" * 70)
    print("PubMed Article Fetcher")
    print("=" * 70)
    print()
    
    # Step 1: Search and get PMIDs
    pmids = fetcher.search_pubmed(query, max_results=max_results)
    
    if not pmids:
        print("No results found.")
        return
    
    # Step 2: Fetch detailed information
    articles = fetcher.fetch_details(pmids)
    
    if not articles:
        print("No article details retrieved.")
        return
    
    # Step 3: Save results
    # Create safe filename from query
    safe_query = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in query)
    safe_query = safe_query.replace(' ', '_')[:50]
    
    os.makedirs(output_dir, exist_ok=True)
    
    json_file = f"{output_dir}/{safe_query}_pubmed.json"
    csv_file = f"{output_dir}/{safe_query}_pubmed.csv"
    
    fetcher.save_to_json(articles, json_file)
    fetcher.save_to_csv(articles, csv_file)
    
    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total articles fetched: {len(articles)}")
    print(f"Query: {query}")
    print(f"\nFiles created:")
    print(f"  - {json_file}")
    print(f"  - {csv_file}")
    
    # Show first 3 articles
    if articles:
        print("\nFirst 3 articles:")
        for i, article in enumerate(articles[:3], 1):
            print(f"\n{i}. {article['title']}")
            print(f"   Authors: {article['authors'][:100]}...")
            print(f"   Journal: {article['journal']}")
            print(f"   Date: {article['publication_date']}")
            print(f"   PMID: {article['pmid']}")
            print(f"   DOI: {article['doi']}")


if __name__ == "__main__":
    main()
