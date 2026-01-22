#!/usr/bin/env python3
"""
RIS Representative Paper Selector
Selects representative papers from each bucket (method × challenge)
Uses scoring heuristics to pick the most exemplary papers
"""

import os
import sys
import re
import csv
from pathlib import Path
from collections import defaultdict, Counter
from typing import List, Tuple, Dict, Any


# Configuration
TOP_N_PER_BUCKET = 3      # Select top 3 papers per bucket
TOTAL_CAP = None          # Optional: cap total papers (None = no cap)
BUCKET_MODE = "phase_x_challenge"  # Options: "phase_only", "phase_x_dataset", "phase_x_challenge"
WRITE_SELECTED_RIS = True  # Write selected papers to RIS file


# Phase (method family) signals - PRIORITY ORDER matters!
# LLM overrides Transformer overrides Deep Learning, etc.
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

# ICD pattern (sanity check)
ICD_PAT = re.compile(r"\bicd\b", re.I)


def year_bucket(y: str) -> str:
    """Convert year to bucket"""
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
    """Parse a RIS file and return list of records"""
    records = []
    current_record = defaultdict(list)
    raw_lines = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            raw_lines.append(line)
            line = line.rstrip('\n\r')

            # End of record
            if line.startswith('ER  - '):
                if current_record:
                    record = dict(current_record)
                    record['_raw'] = ''.join(raw_lines)
                    record['_source'] = str(filepath)
                    records.append(record)
                    current_record = defaultdict(list)
                    raw_lines = []
                continue

            # Parse tag-value pair
            if line and '  - ' in line:
                parts = line.split('  - ', 1)
                if len(parts) == 2:
                    tag = parts[0].strip()
                    value = parts[1].strip()
                    current_record[tag].append(value)

    return records


def get_text_content(record: Dict) -> str:
    """Extract title, abstract, and keywords from record"""
    title = ' '.join(record.get('TI', []))
    abstract = ' '.join(record.get('AB', []))
    keywords = ' '.join(record.get('KW', []))
    return f"{title} {abstract} {keywords}"


def get_year(record: Dict) -> str:
    """Extract publication year from record"""
    if 'PY' in record and record['PY']:
        year_str = record['PY'][0]
        match = re.search(r'\d{4}', year_str)
        if match:
            return match.group(0)
    if 'DA' in record and record['DA']:
        date_str = record['DA'][0]
        match = re.search(r'\d{4}', date_str)
        if match:
            return match.group(0)
    return ""


def tag_phase(text: str) -> str:
    """
    Tag phase with priority order.
    LLM overrides Transformer overrides Deep Learning, etc.
    """
    for label, rx in PHASE_RULES:
        if rx.search(text):
            return label
    return "UNSPECIFIED"


def tag_challenges(text: str) -> List[str]:
    """Tag all challenges mentioned"""
    tags = []
    for label, rx in CHALLENGE_RULES:
        if rx.search(text):
            tags.append(label)
    return tags or ["GENERAL"]


def tag_dataset(text: str) -> str:
    """Tag dataset (first match wins)"""
    for label, rx in DATASET_RULES:
        if rx.search(text):
            return label
    return "UNKNOWN"


def score_record(text: str) -> int:
    """
    Heuristic score to pick representatives inside a bucket.
    Higher score = better representative
    """
    score = 0

    # Evidence of evaluation
    if METRIC_PAT.search(text):
        score += 3

    # Methodological contribution
    if NOVELTY_PAT.search(text):
        score += 2

    # Clearly about coding/assignment
    if CODING_TASK_PAT.search(text):
        score += 2

    # Prefer papers with substantial abstracts
    if len(text) > 600:
        score += 1

    return score


def get_title_from_record(record: Dict) -> str:
    """Extract title from record"""
    if 'TI' in record and record['TI']:
        return record['TI'][0]
    return 'Unknown'


def get_doi_from_record(record: Dict) -> str:
    """Extract DOI from record"""
    if 'DO' in record and record['DO']:
        return record['DO'][0]
    return ''


def get_journal_from_record(record: Dict) -> str:
    """Extract journal from record"""
    if 'JO' in record and record['JO']:
        return record['JO'][0]
    if 'JF' in record and record['JF']:
        return record['JF'][0]
    if 'T2' in record and record['T2']:
        return record['T2'][0]
    return ''


