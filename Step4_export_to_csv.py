"""
Script to convert the merged and deduplicated RIS file to CSV format for easier analysis
"""

import csv
import re
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


def export_to_csv(ris_file, csv_file):
    """
    Export RIS records to CSV format
    """
    print(f"Reading {ris_file}...")
    records = parse_ris_file(ris_file)

    if not records:
        print("No records found!")
        return

    print(f"Found {len(records)} records")

    # Define common fields to export
    common_fields = ['TI', 'DO', 'PY', 'AU', 'T2', 'AB', 'KW', 'UR', 'PB', 'TY']
    field_names = {
        'TI': 'Title',
        'DO': 'DOI',
        'PY': 'Year',
        'AU': 'Authors',
        'T2': 'Publication',
        'AB': 'Abstract',
        'KW': 'Keywords',
        'UR': 'URL',
        'PB': 'Publisher',
        'TY': 'Type',
        '_source': 'Source',
        '_keyphrase': 'Search_Keyphrase',
        '_duplicate_sources': 'Found_In_Sources'
    }

    # Collect all unique fields present in records
    all_fields = set()
    for record in records:
        all_fields.update(record.keys())

    # Order fields: common fields first, then others
    ordered_fields = [f for f in common_fields if f in all_fields]
    # Add metadata fields
    for meta_field in ['_source', '_keyphrase', '_duplicate_sources']:
        if meta_field in all_fields:
            ordered_fields.append(meta_field)
    # Add remaining fields
    for field in sorted(all_fields):
        if field not in ordered_fields:
            ordered_fields.append(field)

    print(f"Writing to {csv_file}...")

    with open(csv_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=ordered_fields, extrasaction='ignore')

        # Write header with friendly names
        header = {field: field_names.get(field, field) for field in ordered_fields}
        writer.writerow(header)

        # Write records
        for record in records:
            # Format list values (like multiple authors)
            formatted_record = {}
            for field in ordered_fields:
                value = record.get(field, '')
                if isinstance(value, list):
                    formatted_record[field] = '; '.join(value)
                else:
                    formatted_record[field] = value

            writer.writerow(formatted_record)

    print(f"[SUCCESS] Successfully exported {len(records)} records to {csv_file}")


def main():
    ris_file = 'merged_deduplicated_papers.ris'
    csv_file = 'merged_deduplicated_papers.csv'

    if not Path(ris_file).exists():
        print(f"Error: {ris_file} not found!")
        print("Please run merge_and_deduplicate.py first.")
        return

    export_to_csv(ris_file, csv_file)


if __name__ == "__main__":
    main()
