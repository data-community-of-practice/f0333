"""
step15_discover_taxonomy.py
=======================================================
ICD Corpus — Iterative LLM Taxonomy Discovery (Path B)
=======================================================
Runs 4 independent inductive passes over random samples of the corpus,
then reconciles them into a consensus taxonomy.

Usage:
    pip install anthropic pandas
    export ANTHROPIC_API_KEY=your_key_here
    python discover_taxonomy.py

Output files (all written to outputs/taxonomy_discovery/):
    taxonomy_batch_1.txt  ...  taxonomy_batch_4.txt   — 4 independent draft taxonomies
    taxonomy_consensus.txt                             — reconciled final taxonomy
    taxonomy_discovery_log.txt                         — full prompts + responses for audit
"""

import os
import random
import pandas as pd
import anthropic
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Configuration ──────────────────────────────────────────────────────────────

CSV_PATH    = os.path.join(BASE_DIR, "output", "icd_verified.csv")
OUT_DIR     = os.path.join(BASE_DIR, "output", "taxonomy_discovery")
BATCH_SIZE  = 100    # papers per inductive pass
NUM_BATCHES = 4      # independent passes (more = more robust consensus)
RANDOM_SEED = 42
MODEL       = "claude-opus-4-8"
MAX_TOKENS  = 32000

# ── Helpers ────────────────────────────────────────────────────────────────────

