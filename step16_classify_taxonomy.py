#!/usr/bin/env python3
"""
step16_classify_taxonomy.py
---------------------------
Classifies every paper in output/icd_verified.csv into the 11-category taxonomy
that was inductively discovered from this corpus.

Uses Anthropic Messages Batches API (one request per paper, cached system
prompt). Resume-safe: already-classified papers are skipped on re-run.

Produces:
  output/taxonomy_classified.csv        — original data + 4 classification columns
  output/taxonomy_classification_report.txt
  output/taxonomy_classify_results.jsonl — raw per-paper results (audit trail)

Usage:
    python step16_classify_taxonomy.py
    python step16_classify_taxonomy.py --resume      # pick up a running batch
    python step16_classify_taxonomy.py --merge-only  # skip API, just write CSVs
"""

import os
import json
import time
import argparse
from collections import Counter

import anthropic
import pandas as pd

BASE      = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(BASE, "output", "icd_verified.csv")
OUT_DIR   = os.path.join(BASE, "output")
RESULTS_JSONL = os.path.join(BASE, "output", "taxonomy_classify_results.jsonl")
STATE_PATH    = os.path.join(BASE, "output", "taxonomy_classify_state.json")
MODEL = "claude-sonnet-4-6"

MISSING = {"", "nan", "none", "na", "null", "n/a"}

