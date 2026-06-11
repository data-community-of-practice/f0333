#!/usr/bin/env python3
"""
step7_enrich_papers.py

Enrich missing Abstract / Keywords in a papers CSV.

Fill order (each stage only touches rows still missing the field):
    1. OpenAlex        (DOI batch lookup, then title search)
    2. Semantic Scholar(DOI batch lookup, then title search)
    3. Crossref        (per-DOI lookup, then title search)

The script is RESUMABLE and IDEMPOTENT: it writes to an output CSV
periodically, and on restart it reloads that output and skips anything
already filled. Just run it again if it crashes or you stop it.

Usage:
    python enrich_papers.py                      # full run, all stages
    python enrich_papers.py --limit 200          # quick test on first 200 rows
    python enrich_papers.py --stages openalex    # run only one/some stages
    python enrich_papers.py --no-title-search    # DOI-only (skip fuzzy title fallback)
"""

import argparse
import html
import json
import os
import re
import sys
import time
from difflib import SequenceMatcher

import pandas as pd
import requests

# ----------------------------------------------------------------------------
# CONFIG  --  EDIT THIS
# ----------------------------------------------------------------------------
# An email puts you in the "polite pool" of OpenAlex & Crossref, giving you
# much better, more reliable rate limits. Use a real address.
CONTACT_EMAIL = "anambissan@swin.edu.au"

# Optional Semantic Scholar API key (raises rate limits). Provided via the
# S2_API_KEY environment variable so the secret never lives in this file.
# When you have a key, run:  $env:S2_API_KEY='<key>'; python enrich_papers.py
S2_API_KEY = os.environ.get("S2_API_KEY", "")

INPUT_CSV  = "output/filtered_papers.csv"
OUTPUT_CSV = "output/enriched_papers.csv"

# How often (rows processed) to flush progress to disk.
SAVE_EVERY = 500

# Title-match safety: only accept a title-searched record if its title is at
# least this similar to ours (0..1). Higher = stricter = fewer wrong matches.
TITLE_MATCH_THRESHOLD = 0.90

# Politeness / batch sizes
OPENALEX_BATCH = 50      # max DOIs per OpenAlex filter request
S2_BATCH       = 100     # DOIs per Semantic Scholar /paper/batch request (max 500)
HTTP_TIMEOUT   = 30
MAX_BACKOFF    = 30      # cap any retry wait (some APIs send absurd Retry-After)
TITLE_RETRIES  = 1       # title search is best-effort: don't retry-storm a single row
CIRCUIT_LIMIT  = 6       # consecutive failed requests -> assume the API is throttling
                         #   us; bail out of the stage (remaining rows retried on resume)
# ----------------------------------------------------------------------------

USER_AGENT = f"paper-enricher/1.0 (mailto:{CONTACT_EMAIL})"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})

MISSING_TOKENS = {"", "nan", "none", "na", "null", "n/a"}


# --------------------------- helpers ----------------------------------------

def is_missing(val) -> bool:
    """True if a cell is empty / NaN / a missing-ish token."""
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    s = str(val).strip().lower()
    return s in MISSING_TOKENS


def norm_doi(doi) -> str | None:
    """Normalize a DOI for matching: lowercase, strip URL prefix/whitespace."""
    if is_missing(doi):
        return None
    s = str(doi).strip().lower()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s)
    s = s.strip()
    return s or None


def doi_is_filter_safe(doi: str) -> bool:
    """Characters that would break an OpenAlex/S2 comma/pipe-delimited filter."""
    return not any(c in doi for c in [",", "|", " "])


def norm_title(t) -> str:
    """Aggressive normalization for fuzzy title comparison."""
    if is_missing(t):
        return ""
    s = str(t).lower()
    s = re.sub(r"<[^>]+>", " ", s)          # strip any html/jats
    s = re.sub(r"[^a-z0-9]+", " ", s)       # keep alnum only
    return re.sub(r"\s+", " ", s).strip()


