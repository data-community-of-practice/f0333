"""
step8_filter_icd_relevance.py
-----------------------
Filters filtered_papers.csv to keep only ICD-relevant papers.
A paper is included if ANY keyword matches in title, abstract, or keywords.
Produces:
  - icd_included.csv   : matched papers
  - icd_excluded.csv   : non-matched papers
  - icd_relevance_report.txt
"""

import os
import re
import csv
import sys
import argparse
from collections import defaultdict

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV  = os.path.join(BASE_DIR, "output", "enriched_papers.csv")
INCLUDED_CSV = os.path.join(BASE_DIR, "output", "icd_relevant.csv")
EXCLUDED_CSV = os.path.join(BASE_DIR, "output", "icd_excluded.csv")
REPORT_FILE  = os.path.join(BASE_DIR, "output", "icd_relevance_report.txt")

# ── Keyword definitions ───────────────────────────────────────────────────────
# Format: "Label": (compiled_regex, category)
# Categories help the report show which themes drove inclusion.

ICD_KEYWORDS = {

    # ── ICD versions & core terminology ──────────────────────────────────────
    "ICD (any)":
        r'\bICD[-\s]?\d*\b',
    "ICD code/coding":
        r'\bICD[\s-]?\d*\s+cod(e|es|ing|ed)\b',
    "ICD-9":
        r'\bICD[-\s]?9\b',
    "ICD-10":
        r'\bICD[-\s]?10\b',
    "ICD-11":
        r'\bICD[-\s]?11\b',
    "ICD-O (Oncology)":
        r'\bICD[-\s]?O\b',
    "ICD-CM":
        r'\bICD[-\s]?\d*[-\s]?CM\b',
    "ICD-PCS":
        r'\bICD[-\s]?\d*[-\s]?PCS\b',
    "International Classification of Diseases":
        r'\binternational classification of diseases\b',

    # ── Medical / clinical coding ─────────────────────────────────────────────
    "Medical coding":
        r'\bmedical cod(ing|e|es|ed)\b',
    "Clinical coding":
        r'\bclinical cod(ing|e|es|ed)\b',
    "Diagnosis coding":
        r'\bdiagnos(is|tic|es) cod(ing|e|es|ed)\b',
    "Diagnostic coding":
        r'\bdiagnostic cod(ing|e|es|ed)\b',
    "Code assignment":
        r'\bcode assignment\b',
    "Disease classification":
        r'\bdisease classification\b',
    "Health record coding":
        r'\bhealth record cod(ing|e|es)\b',
    "Clinical classification":
        r'\bclinical classification\b',
    "Discharge coding":
        r'\bdischarge cod(ing|e|es|ed)\b',
    "Inpatient coding":
        r'\binpatient cod(ing|e|es|ed)\b',
    "Hospital coding":
        r'\bhospital cod(ing|e|es|ed)\b',
    "Procedure coding":
        r'\bprocedure cod(ing|e|es|ed)\b',
    "Coding accuracy":
        r'\bcoding accurac(y|ies)\b',
    "Coding error":
        r'\bcoding errors?\b',
    "Coding quality":
        r'\bcoding qualit(y|ies)\b',
    "Miscoding / undercoding":
        r'\b(mis|under|over)cod(ing|ed)\b',
    "Coder (human)":
        r'\bclinical coder\b',
    "Nosology":
        r'\bnosolog(y|ical|ies)\b',

    # ── Related classification & coding systems ───────────────────────────────
    "DRG (Diagnosis Related Group)":
        r'\bDRG\b|\bdiagnosis[- ]related group\b',
    "Clinical documentation improvement":
        r'\bclinical documentation improvement\b|\bCDI\b',
    "WHO classification":
        r'\bWHO classification\b',
    "SNOMED to ICD mapping":
        r'\bSNOMED\b.{0,60}(ICD|mapping|cod(ing|e))',
    "ICD mapping / crosswalk":
        r'\bICD\b.{0,60}(mapping|crosswalk|GEM|general equivalence)',
    "General Equivalence Mapping":
        r'\bgeneral equivalence mapping\b|\bGEM\b.{0,30}ICD',
    "Administrative data coding":
        r'\badministrative (data|claims?).{0,40}(cod(ing|e)|ICD|classification)',
    "Claims data coding":
        r'\bclaims? (data|based).{0,40}(cod(ing|e)|ICD|diagnosis)',

    # ── EHR / clinical document context ──────────────────────────────────────
    "Electronic health record coding":
        r'\b(EHR|EMR|electronic health record).{0,60}(cod(ing|e)|ICD|classification)',
    "Discharge summary coding":
        r'\bdischarge summar(y|ies).{0,40}(cod(ing|e)|ICD|classification)',
    "Clinical document coding":
        r'\bclinical (document|note|text).{0,40}(cod(ing|e)|ICD|classification)',
}

# Pre-compile all patterns (case-insensitive)
COMPILED = {
    label: re.compile(pattern, re.IGNORECASE | re.DOTALL)
    for label, pattern in ICD_KEYWORDS.items()
}

SEARCH_FIELDS = ["title", "abstract", "keywords"]


def resolve_columns(fieldnames):
    """Map logical field names -> actual CSV headers, case-insensitively.
    Lets the filter work whether columns are 'title' or 'Title', and find a
    'source' column under any casing (falling back to 'Type' if present)."""
    lower = {fn.strip().lower(): fn for fn in (fieldnames or []) if fn}
    cols = {f: lower.get(f) for f in SEARCH_FIELDS}
    cols["source"] = lower.get("source") or lower.get("type")
    return cols


def cell(row, colname):
    return (row.get(colname) or "") if colname else ""


