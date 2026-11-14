"""Open embedding and reranker models on CPU via fastembed (ONNX), with a disk cache."""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from functools import lru_cache

import numpy as np

from agent.settings import ROOT, config

CACHE = ROOT / "data" / "cache" / "embeddings.sqlite"
MODEL_CACHE = ROOT / "data" / "cache" / "models"
_lock = threading.Lock()


def _db() -> sqlite3.Connection:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(CACHE, check_same_thread=False)
    con.execute("create table if not exists emb (k text primary key, v blob)")
    return con


@lru_cache(maxsize=4)
def _embedder(name: str):
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=name, cache_dir=str(MODEL_CACHE))


@lru_cache(maxsize=2)
def _reranker(name: str):
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(model_name=name, cache_dir=str(MODEL_CACHE))


def model_name(alt: bool = False) -> str:
    m = config()["models"]
    return m["embeddings_alt"] if alt else m["embeddings"]


def embed(texts: list[str], name: str | None = None, query: bool = False) -> np.ndarray:
    """L2-normalised embeddings. Query vs passage prefixes for models that need them."""
    name = name or model_name()
    prefix = ""
    if "nomic" in name:
        prefix = "search_query: " if query else "search_document: "
    keyed = [(hashlib.sha256(f"{name}|{prefix}{t}".encode()).hexdigest(), prefix + t) for t in texts]
    out: dict[str, np.ndarray] = {}
    with _lock:
        con = _db()
        for k, _ in keyed:
            row = con.execute("select v from emb where k=?", (k,)).fetchone()
            if row:
                out[k] = np.frombuffer(row[0], dtype=np.float32)
        missing = [(k, t) for k, t in keyed if k not in out]
        if missing:
            vecs = list(_embedder(name).embed([t for _, t in missing], batch_size=32))
            con.executemany(
                "insert or replace into emb values (?,?)",
                [(k, np.asarray(v, dtype=np.float32).tobytes()) for (k, _), v in zip(missing, vecs, strict=True)],
            )
            con.commit()
            for (k, _), v in zip(missing, vecs, strict=True):
                out[k] = np.asarray(v, dtype=np.float32)
        con.close()
    mat = np.vstack([out[k] for k, _ in keyed]) if keyed else np.zeros((0, 384), dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    return mat / np.clip(norms, 1e-9, None)


def rerank(query: str, passages: list[str], name: str | None = None) -> list[float]:
    if not passages:
        return []
    name = name or config()["models"]["reranker"]
    return [float(s) for s in _reranker(name).rerank(query, passages)]
