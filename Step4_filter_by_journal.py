#!/usr/bin/env python3
"""
RIS Journal Filter
Filters RIS files to keep only papers from specified journals
"""

import os
import sys
from pathlib import Path
from collections import defaultdict, Counter


# Target journals to keep
TARGET_JOURNALS = [
    "Journal of Biomedical Informatics",
    "Journal of the American Medical Informatics Association",
    "International Journal of Medical Informatics",
    "BMC Medical Informatics and Decision Making",
    "Studies in Health Technology and Informatics",
    "Computers in Biology and Medicine",
    "IEEE Access",
    "Expert Systems with Applications",
    "Biomedical Signal Processing and Control",
    "Sensors",
    "Applied Sciences Switzerland"
]


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


def normalize_journal_name(journal_name):
    """
    Normalize journal name for comparison

    Args:
        journal_name: Journal name string

    Returns:
        Normalized journal name (lowercase, stripped)
    """
    if not journal_name:
        return ""

    # Convert to lowercase and strip whitespace
    normalized = journal_name.lower().strip()

    # Remove common punctuation that might vary
    normalized = normalized.replace(':', '').replace(',', '').replace('.', '')

    # Normalize spaces
    normalized = ' '.join(normalized.split())

    return normalized


def get_journal_from_record(record):
    """
    Extract journal name from record

    Args:
        record: Record dict

    Returns:
        Journal name string or None
    """
    # Try JO (Journal) tag first
    if 'JO' in record and record['JO']:
        return record['JO'][0].strip()

    # Try JF (Journal Full) tag
    if 'JF' in record and record['JF']:
        return record['JF'][0].strip()

    # Try T2 (Secondary Title - used for conference journals)
    if 'T2' in record and record['T2']:
        return record['T2'][0].strip()

    return None


def matches_target_journal(journal_name, target_journals):
    """
    Check if journal name matches any target journal

    Args:
        journal_name: Journal name from record
        target_journals: List of target journal names

    Returns:
        Matched target journal name or None
    """
    if not journal_name:
        return None

    normalized_journal = normalize_journal_name(journal_name)

    for target in target_journals:
        normalized_target = normalize_journal_name(target)

        # Check for exact match
        if normalized_journal == normalized_target:
            return target

        # Check if target journal is contained in the journal name
        # (handles cases where journal name includes extra info)
        if normalized_target in normalized_journal:
            return target

    return None


def filter_by_journal(records, target_journals):
    """
    Filter records to keep only those from target journals

    Args:
        records: List of record dicts
        target_journals: List of target journal names

    Returns:
        Tuple of (filtered_records, stats_dict)
    """
    filtered_records = []
    matched_journals = Counter()
    unmatched_journals = Counter()
    no_journal_count = 0

    for record in records:
        journal = get_journal_from_record(record)

        if not journal:
            no_journal_count += 1
            continue

        matched_target = matches_target_journal(journal, target_journals)

        if matched_target:
            filtered_records.append(record)
            matched_journals[matched_target] += 1
        else:
            unmatched_journals[journal] += 1

    stats = {
        'matched': matched_journals,
        'unmatched': unmatched_journals,
        'no_journal': no_journal_count
    }

    return filtered_records, stats


def filter_file(input_file, output_file, target_journals):
    """
    Filter a single RIS file by journal

    Args:
        input_file: Path to input RIS file
        output_file: Path to output RIS file
        target_journals: List of target journal names

    Returns:
        Statistics dict
    """
    print(f"\nProcessing: {input_file.name}")

    # Parse records
    records = parse_ris_file(input_file)
    records_before = len(records)
    print(f"  Records before filtering: {records_before}")

    # Filter by journal
    filtered_records, stats = filter_by_journal(records, target_journals)
    records_after = len(filtered_records)
    records_removed = records_before - records_after

    print(f"  Records after filtering:  {records_after}")
    print(f"  Records removed:          {records_removed} ({(records_removed/records_before*100):.1f}%)")

    # Write filtered records
    if filtered_records:
        write_ris_file(filtered_records, output_file)
        print(f"  [OK] Saved: {output_file.name}")
    else:
        print(f"  [WARNING] No matching records - output file not created")

    return {
        'before': records_before,
        'after': records_after,
        'removed': records_removed,
        'matched_journals': stats['matched'],
        'no_journal': stats['no_journal']
    }


