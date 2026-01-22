#!/usr/bin/env python3
"""
RIS Paper Tagger
Tags papers based on method families, challenges, datasets, and time periods
Produces tagged RIS files and analysis CSV
"""

import os
import sys
import re
import csv
from pathlib import Path
from collections import defaultdict, Counter
from typing import List, Tuple, Dict, Any


# Phase (method family) signals
PHASE_RULES: List[Tuple[str, re.Pattern]] = [
    ("LLM_RAG_XAI", re.compile(r"\b(llm|large language model|gpt|chatgpt|prompt|rag|retrieval[- ]augmented|agent)\b", re.I)),
    ("TRANSFORMER", re.compile(r"\b(transformer|bert|roberta|deberta|longformer|bigbird|sparse attention)\b", re.I)),
    ("DEEP_CNN_RNN", re.compile(r"\b(cnn|convolutional|rnn|lstm|bilstm|gru|attention mechanism)\b", re.I)),
    ("CLASSICAL_ML", re.compile(r"\b(svm|support vector|logistic regression|naive bayes|random forest|xgboost|crf|hmm)\b", re.I)),
    ("RULE_BASED", re.compile(r"\b(rule[- ]based|heuristic|dictionary[- ]based|pattern matching|regular expression)\b", re.I)),
]

# Challenge / dimension signals
CHALLENGE_RULES: List[Tuple[str, re.Pattern]] = [
    ("HIERARCHY", re.compile(r"\b(hierarch(y|ical)|taxonomy|tree[- ]structured|parent[- ]child)\b", re.I)),
    ("RARE_LABELS", re.compile(r"\b(rare (labels?|codes?)|long[- ]tail|few[- ]shot|low[- ]resource|data sparsity|imbalanced)\b", re.I)),
    ("LONG_TEXT", re.compile(r"\b(long (documents?|notes?)|long[- ]text|sequence length|truncation|segmentation|chunking)\b", re.I)),
    ("EXTREME_MULTILABEL", re.compile(r"\b(extreme multi[- ]label|xmlc|multi[- ]label)\b", re.I)),
    ("COOCCURRENCE_RULES", re.compile(r"\b(co[- ]occurr|combination rules|code (dependencies|constraints)|post[- ]coordination)\b", re.I)),
    ("MAPPING_INTEROP", re.compile(r"\b(map(ping)?|crosswalk|interoperab|icd[- ]9|icd[- ]10|icd[- ]11|version (transition|mapping))\b", re.I)),
    ("KNOWLEDGE_AUG", re.compile(r"\b(ontology|knowledge graph|umls|snomed|concept normalization|lexical knowledge)\b", re.I)),
    ("EXPLAINABILITY", re.compile(r"\b(explainab|interpretab|lime|shap|integrated gradients|rationale)\b", re.I)),
]

# Dataset signals
DATASET_RULES: List[Tuple[str, re.Pattern]] = [
    ("MIMIC", re.compile(r"\b(mimic[- ]?iii|mimic[- ]?iv|mimic)\b", re.I)),
    ("EICU", re.compile(r"\b(eicu)\b", re.I)),
    ("UCSF", re.compile(r"\b(ucsf)\b", re.I)),
    ("CLAIMS", re.compile(r"\b(claims data|administrative claims)\b", re.I)),
]

# Metric/evaluation signals
METRIC_PAT = re.compile(
    r"\b(f1|micro[- ]?f1|macro[- ]?f1|precision|recall|accuracy|auc|auroc|auprc|hamming loss|exact match|p@k|r@k|top[- ]?k)\b",
    re.I
)

# Novelty/contribution language
NOVELTY_PAT = re.compile(r"\b(we propose|we present|a novel|novel|new framework|new model|first (to|study)|introduc(e|es) a)\b", re.I)

# Coding task specificity
CODING_TASK_PAT = re.compile(r"\b(code assignment|icd coding|clinical coding|medical coding|auto[- ]coding|computer[- ]assisted)\b", re.I)


def year_bucket(y: str) -> str:
    """
    Convert year to bucket

    Args:
        y: Year string

    Returns:
        Year bucket string
    """
    if not y:
        return "UNKNOWN"
    try:
        yi = int(y)
        if yi <= 2011:
            return "pre2012"
        if yi <= 2016:
            return "2012_2016"
        if yi <= 2019:
            return "2017_2019"
        if yi <= 2022:
            return "2020_2022"
        return "2023_plus"
    except (ValueError, TypeError):
        return "UNKNOWN"


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


