#!/usr/bin/env python3
"""
RIS Methodology Filter
Filters RIS files to keep only methodological/technical papers
Keeps: Papers with method/evaluation signals (ML systems, evaluation studies)
Removes: Audit/quality studies, training, billing, qualitative, guidelines
"""

import os
import sys
import re
from pathlib import Path
from collections import defaultdict, Counter


# Methods / system signals (informatics)
METHOD_PATTERNS = [
    r"\b(machine learning|deep learning|neural network|neural|transformer|bert|lstm|bilstm|cnn|rnn)\b",
    r"\b(nlp|natural language processing|language model|large language model|llm|gpt)\b",
    r"\b(classifier|classification|predictor|prediction|model|algorithm|pipeline|framework|system|architecture)\b",
    r"\b(multi[- ]label|hierarch(?:y|ical)|extreme multi[- ]label|xmlc)\b",
    r"\b(weak supervision|distant supervision|self[- ]supervised|semi[- ]supervised)\b",
    r"\b(retrieval[- ]augmented|rag|retrieval|rerank|prompt|prompting|in[- ]context)\b",
    r"\b(embedding|representation learning|fine[- ]tune|finetune|pretrain|pre[- ]train)\b",
    r"\b(ontology|knowledge graph|knowledge[- ]based|snomed|umls)\b",
    r"\b(rule[- ]based|heuristic|dictionary[- ]based|pattern matching|regular expression)\b",
]

# Evaluation signals (metrics + benchmarking language)
EVAL_PATTERNS = [
    # metrics
    r"\b(f1|micro[- ]f1|macro[- ]f1|precision|recall|accuracy)\b",
    r"\b(auc|auroc|auprc|area under the curve)\b",
    r"\b(hamming loss|exact match|top[- ]k|p@k|r@k|precision@k|recall@k)\b",
    r"\b(sensitivity|specificity|ppv|npv)\b",
    # evaluation language
    r"\b(evaluat(?:e|ed|ion)|performance|benchmark|baseline|compare|comparison)\b",
    r"\b(cross[- ]validation|cross validation|train(?:ing)? set|test set|validation set|held[- ]out|external validation)\b",
    r"\b(ablation|error analysis|confusion matrix|statistical significance)\b",
]

