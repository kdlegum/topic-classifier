"""
Pre-computed embedding cache for subtopic classification texts.

Persists embeddings to disk so server restarts only re-encode specs
whose content has actually changed.
"""

import numpy as np
import hashlib
import json
import time
from pathlib import Path

# Global cache: spec_code → {embeddings: np.ndarray, subtopic_ids: list[str], strands: list[str]}
_cache: dict[str, dict] = {}

DISK_CACHE_DIR = Path(__file__).parent / ".embedding_cache"


def _spec_hash(texts: list[str], subtopic_ids: list[str], strands: list[str]) -> str:
    """Deterministic hash of the inputs that affect embeddings for a spec."""
    payload = json.dumps({"texts": texts, "ids": subtopic_ids, "strands": strands}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _load_from_disk(spec_code: str, expected_hash: str):
    """Try to load cached embeddings from disk. Returns cache entry or None."""
    spec_dir = DISK_CACHE_DIR / spec_code
    hash_file = spec_dir / "hash.txt"
    emb_file = spec_dir / "embeddings.npy"
    meta_file = spec_dir / "meta.json"

    if not (hash_file.exists() and emb_file.exists() and meta_file.exists()):
        return None

    stored_hash = hash_file.read_text().strip()
    if stored_hash != expected_hash:
        return None

    embeddings = np.load(emb_file)
    with open(meta_file, "r") as f:
        meta = json.load(f)

    return {
        "embeddings": embeddings,
        "subtopic_ids": meta["subtopic_ids"],
        "strands": meta["strands"],
    }


def _save_to_disk(spec_code: str, content_hash: str, entry: dict):
    """Persist embeddings to disk for future reloads."""
    spec_dir = DISK_CACHE_DIR / spec_code
    spec_dir.mkdir(parents=True, exist_ok=True)

    np.save(spec_dir / "embeddings.npy", entry["embeddings"])
    with open(spec_dir / "meta.json", "w") as f:
        json.dump({"subtopic_ids": entry["subtopic_ids"], "strands": entry["strands"]}, f)
    (spec_dir / "hash.txt").write_text(content_hash)


def build_cache(allSpecs: dict, model) -> dict:
    """Build cache, loading from disk where possible and only encoding changed specs."""
    DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    new_cache = {}
    total_subtopics = 0
    encoded_count = 0
    cached_count = 0

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

        content_hash = _spec_hash(texts, subtopic_ids, strands)

        # Try disk cache first
        disk_entry = _load_from_disk(spec_code, content_hash)
        if disk_entry is not None:
            new_cache[spec_code] = disk_entry
            cached_count += len(texts)
        else:
            # Must encode
            if texts:
                embeddings = model.encode(texts, show_progress_bar=False)
            else:
                embeddings = np.empty((0, model.get_sentence_embedding_dimension()))

            entry = {
                "embeddings": embeddings,
                "subtopic_ids": subtopic_ids,
                "strands": strands,
            }
            new_cache[spec_code] = entry
            _save_to_disk(spec_code, content_hash, entry)
            encoded_count += len(texts)

        total_subtopics += len(texts)

    # Clean up disk entries for specs no longer in the DB
    if DISK_CACHE_DIR.exists():
        for spec_dir in DISK_CACHE_DIR.iterdir():
            if spec_dir.is_dir() and spec_dir.name not in allSpecs:
                import shutil
                shutil.rmtree(spec_dir)

    return new_cache, total_subtopics, encoded_count, cached_count


def rebuild(allSpecs: dict, model):
    """Rebuild the global cache atomically."""
    global _cache
    t0 = time.time()
    new_cache, total, encoded, cached = build_cache(allSpecs, model)
    _cache = new_cache
    elapsed = time.time() - t0
    print(f"Embedding cache: {len(_cache)} specs, {total} subtopics in {elapsed:.2f}s "
          f"({cached} from disk, {encoded} freshly encoded)")


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