def find_matches(row, cols):
    """Return dict of {label: [fields where it matched]} for all matching keywords."""
    text_by_field = {f: cell(row, cols.get(f)) for f in SEARCH_FIELDS}
    matches = defaultdict(list)
    for label, regex in COMPILED.items():
        for field, text in text_by_field.items():
            if text and regex.search(text):
                matches[label].append(field)
    return dict(matches)


def main():
    ap = argparse.ArgumentParser(description="Filter a papers CSV to ICD-relevant rows.")
    ap.add_argument("input", nargs="?", default=INPUT_CSV,
                    help="input CSV (default: filtered_papers.csv)")
    ap.add_argument("--outdir", default=os.path.join(BASE_DIR, "output"),
                    help="directory for output files (default: alongside input)")
    ap.add_argument("--out", default=None,
                    help="explicit path for the INCLUDED csv; the excluded csv and "
                         "report are derived from it (<base>_excluded.csv, <base>_report.txt). "
                         "Overrides the default <stem>__icd_included.csv naming.")
    args = ap.parse_args()

    input_csv = os.path.abspath(args.input)
    stem = os.path.splitext(os.path.basename(input_csv))[0]
    if args.out:
        base = os.path.splitext(args.out)[0]
        included_csv = args.out
        excluded_csv = base + "_excluded.csv"
        report_file  = base + "_report.txt"
    else:
        included_csv = os.path.join(args.outdir, f"{stem}__icd_included.csv")
        excluded_csv = os.path.join(args.outdir, f"{stem}__icd_excluded.csv")
        report_file  = os.path.join(args.outdir, f"{stem}__icd_relevance_report.txt")

    included = []
    excluded = []

    # Counters
    keyword_hit_counts   = defaultdict(int)   # how many papers each keyword matched
    field_hit_counts     = defaultdict(int)   # how many matches per field
    source_included      = defaultdict(int)
    source_excluded      = defaultdict(int)
    title_only_included  = 0
    title_only_excluded  = 0

    fieldnames = None

    with open(input_csv, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        cols = resolve_columns(fieldnames)

        for row in reader:
            has_abstract = bool(cell(row, cols.get("abstract")).strip())
            has_keywords = bool(cell(row, cols.get("keywords")).strip())
            is_title_only = not has_abstract and not has_keywords

            matches = find_matches(row, cols)

            src = cell(row, cols.get("source")).strip() or "all"

            row["matched_keywords"] = " | ".join(sorted(matches.keys()))
            row["matched_in_fields"] = " | ".join(
                sorted({f for fields in matches.values() for f in fields})
            )

            if matches:
                included.append(row)
                source_included[src] += 1
                if is_title_only:
                    title_only_included += 1
                for label, fields in matches.items():
                    keyword_hit_counts[label] += 1
                    for field in fields:
                        field_hit_counts[field] += 1
            else:
                excluded.append(row)
                source_excluded[src] += 1
                if is_title_only:
                    title_only_excluded += 1

    # ── Write CSVs ────────────────────────────────────────────────────────────
    extra_cols = ["matched_keywords", "matched_in_fields"]
    out_fields = list(fieldnames) + [c for c in extra_cols if c not in fieldnames]

    with open(included_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(included)

    with open(excluded_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(excluded)

    # ── Report ────────────────────────────────────────────────────────────────
    total = len(included) + len(excluded)
    lines = []
    sep   = "=" * 65

    lines += [sep, "  ICD RELEVANCE FILTER REPORT", sep, ""]

    lines += ["OVERVIEW", "-" * 40]
    lines += [
        f"  Input records          : {total:>7}",
        f"  ICD-relevant (included): {len(included):>7}  ({len(included)/total*100:.1f}%)",
        f"  Not relevant (excluded): {len(excluded):>7}  ({len(excluded)/total*100:.1f}%)",
        "",
    ]

    lines += ["INCLUDED — BY SOURCE", "-" * 40]
    for src in sorted(source_included):
        tot_src = source_included[src] + source_excluded[src]
        lines.append(
            f"  {src:<10}: {source_included[src]:>6} included"
            f"  /  {tot_src:>6} total  ({source_included[src]/tot_src*100:.1f}%)"
        )
    lines.append("")

    lines += ["MATCH FIELD BREAKDOWN (included papers)", "-" * 40]
    lines += [
        f"  Title matched    : {field_hit_counts['title']:>6}",
        f"  Abstract matched : {field_hit_counts['abstract']:>6}",
        f"  Keywords matched : {field_hit_counts['keywords']:>6}",
        f"  (counts overlap — one paper can match in multiple fields)",
        "",
    ]

    lines += ["DATA COVERAGE NOTE", "-" * 40]
    lines += [
        f"  Title-only records (no abstract/keywords):",
        f"    Included : {title_only_included:>6}  (matched on title alone)",
        f"    Excluded : {title_only_excluded:>6}  (no match on title; abstract/keywords unavailable)",
        "",
    ]

    lines += ["KEYWORD HIT COUNTS (papers matched per keyword, sorted)", "-" * 40]
    for label, count in sorted(keyword_hit_counts.items(), key=lambda x: -x[1]):
        bar = "#" * min(count // 50, 50)
        lines.append(f"  {label:<45}: {count:>5}  {bar}")
    lines.append("")

    lines += [sep, f"  Included CSV -> {included_csv}", f"  Excluded CSV -> {excluded_csv}", sep]

    report = "\n".join(lines)
    safe   = report.encode(sys.stdout.encoding or "utf-8", errors="replace") \
                   .decode(sys.stdout.encoding or "utf-8", errors="replace")
    print(safe)

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n[Done]  Included -> {included_csv}  ({len(included)} rows)")
    print(f"[Done]  Excluded -> {excluded_csv}  ({len(excluded)} rows)")
    print(f"[Done]  Report   -> {report_file}")


if __name__ == "__main__":
    main()
