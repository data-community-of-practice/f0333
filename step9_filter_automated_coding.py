"""
step9_filter_automated_coding.py
--------------------------
Filters icd_included.csv to keep only papers related to AUTOMATED ICD coding.
Checks title, abstract, and keywords fields.
Produces:
  - auto_icd_included.csv   : matched papers
  - auto_icd_excluded.csv   : non-matched papers
  - auto_coding_report.txt
"""

import os
import re
import csv
import sys
import argparse
from collections import defaultdict

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV    = os.path.join(BASE_DIR, "output", "icd_relevant.csv")
INCLUDED_CSV = os.path.join(BASE_DIR, "output", "automated_coding.csv")
EXCLUDED_CSV = os.path.join(BASE_DIR, "output", "automated_excluded.csv")
REPORT_FILE  = os.path.join(BASE_DIR, "output", "automated_coding_report.txt")

SEARCH_FIELDS = ["title", "abstract", "keywords"]

# ── Keyword definitions ───────────────────────────────────────────────────────
# Format: "Label": (pattern_string, "category")

AUTOMATION_KEYWORDS = {

    # ── General automation terms ──────────────────────────────────────────────
    "Automated":
        (r'\bautomated\b',                              "General Automation"),
    "Automatic":
        (r'\bautomatic(ally)?\b',                       "General Automation"),
    "Computer-Assisted":
        (r'\bcomputer[-\s]assisted\b',                  "General Automation"),
    "Auto-coding / Autocoding":
        (r'\bauto[-]?cod(ing|e|es|ed)\b',               "General Automation"),
    "CAC (Computer-Assisted Coding)":
        (r'\bCAC\b',                                    "General Automation"),
    "Algorithm":
        (r'\balgorithm(s|ic)?\b',                       "General Automation"),
    "Computational":
        (r'\bcomputational\b',                          "General Automation"),
    "Rule-based system":
        (r'\brule[-\s]based\b',                         "General Automation"),
    "Expert system":
        (r'\bexpert system\b',                          "General Automation"),
    "Decision support":
        (r'\bdecision support\b',                       "General Automation"),
    "Clinical decision support":
        (r'\bclinical decision support\b',              "General Automation"),

    # ── AI / ML general ───────────────────────────────────────────────────────
    "AI":
        (r'\bAI\b',                                     "AI/ML General"),
    "Artificial Intelligence":
        (r'\bartificial intelligence\b',                "AI/ML General"),
    "ML":
        (r'\bML\b',                                     "AI/ML General"),
    "Machine Learning":
        (r'\bmachine learning\b',                       "AI/ML General"),
    "Deep Learning":
        (r'\bdeep learning\b',                          "AI/ML General"),
    "Model (predictive)":
        (r'\b(predictive|classification|learning) model\b', "AI/ML General"),
    "Prediction":
        (r'\bprediction\b',                             "AI/ML General"),

    # ── NLP & text processing ─────────────────────────────────────────────────
    "NLP":
        (r'\bNLP\b',                                    "NLP"),
    "Natural Language Processing":
        (r'\bnatural language processing\b',            "NLP"),
    "Text Classification":
        (r'\btext classification\b',                    "NLP"),
    "Text Mining":
        (r'\btext mining\b',                            "NLP"),
    "Data Mining":
        (r'\bdata mining\b',                            "NLP"),
    "Information Extraction":
        (r'\binformation extraction\b',                 "NLP"),
    "Named Entity Recognition":
        (r'\bnamed entity recognition\b|\bNER\b',       "NLP"),
    "Relation Extraction":
        (r'\brelation extraction\b',                    "NLP"),
    "Clinical NLP":
        (r'\bclinical (NLP|natural language processing)\b', "NLP"),
    "Biomedical NLP":
        (r'\bbiomedical (NLP|natural language processing)\b', "NLP"),
    "Concept Extraction":
        (r'\bconcept extraction\b',                     "NLP"),
    "Entity Recognition":
        (r'\bentity recognition\b',                     "NLP"),

    # ── Neural network architectures ─────────────────────────────────────────
    "Neural Network":
        (r'\bneural network\b',                         "Neural Networks"),
    "Deep Neural Network":
        (r'\bdeep neural network\b',                    "Neural Networks"),
    "Convolutional Neural Network":
        (r'\bconvolutional neural\b|\bCNN\b',           "Neural Networks"),
    "Recurrent Neural Network":
        (r'\brecurrent neural\b|\bRNN\b',               "Neural Networks"),
    "LSTM":
        (r'\bLSTM\b',                                   "Neural Networks"),
    "BiLSTM":
        (r'\bBiLSTM\b|\bBi-LSTM\b|\bbidirectional LSTM\b', "Neural Networks"),
    "GRU":
        (r'\bGRU\b',                                    "Neural Networks"),
    "Feedforward Network":
        (r'\bfeedforward (neural )?network\b',          "Neural Networks"),
    "Graph Neural Network":
        (r'\bgraph neural network\b|\bGNN\b',           "Neural Networks"),

    # ── Transformers & LLMs ───────────────────────────────────────────────────
    "Transformer":
        (r'\btransformer\b',                            "Transformers/LLMs"),
    "BERT":
        (r'\bBERT\b',                                   "Transformers/LLMs"),
    "BioBERT":
        (r'\bBioBERT\b',                                "Transformers/LLMs"),
    "ClinicalBERT":
        (r'\bClinicalBERT\b|\bClinical BERT\b',         "Transformers/LLMs"),
    "RoBERTa":
        (r'\bRoBERTa\b',                                "Transformers/LLMs"),
    "XLNet":
        (r'\bXLNet\b',                                  "Transformers/LLMs"),
    "DistilBERT":
        (r'\bDistilBERT\b',                             "Transformers/LLMs"),
    "GPT":
        (r'\bGPT[-\s]?\d*\b',                           "Transformers/LLMs"),
    "LLM":
        (r'\bLLM\b',                                    "Transformers/LLMs"),
    "Large Language Model":
        (r'\blarge language model\b',                   "Transformers/LLMs"),
    "Attention Mechanism":
        (r'\battention mechanism\b',                    "Transformers/LLMs"),
    "Self-Attention":
        (r'\bself[-\s]attention\b',                     "Transformers/LLMs"),
    "Encoder-Decoder":
        (r'\bencoder[-\s]decoder\b',                    "Transformers/LLMs"),
    "Seq2Seq":
        (r'\bseq2seq\b|\bsequence[-\s]to[-\s]sequence\b', "Transformers/LLMs"),
    "Pre-trained model":
        (r'\bpre[-\s]trained (model|language model)\b', "Transformers/LLMs"),
    "Fine-tuning":
        (r'\bfine[-\s]tun(ing|ed)\b',                  "Transformers/LLMs"),

    # ── Learning paradigms ────────────────────────────────────────────────────
    "Supervised Learning":
        (r'\bsupervised learning\b',                    "Learning Paradigms"),
    "Unsupervised Learning":
        (r'\bunsupervised learning\b',                  "Learning Paradigms"),
    "Semi-Supervised":
        (r'\bsemi[-\s]supervised\b',                    "Learning Paradigms"),
    "Self-Supervised":
        (r'\bself[-\s]supervised\b',                    "Learning Paradigms"),
    "Reinforcement Learning":
        (r'\breinforcement learning\b',                 "Learning Paradigms"),
    "Transfer Learning":
        (r'\btransfer learning\b',                      "Learning Paradigms"),
    "Multi-Task Learning":
        (r'\bmulti[-\s]task learning\b',                "Learning Paradigms"),
    "Few-Shot":
        (r'\bfew[-\s]shot\b',                           "Learning Paradigms"),
    "Zero-Shot":
        (r'\bzero[-\s]shot\b',                          "Learning Paradigms"),
    "Active Learning":
        (r'\bactive learning\b',                        "Learning Paradigms"),
    "Contrastive Learning":
        (r'\bcontrastive learning\b',                   "Learning Paradigms"),

    # ── Classification & labeling ─────────────────────────────────────────────
    "Multi-Label Classification":
        (r'\bmulti[-\s]label\b',                        "Classification"),
    "Multi-Class Classification":
        (r'\bmulti[-\s]class\b',                        "Classification"),
    "Hierarchical Classification":
        (r'\bhierarchical (classification|label|coding)\b', "Classification"),
    "Label Embedding":
        (r'\blabel embedding\b',                        "Classification"),
    "Code Prediction":
        (r'\bcode prediction\b',                        "Classification"),

    # ── Traditional ML algorithms ─────────────────────────────────────────────
    "Support Vector Machine":
        (r'\bsupport vector (machine|classifier)?\b|\bSVM\b', "Traditional ML"),
    "Random Forest":
        (r'\brandom forest\b',                          "Traditional ML"),
    "Decision Tree":
        (r'\bdecision tree\b',                          "Traditional ML"),
    "XGBoost / GBM":
        (r'\bXGBoost\b|\bgradient boosting\b|\bLightGBM\b|\bCatBoost\b', "Traditional ML"),
    "Naive Bayes":
        (r'\bnaive bayes\b',                            "Traditional ML"),
    "Logistic Regression":
        (r'\blogistic regression\b',                    "Traditional ML"),
    "K-Nearest Neighbours":
        (r'\bk[-\s]nearest\b|\bkNN\b',                 "Traditional ML"),

    # ── Embeddings & representations ──────────────────────────────────────────
    "Word Embedding":
        (r'\bword embedding\b',                         "Embeddings"),
    "Word2Vec":
        (r'\bword2vec\b',                               "Embeddings"),
    "GloVe":
        (r'\bGloVe\b|\bglove embedding\b',              "Embeddings"),
    "FastText":
        (r'\bfasttext\b',                               "Embeddings"),
    "ELMo":
        (r'\bELMo\b',                                   "Embeddings"),
    "Document Embedding":
        (r'\bdocument embedding\b|\bdoc2vec\b',         "Embeddings"),
    "Sentence Embedding":
        (r'\bsentence embedding\b|\bsentence[-\s]BERT\b|\bSBERT\b', "Embeddings"),

    # ── Feature extraction ────────────────────────────────────────────────────
    "TF-IDF":
        (r'\bTF[-\s]?IDF\b',                            "Feature Extraction"),
    "Bag of Words":
        (r'\bbag[-\s]of[-\s]words\b|\bBoW\b',          "Feature Extraction"),
    "N-gram":
        (r'\bn[-\s]gram\b',                             "Feature Extraction"),
    "Feature Extraction":
        (r'\bfeature extraction\b',                     "Feature Extraction"),
    "Feature Engineering":
        (r'\bfeature engineering\b',                    "Feature Extraction"),

    # ── Clinical NLP tools ────────────────────────────────────────────────────
    "MetaMap":
        (r'\bMetaMap\b',                                "Clinical NLP Tools"),
    "cTAKES":
        (r'\bcTAKES\b',                                 "Clinical NLP Tools"),
    "MedSpaCy / spaCy":
        (r'\bMedSpaCy\b|\bspaCy\b',                    "Clinical NLP Tools"),
    "UMLS":
        (r'\bUMLS\b|\bunified medical language system\b', "Clinical NLP Tools"),
    "QuickUMLS":
        (r'\bQuickUMLS\b',                              "Clinical NLP Tools"),

    # ── Knowledge representation ──────────────────────────────────────────────
    "Knowledge Graph":
        (r'\bknowledge graph\b',                        "Knowledge Representation"),
    "Ontology":
        (r'\bontolog(y|ies|ical)\b',                   "Knowledge Representation"),
    "Knowledge Base":
        (r'\bknowledge base\b',                         "Knowledge Representation"),
    "Semantic Similarity":
        (r'\bsemantic similarity\b',                    "Knowledge Representation"),

    # ── Evaluation & benchmarking ─────────────────────────────────────────────
    "Benchmark / Dataset":
        (r'\bbenchmark\b|\bshared task\b',              "Evaluation"),
    "Annotation":
        (r'\bannotation\b|\bannotated corpus\b',        "Evaluation"),
    "Gold Standard":
        (r'\bgold standard\b',                          "Evaluation"),
    "F1 Score / Precision / Recall":
        (r'\bF1[-\s]score\b|\bmicro[-\s]F1\b|\bmacro[-\s]F1\b', "Evaluation"),
    "AUC / ROC":
        (r'\bAUC\b|\bROC curve\b',                      "Evaluation"),
}

