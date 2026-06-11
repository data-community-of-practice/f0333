"""
step11_filter_false_icd.py
-------------------
Post-filter that removes papers where "ICD" matches a different acronym
(not International Classification of Diseases).

Runs AFTER filter_icd_relevance.py. Takes the included corpus and removes
papers where "ICD" clearly refers to:
  - Implantable Cardioverter-Defibrillator (cardiac devices)
  - Indian Classical Dance
  - In-Context Demonstrations (LLM research)
  - OpenCL Installable Client Driver
  - Other clearly off-topic uses of the acronym

A paper is only excluded if:
  (a) it matches a false-ICD pattern, AND
  (b) it has no strong real-ICD signals (ICD-9/10/11, medical coding terms, etc.)

Produces:
  - <stem>__false_icd_removed.csv   : cleaned corpus
  - <stem>__false_icd_excluded.csv  : removed papers with exclusion reason
  - <stem>__false_icd_report.txt    : summary report

Usage:
    python filter_false_icd.py outputs/final_corpus.csv
    python filter_false_icd.py outputs/final_corpus.csv --out outputs/final_corpus_clean.csv
"""

import os
import re
import csv
import sys
import argparse
from collections import defaultdict

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(BASE_DIR, "output", "screened_high_confidence.csv")

# ── Real-ICD signals: if present, override any false-ICD match ───────────────
# A paper with these signals is kept even if a false-ICD pattern also matches.
REAL_ICD = re.compile(
    r'(international\s+classification\s+of\s+diseases'
    r'|icd[-\s]?(9|10|11|cm|pcs|o\b)'
    r'|icd\s+cod(e|es|ing|ed)'
    r'|icd[-\s]based'
    r'|medical\s+cod(ing|e|es|ed)'
    r'|clinical\s+cod(ing|e|es|ed)'
    r'|diagnosis\s+cod(ing|e|es|ed)'
    r'|diagnostic\s+cod(ing|e|es|ed)'
    r'|clinical\s+documentation\s+improvement'
    r'|discharge\s+summar\w+\s+cod'
    r'|billing\s+cod'
    r'|reimbursement\s+cod'
    r'|automated?\s+icd'
    r'|icd\s+assign)',
    re.IGNORECASE,
)

# ── False-ICD patterns: each entry is (label, compiled_regex) ────────────────
# Patterns match the combined title + abstract text.
FALSE_ICD_PATTERNS = [

    # Implantable Cardioverter-Defibrillator ──────────────────────────────────
    # Very common false positive: cardiac device papers.
    (
        "Implantable Cardioverter-Defibrillator (cardiac device)",
        re.compile(
            r'implantable\s+cardioverter[- ]?defibrillator'
            r'|icd\s+(shock|therapy|electrogram|egm|lead\b|generator|patient\b|implant)'
            r'|icd[-\s]treated'
            r'|icd[-\s]detected'
            r'|ventricular\s+(tachycardia|arrhythmia|fibrillation).{0,120}icd'
            r'|icd.{0,120}(tachycardia|arrhythmia|fibrillation|defibrillat)',
            re.IGNORECASE | re.DOTALL,
        ),
    ),

    # Indian Classical Dance ──────────────────────────────────────────────────
    (
        "Indian Classical Dance",
        re.compile(
            r'indian\s+classical\s+dance'
            r'|bharatanatyam|kathak|odissi|kuchipudi|mohiniyattam'
            r'|dance\s+(classification|recognition|sequence|gesture)'
            r'|hand\s+mudra',
            re.IGNORECASE,
        ),
    ),

    # In-Context Demonstrations (LLM/NLP research) ────────────────────────────
    (
        "In-Context Demonstration (LLM/NLP)",
        re.compile(
            r'in[-\s]context\s+demonstration'
            r'|in[-\s]context\s+example'
            r'|demonstration\s+retriev',
            re.IGNORECASE,
        ),
    ),

    # OpenCL Installable Client Driver ────────────────────────────────────────
    (
        "OpenCL Installable Client Driver",
        re.compile(
            r'\bopenCL\b.{0,80}icd'
            r'|icd.{0,80}\bopenCL\b'
            r'|installable\s+client\s+driver'
            r'|khronos.{0,80}icd',
            re.IGNORECASE | re.DOTALL,
        ),
    ),

    # Histogram Intersection (HIK) ────────────────────────────────────────────
    # Not ICD at all — matched via broad "classification" keywords.
    (
        "Histogram Intersection Kernel (not ICD)",
        re.compile(
            r'histogram\s+intersection\s+kernel'
            r'|\bhik\s+svm\b',
            re.IGNORECASE,
        ),
    ),
]

