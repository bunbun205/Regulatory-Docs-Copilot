import numpy as np
import pytest

from app.ingest.embedding import (
    SentenceTransformerEmbedder,
    normalize_rows,
)
from tests.helpers import FakeEmbedder


def test_normalize_rows_returns_unit_vectors() -> None:
    vectors = np.array([[3.0, 4.0], [0.0, -2.0]], dtype=np.float32)
    normalized = normalize_rows(vectors)

    assert normalized.shape == (2, 2)
    assert np.linalg.norm(normalized, axis=1) == pytest.approx([1.0, 1.0])


def test_normalize_rows_rejects_zero_and_invalid_shapes() -> None:
    with pytest.raises(ValueError, match="zero vector"):
        normalize_rows(np.zeros((1, 4), dtype=np.float32))
    with pytest.raises(ValueError, match="2-D"):
        normalize_rows(np.array([1.0, 2.0], dtype=np.float32))
    with pytest.raises(ValueError, match="non-finite"):
        normalize_rows(np.array([[np.inf, 1.0]], dtype=np.float32))


def test_fake_embedder_is_deterministic_and_normalized() -> None:
    embedder = FakeEmbedder()
    first = embedder.embed(["alpha", "beta"])
    second = embedder.embed(["alpha", "beta"])

    assert first.shape == (2, 384)
    assert np.array_equal(first, second)
    assert np.linalg.norm(first, axis=1) == pytest.approx([1.0, 1.0])
    assert embedder.calls == 2


def test_empty_sentence_transformer_embed_does_not_load_model() -> None:
    embedder = SentenceTransformerEmbedder(
        "BAAI/bge-small-en-v1.5",
        dimension=384,
    )
    vectors = embedder.embed([])

    assert vectors.shape == (0, 384)
    assert embedder._model is None
