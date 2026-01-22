#!/usr/bin/env python3
"""
RIS Article Type Filter
Filters RIS files to keep only journal articles (JOUR) and conference papers (CONF)
Removes books (BOOK) and book chapters (CHAP)
"""

import os
import sys
from pathlib import Path
from collections import defaultdict, Counter


# Article types to keep
KEEP_TYPES = ['JOUR', 'CONF']

# Article types to remove
REMOVE_TYPES = ['BOOK', 'CHAP']


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


def get_type_from_record(record):
    """
    Extract article type from record

    Args:
        record: Record dict

    Returns:
        Article type string or None
    """
    if 'TY' in record and record['TY']:
        return record['TY'][0].strip()
    return None


def get_title_from_record(record):
    """
    Extract title from record for logging

    Args:
        record: Record dict

    Returns:
        Title string (truncated to 80 chars)
    """
    if 'TI' in record and record['TI']:
        title = record['TI'][0]
        return title[:80] + '...' if len(title) > 80 else title
    return 'Unknown'


def filter_by_type(records, keep_types, remove_types):
    """
    Filter records to keep only specified article types

    Args:
        records: List of record dicts
        keep_types: List of article types to keep
        remove_types: List of article types to explicitly remove

    Returns:
        Tuple of (filtered_records, stats_dict)
    """
    filtered_records = []
    kept_types = Counter()
    removed_types = Counter()
    no_type_count = 0
    removed_examples = defaultdict(list)

    for record in records:
        article_type = get_type_from_record(record)

        if not article_type:
            # No type specified - keep it but count
            filtered_records.append(record)
            no_type_count += 1
            continue

        if article_type in keep_types:
            # Explicitly keep
            filtered_records.append(record)
            kept_types[article_type] += 1
        elif article_type in remove_types:
            # Explicitly remove
            removed_types[article_type] += 1
            if len(removed_examples[article_type]) < 3:
                removed_examples[article_type].append(get_title_from_record(record))
        else:
            # Unknown type - keep it for safety but count
            filtered_records.append(record)
            kept_types[article_type] += 1

    stats = {
        'kept': kept_types,
        'removed': removed_types,
        'no_type': no_type_count,
        'examples': removed_examples
    }

    return filtered_records, stats


def filter_file(input_file, output_file, keep_types, remove_types):
    """
    Filter a single RIS file by article type

    Args:
        input_file: Path to input RIS file
        output_file: Path to output RIS file
        keep_types: List of types to keep
        remove_types: List of types to remove

    Returns:
        Statistics dict
    """
    print(f"\nProcessing: {input_file.name}")

    # Parse records
    records = parse_ris_file(input_file)
    records_before = len(records)
    print(f"  Records before filtering: {records_before}")

    # Filter by type
    filtered_records, stats = filter_by_type(records, keep_types, remove_types)
    records_after = len(filtered_records)
    records_removed = records_before - records_after

    print(f"  Records after filtering:  {records_after}")
    print(f"  Records removed:          {records_removed} ({(records_removed/records_before*100) if records_before > 0 else 0:.1f}%)")

    # Show breakdown
    if stats['kept']:
        print(f"\n  Kept types:")
        for type_name, count in stats['kept'].most_common():
            type_label = 'Journal Article' if type_name == 'JOUR' else 'Conference Paper' if type_name == 'CONF' else type_name
            print(f"    - {type_label:<25} {count:>5} records")

    if stats['removed']:
        print(f"\n  Removed types:")
        for type_name, count in stats['removed'].most_common():
            type_label = 'Book' if type_name == 'BOOK' else 'Book Chapter' if type_name == 'CHAP' else type_name
            print(f"    - {type_label:<25} {count:>5} records")

    if stats['no_type'] > 0:
        print(f"\n  Records without type (kept): {stats['no_type']}")

    # Write filtered records
    if filtered_records:
        write_ris_file(filtered_records, output_file)
        print(f"\n  [OK] Saved: {output_file.name}")
    else:
        print(f"\n  [WARNING] No matching records - output file not created")

    # Show examples of removed records
    if stats['examples']:
        print(f"\n  Example removed records (showing first 2 per type):")
        for type_name, examples in stats['examples'].items():
            type_label = 'Book' if type_name == 'BOOK' else 'Book Chapter' if type_name == 'CHAP' else type_name
            print(f"    {type_label}:")
            for example in examples[:2]:
                print(f"      - {example}")

    return {
        'before': records_before,
        'after': records_after,
        'removed': records_removed,
        'kept_types': stats['kept'],
        'removed_types': stats['removed'],
        'no_type': stats['no_type']
    }


