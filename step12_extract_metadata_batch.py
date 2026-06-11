#!/usr/bin/env python3
"""
step12_extract_metadata_batch.py
------------------------------
Batch LLM metadata extraction using the Anthropic Messages Batches API.
Extracts structured metadata from each paper's title and abstract.
Resume-safe: re-running skips papers already extracted.

Requires: pip install anthropic pandas
Requires: ANTHROPIC_API_KEY environment variable

Usage:
    python step12_extract_metadata_batch.py
    python step12_extract_metadata_batch.py --input output/final_corpus_clean.csv
    python step12_extract_metadata_batch.py --resume
"""
import argparse
import json
import os
import time

import anthropic
import pandas as pd
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_INPUT  = os.path.join(BASE_DIR, "output", "final_corpus_clean.csv")
DEFAULT_JSONL  = os.path.join(BASE_DIR, "output", "metadata_extraction.jsonl")
DEFAULT_MERGED = os.path.join(BASE_DIR, "output", "metadata_extracted.csv")

MODEL = "claude-sonnet-4-6"

MISSING = {"", "nan", "none", "na", "null", "n/a"}

# --------------------------------------------------------------------------
# System prompt = the inductive-extraction skill (instructions only; the JSON
# shape is enforced by the tool schema below, so schema blocks are omitted).
# --------------------------------------------------------------------------
SYSTEM_PROMPT = """\
# Inductive Metadata Extraction for Automated ICD Coding Literature

## Purpose
Extract descriptive information from a research paper using ONLY its title and abstract,
for inductive taxonomy development. The objective is NOT to classify papers into predefined
categories. It is to create structured descriptions that can later be analysed with topic
modelling, clustering, thematic analysis, or LLMs to discover emerging research themes.

## Core Principles
1. Do NOT classify papers into predefined taxonomy categories.
2. Do NOT infer concepts that are not explicitly supported by the title or abstract.
3. Capture what the paper is trying to achieve.
4. Capture what the paper claims is new.
5. Capture the language used by the authors (prefer the authors' own phrasing).
6. Use concise natural language.
7. If information cannot be determined, return "Unknown" (for list fields, return an empty list).
8. Preserve information; taxonomy creation happens later at the corpus level. This step is extraction only.

## Field guidance (respect the stated word maximums)
- research_problem (<=25 words): What problem is the paper attempting to solve?
- study_objective (<=25 words): The primary objective of the study.
- input_data (<=25 words): What information is provided to the system (e.g. discharge summaries, clinical notes, EHR, diagnosis descriptions, administrative data).
- output_target (<=20 words): What the system predicts or generates (e.g. ICD codes, ICD code groups, ICD mappings, coding recommendations).
- method_summary (<=30 words): The proposed method; focus on what the authors built.
- novelty_claim (<=30 words): What the authors claim is new (look for "we propose", "we introduce", "novel", "first", "new approach", "improved").
- evaluation_focus (<=20 words): What aspect of performance is evaluated (e.g. coding accuracy, F1, rare-code prediction, explainability, efficiency, human-coder agreement).
- dataset_description (<=25 words): Brief description of the dataset (e.g. MIMIC-III discharge summaries, hospital EHR, national claims data).
- key_terms (<=10 items): Important technical concepts mentioned in the title or abstract. Prefer phrases used by the authors. Do not invent terms.
- main_contribution (<=40 words): One sentence describing the central contribution.
- author_perspective (<=15 words): How the authors position their work (e.g. new methodology, performance improvement, clinical deployment, benchmark study, comparative evaluation, decision support tool).
- confidence (0-100): Confidence that the extraction is supported by the title and abstract. 90-100 explicitly stated; 70-89 strong evidence; 50-69 partial evidence; below 50 unclear.

Do NOT emit method labels (e.g. "Transformer", "LLM", "Hierarchy-Aware") unless those terms appear naturally in the paper's title or abstract.
Record the extraction by calling the `record_extraction` tool exactly once.
"""

# Tool schema mirrors the output schema (paper_id is injected by us, not the model).
EXTRACTION_TOOL = {
    "name": "record_extraction",
    "description": "Record the structured metadata extracted from the paper.",
    "input_schema": {
        "type": "object",
        "properties": {
            "research_problem": {"type": "string"},
            "study_objective": {"type": "string"},
            "input_data": {"type": "string"},
            "output_target": {"type": "string"},
            "method_summary": {"type": "string"},
            "novelty_claim": {"type": "string"},
            "evaluation_focus": {"type": "string"},
            "dataset_description": {"type": "string"},
            "key_terms": {"type": "array", "items": {"type": "string"}},
            "main_contribution": {"type": "string"},
            "author_perspective": {"type": "string"},
            "confidence": {"type": "integer"},
        },
        "required": [
            "research_problem", "study_objective", "input_data", "output_target",
            "method_summary", "novelty_claim", "evaluation_focus",
            "dataset_description", "key_terms", "main_contribution",
            "author_perspective", "confidence",
        ],
        "additionalProperties": False,
    },
}


def clean(v):
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() in MISSING else s


def load_done(path):
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    done.add(json.loads(line)["paper_id"])
                except Exception:
                    pass
    return done