SEARCH_FIELDS = ["Title", "Abstract"]


def cell(row, field):
    return (row.get(field) or "").strip()


def combined_text(row):
    return " ".join(cell(row, f) for f in SEARCH_FIELDS)


def classify(row):
    """Return (exclusion_reason | None) for a row."""
    text = combined_text(row)
    # If strong real-ICD signals exist, always keep.
    if REAL_ICD.search(text):
        return None
    for label, pattern in FALSE_ICD_PATTERNS:
        if pattern.search(text):
            return label
    return None


def main():
    ap = argparse.ArgumentParser(
        description="Remove false-ICD papers (ICD != International Classification of Diseases)."
    )
    ap.add_argument("input", nargs="?", default=INPUT_CSV,
                    help="input CSV (default: outputs/final_corpus.csv)")
    ap.add_argument("--out", default=None,
                    help="path for the cleaned output CSV; exclusion CSV and report are derived from it")
    args = ap.parse_args()

    input_csv = os.path.abspath(args.input)
    stem = os.path.splitext(os.path.basename(input_csv))[0]
    outdir = os.path.dirname(input_csv)

    if args.out:
        base = os.path.splitext(os.path.abspath(args.out))[0]
    else:
        base = os.path.join(outdir, f"{stem}__false_icd_removed")

    cleaned_csv  = base + ".csv"
    excluded_csv = base + "_excluded.csv"
    report_file  = base + "_report.txt"

    kept, removed = [], []
    reason_counts = defaultdict(int)

    fieldnames = None
    with open(input_csv, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            reason = classify(row)
            if reason:
                row["false_icd_exclusion_reason"] = reason
                removed.append(row)
                reason_counts[reason] += 1
            else:
                kept.append(row)

    extra = ["false_icd_exclusion_reason"]
    out_fields_kept     = list(fieldnames)
    out_fields_excluded = list(fieldnames) + [c for c in extra if c not in fieldnames]

    with open(cleaned_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields_kept, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(kept)

    with open(excluded_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields_excluded, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(removed)

    # ── Report ────────────────────────────────────────────────────────────────
    total = len(kept) + len(removed)
    sep   = "=" * 65
    lines = [
        sep,
        "  FALSE-ICD EXCLUSION REPORT",
        sep,
        "",
        "OVERVIEW",
        "-" * 40,
        f"  Input records  : {total:>6}",
        f"  Kept           : {len(kept):>6}  ({len(kept)/total*100:.1f}%)",
        f"  Removed        : {len(removed):>6}  ({len(removed)/total*100:.1f}%)",
        "",
        "REMOVED — BY FALSE-ICD CATEGORY",
        "-" * 40,
    ]
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {count:>4}  {reason}")
    lines += [
        "",
        "LOGIC",
        "-" * 40,
        "  A paper is removed ONLY IF:",
        "    (a) its title+abstract matches a false-ICD pattern, AND",
        "    (b) its title+abstract has NO strong real-ICD signals",
        "        (icd-9/10/11, icd coding, medical coding, etc.)",
        "",
        sep,
        f"  Cleaned CSV  -> {cleaned_csv}",
        f"  Excluded CSV -> {excluded_csv}",
        sep,
    ]

    report = "\n".join(lines)
    safe   = report.encode(sys.stdout.encoding or "utf-8", errors="replace") \
                   .decode(sys.stdout.encoding or "utf-8", errors="replace")
    print(safe)

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n[Done]  Cleaned  -> {cleaned_csv}  ({len(kept)} rows)")
    print(f"[Done]  Excluded -> {excluded_csv}  ({len(removed)} rows)")
    print(f"[Done]  Report   -> {report_file}")


if __name__ == "__main__":
    main()
