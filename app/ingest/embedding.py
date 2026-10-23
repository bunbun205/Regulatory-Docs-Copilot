import threading
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    """Minimal embedding interface used by ingestion and retrieval."""

    dimension: int

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an ``(len(texts), dimension)`` float32 array."""


def normalize_rows(vectors: np.ndarray) -> np.ndarray:
    """L2-normalize rows and validate shape/finiteness."""
    array = np.asarray(vectors, dtype=np.float32)
    if array.ndim != 2:
        raise ValueError("Embedding output must be a 2-D array.")
    if not np.isfinite(array).all():
        raise ValueError("Embedding output contains non-finite values.")
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("Embedding output contains a zero vector.")
    return array / norms


class SentenceTransformerEmbedder:
    """CPU sentence-transformers embedder, loaded lazily."""

    def __init__(
        self,
        model_name: str,
        dimension: int = 384,
        batch_size: int = 32,
    ) -> None:
        self.model_name = model_name
        self.dimension = dimension
        self.batch_size = batch_size
        self._model: object | None = None
        self._load_lock = threading.Lock()

    def _load(self) -> object:
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    model = SentenceTransformer(self.model_name, device="cpu")
                    model.max_seq_length = 512
                    self._model = model
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        model = self._load()
        vectors = model.encode(  # type: ignore[attr-defined]
            texts,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=False,
        )
        normalized = normalize_rows(np.asarray(vectors, dtype=np.float32))
        if normalized.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding model returned {normalized.shape[1]} dimensions; "
                f"expected {self.dimension}."
            )
        return normalized