def build_requests(df, done, model):
    """Return (requests, custom_id->paper_id map) for papers not yet extracted."""
    requests, cmap = [], {}
    for i, (_, r) in enumerate(df.iterrows()):
        pid = clean(r.get("DOI")) or clean(r.get("Title"))
        if not pid or pid in done:
            continue
        cid = f"paper-{i}"
        cmap[cid] = pid
        payload = json.dumps({"paper_id": pid, "title": clean(r.get("Title")) or "Unknown",
                              "abstract": clean(r.get("Abstract"))}, ensure_ascii=False)
        requests.append(Request(
            custom_id=cid,
            params=MessageCreateParamsNonStreaming(
                model=model,
                max_tokens=1024,
                system=[{"type": "text", "text": SYSTEM_PROMPT,
                         "cache_control": {"type": "ephemeral"}}],
                tools=[EXTRACTION_TOOL],
                tool_choice={"type": "tool", "name": "record_extraction"},
                messages=[{"role": "user", "content":
                           "Extract metadata from this paper (JSON input follows):\n" + payload}],
            ),
        ))
    return requests, cmap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model",  default=MODEL, help="Anthropic model id (default: claude-sonnet-4-6)")
    ap.add_argument("--input",  default=DEFAULT_INPUT)
    ap.add_argument("--output", default=DEFAULT_JSONL)
    ap.add_argument("--merged", default=DEFAULT_MERGED)
    ap.add_argument("--resume", action="store_true",
                    help="Resume polling/retrieval of an existing batch.")
    args = ap.parse_args()

    model      = args.model
    out_jsonl  = args.output
    merged_csv = args.merged
    state_path = os.path.join(BASE_DIR, "output", f"metadata_batch_state__{model}.json")

    client = anthropic.Anthropic(max_retries=5)
    df = pd.read_csv(args.input, dtype=str)

    # Resume an existing batch, or create a new one.
    state = {}
    if os.path.exists(state_path) and args.resume:
        state = json.load(open(state_path, encoding="utf-8"))
        print(f"Resuming batch {state['batch_id']}")
    else:
        if os.path.exists(state_path):
            os.remove(state_path)
        done = load_done(out_jsonl)
        requests, cmap = build_requests(df, done, model)
        print(f"Papers to extract: {len(requests)} (already done: {len(done)})")
        if not requests:
            print("Nothing to submit.")
        else:
            batch = client.messages.batches.create(requests=requests)
            state = {"batch_id": batch.id, "cmap": cmap}
            json.dump(state, open(state_path, "w", encoding="utf-8"))
            print(f"Created batch {batch.id} with {len(requests)} requests.")

    if not state:
        return

    batch_id, cmap = state["batch_id"], state["cmap"]

    # Poll until the batch finishes.
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        c = batch.request_counts
        print(f"[{batch.processing_status}] processing={c.processing} "
              f"succeeded={c.succeeded} errored={c.errored} "
              f"canceled={c.canceled} expired={c.expired}")
        if batch.processing_status == "ended":
            break
        time.sleep(30)

    # Retrieve results and append to JSONL.
    done = load_done(out_jsonl)
    n_ok = n_err = 0
    with open(out_jsonl, "a", encoding="utf-8") as out_f:
        for result in client.messages.batches.results(batch_id):
            pid = cmap.get(result.custom_id, result.custom_id)
            if pid in done:
                continue
            if result.result.type != "succeeded":
                n_err += 1
                print(f"  ! {pid}: {result.result.type}")
                continue
            msg = result.result.message
            block = next((b for b in msg.content if b.type == "tool_use"), None)
            if block is None:
                n_err += 1
                continue
            rec = dict(block.input)
            rec["paper_id"] = pid
            rec["_usage"] = {"input": msg.usage.input_tokens,
                             "output": msg.usage.output_tokens,
                             "cache_read": getattr(msg.usage, "cache_read_input_tokens", 0)}
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_ok += 1
    print(f"Retrieved: ok={n_ok} err={n_err}. JSONL -> {out_jsonl}")

    if os.path.exists(state_path):
        os.remove(state_path)

    # Merge JSONL extractions into a CSV joined with the source paper rows.
    recs = {}
    for line in open(out_jsonl, encoding="utf-8"):
        line = line.strip()
        if line:
            r = json.loads(line)
            recs[r["paper_id"]] = r
    fields = ["research_problem", "study_objective", "input_data", "output_target",
              "method_summary", "novelty_claim", "evaluation_focus", "dataset_description",
              "key_terms", "main_contribution", "author_perspective", "confidence"]
    src = pd.read_csv(args.input, dtype=str)

    def pid_of(r):
        return clean(r.get("DOI")) or clean(r.get("Title"))

    for fld in fields:
        src["meta_" + fld] = src.apply(
            lambda r: (lambda v: "; ".join(v) if isinstance(v, list) else v)
            (recs.get(pid_of(r), {}).get(fld, "")), axis=1)
    src.to_csv(merged_csv, index=False)
    print(f"Merged CSV -> {merged_csv}  ({len(recs)} papers extracted)")


if __name__ == "__main__":
    main()
