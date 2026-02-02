#!/usr/bin/env python3
"""
EndNote (ENW) to RIS Converter
Converts EndNote .enw files to RIS (Research Information Systems) format
"""

import os
import sys
from pathlib import Path


# Mapping from EndNote tags to RIS tags
ENW_TO_RIS_MAP = {
    '%0': 'TY',   # Type of reference
    '%T': 'TI',   # Title
    '%A': 'AU',   # Author
    '%D': 'PY',   # Date/Year
    '%B': 'T2',   # Book title / Conference name
    '%J': 'JO',   # Journal name
    '%V': 'VL',   # Volume
    '%N': 'IS',   # Issue
    '%P': 'SP',   # Pages (will be split into SP/EP)
    '%@': 'SN',   # ISBN/ISSN
    '%U': 'UR',   # URL
    '%R': 'DO',   # DOI
    '%K': 'KW',   # Keywords
    '%X': 'AB',   # Abstract
    '%C': 'CY',   # City/Location
    '%I': 'PB',   # Publisher
    '%S': 'T3',   # Series title
    '%E': 'ED',   # Editor
    '%Y': 'T2',   # Secondary title
}

# Mapping EndNote reference types to RIS types
TYPE_MAP = {
    'Journal Article': 'JOUR',
    'Conference Paper': 'CONF',
    'Conference Proceedings': 'CONF',
    'Book': 'BOOK',
    'Book Section': 'CHAP',
    'Thesis': 'THES',
    'Report': 'RPRT',
    'Magazine Article': 'MGZN',
    'Newspaper Article': 'NEWS',
    'Generic': 'GEN',
}


def parse_pages(page_str):
    """Parse page string into start and end pages"""
    if not page_str:
        return '', ''

    # Handle range with en-dash or hyphen
    for separator in ['–', '-', '—']:
        if separator in page_str:
            parts = page_str.split(separator)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ''

    return page_str.strip(), ''


def convert_type(enw_type):
    """Convert EndNote type to RIS type"""
    return TYPE_MAP.get(enw_type, 'JOUR')


def parse_keywords(keyword_str):
    """Parse comma-separated keywords"""
    if not keyword_str:
        return []
    return [kw.strip() for kw in keyword_str.split(',')]


def convert_enw_to_ris(enw_file, output_file):
    """
    Convert EndNote .enw file to RIS format

    Args:
        enw_file: Path to input .enw file
        output_file: Path to output .ris file
    """
    print(f"Reading: {enw_file}")

    try:
        with open(enw_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split into individual records (separated by blank lines)
        records = content.split('\n\n')
        records = [r.strip() for r in records if r.strip()]

        print(f"Found {len(records)} records")

        with open(output_file, 'w', encoding='utf-8') as f:
            for record in records:
                lines = record.split('\n')

                # Storage for current record
                current_record = {}
                current_tag = None

                # Parse EndNote record
                for line in lines:
                    if line.startswith('%'):
                        # New tag
                        if len(line) < 2:
                            continue

                        tag = line[:2]
                        value = line[2:].strip() if len(line) > 2 else ''

                        current_tag = tag

                        if tag not in current_record:
                            current_record[tag] = []
                        current_record[tag].append(value)
                    elif current_tag:
                        # Continuation of previous tag
                        current_record[current_tag][-1] += ' ' + line.strip()

                # Convert to RIS
                # Type
                ref_type = current_record.get('%0', ['Journal Article'])[0]
                ris_type = convert_type(ref_type)
                f.write(f"TY  - {ris_type}\n")

                # Process all fields
                for enw_tag, values in current_record.items():
                    ris_tag = ENW_TO_RIS_MAP.get(enw_tag)

                    if not ris_tag or enw_tag == '%0':  # Skip type, already processed
                        continue

                    for value in values:
                        if not value:
                            continue

                        # Special handling for pages
                        if enw_tag == '%P':
                            start_page, end_page = parse_pages(value)
                            if start_page:
                                f.write(f"SP  - {start_page}\n")
                            if end_page:
                                f.write(f"EP  - {end_page}\n")

                        # Special handling for keywords
                        elif enw_tag == '%K':
                            keywords = parse_keywords(value)
                            for kw in keywords:
                                if kw:
                                    f.write(f"KW  - {kw}\n")

                        # Special handling for conference/book title
                        elif enw_tag == '%B':
                            if ris_type == 'CONF':
                                f.write(f"T2  - {value}\n")  # Conference name
                            else:
                                f.write(f"BT  - {value}\n")  # Book title

                        # Regular fields
                        else:
                            f.write(f"{ris_tag}  - {value}\n")

                # End of reference
                f.write("ER  - \n\n")

        print(f"[OK] Converted to: {output_file}")
        return True

    except Exception as e:
        print(f"Error converting {enw_file}: {e}")
        import traceback
        traceback.print_exc()
        return False


def convert_directory(input_dir, output_dir=None):
    """
    Convert all .enw files in a directory

    Args:
        input_dir: Directory containing .enw files
        output_dir: Output directory (defaults to input_dir)
    """
    input_path = Path(input_dir)

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = input_path

    enw_files = list(input_path.glob('*.enw'))

    if not enw_files:
        print(f"No .enw files found in {input_dir}")
        return

    print(f"\n{'='*70}")
    print(f"EndNote to RIS Converter")
    print(f"{'='*70}")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_path}")
    print(f"Found {len(enw_files)} .enw files\n")

    success_count = 0
    for enw_file in enw_files:
        ris_filename = enw_file.stem + '.ris'
        ris_file = output_path / ris_filename

        if convert_enw_to_ris(enw_file, ris_file):
            success_count += 1

    print(f"\n{'='*70}")
    print(f"Conversion Summary")
    print(f"{'='*70}")
    print(f"Total files: {len(enw_files)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(enw_files) - success_count}")


def main():
    """Main execution function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Convert single file:     python convert_enw_to_ris.py <input.enw> [output.ris]")
        print("  Convert directory:       python convert_enw_to_ris.py <input_directory> [output_directory]")
        print("\nExample:")
        print("  python convert_enw_to_ris.py output/acm_output/")
        return

    input_path = sys.argv[1]

    if os.path.isdir(input_path):
        # Directory mode
        output_dir = sys.argv[2] if len(sys.argv) > 2 else None
        convert_directory(input_path, output_dir)
    else:
        # Single file mode
        output_file = sys.argv[2] if len(sys.argv) > 2 else input_path.replace('.enw', '.ris')
        convert_enw_to_ris(input_path, output_file)


if __name__ == "__main__":
    main()