def load_corpus(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = ["Title", "meta_study_objective", "meta_method_summary", "meta_main_contribution"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing columns: {missing}")
    df["_text"] = (
        "TITLE: " + df["Title"].fillna("") + "\n"
        "OBJECTIVE: " + df["meta_study_objective"].fillna("") + "\n"
        "METHOD: " + df["meta_method_summary"].fillna("") + "\n"
        "CONTRIBUTION: " + df["meta_main_contribution"].fillna("")
    )
    print(f"Loaded {len(df)} papers from {path}")
    return df


def sample_batch(df: pd.DataFrame, n: int, exclude_indices: set, rng: random.Random):
    available = df[~df.index.isin(exclude_indices)]
    if len(available) < n:
        raise ValueError(f"Not enough papers left to sample {n} (only {len(available)} remaining).")
    sampled = available.sample(n=n, random_state=rng.randint(0, 99999))
    return sampled, exclude_indices | set(sampled.index)


def format_papers_for_prompt(batch: pd.DataFrame) -> str:
    lines = []
    for i, (_, row) in enumerate(batch.iterrows(), 1):
        lines.append(f"--- Paper {i} ---")
        lines.append(row["_text"])
        lines.append("")
    return "\n".join(lines)


def call_claude(client: anthropic.Anthropic, prompt: str) -> str:
    """Call Claude with adaptive thinking and streaming; return the text response."""
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        msg = stream.get_final_message()
    # Extract the text block (thinking blocks are separate)
    for block in msg.content:
        if block.type == "text":
            return block.text
    return ""


def write_output(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Saved: {path}")


# ── Prompts ────────────────────────────────────────────────────────────────────

INDUCTIVE_PROMPT = """\
Below are {n} research papers from a corpus related to ICD (International Classification of Diseases).

Your task is to discover what natural groupings exist in this sample — purely inductively, \
from the ground up. Do NOT use any pre-existing taxonomy, framework, or classification system \
you may know. Do NOT default to obvious labels like "clinical papers" vs "technical papers".

Instead, look carefully at:
- What problem each paper is actually trying to solve
- What kind of input data or materials it uses
- What kind of output or artifact it produces
- What method or approach it takes
- Who the intended user or beneficiary seems to be

From these signals, identify the natural groupings that emerge from THIS specific set of papers.

Instructions:
1. Propose between 5 and 12 categories. More is fine if genuinely distinct groups exist.
2. For each category:
   - Give it a descriptive name (not a vague label like "other methods")
   - Write 2–3 sentences describing what defines membership — what do papers in this group \
actually DO, not just what topic they cover
   - List the paper numbers (e.g. Paper 3, Paper 17) you would place in it
3. After listing all categories, note any papers that didn't fit cleanly anywhere and explain why.
4. End with a short paragraph reflecting on what surprised you or what tensions you noticed \
in the data.

Here are the papers:

{papers}
"""

RECONCILE_PROMPT = """\
Four independent analysts each read a random sample of 100 papers from the same ICD research \
corpus and proposed a taxonomy inductively — without seeing each other's work and without using \
any pre-existing framework.

Their four draft taxonomies are below.

Your task: reconcile these into a single consensus taxonomy that best represents the full corpus.

Instructions:
1. Identify which categories across the four drafts are describing the same underlying phenomenon \
(even if named differently). Merge these.
2. Identify categories that appear in only one or two drafts — decide whether they represent a \
genuine distinct cluster or an artefact of that sample.
3. Identify genuine tensions or disagreements between drafts — where analysts seem to have \
carved the space differently. Describe the tension and make a principled decision about how \
to resolve it.
4. Produce a final consensus taxonomy of 6–12 categories. For each:
   - Name
   - 3–4 sentence description of what defines it (focus on what papers DO)
   - Estimated proportion of the full corpus (~2,600 papers) you'd expect to fall here
   - Key signals that would identify a new paper as belonging here
5. End with a section called "What the taxonomy reveals" — 3–5 observations about the field \
that the structure of this taxonomy makes visible.

--- DRAFT TAXONOMY 1 ---
{t1}

--- DRAFT TAXONOMY 2 ---
{t2}

--- DRAFT TAXONOMY 3 ---
{t3}

--- DRAFT TAXONOMY 4 ---
{t4}
"""

# ── Main ───────────────────────────────────────────────────────────────────────

def load_batch(batch_num: int) -> str:
    """Load a previously saved batch file; return empty string if missing/header-only."""
    path = os.path.join(OUT_DIR, f"taxonomy_batch_{batch_num}.txt")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    # Strip the header line(s)
    lines = raw.split("\n")
    body_lines = [l for l in lines if not l.startswith("DRAFT TAXONOMY") and not l.startswith("=")]
    return "\n".join(body_lines).strip()


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true",
                    help="Skip batches that already have non-empty content and re-reconcile.")
    args = ap.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY environment variable not set.")

    client = anthropic.Anthropic(api_key=api_key)
    rng = random.Random(RANDOM_SEED)
    log_lines = [f"Taxonomy discovery run — {datetime.now().isoformat()}\n{'='*60}\n"]

    df = load_corpus(CSV_PATH)

    # ── Phase 1: 4 independent inductive passes ────────────────────────────────
    draft_taxonomies = []
    used_indices: set = set()

    for batch_num in range(1, NUM_BATCHES + 1):
        # With --resume, skip batches that already have substantive content
        if args.resume:
            existing = load_batch(batch_num)
            if existing:
                print(f"\nBatch {batch_num}/{NUM_BATCHES} — using cached result ({len(existing)} chars)")
                # Still need to advance used_indices by consuming the same sample deterministically
                batch, used_indices = sample_batch(df, BATCH_SIZE, used_indices, rng)
                draft_taxonomies.append(existing)
                continue

        print(f"\nBatch {batch_num}/{NUM_BATCHES} — sampling {BATCH_SIZE} papers...")
        batch, used_indices = sample_batch(df, BATCH_SIZE, used_indices, rng)

        papers_text = format_papers_for_prompt(batch)
        prompt = INDUCTIVE_PROMPT.format(n=BATCH_SIZE, papers=papers_text)

        print(f"  Calling Claude ({MODEL}) with adaptive thinking...")
        response = call_claude(client, prompt)

        draft_taxonomies.append(response)

        out_path = os.path.join(OUT_DIR, f"taxonomy_batch_{batch_num}.txt")
        header = f"DRAFT TAXONOMY — BATCH {batch_num}\n{'='*50}\n"
        write_output(out_path, header + response)

        log_lines.append(f"\n{'='*60}\nBATCH {batch_num} PROMPT\n{'='*60}\n{prompt}")
        log_lines.append(f"\n{'='*60}\nBATCH {batch_num} RESPONSE\n{'='*60}\n{response}")

    # ── Phase 2: Reconciliation ────────────────────────────────────────────────
    print("\nReconciling 4 draft taxonomies into consensus...")
    reconcile_prompt = RECONCILE_PROMPT.format(
        t1=draft_taxonomies[0],
        t2=draft_taxonomies[1],
        t3=draft_taxonomies[2],
        t4=draft_taxonomies[3],
    )

    consensus = call_claude(client, reconcile_prompt)

    write_output(
        os.path.join(OUT_DIR, "taxonomy_consensus.txt"),
        "CONSENSUS TAXONOMY\n" + "="*50 + "\n" + consensus,
    )

    log_lines.append(f"\n{'='*60}\nRECONCILIATION PROMPT\n{'='*60}\n{reconcile_prompt}")
    log_lines.append(f"\n{'='*60}\nCONSENSUS RESPONSE\n{'='*60}\n{consensus}")

    write_output(
        os.path.join(OUT_DIR, "taxonomy_discovery_log.txt"),
        "\n".join(log_lines),
    )

    print("\nDone. Output files:")
    for i in range(1, NUM_BATCHES + 1):
        print(f"  {OUT_DIR}\\taxonomy_batch_{i}.txt")
    print(f"  {OUT_DIR}\\taxonomy_consensus.txt")
    print(f"  {OUT_DIR}\\taxonomy_discovery_log.txt")
    print("\nRecommended next step:")
    print("  Read taxonomy_consensus.txt — then share it here for discussion.")


if __name__ == "__main__":
    main()