TAXONOMY_TEXT = """\
1. Automated ICD Coding Engines (text -> codes)
   Papers build computational systems that read clinical free text (discharge summaries,
   pathology/operative reports, death certificates) and emit ICD/ICD-O codes, treated as
   multi-label classification or generation. The contribution is architectural or training-method
   innovation (CNN-attention, BERT, graph/hyperbolic nets, contrastive, few-shot, LLM reasoning),
   and the code is the PREDICTION TARGET. Sub-strands include multilingual/death-certificate
   coding (CLEF/CodiEsp-style, low-resource, short text) and shared-task/benchmark overviews.
   Key signals: free-text input + ICD code output; F1/MAP/Hit@k on MIMIC or a shared-task
   corpus; label hierarchy, rare-code handling, or model architecture as the contribution.

2. Computable Phenotyping & Case-Finding
   The question is "does this patient actually have condition X?" Papers build or validate
   algorithms (ICD codes +/- labs/meds/NLP) to assemble a disease cohort, almost always
   validated against chart review or an instrument and reported as PPV/sensitivity/specificity.
   The recurring move: codes alone miss cases and NLP/ML recovers them; the ICD code is the
   IMPERFECT BASELINE, not the goal. Beneficiary is a researcher or registrar needing a clean
   cohort.
   Key signals: named condition; gold standard; sensitivity/PPV reporting; "codes undercount /
   NLP improves recall" framing.

3. Clinical Risk & Outcome Prediction
   Papers forecast a future patient-level event (mortality, readmission, length of stay, surgical
   candidacy, exacerbation, ADE, hypoglycaemia) from structured EHR/claims features. ICD codes
   enter as INPUT FEATURES, never as the target, and the deliverable is a prognostic tool or
   decision-support score for a clinician or planner.
   Key signals: future target variable; coded history as features; prognostic/decision framing;
   AUC/calibration metrics on a future outcome.

4. Epidemiology, Disease Burden & Surveillance
   Papers use ICD-coded population/registry/claims data to estimate incidence, prevalence, cost,
   disparities, comorbidity, or safety signals, or to monitor disease activity in near-real time
   (flu, SARI, injury, vaccine safety, cause-of-death surveillance). The deliverable is
   epidemiological or public-health knowledge, not a tool; the code is a MEASUREMENT INSTRUMENT
   used at face value. Verbal-autopsy and vital-statistics studies sit here.
   Key signals: cohort/case-control/trend design; population or registry substrate;
   burden/cost/incidence as the headline; public-health or policy audience.

5. Terminology, Ontology Engineering & Cross-System Mapping
   The artifact is a bridge or formal structure between vocabularies: crosswalks
   (ICD<->SNOMED/MedDRA/UMLS/AIS, ICD-9<->ICD-10), ontologies, OWL/SWRL diagnostic rules,
   post-coordination, multilingual dictionaries, code-embedding similarity. The problem is
   semantic interoperability across systems, not coding a single note.
   Key signals: two or more coding systems named; crosswalk/mapping/ontology/harmonization/
   interoperability; output is a rule set or aligned vocabulary.

6. Image, Signal & Omics Disease Classification
   Input is non-text biomedical data — radiographs, CT/OCT/MRI/SPECT, ECG/EEG/EMG/fNIRS,
   RNA-seq — classified into disease categories, usually contributing a neural architecture.
   ICD/PheCodes appear only as the label or phenotype anchor; the real subject is the
   imaging/signal/omics method.
   Key signals: non-textual modality as primary input; vision/signal-processing architecture;
   ICD mentioned only as ground-truth source.

7. Data Quality, Code Validation & Auditing
   Papers interrogate how trustworthy the coded data itself is: validating algorithms against gold
   standards, measuring undercoding, ICD-9->10 disagreement, concept/temporal drift, model
   fairness across demographics, dataset representativeness, and methods to make routine data
   research-ready (privacy-preserving linkage, completeness/selection-bias adjustment).
   Key signals: codes/models are the OBJECT OF STUDY; agreement/disagreement, drift, bias,
   completeness metrics; no new disease finding produced.

8. Classification-System Design, Standards, Policy & Coding Workflow
   Papers work at the level of the classification infrastructure and its human use: ICD-11
   architecture and national rollout, reimbursement incentives, code-set engineering methodology,
   coder-vs-clinician debates, ICD-10 transition management, and AI's impact on HIM staffing.
   The deliverable is a framework, recommendation, or organisational analysis, not a classifier.
   Key signals: governance/policy/workflow framing; ICD-11 or HIM operations; recommendations
   rather than metrics.

9. Mental Health Classification & Diagnosis
   Papers interrogate whether a psychiatric or behavioural diagnostic category is valid or
   coherent — historical/philological recovery of a symptom, philosophical critique,
   dimensional/network models, DSM/ICD/HiTOP operationalization, subtyping (ASD, delirium),
   comorbidity structure, psychometric scale validation. ICD is the diagnostic FRAME UNDER
   EXAMINATION, not an object of computation.
   Key signals: a construct is questioned/defined; psychiatric/behavioural focus; conceptual,
   network, or psychometric evidence; no coding-performance metrics.

10. Clinical Information Extraction (non-coding)
    NLP applied to narrative text to surface a specific piece of information other than an ICD
    code — smoking status, gendered-language bias, drug-disease links, documentation gaps,
    chronic-pain mentions — or mining of non-patient literature (guidelines, policy) for
    structured knowledge. The output augments or audits structured data rather than predicting
    codes.
    Key signals: free-text input; target is an entity/relation/attribute, NOT a code; output
    feeds or audits a database.

11. Reviews, Surveys & Methodological Overviews
    Secondary literature synthesising methods, applications, and challenges across automated
    coding, clinical NLP, or phenotyping. The deliverable is a map of a subfield, not a new
    system or finding.
    Key signals: systematic/scoping/narrative review structure; no primary dataset;
    cross-cutting coverage.
"""

SYSTEM_PROMPT = f"""\
You are classifying research papers into a taxonomy that was inductively discovered from this
corpus. Assign each paper to exactly ONE category.

TAXONOMY:
{TAXONOMY_TEXT}

ASSIGNMENT RULES:
- Assign the category where the paper's PRIMARY DELIVERABLE lives.
- If a paper spans two categories, assign the primary one and note the secondary in your reason.
- The key axis is the ROLE ICD plays:
    target         -> cats 1, 4 (epidemiology uses codes as measurement)
    imperfect base -> cat 2
    input feature  -> cat 3
    mapping object -> cat 5
    object of study-> cats 7, 8, 9
    label only     -> cat 6
    non-code target-> cat 10
- Cat 11 is ONLY for pure reviews — no new model, system, or dataset built.
"""

