import hashlib
import os

import numpy as np
from sqlalchemy.engine import make_url

TEST_DATABASE_URL = os.environ.get(
    "LABDOCS_TEST_DATABASE_URL",
    "postgresql+asyncpg://labdocs:labdocs@localhost:5432/labdocs_test",
)
TEST_QDRANT_URL = os.environ.get("LABDOCS_TEST_QDRANT_URL", "http://localhost:6333")

_database_name = make_url(TEST_DATABASE_URL).database or ""
if not _database_name.endswith("_test"):
    raise RuntimeError(
        "Refusing to run tests against a database whose name does not end in "
        f"'_test' (got {_database_name!r})."
    )


class FakeEmbedder:
    """Deterministic, fast stand-in for the sentence-transformers model."""

    dimension = 384

    def __init__(self) -> None:
        self.calls = 0
        self.batches: list[list[str]] = []

    def embed(self, texts: list[str]) -> np.ndarray:
        self.calls += 1
        self.batches.append(list(texts))
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        vectors = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for index, text in enumerate(texts):
            seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
            rng = np.random.default_rng(seed)
            vector = rng.standard_normal(self.dimension).astype(np.float32)
            vectors[index] = vector / np.linalg.norm(vector)
        return vectors