def filter_directory(input_dir, output_dir, keep_types, remove_types):
    """
    Filter all RIS files in a directory

    Args:
        input_dir: Input directory path
        output_dir: Output directory path
        keep_types: List of types to keep
        remove_types: List of types to remove
    """
    print("="*70)
    print("RIS Article Type Filter")
    print("="*70)
    print(f"\nTypes to KEEP:")
    for type_code in keep_types:
        type_label = 'Journal Article (JOUR)' if type_code == 'JOUR' else 'Conference Paper (CONF)' if type_code == 'CONF' else type_code
        print(f"  - {type_label}")

    print(f"\nTypes to REMOVE:")
    for type_code in remove_types:
        type_label = 'Book (BOOK)' if type_code == 'BOOK' else 'Book Chapter (CHAP)' if type_code == 'CHAP' else type_code
        print(f"  - {type_label}")

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
    all_kept_types = Counter()
    all_removed_types = Counter()
    file_stats = []

    for ris_file in sorted(ris_files):
        output_file = output_path / f"{ris_file.stem}_type_filtered.ris"
        stats = filter_file(ris_file, output_file, keep_types, remove_types)

        total_before += stats['before']
        total_after += stats['after']
        all_kept_types.update(stats['kept_types'])
        all_removed_types.update(stats['removed_types'])

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
    print(f"  Total records removed:     {total_before - total_after:>6} ({((total_before-total_after)/total_before*100) if total_before > 0 else 0:.1f}%)")
    print(f"  Retention rate:            {(total_after/total_before*100) if total_before > 0 else 0:.1f}%")

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

    # Kept types distribution
    if all_kept_types:
        print(f"\nKEPT TYPES DISTRIBUTION:")
        print(f"{'-'*70}")
        for type_code, count in all_kept_types.most_common():
            type_label = 'Journal Article' if type_code == 'JOUR' else 'Conference Paper' if type_code == 'CONF' else type_code
            print(f"  {type_label:<60} {count:>6}")
        print(f"{'-'*70}")
        print(f"  {'TOTAL KEPT':<60} {sum(all_kept_types.values()):>6}")

    # Removed types distribution
    if all_removed_types:
        print(f"\nREMOVED TYPES DISTRIBUTION:")
        print(f"{'-'*70}")
        for type_code, count in all_removed_types.most_common():
            type_label = 'Book' if type_code == 'BOOK' else 'Book Chapter' if type_code == 'CHAP' else type_code
            print(f"  {type_label:<60} {count:>6}")
        print(f"{'-'*70}")
        print(f"  {'TOTAL REMOVED':<60} {sum(all_removed_types.values()):>6}")

    print(f"\nFiltered files saved to: {output_dir}/")
    for stat in file_stats:
        if stat['after'] > 0:
            filename = stat['name'].replace('.ris', '_type_filtered.ris')
            print(f"  - {filename:<55} {stat['after']:>6} records")


def main():
    """Main execution function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python Step5_filter_by_type.py <input_file_or_directory> [output_directory]")
        print("\nExamples:")
        print("  python Step5_filter_by_type.py filtered_output/ final_output/")
        print("  python Step5_filter_by_type.py input.ris output_type_filtered.ris")
        print("\nKeeps:")
        print("  - Journal articles (JOUR)")
        print("  - Conference papers (CONF)")
        print("\nRemoves:")
        print("  - Books (BOOK)")
        print("  - Book chapters (CHAP)")
        return

    input_path = sys.argv[1]

    if not os.path.exists(input_path):
        print(f"Error: Input path '{input_path}' not found!")
        return

    if os.path.isdir(input_path):
        # Directory mode
        output_dir = sys.argv[2] if len(sys.argv) > 2 else 'final_output'
        filter_directory(input_path, output_dir, KEEP_TYPES, REMOVE_TYPES)
    else:
        # Single file mode
        output_file = sys.argv[2] if len(sys.argv) > 2 else input_path.replace('.ris', '_type_filtered.ris')
        input_file = Path(input_path)
        output_file = Path(output_file)

        print("="*70)
        print("RIS Article Type Filter")
        print("="*70)
        print(f"\nTypes to KEEP:")
        for type_code in KEEP_TYPES:
            type_label = 'Journal Article (JOUR)' if type_code == 'JOUR' else 'Conference Paper (CONF)' if type_code == 'CONF' else type_code
            print(f"  - {type_label}")

        print(f"\nTypes to REMOVE:")
        for type_code in REMOVE_TYPES:
            type_label = 'Book (BOOK)' if type_code == 'BOOK' else 'Book Chapter (CHAP)' if type_code == 'CHAP' else type_code
            print(f"  - {type_label}")

        filter_file(input_file, output_file, KEEP_TYPES, REMOVE_TYPES)


if __name__ == "__main__":
    main()
