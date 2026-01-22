#!/usr/bin/env python3
"""
RIS Content Filter
Filters RIS files based on content analysis of title, abstract, and keywords
Keeps papers where ICD coding is the primary task (not just metadata/cohort identification)
"""

import os
import sys
import re
from pathlib import Path
from collections import defaultdict, Counter


# Strong positive phrases indicating ICD is the *task*
POS_PHRASES = [
    r"\bicd coding\b",
    r"\bclinical coding\b",
    r"\bmedical coding\b",
    r"\bcode assignment\b",
    r"\bicd code assignment\b",
    r"\bautomatic icd\b",
    r"\bautomated icd\b",
    r"\bcomputer[- ]assisted\b.*\bcoding\b",
    r"\bcomputer[- ]aided\b.*\bcoding\b",
    r"\bauto[- ]coding\b",
    r"\bautomatic coding\b",
    r"\bautomated coding\b",
    r"\b(icd-?10|icd-?11)\s+(classification|coding|assignment|prediction)\b",
]

# Model / method verbs that, near ICD, strongly imply ICD is being predicted/assigned
MODEL_VERBS = [
    "predict", "prediction", "classify", "classification", "assign", "assignment",
    "automate", "automated", "automatic", "extract", "extraction", "label", "labeling",
    "map", "mapping", "code", "coding", "generate", "generation",
]

# General ML/NLP signals (helpful when ICD task phrasing is weaker)
ML_SIGNALS = [
    r"\bmachine learning\b", r"\bdeep learning\b", r"\bneural\b", r"\btransformer\b",
    r"\bb(i|e)lstm\b", r"\bbert\b", r"\bllm\b", r"\blarge language model\b",
    r"\bnlp\b", r"\bnatural language processing\b",
    r"\bmulti[- ]label\b", r"\bhierarch(y|ical)\b", r"\bsequence[- ]to[- ]sequence\b",
    r"\bencoder\b", r"\bdecoder\b", r"\battention\b", r"\bretrieval[- ]augmented\b",
]

# Negative phrases implying ICD is used only for cohort/outcomes (metadata use)
NEG_PHRASES = [
    r"\bused icd (codes? )?to identify\b",
    r"\bpatients? (were )?identified using icd\b",
    r"\b(icd|icd-?10|icd-?11).{0,30}\b(cohort|case definition|case-defining|phenotype|phenotyping)\b",
    r"\bbased on icd codes\b",
    r"\b(icd|icd-?10|icd-?11).{0,30}\b(administrative data|claims data|billing)\b",
    r"\bretrospective cohort\b",
    r"\bpopulation[- ]based\b",
    r"\bincidence\b|\bprevalence\b|\bmortality\b|\brisk factors?\b|\bhealth services\b|\bcost(s)?\b",
]


def parse_ris_file(filepath):
    """Parse a RIS file and return list of records"""
    records = []
    current_record = defaultdict(list)

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n\r')

            if line.startswith('ER  - '):
                if current_record:
                    records.append(dict(current_record))
                    current_record = defaultdict(list)
                continue

            if line and '  - ' in line:
                parts = line.split('  - ', 1)
                if len(parts) == 2:
                    tag = parts[0].strip()
                    value = parts[1].strip()
                    current_record[tag].append(value)

    return records


def write_ris_file(records, output_file):
    """Write records to RIS file"""
    with open(output_file, 'w', encoding='utf-8') as f:
        for record in records:
            tag_order = ['TY', 'TI', 'AU', 'PY', 'DA', 'JO', 'JF', 'T2', 'VL', 'IS',
                        'SP', 'EP', 'SN', 'AB', 'KW', 'DO', 'UR', 'AN', 'N1',
                        'PB', 'CY', 'BT', 'ED', 'T3']

            for tag in tag_order:
                if tag in record:
                    for value in record[tag]:
                        f.write(f"{tag}  - {value}\n")

            for tag, values in record.items():
                if tag not in tag_order:
                    for value in values:
                        f.write(f"{tag}  - {value}\n")

            f.write("ER  - \n\n")


def get_text_content(record):
    """
    Extract title, abstract, and keywords from record

    Returns:
        dict with 'title', 'abstract', 'keywords', 'full_text'
    """
    title = ' '.join(record.get('TI', ['']))
    abstract = ' '.join(record.get('AB', ['']))
    keywords = ' '.join(record.get('KW', ['']))

    full_text = f"{title} {abstract} {keywords}"

    return {
        'title': title.lower(),
        'abstract': abstract.lower(),
        'keywords': keywords.lower(),
        'full_text': full_text.lower()
    }


