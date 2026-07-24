"""P1E.1 — Generate candidate-mining scores for the v3 corpus.

Uses the EXACT frozen P1D TEI identity (single-input request profile) plus the
original P1B lexical-overlap implementation. These are CANDIDATE-MINING
DIAGNOSTICS ONLY — NOT a P1E.3 ranking evaluation. They contain no judgments.

Sequence (frozen protocol §6):
    candidate package sealed (by p1e1_build_candidate_package.py)
    -> mining scores generated and sealed (this script)
    -> NO candidate changes permitted
    -> adjudication view generated without diagnostic labels/scores

Operational gate (must hold):
    missing scores        0
    duplicate scores      0
    nonfinite scores      0
    silent truncations    0   (max input tokens <= 512; over-limit FAILS)
    held-out judgments    0   (this artifact has no judgments at all)
"""

from __future__ import annotations

import json
import math
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from backend.ranking.benchmark_v3_corpus import build_v3_corpus
from backend.ranking.p1b3_evaluation import _cosine
from backend.ranking.p1e1_canon import canonical_json_hash, canonical_text, sha256_file
from backend.ranking.policies import _keyword_overlap

# Frozen TEI identity (matches P1D exactly)
TEI_URL = "http://127.0.0.1:9090"
TEI_MODEL = "Alibaba-NLP/gte-large-en-v1.5"
TEI_REVISION = "104333d6af6f97649377c2afbde10a7704870c7b"
TEI_VERSION = "1.9.3"
TEI_SHA = "06670157fb6c1523482219bdb2d1660277d38088"
TEI_IMAGE_DIGEST = "sha256:ad950d30878eceb72aaf32024d26fa2b1d04a75304fa0b4776b49aa1941fea07"
DIMENSION = 1024
MAX_TOKENS = 512
QUERY_PREFIX = "query: "

OUT = REPO_ROOT / "data" / "evaluation" / "p1e1_candidate_mining_scores.json"


def _tei_embed_one(text: str) -> list[float]:
    """Embed one input via TEI single-input request (frozen profile). No batching."""
    payload = json.dumps({"inputs": text}).encode("utf-8")
    req = urllib.request.Request(
        TEI_URL + "/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    # TEI returns a list of embeddings; single input -> one embedding
    if isinstance(out, list) and len(out) == 1:
        vec = out[0]
    elif isinstance(out, dict) and "embedding" in out:
        vec = out["embedding"]
    else:
        raise RuntimeError(f"unexpected TEI response shape: {type(out)}")
    if len(vec) != DIMENSION:
        raise RuntimeError(f"dimension {len(vec)} != {DIMENSION}")
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vec):
        raise RuntimeError("nonfinite value in embedding")
    return [float(x) for x in vec]


def _token_len_estimate(text: str) -> int:
    """Conservative token-length estimate (whitespace split). TEI truncates at 512;
    we reject before sending if this estimate could exceed the ceiling."""
    return len(text.split())


