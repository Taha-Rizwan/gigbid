"""Metric functions used by every eval runner. Pure Python, no I/O, unit-tested in
tests/unit/test_metrics.py."""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Sequence

# ----------------------------------------------------------------------------- retrieval

def recall_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float | None:
    """Share of the relevant items found in the top k. None when there is nothing relevant."""
    rel = set(relevant)
    if not rel:
        return None
    return len(set(ranked[:k]) & rel) / len(rel)


def precision_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float | None:
    rel = set(relevant)
    if not rel or k <= 0:
        return None
    return len([r for r in ranked[:k] if r in rel]) / k


def mrr(ranked: Sequence[str], relevant: Iterable[str]) -> float | None:
    """Reciprocal rank of the first relevant item (0 if none is retrieved)."""
    rel = set(relevant)
    if not rel:
        return None
    for i, r in enumerate(ranked, start=1):
        if r in rel:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float | None:
    """Binary-relevance nDCG@k. Duplicate ids in `ranked` only count once."""
    rel = set(relevant)
    if not rel:
        return None
    seen: set[str] = set()
    dcg = 0.0
    for i, r in enumerate(ranked[:k], start=1):
        if r in rel and r not in seen:
            dcg += 1.0 / math.log2(i + 1)
        seen.add(r)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(rel), k) + 1))
    return dcg / ideal if ideal else 0.0


# ----------------------------------------------------------------------------- classification

def prf(y_true: Sequence, y_pred: Sequence, positive=True) -> dict[str, float | int | None]:
    """Precision, recall and F1 for one positive class, plus the confusion counts."""
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred differ in length")
    tp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == positive and p == positive)
    fp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t != positive and p == positive)
    fn = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == positive and p != positive)
    tn = len(y_true) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    if precision is None or recall is None or precision + recall == 0:
        f1 = 0.0 if (tp + fp) and (tp + fn) else None
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "n": len(y_true)}


def f1_score(y_true: Sequence, y_pred: Sequence, positive=True) -> float | None:
    return prf(y_true, y_pred, positive)["f1"]


def accuracy(y_true: Sequence, y_pred: Sequence) -> float | None:
    if not y_true:
        return None
    return sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == p) / len(y_true)


def macro_f1(y_true: Sequence, y_pred: Sequence) -> float | None:
    labels = sorted(set(y_true) | set(y_pred), key=str)
    scores = [prf(y_true, y_pred, lab)["f1"] for lab in labels]
    scores = [s for s in scores if s is not None]
    return sum(scores) / len(scores) if scores else None


# ----------------------------------------------------------------------------- agreement

def cohen_kappa(a: Sequence, b: Sequence, labels: Sequence | None = None, weights: str | None = None) -> float | None:
    """Cohen's kappa between two raters. weights=None (exact), "linear" or "quadratic".
    Weighted variants need ordinal labels (given in order via `labels`, or sortable)."""
    if len(a) != len(b):
        raise ValueError("raters differ in length")
    n = len(a)
    if n == 0:
        return None
    labels = list(labels) if labels is not None else sorted(set(a) | set(b))
    idx = {lab: i for i, lab in enumerate(labels)}
    m = len(labels)
    if m < 2:
        return None
    obs = [[0.0] * m for _ in range(m)]
    for x, y in zip(a, b, strict=True):
        obs[idx[x]][idx[y]] += 1
    row = [sum(obs[i]) for i in range(m)]
    col = [sum(obs[i][j] for i in range(m)) for j in range(m)]

    def w(i: int, j: int) -> float:
        if weights is None:
            return 0.0 if i == j else 1.0
        d = abs(i - j) / (m - 1)
        return d if weights == "linear" else d * d

    observed = sum(w(i, j) * obs[i][j] for i in range(m) for j in range(m)) / n
    expected = sum(w(i, j) * row[i] * col[j] for i in range(m) for j in range(m)) / (n * n)
    if expected == 0:
        return 1.0 if observed == 0 else None
    return 1.0 - observed / expected


# ----------------------------------------------------------------------------- summaries

def percentile(values: Sequence[float], p: float) -> float | None:
    """Linear-interpolated percentile (same as numpy's default), p in 0..100."""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    if len(vals) == 1:
        return float(vals[0])
    pos = (len(vals) - 1) * p / 100.0
    lo, hi = math.floor(pos), math.ceil(pos)
    return float(vals[lo] + (vals[hi] - vals[lo]) * (pos - lo))


def mean(values: Iterable[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def bootstrap_ci(values: Sequence[float | None], iters: int = 1000, alpha: float = 0.05,
                 seed: int = 0) -> list[float] | None:
    """Percentile bootstrap CI of the mean (fixed seed, so reruns give the same interval)."""
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return None
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(vals, k=len(vals))) / len(vals) for _ in range(iters))
    return [means[int(alpha / 2 * iters)], means[int((1 - alpha / 2) * iters) - 1]]


def rounded(x, nd: int = 4):
    if x is None:
        return None
    if isinstance(x, float):
        return round(x, nd)
    if isinstance(x, dict):
        return {k: rounded(v, nd) for k, v in x.items()}
    if isinstance(x, list):
        return [rounded(v, nd) for v in x]
    return x