def check_positive_signals(text_dict):
    """
    Check for positive signals indicating ICD coding is the task

    Returns:
        dict with scores and matched patterns
    """
    full_text = text_dict['full_text']
    title = text_dict['title']

    pos_matches = []
    model_verb_matches = []
    ml_signal_matches = []

    # Check positive phrases
    for pattern in POS_PHRASES:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        if matches:
            pos_matches.extend(matches)

    # Check model verbs near "ICD"
    for verb in MODEL_VERBS:
        # Look for verb within 50 chars of ICD
        pattern = rf"\b{verb}\w*\b.{{0,50}}\bicd\b|\bicd\b.{{0,50}}\b{verb}\w*\b"
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        if matches:
            model_verb_matches.append(verb)

    # Check ML/NLP signals
    for pattern in ML_SIGNALS:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        if matches:
            ml_signal_matches.extend(matches)

    # Calculate scores
    pos_score = len(pos_matches)
    verb_score = len(model_verb_matches)
    ml_score = min(len(ml_signal_matches), 3)  # Cap at 3

    # Bonus for positive signals in title
    title_bonus = 0
    for pattern in POS_PHRASES:
        if re.search(pattern, title, re.IGNORECASE):
            title_bonus += 2

    return {
        'pos_score': pos_score,
        'verb_score': verb_score,
        'ml_score': ml_score,
        'title_bonus': title_bonus,
        'pos_matches': pos_matches[:5],  # Keep first 5
        'verb_matches': model_verb_matches[:5],
        'ml_matches': ml_signal_matches[:5]
    }


def check_negative_signals(text_dict):
    """
    Check for negative signals indicating ICD is used only for metadata

    Returns:
        dict with score and matched patterns
    """
    full_text = text_dict['full_text']
    title = text_dict['title']

    neg_matches = []

    for pattern in NEG_PHRASES:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        if matches:
            neg_matches.extend(matches)

    # Extra penalty for negative phrases in title
    title_penalty = 0
    for pattern in NEG_PHRASES:
        if re.search(pattern, title, re.IGNORECASE):
            title_penalty += 3

    neg_score = len(neg_matches) + title_penalty

    return {
        'neg_score': neg_score,
        'neg_matches': neg_matches[:5]
    }


def should_keep_record(record):
    """
    Decide whether to keep a record based on content analysis

    Returns:
        tuple of (keep: bool, reason: str, scores: dict)
    """
    text_dict = get_text_content(record)

    # Get positive and negative signals
    pos_signals = check_positive_signals(text_dict)
    neg_signals = check_negative_signals(text_dict)

    # Calculate total scores
    positive_score = (pos_signals['pos_score'] +
                     pos_signals['verb_score'] +
                     pos_signals['ml_score'] +
                     pos_signals['title_bonus'])

    negative_score = neg_signals['neg_score']

    # Decision logic
    # Strong positive: keep if positive_score >= 3, regardless of negatives
    if positive_score >= 3:
        return True, "Strong positive signals", {
            'positive': positive_score,
            'negative': negative_score,
            **pos_signals,
            **neg_signals
        }

    # Moderate positive: keep if positive_score >= 2 and negative_score <= 2
    if positive_score >= 2 and negative_score <= 2:
        return True, "Moderate positive signals", {
            'positive': positive_score,
            'negative': negative_score,
            **pos_signals,
            **neg_signals
        }

    # Strong negative: remove if negative_score >= 3 and positive_score < 2
    if negative_score >= 3 and positive_score < 2:
        return False, "Strong negative signals (cohort/metadata use)", {
            'positive': positive_score,
            'negative': negative_score,
            **pos_signals,
            **neg_signals
        }

    # Weak signals: keep if any positive signals exist
    if positive_score > 0:
        return True, "Weak positive signals", {
            'positive': positive_score,
            'negative': negative_score,
            **pos_signals,
            **neg_signals
        }

    # No clear signals: remove (too ambiguous)
    return False, "No clear ICD coding task signals", {
        'positive': positive_score,
        'negative': negative_score,
        **pos_signals,
        **neg_signals
    }


def get_title_from_record(record):
    """Extract title from record"""
    if 'TI' in record and record['TI']:
        title = record['TI'][0]
        return title[:100] + '...' if len(title) > 100 else title
    return 'Unknown'


