"""Embedder - bge-m3 wrapper with lazy-loaded singleton."""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

_INSTANCES: dict[str, "Embedder"] = {}
_LOCK = threading.Lock()


class Embedder:
    """Sentence embedding model wrapper (default: BAAI/bge-m3, dim=1024).

    The underlying model is loaded lazily on first use so that importing this
    module is cheap and failures surface only when embeddings are actually
    requested (enabling fail-soft handling at the call site).
    """

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy-load the SentenceTransformer model."""
        if self._model is None:
            # Imported lazily so that module import does not pull torch.
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model: %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts (normalized; cosine == dot product)."""
        if not texts:
            return []
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return [v.tolist() for v in vectors]

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text."""
        return self.embed_texts([text])[0]


def get_embedder(model_name: str = "BAAI/bge-m3") -> Embedder:
    """Return a process-wide singleton Embedder for the given model name."""
    with _LOCK:
        if model_name not in _INSTANCES:
            _INSTANCES[model_name] = Embedder(model_name)
        return _INSTANCES[model_name]
