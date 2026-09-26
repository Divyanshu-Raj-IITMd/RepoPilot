"""Vector store: FAISS when available, exact numpy search otherwise. Persisted to disk."""

from __future__ import annotations

import json
import os

import numpy as np


class VectorStore:
    """Thin wrapper over FAISS IndexFlatIP with a numpy fallback."""

    def __init__(self, dim: int) -> None:
        self.dim = dim
        self._faiss = None
        self._matrix: np.ndarray | None = None
        try:
            import faiss  # noqa: F401  (optional)

            self._faiss = faiss.IndexFlatIP(dim)
        except Exception:
            self._faiss = None

    @property
    def backend(self) -> str:
        return "faiss" if self._faiss is not None else "numpy"

    def add(self, vectors: np.ndarray) -> None:
        if len(vectors) == 0:
            return
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        if self._faiss is not None:
            self._faiss.add(vectors)
        else:
            self._matrix = vectors if self._matrix is None else np.vstack([self._matrix, vectors])

    def search(self, query: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        if self._faiss is not None:
            k = min(k, max(self._faiss.ntotal, 1))
            if self._faiss.ntotal == 0:
                return np.zeros(0), np.zeros(0, dtype=np.int64)
            return self._faiss.search(query.reshape(1, -1).astype(np.float32), k)
        if self._matrix is None or len(self._matrix) == 0:
            return np.zeros(0), np.zeros(0, dtype=np.int64)
        k = min(k, len(self._matrix))
        sims = self._matrix @ query.reshape(-1).astype(np.float32)
        idx = np.argsort(-sims)[:k]
        return sims[idx], idx

    def __len__(self) -> int:
        if self._faiss is not None:
            return self._faiss.ntotal
        return 0 if self._matrix is None else len(self._matrix)

    # ------------------------------------------------------------- persistence

    def save(self, path: str, embedder_state: dict, chunks: list[dict]) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if self._faiss is not None:
            import faiss

            faiss.write_index(self._faiss, path + ".faiss")
            matrix = None
        else:
            matrix = self._matrix
        np.savez_compressed(
            path + ".npz",
            matrix=np.asarray([]) if matrix is None else matrix,
            meta=json.dumps({"embedder_state": embedder_state, "chunks": chunks,
                             "backend": self.backend, "dim": self.dim}),
        )

    @classmethod
    def load(cls, path: str) -> tuple[VectorStore, dict, list[dict]] | None:
        npz_path = path + ".npz"
        if not os.path.exists(npz_path):
            return None
        data = np.load(npz_path, allow_pickle=False)
        meta = json.loads(str(data["meta"]))
        store = cls(dim=meta["dim"])
        if meta["backend"] == "faiss" and os.path.exists(path + ".faiss"):
            import faiss

            store._faiss = faiss.read_index(path + ".faiss")
        else:
            m = data["matrix"]
            if len(m):
                store._matrix = np.asarray(m, dtype=np.float32)
        return store, meta["embedder_state"], meta["chunks"]