# Pre-compile (case-insensitive)
COMPILED = {
    label: (re.compile(pattern, re.IGNORECASE | re.DOTALL), category)
    for label, (pattern, category) in AUTOMATION_KEYWORDS.items()
}


def resolve_columns(fieldnames):
    """Map logical field names -> actual CSV headers, case-insensitively
    (works with 'title' or 'Title'); find 'source' under any casing, else 'type'."""
    lower = {fn.strip().lower(): fn for fn in (fieldnames or []) if fn}
    cols = {f: lower.get(f) for f in SEARCH_FIELDS}
    cols["source"] = lower.get("source") or lower.get("type")
    return cols


def cell(row, colname):
    return (row.get(colname) or "") if colname else ""


def find_matches(row, cols):
    """Return {label: [fields_matched]} for all matching keywords."""
    texts = {f: cell(row, cols.get(f)) for f in SEARCH_FIELDS}
    matches = defaultdict(list)
    for label, (regex, _) in COMPILED.items():
        for field, text in texts.items():
            if text and regex.search(text):
                matches[label].append(field)
    return dict(matches)


def main():
    ap = argparse.ArgumentParser(description="Filter ICD-relevant papers to AUTOMATED-coding ones.")
    ap.add_argument("input", nargs="?", default=INPUT_CSV,
                    help="input CSV (default: icd_included.csv)")
    ap.add_argument("--outdir", default=os.path.join(BASE_DIR, "output"),
                    help="directory for output files (default: alongside script)")
    ap.add_argument("--out", default=None,
                    help="explicit path for the INCLUDED csv; excluded csv and report "
                         "derived from it (<base>_excluded.csv, <base>_report.txt). "
                         "Overrides the default <stem>__auto_included.csv naming.")
    args = ap.parse_args()

    input_csv = os.path.abspath(args.input)
    stem = os.path.splitext(os.path.basename(input_csv))[0]
    if args.out:
        base = os.path.splitext(args.out)[0]
        included_csv = args.out
        excluded_csv = base + "_excluded.csv"
        report_file  = base + "_report.txt"
    else:
        included_csv = os.path.join(args.outdir, f"{stem}__auto_included.csv")
        excluded_csv = os.path.join(args.outdir, f"{stem}__auto_excluded.csv")
        report_file  = os.path.join(args.outdir, f"{stem}__auto_coding_report.txt")

    included = []
    excluded = []

    keyword_hits   = defaultdict(int)
    category_hits  = defaultdict(int)
    field_hits     = defaultdict(int)
    source_inc     = defaultdict(int)
    source_exc     = defaultdict(int)
    title_only_inc = 0
    title_only_exc = 0

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

            row["auto_matched_keywords"] = " | ".join(sorted(matches.keys()))
            row["auto_matched_fields"]   = " | ".join(
                sorted({f for fields in matches.values() for f in fields})
            )
            row["auto_matched_categories"] = " | ".join(
                sorted({COMPILED[lbl][1] for lbl in matches})
            )

            if matches:
                included.append(row)
                source_inc[src] += 1
                if is_title_only:
                    title_only_inc += 1
                for label, fields in matches.items():
                    keyword_hits[label] += 1
                    category_hits[COMPILED[label][1]] += 1
                    for f in fields:
                        field_hits[f] += 1
            else:
                excluded.append(row)
                source_exc[src] += 1
                if is_title_only:
                    title_only_exc += 1

    # ── Write CSVs ────────────────────────────────────────────────────────────
    extra = ["auto_matched_keywords", "auto_matched_fields", "auto_matched_categories"]
    out_fields = list(fieldnames) + [c for c in extra if c not in fieldnames]

    with open(included_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        w.writerows(included)

    with open(excluded_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        w.writerows(excluded)

    # ── Report ────────────────────────────────────────────────────────────────
    total = len(included) + len(excluded)
    lines = []
    sep   = "=" * 65

    lines += [sep, "  AUTOMATED ICD CODING — RELEVANCE FILTER REPORT", sep, ""]

    lines += ["OVERVIEW", "-" * 40]
    lines += [
        f"  Input (ICD-relevant papers) : {total:>6}",
        f"  Automation-relevant kept    : {len(included):>6}  ({len(included)/total*100:.1f}%)",
        f"  Not automation-relevant     : {len(excluded):>6}  ({len(excluded)/total*100:.1f}%)",
        "",
    ]

    lines += ["INCLUDED — BY SOURCE", "-" * 40]
    for src in sorted(source_inc | source_exc):
        tot = source_inc[src] + source_exc[src]
        pct = source_inc[src] / tot * 100 if tot else 0
        lines.append(
            f"  {src:<10}: {source_inc[src]:>5} included  /  {tot:>5} total  ({pct:.1f}%)"
        )
    lines.append("")

    lines += ["MATCH FIELD BREAKDOWN", "-" * 40]
    lines += [
        f"  Title matched    : {field_hits['title']:>5}",
        f"  Abstract matched : {field_hits['abstract']:>5}",
        f"  Keywords matched : {field_hits['keywords']:>5}",
        f"  (counts overlap — one paper can match in multiple fields)",
        "",
    ]

    lines += ["DATA COVERAGE NOTE", "-" * 40]
    lines += [
        f"  Title-only records (no abstract/keywords):",
        f"    Included : {title_only_inc:>5}  (matched on title alone)",
        f"    Excluded : {title_only_exc:>5}  (no match; abstract/keywords unavailable)",
        "",
    ]

    lines += ["KEYWORD CATEGORY HITS (papers matched per category)", "-" * 40]
    for cat, count in sorted(category_hits.items(), key=lambda x: -x[1]):
        bar = "#" * min(count // 20, 50)
        lines.append(f"  {cat:<30}: {count:>5}  {bar}")
    lines.append("")

    lines += ["KEYWORD HIT COUNTS (papers matched per keyword, sorted)", "-" * 40]
    for label, count in sorted(keyword_hits.items(), key=lambda x: -x[1]):
        cat = COMPILED[label][1]
        bar = "#" * min(count // 20, 50)
        lines.append(f"  {label:<45}: {count:>5}  {bar}")
    lines.append("")

    lines += [
        sep,
        f"  Included CSV -> {included_csv}",
        f"  Excluded CSV -> {excluded_csv}",
        sep,
    ]

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
