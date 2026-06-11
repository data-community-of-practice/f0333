#!/usr/bin/env python3
"""
step13_merge_metadata.py

Join previously-extracted metadata (a JSONL produced by extract_metadata*.py)
onto a screened CSV, matching on paper id (DOI if present, else Title). Adds
`meta_*` columns. Lets you re-attach existing extractions to a re-filtered or
deduplicated set without re-calling the API.

Usage:
    python merge_metadata.py output/screened_high_confidence.csv \
        output/metadata_extraction.jsonl --out output/final_corpus.csv
"""
import argparse
import json
import pandas as pd

MISSING = {"", "nan", "none", "na", "null", "n/a"}
FIELDS = ["research_problem", "study_objective", "input_data", "output_target",
          "method_summary", "novelty_claim", "evaluation_focus", "dataset_description",
          "key_terms", "main_contribution", "author_perspective", "confidence"]


def clean(v):
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() in MISSING else s


def pid_of(row):
    return clean(row.get("DOI")) or clean(row.get("Title"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="screened CSV to attach metadata to")
    ap.add_argument("jsonl", help="extraction JSONL (records keyed by paper_id)")
    ap.add_argument("--out", required=True, help="output CSV path")
    args = ap.parse_args()

    recs = {}
    with open(args.jsonl, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                recs[r["paper_id"]] = r

    df = pd.read_csv(args.input, dtype=str)
    pids = df.apply(pid_of, axis=1)

    def val(rec, fld):
        v = rec.get(fld, "")
        return "; ".join(v) if isinstance(v, list) else v

    for fld in FIELDS:
        df["meta_" + fld] = [val(recs.get(p, {}), fld) for p in pids]

    missing = [p for p in pids if p not in recs]
    df.to_csv(args.out, index=False)
    print(f"rows {len(df)} | matched {len(df) - len(missing)} | "
          f"missing metadata {len(missing)} -> {args.out}")
    for p in missing[:10]:
        print("  no extraction for:", p[:90])


if __name__ == "__main__":
    main()
