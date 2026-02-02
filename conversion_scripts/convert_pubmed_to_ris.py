#!/usr/bin/env python3
"""
PubMed JSON to RIS Converter
Converts PubMed JSON files to RIS (Research Information Systems) format
"""

import json
import os
import sys
from pathlib import Path


def parse_authors(author_string):
    """Parse comma-separated authors into individual names"""
    if not author_string or author_string == 'N/A':
        return []
    return [author.strip() for author in author_string.split(',')]


def parse_date(date_string):
    """Extract year from publication date"""
    if not date_string or date_string == 'N/A':
        return ''
    # Handle formats like "2023-Oct", "2020-Jul", "2021-May-27"
    parts = date_string.split('-')
    if parts:
        return parts[0]
    return ''


def parse_pages(page_range):
    """Parse page range into start and end pages"""
    if not page_range or page_range == 'N/A':
        return '', ''

    if '-' in page_range:
        parts = page_range.split('-')
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ''
    return page_range, ''


def convert_pubmed_to_ris(json_file, output_file):
    """
    Convert PubMed JSON file to RIS format

    Args:
        json_file: Path to input JSON file
        output_file: Path to output RIS file
    """
    print(f"Reading: {json_file}")

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            articles = json.load(f)

        print(f"Found {len(articles)} articles")

        with open(output_file, 'w', encoding='utf-8') as f:
            for article in articles:
                # Start of reference
                f.write("TY  - JOUR\n")  # Journal article

                # Title
                title = article.get('title', 'N/A')
                if title and title != 'N/A':
                    f.write(f"TI  - {title}\n")

                # Authors
                authors = parse_authors(article.get('authors', ''))
                for author in authors:
                    f.write(f"AU  - {author}\n")

                # Publication year
                year = parse_date(article.get('publication_date', ''))
                if year:
                    f.write(f"PY  - {year}\n")

                # Publication date (full)
                pub_date = article.get('publication_date', '')
                if pub_date and pub_date != 'N/A':
                    f.write(f"DA  - {pub_date}\n")

                # Journal
                journal = article.get('journal', 'N/A')
                if journal and journal != 'N/A':
                    f.write(f"JO  - {journal}\n")
                    f.write(f"JF  - {journal}\n")

                # Volume
                volume = article.get('volume', '')
                if volume and volume != 'N/A':
                    f.write(f"VL  - {volume}\n")

                # ISSN
                issn = article.get('issn', 'N/A')
                if issn and issn != 'N/A':
                    f.write(f"SN  - {issn}\n")

                # Abstract
                abstract = article.get('abstract', 'N/A')
                if abstract and abstract != 'N/A':
                    f.write(f"AB  - {abstract}\n")

                # Keywords
                keywords_str = article.get('keywords', 'N/A')
                if keywords_str and keywords_str != 'N/A':
                    keywords = [kw.strip() for kw in keywords_str.split(',')]
                    for keyword in keywords:
                        f.write(f"KW  - {keyword}\n")

                # MeSH terms
                mesh_terms = article.get('mesh_terms', 'N/A')
                if mesh_terms and mesh_terms != 'N/A':
                    mesh_list = [mesh.strip() for mesh in mesh_terms.split(',')]
                    for mesh in mesh_list:
                        f.write(f"KW  - {mesh}\n")

                # DOI
                doi = article.get('doi', 'N/A')
                if doi and doi != 'N/A':
                    f.write(f"DO  - {doi}\n")

                # PMID
                pmid = article.get('pmid', 'N/A')
                if pmid and pmid != 'N/A':
                    f.write(f"AN  - PMID:{pmid}\n")

                # PubMed URL
                url = article.get('pubmed_url', 'N/A')
                if url and url != 'N/A':
                    f.write(f"UR  - {url}\n")

                # PMC ID
                pmc_id = article.get('pmc_id', 'N/A')
                if pmc_id and pmc_id != 'N/A':
                    f.write(f"N1  - PMC:{pmc_id}\n")

                # Publication types
                pub_types = article.get('publication_types', 'N/A')
                if pub_types and pub_types != 'N/A':
                    f.write(f"N1  - Publication Types: {pub_types}\n")

                # End of reference
                f.write("ER  - \n\n")

        print(f"[OK] Converted to: {output_file}")
        return True

    except Exception as e:
        print(f"Error converting {json_file}: {e}")
        return False


def convert_directory(input_dir, output_dir=None):
    """
    Convert all PubMed JSON files in a directory

    Args:
        input_dir: Directory containing JSON files
        output_dir: Output directory (defaults to input_dir)
    """
    input_path = Path(input_dir)

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = input_path

    json_files = list(input_path.glob('*.json'))

    if not json_files:
        print(f"No JSON files found in {input_dir}")
        return

    print(f"\n{'='*70}")
    print(f"PubMed to RIS Converter")
    print(f"{'='*70}")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_path}")
    print(f"Found {len(json_files)} JSON files\n")

    success_count = 0
    for json_file in json_files:
        ris_filename = json_file.stem + '.ris'
        ris_file = output_path / ris_filename

        if convert_pubmed_to_ris(json_file, ris_file):
            success_count += 1

    print(f"\n{'='*70}")
    print(f"Conversion Summary")
    print(f"{'='*70}")
    print(f"Total files: {len(json_files)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(json_files) - success_count}")


def main():
    """Main execution function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Convert single file:     python convert_pubmed_to_ris.py <input.json> [output.ris]")
        print("  Convert directory:       python convert_pubmed_to_ris.py <input_directory> [output_directory]")
        print("\nExample:")
        print("  python convert_pubmed_to_ris.py output/pubmed_output/")
        return

    input_path = sys.argv[1]

    if os.path.isdir(input_path):
        # Directory mode
        output_dir = sys.argv[2] if len(sys.argv) > 2 else None
        convert_directory(input_path, output_dir)
    else:
        # Single file mode
        output_file = sys.argv[2] if len(sys.argv) > 2 else input_path.replace('.json', '.ris')
        convert_pubmed_to_ris(input_path, output_file)


if __name__ == "__main__":
    main()
