"""
TruthLens AI – Embeddings Module
Generates dense vector embeddings for text using sentence-transformers.
Falls back to a lightweight hash-based mock when the library is unavailable.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
from typing import Union

import numpy as np

logger = logging.getLogger("truthlens.embeddings")

# Default model – small but accurate; swap for larger models as needed.
DEFAULT_MODEL = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)


class EmbeddingEngine:
    """
    Wraps sentence-transformers SentenceTransformer with:
    - Lazy model loading
    - Batch encoding
    - L2 normalisation (for cosine similarity via dot product)
    - Graceful mock fallback
    """

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self._model_name = model_name
        self._model = None
        self._dim: int = 384            # MiniLM dimension; updated on load
        self._load()

    # ──────────────────────────────────────────────────────────────
    # Init
    # ──────────────────────────────────────────────────────────────
    def _load(self):
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            logger.info("Loading embedding model: %s …", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            self._dim = self._model.get_sentence_embedding_dimension()
            logger.info("Embedding model loaded. Dimension: %d", self._dim)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed; using mock embeddings. "
                "Install with: pip install sentence-transformers"
            )

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────
    @property
    def dimension(self) -> int:
        return self._dim

    def encode(
        self,
        texts: Union[str, list[str]],
        batch_size: int = 32,
        normalize: bool = True,
    ) -> np.ndarray:
        """
        Encode one or more texts into embeddings.

        Returns an ndarray of shape (N, dim) where N = len(texts).
        Vectors are L2-normalised when *normalize=True* (default).
        """
        if isinstance(texts, str):
            texts = [texts]

        if self._model:
            vecs = self._model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=normalize,
            )
        else:
            vecs = np.array([self._mock_embedding(t) for t in texts], dtype=np.float32)

        return vecs

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Cosine similarity between two 1-D vectors (or L2-normalised dot product).
        """
        if a.ndim > 1:
            a = a[0]
        if b.ndim > 1:
            b = b[0]
        dot = float(np.dot(a, b))
        norms = np.linalg.norm(a) * np.linalg.norm(b)
        return dot / (norms + 1e-10)

    # ──────────────────────────────────────────────────────────────
    # Mock fallback
    # ──────────────────────────────────────────────────────────────
    def _mock_embedding(self, text: str) -> np.ndarray:
        """
        Deterministic pseudo-embedding derived from the text hash.
        NOT semantically meaningful – only for offline testing.
        """
        digest = hashlib.sha256(text.encode()).digest()
        # Expand 32 bytes to *dim* floats via simple trig spreading
        rng = np.frombuffer(digest, dtype=np.uint8).astype(np.float32) / 255.0
        # Tile to required dimension
        repeats = math.ceil(self._dim / len(rng))
        vec = np.tile(rng, repeats)[: self._dim]
        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-10)


# Module-level singleton – import and use directly:
#   from app.embeddings import engine
#   vecs = engine.encode(["hello world"])
engine = EmbeddingEngine()
