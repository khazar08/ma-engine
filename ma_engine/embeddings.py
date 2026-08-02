"""Business-description embeddings for adjacency scoring and peer auto-selection.

Abstracted behind ``Embedder`` so the concrete model can be swapped. The default
``TfidfEmbedder`` needs no downloads and is fully deterministic (good for tests
and offline runs); ``SentenceTransformerEmbedder`` uses sentence-transformers
when available for richer semantic adjacency — this is what surfaces non-obvious
adjacencies a keyword screen would miss.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class Embedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (n, d) matrix of embeddings for the given texts."""

    def similarity_matrix(self, texts: list[str]) -> np.ndarray:
        vecs = self.embed(texts)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        unit = vecs / norms
        return unit @ unit.T


class TfidfEmbedder(Embedder):
    """Deterministic TF-IDF embedder (scikit-learn). No network required."""

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectorizer = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2), min_df=1, sublinear_tf=True
        )

    def embed(self, texts: list[str]) -> np.ndarray:
        # fit_transform on the corpus so the vector space is defined by the universe
        mat = self._vectorizer.fit_transform(texts)
        return np.asarray(mat.todense())


class SentenceTransformerEmbedder(Embedder):
    """Semantic embedder using sentence-transformers (optional dependency)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self._model.encode(texts, normalize_embeddings=False))


def get_embedder(prefer_semantic: bool = False) -> Embedder:
    """Return the best available embedder.

    Falls back to TF-IDF if sentence-transformers is not installed, so the engine
    always works offline.
    """
    if prefer_semantic:
        try:
            return SentenceTransformerEmbedder()
        except Exception:
            pass
    return TfidfEmbedder()