def title_similar(a: str, b: str) -> float:
    na, nb = norm_title(a), norm_title(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def reconstruct_abstract(inv_index) -> str | None:
    """Rebuild plain-text abstract from OpenAlex abstract_inverted_index."""
    if not inv_index:
        return None
    positions = []
    for word, idxs in inv_index.items():
        for i in idxs:
            positions.append((i, word))
    if not positions:
        return None
    positions.sort(key=lambda x: x[0])
    text = " ".join(w for _, w in positions).strip()
    return text or None


def clean_jats(text) -> str | None:
    """Crossref abstracts are JATS XML; strip tags, unescape, collapse space."""
    if not text:
        return None
    s = re.sub(r"</(p|sec|title|abstract)>", " ", text, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    # drop a leading bare "Abstract" label if present
    s = re.sub(r"^abstract[:\.\s]+", "", s, flags=re.I).strip()
    return s or None


def join_keywords(items) -> str | None:
    """Normalize a list of keyword/tag strings to 'a; b; c', deduped."""
    seen, out = set(), []
    for it in items or []:
        if not it:
            continue
        k = str(it).strip()
        kl = k.lower()
        if k and kl not in seen:
            seen.add(kl)
            out.append(k)
    return "; ".join(out) if out else None


def http_get(url, params=None, max_retries=5, headers=None):
    """GET with backoff on 429/5xx. Returns Response or None."""
    delay = 1.0
    for attempt in range(max_retries):
        try:
            r = SESSION.get(url, params=params, headers=headers, timeout=HTTP_TIMEOUT)
        except requests.RequestException as e:
            print(f"    ! request error: {e}; retrying in {delay:.0f}s")
            time.sleep(delay); delay = min(delay * 2, 30); continue
        if r.status_code == 200:
            return r
        if r.status_code in (429, 500, 502, 503, 504):
            retry_after = r.headers.get("Retry-After")
            wait = float(retry_after) if (retry_after and retry_after.isdigit()) else delay
            wait = min(wait, MAX_BACKOFF)   # never honor an absurd Retry-After
            print(f"    ! HTTP {r.status_code}; backing off {wait:.0f}s")
            time.sleep(wait); delay = min(delay * 2, MAX_BACKOFF); continue
        # Definite non-retryable response (404 not-found, 400, ...). This is a
        # real answer ("no data"), NOT a throttle -- return it so the caller's
        # circuit breaker does not mistake it for rate-limiting.
        return r
    return None   # network error or exhausted 429/5xx retries == throttle signal


def http_post(url, json_body, params=None, headers=None, max_retries=5):
    delay = 1.0
    for attempt in range(max_retries):
        try:
            r = SESSION.post(url, params=params, json=json_body,
                             headers=headers, timeout=HTTP_TIMEOUT)
        except requests.RequestException as e:
            print(f"    ! request error: {e}; retrying in {delay:.0f}s")
            time.sleep(delay); delay = min(delay * 2, 30); continue
        if r.status_code == 200:
            return r
        if r.status_code in (429, 500, 502, 503, 504):
            retry_after = r.headers.get("Retry-After")
            wait = float(retry_after) if (retry_after and retry_after.isdigit()) else delay
            wait = min(wait, MAX_BACKOFF)   # never honor an absurd Retry-After
            print(f"    ! HTTP {r.status_code}; backing off {wait:.0f}s")
            time.sleep(wait); delay = min(delay * 2, MAX_BACKOFF); continue
        print(f"    ! HTTP {r.status_code} for {url}")
        return None
    return None


# --------------------------- data application -------------------------------

def apply_record(df, idx, abstract, keywords, source):
    """Write fetched abstract/keywords into the df only where still missing.
    Returns (filled_abstract: bool, filled_keywords: bool)."""
    fa = fk = False
    if abstract and is_missing(df.at[idx, "Abstract"]):
        df.at[idx, "Abstract"] = abstract
        df.at[idx, "Abstract_Source"] = source
        fa = True
    if keywords and is_missing(df.at[idx, "Keywords"]):
        df.at[idx, "Keywords"] = keywords
        df.at[idx, "Keywords_Source"] = source
        fk = True
    return fa, fk


def needs(df, idx) -> bool:
    return is_missing(df.at[idx, "Abstract"]) or is_missing(df.at[idx, "Keywords"])


# --------------------------- parsers per source -----------------------------

def parse_openalex(work):
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    kws = [k.get("display_name") for k in (work.get("keywords") or [])]
    if not kws:  # fall back to high-confidence concepts
        kws = [c.get("display_name") for c in (work.get("concepts") or [])
               if (c.get("score") or 0) >= 0.3]
    return abstract, join_keywords(kws), work.get("title")


def parse_s2(paper):
    abstract = paper.get("abstract")
    fos = paper.get("fieldsOfStudy") or []
    if not fos:
        fos = [f.get("category") for f in (paper.get("s2FieldsOfStudy") or [])]
    return abstract, join_keywords(fos), paper.get("title")


def parse_crossref(item):
    abstract = clean_jats(item.get("abstract"))
    subj = item.get("subject") or []
    title_list = item.get("title") or []
    title = title_list[0] if title_list else None
    return abstract, join_keywords(subj), title


# =========================== STAGE 1: OPENALEX ==============================

OPENALEX_SELECT = "doi,title,abstract_inverted_index,keywords,concepts"

def stage_openalex_doi(df, save):
    todo = [i for i in df.index if needs(df, i) and norm_doi(df.at[i, "DOI"])
            and doi_is_filter_safe(norm_doi(df.at[i, "DOI"]))]
    print(f"[OpenAlex/DOI] {len(todo)} rows need lookup")
    by_doi = {}
    for i in todo:
        by_doi.setdefault(norm_doi(df.at[i, "DOI"]), []).append(i)

    dois = list(by_doi)
    fa = fk = 0
    consec_fail = 0
    for b in range(0, len(dois), OPENALEX_BATCH):
        chunk = dois[b:b + OPENALEX_BATCH]
        params = {
            "filter": "doi:" + "|".join(chunk),
            "per-page": OPENALEX_BATCH,
            "select": OPENALEX_SELECT,
            "mailto": CONTACT_EMAIL,
        }
        r = http_get("https://api.openalex.org/works", params=params,
                     max_retries=2)
        if r is None:
            consec_fail += 1
            if consec_fail >= CIRCUIT_LIMIT:
                print(f"  !! OpenAlex throttling us; skipping remaining DOI "
                      f"batches (retry on a later resume run)")
                break
        elif r.status_code == 200:
            consec_fail = 0
            for work in r.json().get("results", []):
                d = norm_doi(work.get("doi"))
                for idx in by_doi.get(d, []):
                    a, k, _ = parse_openalex(work)
                    x, y = apply_record(df, idx, a, k, "openalex")
                    fa += x; fk += y
        if (b // OPENALEX_BATCH) % 20 == 0:
            print(f"  ...{b + len(chunk)}/{len(dois)} dois | +{fa} abstr +{fk} kw")
            save()
        time.sleep(0.12)
    save()
    print(f"[OpenAlex/DOI] filled {fa} abstracts, {fk} keyword sets")


def stage_openalex_title(df, save):
    todo = [i for i in df.index if needs(df, i)
            and not norm_doi(df.at[i, "DOI"])
            and not is_missing(df.at[i, "Title"])]
    print(f"[OpenAlex/title] {len(todo)} no-DOI rows to search")
    fa = fk = 0
    consec_fail = 0
    for n, idx in enumerate(todo):
        title = str(df.at[idx, "Title"])
        params = {"filter": f"title.search:{re.sub(r'[,|]', ' ', title)[:350]}",
                  "per-page": 5, "select": OPENALEX_SELECT, "mailto": CONTACT_EMAIL}
        r = http_get("https://api.openalex.org/works", params=params,
                     max_retries=TITLE_RETRIES)
        if r is None:
            consec_fail += 1
            if consec_fail >= CIRCUIT_LIMIT:
                print(f"  !! OpenAlex throttling us; skipping remaining "
                      f"{len(todo)-n} rows (retry on a later resume run)")
                break
        elif r.status_code == 200:
            consec_fail = 0
            for work in r.json().get("results", []):
                a, k, wt = parse_openalex(work)
                if title_similar(title, wt) >= TITLE_MATCH_THRESHOLD:
                    x, y = apply_record(df, idx, a, k, "openalex:title")
                    fa += x; fk += y
                    break
        if n % SAVE_EVERY == 0 and n:
            print(f"  ...{n}/{len(todo)} | +{fa} abstr +{fk} kw"); save()
        time.sleep(0.25)
    save()
    print(f"[OpenAlex/title] filled {fa} abstracts, {fk} keyword sets")


# ======================= STAGE 2: SEMANTIC SCHOLAR ==========================

S2_FIELDS = "title,abstract,fieldsOfStudy,s2FieldsOfStudy"
S2_HEADERS = {"x-api-key": S2_API_KEY} if S2_API_KEY else None
# Issued keys are capped at 1 request/second CUMULATIVE across all S2 endpoints,
# so pace strictly above 1s regardless; unauthenticated pool is also ~1/s.
S2_SLEEP = 1.1

def stage_s2_doi(df, save):
    todo = [i for i in df.index if needs(df, i) and norm_doi(df.at[i, "DOI"])]
    print(f"[S2/DOI] {len(todo)} rows need lookup")
    by_doi = {}
    for i in todo:
        by_doi.setdefault(norm_doi(df.at[i, "DOI"]), []).append(i)
    dois = list(by_doi)
    fa = fk = 0
    consec_fail = 0
    for b in range(0, len(dois), S2_BATCH):
        chunk = dois[b:b + S2_BATCH]
        r = http_post(
            "https://api.semanticscholar.org/graph/v1/paper/batch",
            json_body={"ids": [f"DOI:{d}" for d in chunk]},
            params={"fields": S2_FIELDS}, headers=S2_HEADERS, max_retries=2)
        if r is None:
            consec_fail += 1
            if consec_fail >= CIRCUIT_LIMIT:
                print(f"  !! Semantic Scholar throttling us; skipping remaining "
                      f"DOI batches (retry on a later resume run)")
                break
        else:
            consec_fail = 0
            data = r.json()
            for d, paper in zip(chunk, data):
                if not paper:
                    continue
                a, k, _ = parse_s2(paper)
                for idx in by_doi.get(d, []):
                    x, y = apply_record(df, idx, a, k, "semanticscholar")
                    fa += x; fk += y
        print(f"  ...{b + len(chunk)}/{len(dois)} dois | +{fa} abstr +{fk} kw")
        save()
        time.sleep(S2_SLEEP)
    save()
    print(f"[S2/DOI] filled {fa} abstracts, {fk} keyword sets")


def stage_s2_title(df, save):
    todo = [i for i in df.index if needs(df, i)
            and not norm_doi(df.at[i, "DOI"])
            and not is_missing(df.at[i, "Title"])]
    print(f"[S2/title] {len(todo)} no-DOI rows to search")
    fa = fk = 0
    consec_fail = 0
    for n, idx in enumerate(todo):
        title = str(df.at[idx, "Title"])
        r = http_get("https://api.semanticscholar.org/graph/v1/paper/search",
                     params={"query": title[:300], "limit": 5, "fields": S2_FIELDS},
                     max_retries=TITLE_RETRIES, headers=S2_HEADERS)
        if r is None:
            consec_fail += 1
            if consec_fail >= CIRCUIT_LIMIT:
                print(f"  !! Semantic Scholar throttling us; skipping remaining "
                      f"{len(todo)-n} rows (retry on a later resume run)")
                break
        elif r.status_code == 200:
            consec_fail = 0
            for paper in r.json().get("data", []) or []:
                a, k, pt = parse_s2(paper)
                if title_similar(title, pt) >= TITLE_MATCH_THRESHOLD:
                    x, y = apply_record(df, idx, a, k, "semanticscholar:title")
                    fa += x; fk += y
                    break
        if n % 100 == 0 and n:
            print(f"  ...{n}/{len(todo)} | +{fa} abstr +{fk} kw"); save()
        time.sleep(S2_SLEEP)
    save()
    print(f"[S2/title] filled {fa} abstracts, {fk} keyword sets")


# =========================== STAGE 3: CROSSREF ==============================

def stage_crossref_doi(df, save):
    todo = [i for i in df.index if needs(df, i) and norm_doi(df.at[i, "DOI"])]
    print(f"[Crossref/DOI] {len(todo)} rows need lookup")
    fa = fk = 0
    consec_fail = 0
    for n, idx in enumerate(todo):
        doi = norm_doi(df.at[idx, "DOI"])
        r = http_get(f"https://api.crossref.org/works/{doi}",
                     params={"mailto": CONTACT_EMAIL}, max_retries=2)
        if r is None:
            consec_fail += 1
            if consec_fail >= CIRCUIT_LIMIT:
                print(f"  !! Crossref throttling us; skipping remaining "
                      f"{len(todo)-n} rows (retry on a later resume run)")
                break
        else:
            consec_fail = 0
            if r.status_code == 200:
                item = r.json().get("message", {})
                a, k, _ = parse_crossref(item)
                x, y = apply_record(df, idx, a, k, "crossref")
                fa += x; fk += y
        if n % SAVE_EVERY == 0 and n:
            print(f"  ...{n}/{len(todo)} | +{fa} abstr +{fk} kw"); save()
        time.sleep(0.05)
    save()
    print(f"[Crossref/DOI] filled {fa} abstracts, {fk} keyword sets")


def stage_crossref_title(df, save):
    todo = [i for i in df.index if needs(df, i)
            and not norm_doi(df.at[i, "DOI"])
            and not is_missing(df.at[i, "Title"])]
    print(f"[Crossref/title] {len(todo)} no-DOI rows to search")
    fa = fk = 0
    consec_fail = 0
    for n, idx in enumerate(todo):
        title = str(df.at[idx, "Title"])
        r = http_get("https://api.crossref.org/works",
                     params={"query.bibliographic": title[:300], "rows": 5,
                             "mailto": CONTACT_EMAIL},
                     max_retries=TITLE_RETRIES)
        if r is None:
            consec_fail += 1
            if consec_fail >= CIRCUIT_LIMIT:
                print(f"  !! Crossref throttling us; skipping remaining "
                      f"{len(todo)-n} rows (retry on a later resume run)")
                break
        elif r.status_code == 200:
            consec_fail = 0
            for item in r.json().get("message", {}).get("items", []):
                a, k, ct = parse_crossref(item)
                if title_similar(title, ct) >= TITLE_MATCH_THRESHOLD:
                    x, y = apply_record(df, idx, a, k, "crossref:title")
                    fa += x; fk += y
                    break
        if n % 100 == 0 and n:
            print(f"  ...{n}/{len(todo)} | +{fa} abstr +{fk} kw"); save()
        time.sleep(0.08)
    save()
    print(f"[Crossref/title] filled {fa} abstracts, {fk} keyword sets")


# =============================== DRIVER =====================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=INPUT_CSV)
    ap.add_argument("--output", default=OUTPUT_CSV)
    ap.add_argument("--limit", type=int, default=None,
                    help="only process first N rows (testing)")
    ap.add_argument("--stages", default="openalex,s2,crossref",
                    help="comma list of: openalex,s2,crossref")
    ap.add_argument("--no-title-search", action="store_true",
                    help="skip fuzzy title fallback for no-DOI rows")
    args = ap.parse_args()

    if CONTACT_EMAIL == "your-email@example.com":
        print("!! Please set CONTACT_EMAIL at the top of the script first.")
        sys.exit(1)

    # Resume from previous output if it exists, else start from input.
    import os
    src = args.output if os.path.exists(args.output) else args.input
    print(f"Loading {src}")
    df = pd.read_csv(src, dtype=str)
    if args.limit:
        df = df.head(args.limit).copy()
    for col in ("Abstract", "Keywords", "Abstract_Source", "Keywords_Source"):
        if col not in df.columns:
            df[col] = pd.NA

    def save():
        # Atomic save: write to a temp file then replace, so an interrupted
        # write (e.g. the process being killed) can never truncate/corrupt
        # the real output file.
        tmp = args.output + ".tmp"
        df.to_csv(tmp, index=False)
        os.replace(tmp, args.output)

    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    use_title = not args.no_title_search

    def report():
        miss_a = sum(is_missing(df.at[i, "Abstract"]) for i in df.index)
        miss_k = sum(is_missing(df.at[i, "Keywords"]) for i in df.index)
        print(f"  >> still missing: {miss_a} abstracts, {miss_k} keywords "
              f"(of {len(df)} rows)")

    print(f"Start ({len(df)} rows). Stages: {stages}  title-search: {use_title}")
    report()

    if "openalex" in stages:
        stage_openalex_doi(df, save)
        if use_title:
            stage_openalex_title(df, save)
        report()
    if "s2" in stages:
        stage_s2_doi(df, save)
        if use_title:
            stage_s2_title(df, save)
        report()
    if "crossref" in stages:
        stage_crossref_doi(df, save)
        if use_title:
            stage_crossref_title(df, save)
        report()

    save()
    print(f"\nDone. Wrote {args.output}")
    report()


if __name__ == "__main__":
    main()
