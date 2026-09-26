"""Embeddings for code chunks.

Two backends:
  * HashingTfidfEmbedder — deterministic, dependency-free, offline. Word tokens
    (identifiers split on camelCase/snake_case) + character trigrams hashed
    into a fixed-width TF-IDF vector. Good enough for grounded retrieval and
    used in CI / zero-setup mode.
  * SentenceTransformerEmbedder — neural embeddings (all-MiniLM-L6-v2 by
    default) when `sentence-transformers` is installed. Higher quality.
"""

from __future__ import annotations

import math
import re
import zlib

import numpy as np

from app.config import Settings

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")
_PART_RE = re.compile(r"[a-z0-9]+")

CODE_STOPWORDS = {
    "the", "a", "an", "is", "are", "of", "in", "on", "for", "to", "and", "or",
    "this", "that", "with", "it", "as", "by", "be", "from", "at", "was", "were",
}


def tokenize(text: str) -> list[str]:
    """Split code-ish text into normalized identifier parts + numbers.

    Includes naive plural stemming ('tokens' -> 'token') so natural-language
    queries match code identifiers.
    """
    out: list[str] = []
    for word in _WORD_RE.findall(text):
        low = word.lower()
        for part in _PART_RE.findall(low):
            if part and part not in CODE_STOPWORDS and len(part) > 1:
                if len(part) > 4 and part.endswith("s") and not part.endswith("ss"):
                    part = part[:-1]
                out.append(part)
    return out


def features_of(text: str) -> dict[str, int]:
    """Feature bag: word tokens + char trigrams of tokens + path tokens."""
    feats: dict[str, int] = {}
    for tok in tokenize(text):
        feats[f"w:{tok}"] = feats.get(f"w:{tok}", 0) + 1
        padded = f"^{tok}$"
        for i in range(len(padded) - 2):
            g = f"g:{padded[i:i+3]}"
            feats[g] = feats.get(g, 0) + 1
    return feats


class BaseEmbedder:
    name = "base"
    dim = 0

    def fit(self, texts: list[str]) -> None:  # noqa: D102
        raise NotImplementedError

    def embed(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError

    def state(self) -> dict | None:
        return None

    def load_state(self, state: dict) -> None:
        pass


class HashingTfidfEmbedder(BaseEmbedder):
    """Hashing-trick TF-IDF with deterministic CRC32 feature hashing."""

    name = "hash-tfidf"
    dim = 4096

    def __init__(self) -> None:
        self._idf: np.ndarray | None = None

    def _hash(self, feat: str) -> int:
        return zlib.crc32(feat.encode("utf-8")) % self.dim

    def fit(self, texts: list[str]) -> None:
        n = max(len(texts), 1)
        df = np.zeros(self.dim, dtype=np.float32)
        for text in texts:
            seen: set[int] = set()
            for feat in features_of(text):
                seen.add(self._hash(feat))
            for h in seen:
                df[h] += 1
        self._idf = (np.log((n + 1.0) / (df + 1.0)) + 1.0).astype(np.float32)

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            feats = features_of(text)
            if not feats:
                continue
            tf = np.zeros(self.dim, dtype=np.float32)
            for feat, count in feats.items():
                h = self._hash(feat)
                tf[h] += 1.0 + math.log(count)
            idf = self._idf if self._idf is not None else np.ones(self.dim, dtype=np.float32)
            vec = tf * idf
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec /= norm
            out[i] = vec
        return out

    def state(self) -> dict:
        return {"idf": self._idf.tolist() if self._idf is not None else None}

    def load_state(self, state: dict) -> None:
        idf = state.get("idf")
        self._idf = np.asarray(idf, dtype=np.float32) if idf else None


class SentenceTransformerEmbedder(BaseEmbedder):  # pragma: no cover - optional dep
    """Neural embeddings via sentence-transformers (lazy-loaded)."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        self._model = SentenceTransformer(model_name)
        self.dim = self._model.get_sentence_embedding_dimension() or 384
        self.name = f"sbert:{model_name.split('/')[-1]}"

    def fit(self, texts: list[str]) -> None:
        pass  # stateless encoder

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return np.asarray(vecs, dtype=np.float32)


def get_embedder(settings: Settings) -> BaseEmbedder:
    mode = settings.embedder
    if mode in ("auto", "sbert"):
        try:
            return SentenceTransformerEmbedder(settings.sbert_model)
        except Exception:
            if mode == "sbert":
                raise
            return HashingTfidfEmbedder()
    return HashingTfidfEmbedder()