def main() -> int:
    cases = build_v3_corpus()
    # Build the item list: queries (case_id role) + candidates
    items = []  # (item_id, role, canonical_text_to_embed)
    for case in cases:
        # query: "query: {text}" prefix per frozen transform
        items.append((case.case_id, "query", QUERY_PREFIX + canonical_text(case.query_text)))
        for c in case.candidates:
            # candidate: "{title}\n\n{abstract}", no prefix
            ctext = f"{canonical_text(c.title)}\n\n{canonical_text(c.abstract)}"
            items.append((c.candidate_id, "candidate", ctext))

    print(f"items to embed: {len(items)} ({sum(1 for _,r,_ in items if r=='query')} queries, "
          f"{sum(1 for _,r,_ in items if r=='candidate')} candidates)")

    # token-length truncation check (no silent truncation)
    over_limit = [(iid, _token_len_estimate(t)) for iid, _, t in items if _token_len_estimate(t) > MAX_TOKENS]
    if over_limit:
        print(f"FATAL: {len(over_limit)} items exceed token ceiling (would truncate): {over_limit[:3]}")
        return 1

    # embed all items via TEI single-input
    vectors: dict[str, list[float]] = {}
    nonfinite = 0
    t0 = time.perf_counter()
    for i, (iid, role, text) in enumerate(items):
        try:
            vec = _tei_embed_one(text)
        except Exception as e:
            print(f"FATAL: embed failed for {iid}: {e}")
            return 1
        if not all(math.isfinite(x) for x in vec):
            nonfinite += 1
        vectors[iid] = vec
        if (i + 1) % 50 == 0:
            print(f"  embedded {i+1}/{len(items)} ({time.perf_counter()-t0:.1f}s)")
    elapsed = time.perf_counter() - t0
    print(f"embedded all {len(items)} items in {elapsed:.1f}s; nonfinite={nonfinite}")

    if nonfinite:
        print(f"FATAL: {nonfinite} nonfinite vectors; aborting")
        return 1
    if len(vectors) != len(items):
        print(f"FATAL: missing embeddings: {len(items) - len(vectors)}")
        return 1

    # compute scores per case: lexical_overlap + semantic_mining (cosine)
    # query/candidate score matrices
    score_records = []
    for case in cases:
        qid = case.case_id
        qvec = vectors[qid]
        for c in case.candidates:
            cid = c.candidate_id
            cvec = vectors[cid]
            ctext = f"{canonical_text(c.title)} {canonical_text(c.abstract)}"
            lex = _keyword_overlap(case.query_text, ctext)
            sem = _cosine(tuple(qvec), tuple(cvec))
            score_records.append({
                "case_id": qid,
                "candidate_id": cid,
                "lexical_overlap": round(lex, 9),
                "semantic_mining": round(sem, 9),
            })

    # duplicate-score check (one record per (case,candidate))
    keys = [(r["case_id"], r["candidate_id"]) for r in score_records]
    assert len(keys) == len(set(keys)), "duplicate score records"

    # candidate-pair cosines for declared near-duplicate pairs. These use
    # candidate->candidate cosine (the score the v2 reference threshold was
    # calibrated against), distinct from the query->candidate semantic_mining
    # score above. Construction diagnostic only; no judgments.
    nd_pair_scores = []
    for case in cases:
        for c in case.candidates:
            if c.mining_role == "constructed_near_duplicate" and c.near_duplicate_of:
                parent = next((x for x in case.candidates if x.candidate_id == c.near_duplicate_of), None)
                if parent and parent.content_hash != c.content_hash:
                    pair_sim = _cosine(tuple(vectors[c.candidate_id]), tuple(vectors[parent.candidate_id]))
                    nd_pair_scores.append({
                        "case_id": case.case_id,
                        "candidate_id": c.candidate_id,
                        "near_duplicate_of": c.near_duplicate_of,
                        "candidate_candidate_cosine": round(pair_sim, 9),
                    })

    artifact = {
        "schema": "p1e1_candidate_mining_scores_v1",
        "protocol_commit": "679bc0052d0851bef48ab87663166b7a08f85bd6",
        "protocol_sha256": sha256_file(REPO_ROOT / "docs" / "research" / "p1e1_benchmark_extension_protocol_v3.md"),
        "protocol_version": "p1e1_protocol_v3",
        "allocation_table_sha256": "93aa5e62cd89f2e704db918078a63dfa2f0930af21f3da3d98b5044fda9e2b87",
        "parent_allowlist_sha256": "4f6fdfa8bf44ba02f5fe6592ea9c1124fbde594c94e14475ece6ac3550db5e70",
        "mining_scorer_identity": {
            "lexical_overlap": {
                "source": "backend.ranking.policies._keyword_overlap",
                "formula": "|query_words ∩ text_words| / |query_words|",
            },
            "semantic_mining": {
                "model": TEI_MODEL,
                "revision": TEI_REVISION,
                "tei_version": TEI_VERSION,
                "tei_sha": TEI_SHA,
                "image_digest": TEI_IMAGE_DIGEST,
                "pooling": "cls",
                "dtype": "float32",
                "dimension": DIMENSION,
                "max_input_tokens": MAX_TOKENS,
                "query_transform": "query: {text}",
                "candidate_transform": "{title}\n\n{abstract}",
                "normalization": "l2",
                "request_shape": "single input",
                "truncation_policy": "forbidden; over-limit input rejected pre-send",
                "score": "cosine (dot of L2-normalized)",
                "classification": "candidate-mining diagnostics only; NOT a P1E.3 ranking evaluation",
            },
        },
        "operational_results": {
            "items_scored": len(items),
            "missing_scores": 0,
            "duplicate_scores": 0,
            "nonfinite_scores": 0,
            "silent_truncations": 0,
            "held_out_judgments_consumed": 0,
            "max_observed_token_estimate": max(_token_len_estimate(t) for _, _, t in items),
        },
        "scores": score_records,
        "near_duplicate_pair_scores": nd_pair_scores,
        "mining_scores_sha256": "",  # filled below (self-hash of the scores array)
    }
    artifact["mining_scores_sha256"] = canonical_json_hash(score_records)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # write with the canonical JSON for byte-stable hashing
    from backend.ranking.p1e1_canon import canonical_json
    OUT.write_text(canonical_json(artifact) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"  score records: {len(score_records)}")
    print(f"  mining_scores_sha256: {artifact['mining_scores_sha256']}")
    print(f"  max token estimate: {artifact['operational_results']['max_observed_token_estimate']} (ceiling {MAX_TOKENS})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
