import math

import pytest

from evals.metrics import (
    accuracy,
    bootstrap_ci,
    cohen_kappa,
    f1_score,
    mrr,
    ndcg_at_k,
    percentile,
    precision_at_k,
    prf,
    recall_at_k,
)


def test_recall_at_k():
    ranked = ["a", "b", "c", "d", "e", "f"]
    assert recall_at_k(ranked, ["a", "f"], 5) == 0.5
    assert recall_at_k(ranked, ["a", "b"], 5) == 1.0
    assert recall_at_k(ranked, ["z"], 5) == 0.0
    assert recall_at_k(ranked, [], 5) is None


def test_precision_at_k():
    assert precision_at_k(["a", "b", "c", "d"], ["a", "c"], 4) == 0.5


def test_mrr():
    assert mrr(["x", "a", "b"], ["a", "b"]) == 0.5
    assert mrr(["a"], ["a"]) == 1.0
    assert mrr(["x", "y"], ["a"]) == 0.0
    assert mrr(["x"], []) is None


def test_ndcg():
    # perfect ranking
    assert ndcg_at_k(["a", "b", "x"], ["a", "b"], 10) == pytest.approx(1.0)
    # one relevant at rank 2 of 1 relevant: 1/log2(3)
    assert ndcg_at_k(["x", "a"], ["a"], 10) == pytest.approx(1 / math.log2(3))
    # relevant beyond k
    assert ndcg_at_k(["x", "y", "a"], ["a"], 2) == 0.0
    # duplicates are counted once
    assert ndcg_at_k(["a", "a"], ["a", "b"], 10) == pytest.approx(1 / (1 + 1 / math.log2(3)))
    assert ndcg_at_k(["a"], [], 10) is None


def test_prf_and_f1():
    y = [True, True, False, False, True]
    p = [True, False, True, False, True]
    r = prf(y, p)
    assert (r["tp"], r["fp"], r["fn"], r["tn"]) == (2, 1, 1, 1)
    assert r["precision"] == pytest.approx(2 / 3)
    assert r["recall"] == pytest.approx(2 / 3)
    assert f1_score(y, p) == pytest.approx(2 / 3)
    assert f1_score(["bid", "skip"], ["bid", "bid"], positive="bid") == pytest.approx(2 / 3)
    # no positives predicted and none true: undefined
    assert f1_score([False, False], [False, False]) is None
    assert accuracy([1, 2, 3], [1, 2, 0]) == pytest.approx(2 / 3)


def test_kappa_exact_and_weighted():
    a = [1, 2, 3, 4, 5]
    assert cohen_kappa(a, a) == pytest.approx(1.0)
    assert cohen_kappa(a, a, labels=[1, 2, 3, 4, 5], weights="quadratic") == pytest.approx(1.0)
    # textbook example: 2x2 table [[20, 5], [10, 15]] -> po=0.7, pe=0.5 -> kappa 0.4
    x = ["y"] * 25 + ["n"] * 25
    yb = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    assert cohen_kappa(x, yb) == pytest.approx(0.4)
    # near misses are penalised less under quadratic weights than exact
    r1 = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]
    r2 = [2, 2, 3, 5, 5, 1, 3, 3, 4, 4]
    exact = cohen_kappa(r1, r2, labels=[1, 2, 3, 4, 5])
    quad = cohen_kappa(r1, r2, labels=[1, 2, 3, 4, 5], weights="quadratic")
    assert quad > exact
    assert cohen_kappa([], []) is None


def test_percentile_and_ci():
    vals = [1, 2, 3, 4, 5]
    assert percentile(vals, 50) == 3
    assert percentile(vals, 95) == pytest.approx(4.8)
    assert percentile([], 50) is None
    ci = bootstrap_ci([0.0, 1.0] * 20)
    assert ci[0] < 0.5 < ci[1]
    assert bootstrap_ci([0.0, 1.0] * 20) == ci  # deterministic
