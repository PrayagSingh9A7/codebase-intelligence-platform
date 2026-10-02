from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import numpy as np


@dataclass
class Hit:
    payload: dict
    score: float


class LocalVectorStore:
    """Tiny in-memory vector store with cosine search; swap for Qdrant in production."""
    def __init__(self) -> None:
        self.vectors: np.ndarray | None = None
        self.payloads: list[dict] = []

    def clear(self) -> None:
        self.vectors = None
        self.payloads = []

    def upsert(self, vectors: np.ndarray, payloads: Iterable[dict]) -> None:
        vectors = np.asarray(vectors, dtype=np.float32)
        self.vectors = vectors if self.vectors is None else np.vstack([self.vectors, vectors])
        self.payloads.extend(list(payloads))

    def search(self, vector: np.ndarray, limit: int = 5) -> list[Hit]:
        if self.vectors is None or not self.payloads:
            return []
        query = np.asarray(vector, dtype=np.float32)
        scores = self.vectors @ query
        top = np.argsort(scores)[::-1][:limit]
        return [Hit(self.payloads[int(i)], float(scores[int(i)])) for i in top]
