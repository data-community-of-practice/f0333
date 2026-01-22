#!/usr/bin/env python3
"""
ScienceDirect API Data Fetcher - Updated Version
Fetches search results using Elsevier's Scopus/ScienceDirect Search API
Supports both API Key and OAuth2 authentication
"""

import requests
import json
import time
from typing import List, Dict, Any, Optional
import os
import configparser


class ScienceDirectFetcher:
    def __init__(self, api_key: str = None, access_token: str = None, base_url: str = None):
        """
        Initialize the fetcher with API credentials
        
        Args:
            api_key: Your ScienceDirect API key (simpler method)
            access_token: OAuth2 access token (alternative method)
            base_url: Base URL for the API
        """
        self.api_key = api_key
        self.access_token = access_token
        self.base_url = base_url or "https://api.elsevier.com"
        
        # Set up headers based on authentication method
        if access_token:
            self.headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
        elif api_key:
            self.headers = {
                'X-ELS-APIKey': api_key,
                'Accept': 'application/json'
            }
        else:
            raise ValueError("Either api_key or access_token must be provided")
    
    def get_oauth_token(self, client_id: str, client_secret: str) -> Optional[str]:
        """
        Get OAuth2 access token using client credentials
        
        Args:
            client_id: Your client ID
            client_secret: Your client secret
            
        Returns:
            Access token string or None if failed
        """
        auth_url = "https://access.identity.elsevier.systems/realms/research-public/protocol/openid-connect/token"
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            response = requests.post(auth_url, data=data, headers=headers)
            response.raise_for_status()
            token_data = response.json()
            return token_data.get('access_token')
        except Exception as e:
            print(f"Error getting OAuth token: {e}")
            return None
        
    def search_articles(self, query: str, max_results: int = 0, results_per_page: int = 25, year_filter: str = None) -> List[Dict[str, Any]]:
        """
        Search for articles on ScienceDirect/Scopus
        
        Args:
            query: Search query string
            max_results: Maximum number of results to fetch (0 = fetch all available, up to API limit)
            results_per_page: Number of results per API call (max 25 for Scopus)
            year_filter: Optional year filter (e.g., "2020" or "2020-2023")
            
        Returns:
            List of article metadata dictionaries
        """
        all_results = []
        start = 0
        
        # Scopus API allows max 25 results per request by default
        count = min(results_per_page, 25)
        
        # Add year filter to query if provided
        if year_filter:
            query = f"{query} AND PUBYEAR IS {year_filter}"
        
        print(f"Fetching results for query: {query}")
        if max_results == 0:
            print(f"Max results: All available results (up to API limit of 5000)")
        else:
            print(f"Max results: {max_results}")
        print(f"Results per page: {count}\n")
        
        # Try different API endpoints
        endpoints_to_try = [
            f"{self.base_url}/content/search/scopus",
            f"{self.base_url}/content/search/sciencedirect"
        ]
        
        for endpoint_base in endpoints_to_try:
            print(f"Trying endpoint: {endpoint_base}")
            all_results = []
            start = 0
            api_limit_reached = False
            
            while True:
                # If max_results is set and we've reached it, stop
                if max_results > 0 and len(all_results) >= max_results:
                    break
                
                # Scopus API has a hard limit at 5000 results
                if len(all_results) >= 5000:
                    print("\n" + "="*70)
                    print("⚠️  API LIMIT REACHED: 5000 results")
                    print("="*70)
                    api_limit_reached = True
                    break
                    
                params = {
                    'query': query,
                    'start': start,
                    'count': count
                }
                
                try:
                    print(f"Fetching results {start} to {start + count}...")
                    response = requests.get(endpoint_base, headers=self.headers, params=params)
                    
                    # Check for rate limiting
                    if response.status_code == 429:
                        print("Rate limit hit. Waiting 60 seconds...")
                        time.sleep(60)
                        continue
                    
                    # Check for the 5000 result limit error
                    if response.status_code == 400:
                        error_data = response.json()
                        if 'service-error' in error_data:
                            error_msg = error_data['service-error']['status'].get('statusText', '')
                            if 'Exceeds the number of search results' in error_msg:
                                print("\n" + "="*70)
                                print("⚠️  API LIMIT REACHED: Maximum 5000 results per query")
                                print("="*70)
                                api_limit_reached = True
                                break
                        print(f"Error 400: {response.text[:500]}")
                        break
                    
                    # If we get 404, try next endpoint
                    if response.status_code == 404:
                        print(f"Endpoint not found (404). Trying next endpoint...")
                        break
                        
                    response.raise_for_status()
                    data = response.json()
                    
                    # Extract search results
                    search_results = data.get('search-results', {})
                    entries = search_results.get('entry', [])
                    
                    if not entries:
                        print("No more results found.")
                        break
                    
                    # Filter out error entries
                    valid_entries = [e for e in entries if 'error' not in e]
                    
                    if not valid_entries:
                        print("No valid results in this batch.")
                        break
                    
                    # Add results to our collection
                    all_results.extend(valid_entries)
                    print(f"Retrieved {len(valid_entries)} results. Total so far: {len(all_results)}")
                    
                    # Check if we've reached the end
                    total_results = int(search_results.get('opensearch:totalResults', 0))
                    print(f"Total available results: {total_results}")
                    
                    # If max_results is 0, fetch all available results (up to 5000 limit)
                    if max_results == 0:
                        if len(all_results) >= min(total_results, 5000):
                            break
                    else:
                        if len(all_results) >= min(total_results, max_results, 5000):
                            break
                    
                    # Move to next page
                    start += count
                    
                    # Be nice to the API - add a small delay
                    time.sleep(1)
                    
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching data: {e}")
                    if hasattr(e, 'response') and e.response is not None:
                        print(f"Status code: {e.response.status_code}")
                        print(f"Response content: {e.response.text[:500]}")
                    break
            
            # If we got results, break out of endpoint loop
            if all_results:
                print(f"\nSuccessfully fetched data from: {endpoint_base}")
                
                # Show warning if we hit the API limit
                if api_limit_reached and total_results > 5000:
                    print("\n" + "⚠️ "*35)
                    print(f"WARNING: Only retrieved 5000 out of {total_results} total results")
                    print(f"Missing: {total_results - 5000} results")
                    print("\nTo get all results, you can:")
                    print("1. Split your query by year (see README for instructions)")
                    print("2. Use more specific search terms")
                    print("3. Apply additional filters to reduce result count")
                    print("⚠️ "*35 + "\n")
                
                break
        
        # Trim to max_results if specified
        if max_results > 0:
            all_results = all_results[:max_results]
            
        print(f"\nTotal results fetched: {len(all_results)}")
        return all_results
    
    def extract_article_info(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract relevant information from raw API results
        
        Args:
            results: Raw API results
            
        Returns:
            List of cleaned article information
        """
        articles = []
        
        for entry in results:
            # Skip error entries
            if 'error' in entry:
                continue
                
            article = {
                'title': entry.get('dc:title', 'N/A'),
                'authors': entry.get('dc:creator', 'N/A'),
                'publication_name': entry.get('prism:publicationName', 'N/A'),
                'cover_date': entry.get('prism:coverDate', entry.get('prism:coverDisplayDate', 'N/A')),
                'doi': entry.get('prism:doi', entry.get('doi', 'N/A')),
                'scopus_id': entry.get('dc:identifier', entry.get('eid', 'N/A')),
                'pii': entry.get('pii', 'N/A'),
                'link': entry.get('link', [{}])[0].get('@href', 'N/A') if entry.get('link') else 'N/A',
                'abstract': entry.get('dc:description', 'N/A'),
                'article_type': entry.get('subtypeDescription', entry.get('subtype', 'N/A')),
                'issn': entry.get('prism:issn', 'N/A'),
                'volume': entry.get('prism:volume', 'N/A'),
                'page_range': entry.get('prism:pageRange', 'N/A'),
                'cited_by_count': entry.get('citedby-count', '0')
            }
            articles.append(article)
        
        return articles
    
    def save_to_json(self, data: List[Dict[str, Any]], filename: str):
        """Save data to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data saved to {filename}")
    
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
        print(f"Data saved to {filename}")


def load_config(config_file: str = "config.ini") -> dict:
    """
    Load configuration from config.ini file
    
    Args:
        config_file: Path to the config file
        
    Returns:
        Dictionary with configuration parameters
    """
    if not os.path.exists(config_file):
        print(f"Error: {config_file} not found!")
        print("\nCreating a template config.ini file...")
        create_config_template(config_file)
        print(f"Please edit {config_file} and add your credentials, then run the script again.")
        return None
    
    config = configparser.ConfigParser()
    config.read(config_file)
    
    try:
        # Try to get API key first
        api_key = config['ScienceDirect'].get('api_key', '')
        
        # Try to get OAuth credentials
        client_id = config.get('OAuth', 'client_id', fallback='')
        client_secret = config.get('OAuth', 'client_secret', fallback='')
        
        base_url = config['ScienceDirect'].get('base_url', 'https://api.elsevier.com')
        query = config['Search']['query']
        max_results = config['Search'].getint('max_results', 0)
        
        # Get output directory
        output_dir = config.get('Output', 'output_dir', fallback='./output')
        
        # Validate that we have at least one authentication method
        if api_key and api_key != "YOUR_API_KEY_HERE":
            auth_method = 'api_key'
        elif client_id and client_id != "YOUR_CLIENT_ID" and client_secret and client_secret != "YOUR_CLIENT_SECRET":
            auth_method = 'oauth'
        else:
            print("Error: Please add either an API key or OAuth credentials to config.ini")
            return None
        
        if not query:
            print("Error: Please add a search query to config.ini")
            return None
            
        return {
            'auth_method': auth_method,
            'api_key': api_key if auth_method == 'api_key' else None,
            'client_id': client_id if auth_method == 'oauth' else None,
            'client_secret': client_secret if auth_method == 'oauth' else None,
            'base_url': base_url,
            'query': query,
            'max_results': max_results,
            'output_dir': output_dir
        }
    except KeyError as e:
        print(f"Error: config.ini is missing required section or key: {e}")
        print("Please check the file format")
        return None


def create_config_template(config_file: str = "config.ini"):
    """Create a template config.ini file"""
    config = configparser.ConfigParser()
    config['ScienceDirect'] = {
        'api_key': 'YOUR_API_KEY_HERE',
        'base_url': 'https://api.elsevier.com'
    }
    config['OAuth'] = {
        'client_id': 'YOUR_CLIENT_ID',
        'client_secret': 'YOUR_CLIENT_SECRET'
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
    
    print(f"\nTemplate {config_file} created with the following content:")
    print("-" * 70)
    print("[ScienceDirect]")
    print("api_key = YOUR_API_KEY_HERE")
    print("base_url = https://api.elsevier.com")
    print()
    print("[OAuth]  # Alternative to API key")
    print("client_id = YOUR_CLIENT_ID")
    print("client_secret = YOUR_CLIENT_SECRET")
    print()
    print("[Search]")
    print("query = automatic international classification of diseases coding")
    print("max_results = 0  # Set to 0 to fetch all available results")
    print()
    print("[Output]")
    print("output_dir = ./output  # Directory where files will be saved")
    print("-" * 70)


def main():
    """Main execution function"""
    
    # Load configuration from config.ini
    config = load_config("config.ini")
    
    if not config:
        return
    
    # Initialize fetcher based on auth method
    if config['auth_method'] == 'oauth':
        print("Using OAuth2 authentication...")
        fetcher = ScienceDirectFetcher(base_url=config['base_url'])
        access_token = fetcher.get_oauth_token(config['client_id'], config['client_secret'])
        if not access_token:
            print("Failed to get OAuth token")
            return
        fetcher.access_token = access_token
        fetcher.headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        print("OAuth token obtained successfully\n")
    else:
        print("Using API Key authentication...\n")
        fetcher = ScienceDirectFetcher(api_key=config['api_key'], base_url=config['base_url'])
    
    # Get query and max_results from config
    query = config['query']
    max_results = config['max_results']
    output_dir = config['output_dir']
    
    # Fetch all results
    print("=" * 70)
    print("ScienceDirect Article Fetcher")
    print("=" * 70)
    
    raw_results = fetcher.search_articles(query, max_results=max_results)
    
    if not raw_results:
        print("No results found or error occurred.")
        return
    
    # Extract and clean the data
    print("\nProcessing article information...")
    articles = fetcher.extract_article_info(raw_results)
    
    # Create safe filename from query (remove special characters)
    safe_query = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in query)
    safe_query = safe_query.replace(' ', '_')[:50]  # Limit length
    
    # Save to files
    os.makedirs(output_dir, exist_ok=True)
    
    json_file = f"{output_dir}/{safe_query}_articles.json"
    csv_file = f"{output_dir}/{safe_query}_articles.csv"
    
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
    
    # Show first 3 articles as examples
    if len(articles) > 0:
        print("\nFirst 3 articles:")
        for i, article in enumerate(articles[:3], 1):
            print(f"\n{i}. {article['title']}")
            print(f"   Authors: {article['authors']}")
            print(f"   Journal: {article['publication_name']}")
            print(f"   Date: {article['cover_date']}")
            print(f"   DOI: {article['doi']}")
            print(f"   Citations: {article['cited_by_count']}")


if __name__ == "__main__":
    main()