def select_representatives(input_dir: str, output_dir: str):
    """
    Select representative papers from each bucket

    Args:
        input_dir: Input directory with RIS files
        output_dir: Output directory for results
    """
    print("="*70)
    print("RIS Representative Paper Selector")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  Bucket mode:        {BUCKET_MODE}")
    print(f"  Top N per bucket:   {TOP_N_PER_BUCKET}")
    print(f"  Total cap:          {TOTAL_CAP or 'None'}")
    print(f"  Write RIS:          {WRITE_SELECTED_RIS}")

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Find all RIS files
    ris_files = list(input_path.glob('*.ris'))

    if not ris_files:
        print(f"\nNo RIS files found in {input_dir}")
        return

    print(f"\nFound {len(ris_files)} RIS file(s) to process")

    # Parse all records
    records = []
    for ris_file in sorted(ris_files):
        print(f"  Reading: {ris_file.name}")
        file_records = parse_ris_file(ris_file)
        records.extend(file_records)

    print(f"\nTotal records loaded: {len(records)}")

    # Tag and bucket records
    tagged_rows: List[Dict[str, str]] = []
    bucketed: Dict[Tuple[str, str], List[Tuple[int, int, Dict, Dict[str, str]]]] = defaultdict(list)

    print("\nTagging and bucketing papers...")
    skipped = 0

    for i, record in enumerate(records, start=1):
        text = get_text_content(record)
        text_norm = re.sub(r"\s+", " ", text).strip()

        # Sanity check: should mention ICD
        if not ICD_PAT.search(text_norm):
            skipped += 1
            continue

        # Tag
        phase = tag_phase(text_norm)
        challenges = tag_challenges(text_norm)
        ds = tag_dataset(text_norm)
        year = get_year(record)
        yb = year_bucket(year)
        score = score_record(text_norm)

        # Primary challenge (for bucketing)
        primary_challenge = next((c for c in challenges if c != "GENERAL"), "GENERAL")

        # Bucket key
        if BUCKET_MODE == "phase_only":
            bucket_key = (phase, "ALL")
        elif BUCKET_MODE == "phase_x_dataset":
            bucket_key = (phase, ds)
        else:  # phase_x_challenge
            bucket_key = (phase, primary_challenge)

        # Create row
        row = {
            "id": str(i),
            "source_file": record.get('_source', ''),
            "year": year,
            "year_bucket": yb,
            "journal": get_journal_from_record(record),
            "doi": get_doi_from_record(record),
            "title": get_title_from_record(record),
            "phase": phase,
            "primary_challenge": primary_challenge,
            "all_challenges": ";".join(challenges),
            "dataset_tag": ds,
            "has_metrics": "1" if METRIC_PAT.search(text_norm) else "0",
            "has_novelty": "1" if NOVELTY_PAT.search(text_norm) else "0",
            "has_coding_task": "1" if CODING_TASK_PAT.search(text_norm) else "0",
            "score": str(score),
        }
        tagged_rows.append(row)

        # Add to bucket
        year_int = int(year) if year.isdigit() else 0
        bucketed[bucket_key].append((score, year_int, record, row))

    print(f"  Tagged: {len(tagged_rows)} papers")
    print(f"  Skipped: {skipped} papers (no ICD mention)")
    print(f"  Buckets created: {len(bucketed)}")

    # Write tagged CSV
    tag_csv = output_path / "tagged_papers.csv"
    with tag_csv.open("w", newline="", encoding="utf-8") as fp:
        if tagged_rows:
            fieldnames = list(tagged_rows[0].keys())
            writer = csv.DictWriter(fp, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(tagged_rows)

    print(f"\n  Wrote: {tag_csv.name} ({len(tagged_rows)} papers)")

    # Select representatives per bucket
    print("\nSelecting representatives per bucket...")
    selected: List[Tuple[Tuple[str, str], int, int, Dict, Dict[str, str]]] = []

    for bkey, items in bucketed.items():
        # Sort by: score desc, year desc (newer as tie-break), title length desc (minor)
        items_sorted = sorted(
            items,
            key=lambda x: (x[0], x[1], len(x[3].get('title', ''))),
            reverse=True
        )
        picked = items_sorted[:TOP_N_PER_BUCKET]
        selected.extend([(bkey, *p) for p in picked])

    print(f"  Selected: {len(selected)} representatives")

    # Optional total cap
    if TOTAL_CAP is not None and len(selected) > TOTAL_CAP:
        print(f"  Applying total cap: {TOTAL_CAP}")
        selected = sorted(selected, key=lambda x: (x[1], x[2]), reverse=True)[:TOTAL_CAP]
        print(f"  Final count: {len(selected)}")

    # Prepare selected CSV + optional RIS
    selected_rows: List[Dict[str, str]] = []
    selected_ris_raw: List[str] = []

    for bkey, score, year_int, rec, row in selected:
        out = dict(row)
        out["bucket_phase"] = bkey[0]
        out["bucket_dim"] = bkey[1]
        out["bucket"] = f"{bkey[0]}__{bkey[1]}"
        selected_rows.append(out)
        if WRITE_SELECTED_RIS:
            selected_ris_raw.append(rec.get('_raw', ''))

    # Write selected CSV
    sel_csv = output_path / "selected_representatives.csv"
    with sel_csv.open("w", newline="", encoding="utf-8") as fp:
        if selected_rows:
            fieldnames = list(selected_rows[0].keys())
            writer = csv.DictWriter(fp, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(selected_rows)

    print(f"\n  Wrote: {sel_csv.name} ({len(selected_rows)} representatives)")

    # Write selected RIS
    if WRITE_SELECTED_RIS:
        sel_ris = output_path / "selected_representatives.ris"
        sel_ris.write_text("".join(selected_ris_raw), encoding="utf-8")
        print(f"  Wrote: {sel_ris.name}")

    # Coverage report
    print(f"\n{'='*70}")
    print("COVERAGE REPORT")
    print(f"{'='*70}")

    coverage = defaultdict(int)
    for r in selected_rows:
        coverage[(r["bucket_phase"], r["bucket_dim"])] += 1

    print(f"\n{'Phase':<20} {'Dimension':<25} {'Count':>5}")
    print("-"*70)
    for (ph, dim), cnt in sorted(coverage.items()):
        print(f"{ph:<20} {dim:<25} {cnt:>5}")
    print("-"*70)
    print(f"{'TOTAL':<20} {'':<25} {len(selected_rows):>5}")

    # Statistics by phase
    phase_counts = Counter([r["bucket_phase"] for r in selected_rows])
    print(f"\nREPRESENTATIVES BY METHOD FAMILY:")
    print("-"*70)
    for phase, count in phase_counts.most_common():
        print(f"  {phase:<30} {count:>4} papers")

    # Statistics by challenge
    challenge_counts = Counter([r["bucket_dim"] for r in selected_rows])
    print(f"\nREPRESENTATIVES BY CHALLENGE/DIMENSION:")
    print("-"*70)
    for challenge, count in challenge_counts.most_common():
        print(f"  {challenge:<30} {count:>4} papers")

    # Year distribution
    year_counts = Counter([r["year_bucket"] for r in selected_rows])
    print(f"\nREPRESENTATIVES BY TIME PERIOD:")
    print("-"*70)
    for bucket in ['pre2012', '2012_2016', '2017_2019', '2020_2022', '2023_plus', 'UNKNOWN']:
        count = year_counts.get(bucket, 0)
        if count > 0:
            print(f"  {bucket:<30} {count:>4} papers")

    print(f"\n{'='*70}")
    print(f"Output saved to: {output_dir}/")
    print(f"  - tagged_papers.csv: All {len(tagged_rows)} papers with tags")
    print(f"  - selected_representatives.csv: {len(selected_rows)} representative papers")
    if WRITE_SELECTED_RIS:
        print(f"  - selected_representatives.ris: {len(selected_rows)} papers in RIS format")


def main():
    """Main execution function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python Step9_select_representatives.py <input_directory> [output_directory]")
        print("\nExamples:")
        print("  python Step9_select_representatives.py tagged_output/")
        print("  python Step9_select_representatives.py tagged_output/ representatives/")
        print("\nConfiguration (edit script to modify):")
        print(f"  TOP_N_PER_BUCKET = {TOP_N_PER_BUCKET}")
        print(f"  BUCKET_MODE = '{BUCKET_MODE}'")
        print(f"  TOTAL_CAP = {TOTAL_CAP}")
        print("\nSelects representative papers from each bucket:")
        print("  - Buckets by method family × challenge")
        print("  - Scores by metrics, novelty, coding task, length")
        print("  - Picks top N per bucket")
        return

    input_dir = sys.argv[1]

    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_dir}' not found!")
        return

    if not os.path.isdir(input_dir):
        print(f"Error: '{input_dir}' is not a directory!")
        return

    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'representatives'

    select_representatives(input_dir, output_dir)


if __name__ == "__main__":
    main()