def get_text_content(record: Dict) -> str:
    """
    Extract title, abstract, and keywords from record

    Args:
        record: Record dict

    Returns:
        Combined text (lowercase)
    """
    title = ' '.join(record.get('TI', []))
    abstract = ' '.join(record.get('AB', []))
    keywords = ' '.join(record.get('KW', []))
    return f"{title} {abstract} {keywords}".lower()


def get_year(record: Dict) -> str:
    """
    Extract publication year from record

    Args:
        record: Record dict

    Returns:
        Year string or empty string
    """
    # Try PY (Publication Year) tag first
    if 'PY' in record and record['PY']:
        year_str = record['PY'][0]
        # Extract first 4 digits
        match = re.search(r'\d{4}', year_str)
        if match:
            return match.group(0)

    # Try DA (Date) tag
    if 'DA' in record and record['DA']:
        date_str = record['DA'][0]
        match = re.search(r'\d{4}', date_str)
        if match:
            return match.group(0)

    return ""


def apply_tags(record: Dict) -> Dict[str, Any]:
    """
    Apply all tagging rules to a record

    Args:
        record: Record dict

    Returns:
        Dict with tag results
    """
    text = get_text_content(record)
    year = get_year(record)
    title = ' '.join(record.get('TI', [''])).lower()
    abstract = ' '.join(record.get('AB', [''])).lower()

    tags = {
        'year': year,
        'year_bucket': year_bucket(year),
        'phases': [],
        'challenges': [],
        'datasets': [],
        'has_metrics': False,
        'has_novelty': False,
        'has_coding_task': False,
    }

    # Phase tags
    for phase_name, pattern in PHASE_RULES:
        if pattern.search(text):
            tags['phases'].append(phase_name)

    # Challenge tags
    for challenge_name, pattern in CHALLENGE_RULES:
        if pattern.search(text):
            tags['challenges'].append(challenge_name)

    # Dataset tags
    for dataset_name, pattern in DATASET_RULES:
        if pattern.search(text):
            tags['datasets'].append(dataset_name)

    # Metric presence
    tags['has_metrics'] = bool(METRIC_PAT.search(text))

    # Novelty language
    tags['has_novelty'] = bool(NOVELTY_PAT.search(text))

    # Coding task specificity
    tags['has_coding_task'] = bool(abstract and CODING_TASK_PAT.search(text))

    return tags


def add_tags_to_record(record: Dict, tags: Dict[str, Any]) -> Dict:
    """
    Add tags to record as N1 notes

    Args:
        record: Record dict
        tags: Tags dict

    Returns:
        Modified record with tags
    """
    # Create tag summary
    tag_lines = []

    if tags['year_bucket'] != 'UNKNOWN':
        tag_lines.append(f"PERIOD: {tags['year_bucket']}")

    if tags['phases']:
        tag_lines.append(f"METHODS: {', '.join(tags['phases'])}")

    if tags['challenges']:
        tag_lines.append(f"CHALLENGES: {', '.join(tags['challenges'])}")

    if tags['datasets']:
        tag_lines.append(f"DATASETS: {', '.join(tags['datasets'])}")

    flags = []
    if tags['has_metrics']:
        flags.append("HAS_METRICS")
    if tags['has_novelty']:
        flags.append("NOVEL")
    if tags['has_coding_task']:
        flags.append("CODING_TASK")

    if flags:
        tag_lines.append(f"FLAGS: {', '.join(flags)}")

    # Add to N1 field
    if tag_lines:
        tag_text = "[AUTO_TAGS] " + " | ".join(tag_lines)
        if 'N1' not in record:
            record['N1'] = []
        record['N1'].append(tag_text)

    return record


def get_title_from_record(record: Dict) -> str:
    """
    Extract title from record

    Args:
        record: Record dict

    Returns:
        Title string (truncated to 80 chars)
    """
    if 'TI' in record and record['TI']:
        title = record['TI'][0]
        return title[:80] + '...' if len(title) > 80 else title
    return 'Unknown'


def get_doi_from_record(record: Dict) -> str:
    """
    Extract DOI from record

    Args:
        record: Record dict

    Returns:
        DOI string or empty
    """
    if 'DO' in record and record['DO']:
        return record['DO'][0]
    return ''


