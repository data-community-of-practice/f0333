#!/usr/bin/env python3
"""
Master Converter Script
Converts all literature data (PubMed, Scopus, ACM) to RIS format
"""

import os
import sys
from pathlib import Path

# Import the individual converters
from convert_pubmed_to_ris import convert_directory as convert_pubmed_dir
from convert_scopus_to_ris import convert_directory as convert_scopus_dir
from convert_enw_to_ris import convert_directory as convert_enw_dir


def convert_all(output_base_dir='output'):
    """
    Convert all literature data files to RIS format

    Args:
        output_base_dir: Base directory containing output folders
    """
    print("="*70)
    print("Literature Data to RIS Converter")
    print("="*70)
    print(f"\nProcessing directory: {output_base_dir}\n")

    base_path = Path(output_base_dir)

    if not base_path.exists():
        print(f"Error: Directory {output_base_dir} not found!")
        return False

    # Track conversions
    conversions = []

    # 1. Convert PubMed JSON files
    pubmed_dir = base_path / 'pubmed_output'
    if pubmed_dir.exists():
        print("\n" + "="*70)
        print("Converting PubMed JSON files")
        print("="*70)
        convert_pubmed_dir(str(pubmed_dir))
        conversions.append(('PubMed', pubmed_dir))
    else:
        print(f"\nSkipping PubMed (directory not found: {pubmed_dir})")

    # 2. Convert Scopus JSON files
    scopus_dir = base_path / 'Scopus'
    if scopus_dir.exists():
        print("\n" + "="*70)
        print("Converting Scopus JSON files")
        print("="*70)
        convert_scopus_dir(str(scopus_dir))
        conversions.append(('Scopus', scopus_dir))
    else:
        print(f"\nSkipping Scopus (directory not found: {scopus_dir})")

    # 3. Convert ACM EndNote files
    acm_dir = base_path / 'acm_output'
    if acm_dir.exists():
        print("\n" + "="*70)
        print("Converting ACM EndNote files")
        print("="*70)
        convert_enw_dir(str(acm_dir))
        conversions.append(('ACM', acm_dir))
    else:
        print(f"\nSkipping ACM (directory not found: {acm_dir})")

    # Final summary
    print("\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)

    if conversions:
        print(f"\nSuccessfully processed {len(conversions)} source(s):")
        for source, path in conversions:
            ris_files = list(path.glob('*.ris'))
            print(f"  - {source}: {len(ris_files)} RIS files created in {path}")

        print("\nAll RIS files are saved in their respective source directories:")
        print("  - PubMed RIS files: output/pubmed_output/*.ris")
        print("  - Scopus RIS files: output/Scopus/*.ris")
        print("  - ACM RIS files: output/acm_output/*.ris")

        print("\nYou can now import these RIS files into reference management software")
        print("such as Zotero, Mendeley, EndNote, or RefWorks.")
    else:
        print("\nNo conversions performed. Please check your directory structure.")

    return True


def main():
    """Main execution function"""
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        output_dir = 'output'

    print(f"\nUsing output directory: {output_dir}")

    convert_all(output_dir)


if __name__ == "__main__":
    main()
