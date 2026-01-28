"""
Script to merge RIS files from multiple sources and remove duplicates based on DOI
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

                # Check if this is a tag line (format: TAG  - Value)
                if line.startswith('ER  -'):
                    # End of record
                    if current_record:
                        records.append(current_record)
                        current_record = {}
                    current_tag = None
                elif '  - ' in line[:6]:
                    # New tag
                    tag = line[:2]
                    value = line[6:].strip()
                    current_tag = tag

                    # Handle multiple values for same tag (like multiple authors)
                    if tag in current_record:
                        if isinstance(current_record[tag], list):
                            current_record[tag].append(value)
                        else:
                            current_record[tag] = [current_record[tag], value]
                    else:
                        current_record[tag] = value
                elif current_tag and line.strip():
                    # Continuation of previous tag
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

    # Remove common URL prefixes
    doi = doi.lower().strip()
    doi = re.sub(r'^https?://(dx\.)?doi\.org/', '', doi)
    doi = re.sub(r'^doi:', '', doi)

    return doi.strip()


def merge_and_deduplicate(folders):
    """
    Merge RIS files from multiple folders and deduplicate based on DOI
    """
    all_records = []
    stats = {
        'total_files': 0,
        'records_per_source': {},
        'records_per_keyphrase': defaultdict(int),
        'total_records_before': 0,
        'records_with_doi': 0,
        'records_without_doi': 0,
        'duplicates_removed': 0,
        'total_records_after': 0
    }

    # Process each folder
    for folder in folders:
        folder_path = Path(folder)
        source_name = folder_path.name.replace('_output', '')
        stats['records_per_source'][source_name] = 0

        print(f"\nProcessing {source_name}...")

        # Process each RIS file in the folder
        for ris_file in folder_path.glob('*.ris'):
            stats['total_files'] += 1
            print(f"  Reading {ris_file.name}...")

            records = parse_ris_file(ris_file)

            # Extract keyphrase from filename
            keyphrase = ris_file.stem
            for pattern in ['_acm', '_pubmed', '_ALL_articles', '_part1', '_part2']:
                keyphrase = keyphrase.replace(pattern, '')

            # Add source and keyphrase metadata to each record
            for record in records:
                record['_source'] = source_name
                record['_source_file'] = ris_file.name
                record['_keyphrase'] = keyphrase
                all_records.append(record)
                stats['records_per_source'][source_name] += 1
                stats['records_per_keyphrase'][keyphrase] += 1

    stats['total_records_before'] = len(all_records)
    print(f"\n{'='*60}")
    print(f"Total records collected: {stats['total_records_before']}")

    # Deduplicate based on DOI
    print("\nDeduplicating based on DOI...")

    doi_to_record = {}
    records_without_doi = []
    duplicate_count = 0

    for record in all_records:
        doi = normalize_doi(record.get('DO', ''))

        if doi:
            stats['records_with_doi'] += 1
            if doi in doi_to_record:
                duplicate_count += 1
                # Keep track of sources where duplicates were found
                existing = doi_to_record[doi]
                if '_duplicate_sources' not in existing:
                    existing['_duplicate_sources'] = [existing['_source']]
                existing['_duplicate_sources'].append(record['_source'])
            else:
                doi_to_record[doi] = record
        else:
            stats['records_without_doi'] += 1
            records_without_doi.append(record)

    # Combine unique records
    unique_records = list(doi_to_record.values()) + records_without_doi

    stats['duplicates_removed'] = duplicate_count
    stats['total_records_after'] = len(unique_records)

    return unique_records, stats


def write_ris_file(records, output_file):
    """
    Write records to a RIS file
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        for record in records:
            # Write each tag
            for tag, value in record.items():
                # Skip metadata tags
                if tag.startswith('_'):
                    continue

                # Handle multiple values (like authors)
                if isinstance(value, list):
                    for v in value:
                        f.write(f"{tag}  - {v}\n")
                else:
                    f.write(f"{tag}  - {value}\n")

            # End of record
            f.write("ER  - \n\n")


def print_statistics(stats):
    """
    Print detailed statistics
    """
    print(f"\n{'='*60}")
    print("DEDUPLICATION STATISTICS")
    print(f"{'='*60}")

    print(f"\nTotal files processed: {stats['total_files']}")

    print(f"\nRecords per source:")
    for source, count in stats['records_per_source'].items():
        print(f"  {source:15s}: {count:5d} records")

    print(f"\nRecords per keyphrase:")
    sorted_keyphrases = sorted(stats['records_per_keyphrase'].items(),
                               key=lambda x: x[1], reverse=True)
    for keyphrase, count in sorted_keyphrases:
        print(f"  {keyphrase:60s}: {count:5d} records")

    print(f"\n{'-'*60}")
    print(f"Total records before deduplication: {stats['total_records_before']:5d}")
    print(f"  - Records with DOI:                {stats['records_with_doi']:5d}")
    print(f"  - Records without DOI:             {stats['records_without_doi']:5d}")
    print(f"\nDuplicates removed:                  {stats['duplicates_removed']:5d}")
    print(f"Total records after deduplication:   {stats['total_records_after']:5d}")
    print(f"\nDeduplication rate: {(stats['duplicates_removed']/stats['total_records_before']*100):.2f}%")
    print(f"{'='*60}")


def main():
    # Define the three source folders
    folders = ['acm_output', 'pubmed_output', 'scopus_output']

    # Check if folders exist
    for folder in folders:
        if not os.path.exists(folder):
            print(f"Error: Folder '{folder}' not found!")
            return

    print("Starting merge and deduplication process...")
    print("="*60)

    # Merge and deduplicate
    unique_records, stats = merge_and_deduplicate(folders)

    # Write output
    output_file = 'merged_deduplicated_papers.ris'
    print(f"\nWriting deduplicated records to {output_file}...")
    write_ris_file(unique_records, output_file)

    # Print statistics
    print_statistics(stats)

    # Write statistics to file
    stats_file = 'deduplication_statistics.txt'
    print(f"\nWriting statistics to {stats_file}...")

    with open(stats_file, 'w', encoding='utf-8') as f:
        f.write("DEDUPLICATION STATISTICS\n")
        f.write("="*60 + "\n\n")

        f.write(f"Total files processed: {stats['total_files']}\n\n")

        f.write("Records per source:\n")
        for source, count in stats['records_per_source'].items():
            f.write(f"  {source:15s}: {count:5d} records\n")

        f.write("\nRecords per keyphrase:\n")
        sorted_keyphrases = sorted(stats['records_per_keyphrase'].items(),
                                   key=lambda x: x[1], reverse=True)
        for keyphrase, count in sorted_keyphrases:
            f.write(f"  {keyphrase:60s}: {count:5d} records\n")

        f.write("\n" + "-"*60 + "\n")
        f.write(f"Total records before deduplication: {stats['total_records_before']:5d}\n")
        f.write(f"  - Records with DOI:                {stats['records_with_doi']:5d}\n")
        f.write(f"  - Records without DOI:             {stats['records_without_doi']:5d}\n")
        f.write(f"\nDuplicates removed:                  {stats['duplicates_removed']:5d}\n")
        f.write(f"Total records after deduplication:   {stats['total_records_after']:5d}\n")
        f.write(f"\nDeduplication rate: {(stats['duplicates_removed']/stats['total_records_before']*100):.2f}%\n")

    print(f"\n[SUCCESS] Process completed successfully!")
    print(f"  - Output file: {output_file}")
    print(f"  - Statistics file: {stats_file}")


if __name__ == "__main__":
    main()
