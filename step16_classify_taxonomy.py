#!/usr/bin/env python3
"""
step16_classify_taxonomy.py
--------------------
Classifies every paper in icd_verified.csv into the 10-category taxonomy
that was inductively discovered from this corpus.

Uses Anthropic Messages Batches API (one request per paper, cached system
prompt). Resume-safe: already-classified papers are skipped on re-run.

Produces:
  outputs/taxonomy_classified.csv   — original data + 4 classification columns
  outputs/taxonomy_classification_report.txt
  taxonomy_classify_results.jsonl   — raw per-paper results (audit trail)

Usage:
    python classify_taxonomy.py
    python classify_taxonomy.py --resume      # pick up a running batch
    python classify_taxonomy.py --merge-only  # skip API, just write CSVs
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
1. Automatic ICD/Procedure Coding from Clinical Text
   Papers whose explicit deliverable is a predicted ICD/DRG code from narrative or structured
   input, framed as replacing or accelerating human coders and scored on coding F1/accuracy.
   Spans novel architectures (attention, contrastive, graph/hierarchy-aware, LLM) through to
   deployable, language-specific coders, plus work auditing the task itself (long-tail, fairness,
   interpretability). ICD is the TARGET.
   Key signals: MIMIC/shared-task benchmarks; micro/macro-F1 on a code label space;
   "automatic coding," "label hierarchy," "long-tail codes."

2. Cause-of-Death, Mortality & Injury Coding
   A tight cluster coding verbatim cause-of-death text, death certificates, autopsy/forensic and
   injury narratives for vital statistics and surveillance. Methods include dictionaries,
   rule-based underlying-cause selection, and shared-task systems. ICD is the TARGET, mortality
   domain.
   Key signals: "underlying cause of death," death certificates, multilingual mortality shared
   tasks, registry/statistics framing.

3. Phenotyping, Case-Finding & Code Validation
   Papers interrogating whether patients with a condition can be reliably identified — either by
   validating existing code definitions against chart review (PPV/sensitivity) or by building
   NLP/ML pipelines that recover cases codes miss. Includes clinical-NLP extraction when the goal
   is cohort or condition labeling. ICD is the SUSPECT; recurring conclusion: "codes alone are
   insufficient."
   Key signals: chart-review gold standard, PPV/sensitivity reporting, "underascertainment,"
   notes-vs-codes comparison, named-disease cohort.

4. Clinical Risk Prediction, Outcome Modeling & Decision Support
   Models trained on structured EHR/claims to forecast an outcome (mortality, readmission, onset,
   cost, LOS) or trigger an alert. ICD codes are FEATURES, not the prediction target. Includes
   explainability (SHAP/xAI) and a minority evaluating deployed decision-support effects on
   clinician behavior.
   Key signals: AUROC/calibration on an outcome, "risk score," "readmission/mortality
   prediction," codes used as covariates, alert/CDS evaluation.

5. Terminology Mapping, Ontologies & Knowledge Representation
   Engineering or evaluating the semantic scaffolding: crosswalks (ICD↔SNOMED↔ORPHA↔ICD-11),
   OWL ontologies, code embeddings, knowledge graphs, LLM-driven structured extraction onto a
   vocabulary. Output is a reusable mapping/representation, not a patient-level result. ICD is
   the OBJECT OF STUDY as a vocabulary.
   Key signals: "mapping/crosswalk," ontology/OWL, embeddings, entity alignment,
   interoperability, knowledge graph.

6. Epidemiology, Health-Services & Outcomes Studies Using Coded Data
   Substantive clinical, epidemiological, comorbidity, safety-signal, utilization, or cost
   questions answered by analyzing ICD-coded populations. ICD is the COHORT-DEFINING INPUT;
   the contribution is domain knowledge, not a tool or method.
   Key signals: incidence/prevalence/association estimates, claims-database utilization/cost,
   retrospective cohort, phenome-wide screening.

7. Classification Systems, Coding Practice & Data Infrastructure
   Papers about the apparatus around codes: ICD-11 architecture and authoring, version
   transitions (9→10→11), coder behavior and data-quality auditing, assembled data resources
   (registries, surveillance networks, multi-practice databases). Beneficiaries are
   administrators, standards bodies, and informatics infrastructure.
   Key signals: "ICD-11 implementation," version-transition impact, coding workflow/policy,
   registry/database construction, data-quality audit.

8. Psychiatric & Conceptual Analyses of Classification
   Conceptual, historical, or psychometric work on how diagnostic constructs are defined,
   bounded, and measured — dimensional vs categorical debates, depathologizing milestones,
   network structure of scales, philosophy of classification. Often non-computational.
   Key signals: DSM/ICD construct debates, dimensional/categorical, scale
   reliability/psychometrics, argumentative or historical rather than empirical-computational.

9. Biomedical Signal & Image Processing (peripheral)
   Disease classification/segmentation directly from images or waveforms (CXR, CT, OCT,
   ECG/phonocardiogram, EMG, dermoscopy). Linked to the corpus mostly by thin ICD framing;
   a community largely separate from the rest.
   Key signals: raw signal/image input, segmentation/classification metrics (Dice, AUC on
   imaging), no coded-text component.

10. Reviews & Evidence Synthesis
    Narrative, systematic, or meta-analytic syntheses producing no new model or dataset —
    surveys of NLP/AI methods, validity studies, text-classification trend reviews.
    Key signals: "systematic review," PRISMA, "we surveyed," no built artifact.
"""

SYSTEM_PROMPT = f"""\
You are classifying research papers into a taxonomy that was inductively discovered from this
corpus. Assign each paper to exactly ONE category.

TAXONOMY:
{TAXONOMY_TEXT}

ASSIGNMENT RULES:
- Assign the category where the paper's PRIMARY DELIVERABLE lives.
- If a paper spans two categories, assign the primary one and note the secondary in your reason.
- The key axis is the ROLE ICD plays: target (1,2), suspect/object (3,5,7,8), feature/input (4,6).
- Category 9 is for papers where the main input is a raw signal or image, not coded text.
- Category 10 is only for pure reviews — no new model, system, or dataset built.
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
                "maximum": 10,
                "description": "The primary taxonomy category (1–10).",
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
                "maximum": 10,
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

        # Build concise paper description
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
    1:  "Automatic ICD/Procedure Coding from Clinical Text",
    2:  "Cause-of-Death, Mortality & Injury Coding",
    3:  "Phenotyping, Case-Finding & Code Validation",
    4:  "Clinical Risk Prediction, Outcome Modeling & Decision Support",
    5:  "Terminology Mapping, Ontologies & Knowledge Representation",
    6:  "Epidemiology, Health-Services & Outcomes Studies Using Coded Data",
    7:  "Classification Systems, Coding Practice & Data Infrastructure",
    8:  "Psychiatric & Conceptual Analyses of Classification",
    9:  "Biomedical Signal & Image Processing (peripheral)",
    10: "Reviews & Evidence Synthesis",
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
    for cat_num in range(1, 11):
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
