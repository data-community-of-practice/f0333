#!/usr/bin/env python3
"""
Scopus/ScienceDirect JSON to RIS Converter
Converts Scopus JSON files to RIS (Research Information Systems) format
"""

import json
import os
import sys
from pathlib import Path


def parse_authors(author_string):
    """Parse author string into individual names"""
    if not author_string or author_string == 'N/A':
        return []
    # Scopus may have authors separated by semicolons or commas
    if ';' in author_string:
        return [author.strip() for author in author_string.split(';')]
    return [author.strip() for author in author_string.split(',')]


def parse_date(date_string):
    """Extract year from cover date"""
    if not date_string or date_string == 'N/A':
        return ''
    # Handle formats like "2005-12-01", "2023-10"
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
    elif '–' in page_range:  # em-dash
        parts = page_range.split('–')
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ''
    return page_range, ''


def determine_type(article_type):
    """Map Scopus article type to RIS type"""
    article_type_lower = article_type.lower() if article_type and article_type != 'N/A' else ''

    if 'conference' in article_type_lower or 'proceeding' in article_type_lower:
        return 'CONF'
    elif 'review' in article_type_lower:
        return 'JOUR'  # Review article
    elif 'book' in article_type_lower:
        return 'BOOK'
    elif 'chapter' in article_type_lower:
        return 'CHAP'
    else:
        return 'JOUR'  # Default to journal article


def convert_scopus_to_ris(json_file, output_file):
    """
    Convert Scopus JSON file to RIS format

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
                # Determine reference type
                article_type = article.get('article_type', 'Article')
                ris_type = determine_type(article_type)
                f.write(f"TY  - {ris_type}\n")

                # Title
                title = article.get('title', 'N/A')
                if title and title != 'N/A':
                    f.write(f"TI  - {title}\n")

                # Authors
                authors = parse_authors(article.get('authors', ''))
                for author in authors:
                    f.write(f"AU  - {author}\n")

                # Publication year
                year = parse_date(article.get('cover_date', ''))
                if year:
                    f.write(f"PY  - {year}\n")

                # Publication date (full)
                cover_date = article.get('cover_date', '')
                if cover_date and cover_date != 'N/A':
                    f.write(f"DA  - {cover_date}\n")

                # Journal/Publication name
                pub_name = article.get('publication_name', 'N/A')
                if pub_name and pub_name != 'N/A':
                    if ris_type == 'CONF':
                        f.write(f"T2  - {pub_name}\n")  # Conference name
                    else:
                        f.write(f"JO  - {pub_name}\n")  # Journal name
                        f.write(f"JF  - {pub_name}\n")

                # Volume
                volume = article.get('volume', 'N/A')
                if volume and volume != 'N/A':
                    f.write(f"VL  - {volume}\n")

                # Pages
                page_range = article.get('page_range', 'N/A')
                if page_range and page_range != 'N/A':
                    start_page, end_page = parse_pages(page_range)
                    if start_page:
                        f.write(f"SP  - {start_page}\n")
                    if end_page:
                        f.write(f"EP  - {end_page}\n")

                # ISSN
                issn = article.get('issn', 'N/A')
                if issn and issn != 'N/A':
                    f.write(f"SN  - {issn}\n")

                # Abstract
                abstract = article.get('abstract', 'N/A')
                if abstract and abstract != 'N/A':
                    f.write(f"AB  - {abstract}\n")

                # DOI
                doi = article.get('doi', 'N/A')
                if doi and doi != 'N/A':
                    f.write(f"DO  - {doi}\n")

                # Scopus ID
                scopus_id = article.get('scopus_id', 'N/A')
                if scopus_id and scopus_id != 'N/A':
                    # Extract just the ID number if it's in format "SCOPUS_ID:xxxxx"
                    if ':' in scopus_id:
                        scopus_id = scopus_id.split(':')[-1]
                    f.write(f"AN  - Scopus:{scopus_id}\n")

                # URL/Link
                link = article.get('link', 'N/A')
                if link and link != 'N/A':
                    f.write(f"UR  - {link}\n")

                # PII
                pii = article.get('pii', 'N/A')
                if pii and pii != 'N/A':
                    f.write(f"N1  - PII:{pii}\n")

                # Citation count
                cited_by = article.get('cited_by_count', '0')
                if cited_by and cited_by != '0':
                    f.write(f"N1  - Cited by: {cited_by}\n")

                # Article type
                if article_type and article_type != 'N/A':
                    f.write(f"N1  - Document Type: {article_type}\n")

                # End of reference
                f.write("ER  - \n\n")

        print(f"[OK] Converted to: {output_file}")
        return True

    except Exception as e:
        print(f"Error converting {json_file}: {e}")
        return False


def convert_directory(input_dir, output_dir=None):
    """
    Convert all Scopus JSON files in a directory

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
    print(f"Scopus to RIS Converter")
    print(f"{'='*70}")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_path}")
    print(f"Found {len(json_files)} JSON files\n")

    success_count = 0
    for json_file in json_files:
        ris_filename = json_file.stem + '.ris'
        ris_file = output_path / ris_filename

        if convert_scopus_to_ris(json_file, ris_file):
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
        print("  Convert single file:     python convert_scopus_to_ris.py <input.json> [output.ris]")
        print("  Convert directory:       python convert_scopus_to_ris.py <input_directory> [output_directory]")
        print("\nExample:")
        print("  python convert_scopus_to_ris.py output/Scopus/")
        return

    input_path = sys.argv[1]

    if os.path.isdir(input_path):
        # Directory mode
        output_dir = sys.argv[2] if len(sys.argv) > 2 else None
        convert_directory(input_path, output_dir)
    else:
        # Single file mode
        output_file = sys.argv[2] if len(sys.argv) > 2 else input_path.replace('.json', '.ris')
        convert_scopus_to_ris(input_path, output_file)


if __name__ == "__main__":
    main()