# Negative signals (non-method focus)
NEG_PATTERNS = [
    r"\b(audit|chart review|manual review|coding quality|coding accuracy)\b",
    r"\b(inter[- ]rater|interrater|kappa|agreement)\b",
    r"\b(coder training|coding training|education program|workforce)\b",
    r"\b(billing|reimbursement|drg|claims processing|administrative claims)\b",
    r"\b(qualitative|interview|focus group|survey|implementation study|workflow)\b",
    r"\b(guideline|policy|position paper|editorial|commentary)\b",
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


def get_text_content(record):
    """
    Extract title, abstract, and keywords from record

    Args:
        record: Record dict

    Returns:
        Dict with 'title', 'abstract', 'keywords' (all lowercase)
    """
    title = ' '.join(record.get('TI', [])).lower()
    abstract = ' '.join(record.get('AB', [])).lower()
    keywords = ' '.join(record.get('KW', [])).lower()

    return {
        'title': title,
        'abstract': abstract,
        'keywords': keywords,
        'all': f"{title} {abstract} {keywords}"
    }


def check_patterns(text, patterns):
    """
    Check if any pattern matches the text

    Args:
        text: Text to search (should be lowercase)
        patterns: List of regex patterns

    Returns:
        List of matched patterns
    """
    matches = []
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            matches.append(pattern)
    return matches


def should_keep_record(record):
    """
    Determine if record should be kept based on methodology signals

    Args:
        record: Record dict

    Returns:
        Tuple of (keep: bool, reason: str, details: dict)
    """
    text_dict = get_text_content(record)
    all_text = text_dict['all']

    # Check for positive signals (method or evaluation)
    method_matches = check_patterns(all_text, METHOD_PATTERNS)
    eval_matches = check_patterns(all_text, EVAL_PATTERNS)

    # Check for negative signals
    neg_matches = check_patterns(all_text, NEG_PATTERNS)

    has_method = len(method_matches) > 0
    has_eval = len(eval_matches) > 0
    has_negative = len(neg_matches) > 0

    details = {
        'method_count': len(method_matches),
        'eval_count': len(eval_matches),
        'neg_count': len(neg_matches),
        'method_matches': method_matches[:3],  # Store first 3 for logging
        'eval_matches': eval_matches[:3],
        'neg_matches': neg_matches[:3]
    }

    # Decision logic:
    # REMOVE if negative signals present
    if has_negative:
        return False, "Non-methodological focus (audit/billing/qualitative/guideline)", details

    # KEEP if has method or evaluation signals
    if has_method or has_eval:
        if has_method and has_eval:
            return True, "Strong methodology signals (method + evaluation)", details
        elif has_method:
            return True, "Method signals present", details
        else:
            return True, "Evaluation signals present", details

    # REMOVE if no signals
    return False, "No methodology or evaluation signals", details


def get_title_from_record(record):
    """
    Extract title from record for logging

    Args:
        record: Record dict

    Returns:
        Title string (truncated to 100 chars)
    """
    if 'TI' in record and record['TI']:
        title = record['TI'][0]
        return title[:100] + '...' if len(title) > 100 else title
    return 'Unknown'


def filter_by_methodology(records):
    """
    Filter records to keep only methodological/technical papers

    Args:
        records: List of record dicts

    Returns:
        Tuple of (filtered_records, stats_dict)
    """
    filtered_records = []
    kept_reasons = Counter()
    removed_reasons = Counter()
    examples_kept = defaultdict(list)
    examples_removed = defaultdict(list)

    for record in records:
        keep, reason, details = should_keep_record(record)
        title = get_title_from_record(record)

        if keep:
            filtered_records.append(record)
            kept_reasons[reason] += 1
            if len(examples_kept[reason]) < 2:
                examples_kept[reason].append({
                    'title': title,
                    'method_count': details['method_count'],
                    'eval_count': details['eval_count']
                })
        else:
            removed_reasons[reason] += 1
            if len(examples_removed[reason]) < 2:
                examples_removed[reason].append({
                    'title': title,
                    'neg_count': details['neg_count']
                })

    stats = {
        'kept_reasons': kept_reasons,
        'removed_reasons': removed_reasons,
        'examples_kept': examples_kept,
        'examples_removed': examples_removed
    }

    return filtered_records, stats


def filter_file(input_file, output_file):
    """
    Filter a single RIS file by methodology

    Args:
        input_file: Path to input RIS file
        output_file: Path to output RIS file

    Returns:
        Statistics dict
    """
    print(f"\nProcessing: {input_file.name}")

    # Parse records
    records = parse_ris_file(input_file)
    records_before = len(records)
    print(f"  Records before filtering: {records_before}")

    # Filter by methodology
    filtered_records, stats = filter_by_methodology(records)
    records_after = len(filtered_records)
    records_removed = records_before - records_after

    print(f"  Records after filtering:  {records_after}")
    print(f"  Records removed:          {records_removed} ({(records_removed/records_before*100) if records_before > 0 else 0:.1f}%)")

    # Show breakdown
    if stats['kept_reasons']:
        print(f"\n  Reasons for keeping:")
        for reason, count in stats['kept_reasons'].most_common():
            print(f"    - {reason:<55} {count:>5} records")

    if stats['removed_reasons']:
        print(f"\n  Reasons for removing:")
        for reason, count in stats['removed_reasons'].most_common():
            print(f"    - {reason:<55} {count:>5} records")

    # Write filtered records
    if filtered_records:
        write_ris_file(filtered_records, output_file)
        print(f"\n  [OK] Saved: {output_file.name}")
    else:
        print(f"\n  [WARNING] No matching records - output file not created")

    # Show examples
    if stats['examples_kept']:
        print(f"\n  Example KEPT records (showing first 2 per reason):")
        for reason, examples in stats['examples_kept'].items():
            print(f"    {reason}:")
            for ex in examples:
                print(f"      - {ex['title']}")
                print(f"        (method signals: {ex['method_count']}, eval signals: {ex['eval_count']})")

    if stats['examples_removed']:
        print(f"\n  Example REMOVED records (showing first 2 per reason):")
        for reason, examples in stats['examples_removed'].items():
            print(f"    {reason}:")
            for ex in examples:
                print(f"      - {ex['title']}")

    return {
        'before': records_before,
        'after': records_after,
        'removed': records_removed,
        'kept_reasons': stats['kept_reasons'],
        'removed_reasons': stats['removed_reasons']
    }


def filter_directory(input_dir, output_dir):
    """
    Filter all RIS files in a directory

    Args:
        input_dir: Input directory path
        output_dir: Output directory path
    """
    print("="*70)
    print("RIS Methodology Filter")
    print("="*70)
    print("\nKEEPS papers with:")
    print("  - Method signals (ML, NLP, algorithms, systems)")
    print("  - Evaluation signals (metrics, benchmarking, validation)")
    print("\nREMOVES papers with:")
    print("  - Audit/quality studies")
    print("  - Training/education")
    print("  - Billing/administrative")
    print("  - Qualitative/implementation studies")
    print("  - Guidelines/commentaries")

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
    all_kept_reasons = Counter()
    all_removed_reasons = Counter()
    file_stats = []

    for ris_file in sorted(ris_files):
        output_file = output_path / f"{ris_file.stem}_methodology_filtered.ris"
        stats = filter_file(ris_file, output_file)

        total_before += stats['before']
        total_after += stats['after']
        all_kept_reasons.update(stats['kept_reasons'])
        all_removed_reasons.update(stats['removed_reasons'])

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

    # Kept reasons distribution
    if all_kept_reasons:
        print(f"\nREASONS FOR KEEPING RECORDS:")
        print(f"{'-'*70}")
        for reason, count in all_kept_reasons.most_common():
            print(f"  {reason:<60} {count:>6}")
        print(f"{'-'*70}")
        print(f"  {'TOTAL KEPT':<60} {sum(all_kept_reasons.values()):>6}")

    # Removed reasons distribution
    if all_removed_reasons:
        print(f"\nREASONS FOR REMOVING RECORDS:")
        print(f"{'-'*70}")
        for reason, count in all_removed_reasons.most_common():
            print(f"  {reason:<60} {count:>6}")
        print(f"{'-'*70}")
        print(f"  {'TOTAL REMOVED':<60} {sum(all_removed_reasons.values()):>6}")

    print(f"\nFiltered files saved to: {output_dir}/")
    for stat in file_stats:
        if stat['after'] > 0:
            filename = stat['name'].replace('.ris', '_methodology_filtered.ris')
            print(f"  - {filename:<55} {stat['after']:>6} records")


def main():
    """Main execution function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python Step7_filter_by_methodology.py <input_file_or_directory> [output_directory]")
        print("\nExamples:")
        print("  python Step7_filter_by_methodology.py curated_output/ refined_output/")
        print("  python Step7_filter_by_methodology.py input.ris output_methodology_filtered.ris")
        print("\nKeeps:")
        print("  - Papers with method/system signals (ML, NLP, algorithms)")
        print("  - Papers with evaluation signals (metrics, benchmarking)")
        print("\nRemoves:")
        print("  - Audit/quality studies")
        print("  - Training/education papers")
        print("  - Billing/administrative papers")
        print("  - Qualitative/implementation studies")
        print("  - Guidelines/commentaries")
        return

    input_path = sys.argv[1]

    if not os.path.exists(input_path):
        print(f"Error: Input path '{input_path}' not found!")
        return

    if os.path.isdir(input_path):
        # Directory mode
        output_dir = sys.argv[2] if len(sys.argv) > 2 else 'refined_output'
        filter_directory(input_path, output_dir)
    else:
        # Single file mode
        output_file = sys.argv[2] if len(sys.argv) > 2 else input_path.replace('.ris', '_methodology_filtered.ris')
        input_file = Path(input_path)
        output_file = Path(output_file)

        print("="*70)
        print("RIS Methodology Filter")
        print("="*70)
        print("\nKEEPS papers with:")
        print("  - Method signals (ML, NLP, algorithms, systems)")
        print("  - Evaluation signals (metrics, benchmarking, validation)")
        print("\nREMOVES papers with:")
        print("  - Audit/quality studies")
        print("  - Training/education")
        print("  - Billing/administrative")
        print("  - Qualitative/implementation studies")
        print("  - Guidelines/commentaries")

        filter_file(input_file, output_file)


if __name__ == "__main__":
    main()
