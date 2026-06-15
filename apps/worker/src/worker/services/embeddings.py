from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


class EmbeddingService:
    """BAAI/bge-m3 wrapper (1024-dim, multilingual uz+ru).

    Load once at worker startup; reuse across all jobs in that process.
    """

    DIM = 1024
    DEFAULT_MODEL = "BAAI/bge-m3"

    def __init__(self) -> None:
        self._model: object | None = None

    def load(self, model_name: str = DEFAULT_MODEL) -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

        self._model = SentenceTransformer(model_name)

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _require_model(self) -> object:
        if self._model is None:
            raise RuntimeError("EmbeddingService.load() must be called before embedding")
        return self._model

    def embed(self, text: str) -> list[float]:
        model = self._require_model()
        vec: NDArray[np.float32] = model.encode(  # type: ignore[attr-defined]
            text, normalize_embeddings=True, convert_to_numpy=True
        )
        return vec.tolist()

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        model = self._require_model()
        vecs: NDArray[np.float32] = model.encode(  # type: ignore[attr-defined]
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            batch_size=batch_size,
        )
        return vecs.tolist()