def tag_file(input_file: Path, output_file: Path, csv_writer=None) -> Dict[str, Any]:
    """
    Tag a single RIS file

    Args:
        input_file: Path to input RIS file
        output_file: Path to output RIS file
        csv_writer: Optional CSV writer for analysis

    Returns:
        Statistics dict
    """
    print(f"\nProcessing: {input_file.name}")

    # Parse records
    records = parse_ris_file(input_file)
    total_records = len(records)
    print(f"  Total records: {total_records}")

    # Tag records
    tagged_records = []
    stats = {
        'total': total_records,
        'phase_counts': Counter(),
        'challenge_counts': Counter(),
        'dataset_counts': Counter(),
        'year_bucket_counts': Counter(),
        'metrics_count': 0,
        'novelty_count': 0,
        'coding_task_count': 0,
    }

    for record in records:
        tags = apply_tags(record)

        # Update statistics
        for phase in tags['phases']:
            stats['phase_counts'][phase] += 1
        for challenge in tags['challenges']:
            stats['challenge_counts'][challenge] += 1
        for dataset in tags['datasets']:
            stats['dataset_counts'][dataset] += 1
        stats['year_bucket_counts'][tags['year_bucket']] += 1
        if tags['has_metrics']:
            stats['metrics_count'] += 1
        if tags['has_novelty']:
            stats['novelty_count'] += 1
        if tags['has_coding_task']:
            stats['coding_task_count'] += 1

        # Add tags to record
        tagged_record = add_tags_to_record(record.copy(), tags)
        tagged_records.append(tagged_record)

        # Write to CSV if provided
        if csv_writer:
            csv_writer.writerow({
                'file': input_file.name,
                'title': get_title_from_record(record),
                'doi': get_doi_from_record(record),
                'year': tags['year'],
                'year_bucket': tags['year_bucket'],
                'phases': '|'.join(tags['phases']),
                'challenges': '|'.join(tags['challenges']),
                'datasets': '|'.join(tags['datasets']),
                'has_metrics': tags['has_metrics'],
                'has_novelty': tags['has_novelty'],
                'has_coding_task': tags['has_coding_task'],
            })

    # Show statistics
    print(f"\n  Tagging statistics:")

    if stats['phase_counts']:
        print(f"    Method families:")
        for phase, count in stats['phase_counts'].most_common():
            print(f"      - {phase:<20} {count:>4} papers")

    if stats['challenge_counts']:
        print(f"    Challenges:")
        for challenge, count in stats['challenge_counts'].most_common():
            print(f"      - {challenge:<20} {count:>4} papers")

    if stats['dataset_counts']:
        print(f"    Datasets:")
        for dataset, count in stats['dataset_counts'].most_common():
            print(f"      - {dataset:<20} {count:>4} papers")

    print(f"    Year buckets:")
    for bucket in ['pre2012', '2012_2016', '2017_2019', '2020_2022', '2023_plus', 'UNKNOWN']:
        count = stats['year_bucket_counts'].get(bucket, 0)
        if count > 0:
            print(f"      - {bucket:<20} {count:>4} papers")

    print(f"    Flags:")
    print(f"      - Has metrics:       {stats['metrics_count']:>4} papers")
    print(f"      - Has novelty:       {stats['novelty_count']:>4} papers")
    print(f"      - Coding task:       {stats['coding_task_count']:>4} papers")

    # Write tagged records
    write_ris_file(tagged_records, output_file)
    print(f"\n  [OK] Saved: {output_file.name}")

    return stats


