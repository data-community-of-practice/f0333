"""
Script to analyze duplicates in detail - shows which papers appeared in multiple sources
"""

import os
import re
from collections import defaultdict
from pathlib import Path


def parse_ris_file(file_path):
    """
    Parse a RIS file and extract individual records
    Returns a list of dictionaries, each representing a paper record
    """
    records = []
    current_record = {}
    current_tag = None

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.rstrip('\n')

                if line.startswith('ER  -'):
                    if current_record:
                        records.append(current_record)
                        current_record = {}
                    current_tag = None
                elif '  - ' in line[:6]:
                    tag = line[:2]
                    value = line[6:].strip()
                    current_tag = tag

                    if tag in current_record:
                        if isinstance(current_record[tag], list):
                            current_record[tag].append(value)
                        else:
                            current_record[tag] = [current_record[tag], value]
                    else:
                        current_record[tag] = value
                elif current_tag and line.strip():
                    if isinstance(current_record[current_tag], list):
                        current_record[current_tag][-1] += ' ' + line.strip()
                    else:
                        current_record[current_tag] += ' ' + line.strip()

    except Exception as e:
        print(f"Error parsing {file_path}: {e}")

    return records


def normalize_doi(doi):
    """
    Normalize DOI by removing URL prefix and converting to lowercase
    """
    if not doi:
        return None

    doi = doi.lower().strip()
    doi = re.sub(r'^https?://(dx\.)?doi\.org/', '', doi)
    doi = re.sub(r'^doi:', '', doi)

    return doi.strip()


def analyze_duplicates(folders):
    """
    Analyze duplicates across sources and keyphrases
    """
    all_records = []

    # Collect all records with metadata
    for folder in folders:
        folder_path = Path(folder)
        source_name = folder_path.name.replace('_output', '')

        for ris_file in folder_path.glob('*.ris'):
            records = parse_ris_file(ris_file)

            # Extract keyphrase from filename
            keyphrase = ris_file.stem
            for pattern in ['_acm', '_pubmed', '_ALL_articles', '_part1', '_part2']:
                keyphrase = keyphrase.replace(pattern, '')

            for record in records:
                record['_source'] = source_name
                record['_source_file'] = ris_file.name
                record['_keyphrase'] = keyphrase
                all_records.append(record)

    # Build DOI index
    doi_index = defaultdict(list)
    records_without_doi = []

    for record in all_records:
        doi = normalize_doi(record.get('DO', ''))
        if doi:
            doi_index[doi].append(record)
        else:
            records_without_doi.append(record)

    # Analyze duplicates
    duplicates = {doi: records for doi, records in doi_index.items() if len(records) > 1}

    # Statistics
    stats = {
        'total_records': len(all_records),
        'unique_dois': len(doi_index),
        'records_without_doi': len(records_without_doi),
        'duplicate_dois': len(duplicates),
        'total_duplicate_records': sum(len(records) - 1 for records in duplicates.values())
    }

    # Source overlap analysis
    source_overlap = defaultdict(int)
    for doi, records in duplicates.items():
        sources = sorted(set(r['_source'] for r in records))
        source_key = ' & '.join(sources)
        source_overlap[source_key] += 1

    # Keyphrase overlap analysis
    keyphrase_overlap = defaultdict(int)
    for doi, records in duplicates.items():
        keyphrases = sorted(set(r['_keyphrase'] for r in records))
        if len(keyphrases) > 1:
            keyphrase_key = ' & '.join(keyphrases[:3])  # Show up to 3
            if len(keyphrases) > 3:
                keyphrase_key += f' (+{len(keyphrases)-3} more)'
            keyphrase_overlap[keyphrase_key] += 1

    return stats, source_overlap, keyphrase_overlap, duplicates


def print_analysis(stats, source_overlap, keyphrase_overlap, duplicates, output_file=None):
    """
    Print detailed analysis
    """
    output = []

    def write(text=""):
        output.append(text)
        print(text)

    write("="*80)
    write("DUPLICATE ANALYSIS REPORT")
    write("="*80)

    write(f"\nOVERALL STATISTICS:")
    write(f"  Total records collected:        {stats['total_records']:,}")
    write(f"  Unique DOIs:                    {stats['unique_dois']:,}")
    write(f"  Records without DOI:            {stats['records_without_doi']:,}")
    write(f"  DOIs with duplicates:           {stats['duplicate_dois']:,}")
    write(f"  Total duplicate records:        {stats['total_duplicate_records']:,}")
    write(f"  Deduplication rate:             {(stats['total_duplicate_records']/stats['total_records']*100):.2f}%")

    write(f"\n{'='*80}")
    write("SOURCE OVERLAP ANALYSIS")
    write("="*80)
    write("\nNumber of papers found in multiple sources:")

    sorted_sources = sorted(source_overlap.items(), key=lambda x: x[1], reverse=True)
    for source_combo, count in sorted_sources:
        write(f"  {source_combo:40s}: {count:5,} papers")

    write(f"\n{'='*80}")
    write("KEYPHRASE OVERLAP ANALYSIS")
    write("="*80)
    write("\nNumber of papers appearing in multiple keyphrases:")

    sorted_keyphrases = sorted(keyphrase_overlap.items(), key=lambda x: x[1], reverse=True)
    for keyphrase_combo, count in sorted_keyphrases[:20]:  # Show top 20
        write(f"  {keyphrase_combo:60s}: {count:5,} papers")

    if len(keyphrase_overlap) > 20:
        write(f"  ... and {len(keyphrase_overlap) - 20} more combinations")

    write(f"\n{'='*80}")
    write("SAMPLE DUPLICATES (First 10)")
    write("="*80)

    for i, (doi, records) in enumerate(list(duplicates.items())[:10], 1):
        title = records[0].get('TI', 'No title')
        if len(title) > 70:
            title = title[:67] + "..."

        write(f"\n{i}. {title}")
        write(f"   DOI: {doi}")
        write(f"   Found {len(records)} times in:")

        for record in records:
            write(f"     - {record['_source']:10s} | {record['_keyphrase']}")

    # Write to file if requested
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output))
        write(f"\n{'='*80}")
        write(f"Report saved to: {output_file}")


def main():
    folders = ['acm_output', 'pubmed_output', 'scopus_output']

    # Check if folders exist
    for folder in folders:
        if not os.path.exists(folder):
            print(f"Error: Folder '{folder}' not found!")
            return

    print("Analyzing duplicates across sources and keyphrases...")
    print("This may take a moment...\n")

    stats, source_overlap, keyphrase_overlap, duplicates = analyze_duplicates(folders)

    output_file = 'duplicate_analysis_report.txt'
    print_analysis(stats, source_overlap, keyphrase_overlap, duplicates, output_file)


if __name__ == "__main__":
    main()
