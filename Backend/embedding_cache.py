"""
Pre-computed embedding cache for subtopic classification texts.

Encodes all subtopic texts once at startup; classify requests
use the cached embeddings instead of re-encoding every time.
"""

import numpy as np
import time

# Global cache: spec_code → {embeddings: np.ndarray, subtopic_ids: list[str], strands: list[str]}
_cache: dict[str, dict] = {}


def build_cache(allSpecs: dict, model) -> dict:
    """Build a fresh cache dict from allSpecs (keyed by spec_code) and the sentence-transformer model."""
    new_cache = {}
    total_subtopics = 0

    for spec_code, spec in allSpecs.items():
        texts = []
        subtopic_ids = []
        strands = []

        for t in spec["Topics"]:
            topic_name = t["Topic_name"]
            strand = t["Strand"]
            for s in t["Sub_topics"]:
                texts.append(topic_name + ". " + s["description"])
                subtopic_ids.append(s["subtopic_id"])
                strands.append(strand)

        if texts:
            embeddings = model.encode(texts, show_progress_bar=False)
        else:
            embeddings = np.empty((0, model.get_sentence_embedding_dimension()))

        new_cache[spec_code] = {
            "embeddings": embeddings,
            "subtopic_ids": subtopic_ids,
            "strands": strands,
        }
        total_subtopics += len(texts)

    return new_cache


def rebuild(allSpecs: dict, model):
    """Rebuild the global cache atomically."""
    global _cache
    t0 = time.time()
    new_cache = build_cache(allSpecs, model)
    _cache = new_cache
    total = sum(len(v["subtopic_ids"]) for v in _cache.values())
    print(f"Embedding cache built: {len(_cache)} specs, {total} subtopics in {time.time() - t0:.2f}s")


def get_embeddings(spec_code: str, strand_filter: set[str] | None = None):
    """
    Return (embeddings_matrix, subtopic_ids) for a spec, optionally filtered by strands.
    """
    entry = _cache.get(spec_code)
    if entry is None:
        raise KeyError(f"Spec '{spec_code}' not found in embedding cache")

    if strand_filter is None:
        return entry["embeddings"], entry["subtopic_ids"]

    # Apply strand filter via boolean mask
    mask = np.array([s in strand_filter for s in entry["strands"]])
    if not mask.any():
        return np.empty((0, entry["embeddings"].shape[1] if entry["embeddings"].ndim == 2 else 0)), []

    filtered_embeddings = entry["embeddings"][mask]
    filtered_ids = [sid for sid, keep in zip(entry["subtopic_ids"], mask) if keep]
    return filtered_embeddings, filtered_ids