def filter_by_content(records):
    """
    Filter records based on content analysis

    Returns:
        tuple of (filtered_records, stats)
    """
    filtered_records = []
    kept_reasons = Counter()
    removed_reasons = Counter()
    kept_examples = []
    removed_examples = []

    for record in records:
        keep, reason, scores = should_keep_record(record)

        if keep:
            filtered_records.append(record)
            kept_reasons[reason] += 1
            if len(kept_examples) < 3:
                kept_examples.append({
                    'title': get_title_from_record(record),
                    'reason': reason,
                    'scores': scores
                })
        else:
            removed_reasons[reason] += 1
            if len(removed_examples) < 3:
                removed_examples.append({
                    'title': get_title_from_record(record),
                    'reason': reason,
                    'scores': scores
                })

    stats = {
        'kept_reasons': kept_reasons,
        'removed_reasons': removed_reasons,
        'kept_examples': kept_examples,
        'removed_examples': removed_examples
    }

    return filtered_records, stats


def filter_file(input_file, output_file):
    """Filter a single RIS file by content"""
    print(f"\nProcessing: {input_file.name}")

    records = parse_ris_file(input_file)
    records_before = len(records)
    print(f"  Records before filtering: {records_before}")

    filtered_records, stats = filter_by_content(records)
    records_after = len(filtered_records)
    records_removed = records_before - records_after

    print(f"  Records after filtering:  {records_after}")
    print(f"  Records removed:          {records_removed} ({(records_removed/records_before*100) if records_before > 0 else 0:.1f}%)")

    # Show kept reasons
    if stats['kept_reasons']:
        print(f"\n  Kept reasons:")
        for reason, count in stats['kept_reasons'].most_common():
            print(f"    - {reason:<50} {count:>5}")

    # Show removed reasons
    if stats['removed_reasons']:
        print(f"\n  Removed reasons:")
        for reason, count in stats['removed_reasons'].most_common():
            print(f"    - {reason:<50} {count:>5}")

    # Show examples
    if stats['kept_examples']:
        print(f"\n  Example kept records:")
        for ex in stats['kept_examples'][:2]:
            print(f"    Title: {ex['title']}")
            print(f"    Reason: {ex['reason']}")
            print(f"    Scores: +{ex['scores']['positive']} / -{ex['scores']['negative']}")

    if stats['removed_examples']:
        print(f"\n  Example removed records:")
        for ex in stats['removed_examples'][:2]:
            print(f"    Title: {ex['title']}")
            print(f"    Reason: {ex['reason']}")
            print(f"    Scores: +{ex['scores']['positive']} / -{ex['scores']['negative']}")

    if filtered_records:
        write_ris_file(filtered_records, output_file)
        print(f"\n  [OK] Saved: {output_file.name}")
    else:
        print(f"\n  [WARNING] No matching records - output file not created")

    return {
        'before': records_before,
        'after': records_after,
        'removed': records_removed,
        'kept_reasons': stats['kept_reasons'],
        'removed_reasons': stats['removed_reasons']
    }


def filter_directory(input_dir, output_dir):
    """Filter all RIS files in a directory"""
    print("="*70)
    print("RIS Content Filter - ICD Coding Task Identification")
    print("="*70)
    print("\nFiltering criteria:")
    print("  KEEP: Papers where ICD coding is the primary task")
    print("  REMOVE: Papers using ICD only for cohort identification")

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    ris_files = list(input_path.glob('*.ris'))

    if not ris_files:
        print(f"\nNo RIS files found in {input_dir}")
        return

    print(f"\nFound {len(ris_files)} RIS file(s) to process")

    total_before = 0
    total_after = 0
    all_kept_reasons = Counter()
    all_removed_reasons = Counter()
    file_stats = []

    for ris_file in sorted(ris_files):
        output_file = output_path / f"{ris_file.stem}_content_filtered.ris"
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
            filename = stat['name'].replace('.ris', '_content_filtered.ris')
            print(f"  - {filename:<55} {stat['after']:>6} records")


def main():
    """Main execution function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python Step6_filter_by_content.py <input_file_or_directory> [output_directory]")
        print("\nExamples:")
        print("  python Step6_filter_by_content.py final_output/ curated_output/")
        print("  python Step6_filter_by_content.py input.ris output_content_filtered.ris")
        print("\nFiltering Criteria:")
        print("  KEEPS papers where ICD coding is the primary research task")
        print("  REMOVES papers using ICD codes only for cohort identification")
        return

    input_path = sys.argv[1]

    if not os.path.exists(input_path):
        print(f"Error: Input path '{input_path}' not found!")
        return

    if os.path.isdir(input_path):
        output_dir = sys.argv[2] if len(sys.argv) > 2 else 'curated_output'
        filter_directory(input_path, output_dir)
    else:
        output_file = sys.argv[2] if len(sys.argv) > 2 else input_path.replace('.ris', '_content_filtered.ris')
        input_file = Path(input_path)
        output_file = Path(output_file)

        print("="*70)
        print("RIS Content Filter - ICD Coding Task Identification")
        print("="*70)
        filter_file(input_file, output_file)


if __name__ == "__main__":
    main()
