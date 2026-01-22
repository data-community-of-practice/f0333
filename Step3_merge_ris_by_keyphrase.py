#!/usr/bin/env python3
"""
RIS File Merger and Deduplicator
Merges RIS files by key phrase and deduplicates based on DOI
"""

import os
import sys
from pathlib import Path
from collections import defaultdict
import re


def parse_ris_file(filepath):
    """
    Parse a RIS file and return list of records (each record is a dict of tag->values)

    Args:
        filepath: Path to RIS file

    Returns:
        List of records, where each record is a dict
    """
    records = []
    current_record = defaultdict(list)

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n\r')

            # End of record
            if line.startswith('ER  - '):
                if current_record:
                    records.append(dict(current_record))
                    current_record = defaultdict(list)
                continue

            # Parse tag-value pair
            if line and '  - ' in line:
                parts = line.split('  - ', 1)
                if len(parts) == 2:
                    tag = parts[0].strip()
                    value = parts[1].strip()
                    current_record[tag].append(value)

    return records


def write_ris_file(records, output_file):
    """
    Write records to RIS file

    Args:
        records: List of record dicts
        output_file: Output file path
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        for record in records:
            # Write in standard RIS order
            tag_order = ['TY', 'TI', 'AU', 'PY', 'DA', 'JO', 'JF', 'T2', 'VL', 'IS',
                        'SP', 'EP', 'SN', 'AB', 'KW', 'DO', 'UR', 'AN', 'N1',
                        'PB', 'CY', 'BT', 'ED', 'T3']

            # Write ordered tags first
            for tag in tag_order:
                if tag in record:
                    for value in record[tag]:
                        f.write(f"{tag}  - {value}\n")

            # Write any remaining tags
            for tag, values in record.items():
                if tag not in tag_order:
                    for value in values:
                        f.write(f"{tag}  - {value}\n")

            # End of record
            f.write("ER  - \n\n")


def get_doi_from_record(record):
    """
    Extract DOI from a record

    Args:
        record: Record dict

    Returns:
        DOI string or None
    """
    if 'DO' in record and record['DO']:
        doi = record['DO'][0].strip()
        # Clean DOI - remove URL prefix if present
        doi = doi.replace('https://doi.org/', '')
        doi = doi.replace('http://doi.org/', '')
        doi = doi.replace('doi:', '')
        return doi.lower()
    return None


def get_title_from_record(record):
    """Extract title from record for logging"""
    if 'TI' in record and record['TI']:
        return record['TI'][0][:100]
    return 'Unknown'


def deduplicate_records(records):
    """
    Deduplicate records based on DOI

    Args:
        records: List of record dicts

    Returns:
        Deduplicated list of records, list of duplicates info
    """
    unique_records = []
    seen_dois = {}
    duplicates = []
    no_doi_count = 0

    for record in records:
        doi = get_doi_from_record(record)

        if doi:
            if doi in seen_dois:
                # Duplicate found
                duplicates.append({
                    'doi': doi,
                    'title': get_title_from_record(record),
                    'original_title': get_title_from_record(seen_dois[doi])
                })
            else:
                # New DOI
                seen_dois[doi] = record
                unique_records.append(record)
        else:
            # No DOI - keep all records without DOI
            unique_records.append(record)
            no_doi_count += 1

    return unique_records, duplicates, no_doi_count


def extract_keyphrase(filename):
    """
    Extract key phrase from filename

    Args:
        filename: Filename string

    Returns:
        Key phrase or None
    """
    keyphrases = [
        'automated_ICD_coding',
        'automatic_international_classification_of_diseases',
        'computer_assisted_ICD_coding',
        'clinical_coding_ICD'
    ]

    filename_lower = filename.lower()
    for phrase in keyphrases:
        if phrase.lower() in filename_lower:
            return phrase

    return None


def find_ris_files(input_dir):
    """
    Find all RIS files and group by key phrase

    Args:
        input_dir: Base directory to search

    Returns:
        Dict mapping key phrase to list of file paths
    """
    grouped_files = defaultdict(list)

    input_path = Path(input_dir)

    # Find all .ris files recursively
    for ris_file in input_path.rglob('*.ris'):
        keyphrase = extract_keyphrase(ris_file.name)
        if keyphrase:
            grouped_files[keyphrase].append(ris_file)

    return grouped_files


def merge_and_deduplicate(input_dir, output_dir):
    """
    Merge RIS files by key phrase and deduplicate

    Args:
        input_dir: Input directory containing RIS files
        output_dir: Output directory for merged files
    """
    print("="*70)
    print("RIS File Merger and Deduplicator")
    print("="*70)
    print(f"\nSearching for RIS files in: {input_dir}\n")

    # Find and group files
    grouped_files = find_ris_files(input_dir)

    if not grouped_files:
        print("No RIS files found!")
        return

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Process each key phrase
    total_original = 0
    total_unique = 0
    total_duplicates = 0

    # Track stats per keyphrase for summary table
    keyphrase_stats = {}

    for keyphrase, files in sorted(grouped_files.items()):
        print(f"\n{'='*70}")
        print(f"Key Phrase: {keyphrase}")
        print(f"{'='*70}")
        print(f"Input: {len(files)} file(s) to merge")

        # Parse all files for this key phrase
        all_records = []
        file_details = []

        for ris_file in files:
            records = parse_ris_file(ris_file)
            all_records.extend(records)
            file_details.append({
                'name': ris_file.name,
                'count': len(records)
            })

        # Show file breakdown
        print("\nSource files:")
        for detail in file_details:
            print(f"  - {detail['name']:<60} {detail['count']:>6} records")

        records_before = len(all_records)
        print(f"\n{'-'*70}")
        print(f"BEFORE MERGING:  {records_before:>6} total records")

        # Deduplicate
        unique_records, duplicates, no_doi_count = deduplicate_records(all_records)

        records_after = len(unique_records)
        records_removed = len(duplicates)
        records_with_doi = records_after - no_doi_count

        print(f"AFTER MERGING:   {records_after:>6} unique records")
        print(f"{'-'*70}")
        print(f"Change:          {records_removed:>6} duplicates removed ({(records_removed/records_before*100):.1f}%)")
        print(f"\nBreakdown:")
        print(f"  - Records with DOI:    {records_with_doi:>6}")
        print(f"  - Records without DOI: {no_doi_count:>6} (all kept)")

        # Store stats for summary
        keyphrase_stats[keyphrase] = {
            'files': len(files),
            'before': records_before,
            'after': records_after,
            'removed': records_removed,
            'with_doi': records_with_doi,
            'no_doi': no_doi_count
        }

        total_original += records_before
        total_unique += records_after
        total_duplicates += records_removed

        # Write merged file
        output_file = output_path / f"{keyphrase}_merged.ris"
        write_ris_file(unique_records, output_file)
        print(f"\n[OK] Saved: {output_file.name}")

        # Show some duplicate examples
        if duplicates:
            print(f"\nExample duplicates removed (showing first 3):")
            for dup in duplicates[:3]:
                print(f"  DOI: {dup['doi']}")
                print(f"    Title: {dup['title'][:80]}...")

    # Final summary
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")

    # Overall stats
    print(f"\nOVERALL STATISTICS:")
    print(f"  Key phrases processed:     {len(grouped_files)}")
    print(f"  Total records BEFORE:      {total_original:>6}")
    print(f"  Total records AFTER:       {total_unique:>6}")
    print(f"  Total duplicates removed:  {total_duplicates:>6} ({(total_duplicates/total_original*100):.1f}%)")
    print(f"  Net reduction:             {total_duplicates:>6} records")

    # Summary table by keyphrase
    print(f"\n{'-'*70}")
    print("BREAKDOWN BY KEY PHRASE:")
    print(f"{'-'*70}")
    print(f"{'Key Phrase':<45} {'Before':>8} {'After':>8} {'Removed':>8}")
    print(f"{'-'*70}")

    for keyphrase in sorted(keyphrase_stats.keys()):
        stats = keyphrase_stats[keyphrase]
        # Shorten keyphrase for display
        display_name = keyphrase.replace('_', ' ').title()
        if len(display_name) > 44:
            display_name = display_name[:41] + '...'

        print(f"{display_name:<45} {stats['before']:>8} {stats['after']:>8} {stats['removed']:>8}")

    print(f"{'-'*70}")
    print(f"{'TOTAL':<45} {total_original:>8} {total_unique:>8} {total_duplicates:>8}")
    print(f"{'-'*70}")

    print(f"\nOutput files created in: {output_dir}/")
    for keyphrase in sorted(grouped_files.keys()):
        filename = f"{keyphrase}_merged.ris"
        records = keyphrase_stats[keyphrase]['after']
        print(f"  - {filename:<60} {records:>6} records")

    print("\nThese merged files are ready to import into reference management software")
    print("such as Zotero, Mendeley, EndNote, or RefWorks.")


def main():
    """Main execution function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python merge_ris_by_keyphrase.py <input_directory> [output_directory]")
        print("\nExample:")
        print("  python merge_ris_by_keyphrase.py output/ merged_output/")
        print("  python merge_ris_by_keyphrase.py output/")
        print("\nThis will:")
        print("  1. Find all RIS files in input_directory")
        print("  2. Group them by key phrase:")
        print("     - automated_ICD_coding")
        print("     - automatic_international_classification_of_diseases")
        print("     - computer_assisted_ICD_coding")
        print("     - clinical_coding_ICD")
        print("  3. Merge files with the same key phrase")
        print("  4. Deduplicate based on DOI")
        print("  5. Save merged files to output_directory")
        return

    input_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'merged_output'

    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_dir}' not found!")
        return

    merge_and_deduplicate(input_dir, output_dir)


if __name__ == "__main__":
    main()