def filter_directory(input_dir, output_dir, target_journals):
    """
    Filter all RIS files in a directory

    Args:
        input_dir: Input directory path
        output_dir: Output directory path
        target_journals: List of target journal names
    """
    print("="*70)
    print("RIS Journal Filter")
    print("="*70)
    print(f"\nTarget journals ({len(target_journals)}):")
    for i, journal in enumerate(target_journals, 1):
        print(f"  {i:2d}. {journal}")

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Find all RIS files
    ris_files = list(input_path.glob('*.ris'))

    if not ris_files:
        print(f"\nNo RIS files found in {input_dir}")
        return

    print(f"\nFound {len(ris_files)} RIS file(s) to process")

    # Process each file
    total_before = 0
    total_after = 0
    all_matched_journals = Counter()
    file_stats = []

    for ris_file in sorted(ris_files):
        output_file = output_path / f"{ris_file.stem}_filtered.ris"
        stats = filter_file(ris_file, output_file, target_journals)

        total_before += stats['before']
        total_after += stats['after']
        all_matched_journals.update(stats['matched_journals'])

        file_stats.append({
            'name': ris_file.name,
            'before': stats['before'],
            'after': stats['after'],
            'removed': stats['removed']
        })

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    print(f"\nOVERALL STATISTICS:")
    print(f"  Files processed:           {len(ris_files)}")
    print(f"  Total records BEFORE:      {total_before:>6}")
    print(f"  Total records AFTER:       {total_after:>6}")
    print(f"  Total records removed:     {total_before - total_after:>6} ({((total_before-total_after)/total_before*100):.1f}%)")
    print(f"  Retention rate:            {(total_after/total_before*100):.1f}%")

    # Breakdown by file
    print(f"\n{'-'*70}")
    print("BREAKDOWN BY FILE:")
    print(f"{'-'*70}")
    print(f"{'File':<50} {'Before':>8} {'After':>8} {'Removed':>8}")
    print(f"{'-'*70}")

    for stat in file_stats:
        name = stat['name']
        if len(name) > 49:
            name = name[:46] + '...'
        print(f"{name:<50} {stat['before']:>8} {stat['after']:>8} {stat['removed']:>8}")

    print(f"{'-'*70}")
    print(f"{'TOTAL':<50} {total_before:>8} {total_after:>8} {total_before - total_after:>8}")
    print(f"{'-'*70}")

    # Matched journals distribution
    if all_matched_journals:
        print(f"\nMATCHED JOURNALS DISTRIBUTION:")
        print(f"{'-'*70}")
        for journal, count in all_matched_journals.most_common():
            print(f"  {journal:<60} {count:>6}")
        print(f"{'-'*70}")
        print(f"  {'TOTAL':<60} {sum(all_matched_journals.values()):>6}")

    print(f"\nFiltered files saved to: {output_dir}/")
    for stat in file_stats:
        if stat['after'] > 0:
            filename = stat['name'].replace('.ris', '_filtered.ris')
            print(f"  - {filename:<55} {stat['after']:>6} records")


def main():
    """Main execution function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python Step4_filter_by_journal.py <input_file_or_directory> [output_directory]")
        print("\nExamples:")
        print("  python Step4_filter_by_journal.py merged_output/ filtered_output/")
        print("  python Step4_filter_by_journal.py input.ris output_filtered.ris")
        print("\nTarget Journals:")
        for i, journal in enumerate(TARGET_JOURNALS, 1):
            print(f"  {i:2d}. {journal}")
        return

    input_path = sys.argv[1]

    if not os.path.exists(input_path):
        print(f"Error: Input path '{input_path}' not found!")
        return

    if os.path.isdir(input_path):
        # Directory mode
        output_dir = sys.argv[2] if len(sys.argv) > 2 else 'filtered_output'
        filter_directory(input_path, output_dir, TARGET_JOURNALS)
    else:
        # Single file mode
        output_file = sys.argv[2] if len(sys.argv) > 2 else input_path.replace('.ris', '_filtered.ris')
        input_file = Path(input_path)
        output_file = Path(output_file)

        print("="*70)
        print("RIS Journal Filter")
        print("="*70)
        print(f"\nTarget journals ({len(TARGET_JOURNALS)}):")
        for i, journal in enumerate(TARGET_JOURNALS, 1):
            print(f"  {i:2d}. {journal}")

        filter_file(input_file, output_file, TARGET_JOURNALS)


if __name__ == "__main__":
    main()
