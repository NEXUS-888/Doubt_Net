"""
cluster.py
----------
TF-IDF + cosine similarity clustering for grouping similar doubts.
Uses scikit-learn — the only non-standard-library dependency.
Provides auto-clustering plus manual merge/split with single-level undo.
"""

import threading
import copy

_lock = threading.Lock()
_undo_stack = []


def _push_undo(clusters: dict):
    _undo_stack.append(copy.deepcopy(clusters))
    if len(_undo_stack) > 10:
        _undo_stack.pop(0)

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


def auto_cluster(doubts: list, threshold: float = 0.55) -> dict:
    """
    Group approved doubts into clusters based on text similarity.
    Returns { cluster_id: { representative_text, doubt_ids, size, avg_urgency_score } }
    """
    if not HAS_SKLEARN or not doubts:
        return _fallback_cluster(doubts)

    texts = [d["text"] for d in doubts]
    ids = [d["id"] for d in doubts]

    try:
        vectorizer = TfidfVectorizer(stop_words="english", max_features=1000)
        tfidf = vectorizer.fit_transform(texts)
        sim_matrix = cosine_similarity(tfidf)
    except Exception:
        return _fallback_cluster(doubts)

    n = len(doubts)
    assigned = [False] * n
    clusters = {}
    cluster_idx = 0

    for i in range(n):
        if assigned[i]:
            continue
        group = [i]
        assigned[i] = True
        for j in range(i + 1, n):
            if not assigned[j] and sim_matrix[i][j] >= threshold:
                group.append(j)
                assigned[j] = True

        cid = f"c_{cluster_idx:03d}"
        cluster_idx += 1
        group_ids = [ids[idx] for idx in group]
        group_doubts = [doubts[idx] for idx in group]

        scores = []
        for d in group_doubts:
            u = d.get("urgency", "clarification")
            scores.append(1.0 if u == "blocking" else 0.3)

        clusters[cid] = {
            "representative_text": _pick_representative(group_doubts, texts, group),
            "doubt_ids": group_ids,
            "size": len(group_ids),
            "avg_urgency_score": round(sum(scores) / len(scores), 2) if scores else 0,
        }

    return clusters


def _fallback_cluster(doubts: list) -> dict:
    """Fallback when sklearn is unavailable — each doubt is its own cluster."""
    clusters = {}
    for i, d in enumerate(doubts):
        cid = f"c_{i:03d}"
        u = d.get("urgency", "clarification")
        score = 1.0 if u == "blocking" else 0.3
        clusters[cid] = {
            "representative_text": d["text"],
            "doubt_ids": [d["id"]],
            "size": 1,
            "avg_urgency_score": score,
        }
    return clusters


def _pick_representative(doubts: list, texts: list, indices: list) -> str:
    """Pick the longest text in the cluster as representative."""
    if not doubts:
        return ""
    return max(doubts, key=lambda d: len(d.get("text", ""))).get("text", "")


def merge_clusters(clusters: dict, cluster_a: str, cluster_b: str) -> dict:
    """Merge two clusters into one. Keeps a->b merge direction. Returns updated clusters."""
    with _lock:
        _push_undo(clusters)

        if cluster_a not in clusters or cluster_b not in clusters:
            return clusters
        if cluster_a == cluster_b:
            return clusters

        merged_ids = clusters[cluster_a]["doubt_ids"] + clusters[cluster_b]["doubt_ids"]
        merged_doubts_entry = clusters[cluster_a]
        merged_doubts_entry["doubt_ids"] = merged_ids
        merged_doubts_entry["size"] = len(merged_ids)
        merged_urgency = max(clusters[cluster_a]["avg_urgency_score"],
                             clusters[cluster_b]["avg_urgency_score"])
        merged_doubts_entry["avg_urgency_score"] = merged_urgency
        merged_text = clusters[cluster_a]["representative_text"]
        if len(clusters[cluster_b]["representative_text"]) > len(merged_text):
            merged_text = clusters[cluster_b]["representative_text"]
        merged_doubts_entry["representative_text"] = merged_text

        del clusters[cluster_b]
        return clusters


def split_cluster(clusters: dict, cluster_id: str, doubt_ids_to_extract: list) -> dict:
    """Extract doubts from a cluster into a new cluster. Returns updated clusters."""
    with _lock:
        _push_undo(clusters)

        if cluster_id not in clusters:
            return clusters

        remaining = [did for did in clusters[cluster_id]["doubt_ids"]
                     if did not in doubt_ids_to_extract]
        if not remaining or not doubt_ids_to_extract:
            return clusters

        # Update original
        clusters[cluster_id]["doubt_ids"] = remaining
        clusters[cluster_id]["size"] = len(remaining)

        # Create new cluster
        idx = len(clusters)
        new_id = f"c_{idx:03d}"
        while new_id in clusters:
            idx += 1
            new_id = f"c_{idx:03d}"

        clusters[new_id] = {
            "representative_text": "",
            "doubt_ids": doubt_ids_to_extract,
            "size": len(doubt_ids_to_extract),
            "avg_urgency_score": clusters[cluster_id]["avg_urgency_score"],
        }

        return clusters


def undo_last_action(clusters: dict) -> dict:
    """Restore the previous cluster state. Single-level undo."""
    with _lock:
        if _undo_stack:
            return _undo_stack.pop()
        return clusters


def finalize_clusters(clusters: dict) -> dict:
    """Mark clusters as finalized. Returns the clusters as-is (locking happens at store level)."""
    return clusters