def tag_directory(input_dir: str, output_dir: str, csv_file: str):
    """
    Tag all RIS files in a directory

    Args:
        input_dir: Input directory path
        output_dir: Output directory path
        csv_file: Path to output CSV file
    """
    print("="*70)
    print("RIS Paper Tagger")
    print("="*70)
    print("\nTagging papers by:")
    print("  - Method families (LLM/Transformer/Deep/Classical/Rule-based)")
    print("  - Challenges (Hierarchy/Rare labels/Long text/etc.)")
    print("  - Datasets (MIMIC/eICU/UCSF/Claims)")
    print("  - Time periods (pre2012 to 2023+)")

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Find all RIS files
    ris_files = list(input_path.glob('*.ris'))

    if not ris_files:
        print(f"\nNo RIS files found in {input_dir}")
        return

    print(f"\nFound {len(ris_files)} RIS file(s) to process")

    # Open CSV for writing
    csv_path = Path(csv_file)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['file', 'title', 'doi', 'year', 'year_bucket', 'phases',
                     'challenges', 'datasets', 'has_metrics', 'has_novelty', 'has_coding_task']
        csv_writer = csv.DictWriter(f, fieldnames=fieldnames)
        csv_writer.writeheader()

        # Process each file
        total_records = 0
        all_phase_counts = Counter()
        all_challenge_counts = Counter()
        all_dataset_counts = Counter()
        all_year_bucket_counts = Counter()
        all_metrics_count = 0
        all_novelty_count = 0
        all_coding_task_count = 0

        for ris_file in sorted(ris_files):
            output_file = output_path / f"{ris_file.stem}_tagged.ris"
            stats = tag_file(ris_file, output_file, csv_writer)

            total_records += stats['total']
            all_phase_counts.update(stats['phase_counts'])
            all_challenge_counts.update(stats['challenge_counts'])
            all_dataset_counts.update(stats['dataset_counts'])
            all_year_bucket_counts.update(stats['year_bucket_counts'])
            all_metrics_count += stats['metrics_count']
            all_novelty_count += stats['novelty_count']
            all_coding_task_count += stats['coding_task_count']

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    print(f"\nOVERALL STATISTICS:")
    print(f"  Files processed:           {len(ris_files)}")
    print(f"  Total papers tagged:       {total_records}")

    # Method families
    print(f"\n{'-'*70}")
    print("METHOD FAMILIES (a paper can have multiple):")
    print(f"{'-'*70}")
    for phase, count in all_phase_counts.most_common():
        pct = (count / total_records * 100) if total_records > 0 else 0
        print(f"  {phase:<30} {count:>4} papers ({pct:>5.1f}%)")
    print(f"{'-'*70}")

    # Challenges
    if all_challenge_counts:
        print(f"\nCHALLENGES ADDRESSED (a paper can address multiple):")
        print(f"{'-'*70}")
        for challenge, count in all_challenge_counts.most_common():
            pct = (count / total_records * 100) if total_records > 0 else 0
            print(f"  {challenge:<30} {count:>4} papers ({pct:>5.1f}%)")
        print(f"{'-'*70}")

    # Datasets
    if all_dataset_counts:
        print(f"\nDATASETS USED:")
        print(f"{'-'*70}")
        for dataset, count in all_dataset_counts.most_common():
            pct = (count / total_records * 100) if total_records > 0 else 0
            print(f"  {dataset:<30} {count:>4} papers ({pct:>5.1f}%)")
        print(f"{'-'*70}")

    # Time periods
    print(f"\nTIME PERIODS:")
    print(f"{'-'*70}")
    for bucket in ['pre2012', '2012_2016', '2017_2019', '2020_2022', '2023_plus', 'UNKNOWN']:
        count = all_year_bucket_counts.get(bucket, 0)
        pct = (count / total_records * 100) if total_records > 0 else 0
        print(f"  {bucket:<30} {count:>4} papers ({pct:>5.1f}%)")
    print(f"{'-'*70}")

    # Flags
    print(f"\nCONTENT FLAGS:")
    print(f"{'-'*70}")
    metrics_pct = (all_metrics_count / total_records * 100) if total_records > 0 else 0
    novelty_pct = (all_novelty_count / total_records * 100) if total_records > 0 else 0
    coding_pct = (all_coding_task_count / total_records * 100) if total_records > 0 else 0
    print(f"  Has evaluation metrics:    {all_metrics_count:>4} papers ({metrics_pct:>5.1f}%)")
    print(f"  Has novelty language:      {all_novelty_count:>4} papers ({novelty_pct:>5.1f}%)")
    print(f"  Explicit coding task:      {all_coding_task_count:>4} papers ({coding_pct:>5.1f}%)")
    print(f"{'-'*70}")

    print(f"\nTagged RIS files saved to: {output_dir}/")
    print(f"Analysis CSV saved to: {csv_file}")


def main():
    """Main execution function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python Step8_tag_papers.py <input_directory> [output_directory] [csv_file]")
        print("\nExamples:")
        print("  python Step8_tag_papers.py refined_output/")
        print("  python Step8_tag_papers.py refined_output/ tagged_output/ analysis.csv")
        print("\nTags papers by:")
        print("  - Method families (LLM, Transformer, Deep, Classical ML, Rule-based)")
        print("  - Challenges (Hierarchy, Rare labels, Long text, etc.)")
        print("  - Datasets (MIMIC, eICU, UCSF, Claims)")
        print("  - Time periods (pre2012, 2012-2016, 2017-2019, 2020-2022, 2023+)")
        return

    input_dir = sys.argv[1]

    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_dir}' not found!")
        return

    if not os.path.isdir(input_dir):
        print(f"Error: '{input_dir}' is not a directory!")
        return

    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'tagged_output'
    csv_file = sys.argv[3] if len(sys.argv) > 3 else 'paper_tags_analysis.csv'

    tag_directory(input_dir, output_dir, csv_file)


if __name__ == "__main__":
    main()
