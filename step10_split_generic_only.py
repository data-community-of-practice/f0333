#!/usr/bin/env python3
"""
Split an auto-coding __auto_included.csv into:
  - <stem>__generic_only.csv      : papers that matched ONLY generic/weak terms
                                     (no strong/specific automated-coding term) -> likely false positives
  - <stem>__high_confidence.csv   : papers that matched >=1 strong term
Reads the `auto_matched_keywords` column written by filter_automated_coding.py.

Usage: python split_generic_only.py <auto_included.csv>
"""
import os
import sys
import csv
import argparse
from collections import Counter

# Generic / weak terms: signal quantitative/statistical methods but are common
# in ordinary clinical papers that are NOT about automated coding.
GENERIC = {
    "Algorithm", "Logistic Regression", "Prediction", "Model (predictive)",
    "Computational", "AI", "ML", "Gold Standard", "AUC / ROC",
    "F1 Score / Precision / Recall", "Benchmark / Dataset", "Annotation",
    "Decision support", "Random Forest", "Decision Tree", "Naive Bayes",
    "Support Vector Machine", "K-Nearest Neighbours", "XGBoost / GBM",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?",
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "automated_coding.csv"),
                    help="an automated-coding included csv")
    ap.add_argument("--out-prefix", default=None,
                    help="output base path; writes <prefix>_high_confidence.csv and "
                         "<prefix>_generic_only.csv. Overrides the default <stem>__* naming.")
    args = ap.parse_args()

    input_csv = os.path.abspath(args.input)
    if args.out_prefix:
        generic_csv = args.out_prefix + "_generic_only.csv"
        strong_csv  = args.out_prefix + "_high_confidence.csv"
    else:
        stem = os.path.splitext(input_csv)[0]
        generic_csv = stem + "__generic_only.csv"
        strong_csv  = stem + "__high_confidence.csv"

    generic_only, high_conf = [], []
    generic_term_counts = Counter()   # which weak terms drove the generic-only set
    fieldnames = None

    with open(input_csv, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            raw = (row.get("auto_matched_keywords") or "").strip()
            matched = {t.strip() for t in raw.split(" | ") if t.strip()}
            if matched and matched.issubset(GENERIC):
                generic_only.append(row)
                generic_term_counts.update(matched)
            else:
                high_conf.append(row)

    for path, rows in ((generic_csv, generic_only), (strong_csv, high_conf)):
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    total = len(generic_only) + len(high_conf)
    print(f"Input auto-included papers : {total}")
    print(f"  GENERIC-ONLY (review)    : {len(generic_only):>6}  ({len(generic_only)/total*100:.1f}%)")
    print(f"  HIGH-CONFIDENCE (>=1 strong term): {len(high_conf):>6}  ({len(high_conf)/total*100:.1f}%)")
    print("\nWeak terms driving the GENERIC-ONLY papers (paper can have >1):")
    for term, c in generic_term_counts.most_common():
        print(f"  {term:<35}: {c:>6}")
    print(f"\n[Done] generic-only    -> {generic_csv}")
    print(f"[Done] high-confidence -> {strong_csv}")


if __name__ == "__main__":
    main()