CLASSIFY_TOOL = {
    "name": "classify_paper",
    "description": "Assign this paper to one taxonomy category.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category_number": {
                "type": "integer",
                "minimum": 1,
                "maximum": 11,
                "description": "The primary taxonomy category (1-11).",
            },
            "confidence": {
                "type": "string",
                "enum": ["HIGH", "MEDIUM", "LOW"],
                "description": (
                    "HIGH — clearly fits one category. "
                    "MEDIUM — fits well but has secondary overlap. "
                    "LOW — genuinely ambiguous or sparse information."
                ),
            },
            "reason": {
                "type": "string",
                "description": (
                    "One sentence (under 20 words) explaining the assignment. "
                    "If it spans two categories, name the secondary one."
                ),
            },
            "secondary_category": {
                "type": "integer",
                "minimum": 1,
                "maximum": 11,
                "description": "Secondary category number, if the paper meaningfully spans two (optional).",
            },
        },
        "required": ["category_number", "confidence", "reason"],
    },
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def clean(v):
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() in MISSING else s


def paper_id(row):
    return clean(row.get("DOI")) or clean(row.get("Title"))


def load_done(path):
    done = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    done[r["paper_id"]] = r
                except Exception:
                    pass
    return done


def build_requests(df, done):
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    requests, id_map = [], {}
    for i, row in df.iterrows():
        pid = paper_id(row)
        if pid in done:
            continue
        title    = clean(row.get("Title"))
        obj_     = clean(row.get("meta_study_objective"))
        method   = clean(row.get("meta_method_summary"))
        contrib  = clean(row.get("meta_main_contribution"))
        abstract = clean(row.get("Abstract"))

        parts = [f"TITLE: {title}"]
        if obj_:
            parts.append(f"OBJECTIVE: {obj_}")
        if method:
            parts.append(f"METHOD: {method}")
        if contrib:
            parts.append(f"CONTRIBUTION: {contrib}")
        if not (obj_ or method or contrib) and abstract:
            parts.append(f"ABSTRACT: {abstract[:400]}")

        body = "\n".join(parts)
        cid = f"req-{i:05d}"
        id_map[cid] = pid

        requests.append(Request(
            custom_id=cid,
            params=MessageCreateParamsNonStreaming(
                model=MODEL,
                max_tokens=200,
                system=[{"type": "text", "text": SYSTEM_PROMPT,
                         "cache_control": {"type": "ephemeral"}}],
                tools=[CLASSIFY_TOOL],
                tool_choice={"type": "tool", "name": "classify_paper"},
                messages=[{"role": "user", "content": body}],
            ),
        ))
    return requests, id_map


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume",     action="store_true")
    ap.add_argument("--merge-only", action="store_true")
    args = ap.parse_args()

    df = pd.read_csv(INPUT_CSV, dtype=str)
    print(f"Loaded {len(df)} papers from {INPUT_CSV}")

    if args.merge_only:
        done = load_done(RESULTS_JSONL)
        print(f"Merge-only: {len(done)} results found.")
        _write_outputs(df, done)
        return

    client = anthropic.Anthropic(max_retries=5)
    done   = load_done(RESULTS_JSONL)

    state = {}
    if os.path.exists(STATE_PATH) and args.resume:
        state = json.load(open(STATE_PATH, encoding="utf-8"))
        print(f"Resuming batch {state['batch_id']} ({len(done)} already retrieved).")
    else:
        if os.path.exists(STATE_PATH):
            os.remove(STATE_PATH)
        requests, id_map = build_requests(df, done)
        print(f"Papers to classify : {len(requests)}  (already done: {len(done)})")
        if not requests:
            print("Nothing to submit — all papers already classified.")
        else:
            batch = client.messages.batches.create(requests=requests)
            state = {"batch_id": batch.id, "id_map": id_map}
            json.dump(state, open(STATE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"Created batch {batch.id} with {len(requests)} requests.")

    if not state:
        _write_outputs(df, done)
        return

    batch_id = state["batch_id"]
    id_map   = state["id_map"]

    while True:
        batch = client.messages.batches.retrieve(batch_id)
        c = batch.request_counts
        print(f"  [{batch.processing_status}]  "
              f"processing={c.processing}  succeeded={c.succeeded}  "
              f"errored={c.errored}  expired={c.expired}")
        if batch.processing_status == "ended":
            break
        time.sleep(30)

    done = load_done(RESULTS_JSONL)
    n_ok = n_err = 0
    with open(RESULTS_JSONL, "a", encoding="utf-8") as out_f:
        for result in client.messages.batches.results(batch_id):
            pid = id_map.get(result.custom_id, result.custom_id)
            if pid in done:
                continue
            if result.result.type != "succeeded":
                n_err += 1
                print(f"  ! {str(pid)[:60]}: {result.result.type}")
                continue
            msg   = result.result.message
            block = next((b for b in msg.content if b.type == "tool_use"), None)
            if block is None:
                n_err += 1
                print(f"  ! {str(pid)[:60]}: no tool_use block")
                continue
            rec = dict(block.input)
            rec["paper_id"] = pid
            rec["_usage"] = {
                "input":      msg.usage.input_tokens,
                "output":     msg.usage.output_tokens,
                "cache_read": getattr(msg.usage, "cache_read_input_tokens", 0),
            }
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_ok += 1

    print(f"Retrieved: ok={n_ok}  errors={n_err}")
    if os.path.exists(STATE_PATH):
        os.remove(STATE_PATH)

    done = load_done(RESULTS_JSONL)
    _write_outputs(df, done)


CATEGORY_NAMES = {
    1:  "Automated ICD Coding Engines (text -> codes)",
    2:  "Computable Phenotyping & Case-Finding",
    3:  "Clinical Risk & Outcome Prediction",
    4:  "Epidemiology, Disease Burden & Surveillance",
    5:  "Terminology, Ontology Engineering & Cross-System Mapping",
    6:  "Image, Signal & Omics Disease Classification",
    7:  "Data Quality, Code Validation & Auditing",
    8:  "Classification-System Design, Standards, Policy & Coding Workflow",
    9:  "Mental Health Classification & Diagnosis",
    10: "Clinical Information Extraction (non-coding)",
    11: "Reviews, Surveys & Methodological Overviews",
}


def _write_outputs(df, done):
    rows = []
    for _, row in df.iterrows():
        pid = paper_id(row)
        rec = done.get(pid, {})
        row = row.copy()
        cat = rec.get("category_number", "")
        row["taxonomy_category"]       = cat
        row["taxonomy_category_name"]  = CATEGORY_NAMES.get(cat, "") if cat else ""
        row["taxonomy_confidence"]     = rec.get("confidence", "")
        row["taxonomy_reason"]         = rec.get("reason", "")
        row["taxonomy_secondary"]      = rec.get("secondary_category", "")
        rows.append(row)

    out_df = pd.DataFrame(rows)
    out_path = os.path.join(OUT_DIR, "taxonomy_classified.csv")
    out_df.to_csv(out_path, index=False)

    # ── Report ─────────────────────────────────────────────────────────────────
    classified = out_df[out_df["taxonomy_category"] != ""]
    cat_counts  = Counter(int(r["taxonomy_category"]) for _, r in classified.iterrows()
                          if str(r["taxonomy_category"]).isdigit())
    conf_counts = Counter(classified["taxonomy_confidence"])
    total = len(df)
    n_cls = len(classified)

    sep = "=" * 65
    lines = [
        sep,
        "  TAXONOMY CLASSIFICATION REPORT",
        sep,
        "",
        "OVERVIEW",
        "-" * 40,
        f"  Input papers       : {total:>6}",
        f"  Classified         : {n_cls:>6}  ({n_cls/total*100:.1f}%)",
        f"  Unclassified       : {total-n_cls:>6}",
        "",
        "CONFIDENCE DISTRIBUTION",
        "-" * 40,
    ]
    for conf in ("HIGH", "MEDIUM", "LOW"):
        c = conf_counts.get(conf, 0)
        lines.append(f"  {conf:<8}: {c:>5}  ({c/n_cls*100:.1f}%)" if n_cls else f"  {conf}: 0")
    lines += ["", "PAPERS PER CATEGORY", "-" * 40]
    for cat_num in range(1, 12):
        cnt  = cat_counts.get(cat_num, 0)
        name = CATEGORY_NAMES[cat_num]
        pct  = cnt / total * 100 if total else 0
        lines.append(f"  Cat {cat_num:>2}  {cnt:>5}  ({pct:4.1f}%)  {name}")
    lines += [
        "",
        sep,
        f"  Output CSV -> {out_path}",
        sep,
    ]

    report = "\n".join(lines)
    print("\n" + report)

    report_path = os.path.join(OUT_DIR, "taxonomy_classification_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n[Done]  Classified CSV -> {out_path}  ({total} rows)")
    print(f"[Done]  Report         -> {report_path}")


if __name__ == "__main__":
    main()
