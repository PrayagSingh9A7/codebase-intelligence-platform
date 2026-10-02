from __future__ import annotations

from typing import Sequence
import numpy as np

class Embedder:
    """Use sentence-transformers when available; deterministic fallback keeps the demo runnable."""
    def __init__(self) -> None:
        self.model = None
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            self.model = None

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if self.model:
            return np.asarray(self.model.encode(list(texts), normalize_embeddings=True), dtype=np.float32)
        vectors = []
        for text in texts:
            seed = np.frombuffer(text.encode("utf-8")[:512].ljust(512, b"0"), dtype=np.uint8).astype(np.float32)
            v = np.resize(seed, 384)
            v = v - v.mean()
            norm = np.linalg.norm(v) or 1.0
            vectors.append(v / norm)
        return np.asarray(vectors, dtype=np.float32)
