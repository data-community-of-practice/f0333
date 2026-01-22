#!/usr/bin/env python3
"""
ScienceDirect Fetcher - Get ALL Results (Bypass 5000 Limit)
This script splits queries by year to fetch more than 5000 results
"""

import sys
import os
import configparser
import subprocess
import json
import csv
from datetime import datetime

# Import the main fetcher
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Helper_sciencedirect_fetcher_v2 import ScienceDirectFetcher, load_config


def get_year_range():
    """Get year range from user or config"""
    current_year = datetime.now().year
    
    print("="*70)
    print("FETCH ALL RESULTS BY YEAR")
    print("="*70)
    print("\nTo bypass the 5000 result limit, we'll split your query by year.")
    print(f"\nDefault range: 2000-{current_year}")
    
    start_year = input(f"\nEnter start year (default 2000): ").strip()
    end_year = input(f"Enter end year (default {current_year}): ").strip()
    
    start_year = int(start_year) if start_year else 2000
    end_year = int(end_year) if end_year else current_year
    
    return start_year, end_year


def fetch_by_year(config, start_year, end_year):
    """Fetch results year by year"""
    
    # Initialize fetcher
    if config['auth_method'] == 'oauth':
        print("Using OAuth2 authentication...")
        fetcher = ScienceDirectFetcher(base_url=config['base_url'])
        access_token = fetcher.get_oauth_token(config['client_id'], config['client_secret'])
        if not access_token:
            print("Failed to get OAuth token")
            return []
        fetcher.access_token = access_token
        fetcher.headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
    else:
        fetcher = ScienceDirectFetcher(api_key=config['api_key'], base_url=config['base_url'])
    
    base_query = config['query']
    all_articles = []
    
    print("\n" + "="*70)
    print(f"Fetching results from {start_year} to {end_year}")
    print("="*70 + "\n")
    
    for year in range(start_year, end_year + 1):
        print(f"\n{'='*70}")
        print(f"YEAR: {year}")
        print(f"{'='*70}")
        
        # Add year filter to query
        year_query = f"{base_query} AND PUBYEAR IS {year}"
        
        # Fetch results for this year
        raw_results = fetcher.search_articles(year_query, max_results=0)
        
        if raw_results:
            # Extract article info
            articles = fetcher.extract_article_info(raw_results)
            all_articles.extend(articles)
            
            print(f"✓ Year {year}: {len(articles)} articles fetched")
            print(f"✓ Total so far: {len(all_articles)} articles")
        else:
            print(f"✗ Year {year}: No results")
        
        # Small delay between years
        import time
        time.sleep(2)
    
    return all_articles


def merge_and_save(articles, query, output_dir):
    """Save all articles to files"""
    
    if not articles:
        print("\nNo articles to save!")
        return
    
    # Remove duplicates based on DOI
    seen_dois = set()
    unique_articles = []
    
    for article in articles:
        doi = article.get('doi', 'N/A')
        if doi != 'N/A' and doi not in seen_dois:
            seen_dois.add(doi)
            unique_articles.append(article)
        elif doi == 'N/A':
            unique_articles.append(article)
    
    print(f"\n{'='*70}")
    print("DEDUPLICATION")
    print(f"{'='*70}")
    print(f"Total articles fetched: {len(articles)}")
    print(f"Unique articles: {len(unique_articles)}")
    print(f"Duplicates removed: {len(articles) - len(unique_articles)}")
    
    # Create safe filename from query
    safe_query = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in query)
    safe_query = safe_query.replace(' ', '_')[:50]
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Save to JSON
    json_file = f"{output_dir}/{safe_query}_ALL_articles.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(unique_articles, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Saved to: {json_file}")
    
    # Save to CSV
    csv_file = f"{output_dir}/{safe_query}_ALL_articles.csv"
    if unique_articles:
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=unique_articles[0].keys())
            writer.writeheader()
            writer.writerows(unique_articles)
        print(f"✓ Saved to: {csv_file}")
    
    return json_file, csv_file


def main():
    """Main execution"""
    
    # Load config
    config = load_config("config.ini")
    if not config:
        return
    
    # Get year range
    start_year, end_year = get_year_range()
    
    # Confirm with user
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Query: {config['query']}")
    print(f"Years: {start_year} to {end_year}")
    print(f"Total years to fetch: {end_year - start_year + 1}")
    print(f"\nThis will make multiple API calls and may take a while.")
    
    confirm = input("\nProceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return
    
    # Fetch all results
    articles = fetch_by_year(config, start_year, end_year)
    
    # Save results
    if articles:
        json_file, csv_file = merge_and_save(articles, config['query'], config['output_dir'])
        
        # Print final summary
        print(f"\n{'='*70}")
        print("FINAL RESULTS")
        print(f"{'='*70}")
        print(f"Total unique articles: {len(articles)}")
        print(f"Years covered: {start_year}-{end_year}")
        print(f"\nFiles created:")
        print(f"  - {json_file}")
        print(f"  - {csv_file}")
        
        # Show distribution by year
        year_counts = {}
        for article in articles:
            year = article.get('cover_date', 'N/A')[:4]
            year_counts[year] = year_counts.get(year, 0) + 1
        
        print(f"\nDistribution by year:")
        for year in sorted(year_counts.keys()):
            if year != 'N/A':
                print(f"  {year}: {year_counts[year]} articles")
    else:
        print("\nNo articles fetched!")


if __name__ == "__main__":
    main()